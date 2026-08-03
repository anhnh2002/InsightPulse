"""Writer agent: reads the item workdir, submits a validated blog draft."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from caw import ToolGroup, ToolKit, tool

from insightpulse import topics
from insightpulse.agents.base import load_prompt, run_agent
from insightpulse.config import load_settings
from insightpulse.models import Draft, Kind, PaperMeta, RepoMeta, Source

log = logging.getLogger(__name__)

REQUIRED_SECTIONS = {
    Kind.paper: ["## The Big Idea", "## How It Works", "## What They Found",
                 "## Glossary", "## Links"],
    Kind.news: ["## What Happened", "## Why It Matters",
                "## Glossary", "## Links"],
}

REQUIRED_SECTIONS_VI = {
    Kind.paper: ["## Ý tưởng chính", "## Cách hoạt động", "## Kết quả",
                 "## Thuật ngữ", "## Liên kết"],
    Kind.news: ["## Chuyện gì đã xảy ra", "## Vì sao đáng chú ý",
                "## Thuật ngữ", "## Liên kết"],
}


FIGURE_REF_RE = re.compile(r"!\[[^\]]*\]\((figures/[^)]+)\)")


class BlogToolKit(ToolKit, server_name="blog_reporter",
                  display_name="Blog Draft Reporter", thread_safe=True):
    def __init__(self, kind: Kind, workdir: Path):
        self.kind = kind
        self.workdir = workdir
        self.draft_data: dict | None = None

    def _load_manifest(self) -> list[dict]:
        manifest = self.workdir / "figures.json"
        if manifest.exists():
            try:
                return json.loads(manifest.read_text())
            except json.JSONDecodeError:
                pass
        return []

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
            "Submit the finished bilingual blog draft. title/summary/"
            "body_markdown are the English version; title_vi/summary_vi/"
            "body_markdown_vi are the complete Vietnamese version. "
            "topic_path_json is a JSON array of "
            'slugs from root to leaf, e.g. ["ai", "llm", "reasoning"]. '
            "keywords_json is a JSON array of 3-8 lowercase keyword strings. "
            "reliability_json is a JSON object with exactly these keys: "
            '{"authors_orgs": str, "venue": str, "code_available": bool, '
            '"evidence": str} — short factual statements only, no judgments. '
            "hero_figure is the workdir-relative path of the single best "
            "extracted figure to use as the post's cover image (e.g. "
            '"figures/fig01.png"), or "" when none is compelling. '
            "Returns 'OK' or validation errors to fix."
        ),
    )
    async def submit_blog(self, title: str, topic_path_json: str, keywords_json: str,
                          summary: str, body_markdown: str,
                          title_vi: str, summary_vi: str, body_markdown_vi: str,
                          reliability_json: str = "{}",
                          hero_figure: str = "") -> str:
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
        if not title_vi.strip() or len(title_vi) > 120:
            errors.append("title_vi must be non-empty and <= 120 chars")
        if not summary_vi.strip():
            errors.append("summary_vi must be non-empty")
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
        missing_vi = [s for s in REQUIRED_SECTIONS_VI[self.kind]
                      if s not in body_markdown_vi]
        if missing_vi:
            errors.append(f"body_markdown_vi missing required sections: {missing_vi}")
        if len(body_markdown_vi) < 500:
            errors.append("body_markdown_vi is too short for a useful blog post")

        manifest = self._load_manifest()
        manifest_files = {f["file"] for f in manifest}
        refs = set(FIGURE_REF_RE.findall(body_markdown))
        refs |= set(FIGURE_REF_RE.findall(body_markdown_vi))
        hero_figure = hero_figure.strip()
        if hero_figure:
            refs.add(hero_figure)
        for ref in sorted(refs):
            if not (self.workdir / ref).is_file():
                errors.append(f"referenced figure does not exist: {ref}")
        if hero_figure and hero_figure not in manifest_files:
            errors.append(f"hero_figure must be listed in figures.json: {hero_figure}")

        if errors:
            return "ERROR: " + "; ".join(errors) + ". Fix and resubmit."

        self.draft_data = {
            "title": title.strip(),
            "topic_path": topic_path,
            "topic_proposed": is_new,
            "keywords": [k.strip().lower() for k in keywords],
            "summary": summary.strip(),
            "body_markdown": body_markdown.strip(),
            "title_vi": title_vi.strip(),
            "summary_vi": summary_vi.strip(),
            "body_markdown_vi": body_markdown_vi.strip(),
            "reliability": reliability,
            "hero_figure": hero_figure,
            "figures": [f for f in manifest if f["file"] in refs],
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
    social: dict | None = None,
) -> Draft:
    """Run the writer agent for one enriched item; returns the validated Draft."""
    toolkit = BlogToolKit(kind, workdir)
    prompt_file = "writer_paper.md" if kind == Kind.paper else "writer_news.md"
    user_prompt = (
        "Write the blog post for the item in your working directory. "
        "Start by reading paper.txt/content.txt and meta.json, and call "
        "get_topic_tree before classifying."
    )
    n_figs = len(toolkit._load_manifest())
    if n_figs:
        user_prompt += (
            f" The workdir contains {n_figs} extracted paper figures — "
            "see figures.json for captions."
        )
    run_agent(
        name=f"Blog Writer ({kind.value})",
        system_prompt=load_prompt(prompt_file),
        user_prompt=user_prompt,
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
        social=social or {},
        **d,
    )
