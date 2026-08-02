# Roadmap — later implementation

Documented here per the original design; none of this is built yet.

## Trend-summarization agent
Treat accepted blogs as a knowledge base: a periodic caw agent reads recent accepted posts (`data/queue/accepted/` + published content), clusters by topic tree, and writes a "recent trends" digest post. Needs: a `trends` CLI command, a digest prompt, and a way to mark digest posts distinctly on the blog.

## Web review UI
Replace/augment the file+CLI queue with a small local web dashboard (list pending drafts, inline edit, accept/reject buttons, topic picker fed by `topics.yaml`). The file-based queue stays the source of truth; the UI is a front-end over `queue.py`.

## Pipeline containerization
Currently the pipeline runs on the host because auth is host-side. To containerize:
- caw: `caw auth setup` symlinks host creds into `~/.caw/auth/`; `caw auth docker-flags` emits the bind-mount flags (works for codex/claude CLIs).
- X: mount `~/.agent-reach/config.yaml` (or pass `TWITTER_AUTH_TOKEN`/`TWITTER_CT0` as secrets) + install `twitter-cli` in the image.
- LinkedIn: hardest — needs the patchright Chromium + the logged-in profile dir (`~/.linkedin-mcp/`) mounted, and only one process may hold `profile.lock`.
- Then add a `pipeline` service (with an ofelia/cron sidecar for scheduling) to docker-compose.

## Smaller items
- Retry/backoff queue for codex rate limits (today: fail fast, item retried next run).
- Richer paper ingestion: PDF figures, OpenReview reviews as extra writer context.
- OpenReview / HuggingFace papers as first-class sources alongside X/LinkedIn.
- Blog polish: OG images, per-post hero images, comments.
- Taxonomy refactoring tooling: moving existing published posts when the topic tree is reorganized.
- LinkedIn dedup hardening: text-hash dedup can duplicate edited posts (arXiv-id dedup already catches the same-paper case).
- `insightpulse watch` streaming mode (Agent-Reach has a `watch` command) instead of poll-based cron.
