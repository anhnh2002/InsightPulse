"""File-based review queue: drafts as markdown + YAML frontmatter."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import frontmatter

from insightpulse.models import Draft
from insightpulse.paths import QUEUE_ACCEPTED, QUEUE_PENDING, QUEUE_REJECTED

log = logging.getLogger(__name__)

# separates the English body from the Vietnamese body in a draft file
VI_SEPARATOR = "<!--vi-->"


def write_draft(draft: Draft, workdir: Path | None = None) -> Path:
    meta = {
        "id": draft.id,
        "kind": draft.kind.value,
        "title": draft.title,
        "date": draft.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": draft.source.value,
        "kol": draft.kol,
        "source_url": draft.source_url,
        "topic_path": draft.topic_path,
        "topic_proposed": draft.topic_proposed,
        "keywords": draft.keywords,
        "summary": draft.summary,
        "run_id": draft.run_id,
    }
    if draft.title_vi:
        meta["title_vi"] = draft.title_vi
    if draft.summary_vi:
        meta["summary_vi"] = draft.summary_vi
    if draft.paper:
        meta["paper"] = draft.paper.model_dump(exclude_defaults=True)
    if draft.repo:
        meta["repo"] = draft.repo.model_dump(exclude_defaults=True)
    if draft.reliability:
        meta["reliability"] = draft.reliability
    if draft.social:
        meta["social"] = draft.social
    if draft.hero_figure:
        meta["hero_figure"] = draft.hero_figure
    if draft.figures:
        meta["figures"] = draft.figures

    body = draft.body_markdown
    if draft.body_markdown_vi:
        body += f"\n\n{VI_SEPARATOR}\n\n{draft.body_markdown_vi}"
    post = frontmatter.Post(body, **meta)
    QUEUE_PENDING.mkdir(parents=True, exist_ok=True)
    path = QUEUE_PENDING / f"{draft.id}.md"
    path.write_bytes(frontmatter.dumps(post).encode())
    if draft.figures and workdir is not None:
        asset_dir = QUEUE_PENDING / draft.id / "figures"
        asset_dir.mkdir(parents=True, exist_ok=True)
        for fig in draft.figures:
            src = workdir / fig["file"]
            if src.is_file():
                shutil.copy2(src, asset_dir / src.name)
    log.info("queue: draft written to %s", path)
    return path


def find_draft(draft_id: str) -> Path | None:
    for d in (QUEUE_PENDING, QUEUE_ACCEPTED, QUEUE_REJECTED):
        p = d / f"{draft_id}.md"
        if p.exists():
            return p
    return None


def list_drafts(status: str = "pending") -> list[frontmatter.Post]:
    d = {"pending": QUEUE_PENDING, "accepted": QUEUE_ACCEPTED,
         "rejected": QUEUE_REJECTED}[status]
    posts = []
    for f in sorted(d.glob("*.md")):
        post = frontmatter.load(f)
        post.metadata.setdefault("id", f.stem)
        posts.append(post)
    return posts


def move_draft(draft_id: str, dest: str, extra_meta: dict | None = None) -> Path:
    """Move a pending draft to accepted/ or rejected/, optionally updating metadata."""
    src = QUEUE_PENDING / f"{draft_id}.md"
    if not src.exists():
        raise FileNotFoundError(f"no pending draft {draft_id}")
    dest_dir = {"accepted": QUEUE_ACCEPTED, "rejected": QUEUE_REJECTED}[dest]
    dest_dir.mkdir(parents=True, exist_ok=True)
    post = frontmatter.load(src)
    if extra_meta:
        post.metadata.update(extra_meta)
    dest_path = dest_dir / src.name
    dest_path.write_bytes(frontmatter.dumps(post).encode())
    src.unlink()
    asset_dir = QUEUE_PENDING / draft_id
    if asset_dir.is_dir():
        dest_assets = dest_dir / draft_id
        if dest_assets.exists():
            shutil.rmtree(dest_assets)
        shutil.move(str(asset_dir), str(dest_assets))
    log.info("queue: %s -> %s", draft_id, dest)
    return dest_path
