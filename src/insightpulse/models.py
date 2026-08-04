"""Core data models passed between pipeline stages."""

from __future__ import annotations

import hashlib
import re
from enum import Enum

from pydantic import BaseModel, Field


class Source(str, Enum):
    x = "x"
    linkedin = "linkedin"
    manual = "manual"             # added by hand in the admin; no social post


class Kind(str, Enum):
    paper = "paper"
    news = "news"
    skip = "skip"


class RawPost(BaseModel):
    """A single social post, normalized across sources."""

    source: Source
    kol: str                      # handle / slug of the KOL
    external_id: str = ""         # tweet id for X; empty for LinkedIn
    text: str
    urls: list[str] = Field(default_factory=list)
    paper_name: str = ""          # verbatim paper title/short-name the post names
    author_name: str = ""
    created_at: str = ""          # ISO-ish string when known
    permalink: str = ""

    @property
    def dedup_key(self) -> str:
        if self.external_id:
            return f"{self.source.value}:{self.external_id}"
        normalized = re.sub(r"\s+", " ", self.text.strip().lower())
        digest = hashlib.sha1(normalized.encode()).hexdigest()
        return f"{self.source.value}:{digest}"


class TriageResult(BaseModel):
    post_id: str                  # dedup_key of the triaged post
    kind: Kind
    arxiv_url: str = ""
    github_url: str = ""
    links: list[str] = Field(default_factory=list)
    paper_name: str = ""
    working_title: str = ""
    reason: str = ""


class PaperMeta(BaseModel):
    arxiv_id: str = ""
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    published: str = ""
    pdf_url: str = ""
    abs_url: str = ""


class RepoMeta(BaseModel):
    url: str = ""
    full_name: str = ""
    stars: int = 0
    license: str = ""
    pushed_at: str = ""
    archived: bool = False
    description: str = ""


class Draft(BaseModel):
    """Validated output of the writer agent, written to the review queue."""

    id: str
    kind: Kind
    title: str
    summary: str
    body_markdown: str
    title_vi: str = ""
    summary_vi: str = ""
    body_markdown_vi: str = ""
    topic_path: list[str]
    topic_proposed: bool = False
    keywords: list[str] = Field(default_factory=list)
    source: Source
    kol: str
    source_url: str = ""
    paper: PaperMeta | None = None
    repo: RepoMeta | None = None
    reliability: dict = Field(default_factory=dict)
    social: dict = Field(default_factory=dict)
    hero_figure: str = ""
    figures: list[dict] = Field(default_factory=list)
    run_id: str = ""
    date: str = ""
