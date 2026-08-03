"""Fetch KOL posts from LinkedIn via mcporter → linkedin-scraper MCP server.

The scraper drives a persistent logged-in Chromium profile (~/.linkedin-mcp/)
guarded by a profile.lock, so LinkedIn fetches must run sequentially. Results
are semi-structured raw innerText that a downstream LLM extraction step parses.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess

log = logging.getLogger(__name__)

RATE_LIMIT_SENTINEL = "[Rate limited]"


class LinkedInRateLimited(RuntimeError):
    pass


class LinkedInFetchError(RuntimeError):
    pass


def _mcporter_call(expr: str, timeout: int = 420) -> str:
    cmd = ["mcporter", "call", expr]
    log.info("LinkedIn: %s", expr.split("(")[0])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout).strip()
        if "profile.lock" in stderr or "lock" in stderr.lower():
            raise LinkedInFetchError(
                "LinkedIn browser profile is locked by another process — "
                "wait for it to finish and retry"
            )
        raise LinkedInFetchError(f"mcporter call failed: {stderr[:500]}")
    return proc.stdout


def _extract_json(output: str) -> dict:
    """mcporter prints the tool result, possibly with log lines around the JSON."""
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    # Not JSON at all — treat the whole output as one raw text section
    return {"sections": {"raw": output}}


def _check_rate_limit(data: dict) -> None:
    for section, err in (data.get("section_errors") or {}).items():
        err_text = json.dumps(err) if isinstance(err, dict) else str(err)
        if "rate_limit" in err_text or RATE_LIMIT_SENTINEL in err_text:
            raise LinkedInRateLimited(
                f"LinkedIn rate-limited on section '{section}' — try again later"
            )


def _fetch(expr: str, target: str) -> dict:
    data = _extract_json(_mcporter_call(expr))
    _check_rate_limit(data)
    sections = data.get("sections") or {}
    if not any(v and str(v).strip() for v in sections.values()):
        raise LinkedInFetchError(
            f"LinkedIn returned no post content for {target} "
            f"(section_errors: {data.get('section_errors')})"
        )
    return data


def fetch_person_raw(username: str, max_scrolls: int) -> dict:
    """Fetch the raw posts payload for a person profile at the given scroll depth."""
    expr = (
        f'linkedin-scraper.get_person_profile(linkedin_username: "{username}", '
        f'sections: "posts", max_scrolls: {max_scrolls})'
    )
    return _fetch(expr, username)


def fetch_company_raw(company_name: str) -> dict:
    """Fetch the raw posts payload for a company page (depth is not tunable)."""
    expr = f'linkedin-scraper.get_company_posts(company_name: "{company_name}")'
    return _fetch(expr, company_name)
