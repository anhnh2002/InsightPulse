"""LLM extraction of structured posts from raw LinkedIn innerText."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from caw import ToolKit, tool

from insightpulse.agents.base import load_prompt, run_agent
from insightpulse.config import load_settings
from insightpulse.models import RawPost, Source

log = logging.getLogger(__name__)


class ExtractToolKit(ToolKit, server_name="post_extractor",
                     display_name="LinkedIn Post Extractor", thread_safe=True):
    def __init__(self):
        self.posts: list[dict] = []

    @tool(
        name="submit_posts",
        description=(
            "Submit the extracted posts as a JSON array. Each element must be an "
            'object: {"author": str, "text": str, "links": [str], "approx_date": str}. '
            "Call exactly once with ALL extracted posts."
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
            if not isinstance(p, dict) or not str(p.get("text", "")).strip():
                errors.append(f"post[{i}] missing non-empty 'text'")
            if not isinstance(p.get("links", []), list):
                errors.append(f"post[{i}] 'links' must be an array")
        if errors:
            return "ERROR: " + "; ".join(errors) + ". Fix and resubmit."
        self.posts = data
        return f"Accepted {len(data)} posts."


def extract_posts(kol_id: str, raw: dict, output_dir: Path) -> list[RawPost]:
    """Turn one KOL's raw LinkedIn payload into RawPost objects."""
    sections = raw.get("sections") or {}
    text = "\n\n".join(
        f"### section: {name}\n{content}" for name, content in sections.items() if content
    )
    toolkit = ExtractToolKit()
    run_agent(
        name="LinkedIn Post Extractor",
        system_prompt=load_prompt("linkedin_extractor.md"),
        user_prompt=(
            f"Raw innerText captured from the LinkedIn page of '{kol_id}':\n\n{text}"
        ),
        model=load_settings().models.extractor,
        toolkit=toolkit,
        output_dir=output_dir,
        traj_name=f"extract_{kol_id}",
        check_done=lambda: bool(toolkit.posts),
    )
    posts = [
        RawPost(
            source=Source.linkedin,
            kol=kol_id,
            text=p["text"],
            urls=[u for u in p.get("links", []) if isinstance(u, str)],
            author_name=p.get("author", ""),
            created_at=p.get("approx_date", ""),
            permalink=raw.get("url", ""),
        )
        for p in toolkit.posts
    ]
    log.info("LinkedIn extractor: %s -> %d posts", kol_id, len(posts))
    return posts
