"""Writer agent: reads the item workdir, submits a validated blog draft."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from caw import ToolGroup, ToolKit, tool

from insightpulse import topics
from insightpulse.agents.base import load_prompt, run_agent
from insightpulse.config import load_settings
from insightpulse.models import Draft, Kind, PaperMeta, RepoMeta, Source

log = logging.getLogger(__name__)

REQUIRED_SECTIONS = {
    Kind.paper: ["## Summary", "## Key Contributions", "## My Take", "### Strengths",
                 "### Weaknesses", "### Potential Applications", "### Next Directions",
                 "## Reliability", "## Links"],
    Kind.news: ["## Summary", "## Why It Matters", "## My Take", "## Reliability",
                "## Links"],
}


class BlogToolKit(ToolKit, server_name="blog_reporter",
                  display_name="Blog Draft Reporter", thread_safe=True):
    def __init__(self, kind: Kind):
        self.kind = kind
        self.draft_data: dict | None = None

    @tool(
        name="get_topic_tree",
        description=(
            "Get the current hierarchical topic tree (accepted paths plus paths "
            "already proposed by drafts awaiting review). Call before choosing "
            "topic_path."
        ),
    )
    async def get_topic_tree(self) -> str:
        return topics.render_tree_for_prompt()

    @tool(
        name="submit_blog",
        description=(
            "Submit the finished blog draft. topic_path_json is a JSON array of "
            'slugs from root to leaf, e.g. ["ai", "llm", "reasoning"]. '
            "keywords_json is a JSON array of 3-8 lowercase keyword strings. "
            "reliability_json is a JSON object of reliability facts "
            '(e.g. {"authors_orgs": "...", "code_available": true, "venue": "..."}). '
            "Returns 'OK' or validation errors to fix."
        ),
    )
    async def submit_blog(self, title: str, topic_path_json: str, keywords_json: str,
                          summary: str, body_markdown: str,
                          reliability_json: str = "{}") -> str:
        errors = []
        try:
            topic_path = json.loads(topic_path_json)
            assert isinstance(topic_path, list) and all(isinstance(s, str) for s in topic_path)
        except Exception:
            return 'ERROR: topic_path_json must be a JSON array of strings. Fix and resubmit.'
        try:
            keywords = json.loads(keywords_json)
            assert isinstance(keywords, list) and all(isinstance(s, str) for s in keywords)
        except Exception:
            return 'ERROR: keywords_json must be a JSON array of strings. Fix and resubmit.'
        try:
            reliability = json.loads(reliability_json) if reliability_json else {}
            assert isinstance(reliability, dict)
        except Exception:
            return "ERROR: reliability_json must be a JSON object. Fix and resubmit."

        if not title.strip() or len(title) > 120:
            errors.append("title must be non-empty and <= 120 chars")
        if not summary.strip():
            errors.append("summary must be non-empty")
        if not 3 <= len(keywords) <= 8:
            errors.append("need 3-8 keywords")

        valid, err, is_new = topics.validate_path(topic_path)
        if not valid:
            errors.append(f"topic_path: {err}")

        missing = [s for s in REQUIRED_SECTIONS[self.kind]
                   if s not in body_markdown]
        if missing:
            errors.append(f"body_markdown missing required sections: {missing}")
        if len(body_markdown) < 500:
            errors.append("body_markdown is too short for a useful blog post")

        if errors:
            return "ERROR: " + "; ".join(errors) + ". Fix and resubmit."

        self.draft_data = {
            "title": title.strip(),
            "topic_path": topic_path,
            "topic_proposed": is_new,
            "keywords": [k.strip().lower() for k in keywords],
            "summary": summary.strip(),
            "body_markdown": body_markdown.strip(),
            "reliability": reliability,
        }
        return "OK — draft accepted."


def write_blog(
    *,
    item_id: str,
    kind: Kind,
    source: Source,
    kol: str,
    source_url: str,
    workdir: Path,
    output_dir: Path,
    run_id: str,
    paper: PaperMeta | None = None,
    repo: RepoMeta | None = None,
    date_str: str = "",
) -> Draft:
    """Run the writer agent for one enriched item; returns the validated Draft."""
    toolkit = BlogToolKit(kind)
    prompt_file = "writer_paper.md" if kind == Kind.paper else "writer_news.md"
    run_agent(
        name=f"Blog Writer ({kind.value})",
        system_prompt=load_prompt(prompt_file),
        user_prompt=(
            "Write the blog post for the item in your working directory. "
            "Start by reading paper.txt/content.txt and meta.json, and call "
            "get_topic_tree before classifying."
        ),
        model=load_settings().models.writer,
        toolkit=toolkit,
        output_dir=output_dir,
        traj_name=f"write_{item_id}",
        workdir=workdir,
        # writer needs file-reading tools in its workdir
        tools=ToolGroup.NO_INTERACTION,
        check_done=lambda: toolkit.draft_data is not None,
        retry_prompt=(
            "You have not submitted the draft via submit_blog yet (or it failed "
            "validation). Call submit_blog now with the complete draft."
        ),
    )
    d = toolkit.draft_data
    return Draft(
        id=item_id,
        kind=kind,
        source=source,
        kol=kol,
        source_url=source_url,
        run_id=run_id,
        date=date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        paper=paper,
        repo=repo,
        **d,
    )
