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


_ID_FROM_ENTRY_RE = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5})")

_TITLE_STOPWORDS = frozenset(
    "a an the of for in on with and or to from via by at as is are how what".split()
)


def _title_tokens(s: str) -> set[str]:
    words = re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()
    return {w.rstrip("s") for w in words if w not in _TITLE_STOPWORDS}


def search_by_title(title: str, min_recall: float = 0.6,
                    ambiguity_margin: float = 0.15) -> str:
    """Best-effort arXiv id lookup by paper title; '' when no confident match.

    Social posts often name a paper without linking it, and triage working
    titles paraphrase subtitles — so this searches by the distinctive head
    ("SkillSmith: ..." -> SkillSmith) when there is one, scores candidates by
    token overlap, and refuses ambiguous results (several papers can share a
    nickname; blogging the wrong paper is worse than demoting to news).
    """
    head = title.split(":", 1)[0].strip() if ":" in title else ""
    if head and (" " in head or head.lower() in _TITLE_STOPWORDS):
        head = ""
    query = f"all:{head}" if head else 'ti:"%s"' % re.sub(r"[^\w\s]", " ", title).strip()
    want = _title_tokens(title)
    if not want:
        return ""
    try:
        resp = httpx.get(
            API_URL, params={"search_query": query, "max_results": 10},
            headers=_HEADERS, timeout=30, follow_redirects=True,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except (httpx.HTTPError, ET.ParseError) as e:
        log.warning("arXiv title search failed for %r: %s", title, e)
        return ""
    scored = []
    for entry in root.findall("atom:entry", ATOM_NS):
        got_title = (entry.findtext("atom:title", "", ATOM_NS) or "").strip()
        got = _title_tokens(got_title)
        if not got or (head and head.lower().rstrip("s") not in got):
            continue
        m = _ID_FROM_ENTRY_RE.search(entry.findtext("atom:id", "", ATOM_NS) or "")
        if m:
            scored.append((len(want & got) / len(want), m.group(1), got_title))
    scored.sort(reverse=True)
    if not scored or scored[0][0] < min_recall:
        return ""
    if len(scored) > 1 and scored[0][0] - scored[1][0] < ambiguity_margin:
        log.info("arXiv title search: %r ambiguous (%.2f %s vs %.2f %s) — refusing",
                 title, scored[0][0], scored[0][1], scored[1][0], scored[1][1])
        return ""
    recall, arxiv_id, got_title = scored[0]
    log.info("arXiv title search: %r -> %s %r (recall %.2f)", title, arxiv_id,
             got_title[:60], recall)
    return arxiv_id


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|nav|header|footer|figure)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)</(p|div|section|h[1-6]|li|tr)>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def fetch_paper_html(meta: PaperMeta) -> tuple[str, str] | None:
    """Best-effort paper HTML: ar5iv → arxiv html. Returns (final_url, html)."""
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
                    return str(resp.url), resp.text
        except httpx.HTTPError as e:
            log.debug("arxiv %s: %s failed: %s", meta.arxiv_id, url, e)
    return None


def fetch_paper_text(meta: PaperMeta, char_cap: int) -> str:
    """Best-effort full text: ar5iv HTML → arxiv html → abstract only."""
    res = fetch_paper_html(meta)
    if res:
        return _strip_html(res[1])[:char_cap]
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
