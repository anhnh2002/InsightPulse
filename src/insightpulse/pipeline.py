"""One pipeline pass: collect → extract → dedup → triage → enrich → write → queue."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from insightpulse import queue as review_queue
from insightpulse.agents.linkedin_extractor import extract_posts
from insightpulse.agents.triage import arxiv_id_from_url, triage_posts
from insightpulse.agents.writer import write_blog
from insightpulse.config import load_kols, load_settings
from insightpulse.dates import parse_post_date, yesterday_utc
from insightpulse.enrich import arxiv as arxiv_enrich
from insightpulse.enrich import figures as figures_enrich
from insightpulse.enrich import github as github_enrich
from insightpulse.models import Kind, RawPost, Source, TriageResult
from insightpulse.paths import RAW_DIR, RUN_LOCK, RUNS_DIR, ensure_dirs
from insightpulse.sources import linkedin_source, x_source
from insightpulse.state import State, new_run_id

log = logging.getLogger(__name__)

SHORTENER_HOSTS = ("lnkd.in", "t.co", "buff.ly", "bit.ly", "tinyurl.com")


class RunLocked(RuntimeError):
    pass


def _acquire_lock() -> None:
    if RUN_LOCK.exists():
        pid = RUN_LOCK.read_text().strip()
        raise RunLocked(
            f"another run appears to be in progress (pid {pid}); "
            f"remove {RUN_LOCK} if it is stale"
        )
    RUN_LOCK.write_text(str(os.getpid()))


def _release_lock() -> None:
    RUN_LOCK.unlink(missing_ok=True)


_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
# lnkd.in serves an interstitial page instead of a redirect; the target is in
# an anchor tagged external_url_click
_INTERSTITIAL_RES = (
    re.compile(r'data-tracking-control-name="external_url_click"[^>]*href="([^"]+)'),
    re.compile(r'<a[^>]+href="(https?://(?!lnkd\.in|www\.linkedin\.com)[^"]+)"'),
)


def _resolve_short_links(urls: list[str]) -> list[str]:
    """Follow shorteners (lnkd.in, t.co, ...) so triage sees the real targets."""
    resolved = []
    for u in urls:
        if any(h in u for h in SHORTENER_HOSTS):
            try:
                resp = httpx.get(u, follow_redirects=True, timeout=15, headers=_UA)
                final = str(resp.url)
                if any(h in final for h in SHORTENER_HOSTS):
                    for pat in _INTERSTITIAL_RES:
                        m = pat.search(resp.text)
                        if m:
                            final = m.group(1)
                            break
                resolved.append(final)
                continue
            except httpx.HTTPError:
                pass
        resolved.append(u)
    return resolved


def collect_x(state: State, run_id: str, target_date: date) -> list[tuple[str, RawPost]]:
    new_items = []
    for kol in load_kols().x:
        try:
            posts = x_source.fetch_user_posts_for_day(kol.handle, target_date, kol.max_posts)
        except Exception as e:
            log.error("X collect failed for @%s: %s", kol.handle, e)
            continue
        for p in posts:
            item_id = state.insert_post(p, run_id)
            if item_id:
                new_items.append((item_id, p))
    return new_items


def collect_linkedin(state: State, run_id: str, run_dir: Path,
                     target_date: date) -> list[tuple[str, RawPost]]:
    new_items = []
    now = datetime.now(timezone.utc)
    age_days = (now.date() - target_date).days
    if age_days > 7:
        # LinkedIn only shows relative ages; beyond ~a week the granularity is
        # weeks/months, so bucketing posts into a specific day is meaningless.
        log.warning("LinkedIn: target day %s is %d days old — relative dates too "
                    "coarse, skipping LinkedIn", target_date, age_days)
        return new_items
    for kol in load_kols().linkedin:
        try:
            raw = linkedin_source.fetch_kol_raw(kol)
        except linkedin_source.LinkedInRateLimited as e:
            log.warning("LinkedIn rate-limited (%s) — skipping rest of LinkedIn", e)
            break
        except Exception as e:
            log.error("LinkedIn collect failed for %s: %s", kol.id, e)
            continue
        raw_path = RAW_DIR / run_id / f"linkedin_{kol.id}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(raw, indent=2))
        try:
            posts = extract_posts(kol.id, raw, run_dir / "logs")
        except Exception as e:
            log.error("LinkedIn extraction failed for %s: %s", kol.id, e)
            continue
        in_window, new = 0, 0
        for p in posts:
            est = parse_post_date(p.created_at, now)
            if est is not None:
                p.created_at = est.isoformat()
                if est != target_date:
                    continue
            elif age_days > 1:
                # unknown date: only trust it as "fresh" on a current-day run
                continue
            in_window += 1
            item_id = state.insert_post(p, run_id)
            if item_id:
                new += 1
                new_items.append((item_id, p))
        log.info("LinkedIn %s: %d posts extracted, %d within %s, %d new",
                 kol.id, len(posts), in_window, target_date, new)
    return new_items


def triage_new(state: State, new_items: list[tuple[str, RawPost]],
               run_dir: Path) -> list[tuple[str, RawPost, TriageResult]]:
    settings = load_settings()
    triaged = []
    batch_size = settings.limits.triage_batch_size
    for bi in range(0, len(new_items), batch_size):
        batch = new_items[bi:bi + batch_size]
        payload = [
            {
                "post_id": item_id,
                "kol": p.kol,
                "source": p.source.value,
                "text": p.text[:4000],
                "urls": _resolve_short_links(p.urls),
            }
            for item_id, p in batch
        ]
        try:
            results = triage_posts(payload, run_dir / "logs", f"batch{bi}")
        except Exception as e:
            log.error("triage batch %d failed: %s", bi, e)
            for item_id, _ in batch:
                state.set_status(item_id, "failed:triage", str(e)[:500])
            continue
        by_id = {r.post_id: r for r in results}
        for item_id, p in batch:
            r = by_id.get(item_id)
            if r is None:
                continue
            arxiv_id = arxiv_id_from_url(r.arxiv_url) if r.arxiv_url else ""
            if arxiv_id and state.arxiv_seen(arxiv_id, exclude_item=item_id):
                log.info("item %s: paper %s already covered, skipping", item_id, arxiv_id)
                state.set_triage(item_id, Kind.skip, r.links, r.working_title, arxiv_id)
                continue
            state.set_triage(item_id, r.kind, r.links, r.working_title, arxiv_id)
            if r.kind != Kind.skip:
                triaged.append((item_id, p, r))
    return triaged


def process_item(state: State, item_id: str, post: RawPost, tri: TriageResult,
                 run_id: str, run_dir: Path, target_date: date) -> None:
    """Enrich one triaged item and run the writer agent on it."""
    settings = load_settings()
    workdir = run_dir / "items" / item_id
    workdir.mkdir(parents=True, exist_ok=True)

    kind = tri.kind
    paper_meta = None
    repo_meta = None
    meta: dict = {
        "kind": kind.value,
        "social_post": {
            "source": post.source.value,
            "kol": post.kol,
            "author": post.author_name,
            "text": post.text,
            "permalink": post.permalink,
            "created_at": post.created_at,
        },
        "links": tri.links,
        "working_title": tri.working_title,
    }

    arxiv_id = arxiv_id_from_url(tri.arxiv_url) if tri.arxiv_url else ""
    if kind == Kind.paper and not arxiv_id:
        # Paper without a resolvable arXiv link: treat as news over the post text
        log.info("item %s: paper without arxiv link, writing as news", item_id)
        kind = Kind.news

    if kind == Kind.paper:
        paper_meta = arxiv_enrich.fetch_meta(arxiv_id)
        meta["paper"] = paper_meta.model_dump()
        res = arxiv_enrich.fetch_paper_html(paper_meta)
        if res:
            page_url, html = res
            text = arxiv_enrich._strip_html(html)[:settings.limits.paper_text_chars]
            figs = figures_enrich.extract_html_figures(html, page_url, workdir)
        else:
            log.warning("arxiv %s: falling back to abstract only", arxiv_id)
            text = f"{paper_meta.title}\n\nAbstract: {paper_meta.abstract}"
            figs = []
        if not figs and paper_meta.pdf_url:
            figs = figures_enrich.extract_pdf_figures(paper_meta.pdf_url, workdir)
        figures_enrich.write_manifest(figs, workdir)
        (workdir / "paper.txt").write_text(text)
    else:
        chunks = []
        for url in [u for u in ([tri.github_url] + tri.links) if u][:3]:
            page = arxiv_enrich.fetch_page_text(url, settings.limits.news_text_chars)
            if page:
                chunks.append(f"### content from {url}\n{page}")
        (workdir / "content.txt").write_text(
            "\n\n".join(chunks)[:settings.limits.news_text_chars]
        )

    if tri.github_url:
        repo_meta = github_enrich.fetch_repo_meta(tri.github_url)
        if repo_meta:
            meta["repo"] = repo_meta.model_dump()

    (workdir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    state.set_status(item_id, "enriched")

    # date the draft by the post's own day; leftovers from earlier runs keep theirs
    draft_date = parse_post_date(post.created_at, datetime.now(timezone.utc)) or target_date
    draft = write_blog(
        item_id=item_id,
        kind=kind,
        source=post.source,
        kol=post.kol,
        source_url=post.permalink,
        workdir=workdir,
        output_dir=run_dir / "logs",
        run_id=run_id,
        paper=paper_meta,
        repo=repo_meta,
        date_str=draft_date.isoformat(),
        social={
            "text": post.text[:500],
            "author": post.author_name or post.kol,
            "created_at": post.created_at,
        },
    )
    review_queue.write_draft(draft, workdir=workdir)
    state.set_status(item_id, "drafted")


def _row_to_post(row) -> RawPost:
    return RawPost(
        source=Source(row["source"]),
        kol=row["kol"],
        external_id=row["external_id"],
        text=row["post_text"],
        urls=json.loads(row["links_json"]),
        created_at=row["posted_at"],
        permalink=row["url"],
    )


def _untriaged_items(state: State, exclude_ids: set[str]) -> list[tuple[str, RawPost]]:
    """Items collected in earlier runs (dry-run, or failed triage) never triaged."""
    items = []
    for status in ("collected", "failed:triage"):
        for row in state.items_by_status(status):
            if row["id"] not in exclude_ids:
                items.append((row["id"], _row_to_post(row)))
    return items


def _leftover_items(state: State, exclude_ids: set[str]) -> list[tuple[str, RawPost, TriageResult]]:
    """Items triaged in earlier runs but never drafted (over-limit or failed writes)."""
    leftovers = []
    for status in ("triaged", "enriched", "failed:write"):
        for row in state.items_by_status(status):
            if row["id"] in exclude_ids or not row["kind"]:
                continue
            post = _row_to_post(row)
            links = json.loads(row["links_json"])
            tri = TriageResult(
                post_id=row["dedup_key"],
                kind=Kind(row["kind"]),
                arxiv_url=f"https://arxiv.org/abs/{row['arxiv_id']}" if row["arxiv_id"] else "",
                github_url=next((u for u in links if "github.com" in u), ""),
                links=links,
                working_title=row["title"],
            )
            leftovers.append((row["id"], post, tri))
    return leftovers


def run_pipeline(source: str = "all", limit: int | None = None,
                 dry_run: bool = False, target_date: date | None = None) -> dict:
    """Execute one pipeline pass covering a single UTC day. Returns counts."""
    ensure_dirs()
    settings = load_settings()
    limit = limit if limit is not None else settings.limits.items_per_run
    target_date = target_date or yesterday_utc()
    _acquire_lock()
    run_id = new_run_id(target_date)
    run_dir = RUNS_DIR / run_id
    counts = {"collected": 0, "triaged": 0, "drafted": 0, "failed": 0}
    try:
        with State() as state:
            state.start_run(run_id, target_date.isoformat())

            new_items: list[tuple[str, RawPost]] = []
            if source in ("all", "x"):
                new_items += collect_x(state, run_id, target_date)
            if source in ("all", "linkedin"):
                new_items += collect_linkedin(state, run_id, run_dir, target_date)
            counts["collected"] = len(new_items)
            log.info("run %s (day %s): %d new posts", run_id, target_date, len(new_items))

            if dry_run:
                state.finish_run(run_id, counts)
                return counts

            new_items += _untriaged_items(state, {i for i, _ in new_items})
            triaged = triage_new(state, new_items, run_dir) if new_items else []
            counts["triaged"] = len(triaged)

            leftovers = _leftover_items(state, {i for i, _, _ in triaged})
            if leftovers:
                log.info("run %s: picking up %d leftover items from earlier runs",
                         run_id, len(leftovers))
            work = triaged + leftovers

            for item_id, post, tri in work[:limit]:
                try:
                    process_item(state, item_id, post, tri, run_id, run_dir, target_date)
                    counts["drafted"] += 1
                except Exception as e:
                    log.exception("item %s failed", item_id)
                    state.set_status(item_id, "failed:write", str(e)[:500])
                    counts["failed"] += 1
            if len(work) > limit:
                log.info("run %s: %d triaged items beyond --limit left for next run",
                         run_id, len(work) - limit)

            state.finish_run(run_id, counts)
    finally:
        _release_lock()
    log.info("run %s finished: %s", run_id, counts)
    return counts
