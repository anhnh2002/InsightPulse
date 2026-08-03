"""Paper figure extraction: ar5iv/arxiv HTML primary, PDF (pymupdf) fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx

log = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "InsightPulse/0.1 (research blog pipeline)"}

FIGURE_RE = re.compile(r"(?is)<figure[^>]*>(.*?)</figure>")
IMG_SRC_RE = re.compile(r'(?i)<img[^>]+src="([^"]+)"')
CAPTION_RE = re.compile(r"(?is)<figcaption[^>]*>(.*?)</figcaption>")

_EXT_BY_TYPE = {"image/png": ".png", "image/jpeg": ".jpg"}


def _clean_caption(html: str, max_chars: int = 500) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def extract_html_figures(html: str, page_url: str, workdir: Path,
                         max_figures: int = 8, min_bytes: int = 10_000) -> list[dict]:
    """Parse <figure> blocks, download their png/jpg images into workdir/figures/.

    Returns manifest entries {file, caption, origin}. Small images (icons,
    inline equations) are skipped; duplicate images are deduped by content hash.
    """
    fig_dir = workdir / "figures"
    figs: list[dict] = []
    seen: set[str] = set()
    for block in FIGURE_RE.findall(html):
        if len(figs) >= max_figures:
            break
        m = IMG_SRC_RE.search(block)
        if not m:
            continue
        src = urljoin(page_url, m.group(1))
        try:
            resp = httpx.get(src, headers=_HEADERS, timeout=30, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.debug("figure fetch failed for %s: %s", src, e)
            continue
        ctype = resp.headers.get("content-type", "").split(";")[0].strip()
        ext = _EXT_BY_TYPE.get(ctype)
        if not ext or len(resp.content) < min_bytes:
            continue
        digest = hashlib.sha1(resp.content).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        cap_m = CAPTION_RE.search(block)
        caption = _clean_caption(cap_m.group(1)) if cap_m else ""
        fig_dir.mkdir(parents=True, exist_ok=True)
        name = f"fig{len(figs) + 1:02d}{ext}"
        (fig_dir / name).write_bytes(resp.content)
        figs.append({"file": f"figures/{name}", "caption": caption, "origin": "html"})
    if figs:
        log.info("figures: extracted %d from %s", len(figs), page_url)
    return figs


def _page_captions(page, caption_re) -> list[tuple]:
    import fitz

    return [
        (fitz.Rect(b[:4]), re.sub(r"\s+", " ", b[4]).strip())
        for b in page.get_text("blocks")
        if caption_re.match(b[4].strip())
    ]


def _raster_figures(doc, fig_dir: Path, max_figures: int, min_bytes: int,
                    caption_re) -> list[dict]:
    """Embedded raster images, paired with the nearest caption below them."""
    import fitz

    figs: list[dict] = []
    seen: set[str] = set()
    for page in doc:
        if len(figs) >= max_figures:
            break
        captions = _page_captions(page, caption_re)
        for info in page.get_image_info(xrefs=True):
            if len(figs) >= max_figures:
                break
            xref = info.get("xref", 0)
            if not xref:
                continue
            try:
                img = doc.extract_image(xref)
            except Exception:
                continue
            ext = "." + img["ext"] if img["ext"] in ("png", "jpg", "jpeg") else None
            if not ext or len(img["image"]) < min_bytes:
                continue
            digest = hashlib.sha1(img["image"]).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            rect = fitz.Rect(info["bbox"])
            caption = ""
            best_dy = 120.0  # points; captions sit close under the figure
            for crect, ctext in captions:
                dy = crect.y0 - rect.y1
                if -10 <= dy < best_dy:
                    best_dy, caption = dy, ctext[:500]
            fig_dir.mkdir(parents=True, exist_ok=True)
            name = f"fig{len(figs) + 1:02d}{'.jpg' if ext == '.jpeg' else ext}"
            (fig_dir / name).write_bytes(img["image"])
            figs.append({"file": f"figures/{name}", "caption": caption, "origin": "pdf"})
    return figs


def _vector_figures(doc, fig_dir: Path, max_figures: int, caption_re) -> list[dict]:
    """Vector-drawn figures: union drawing clusters above each caption, render."""
    import fitz

    figs: list[dict] = []
    for page in doc:
        if len(figs) >= max_figures:
            break
        clusters = [c for c in page.cluster_drawings()
                    if c.width > 150 and c.height > 80]
        for crect, ctext in _page_captions(page, caption_re):
            if len(figs) >= max_figures:
                break
            # drawings that end within 400pt above the caption
            parts = [c for c in clusters
                     if -10 <= crect.y0 - c.y1 <= 400 and c.y0 < crect.y0]
            if not parts:
                continue
            region = parts[0]
            for c in parts[1:]:
                region |= c
            if region.width < 150 or region.height < 80:
                continue
            try:
                pix = page.get_pixmap(clip=region, matrix=fitz.Matrix(2, 2))
            except Exception:
                continue
            fig_dir.mkdir(parents=True, exist_ok=True)
            name = f"fig{len(figs) + 1:02d}.png"
            pix.save(fig_dir / name)
            figs.append({"file": f"figures/{name}", "caption": ctext[:500],
                         "origin": "pdf-render"})
    return figs


def extract_pdf_figures(pdf_url: str, workdir: Path,
                        max_figures: int = 8, min_bytes: int = 10_000) -> list[dict]:
    """Fallback: download the PDF and pull figures via pymupdf.

    Embedded raster images first; if the paper draws its figures as vector
    graphics (common on arXiv), render the drawing clusters above each
    "Figure N" caption instead.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        log.warning("figures: pymupdf not installed, skipping PDF extraction")
        return []
    try:
        resp = httpx.get(pdf_url, headers=_HEADERS, timeout=120, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("figures: PDF fetch failed for %s: %s", pdf_url, e)
        return []

    fig_dir = workdir / "figures"
    caption_re = re.compile(r"(?is)^(figure|fig\.?)\s*\d+")
    try:
        doc = fitz.open(stream=resp.content, filetype="pdf")
    except Exception as e:
        log.warning("figures: pymupdf failed to open %s: %s", pdf_url, e)
        return []
    try:
        figs = _raster_figures(doc, fig_dir, max_figures, min_bytes, caption_re)
        if not figs:
            figs = _vector_figures(doc, fig_dir, max_figures, caption_re)
    finally:
        doc.close()
    if figs:
        log.info("figures: extracted %d from PDF %s", len(figs), pdf_url)
    return figs


def write_manifest(figs: list[dict], workdir: Path) -> None:
    if figs:
        (workdir / "figures.json").write_text(
            json.dumps(figs, indent=2, ensure_ascii=False)
        )
