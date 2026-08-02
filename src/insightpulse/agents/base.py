"""Shared caw agent runner.

Conventions (from the proven cgsa pattern):
- the ToolKit instance is the result channel — callers read structured results
  off the toolkit after the run, never from the agent's final text;
- data_dir points at the run output dir so caw session files never pollute
  the repo or the agent's working directory;
- auto_wait=False so provider rate limits fail fast instead of sleeping
  silently for the reset window;
- sessions are always context-managed (tool servers are real HTTP MCP servers
  that leak otherwise).
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path

from caw import Agent, ModelTier, ToolGroup

from insightpulse.config import load_settings

log = logging.getLogger(__name__)

_TIERS = {"FAST": ModelTier.FAST, "STRONGEST": ModelTier.STRONGEST}


class AgentRunError(RuntimeError):
    pass


def resolve_model(name: str):
    """Map a settings model name (FAST/STRONGEST/raw string) to a caw model."""
    return _TIERS.get(name, name)


@contextmanager
def _chdir(path: Path | None):
    if path is None:
        yield
        return
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def run_agent(
    *,
    name: str,
    system_prompt: str,
    user_prompt: str,
    model: str,
    toolkit,
    output_dir: Path,
    traj_name: str,
    workdir: Path | None = None,
    tools: ToolGroup = ToolGroup.NO_INTERACTION,
    check_done=None,
    retry_prompt: str = "",
) -> None:
    """Run a single-turn caw agent; results accumulate on `toolkit`.

    check_done: optional () -> bool read off the toolkit; when it returns False
    after the first turn, `retry_prompt` is sent once more in the same session.
    """
    settings = load_settings()
    output_dir.mkdir(parents=True, exist_ok=True)
    traj_path = output_dir / f"{traj_name}.traj.json"
    (output_dir / f"{traj_name}.system_prompt.md").write_text(system_prompt)

    agent = Agent(
        provider=settings.provider,
        name=name,
        system_prompt=system_prompt,
        model=resolve_model(model),
        tools=tools,
        tool_servers=[toolkit],
        data_dir=str(output_dir),
        auto_wait=False,
    )

    with _chdir(workdir):
        with agent.start_session(traj_path=str(traj_path)) as session:
            session.send(user_prompt)
            if check_done is not None and not check_done():
                log.warning("%s: no result submitted, retrying once", name)
                session.send(
                    retry_prompt
                    or "You have not submitted results via the required tool yet. "
                    "Call the submission tool now with your results."
                )

    if check_done is not None and not check_done():
        raise AgentRunError(f"{name}: agent finished without submitting results")


def load_prompt(name: str) -> str:
    return (Path(__file__).parent / "prompts" / name).read_text()
