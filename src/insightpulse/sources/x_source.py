"""Fetch KOL posts from X via the Agent-Reach `twitter` CLI.

The CLI returns clean structured JSON, so no LLM step is needed. Auth cookies
must be injected into the child process env (read from ~/.agent-reach/config.yaml);
without them twitter-cli falls back to scraping browser cookies, which the
Agent-Reach docs tell us to avoid.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

import yaml

from insightpulse.models import RawPost, Source

log = logging.getLogger(__name__)

AGENT_REACH_CONFIG = Path.home() / ".agent-reach" / "config.yaml"


class XAuthError(RuntimeError):
    pass


def _auth_env() -> dict[str, str]:
    if not AGENT_REACH_CONFIG.exists():
        raise XAuthError(
            f"{AGENT_REACH_CONFIG} not found — run `agent-reach configure twitter`"
        )
    with open(AGENT_REACH_CONFIG) as f:
        cfg = yaml.safe_load(f) or {}
    token, ct0 = cfg.get("twitter_auth_token"), cfg.get("twitter_ct0")
    if not token or not ct0:
        raise XAuthError(
            "twitter_auth_token / twitter_ct0 missing from agent-reach config — "
            "re-run `agent-reach configure twitter`"
        )
    env = os.environ.copy()
    env["TWITTER_AUTH_TOKEN"] = token
    env["TWITTER_CT0"] = ct0
    return env


def fetch_user_posts(handle: str, max_posts: int = 20) -> list[RawPost]:
    """Fetch recent posts for one X handle (without @)."""
    cmd = ["twitter", "user-posts", handle, "-n", str(max_posts), "--json"]
    log.info("X: fetching %d posts from @%s", max_posts, handle)
    proc = subprocess.run(
        cmd, env=_auth_env(), capture_output=True, text=True, timeout=300
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if "auth" in stderr.lower() or "401" in stderr or "403" in stderr:
            raise XAuthError(
                f"twitter CLI auth failure for @{handle} — X cookies likely expired; "
                f"re-run `agent-reach configure twitter`. stderr: {stderr[:500]}"
            )
        raise RuntimeError(f"twitter CLI failed for @{handle}: {stderr[:500]}")

    tweets = json.loads(proc.stdout)
    if isinstance(tweets, dict):  # some versions wrap the list
        tweets = tweets.get("tweets") or tweets.get("data") or []

    posts: list[RawPost] = []
    for t in tweets:
        text = t.get("text", "")
        # X posts wrap long-form articles; include their text when present
        if t.get("articleText"):
            text = f"{t.get('articleTitle', '')}\n{text}\n{t['articleText']}"
        urls = [u for u in (t.get("urls") or []) if isinstance(u, str)]
        quoted = t.get("quotedTweet") or {}
        if quoted.get("text"):
            text += f"\n[quoted @{(quoted.get('author') or {}).get('screenName', '')}]: {quoted['text']}"
        posts.append(
            RawPost(
                source=Source.x,
                kol=handle,
                external_id=str(t.get("id", "")),
                text=text,
                urls=urls,
                author_name=(t.get("author") or {}).get("name", ""),
                created_at=t.get("createdAtISO") or t.get("createdAt", ""),
                permalink=f"https://x.com/{handle}/status/{t.get('id', '')}",
            )
        )
    log.info("X: got %d posts from @%s", len(posts), handle)
    return posts
