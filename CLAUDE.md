<!-- CC-PROJECT-FRAMEWORK-INTEGRATED -->

## 🔴 MANDATORY: Read Before Any Work

Before starting ANY task, you MUST:

1. Read `docs/PLAN.md` — the current strategic plan and scope
2. Read `docs/STATUS.md` — what's done, in progress, and blocked
3. Read `docs/DECISIONS.md` — why things changed (if it exists)
4. Read any spec files in `docs/specs/` — SDD artifacts live here

If any of these files don't exist, create them.

## 🔵 Status Reporting (AUTOMATIC — DO THIS ALWAYS)

After completing any meaningful unit of work (feature, fix, task, subtask), you MUST
update `docs/STATUS.md` by appending an entry in this format:

```
### [YYYY-MM-DD HH:MM] — {{summary}}
- **Type**: feature | fix | refactor | research | planning
- **Status**: completed | in-progress | blocked
- **Files changed**: list of key files
- **What was done**: 1-2 sentence description
- **What's next**: 1-2 sentence description of immediate next step
- **Blockers**: none | description of what's blocking
```

This is NON-NEGOTIABLE. The project dashboard depends on this file being current.

## 🟡 Plan Hierarchy (IMPORTANT)

```
docs/PLAN.md              ← STRATEGIC (master, human-updated)
  │                          Project direction, scope, phases, milestones.
  │
  └── .omc/plans/*        ← TACTICAL (per-feature, OMC-created)
                             Implementation plans for specific features/tasks.
```

Rules:
- ALWAYS read `docs/PLAN.md` first to understand project direction
- NEVER contradict `docs/PLAN.md` in an OMC tactical plan — if conflict, PLAN.md wins
- If the user gives a strategic change (scope, pivot, dropped feature), update `docs/PLAN.md`
- `docs/PLAN.md` feeds the cross-project dashboard. `.omc/plans/` do not.

## 🟠 Plan Change Protocol

When new information arrives that changes the plan:

1. Update `docs/PLAN.md` with the new plan
2. Add an entry to `docs/DECISIONS.md` explaining what/why/impact
3. Update `docs/STATUS.md` to reflect any tasks now invalid/blocked
4. If tasks are in progress that conflict with the new plan, STOP and flag in STATUS.md

<!-- END CC-PROJECT-FRAMEWORK -->
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

IdeaGen — automated idea generation from trending data. Scrapes HN, Reddit, Product Hunt, Twitter/X, then uses AI to analyze pain points and generate business ideas targeting high-WTP audience segments.

Python 3.11+ required. Uses Claude CLI as the default AI provider (no API key needed with Max plan).

## Commands

```bash
# Install
pip install -e ".[dev]"

# Run tests (use the ideagen conda env: /home/cluelessog/anaconda3/envs/ideagen/bin/python)
pytest tests/ -v --tb=short                    # full suite (exclude integration)
pytest tests/ --ignore=tests/integration -v    # skip live integration tests
pytest tests/core/test_service.py -v           # single test file
pytest tests/core/test_service.py::test_name   # single test

# Lint
ruff check ideagen/ tests/

# Run the tool
ideagen run --domain software                  # full pipeline
ideagen run --dry-run                          # preview without AI calls
ideagen run --cached                           # reuse last scrape, re-run AI only
```

## Architecture

**Library-first design** — all core logic is reusable without the CLI. The CLI (`ideagen/cli/`) is a thin Typer layer with no business logic.

### Pipeline Flow (ideagen/core/service.py → IdeaGenService.run)

```
Collect (parallel, all sources) → Dedup (rapidfuzz) → Analyze → Identify Gaps → Synthesize → Refine → Store
```

Each stage yields `PipelineEvent` objects (async iterator pattern). The CLI consumes these via `PipelineEventRenderer` for live progress display.

### Key Abstractions (all use ABC pattern)

| ABC | Location | Implementations |
|-----|----------|-----------------|
| `DataSource` | `sources/base.py` | HN, Reddit, ProductHunt, Twitter (all web scraping, no API keys) |
| `AIProvider` | `providers/base.py` | Claude (CLI subprocess), OpenAI, Gemini |
| `StorageBackend` | `storage/base.py` | SQLiteStorage (aiosqlite) |

### Async Bridge

CLI commands are sync (Typer), but core logic is async. `ideagen/cli/async_bridge.py:run_async()` bridges between them. All CLI commands use this pattern:
```python
result = run_async(some_async_call())
```

### Data Models (Pydantic v2, ideagen/core/models.py)

Domain enum: `SOFTWARE_SAAS`, `BROAD_BUSINESS`, `CONTENT_MEDIA`

Key chain: `TrendingItem → PainPoint → GapAnalysis → Idea → IdeaReport (with MarketAnalysis, FeasibilityScore, MonetizationAngle) → RunResult`

### Exception Hierarchy (ideagen/core/exceptions.py)

`IdeaGenError` base with: `SourceUnavailableError`, `ProviderError`, `ConfigError`, `StorageError`

### Configuration

TOML at `~/.ideagen/config.toml`. Loaded via `ideagen/cli/config_loader.py`. Pure config classes in `ideagen/core/config.py` (IdeaGenConfig with SourceConfig, ProviderConfig, StorageConfig, GenerationConfig).

### Provider Pattern

Claude provider (`providers/claude.py`) shells out to `claude` CLI with `--output-format json`. Uses retry decorator (2 retries, exponential backoff). Provider registry (`providers/registry.py`) does lazy imports with helpful error messages for optional deps.

## Testing

- pytest with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio` on most tests)
- Shared factories in `tests/conftest.py`: `make_idea()`, `make_report()`, `make_run()`, `make_trending_item()`
- HTTP mocking via `respx` for source tests, `unittest.mock` for everything else
- CLI tests use `typer.testing.CliRunner`

## Workflow Rules

- **Test-first bug fixes:** When fixing an issue, first write tests that reproduce the bug, then fix the code until all tests pass.
- **Always use worktrees:** Start all work in a new git worktree under `.claude/worktrees/` within the project directory. Never create worktrees outside the project root. Commit only to the worktree branch — do not merge to master without explicit user approval.

## Conventions

- Lazy imports in CLI commands (keeps startup fast)
- Sources collect in parallel via `asyncio.gather`
- All scrapers use web scraping (no API keys required for any source)
- 22 built-in WTP segments in `ideagen/core/wtp_segments.py`
- Storage uses `scrape_cache` table for `--cached` mode reuse
