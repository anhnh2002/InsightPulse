"""One pipeline pass: collect → extract → dedup → triage → enrich → write → queue."""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from insightpulse import queue as review_queue
from insightpulse.agents.linkedin_crawler import crawl_linkedin
from insightpulse.agents.triage import triage_posts
from insightpulse.agents.writer import write_blog
from insightpulse.config import load_kols, load_settings
from insightpulse.dates import parse_post_date, yesterday_utc
from insightpulse.enrich import arxiv as arxiv_enrich
from insightpulse.enrich.arxiv import arxiv_id_from_url
from insightpulse.enrich import figures as figures_enrich
from insightpulse.enrich import github as github_enrich
from insightpulse.models import Kind, RawPost, Source, TriageResult
from insightpulse.paths import RAW_DIR, RUN_LOCK, RUNS_DIR, ensure_dirs
from insightpulse.publish import accept_draft, rebuild_site
from insightpulse.sources import x_source
from insightpulse.state import State, new_run_id

log = logging.getLogger(__name__)

SHORTENER_HOSTS = ("t.co", "buff.ly", "bit.ly", "tinyurl.com")


class RunLocked(RuntimeError):
    pass


def _acquire_lock() -> None:
    # O_EXCL makes create-if-absent atomic: two concurrent runs cannot both
    # pass an exists() check and clobber each other's lock.
    try:
        fd = os.open(RUN_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            pid = RUN_LOCK.read_text().strip() or "unknown"
        except OSError:
            pid = "unknown"
        raise RunLocked(
            f"another run appears to be in progress (pid {pid}); "
            f"remove {RUN_LOCK} if it is stale"
        ) from None
    with os.fdopen(fd, "w") as f:
        f.write(str(os.getpid()))


def _release_lock() -> None:
    RUN_LOCK.unlink(missing_ok=True)


_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def _resolve_short_links(urls: list[str]) -> list[str]:
    """Follow shorteners (t.co, ...) so triage sees the real targets."""
    resolved = []
    for u in urls:
        if any(h in u for h in SHORTENER_HOSTS):
            try:
                resp = httpx.get(u, follow_redirects=True, timeout=15, headers=_UA)
                resolved.append(str(resp.url))
                continue
            except httpx.HTTPError:
                pass
        resolved.append(u)
    return resolved


def collect_x(state: State, run_id: str, start: date,
              end: date) -> list[tuple[str, RawPost]]:
    new_items = []
    for kol in load_kols().x:
        day = start
        while day <= end:
            try:
                posts = x_source.fetch_user_posts_for_day(kol.handle, day, kol.max_posts)
            except Exception as e:
                log.error("X collect failed for @%s (%s): %s", kol.handle, day, e)
                day += timedelta(days=1)
                continue
            for p in posts:
                item_id = state.insert_post(p, run_id)
                if item_id:
                    new_items.append((item_id, p))
            day += timedelta(days=1)
    return new_items


def collect_linkedin(state: State, run_id: str, run_dir: Path, start: date,
                     end: date, backfill: bool = False) -> list[tuple[str, RawPost]]:
    new_items = []
    age_days = (datetime.now(timezone.utc).date() - start).days
    if age_days > 35:
        # LinkedIn only shows relative ages; beyond ~a month the granularity is
        # months, so window coverage becomes unreliable. Crawl anyway.
        log.warning("LinkedIn: window start %s is %d days old — month-granularity "
                    "dates make coverage unreliable", start, age_days)
    try:
        posts, rate_limited = crawl_linkedin(
            load_kols().linkedin, start, end, RAW_DIR / run_id, run_dir / "logs",
            backfill=backfill,
        )
    except Exception as e:
        log.error("LinkedIn crawl failed: %s", e)
        return new_items
    if rate_limited:
        log.warning("LinkedIn: rate-limited KOLs skipped this run: %s",
                    ", ".join(sorted(rate_limited)))
    new = 0
    for p in posts:
        if p.external_id:
            # Transition guard: rows collected before activity-id dedup existed
            # are keyed by text hash — don't re-insert them under the new key.
            legacy_key = p.model_copy(update={"external_id": ""}).dedup_key
            if state.has_dedup_key(legacy_key):
                continue
        item_id = state.insert_post(p, run_id)
        if item_id:
            new += 1
            new_items.append((item_id, p))
    log.info("LinkedIn crawl: %d posts in window %s..%s, %d new",
             len(posts), start, end, new)
    if new_items:
        (RAW_DIR / run_id).mkdir(parents=True, exist_ok=True)
        (RAW_DIR / run_id / "collected_posts.json").write_text(json.dumps(
            [p.model_dump(mode="json") for _, p in new_items],
            indent=2, ensure_ascii=False))
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
                "paper_name": p.paper_name,
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
            paper_name = r.paper_name or p.paper_name
            arxiv_id = arxiv_id_from_url(r.arxiv_url) if r.arxiv_url else ""
            if not arxiv_id and r.kind == Kind.paper:
                # LinkedIn posts carry no links — resolve the paper by name.
                for name in (paper_name, r.working_title):
                    if name:
                        arxiv_id = arxiv_enrich.search_by_title(
                            name,
                            min_recall=settings.arxiv.title_min_recall,
                            ambiguity_margin=settings.arxiv.title_ambiguity_margin,
                        )
                    if arxiv_id:
                        break
                if arxiv_id:
                    r.arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
            if arxiv_id and state.arxiv_seen(arxiv_id, exclude_item=item_id):
                log.info("item %s: paper %s already covered, skipping", item_id, arxiv_id)
                state.set_triage(item_id, Kind.skip, r.links, r.working_title,
                                 arxiv_id, paper_name)
                continue
            state.set_triage(item_id, r.kind, r.links, r.working_title, arxiv_id,
                             paper_name)
            if r.kind == Kind.paper and not arxiv_id:
                # Unresolvable paper: park it for a manual link fill in the
                # admin (/admin/links) instead of spending a writer call.
                log.info("item %s: paper %r has no arXiv link — needs manual fill",
                         item_id, paper_name or r.working_title)
                state.set_status(item_id, "needs_link")
                continue
            if r.kind != Kind.skip:
                triaged.append((item_id, p, r))
    return triaged


def process_item(state: State, item_id: str, post: RawPost, tri: TriageResult,
                 run_id: str, run_dir: Path, fallback_date: date) -> bool:
    """Enrich one triaged item and run the writer agent on it.

    Returns False when the item turned out to be a duplicate and was skipped.
    """
    settings = load_settings()
    workdir = run_dir / "items" / item_id
    workdir.mkdir(parents=True, exist_ok=True)

    kind = tri.kind
    arxiv_id = arxiv_id_from_url(tri.arxiv_url) if tri.arxiv_url else ""
    if kind == Kind.paper and not arxiv_id:
        # Safety net — triage should have parked these already.
        log.info("item %s: paper without arxiv link, parking as needs_link", item_id)
        state.set_status(item_id, "needs_link")
        return False
    paper_meta = None
    repo_meta = None
    meta: dict = {
        "kind": kind.value,
        "links": tri.links,
        "paper_name": tri.paper_name,
        "working_title": tri.working_title,
    }
    # manually added items have no social post — don't fabricate an empty one
    if post.text or post.permalink:
        meta["social_post"] = {
            "source": post.source.value,
            "kol": post.kol,
            "author": post.author_name,
            "text": post.text,
            "permalink": post.permalink,
            "created_at": post.created_at,
        }

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

    # papers are dated by their arXiv publication day; everything else by the
    # post's own day (leftovers from earlier runs keep theirs)
    draft_date = parse_post_date(post.created_at, datetime.now(timezone.utc)) or fallback_date
    if paper_meta and paper_meta.published:
        try:
            draft_date = date.fromisoformat(paper_meta.published)
        except ValueError:
            pass
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
        } if (post.text or post.permalink) else None,
    )
    review_queue.write_draft(draft, workdir=workdir)
    state.set_status(item_id, "drafted")
    return True


