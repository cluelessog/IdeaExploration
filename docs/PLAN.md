# Plan: IdeaExploration

> Last updated: 2026-03-15
> Version: 2.0

## Objective

IdeaGen — an automated idea generation framework that scrapes trending data from Hacker News, Reddit, Product Hunt, and Twitter/X, then uses AI (Claude CLI) to identify pain points, market gaps, and generate business ideas targeting high willingness-to-pay audience segments. Library-first design with a Typer CLI.

## Current Phase

complete (all planned phases delivered)

## Scope

### In Scope
- 4 data sources (HN, Reddit, Product Hunt, Twitter) — all web scraping, no API keys
- AI-powered pipeline: collect → dedup → analyze → synthesize → refine → store
- 22 built-in WTP audience segments
- Claude CLI as default AI provider (+ OpenAI/Gemini optional)
- SQLite persistence with scrape cache for reuse
- CLI with run, sources, config, history, schedule, compare, prompts, interactive commands
- Multiple run modes: single-shot, cached, dry-run, scheduled, interactive REPL
- Output formats: rich (default), json, markdown
- Source filtering, run comparison, prompt customization

### Out of Scope
- Web UI / dashboard (Phase 11.5 — deferred, CLI-only for now)
- Paid API integrations as primary sources
- Real-time monitoring / alerting
- Idea validation or market size estimation beyond current pipeline

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Foundation: models, config, ABCs, utilities | completed |
| 2 | Data Sources: 4 scrapers + registry + rate limiter | completed |
| 3 | AI Providers: Claude CLI, OpenAI, Gemini + prompts + pipeline | completed |
| 4 | Core Pipeline: dedup, service orchestrator, storage | completed |
| 5 | CLI: all commands, formatters, async bridge | completed |
| 6 | Testing & Docs: integration tests, README | completed |
| 7 | Housekeeping: dead code removal, parallel HN fetching | completed |
| 8 | Live Smoke: Product Hunt + Twitter scraper fixes | completed |
| FG | Feature Gaps: sources list, history show, --cached, schedule | completed |
| 9 | Test Coverage & Quality: 84% → 95%, 628 tests | completed |
| 10 | Robustness: duplicate detection, cache warning, prefix ambiguity, WSL | completed |
| 11 | New Capabilities: output formats, source filters, compare, prompts | completed |
| Audit | Code audit fixes: 17 findings (timeout, cache, async, validation, docs) | completed |
| 11.5 | Web Dashboard (deferred) | not-started |

## Task Breakdown

### Phases 1-11 + Audit: Complete

All planned work is delivered. 746 tests, 95%+ coverage. See `.omc/plans/MASTER-PLAN.md` for detailed per-phase breakdown.

### Phase 11.5: Web Dashboard (Deferred)
- [ ] FastAPI + htmx for browsing history, viewing ideas, triggering runs
- Only to be considered if CLI-only workflow proves insufficient

## Open Questions

- Whether to add a web UI in a future iteration (Phase 11.5)

## Dependencies

- Claude CLI installed and authenticated (Max plan)
- Python 3.11+
