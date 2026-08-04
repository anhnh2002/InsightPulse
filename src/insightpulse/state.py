"""SQLite state store: item lifecycle + run history + cross-run dedup."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone

from insightpulse.models import Kind, RawPost, Source
from insightpulse.paths import STATE_DB

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    kol         TEXT NOT NULL,
    external_id TEXT DEFAULT '',
    url         TEXT DEFAULT '',
    dedup_key   TEXT NOT NULL UNIQUE,
    arxiv_id    TEXT DEFAULT '',
    kind        TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'collected',
    run_id      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    error       TEXT DEFAULT '',
    links_json  TEXT DEFAULT '[]',
    paper_name  TEXT DEFAULT '',
    title       TEXT DEFAULT '',
    post_text   TEXT DEFAULT '',
    posted_at   TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_arxiv ON items(arxiv_id) WHERE arxiv_id != '';

CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT DEFAULT '',
    counts_json TEXT DEFAULT '{}',
    target_date TEXT DEFAULT ''
);
"""

# Additive migrations for DBs created before these columns existed
# (CREATE TABLE IF NOT EXISTS never alters an existing table).
_MIGRATIONS = [
    ("items", "posted_at", "ALTER TABLE items ADD COLUMN posted_at TEXT DEFAULT ''"),
    ("runs", "target_date", "ALTER TABLE runs ADD COLUMN target_date TEXT DEFAULT ''"),
    ("items", "paper_name", "ALTER TABLE items ADD COLUMN paper_name TEXT DEFAULT ''"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id(target: date | None = None) -> str:
    """Run id prefixed with the covered day; random suffix keeps backfill
    runs started within the same second from colliding."""
    day = (target or datetime.now(timezone.utc).date()).strftime("%Y%m%d")
    now = datetime.now(timezone.utc).strftime("%H%M%S")
    return f"{day}-{now}-{uuid.uuid4().hex[:4]}"


def new_item_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"


class State:
    def __init__(self, db_path=STATE_DB):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        for table, col, ddl in _MIGRATIONS:
            cols = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                self.conn.execute(ddl)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "State":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- runs ---

    def start_run(self, run_id: str, target_date: str = "") -> None:
        self.conn.execute(
            "INSERT INTO runs (run_id, started_at, target_date) VALUES (?, ?, ?)",
            (run_id, _now(), target_date),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, counts: dict) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at = ?, counts_json = ? WHERE run_id = ?",
            (_now(), json.dumps(counts), run_id),
        )
        self.conn.commit()

    # --- items ---

    def insert_post(self, post: RawPost, run_id: str) -> str | None:
        """Insert a collected post; returns the new item id, or None if already seen."""
        item_id = new_item_id()
        try:
            self.conn.execute(
                "INSERT INTO items (id, source, kol, external_id, url, dedup_key,"
                " status, run_id, created_at, links_json, paper_name, post_text,"
                " posted_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'collected', ?, ?, ?, ?, ?, ?)",
                (
                    item_id,
                    post.source.value,
                    post.kol,
                    post.external_id,
                    post.permalink,
                    post.dedup_key,
                    run_id,
                    _now(),
                    json.dumps(post.urls),
                    post.paper_name,
                    post.text,
                    post.created_at,
                ),
            )
        except sqlite3.IntegrityError:
            return None
        self.conn.commit()
        return item_id

    def set_triage(self, item_id: str, kind: Kind, links: list[str], title: str,
                   arxiv_id: str = "", paper_name: str = "") -> None:
        self.conn.execute(
            "UPDATE items SET kind = ?, status = ?, links_json = ?, title = ?,"
            " arxiv_id = ?, paper_name = ? WHERE id = ?",
            (
                kind.value,
                "skipped" if kind == Kind.skip else "triaged",
                json.dumps(links),
                title,
                arxiv_id,
                paper_name,
                item_id,
            ),
        )
        self.conn.commit()

    def has_dedup_key(self, key: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM items WHERE dedup_key = ? LIMIT 1", (key,)
        ).fetchone()
        return row is not None

    def arxiv_seen(self, arxiv_id: str, exclude_item: str = "") -> bool:
        """True if another item already covers this arxiv id (paper-level dedup)."""
        row = self.conn.execute(
            "SELECT 1 FROM items WHERE arxiv_id = ? AND id != ? AND status != 'skipped'"
            " LIMIT 1",
            (arxiv_id, exclude_item),
        ).fetchone()
        return row is not None

    def resolve_link(self, item_id: str, arxiv_id: str) -> None:
        """Manually filled arXiv id: the item leaves needs_link and becomes
        writable again (picked up as a leftover by the next run)."""
        self.conn.execute(
            "UPDATE items SET arxiv_id = ?, status = 'triaged' WHERE id = ?",
            (arxiv_id, item_id),
        )
        self.conn.commit()

    def set_arxiv(self, item_id: str, arxiv_id: str) -> None:
        """Record a manually resolved arXiv id without touching the status."""
        self.conn.execute(
            "UPDATE items SET arxiv_id = ? WHERE id = ?", (arxiv_id, item_id)
        )
        self.conn.commit()

    def set_status(self, item_id: str, status: str, error: str = "") -> None:
        self.conn.execute(
            "UPDATE items SET status = ?, error = ? WHERE id = ?",
            (status, error, item_id),
        )
        self.conn.commit()

    def get_item(self, item_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()

    def items_by_status(self, status: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM items WHERE status = ? ORDER BY created_at", (status,)
        ).fetchall()

    def status_counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM items GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def recent_runs(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
