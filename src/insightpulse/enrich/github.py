"""GitHub repo reliability metadata via the `gh` CLI."""

from __future__ import annotations

import json
import logging
import re
import subprocess

from insightpulse.models import RepoMeta

log = logging.getLogger(__name__)

REPO_RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?]|$)")


def repo_from_url(url: str) -> str:
    m = REPO_RE.search(url)
    if not m:
        return ""
    owner, name = m.group(1), m.group(2)
    if owner.lower() in ("features", "topics", "orgs", "sponsors", "search"):
        return ""
    return f"{owner}/{name}"


def fetch_repo_meta(url: str) -> RepoMeta | None:
    full_name = repo_from_url(url)
    if not full_name:
        return None
    proc = subprocess.run(
        ["gh", "api", f"repos/{full_name}"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        log.warning("gh api failed for %s: %s", full_name, proc.stderr.strip()[:200])
        return None
    d = json.loads(proc.stdout)
    return RepoMeta(
        url=d.get("html_url", url),
        full_name=d.get("full_name", full_name),
        stars=d.get("stargazers_count", 0),
        license=(d.get("license") or {}).get("spdx_id", "") or "",
        pushed_at=(d.get("pushed_at") or "")[:10],
        archived=bool(d.get("archived")),
        description=d.get("description") or "",
    )
