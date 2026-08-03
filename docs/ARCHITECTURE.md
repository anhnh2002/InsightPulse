# Architecture

## Pipeline data flow (`insightpulse run`)

1. **collect** — `sources/x_source.py` runs the Agent-Reach `twitter` CLI (`user-posts <handle> --json`, structured output, cookies injected from `~/.agent-reach/config.yaml`). `sources/linkedin_source.py` runs `mcporter call linkedin-scraper.get_person_profile/get_company_posts` (raw innerText; persistent logged-in Chromium profile, strictly sequential). Raw captures are saved to `data/raw/<run_id>/`.
2. **extract** (LinkedIn only) — `agents/linkedin_extractor.py`: a cheap caw agent parses the raw innerText into structured posts via a `submit_posts` tool.
3. **dedup** — `state.py` inserts posts into SQLite with a unique `dedup_key` (tweet id for X, text hash for LinkedIn); only new rows continue.
4. **triage** — `agents/triage.py`: a cheap caw agent classifies each new post as `paper` / `news` / `skip` and extracts canonical links (arXiv, GitHub) via `submit_triage`. Short links (lnkd.in, t.co, …) are resolved with HTTP redirects before triage. A second dedup pass drops papers whose arXiv id is already covered.
5. **enrich** — `enrich/arxiv.py` fetches paper metadata (export.arxiv.org API) and full text (ar5iv → arxiv HTML → abstract fallback) into the item workdir as `paper.txt`; `enrich/figures.py` extracts paper figures into `figures/figNN.png` + `figures.json` (captions), parsing `<figure>` blocks from the same ar5iv/arxiv HTML, with a pymupdf PDF fallback (embedded raster images, or rendered vector-drawing clusters anchored to "Figure N" captions). `enrich/github.py` fetches repo stars/license/activity via `gh api`. News items get linked-page text as `content.txt`. A `paper` with no resolvable arXiv link is downgraded to the news flow.
6. **write** — `agents/writer.py`: a frontier caw agent is chdir'd into `data/runs/<run_id>/items/<item_id>/` (containing `paper.txt`/`content.txt` + `meta.json` + optional `figures/`), reads the files with its built-in tools (it can view the figure images), calls `get_topic_tree`, and submits via `submit_blog` — one call carrying **both the English and Vietnamese versions** (`title/summary/body_markdown` + `title_vi/summary_vi/body_markdown_vi`) plus an optional `hero_figure`. Validation checks required sections in both languages (storytelling skeleton: The Big Idea / How It Works / What They Found / Glossary / Links for papers), 3–8 keywords, topic path, and that every `![...](figures/...)` reference and the hero figure actually exist; errors are returned for self-correction.
7. **queue** — `queue.py` writes the validated draft as markdown + YAML frontmatter to `data/queue/pending/<item_id>.md` — the English body, then a `<!--vi-->` separator line, then the Vietnamese body, so both versions are reviewed in one file. Referenced figures are copied to `data/queue/pending/<item_id>/figures/` and travel with the draft on accept/reject.

Per-item failures mark the item `failed:<stage>` and never abort the run; triaged-but-unwritten items (over `--limit`, or failed writes) are picked up by the next run.

## caw agent conventions (`agents/base.py`)

- The **ToolKit instance is the result channel**: structured results are read off the toolkit after the session, never parsed from agent text. Validation errors are returned as tool results so the agent retries within the session.
- `provider` comes from `config/settings.yaml` (`codex` → Codex subscription via `codex exec`, auth in `~/.codex/auth.json`).
- `auto_wait=False` — provider rate limits fail fast instead of silently sleeping until the reset window.
- `data_dir` points at the run output dir so caw session files never pollute the repo; `os.chdir` gives the writer its item workdir.
- Sessions are always context-managed (toolkits are real HTTP MCP servers that would otherwise leak).
- Model names in settings are raw provider strings (e.g. `gpt-5.6-sol`); caw's built-in `FAST`/`STRONGEST` tier map can lag what the Codex account actually supports.

## Topic-tree protocol

- `config/topics.yaml` holds only the **accepted** taxonomy (max depth 3).
- The writer picks the most specific existing path, or proposes a new node under an existing root (`topic_proposed: true` in draft frontmatter).
- `get_topic_tree` also shows paths proposed by drafts still pending review, so concurrent drafts converge instead of inventing near-duplicates.
- `insightpulse accept` merges the draft's path into `topics.yaml` (with `--topic` override); rejecting changes nothing, so the tree never accumulates junk.

## Review queue

Drafts are plain markdown files with YAML frontmatter (`id`, `kind`, `title`, `title_vi`, `topic_path`, `keywords`, `paper`, `repo`, `reliability`, `social`, `hero_figure`, `figures`, …) in `data/queue/{pending,accepted,rejected}/`; the body holds the English version, a `<!--vi-->` separator, then the Vietnamese version. A sibling `<id>/figures/` dir carries the referenced images. Review them in any editor, with `insightpulse review <id>` (spawns codex), or via `show`. Lifecycle status is mirrored in SQLite.

## Blog

Hugo (PaperMod theme, vendored in `blog/site/themes/`), **bilingual** (`en` at `/`, `vi` under `/vi/`, per-language menus in `hugo.toml`; PaperMod's translation switcher and hreflang tags come free) with two taxonomies: `tags` (flat keywords) and `topics` (hierarchical slugs — a post with `topic_path: [ai, llm, agents]` gets terms `ai`, `ai/llm`, `ai/llm/agents`, so every tree level has a page). `publish.py` writes each accepted draft as a **leaf page bundle** `content/posts/<date>-<slug>/` containing `index.md` (EN), `index.vi.md` (VI, auto-linked as its translation), and the `figures/` it references; `hero_figure` becomes PaperMod's `cover` (responsive srcset + og:image; posts without figures fall back to the site-wide `params.images` default). A small `post_meta_extra.html` partial renders the metadata box (paper authors, repo stars/license/activity, original-post link, and the slim `reliability` facts — the body itself no longer has a Reliability section). Site-level extras: a mermaid render hook + vendored `static/js/mermaid.min.js` (loaded only on pages that use it), a `source-post` shortcode (static quote card of the originating social post, fed by the `social` frontmatter), and `assets/css/extended/custom.css` (tables, pull-quotes, figure captions). The site is built by a one-shot `hugomods/hugo` container and served by nginx (`docker compose up -d web`, port 8080). Note: Hugo reserves the `kind` frontmatter key, so the post's type is published as `item_kind`.

## State

Single SQLite file `data/state.db`: `items` (dedup keys, lifecycle `collected → triaged → enriched → drafted → accepted|rejected`, `failed:<stage>`, `skipped`) and `runs` (history + counts). Item ids are `YYYYMMDD-<8 hex>`.
