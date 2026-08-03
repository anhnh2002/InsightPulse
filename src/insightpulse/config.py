"""Loaders for the three YAML config files."""

from __future__ import annotations

from functools import lru_cache

import yaml
from pydantic import BaseModel, Field

from insightpulse.paths import CONFIG_DIR


class XKol(BaseModel):
    handle: str
    max_posts: int = 20


class LinkedInKol(BaseModel):
    kind: str  # "person" | "company"
    id: str
    max_scrolls: int = 10


class Kols(BaseModel):
    x: list[XKol] = Field(default_factory=list)
    linkedin: list[LinkedInKol] = Field(default_factory=list)


class Models(BaseModel):
    crawler: str = "FAST"
    triage: str = "FAST"
    writer: str = "STRONGEST"


class Limits(BaseModel):
    items_per_run: int = 10
    triage_batch_size: int = 20
    paper_text_chars: int = 60000
    news_text_chars: int = 20000


class TopicSettings(BaseModel):
    max_depth: int = 3


class ArxivSettings(BaseModel):
    # name -> arXiv-id resolution thresholds (enrich.arxiv.search_by_title)
    title_min_recall: float = 0.6
    title_ambiguity_margin: float = 0.15


class ReviewSettings(BaseModel):
    auto_accept: bool = False


class Settings(BaseModel):
    models: Models = Field(default_factory=Models)
    provider: str = "codex"
    limits: Limits = Field(default_factory=Limits)
    topics: TopicSettings = Field(default_factory=TopicSettings)
    arxiv: ArxivSettings = Field(default_factory=ArxivSettings)
    review: ReviewSettings = Field(default_factory=ReviewSettings)


def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name) as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_kols() -> Kols:
    return Kols.model_validate(_load_yaml("kols.yaml"))


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings.model_validate(_load_yaml("settings.yaml"))
