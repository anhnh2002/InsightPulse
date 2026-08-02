"""Project-root-relative paths. The pipeline always runs from the repo root."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RUNS_DIR = DATA_DIR / "runs"
QUEUE_DIR = DATA_DIR / "queue"
QUEUE_PENDING = QUEUE_DIR / "pending"
QUEUE_ACCEPTED = QUEUE_DIR / "accepted"
QUEUE_REJECTED = QUEUE_DIR / "rejected"
STATE_DB = DATA_DIR / "state.db"
RUN_LOCK = DATA_DIR / ".run.lock"
BLOG_SITE = ROOT / "blog" / "site"
BLOG_CONTENT = BLOG_SITE / "content" / "posts"


def ensure_dirs() -> None:
    for p in (RAW_DIR, RUNS_DIR, QUEUE_PENDING, QUEUE_ACCEPTED, QUEUE_REJECTED):
        p.mkdir(parents=True, exist_ok=True)
