"""Helpers over the published Hugo bundles in blog/site/content/posts/."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from insightpulse.admin import links
from insightpulse.paths import BLOG_CONTENT

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def check_name(name: str, base: Path = BLOG_CONTENT) -> Path:
    """Validate a bundle/draft name and return its path, guarding against traversal."""
    if not _NAME_RE.match(name):
        raise ValueError(f"invalid name: {name!r}")
    path = (base / name).resolve()
    if base.resolve() not in path.parents:
        raise ValueError(f"invalid name: {name!r}")
    return path


def list_published() -> list[dict]:
    out = []
    if not BLOG_CONTENT.is_dir():
        return out
    for bundle in sorted(BLOG_CONTENT.iterdir(), reverse=True):
        index = bundle / "index.md"
        if not index.is_file():
            continue
        meta = frontmatter.load(index).metadata
        out.append({
            "name": bundle.name,
            "title": meta.get("title", bundle.name),
            "date": str(meta.get("date", "")),
            "kind": meta.get("item_kind", ""),
            "has_vi": (bundle / "index.vi.md").is_file(),
            "missing_link": bool(meta.get("missing_link")),
        })
    return out


def read_bundle(name: str) -> dict:
    bundle = check_name(name)
    index = bundle / "index.md"
    if not index.is_file():
        raise FileNotFoundError(f"no published post {name}")
    vi = bundle / "index.vi.md"
    return {
        "name": name,
        "en": index.read_text(),
        "vi": vi.read_text() if vi.is_file() else "",
    }


def write_bundle(name: str, en: str, vi: str) -> None:
    bundle = check_name(name)
    if not (bundle / "index.md").is_file():
        raise FileNotFoundError(f"no published post {name}")
    _validate_frontmatter(en)
    (bundle / "index.md").write_text(en)
    vi_path = bundle / "index.vi.md"
    if vi.strip():
        _validate_frontmatter(vi)
        vi_path.write_text(vi)
    elif vi_path.is_file():
        vi_path.unlink()


def create_bundle(name: str, en: str, vi: str) -> None:
    bundle = check_name(name)
    if bundle.exists():
        raise FileExistsError(f"post {name} already exists")
    _validate_frontmatter(en)
    if vi.strip():
        _validate_frontmatter(vi)
    bundle.mkdir(parents=True)
    (bundle / "index.md").write_text(en)
    if vi.strip():
        (bundle / "index.vi.md").write_text(vi)


def fill_bundle_link(name: str, url: str) -> None:
    """Set the paper link on a published bundle (EN + VI) and clear the flag."""
    bundle = check_name(name)
    index = bundle / "index.md"
    if not index.is_file():
        raise FileNotFoundError(f"no published post {name}")
    post = frontmatter.load(index)
    arxiv_id = links.fill_link(post.metadata, url)
    index.write_bytes(frontmatter.dumps(post).encode())
    vi = bundle / "index.vi.md"
    if vi.is_file():
        post_vi = frontmatter.load(vi)
        post_vi.metadata["paper"] = post.metadata["paper"]
        post_vi.metadata.pop("missing_link", None)
        vi.write_bytes(frontmatter.dumps(post_vi).encode())
    links.record_arxiv(str(post.metadata.get("draft_id", "")), arxiv_id)


def bundle_topic_path(meta: dict) -> list[str]:
    """Leaf topic path of a published bundle, e.g. ['ai', 'llm', 'agents']."""
    terms = [str(t) for t in meta.get("topics") or []]
    return terms[-1].split("/") if terms else []


def set_bundle_topic(name: str, path: list[str]) -> None:
    """Rewrite the hierarchical topic terms on a bundle (EN + VI)."""
    bundle = check_name(name)
    index = bundle / "index.md"
    if not index.is_file():
        raise FileNotFoundError(f"no published post {name}")
    terms = ["/".join(path[: i + 1]) for i in range(len(path))]
    for f in (index, bundle / "index.vi.md"):
        if not f.is_file():
            continue
        post = frontmatter.load(f)
        post.metadata["topics"] = terms
        f.write_bytes(frontmatter.dumps(post).encode())


def set_file_code(f: Path, url: str) -> None:
    """Set or clear the code link in one file's reliability metadata.

    A non-empty url marks code as available with a link; an empty url marks
    it as not released.
    """
    post = frontmatter.load(f)
    rel = post.metadata.setdefault("reliability", {})
    rel["code_available"] = bool(url)
    if url:
        rel["code_url"] = url
    else:
        rel.pop("code_url", None)
    f.write_bytes(frontmatter.dumps(post).encode())


def set_bundle_code(name: str, url: str) -> None:
    """Set or clear the code link in the reliability metadata (EN + VI)."""
    bundle = check_name(name)
    index = bundle / "index.md"
    if not index.is_file():
        raise FileNotFoundError(f"no published post {name}")
    for f in (index, bundle / "index.vi.md"):
        if f.is_file():
            set_file_code(f, url)


def delete_bundle(name: str) -> None:
    bundle = check_name(name)
    if not (bundle / "index.md").is_file():
        raise FileNotFoundError(f"no published post {name}")
    shutil.rmtree(bundle)


def _validate_frontmatter(text: str) -> None:
    """Reject content whose frontmatter would break the Hugo build."""
    try:
        frontmatter.loads(text)
    except Exception as exc:
        raise ValueError(f"invalid frontmatter: {exc}") from exc


def new_post_template() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        "---\n"
        f"title: \"\"\n"
        f"date: {today}\n"
        "summary: \"\"\n"
        "description: \"\"\n"
        "tags: []\n"
        "topics: []\n"
        "item_kind: news\n"
        "item_source: \"\"\n"
        "kol: \"\"\n"
        "source_url: \"\"\n"
        "---\n\n"
    )
