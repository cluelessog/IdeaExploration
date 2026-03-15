# IdeaGen Master Plan — Single Source of Truth

**Last updated:** 2026-03-15
**Coverage:** 95%+ (746 tests — 720 unit + 26 integration)
**Branch:** master

This is the only plan file that matters. All prior plans (`ideagen-implementation.md`, `prd-ideagen.md`, `ideagen-feature-gaps.md`, `open-questions.md`) are archived — their work is complete.

---

## Current State

### Completed (Phases 1–11)

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
| 9 | Test Coverage & Quality: 84% → 95%, 628 tests | DONE |
| 10 | Robustness: duplicate detection, cache warning, prefix ambiguity, WSL | DONE |
| 11 | New Capabilities: output formats, source filters, compare, prompts | DONE |
| Audit | Code audit fixes: 17 findings (timeout, cache, async, validation, docs) | DONE |

### What Works Today

- `ideagen run --domain software` — full end-to-end pipeline
- `ideagen run --dry-run` — preview without AI calls
- `ideagen run --cached` — reuse last scrape, re-run AI only (warns if cache empty)
- `ideagen run --segment parents --segment pet_owners` — WTP targeting
- `ideagen run --format json|markdown|rich` — machine-readable output
- `ideagen run --source hackernews --source reddit` — run specific sources only
- `ideagen compare <run1> <run2> [--threshold]` — fuzzy-diff two runs
- `ideagen prompts list` / `ideagen prompts init` — prompt template customization
- `ideagen sources list` / `ideagen sources test`
- `ideagen config init` / `ideagen config show`
- `ideagen history list` / `ideagen history show <id>` / `ideagen history prune`
- `ideagen schedule add/list/remove` — TOML persistence + cron (WSL-aware)
- `ideagen interactive` — REPL with generate/list/detail/export

---

## Phase 9: Test Coverage & Quality — DONE

**Goal:** Raise coverage from 84% to 90%+, fix the one known bug, harden low-coverage modules.
**Result:** 95% coverage, 628 tests (64 new tests added across 8 modules).

### Coverage improvements achieved

| Module | Before | After |
|--------|--------|-------|
| `cli/callbacks.py` | 0% | 100% |
| `cli/formatters.py` | 38% | 100% |
| `cli/commands/history.py` | 59% | 100% |
| `cli/commands/interactive.py` | 12% | 99% |
| `providers/registry.py` | 29% | 100% |
| `cli/schedule_store.py` | 73% | 99% |
| `cli/async_bridge.py` | 75% | 90% |
| `cli/commands/config_cmd.py` | 62% | 96% |

### New test files

- `tests/providers/test_registry.py` — 8 tests
- `tests/cli/test_callbacks.py` — 4 tests
- `tests/cli/test_formatters.py` — 12 tests
- `tests/cli/test_interactive.py` — 14 tests
- `tests/cli/test_async_bridge.py` — 6 tests
- Extended: `test_history.py` (+6), `test_schedule.py` (+12), `test_cli_e2e.py` (+2)

**Acceptance criteria:**
- [x] Overall coverage >= 90% (achieved 95%)
- [x] Every module >= 60% coverage (lowest is 90%)
- [x] All 590+ tests pass (628 pass, 4 pre-existing warnings)

---

## Phase 10: Robustness & Polish — DONE

**Goal:** Harden edge cases, improve UX, close remaining PRD gaps.
**Result:** 4 robustness improvements, 19 new tests.

### 10.1 — Duplicate run detection via content hash ✓

- `DuplicateRunWarning` PipelineEvent emitted after save when content_hash collision found
- `find_runs_by_content_hash(hash, exclude_id)` in StorageBackend ABC + SQLite impl
- Renderer displays yellow warning with matching run IDs

### 10.2 — `--cached` with no cache: better UX ✓

- `CacheEmptyWarning` PipelineEvent emitted when `--cached` finds empty cache
- Renderer shows: "No cached data found. Run without --cached first."

### 10.3 — `history show` prefix ambiguity ✓

- `find_runs_by_prefix(prefix)` in StorageBackend ABC + SQLite impl (ORDER BY timestamp DESC)
- CLI warns on ambiguous prefix, shows matching runs table, displays most recent

### 10.4 — Schedule: WSL detection and warning ✓

- `is_wsl()` detection via `/proc/version` for "microsoft"
- `install_cron()` warns on WSL but still attempts installation
- Suggests schtasks or systemd timers as alternatives

---

## Phase 11: New Capabilities — DONE

**Goal:** Add composability features for scripts/CI usage.
**Result:** 4 new capabilities, 27 new tests, 3 new modules.

### 11.1 — Output format options ✓

- `--format rich|json|markdown` on `ideagen run`
- JSON: `result.model_dump_json(indent=2)` to stdout, zero Rich machinery
- Markdown: `format_run_as_markdown()` — clean report format
- Inline async consumer bypasses Rich Progress entirely for json/markdown

### 11.2 — Source filters ✓

- `--source/-S` repeatable option on `ideagen run`
- CLI errors only when ALL sources unknown; registry warning handles partials
- Overrides config `sources.enabled` when specified

### 11.3 — Idea comparison ✓

- `ideagen compare <run1> <run2> [--threshold]` CLI command
- `compare_runs()` in `core/comparison.py` with fuzzy matching via `rapidfuzz.fuzz.ratio()` at 0.85 threshold
- `ComparisonResult` Pydantic model: added/removed/common/score_changes
- Rich table: added (green), removed (red), common (dim), score changes (yellow)

### 11.4 — Prompt customization ✓

- `ideagen prompts list` — shows 4 prompt names + override status
- `ideagen prompts init [--dir]` — creates template files, doesn't overwrite existing
- Reads `prompt_override_dir` from TOML config

---

## Phase 11.5: Web Dashboard — DEFERRED

Stretch goal, not committed. Only to be considered if CLI-only workflow proves insufficient.

- FastAPI + htmx for browsing history, viewing ideas, triggering runs
- PRD explicitly deferred this to a future version

---

## Priority Order

```
Phase 9 (test coverage)     ← DONE (95%, 628 tests)
Phase 10 (robustness)       ← DONE (674 tests)
Phase 11 (new capabilities) ← DONE (674 tests)
Audit (code audit fixes)    ← DONE (746 tests)
Phase 11.5 (web dashboard)  ← DEFERRED — only if needed
```

---

## Resolved Decisions (from prior plans)

| Decision | Resolution |
|----------|-----------|
| Scheduler approach | TOML + cron (not APScheduler daemon) |
| TOML library | `tomllib` (stdlib 3.11+) + `tomli-w` for writing |
| Dedup threshold | rapidfuzz at 0.85 |
| Python version | 3.11 minimum |
| AI prompts | Fixed in code, override dir `~/.ideagen/prompts/` — wired via `prompts init/list` |
| REPL framework | Rich prompts (not prompt_toolkit) |
| Scoring approach | Bundled with synthesis; separate call for refinement only |
| scrape_cache run_id | Placeholder batch UUID (avoids schema migration) |
| --cached empty behavior | CacheEmptyWarning event + proceed (user-friendly) |
| history show prefix | Flexible LIKE prefix with ambiguity warning |
| Output formats | Inline async consumer for json/markdown (not Console(quiet=True)) |
| Fuzzy compare | rapidfuzz at 0.85 threshold (not exact title match) |
| Duplicate detection | DuplicateRunWarning in service layer (consistent with PipelineEvent pattern) |
| Source filter errors | CLI errors only when ALL unknown; registry logger handles partials |
