"""InsightPulse CLI."""

from __future__ import annotations

import json
import subprocess
from datetime import date, timedelta

import typer
from rich.console import Console
from rich.table import Table

from insightpulse.logging_setup import setup_logging

app = typer.Typer(help="Semi-autonomous KOL paper/news → blog pipeline",
                  no_args_is_help=True, pretty_exceptions_show_locals=False)
console = Console()


@app.callback()
def _init(verbose: bool = typer.Option(False, "--verbose", "-v")):
    setup_logging(verbose)


def _parse_day_opt(value: str, opt: str) -> date:
    from insightpulse.dates import parse_day

    try:
        return parse_day(value)
    except ValueError:
        raise typer.BadParameter(f"{opt} must be YYYY-MM-DD") from None


def _parse_sources(value: str) -> set:
    from insightpulse.models import Source

    if value.strip().lower() == "all":
        return set(Source)
    try:
        sources = {Source(v.strip().lower()) for v in value.split(",") if v.strip()}
    except ValueError:
        sources = set()
    if not sources:
        raise typer.BadParameter("source must be all or a comma-separated mix of x, linkedin")
    return sources


def _parse_kinds(value: str) -> set:
    from insightpulse.models import Kind

    if value.strip().lower() == "all":
        return {Kind.paper, Kind.news}
    try:
        kinds = {Kind(v.strip().lower()) for v in value.split(",") if v.strip()}
    except ValueError:
        kinds = set()
    if not kinds or Kind.skip in kinds:
        raise typer.BadParameter("kind must be all or a comma-separated mix of paper, news")
    return kinds


@app.command()
def run(
    source: str = typer.Option("all", help="sources to crawl: all or a comma-separated "
                                           "mix of x, linkedin"),
    kind: str = typer.Option("all", help="kinds to write: all or a comma-separated mix "
                                         "of paper, news (others stay queued)"),
    limit: int = typer.Option(None, help="max items sent to the writer this run"),
    dry_run: bool = typer.Option(False, help="collect + dedup only, no agents"),
    date: str = typer.Option(None, "--date",
                             help="target day YYYY-MM-DD (UTC); default: yesterday"),
    auto_accept: bool = typer.Option(
        None, "--auto-accept/--no-auto-accept",
        help="accept + publish drafts immediately, skipping review "
             "(default: review.auto_accept in settings.yaml)"),
):
    """Run one pipeline pass over a single day: crawl → triage → enrich → write → queue."""
    from insightpulse.pipeline import run_pipeline

    target = _parse_day_opt(date, "--date") if date else None
    counts = run_pipeline(sources=_parse_sources(source), kinds=_parse_kinds(kind),
                          limit=limit, dry_run=dry_run, target_date=target,
                          auto_accept=auto_accept)
    console.print(f"[bold]Run finished:[/bold] {counts}")


@app.command()
def backfill(
    from_date: str = typer.Option(None, "--from", help="first day YYYY-MM-DD"),
    to_date: str = typer.Option(None, "--to",
                                help="last day YYYY-MM-DD (inclusive); default: yesterday"),
    days: int = typer.Option(None, "--days", help="backfill the last N complete days"),
    source: str = typer.Option("all", help="sources to crawl: all or a comma-separated "
                                           "mix of x, linkedin"),
    kind: str = typer.Option("all", help="kinds to write: all or a comma-separated mix "
                                         "of paper, news (others stay queued)"),
    limit: int = typer.Option(None, help="max items sent to the writer per day"),
    dry_run: bool = typer.Option(False, help="collect + dedup only, no agents"),
    auto_accept: bool = typer.Option(
        None, "--auto-accept/--no-auto-accept",
        help="accept + publish drafts immediately, skipping review "
             "(default: review.auto_accept in settings.yaml)"),
):
    """Run the pipeline once per past day, oldest first."""
    from insightpulse.dates import yesterday_utc
    from insightpulse.pipeline import run_pipeline

    sources = _parse_sources(source)
    kinds = _parse_kinds(kind)
    if (from_date is None) == (days is None):
        raise typer.BadParameter("pass exactly one of --from or --days")
    if days is not None and to_date is not None:
        raise typer.BadParameter("--to only combines with --from")

    end = _parse_day_opt(to_date, "--to") if to_date else yesterday_utc()
    if days is not None:
        if days < 1:
            raise typer.BadParameter("--days must be >= 1")
        start = end - timedelta(days=days - 1)
    else:
        start = _parse_day_opt(from_date, "--from")
    if start > end:
        raise typer.BadParameter(f"--from {start} is after {end}")
    if end > yesterday_utc():
        raise typer.BadParameter("--to cannot be later than yesterday (complete days only)")

    results: list[tuple[date, str]] = []
    failed = False
    day = start
    while day <= end:
        console.print(f"[bold]Backfilling {day}…[/bold]")
        try:
            counts = run_pipeline(sources=sources, kinds=kinds, limit=limit,
                                  dry_run=dry_run, target_date=day,
                                  auto_accept=auto_accept)
            results.append((day, str(counts)))
        except Exception as e:
            failed = True
            results.append((day, f"FAILED: {e}"))
            console.print(f"[red]{day} failed:[/red] {e}")
        day += timedelta(days=1)

    table = Table(title=f"Backfill {start} → {end}")
    table.add_column("day")
    table.add_column("result")
    for d, r in results:
        table.add_row(str(d), r)
    console.print(table)
    if failed:
        raise typer.Exit(1)


