# IdeaGen Master Plan — Single Source of Truth

**Last updated:** 2026-03-12
**Coverage:** 84% (564 unit + 26 integration tests)
**Branch:** master

This is the only plan file that matters. All prior plans (`ideagen-implementation.md`, `prd-ideagen.md`, `ideagen-feature-gaps.md`, `open-questions.md`) are archived — their work is complete.

---

## Current State

### Completed (Phases 1–8 + Feature Gaps)

| Phase | What | Status |
|-------|------|--------|
| 1 | Foundation: models, config, ABCs, utilities | DONE |
| 2 | Data Sources: 4 scrapers + registry + rate limiter | DONE |
| 3 | AI Providers: Claude CLI, OpenAI, Gemini + prompts + pipeline | DONE |
| 4 | Core Pipeline: dedup, service orchestrator, storage | DONE |
| 5 | CLI: all commands, formatters, async bridge | DONE |
| 6 | Testing & Docs: integration tests, README | DONE |
| 7 | Housekeeping: dead code removal, parallel HN fetching | DONE |
| 8 | Live Smoke: Product Hunt + Twitter scraper fixes | DONE |
| FG | Feature Gaps: sources list, history show, --cached, schedule | DONE |

### What Works Today

- `ideagen run --domain software` — full end-to-end pipeline
- `ideagen run --dry-run` — preview without AI calls
- `ideagen run --cached` — reuse last scrape, re-run AI only
- `ideagen run --segment parents --segment pet_owners` — WTP targeting
- `ideagen sources list` / `ideagen sources test`
- `ideagen config init` / `ideagen config show`
- `ideagen history list` / `ideagen history show <id>` / `ideagen history prune`
- `ideagen schedule add/list/remove` — TOML persistence + cron
- `ideagen interactive` — REPL with generate/list/detail/export

---

## Phase 9: Test Coverage & Quality

**Goal:** Raise coverage from 84% to 90%+, fix the one known bug, harden low-coverage modules.

### 9.1 — Fix integration MockStorage (DONE)
- Added missing `get_run_detail`, `save_scrape_cache`, `load_latest_scrape_cache` stubs
- 26/26 integration tests now pass

### 9.2 — Cover low-coverage modules

Current coverage gaps (modules below 80%):

| Module | Coverage | Missing | What to test |
|--------|----------|---------|--------------|
| `cli/formatters.py` | 38% | `PipelineEventRenderer.render()`, `format_run_summary()` | Mock async event stream, verify Rich output |
| `cli/commands/history.py` | 59% | `list_runs()`, `prune_history()` | CLI runner tests with mocked storage |
| `cli/commands/config_cmd.py` | 62% | `init_config()` file creation, `show_config()` display | CLI runner with tmp config paths |
| `cli/schedule_store.py` | 73% | `install_cron()`, `uninstall_cron()` | Mock subprocess, test cron line generation |
| `cli/commands/interactive.py` | 12% | The entire REPL loop | Mock Prompt.ask() to feed commands, verify outputs |
| `cli/async_bridge.py` | 75% | Signal handler branches, KeyboardInterrupt | Test cancellation flow |
| `providers/registry.py` | 29% | `get_provider()` branches for openai/gemini/unknown | Mock imports, test error messages |
| `cli/callbacks.py` | 0% | `verbose_callback`, `quiet_callback` | Verify logging level changes |

**Acceptance criteria:**
- [ ] Overall coverage >= 90%
- [ ] Every module >= 60% coverage
- [ ] All 590+ tests pass (unit + integration)

### 9.3 — Provider registry tests

`providers/registry.py` is at 29% — add tests for:
- Claude provider returned by default
- OpenAI import error gives clear message
- Gemini import error gives clear message
- Unknown provider name raises ConfigError
- API key missing raises ConfigError

### 9.4 — Interactive REPL tests

`interactive.py` is at 12% — add tests for:
- REPL starts and shows welcome banner
- `generate` command triggers pipeline
- `list` command shows idea table
- `detail <n>` command shows idea card
- `export` command calls json_export
- `quit` exits cleanly
- Unknown command shows help

---

## Phase 10: Robustness & Polish

**Goal:** Harden edge cases, improve UX, close remaining PRD gaps.

### 10.1 — Duplicate run detection via content hash

PRD acceptance criterion not yet implemented:
- After `save_run()`, check if `content_hash` already exists in `runs` table
- If duplicate found, warn user: "Similar run already exists (run_id: xxx)"
- Don't block — just warn

**Files:** `storage/sqlite.py` (add `has_content_hash()` method), `service.py` (check after store)

### 10.2 — `--cached` with no cache: better UX

Currently proceeds silently with empty items → produces empty result.
- Add a warning: "No cached data found. Run without --cached first."
- Still proceed (don't error out), but inform the user

**Files:** `service.py` (add warning after `load_latest_scrape_cache()` returns empty)

### 10.3 — `history show` prefix ambiguity

Short prefixes (e.g., 2 chars) could match multiple runs.
- If LIKE query matches >1 run, show all matches and ask user to be more specific
- Or return the most recent match with a note

**Files:** `storage/sqlite.py` (modify `get_run_detail`), `cli/commands/history.py`

### 10.4 — Schedule: Windows/WSL warning improvement

`crontab` may not work on WSL2. Currently warns but could be clearer.
- Detect WSL specifically (check `/proc/version` for "microsoft")
- Suggest `schtasks` or systemd timer as alternatives

**Files:** `cli/schedule_store.py`

---

## Phase 11: New Capabilities (Future)

These are stretch goals — not committed, just tracked for when the core is solid.

### 11.1 — Output format options
- `ideagen run --output json` — machine-readable JSON output
- `ideagen run --output markdown` — markdown report file
- Currently only Rich terminal output + JSON export via interactive mode

### 11.2 — Source filters
- `ideagen run --source hackernews --source reddit` — run only specific sources
- Currently all enabled sources always run

### 11.3 — Idea comparison
- `ideagen compare <run1> <run2>` — diff two runs, show new/removed ideas
- Useful for tracking how trending topics evolve

### 11.4 — Prompt customization
- `~/.ideagen/prompts/` override directory exists in config but isn't wired
- Allow users to customize analysis/synthesis prompts

### 11.5 — Web dashboard
- FastAPI + htmx for browsing history, viewing ideas, triggering runs
- PRD explicitly deferred this to a future version

---

## Priority Order

```
Phase 9 (test coverage)     ← DO NEXT — low risk, high value
Phase 10 (robustness)       ← after 9 — UX polish
Phase 11 (new capabilities) ← future — only if needed
```

---

## Resolved Decisions (from prior plans)

| Decision | Resolution |
|----------|-----------|
| Scheduler approach | TOML + cron (not APScheduler daemon) |
| TOML library | `tomllib` (stdlib 3.11+) + `tomli-w` for writing |
| Dedup threshold | rapidfuzz at 0.85 |
| Python version | 3.11 minimum |
| AI prompts | Fixed in code, override dir `~/.ideagen/prompts/` (not yet wired) |
| REPL framework | Rich prompts (not prompt_toolkit) |
| Scoring approach | Bundled with synthesis; separate call for refinement only |
| scrape_cache run_id | Placeholder batch UUID (avoids schema migration) |
| --cached empty behavior | Silent proceed with warning (user-friendly) |
| history show prefix | Flexible LIKE prefix (any length) |