def _row_to_post(row) -> RawPost:
    return RawPost(
        source=Source(row["source"]),
        kol=row["kol"],
        external_id=row["external_id"],
        text=row["post_text"],
        urls=json.loads(row["links_json"]),
        paper_name=row["paper_name"],
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
            if row["kind"] == Kind.paper.value and not row["arxiv_id"]:
                # Pre-needs_link rows: park them for a manual link fill.
                log.info("item %s: paper %r has no arXiv link — needs manual fill",
                         row["id"], row["paper_name"] or row["title"])
                state.set_status(row["id"], "needs_link")
                continue
            post = _row_to_post(row)
            links = json.loads(row["links_json"])
            tri = TriageResult(
                post_id=row["dedup_key"],
                kind=Kind(row["kind"]),
                arxiv_url=f"https://arxiv.org/abs/{row['arxiv_id']}" if row["arxiv_id"] else "",
                github_url=next((u for u in links if "github.com" in u), ""),
                links=links,
                paper_name=row["paper_name"],
                working_title=row["title"],
            )
            leftovers.append((row["id"], post, tri))
    return leftovers


def run_pipeline(sources: set[Source] | None = None, limit: int | None = None,
                 dry_run: bool = False, start_date: date | None = None,
                 end_date: date | None = None, auto_accept: bool | None = None,
                 kinds: set[Kind] | None = None, backfill: bool = False) -> dict:
    """Execute one pipeline pass covering a UTC day window. Returns counts."""
    ensure_dirs()
    settings = load_settings()
    # sources=set() is meaningful: process already-collected items, crawl nothing
    sources = set(Source) if sources is None else sources
    kinds = kinds or {Kind.paper, Kind.news}
    if limit is None:
        # A backfill is one deliberate catch-up pass: write everything that is
        # ready instead of draining items_per_run per run.
        limit = 10 ** 9 if backfill else settings.limits.items_per_run
    auto_accept = auto_accept if auto_accept is not None else settings.review.auto_accept
    end_date = end_date or yesterday_utc()
    start_date = start_date or end_date
    if start_date > end_date:
        raise ValueError(f"start_date {start_date} is after end_date {end_date}")
    window = (start_date.isoformat() if start_date == end_date
              else f"{start_date}..{end_date}")
    _acquire_lock()
    run_id = new_run_id(end_date)
    run_dir = RUNS_DIR / run_id
    counts = {"collected": 0, "triaged": 0, "drafted": 0, "failed": 0}
    if auto_accept:
        counts["accepted"] = 0
    try:
        with State() as state:
            state.start_run(run_id, window)

            new_items: list[tuple[str, RawPost]] = []
            if Source.x in sources:
                new_items += collect_x(state, run_id, start_date, end_date)
            if Source.linkedin in sources:
                new_items += collect_linkedin(state, run_id, run_dir, start_date,
                                              end_date, backfill)
            counts["collected"] = len(new_items)
            log.info("run %s (window %s): %d new posts", run_id, window, len(new_items))

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

            deferred = [w for w in work if w[2].kind not in kinds]
            if deferred:
                log.info("run %s: %d items outside --kind %s stay triaged for a "
                         "later run", run_id, len(deferred),
                         ",".join(sorted(k.value for k in kinds)))
                work = [w for w in work if w[2].kind in kinds]

            for item_id, post, tri in work[:limit]:
                try:
                    if not process_item(state, item_id, post, tri, run_id, run_dir,
                                        end_date):
                        continue
                    counts["drafted"] += 1
                except Exception as e:
                    log.exception("item %s failed", item_id)
                    state.set_status(item_id, "failed:write", str(e)[:500])
                    counts["failed"] += 1
                    continue
                if auto_accept:
                    try:
                        out = accept_draft(item_id, state=state)
                        counts["accepted"] += 1
                        log.info("item %s auto-accepted -> %s", item_id, out)
                    except Exception:
                        log.exception("item %s auto-accept failed; draft left pending",
                                      item_id)
            if len(work) > limit:
                log.info("run %s: %d triaged items beyond --limit left for next run",
                         run_id, len(work) - limit)

            state.finish_run(run_id, counts)

        if counts.get("accepted"):
            rebuild_site()
    finally:
        _release_lock()
    log.info("run %s finished: %s", run_id, counts)
    return counts
