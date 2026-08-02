"""Hierarchical topic tree: render for prompts, validate paths, merge on accept."""

from __future__ import annotations

import logging
import re

import yaml

from insightpulse.config import load_settings
from insightpulse.paths import CONFIG_DIR, QUEUE_PENDING

log = logging.getLogger(__name__)

TOPICS_FILE = CONFIG_DIR / "topics.yaml"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def load_tree() -> list[dict]:
    with open(TOPICS_FILE) as f:
        return (yaml.safe_load(f) or {}).get("topics", [])


def save_tree(tree: list[dict]) -> None:
    header = (
        "# Accepted hierarchical topic taxonomy (max depth 3).\n"
        "# Writer agents may PROPOSE new nodes; they are merged here only when"
        " a draft is accepted.\n"
    )
    with open(TOPICS_FILE, "w") as f:
        f.write(header)
        yaml.safe_dump({"topics": tree}, f, sort_keys=False, allow_unicode=True)


def _render(nodes: list[dict], prefix: list[str], lines: list[str]) -> None:
    for n in nodes:
        path = prefix + [n["slug"]]
        lines.append(f"{'  ' * (len(path) - 1)}- {'/'.join(path)}  ({n.get('name', n['slug'])})")
        _render(n.get("children") or [], path, lines)


def pending_proposals() -> list[list[str]]:
    """Topic paths proposed by drafts currently in the pending queue."""
    import frontmatter

    proposals = []
    for f in sorted(QUEUE_PENDING.glob("*.md")):
        try:
            meta = frontmatter.load(f).metadata
        except Exception:
            continue
        if meta.get("topic_proposed") and meta.get("topic_path"):
            proposals.append([str(s) for s in meta["topic_path"]])
    return proposals


def render_tree_for_prompt() -> str:
    lines: list[str] = []
    _render(load_tree(), [], lines)
    proposals = pending_proposals()
    out = "Accepted topic tree (path  (name)):\n" + "\n".join(lines)
    if proposals:
        out += (
            "\n\nPaths already PROPOSED by drafts awaiting review"
            " (prefer reusing these over inventing near-duplicates):\n"
            + "\n".join(f"- {'/'.join(p)}" for p in proposals)
        )
    return out


def validate_path(path: list[str]) -> tuple[bool, str, bool]:
    """Returns (valid, error_message, is_new_proposal)."""
    max_depth = load_settings().topics.max_depth
    if not path:
        return False, "topic_path is empty", False
    if len(path) > max_depth:
        return False, f"topic_path deeper than {max_depth} levels", False
    for slug in path:
        if not SLUG_RE.match(slug):
            return (False,
                    f"invalid slug '{slug}' (lowercase letters/digits/hyphens only)",
                    False)

    nodes = load_tree()
    existing_roots = {n["slug"] for n in nodes}
    if path[0] not in existing_roots:
        return (False,
                f"root '{path[0]}' does not exist; new nodes may only be created"
                f" under an existing root ({sorted(existing_roots)})",
                False)

    is_new = False
    for slug in path:
        node = next((n for n in nodes if n["slug"] == slug), None)
        if node is None:
            is_new = True
            nodes = []
        else:
            nodes = node.get("children") or []
    return True, "", is_new


def merge_path(path: list[str]) -> None:
    """Merge a topic path into topics.yaml, creating missing nodes."""
    tree = load_tree()
    nodes = tree
    for slug in path:
        node = next((n for n in nodes if n["slug"] == slug), None)
        if node is None:
            node = {"slug": slug, "name": slug.replace("-", " ").title()}
            nodes.append(node)
        if slug != path[-1]:
            node.setdefault("children", [])
            nodes = node["children"]
    save_tree(tree)
    log.info("topics: merged path %s", "/".join(path))
