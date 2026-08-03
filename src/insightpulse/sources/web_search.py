"""Web search via mcporter → exa MCP server (hosted, keyless)."""

from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)

_SNIPPET_CHARS = 700


class WebSearchError(RuntimeError):
    pass


def _mcporter_call(expr: str, timeout: int = 60) -> str:
    cmd = ["mcporter", "call", expr]
    log.info("web search: %s", expr.split("(")[0])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout).strip()
        raise WebSearchError(f"mcporter call failed: {stderr[:500]}")
    return proc.stdout


def _parse_results(output: str) -> list[dict]:
    """exa prints plain-text blocks: 'Title: …' / 'URL: …' / highlight lines."""
    results: list[dict] = []
    cur: dict | None = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Title:"):
            cur = {"title": stripped[len("Title:"):].strip(), "url": "", "snippet": ""}
            results.append(cur)
        elif cur is None:
            continue
        elif stripped.startswith("URL:"):
            cur["url"] = stripped[len("URL:"):].strip()
        elif stripped and not stripped.startswith(("Published:", "Author:", "Highlights:")):
            if len(cur["snippet"]) < _SNIPPET_CHARS:
                cur["snippet"] = (cur["snippet"] + " " + stripped).strip()[:_SNIPPET_CHARS]
    return [r for r in results if r["url"]]


def search_web(query: str, num_results: int = 5) -> list[dict]:
    """Top web results for a query as [{title, url, snippet}]."""
    escaped = query.replace("\\", "\\\\").replace('"', '\\"')
    expr = f'exa.web_search_exa(query: "{escaped}", numResults: {num_results})'
    results = _parse_results(_mcporter_call(expr))
    if not results:
        raise WebSearchError(f"web search returned no results for {query!r}")
    return results
