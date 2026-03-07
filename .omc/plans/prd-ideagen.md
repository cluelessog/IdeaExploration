# PRD: IdeaGen — Automated Idea Generation Framework

**Created:** 2026-03-07
**Status:** Ready for Ralph execution
**Implementation Plan:** `.omc/plans/ideagen-implementation.md`
**WTP Research:** `.omc/research/high-wtp-segments.md`

---

## Problem Statement

Entrepreneurs and builders waste hours manually browsing Reddit, Hacker News, Twitter, and Product Hunt to find business opportunities. There is no automated tool that scrapes trending data, identifies pain points and market gaps, and generates novel business ideas targeting audiences that actually spend money — all from a single terminal command with zero setup.

## Goals

1. Build a Python CLI tool (`ideagen`) that automates the full idea generation pipeline: scrape → analyze → synthesize → score → store
2. All 4 data sources work without login or API keys (web scraping only)
3. AI analysis via `claude` CLI subprocess (Claude Code Max plan, no SDK needed)
4. Built-in knowledge of 22 high willingness-to-pay audience segments
5. Three modes: single-shot (`run`), scheduled (`schedule`), interactive REPL (`interactive`)
6. Library-first architecture: core logic reusable by future web/desktop frontends

## Non-Goals

- No web framework (no FastAPI/Flask) in this version
- No Docker/containerization
- No paid API integrations for any data source
- No LangChain or heavy orchestration frameworks
- No GUI
- No cost tracking (unlimited plan)

---

## Acceptance Criteria

### Phase 1: Foundation
- [ ] `pip install -e .` succeeds; `ideagen --help` shows version
- [ ] All Pydantic models instantiate with valid data and reject invalid data
- [ ] `IdeaGenConfig` works with defaults (no config file needed); no filesystem imports in `core/config.py`
- [ ] ABCs enforce method signatures; `AIProvider` has only `complete()` method
- [ ] `@with_retry` decorator retries with exponential backoff
- [ ] `extract_json()` strips markdown code fences and returns clean JSON
- [ ] Structured logging outputs JSON format

### Phase 2: Data Sources
- [ ] HN collector returns TrendingItems from live Firebase API (no auth)
- [ ] Reddit collector scrapes old.reddit.com and returns TrendingItems (no login)
- [ ] Product Hunt collector scrapes producthunt.com and returns TrendingItems (no login)
- [ ] Twitter/X collector returns TrendingItems via snscrape (no auth, fallback to ntscraper)
- [ ] Source registry returns all 4 sources by default (no credential check needed)
- [ ] Rate limiter throttles requests to configured delay per source
- [ ] Each scraper has a `PARSER_VERSION` constant
- [ ] `sources test` command reports live status of each source

### Phase 3: AI Provider Layer
- [ ] Claude provider shells out to `claude` CLI via stdin pipe and returns validated Pydantic models
- [ ] Clear error message when `claude` CLI is not installed or not authenticated
- [ ] Large prompts (>100KB) work via stdin pipe
- [ ] Prompts include JSON schema (via `model_json_schema()`) and WTP segment context
- [ ] `AnalysisPipeline` calls `provider.complete()` with correct prompts; prompt logic lives in core only
- [ ] Optional OpenAI provider works via `pip install ideagen[openai]`
- [ ] Optional Gemini provider works via `pip install ideagen[gemini]`

### Phase 4: Core Pipeline & Storage
- [ ] Fuzzy dedup via rapidfuzz (threshold 0.85) merges near-duplicate items across sources
- [ ] Full pipeline runs end-to-end: collect → dedup → analyze → synthesize → score → store
- [ ] Pipeline yields typed `PipelineEvent`s at each stage (`StageStarted`, `StageCompleted`, `SourceFailed`, `IdeaGenerated`, `PipelineComplete`)
- [ ] Partial source failures don't halt pipeline (emits `SourceFailed`, continues)
- [ ] `CancellationToken` stops pipeline cooperatively between stages
- [ ] `--dry-run` shows pipeline plan without LLM calls
- [ ] `--cached` reuses last scrape data from SQLite, re-runs LLM stages only
- [ ] Zero-item abort: clear message when all sources return empty after dedup
- [ ] SQLite persists runs, ideas, and scrape cache; paginated search works
- [ ] JSON export produces valid, human-readable files with all model fields
- [ ] Duplicate run detection via content hash warns user

