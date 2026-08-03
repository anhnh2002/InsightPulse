"""Per-post link finder: one small agent per link-less post.

LinkedIn authors put the paper link in the first comment, which the scraper
cannot see, so paper posts routinely arrive with no links. The crawl agent
proved too overloaded to chase them all, so each link-less post gets its own
finder agent with fresh context and two search tools (arXiv title match, exa
web search). Wrong link is worse than no link — finders are told to submit an
empty array unless a candidate clearly matches.
"""

from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from caw import ToolKit, tool

from insightpulse.agents.base import load_prompt, run_agent
from insightpulse.config import load_settings
from insightpulse.enrich import arxiv as arxiv_enrich
from insightpulse.models import RawPost
from insightpulse.sources import web_search

log = logging.getLogger(__name__)

_MAX_POST_CHARS = 2000
_MAX_LINKS = 3
_WORKERS = 4


class LinkFinderToolKit(ToolKit, server_name="link_finder",
                        display_name="Paper Link Finder", thread_safe=True):
    def __init__(self, max_searches: int = 5):
        self.max_searches = max_searches
        self.search_count = 0
        self.links: list[str] = []
        self.submitted = False

    def _budget(self) -> str | None:
        if self.search_count >= self.max_searches:
            return ("ERROR: search budget exhausted — call submit_links now "
                    "(an empty array if nothing was confirmed).")
        self.search_count += 1
        return None

    @tool(
        name="search_arxiv",
        description=(
            "Search arXiv for a paper by title. Returns "
            '{"found": true, "url": ..., "title": ...} on a confident match — '
            "verify the returned title really is the paper the post names "
            "(a related follow-up paper is a wrong match) — or "
            '{"found": false} when arXiv has no unambiguous match.'
        ),
    )
    async def search_arxiv(self, paper_title: str) -> str:
        title = paper_title.strip()
        if not title:
            return "ERROR: paper_title must be non-empty."
        err = self._budget()
        if err:
            return err
        arxiv_id = await asyncio.to_thread(arxiv_enrich.search_by_title, title)
        if not arxiv_id:
            return json.dumps({"found": False})
        result = {"found": True, "url": f"https://arxiv.org/abs/{arxiv_id}"}
        try:
            meta = await asyncio.to_thread(arxiv_enrich.fetch_meta, arxiv_id)
            result["title"] = meta.title
        except Exception:
            pass  # title is a nicety for verification; the URL stands alone
        return json.dumps(result, ensure_ascii=False)

    @tool(
        name="search_web",
        description=(
            "Web search. Returns a JSON array of {title, url, snippet} results. "
            "Use when arXiv has no match, or for non-arXiv artifacts "
            "(repo, blog post, project page)."
        ),
    )
    async def search_web(self, query: str) -> str:
        q = query.strip()
        if not q:
            return "ERROR: query must be non-empty."
        err = self._budget()
        if err:
            return err
        try:
            results = await asyncio.to_thread(web_search.search_web, q, 5)
        except Exception as e:
            return f"ERROR: web search failed ({e})."
        return json.dumps(results, ensure_ascii=False)

    @tool(
        name="submit_links",
        description=(
            "Submit your verdict as a JSON array of URLs, e.g. "
            '["https://arxiv.org/abs/2304.08485"]. An empty array [] means the '
            "post needs no link or none could be confirmed. Call exactly once."
        ),
    )
    async def submit_links(self, links_json: str) -> str:
        try:
            data = json.loads(links_json)
        except json.JSONDecodeError as e:
            return f"ERROR: invalid JSON ({e}). Fix and resubmit."
        if not isinstance(data, list) or not all(
            isinstance(u, str) and u.startswith(("http://", "https://"))
            for u in data
        ):
            return "ERROR: expected a JSON array of http(s) URL strings."
        self.links = data[:_MAX_LINKS]
        self.submitted = True
        return f"Accepted {len(self.links)} links."


def _find_for_post(idx: int, post: RawPost, output_dir: Path, model: str) -> list[str]:
    toolkit = LinkFinderToolKit()
    try:
        run_agent(
            name=f"Link Finder {idx}",
            system_prompt=load_prompt("link_finder.md"),
            user_prompt=(
                f"KOL: {post.kol}\n"
                f"Author: {post.author_name or 'unknown'}\n"
                f"Post text:\n{post.text[:_MAX_POST_CHARS]}"
            ),
            model=model,
            toolkit=toolkit,
            output_dir=output_dir,
            traj_name=f"link_finder_{idx:03d}",
            check_done=lambda: toolkit.submitted,
            retry_prompt=(
                "You have not called submit_links yet. Call it now — "
                "an empty array is a valid answer."
            ),
        )
    except Exception as e:
        log.warning("link finder for post %d failed: %s", idx, e)
        return []
    return toolkit.links


def find_missing_links(posts: list[RawPost], output_dir: Path) -> int:
    """Fill `urls` on link-less posts, one finder agent per post.

    Mutates the posts in place; returns how many gained at least one link.
    Finder failures leave the post unchanged — never fatal for the run.
    """
    targets = [(i, p) for i, p in enumerate(posts) if not p.urls]
    if not targets:
        return 0
    out = output_dir / "link_finder"
    model = load_settings().models.crawler
    log.info("Link finder: %d/%d posts lack links, running finders (%d parallel)",
             len(targets), len(posts), _WORKERS)
    filled = 0
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        for post, links in pool.map(
            lambda t: (t[1], _find_for_post(t[0], t[1], out, model)), targets
        ):
            if links:
                post.urls = links
                filled += 1
    log.info("Link finder: found links for %d of %d link-less posts",
             filled, len(targets))
    return filled
