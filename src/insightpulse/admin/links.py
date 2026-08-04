"""Fill a manually supplied paper link into draft/post frontmatter."""

from __future__ import annotations

from insightpulse.enrich import arxiv as arxiv_enrich
from insightpulse.enrich.arxiv import arxiv_id_from_url
from insightpulse.state import State


def fill_link(meta: dict, url: str) -> str:
    """Set meta['paper'] from a user-supplied URL and clear the missing-link flag.

    arXiv links are enriched with full paper metadata; anything else is kept as
    a bare link. Returns the arXiv id ("" for non-arXiv links). Raises on bad
    input or an unreachable arXiv API.
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"not a URL: {url!r}")
    arxiv_id = arxiv_id_from_url(url)
    if arxiv_id:
        paper = arxiv_enrich.fetch_meta(arxiv_id).model_dump(exclude_defaults=True)
    else:
        paper = {"abs_url": url}
        if meta.get("paper_name"):
            paper["title"] = meta["paper_name"]
    meta["paper"] = paper
    meta.pop("missing_link", None)
    return arxiv_id


def record_arxiv(item_id: str, arxiv_id: str) -> None:
    """Store the resolved id in the state DB so paper-level dedup sees it."""
    if not arxiv_id:
        return
    with State() as state:
        if state.get_item(item_id):
            state.set_arxiv(item_id, arxiv_id)
