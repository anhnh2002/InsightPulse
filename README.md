# InsightPulse

Semi-autonomous pipeline that surfaces noteworthy AI papers and news (discovered via what AI/ML researchers share on **X** and **LinkedIn**), has AI agents write big-picture summaries of each paper's core idea, queues the drafts for **your** review, and publishes accepted posts to a self-hosted blog — keep up with AI without spending hours reading every paper.

```
X / LinkedIn ──crawl+extract──▶ dedup ──▶ triage ──▶ enrich ──▶ write ──▶ review queue ──accept──▶ blog
 (Agent-Reach)  (agent-driven)  (SQLite)   (agent)  (arXiv/gh)  (agent)   (markdown files)        (Hugo+nginx)
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
uv run insightpulse run                     # one pass over yesterday (UTC), all sources
uv run insightpulse run --date 2026-07-30   # a specific day
uv run insightpulse run --source x --limit 3          # X only (--source x,linkedin for both)
uv run insightpulse run --kind paper                  # write only paper posts; triaged news
                                                      # stays queued for a later run
uv run insightpulse run --dry-run           # collect + dedup only, no blog writing
uv run insightpulse posts                   # inspect the raw crawled posts (--full for everything)
uv run insightpulse process                 # triage + write what was collected, no re-crawl
uv run insightpulse run --auto-accept       # publish drafts immediately, no review

uv run insightpulse backfill --days 7          # last 7 complete days; writes ALL
                                               # ready items (no per-run cap)
uv run insightpulse backfill --source linkedin --kind paper --auto-accept --days 30
uv run insightpulse backfill --from 2026-07-20 --to 2026-07-25

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

To run fully autonomously, skip the review queue with `--auto-accept` (or set `review.auto_accept: true` in `config/settings.yaml` to make it the default; `--no-auto-accept` overrides it per run). Drafts are then accepted and published as soon as they are written — including any new topic nodes the writer proposes — and the site is rebuilt once at the end of the run. A draft whose accept step fails stays in `data/queue/pending/` for manual handling.

## Admin UI

A small host-run web app for reviewing the queue and managing published posts (the blog's nginx proxies `/admin` to it):

```bash
uv run insightpulse admin set-password   # once; stores a hash in data/admin_auth.json (git-ignored)
uv run insightpulse admin serve          # http://localhost:8080/admin/ (or directly :8082/admin/)
docker compose up -d --force-recreate web   # once after pulling this feature, to load the new nginx config
```

From there: edit/accept/reject pending drafts, add/edit/delete published posts, and rebuild the site with one button (mutations show a "site out of date" banner instead of rebuilding on every change).

Papers whose link couldn't be resolved automatically (no arXiv URL in the post, title search came up empty) are **not** written — they park in a **Missing links** list (`/admin/links`, status `needs_link`) so no writer budget is spent on them. Find the paper and paste its arXiv URL there (non-arXiv URLs are rejected; Skip posts you never want written). Filled items are written by the next pipeline run, or immediately via the page's **Write now** button, which runs `insightpulse process --kind paper` in the background (log: `data/admin_process.log`). Published posts that still lack a link (from before this flow) keep a ⚠ badge and a fill form on their edit page; filling one updates both languages — hit Rebuild afterwards.

Notes:
- The server binds `0.0.0.0:8082` so the nginx container can reach it via `host.docker.internal` — on a LAN, the admin port is reachable from other machines (password-protected; put a firewall rule on 8082 if that matters).
- CSRF is mitigated by the `SameSite=Lax` session cookie; if you ever expose the admin beyond your LAN, add per-session CSRF tokens and TLS first.
- To keep it running: `systemd` unit with `WorkingDirectory=<repo>` and `ExecStart=uv run insightpulse admin serve`.

## Configuration

- `config/kols.yaml` — the KOL watchlist; edit freely, picked up next run.
- `config/topics.yaml` — the accepted topic taxonomy. Writer agents propose new nodes; proposals are merged only when you accept the draft.
- `config/settings.yaml` — models per agent role, per-run limits, text caps.

## Scheduling (cron)

Each run covers a UTC day window of posts — by default just **yesterday** (a complete day). Pass `--days 2` to also sweep today-so-far, so fresh posts land the same day instead of waiting for tomorrow's run; dedup makes the overlap free. Open your crontab with `crontab -e` and add an entry like:

```cron
0 8 * * * cd ~/InsightPulse && $HOME/.local/bin/uv run insightpulse run --source linkedin --kind paper --days 2 >> data/cron.log 2>&1
```

(This is a crontab line, not a shell command — the `0 8 * * *` prefix is the schedule, daily at 08:00. Use the absolute path to `uv` — `which uv` — because cron runs with a minimal `PATH`.)

Runs are idempotent: the day window plus cross-run dedup means re-running a day collects nothing new and only retries previously failed items. If cron missed some days, catch up with `insightpulse backfill --days N` (or `--from`/`--to`) — it runs the pipeline **once over the whole window**: X is fetched per day (date-scoped search), while LinkedIn is crawled in a single agent-driven pass that scrolls each KOL deep enough to cover the window. LinkedIn only exposes relative post ages ("3d", "2 tuần"), so window matching is precision-tolerant ("2w" → ±3 days); beyond ~a month coverage becomes unreliable.

A `.run.lock` in `data/` prevents overlapping runs (LinkedIn's browser profile only tolerates one process anyway).

## Debugging agent runs

Every agent run writes a trajectory to `data/runs/<run_id>/logs/*.traj.json` (inspect with `caw traj <path>` or `caw viewer`), plus the exact system prompt used. Raw social captures land in `data/raw/<run_id>/`. Failed items get status `failed:<stage>` in `data/state.db` and are retried on the next run.

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — data flow, agent designs, topic-tree protocol
- [docs/ROADMAP.md](docs/ROADMAP.md) — planned later work (trend agent, web review UI, pipeline containerization, …)
