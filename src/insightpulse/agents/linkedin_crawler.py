"""Agent-driven LinkedIn crawl: the agent drives the scraper via tools and
submits structured posts for a whole date window in one pass."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path

from caw import ToolKit, tool

from insightpulse.agents.base import load_prompt, run_agent
from insightpulse.config import LinkedInKol, load_settings
from insightpulse.dates import overlaps_window
from insightpulse.models import RawPost, Source
from insightpulse.sources import linkedin_source

log = logging.getLogger(__name__)

_ACTIVITY_RE = re.compile(r"urn:li:activity:(\d+)")
_PRECISIONS = ("day", "week", "month", "unknown")
_MAX_TOOL_RETURN_CHARS = 150_000


def _payload_json(data: dict, max_chars: int = _MAX_TOOL_RETURN_CHARS) -> str:
    """Sections + references as a JSON string capped for the agent's context.

    Only section texts are truncated (with a marker); references are small and
    carry the post URLs, so they are always kept whole.
    """
    payload = {
        "url": data.get("url", ""),
        "sections": dict(data.get("sections") or {}),
        "references": data.get("references") or {},
    }
    out = json.dumps(payload, ensure_ascii=False)
    while len(out) > max_chars:
        largest = max(payload["sections"], key=lambda k: len(str(payload["sections"][k])),
                      default=None)
        if largest is None:
            break
        text = str(payload["sections"][largest])
        keep = max(len(text) - (len(out) - max_chars) - 100, 0)
        payload["sections"][largest] = text[:keep] + "\n[truncated]"
        out = json.dumps(payload, ensure_ascii=False)
        if keep == 0:
            break
    return out


class CrawlToolKit(ToolKit, server_name="linkedin_crawler",
                   display_name="LinkedIn Crawler", thread_safe=True):
    def __init__(self, kols: list[LinkedInKol], raw_dir: Path,
                 max_fetches_per_kol: int = 3, max_scrolls_cap: int = 25):
        self.allowed = {k.id: k for k in kols}
        self.raw_dir = raw_dir
        self.max_fetches_per_kol = max_fetches_per_kol
        self.max_scrolls_cap = max_scrolls_cap
        self.posts: list[dict] = []
        self.submitted = False
        self.fetch_counts: dict[str, int] = {}   # successful fetches (budgeted)
        self.attempt_counts: dict[str, int] = {}  # all attempts (hard cap)
        self.rate_limited: set[str] = set()

    def _guard(self, target: str, kind: str) -> str | None:
        kol = self.allowed.get(target)
        if kol is None or kol.kind != kind:
            roster = ", ".join(f"{k.kind}:{k.id}" for k in self.allowed.values())
            return f"ERROR: '{target}' is not a {kind} in the KOL roster ({roster})."
        if target in self.rate_limited:
            return (f"ERROR: {target} is rate-limited for this run. "
                    "Do NOT retry it; continue with other KOLs.")
        if self.fetch_counts.get(target, 0) >= self.max_fetches_per_kol:
            return (f"ERROR: fetch budget for {target} exhausted "
                    f"({self.max_fetches_per_kol} fetches) — work with what you have.")
        if self.attempt_counts.get(target, 0) >= 2 * self.max_fetches_per_kol:
            return (f"ERROR: too many failed fetch attempts for {target} — "
                    "skip this KOL and work with what you have.")
        return None

    async def _run_fetch(self, target: str, fetch) -> str:
        self.attempt_counts[target] = self.attempt_counts.get(target, 0) + 1
        try:
            # The mcporter subprocess blocks up to 7 minutes; keep the MCP
            # server's event loop free while it runs.
            data = await asyncio.to_thread(fetch)
        except linkedin_source.LinkedInRateLimited as e:
            self.rate_limited.add(target)
            return (f"ERROR: LinkedIn rate-limited fetching {target} ({e}). "
                    "Do NOT retry this KOL. Continue with remaining KOLs; if they "
                    "also rate-limit, stop fetching and submit what you have.")
        except Exception as e:
            return f"ERROR: fetch failed for {target}: {e}. Retry once or skip this KOL."
        # only successful scrapes consume the budget; failed attempts are cheap
        self.fetch_counts[target] = self.fetch_counts.get(target, 0) + 1
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        stem = f"linkedin_{target}_fetch{self.fetch_counts[target]}"
        (self.raw_dir / f"{stem}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False))
        # the page innerText again as plain text — the .json holds it as one
        # giant string, unreadable in an editor
        (self.raw_dir / f"{stem}.txt").write_text("\n\n".join(
            f"### section: {name}\n{content}"
            for name, content in (data.get("sections") or {}).items() if content))
        return _payload_json(data)

    @tool(
        name="fetch_person_posts",
        description=(
            "Fetch the posts section of a person's LinkedIn profile. "
            "`linkedin_username` must be a person from the KOL roster. "
            "`max_scrolls` controls how far back the page is scrolled (more scrolls "
            "= older posts, slower fetch). Returns JSON with `sections` (raw page "
            "innerText) and `references` (URLs found per section). You have a "
            "limited fetch budget per KOL."
        ),
    )
    async def fetch_person_posts(self, linkedin_username: str, max_scrolls: int) -> str:
        err = self._guard(linkedin_username, "person")
        if err:
            return err
        scrolls = max(1, min(int(max_scrolls), self.max_scrolls_cap))
        return await self._run_fetch(
            linkedin_username,
            lambda: linkedin_source.fetch_person_raw(linkedin_username, scrolls),
        )

    @tool(
        name="fetch_company_posts",
        description=(
            "Fetch the posts of a company LinkedIn page. `company_name` must be a "
            "company from the KOL roster. Depth is NOT tunable for companies — "
            "re-fetching returns the same window, so fetch each company at most once. "
            "Returns JSON with `sections` (raw page innerText) and `references` "
            "(URLs found per section)."
        ),
    )
    async def fetch_company_posts(self, company_name: str) -> str:
        err = self._guard(company_name, "company")
        if err:
            return err
        return await self._run_fetch(
            company_name,
            lambda: linkedin_source.fetch_company_raw(company_name),
        )

    @tool(
        name="submit_posts",
        description=(
            "Submit ALL extracted posts across ALL KOLs as a JSON array. Each element: "
            '{"kol": str (roster id), "author": str, "text": str, "links": [str], '
            '"permalink": str, "approx_date": "YYYY-MM-DD" or "", '
            '"date_precision": "day"|"week"|"month"|"unknown"}. '
            "Call exactly once when you are done crawling. An empty array is valid "
            "when no posts fall in the target window."
        ),
    )
    async def submit_posts(self, posts_json: str) -> str:
        try:
            data = json.loads(posts_json)
        except json.JSONDecodeError as e:
            return f"ERROR: invalid JSON ({e}). Fix and resubmit."
        if not isinstance(data, list):
            return "ERROR: expected a JSON array of post objects. Fix and resubmit."
        errors = []
        for i, p in enumerate(data):
            if not isinstance(p, dict):
                errors.append(f"post[{i}] is not an object")
                continue
            if p.get("kol") not in self.allowed:
                errors.append(f"post[{i}] 'kol' must be one of {sorted(self.allowed)}")
            if not str(p.get("text", "")).strip():
                errors.append(f"post[{i}] missing non-empty 'text'")
            if not isinstance(p.get("links", []), list):
                errors.append(f"post[{i}] 'links' must be an array")
            if p.get("date_precision", "unknown") not in _PRECISIONS:
                errors.append(f"post[{i}] 'date_precision' must be one of {_PRECISIONS}")
            approx = str(p.get("approx_date", "")).strip()
            if approx:
                try:
                    date.fromisoformat(approx)
                except ValueError:
                    errors.append(f"post[{i}] 'approx_date' must be YYYY-MM-DD or empty")
        if errors:
            return "ERROR: " + "; ".join(errors[:20]) + ". Fix and resubmit."
        self.posts = data
        self.submitted = True
        return f"Accepted {len(data)} posts."


def _to_raw_post(p: dict, profile_url: str) -> RawPost:
    links = [u for u in p.get("links", []) if isinstance(u, str)]
    permalink = str(p.get("permalink", "")).strip()
    m = _ACTIVITY_RE.search(permalink) or next(
        (mm for mm in map(_ACTIVITY_RE.search, links) if mm), None
    )
    external_id = m.group(1) if m else ""
    if external_id:
        permalink = f"https://www.linkedin.com/feed/update/urn:li:activity:{external_id}/"
    elif not permalink:
        permalink = profile_url
    return RawPost(
        source=Source.linkedin,
        kol=p["kol"],
        external_id=external_id,
        text=p["text"],
        urls=links,
        author_name=p.get("author", ""),
        created_at=str(p.get("approx_date", "")).strip(),
        permalink=permalink,
    )


def crawl_linkedin(kols: list[LinkedInKol], start: date, end: date, raw_dir: Path,
                   output_dir: Path, backfill: bool = False
                   ) -> tuple[list[RawPost], set[str]]:
    """Run the crawl agent over all KOLs; return in-window posts + rate-limited KOLs.

    In backfill mode no post is dropped by date: the agent submits everything
    visible and dedup downstream handles repeats.
    """
    toolkit = CrawlToolKit(kols, raw_dir, max_scrolls_cap=50 if backfill else 25)
    today = datetime.now(timezone.utc).date()
    roster = "\n".join(
        f"- person {k.id} (suggested initial max_scrolls: {k.max_scrolls})"
        if k.kind == "person" else f"- company {k.id} (fixed depth, fetch once)"
        for k in kols
    )
    mode = (
        "Mode: BACKFILL — submit every post visible in the fetched pages "
        "regardless of date; still fill approx_date/date_precision as best you can."
        if backfill else
        "Mode: DAILY — apply the target-window rules."
    )
    run_agent(
        name="LinkedIn Crawler",
        system_prompt=load_prompt("linkedin_crawler.md"),
        user_prompt=(
            f"Capture date (UTC): {today.isoformat()}.\n"
            f"Target window: {start.isoformat()} .. {end.isoformat()} (inclusive).\n"
            f"{mode}\n\n"
            f"KOL roster:\n{roster}"
        ),
        model=load_settings().models.crawler,
        toolkit=toolkit,
        output_dir=output_dir,
        traj_name="crawl_linkedin",
        check_done=lambda: toolkit.submitted,
        retry_prompt=(
            "You have not called submit_posts yet. Call it now with everything you "
            "extracted so far — partial results are acceptable, an empty array is "
            "acceptable if nothing falls in the window."
        ),
    )

    if toolkit.posts:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "crawled_posts.json").write_text(
            json.dumps(toolkit.posts, indent=2, ensure_ascii=False))

    fresh_window = (today - end).days <= 1
    posts, rate_limited = [], toolkit.rate_limited
    dropped = 0
    for p in toolkit.posts:
        kol = toolkit.allowed[p["kol"]]
        profile_url = (
            f"https://www.linkedin.com/in/{kol.id}/" if kol.kind == "person"
            else f"https://www.linkedin.com/company/{kol.id}/"
        )
        post = _to_raw_post(p, profile_url)
        if not backfill:  # backfill keeps everything; dedup handles repeats
            if post.created_at:
                approx = date.fromisoformat(post.created_at)
                precision = p.get("date_precision", "unknown")
                if not overlaps_window(approx, precision, start, end):
                    dropped += 1
                    continue
            elif not fresh_window:
                # unknown date: only trust it as "fresh" when the window is current
                dropped += 1
                continue
        posts.append(post)
    log.info("LinkedIn crawl: %d posts submitted, %d in window %s..%s, "
             "rate-limited KOLs: %s",
             len(toolkit.posts), len(posts), start, end,
             ",".join(sorted(rate_limited)) or "none")
    return posts, rate_limited
