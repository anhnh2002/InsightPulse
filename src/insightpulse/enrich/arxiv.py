"""arXiv metadata + paper text fetching (no LLM)."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import httpx

from insightpulse.models import PaperMeta

log = logging.getLogger(__name__)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
API_URL = "http://export.arxiv.org/api/query"

_HEADERS = {"User-Agent": "InsightPulse/0.1 (research blog pipeline)"}


def fetch_meta(arxiv_id: str) -> PaperMeta:
    resp = httpx.get(
        API_URL, params={"id_list": arxiv_id, "max_results": 1},
        headers=_HEADERS, timeout=30, follow_redirects=True,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    entry = root.find("atom:entry", ATOM_NS)
    if entry is None:
        raise ValueError(f"arXiv API returned no entry for {arxiv_id}")
    title = (entry.findtext("atom:title", "", ATOM_NS) or "").strip()
    if title.lower() == "error":
        raise ValueError(f"arXiv API error for {arxiv_id}")
    return PaperMeta(
        arxiv_id=arxiv_id,
        title=re.sub(r"\s+", " ", title),
        authors=[
            (a.findtext("atom:name", "", ATOM_NS) or "").strip()
            for a in entry.findall("atom:author", ATOM_NS)
        ],
        abstract=re.sub(r"\s+", " ", (entry.findtext("atom:summary", "", ATOM_NS) or "").strip()),
        published=(entry.findtext("atom:published", "", ATOM_NS) or "")[:10],
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
    )


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|nav|header|footer|figure)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)</(p|div|section|h[1-6]|li|tr)>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def fetch_paper_text(meta: PaperMeta, char_cap: int) -> str:
    """Best-effort full text: ar5iv HTML → arxiv html → abstract only."""
    for url in (
        f"https://ar5iv.labs.arxiv.org/html/{meta.arxiv_id}",
        f"https://arxiv.org/html/{meta.arxiv_id}",
    ):
        try:
            resp = httpx.get(url, headers=_HEADERS, timeout=60, follow_redirects=True)
            if resp.status_code == 200 and len(resp.text) > 5000:
                text = _strip_html(resp.text)
                if len(text) > 2000:
                    log.info("arxiv %s: got %d chars from %s", meta.arxiv_id, len(text), url)
                    return text[:char_cap]
        except httpx.HTTPError as e:
            log.debug("arxiv %s: %s failed: %s", meta.arxiv_id, url, e)
    log.warning("arxiv %s: falling back to abstract only", meta.arxiv_id)
    return f"{meta.title}\n\nAbstract: {meta.abstract}"


def fetch_page_text(url: str, char_cap: int) -> str:
    """Generic best-effort page text for news items."""
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=45, follow_redirects=True)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype:
            return ""
        return _strip_html(resp.text)[:char_cap]
    except httpx.HTTPError as e:
        log.warning("page fetch failed for %s: %s", url, e)
        return ""