@app.command("list")
def list_cmd(status: str = typer.Option("pending", help="pending | accepted | rejected")):
    """List drafts in the review queue."""
    from insightpulse.queue import list_drafts

    drafts = list_drafts(status)
    if not drafts:
        console.print(f"No {status} drafts.")
        return
    table = Table(title=f"{status} drafts ({len(drafts)})")
    for col in ("id", "kind", "title", "topic", "kol", "vi", "figs"):
        table.add_column(col)
    for d in drafts:
        m = d.metadata
        topic = "/".join(m.get("topic_path", []))
        if m.get("topic_proposed"):
            topic += " *new"
        table.add_row(str(m.get("id")), str(m.get("kind", "")),
                      str(m.get("title", ""))[:60], topic, str(m.get("kol", "")),
                      "✓" if m.get("title_vi") else "",
                      str(len(m.get("figures", []) or [])) if m.get("figures") else "")
    console.print(table)


@app.command()
def show(draft_id: str):
    """Print a draft (frontmatter + body)."""
    from insightpulse.queue import find_draft

    path = find_draft(draft_id)
    if not path:
        console.print(f"[red]No draft {draft_id}[/red]")
        raise typer.Exit(1)
    console.print(path.read_text())


@app.command()
def review(draft_id: str):
    """Open a pending draft in codex for assisted review."""
    from insightpulse.paths import QUEUE_PENDING

    path = QUEUE_PENDING / f"{draft_id}.md"
    if not path.exists():
        console.print(f"[red]No pending draft {draft_id}[/red]")
        raise typer.Exit(1)
    prompt = (
        f"Review the blog draft at {path}. Check: factual accuracy against the "
        f"linked sources, that the story is understandable to a reader with no "
        f"ML background, that the Glossary only defines truly rare terms "
        f"(widely known ones like LLM or AI agent need no entry), that the "
        f"Vietnamese version reads naturally and keeps English tech terms "
        f"as-is (including in the title), topic classification "
        f"and keywords in the frontmatter. Suggest concrete edits, and apply "
        f"them to the file if I approve. Afterwards I will run "
        f"`insightpulse accept {draft_id}` or `insightpulse reject {draft_id}`."
    )
    subprocess.run(["codex", prompt])


@app.command()
def accept(
    draft_id: str,
    topic: str = typer.Option(None, "--topic", help="override topic path, e.g. ai/llm/agents"),
    no_build: bool = typer.Option(False, help="skip the Hugo site rebuild"),
):
    """Accept a draft: merge its topic into the tree and publish it to the blog."""
    from insightpulse import topics
    from insightpulse.publish import accept_draft, rebuild_site

    path = None
    if topic:
        path = topic.strip("/").split("/")
        valid, err, _ = topics.validate_path(path)
        if not valid:
            console.print(f"[red]--topic invalid: {err}[/red]")
            raise typer.Exit(1)

    out = accept_draft(draft_id, topic_override=path)
    console.print(f"[green]Accepted[/green] {draft_id} → {out}")
    if not no_build:
        rebuild_site()
        console.print("Site rebuilt.")


@app.command()
def reject(
    draft_id: str,
    reason: str = typer.Option("", "--reason", help="why the draft was rejected"),
):
    """Reject a pending draft."""
    from insightpulse.queue import move_draft
    from insightpulse.state import State

    move_draft(draft_id, "rejected", {"reject_reason": reason} if reason else {})
    with State() as state:
        if state.get_item(draft_id):
            state.set_status(draft_id, "rejected")
    console.print(f"[yellow]Rejected[/yellow] {draft_id}")


@app.command()
def publish():
    """Rebuild the Hugo site from all accepted posts."""
    from insightpulse.publish import rebuild_site

    rebuild_site()
    console.print("Site rebuilt.")


@app.command()
def status():
    """Show item counts and recent runs."""
    from insightpulse.state import State

    with State() as state:
        counts = state.status_counts()
        table = Table(title="Items by status")
        table.add_column("status")
        table.add_column("count", justify="right")
        for k in sorted(counts):
            table.add_row(k, str(counts[k]))
        console.print(table)

        runs = state.recent_runs()
        if runs:
            rt = Table(title="Recent runs")
            for col in ("run_id", "started", "finished", "counts"):
                rt.add_column(col)
            for r in runs:
                rt.add_row(r["run_id"], r["started_at"], r["finished_at"],
                           json.dumps(json.loads(r["counts_json"] or "{}")))
            console.print(rt)


if __name__ == "__main__":
    app()
