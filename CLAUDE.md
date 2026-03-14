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
- **Always use worktrees:** Start all work in a new git worktree to keep master clean.

## Conventions

- Lazy imports in CLI commands (keeps startup fast)
- Sources collect in parallel via `asyncio.gather`
- All scrapers use web scraping (no API keys required for any source)
- 22 built-in WTP segments in `ideagen/core/wtp_segments.py`
- Storage uses `scrape_cache` table for `--cached` mode reuse
