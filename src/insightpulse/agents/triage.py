"""Batch triage of collected posts into paper / news / skip."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from caw import ToolKit, tool

from insightpulse.agents.base import load_prompt, run_agent
from insightpulse.config import load_settings
from insightpulse.models import Kind, TriageResult

log = logging.getLogger(__name__)

ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?")


def arxiv_id_from_url(url: str) -> str:
    m = ARXIV_ID_RE.search(url)
    return m.group(1) if m else ""


class TriageToolKit(ToolKit, server_name="triage_reporter",
                    display_name="Post Triage Reporter", thread_safe=True):
    def __init__(self, expected_ids: list[str]):
        self.expected_ids = set(expected_ids)
        self.results: list[TriageResult] = []

    @tool(
        name="submit_triage",
        description=(
            "Submit triage results as a JSON array, one element per input post: "
            '{"post_id": str, "kind": "paper"|"news"|"skip", "arxiv_url": str, '
            '"github_url": str, "links": [str], "working_title": str, "reason": str}. '
            "Call exactly once covering every post_id."
        ),
    )
    async def submit_triage(self, results_json: str) -> str:
        try:
            data = json.loads(results_json)
        except json.JSONDecodeError as e:
            return f"ERROR: invalid JSON ({e}). Fix and resubmit."
        if not isinstance(data, list):
            return "ERROR: expected a JSON array. Fix and resubmit."
        parsed, errors = [], []
        for i, r in enumerate(data):
            try:
                parsed.append(TriageResult.model_validate(r))
            except Exception as e:
                errors.append(f"result[{i}]: {e}")
        got_ids = {r.post_id for r in parsed}
        missing = self.expected_ids - got_ids
        unknown = got_ids - self.expected_ids
        if missing:
            errors.append(f"missing post_ids: {sorted(missing)}")
        if unknown:
            errors.append(f"unknown post_ids: {sorted(unknown)}")
        if errors:
            return "ERROR: " + "; ".join(errors)[:2000] + ". Fix and resubmit."
        self.results = parsed
        return f"Accepted {len(parsed)} triage results."


def triage_posts(posts: list[dict], output_dir: Path, batch_label: str) -> list[TriageResult]:
    """posts: [{"post_id", "kol", "source", "text", "urls"}] — one triage agent call."""
    toolkit = TriageToolKit([p["post_id"] for p in posts])
    payload = json.dumps(posts, indent=2, ensure_ascii=False)
    run_agent(
        name="Post Triage Agent",
        system_prompt=load_prompt("triage.md"),
        user_prompt=f"Triage the following {len(posts)} posts:\n\n{payload}",
        model=load_settings().models.triage,
        toolkit=toolkit,
        output_dir=output_dir,
        traj_name=f"triage_{batch_label}",
        check_done=lambda: bool(toolkit.results),
    )
    counts: dict[str, int] = {}
    for r in toolkit.results:
        counts[r.kind.value] = counts.get(r.kind.value, 0) + 1
    log.info("Triage %s: %s", batch_label, counts)
    return toolkit.results
