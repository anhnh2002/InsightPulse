# InsightPulse

Semi-autonomous pipeline that watches AI/ML thought leaders (KOLs) on **X** and **LinkedIn**, has AI agents write opinionated blog drafts about the papers and news they share, queues the drafts for **your** review, and publishes accepted posts to a self-hosted blog.

```
X / LinkedIn ──collect──▶ extract ──▶ dedup ──▶ triage ──▶ enrich ──▶ write ──▶ review queue ──accept──▶ blog
   (Agent-Reach)          (agent)   (SQLite)   (agent)  (arXiv/gh)  (agent)   (markdown files)        (Hugo+nginx)
```

## Prerequisites (host)

The pipeline runs on the host (not in Docker) because it depends on host-side auth:

- **[Agent-Reach](https://github.com/Panniantong/Agent-Reach)** installed and authenticated:
  - X: `twitter` CLI with cookies in `~/.agent-reach/config.yaml` (`agent-reach configure twitter`)
  - LinkedIn: `linkedin-scraper-mcp` via `mcporter`, logged-in browser profile in `~/.linkedin-mcp/`
- **codex CLI** authenticated (`~/.codex/auth.json`) — agents run on your Codex subscription via [caw](https://github.com/zzjas/caw)
- **gh** CLI (GitHub repo metadata), **docker** + compose (blog serving/build), **uv**

Setup:

```bash
uv sync
docker compose up -d web        # blog at http://localhost:8080
```

## Usage

```bash
uv run insightpulse run                     # one full pass (all sources)
uv run insightpulse run --source x --limit 3
uv run insightpulse run --dry-run           # collect + dedup only, no agents

uv run insightpulse list                    # pending drafts
uv run insightpulse show <id>               # print a draft
uv run insightpulse review <id>             # open the draft in codex for assisted review
uv run insightpulse accept <id>             # merge topic, publish to blog, rebuild site
uv run insightpulse accept <id> --topic ai/llm/agents   # fix classification while accepting
uv run insightpulse reject <id> --reason "duplicate"

uv run insightpulse publish                 # rebuild the site manually
uv run insightpulse status                  # item counts + recent runs
```

Drafts are plain markdown files in `data/queue/pending/` — you can also edit them directly (or point codex at them) before accepting.

## Configuration

- `config/kols.yaml` — the KOL watchlist; edit freely, picked up next run.
- `config/topics.yaml` — the accepted topic taxonomy. Writer agents propose new nodes; proposals are merged only when you accept the draft.
- `config/settings.yaml` — models per agent role, per-run limits, text caps.

## Scheduling (cron)

The pipeline is a single idempotent pass (dedup is cross-run), so cron is enough:

```cron
0 8 * * * cd ~/InsightPulse && uv run insightpulse run >> data/cron.log 2>&1
```

A `.run.lock` in `data/` prevents overlapping runs (LinkedIn's browser profile only tolerates one process anyway).

## Debugging agent runs

Every agent run writes a trajectory to `data/runs/<run_id>/logs/*.traj.json` (inspect with `caw traj <path>` or `caw viewer`), plus the exact system prompt used. Raw social captures land in `data/raw/<run_id>/`. Failed items get status `failed:<stage>` in `data/state.db` and are retried on the next run.

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — data flow, agent designs, topic-tree protocol
- [docs/ROADMAP.md](docs/ROADMAP.md) — planned later work (trend agent, web review UI, pipeline containerization, …)
