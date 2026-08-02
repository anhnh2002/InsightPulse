"""Publish accepted drafts as Hugo posts and rebuild the site."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

import frontmatter

from insightpulse.paths import BLOG_CONTENT, ROOT

log = logging.getLogger(__name__)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60] or "post"


def publish_draft(draft_path: Path) -> Path:
    """Convert an accepted draft into a Hugo content file."""
    post = frontmatter.load(draft_path)
    m = post.metadata

    topic_path = [str(s) for s in m.get("topic_path", [])]
    # hierarchical taxonomy terms: [ai, ai/llm, ai/llm/reasoning]
    topic_terms = ["/".join(topic_path[: i + 1]) for i in range(len(topic_path))]

    hugo_meta = {
        "title": m.get("title", ""),
        "date": str(m.get("date", "")),
        "summary": m.get("summary", ""),
        "description": m.get("summary", ""),
        "tags": m.get("keywords", []),
        "topics": topic_terms,
        "item_kind": m.get("kind", ""),  # "kind" is reserved by Hugo
        "kol": m.get("kol", ""),
        "source_url": m.get("source_url", ""),
        "draft_id": m.get("id", ""),
    }
    for key in ("paper", "repo", "reliability"):
        if m.get(key):
            hugo_meta[key] = m[key]

    BLOG_CONTENT.mkdir(parents=True, exist_ok=True)
    out = BLOG_CONTENT / f"{m.get('date', '')}-{_slugify(str(m.get('title', '')))}.md"
    out.write_bytes(frontmatter.dumps(frontmatter.Post(post.content, **hugo_meta)).encode())
    log.info("published %s -> %s", draft_path.name, out)
    return out


def rebuild_site() -> None:
    """Build the Hugo site via the one-shot builder container."""
    subprocess.run(
        ["docker", "compose", "run", "--rm", "builder"],
        cwd=ROOT, check=True,
    )
