"""Publish accepted drafts as Hugo posts and rebuild the site."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

import frontmatter

from insightpulse import topics
from insightpulse.paths import BLOG_CONTENT, ROOT
from insightpulse.queue import VI_SEPARATOR, move_draft
from insightpulse.state import State

log = logging.getLogger(__name__)


def accept_draft(draft_id: str, topic_override: list[str] | None = None,
                 state: State | None = None) -> Path:
    """Accept a pending draft: merge its topic into the tree and publish it.

    Does not rebuild the site — callers batch that. Pass an already-open
    State to avoid a second connection from within a run.
    """
    extra = {"topic_path": topic_override, "topic_proposed": False} if topic_override else {}
    dest = move_draft(draft_id, "accepted", extra)
    meta = frontmatter.load(dest).metadata
    topics.merge_path([str(s) for s in meta["topic_path"]])
    out = publish_draft(dest)
    if state is not None:
        if state.get_item(draft_id):
            state.set_status(draft_id, "accepted")
    else:
        with State() as s:
            if s.get_item(draft_id):
                s.set_status(draft_id, "accepted")
    return out


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
        "item_source": m.get("source", ""),
        "kol": m.get("kol", ""),
        "source_url": m.get("source_url", ""),
        "draft_id": m.get("id", ""),
    }
    for key in ("paper", "repo", "reliability", "social"):
        if m.get(key):
            hugo_meta[key] = m[key]
    if m.get("source") == "linkedin":
        # LinkedIn crawls only yield profile URLs, not post permalinks — don't
        # surface original-post provenance on the published page
        hugo_meta["source_url"] = ""
        hugo_meta.pop("social", None)

    bundle_name = f"{m.get('date', '')}-{_slugify(str(m.get('title', '')))}"

    figures = m.get("figures", []) or []
    hero = m.get("hero_figure", "")
    if hero:
        cap = next((f.get("caption", "") for f in figures if f.get("file") == hero), "")
        hugo_meta["cover"] = {"image": hero, "alt": cap or hugo_meta["title"],
                              "caption": cap, "relative": True}

    en_body, _, vi_body = post.content.partition(VI_SEPARATOR)
    en_body, vi_body = en_body.strip(), vi_body.strip()

    # leaf page bundle: figures live next to index.md and resolve natively;
    # index.vi.md in the same bundle is auto-linked as the translation
    bundle = BLOG_CONTENT / bundle_name
    bundle.mkdir(parents=True, exist_ok=True)
    out = bundle / "index.md"
    out.write_bytes(frontmatter.dumps(frontmatter.Post(en_body, **hugo_meta)).encode())
    if vi_body:
        meta_vi = dict(hugo_meta)
        meta_vi["title"] = m.get("title_vi") or hugo_meta["title"]
        meta_vi["summary"] = m.get("summary_vi") or hugo_meta["summary"]
        meta_vi["description"] = meta_vi["summary"]
        if hero:
            # bundle resources publish under the EN permalink only; point the
            # VI cover at that site-absolute path so its og:image resolves
            meta_vi["cover"] = dict(hugo_meta["cover"])
            meta_vi["cover"]["image"] = f"/posts/{bundle_name}/{hero}"
            meta_vi["cover"]["relative"] = False
        (bundle / "index.vi.md").write_bytes(
            frontmatter.dumps(frontmatter.Post(vi_body, **meta_vi)).encode()
        )
    assets = draft_path.parent / str(m.get("id", draft_path.stem)) / "figures"
    if assets.is_dir():
        shutil.copytree(assets, bundle / "figures", dirs_exist_ok=True)
    log.info("published %s -> %s%s", draft_path.name, out,
             " (+vi)" if vi_body else "")
    return out


def rebuild_site() -> None:
    """Build the Hugo site via the one-shot builder container."""
    subprocess.run(
        ["docker", "compose", "run", "--rm", "builder"],
        cwd=ROOT, check=True,
    )