### Phase 5: CLI
- [ ] `ideagen run --domain software` produces at least 5 idea reports with all fields
- [ ] `ideagen run --segment parents --segment pet_owners` generates WTP-targeted ideas
- [ ] `ideagen run --dry-run` shows plan without calling Claude
- [ ] `ideagen run --cached` works with previously scraped data
- [ ] Rich progress display via `PipelineEventRenderer` consuming async event stream
- [ ] Ctrl+C triggers cooperative cancellation via async bridge
- [ ] `ideagen schedule add --daily --time 09:00` creates a schedule via APScheduler
- [ ] `ideagen interactive` starts REPL; browse, drill into, refine, and export ideas
- [ ] `ideagen config init` creates valid TOML; `config show` redacts optional API keys
- [ ] `ideagen history list` shows paginated past runs; `history prune --older-than 30d` works
- [ ] `ideagen sources test` reports status of all 4 scrapers

### Phase 6: Testing & Docs
- [ ] Integration test: full pipeline with mocked externals produces valid RunResult
- [ ] Integration test: cancellation mid-pipeline works
- [ ] Integration test: partial source failure + pipeline continuation
- [ ] CLI E2E test: `run` command produces expected output via CliRunner
- [ ] CLI E2E test: missing `claude` CLI gives clear error
- [ ] README: new user can install and run first generation following docs alone
- [ ] >80% overall test coverage

---

## Technical Constraints

- **Python 3.11+** (required for stdlib `tomllib`)
- **Claude Code Max plan** — `claude` CLI subprocess, no Anthropic SDK
- **Web scraping only** — no API keys for any data source
- **Library-first** — zero business logic in CLI layer; core has no filesystem I/O
- **Two-tier AI** — `AIProvider.complete()` for LLM communication; `AnalysisPipeline` for prompt logic
- **AsyncIterator[PipelineEvent]** — not callbacks, not return values
- **Pydantic throughout** — all data structures typed and validated

## Key Dependencies

```
Core:     pydantic>=2.0, httpx>=0.25, aiosqlite>=0.19
Scraping: beautifulsoup4>=4.12, snscrape>=0.7, crawl4ai>=0.3
CLI:      typer>=0.9, rich>=13.0
Utils:    rapidfuzz>=3.0, apscheduler>=3.10, tomli-w>=1.0
Optional: openai>=1.0, google-genai>=1.0
```

---

## Implementation Phases

| Phase | Focus | Key Files |
|-------|-------|-----------|
| 1 | Foundation: models, config, ABCs, utilities | `core/models.py`, `core/config.py`, `sources/base.py`, `providers/base.py`, `utils/retry.py`, `utils/text.py`, `utils/logging.py` |
| 2 | Sources: 4 scrapers + registry + rate limiter | `sources/hackernews.py`, `sources/reddit.py`, `sources/producthunt.py`, `sources/twitter.py`, `sources/registry.py`, `utils/rate_limiter.py` |
| 3 | AI: Claude provider, prompts, pipeline, registry | `providers/claude.py`, `core/prompts.py`, `core/pipeline.py`, `core/wtp_segments.py`, `providers/registry.py` |
| 4 | Pipeline: dedup, orchestrator, storage | `core/dedup.py`, `core/service.py`, `storage/sqlite.py`, `storage/json_export.py` |
| 5 | CLI: all commands, formatters, async bridge | `cli/app.py`, `cli/commands/*.py`, `cli/formatters.py`, `cli/async_bridge.py`, `cli/config_loader.py` |
| 6 | Tests & docs: integration, E2E, README | `tests/integration/*.py`, `README.md`, `config.example.toml` |

---

## Definition of Done

All acceptance criteria above are checked. Specifically:
1. `pip install -e .` works
2. `ideagen run --domain software` produces 5+ idea reports with zero config (just `claude` CLI authenticated)
3. All 4 sources scrape successfully without any login or API keys
4. `--segment`, `--dry-run`, `--cached` flags all work
5. `ideagen interactive` allows drilling into and refining ideas
6. `ideagen sources test` reports all scrapers healthy
7. All unit tests pass per-phase; integration/E2E tests pass; >80% coverage
8. README enables a new user to go from zero to first run
