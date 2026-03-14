# IdeaGen Feature Gaps Implementation Plan

**Created:** 2026-03-10
**Scope:** 4 feature gaps + test infrastructure across ~10 files
**Estimated complexity:** MEDIUM
**Dependencies between steps:** Step 1 (test fixtures) is independent. Steps 2-5 are independent of each other but all benefit from Step 1. Step 6 depends on all prior steps.

---

## Context

The IdeaGen CLI (Typer + Rich + Pydantic v2 + async) has 4 feature gaps where the README/CLI structure promises functionality that is stubbed or missing:
- `ideagen sources list` -- no subcommand exists
- `ideagen history show <id>` -- no subcommand exists
- `ideagen schedule *` -- all 3 subcommands are print-only stubs
- `--cached` flag -- accepted but does not load cached data

The codebase is well-structured with clear patterns: CLI commands live in `ideagen/cli/commands/`, they use `run_async()` from `async_bridge.py` to call async storage/source code, and tests use `pytest-asyncio` + `unittest.mock` + `typer.testing.CliRunner`.

---

## Work Objectives

1. Close all 4 feature gaps with minimal, idiomatic changes
2. Establish shared test fixtures in `tests/conftest.py`
3. Add test coverage for every new feature
4. No new dependencies; no daemon processes

---

## Guardrails

### Must Have
- All new CLI commands follow existing patterns (lazy imports, `run_async()`, Rich tables/panels)
- Schedule persistence uses TOML config file (not a daemon, not a database)
- `--cached` wires to the existing `scrape_cache` table in SQLite schema
- Tests use `pytest-asyncio`, `unittest.mock`, `typer.testing.CliRunner`
- All existing tests continue to pass

### Must NOT Have
- No new pip dependencies
- No background daemon or scheduler process
- No changes to existing Pydantic models (extend only)
- No architectural changes to the pipeline or service layer

---

## Task Flow

```
Step 1 (test fixtures) ──────────────────────────────┐
Step 2 (sources list) ──── independent ──────────────>│
Step 3 (history show) ──── independent ──────────────>│── Step 6 (verification)
Step 4 (--cached flag) ──── independent ─────────────>│
Step 5 (schedule cmds) ──── independent ─────────────>│
```

---

## Step 1: Shared Test Fixtures in `tests/conftest.py`

**Goal:** Extract duplicated factory helpers into shared fixtures so all new (and existing) tests can use them.

**Files to modify:**
- `tests/conftest.py` -- add shared fixtures
- `tests/storage/test_sqlite.py` -- update to use shared fixtures (optional, non-breaking)

**What to do:**

In `tests/conftest.py`, add:
- `make_idea(title="Test Idea", **overrides) -> Idea` -- factory function (not a fixture, a helper) that creates an `Idea` with sensible defaults. Mirror the existing `_make_idea` from `test_sqlite.py`.
- `make_report(title="Test Idea", wtp_score=4.2, **overrides) -> IdeaReport` -- factory that creates a full `IdeaReport` with `MarketAnalysis`, `FeasibilityScore`, `MonetizationAngle`. Mirror `_make_report`.
- `make_run(title="Test Idea", timestamp=None, **overrides) -> RunResult` -- factory for `RunResult`. Mirror `_make_run`.
- `@pytest.fixture def tmp_storage(tmp_path) -> SQLiteStorage` -- returns a `SQLiteStorage` pointing to a temp db file.
- `@pytest.fixture def runner() -> CliRunner` -- shared CLI test runner.

**Acceptance criteria:**
- [ ] `tests/conftest.py` contains `make_idea`, `make_report`, `make_run`, `tmp_storage`, and `runner`
- [ ] Running `pytest tests/storage/test_sqlite.py` still passes (existing tests unbroken)
- [ ] New tests in subsequent steps use these shared helpers

---

## Step 2: Implement `ideagen sources list`

**Goal:** Add a `list` subcommand to the sources CLI that shows all registered data sources with their enabled/disabled status.

**Files to modify:**
- `ideagen/cli/commands/sources_cmd.py` -- add `list` command

**Files to create:**
- `tests/cli/test_sources_list.py` -- tests for the new command

**What to do in `sources_cmd.py`:**

Add a new command `list` to `sources_app`:
```
@sources_app.command("list")
def list_sources(config_path: Optional[Path] = None):
```

Implementation:
1. Import `get_available_source_names` from `ideagen.sources.registry`
2. Import `load_config` from `ideagen.cli.config_loader`
3. Load config, get `config.sources.enabled` list
4. Build a Rich `Table` with columns: "Source", "Status" (enabled/disabled)
5. For each name from `get_available_source_names()`, check if it's in the enabled list
6. Display with green "enabled" or dim "disabled" styling

**No async needed** -- this is a pure config lookup, no network calls.

**Tests (`tests/cli/test_sources_list.py`):**
- `test_sources_list_shows_all_sources` -- invoke `["sources", "list"]`, assert all 4 source names appear in output
- `test_sources_list_shows_enabled_status` -- patch `load_config` to return config with only `["hackernews"]` enabled, assert "enabled" appears for hackernews and "disabled" for others
- `test_sources_list_with_custom_config` -- pass `--config` flag pointing to a temp TOML

**Acceptance criteria:**
- [ ] `ideagen sources list` prints a table of all sources with enabled/disabled status
- [ ] `ideagen sources list --config path/to/config.toml` respects custom config
- [ ] 3 passing tests

---

## Step 3: Implement `ideagen history show <id>`

**Goal:** Add a `show` subcommand that displays full details of a specific run by its ID prefix.

**Files to modify:**
- `ideagen/storage/sqlite.py` -- add `get_run_detail(run_id_prefix)` method
- `ideagen/storage/base.py` -- add abstract method signature
- `ideagen/cli/commands/history.py` -- add `show` command

**Files to create:**
- `tests/cli/test_history_show.py` -- tests for the new command

**What to do in `sqlite.py`:**

Add method `get_run_detail(self, run_id_prefix: str) -> dict | None`:
1. Query: `SELECT * FROM runs WHERE id LIKE ? LIMIT 1` with `f"{run_id_prefix}%"`
2. If found, also query: `SELECT report_json FROM ideas WHERE run_id = ? ORDER BY wtp_score DESC`
3. Return dict with run metadata + list of deserialized `IdeaReport` objects
4. Return `None` if no matching run

Add abstract method to `base.py`:
```python
@abstractmethod
async def get_run_detail(self, run_id_prefix: str) -> dict | None: ...
```

**What to do in `history.py`:**

Add command:
```
@history_app.command("show")
def show_run(run_id: str = typer.Argument(..., help="Run ID or prefix")):
```

Implementation:
1. Load config, create `SQLiteStorage`
2. Call `storage.get_run_detail(run_id)` via `run_async`
3. If None, print error and exit
4. Display run metadata in a Rich `Table` (ID, timestamp, domain, sources, items scraped, after dedup)
5. For each `IdeaReport`, render using the existing `format_idea_card()` from `formatters.py`

**Tests (`tests/cli/test_history_show.py`):**
- `test_show_run_displays_details` -- save a run to tmp storage, invoke `["history", "show", id_prefix]`, assert run metadata and idea title appear in output
- `test_show_run_not_found` -- invoke with bogus ID, assert error message
- `test_show_run_prefix_match` -- save a run, invoke with first 8 chars of ID, assert it finds the run
- `test_get_run_detail_storage_method` -- unit test the new `SQLiteStorage.get_run_detail()` directly

**Acceptance criteria:**
- [ ] `ideagen history show <id>` displays run metadata + all ideas from that run
- [ ] Partial ID prefix matching works (first 8 chars)
- [ ] Graceful error message when ID not found
- [ ] 4 passing tests

---

## Step 4: Wire `--cached` Flag to `scrape_cache` Table

**Goal:** Make `--cached` actually load the most recent run's scraped data from SQLite instead of yielding an empty list.

**Files to modify:**
- `ideagen/storage/sqlite.py` -- add `save_scrape_cache()` and `load_latest_scrape_cache()` methods
- `ideagen/storage/base.py` -- add abstract method signatures
- `ideagen/core/service.py` -- wire the cached branch to call storage methods

**What to do in `sqlite.py`:**

Add method `save_scrape_cache(self, run_id: str, source: str, items: list[TrendingItem]) -> None`:
1. Serialize `items` to JSON (list of dicts via `[item.model_dump(mode="json") for item in items]`)
2. Insert into `scrape_cache` table: `(id=uuid, run_id, source, items_json, scraped_at=now)`

Add method `load_latest_scrape_cache(self) -> list[TrendingItem]`:
1. Query: `SELECT items_json FROM scrape_cache WHERE run_id = (SELECT id FROM runs ORDER BY timestamp DESC LIMIT 1)`
2. Deserialize all rows' `items_json` back into `TrendingItem` objects
3. Return combined list; return empty list if no cache exists

Add abstract methods to `base.py`:
```python
@abstractmethod
async def save_scrape_cache(self, run_id: str, source: str, items: list) -> None: ...

@abstractmethod
async def load_latest_scrape_cache(self) -> list: ...
```

**What to do in `service.py`:**

In the `_collect_all` method (or after it returns in the `run` method):
1. After successful collection (non-cached path), call `self._storage.save_scrape_cache(run_id, source_name, items)` for each source's items. Since `run_id` isn't known yet at collection time, save cache keyed by a temporary batch ID, or restructure slightly: save cache after the run is stored. **Simpler approach:** save the cache in the `store` stage using the `run_id` returned by `save_run`. But this means items need to be tracked per-source. **Simplest approach:** save all collected items as a single cache entry right after `_collect_all` returns, using a placeholder run_id that gets updated later, OR just save them grouped by source name in the collection stage before the run_id exists, using a UUID generated early.

**Recommended approach for minimal changes:**
1. In `run()` method, generate `run_id = str(uuid.uuid4())` at the top
2. Pass `run_id` down to `save_run` (modify `save_run` to accept optional `run_id` parameter instead of generating its own)
3. After `_collect_all`, save each source's items to `scrape_cache` using that `run_id`
4. In the cached branch, call `load_latest_scrape_cache()` and assign to `all_items`

**Actually, even simpler -- avoid changing save_run signature:**
1. After `_collect_all` returns in the non-cached branch, save items per source: modify `_collect_all` to return `dict[str, list[TrendingItem]]` instead of flat list, then flatten after saving cache
2. In the cached branch, call `load_latest_scrape_cache()` to populate `all_items`

**Simplest approach (recommended):**
1. Add `save_scrape_cache(source, items)` that auto-generates its own row ID and uses no run_id FK (just stores source + items + timestamp). The `scrape_cache` table has `run_id` as NOT NULL, so either: (a) make it nullable in schema, or (b) generate a batch UUID. Option (b) is safest to avoid schema migration.
2. Add `load_latest_scrape_cache()` that loads items from the most recent `scraped_at` batch.
3. In `service.py`, after `_collect_all`, save cache. In cached branch, load cache.

**Final recommended implementation:**
- Modify `_collect_all` to also return per-source results
- After collection, call `storage.save_scrape_cache(batch_id, source_name, items)` for each source using a UUID as run_id placeholder
- In cached path, `all_items = await self._storage.load_latest_scrape_cache()`

**Files to create:**
- `tests/storage/test_scrape_cache.py` -- tests for cache storage methods
- `tests/core/test_service_cached.py` -- integration test for cached pipeline path

**Tests:**
- `test_save_and_load_scrape_cache` -- save items for 2 sources, load back, verify all items returned
- `test_load_latest_cache_empty_db` -- returns empty list when no cache exists
- `test_cached_flag_loads_from_storage` -- mock storage's `load_latest_scrape_cache` to return items, run service with `cached=True`, verify collection was skipped and items were used

**Acceptance criteria:**
- [ ] `ideagen run` saves scraped items to `scrape_cache` table after collection
- [ ] `ideagen run --cached` loads items from the most recent cache instead of scraping
- [ ] Graceful fallback: if no cache exists, `--cached` proceeds with empty items (existing behavior)
- [ ] 3 passing tests

---

## Step 5: Implement Schedule Commands with TOML Persistence

**Goal:** Replace the 3 stub schedule commands with working implementations that persist schedules to a TOML config file and generate/remove user-level cron jobs.

**Files to modify:**
- `ideagen/cli/commands/schedule.py` -- rewrite all 3 commands

**Files to create:**
- `ideagen/cli/schedule_store.py` -- TOML-based schedule persistence
- `tests/cli/test_schedule.py` -- tests for all 3 commands

**What to do in `schedule_store.py`:**

Create a small module for schedule CRUD:
```python
SCHEDULE_FILE = Path("~/.ideagen/schedules.toml")
```

Functions:
- `load_schedules(path=None) -> list[dict]` -- read TOML file, return list of schedule dicts `[{id, frequency, time, domain, created_at}]`
- `save_schedule(schedule: dict, path=None) -> str` -- append a schedule to the TOML file, return generated ID (short UUID)
- `remove_schedule(schedule_id: str, path=None) -> bool` -- remove by ID, return success
- `install_cron(schedule: dict) -> None` -- use `subprocess.run(["crontab", ...])` to add a cron entry with comment tag `# ideagen-{id}`. The cron line runs `ideagen run --domain {domain}`. On Windows (detected via `sys.platform`), print a warning that cron is not available and show the equivalent command.
- `uninstall_cron(schedule_id: str) -> None` -- remove the cron entry matching `# ideagen-{id}`

**Cron approach:** Read existing crontab via `crontab -l`, append/filter lines, write back via `crontab -` (stdin). This is the standard non-daemon approach.

**What to do in `schedule.py`:**

Rewrite `add_schedule`:
1. Import `schedule_store`
2. Build schedule dict from args
3. Call `save_schedule()` to persist to TOML
4. Call `install_cron()` to register cron job
5. Print confirmation with schedule ID

Rewrite `list_schedules`:
1. Call `load_schedules()`
2. Display Rich table: ID, Frequency, Time, Domain, Created

Rewrite `remove_schedule`:
1. Call `remove_schedule(schedule_id)`
2. Call `uninstall_cron(schedule_id)`
3. Print confirmation or "not found" error

**Tests (`tests/cli/test_schedule.py`):**
- `test_add_schedule_persists_to_toml` -- invoke `["schedule", "add", "--daily", "--time", "09:00"]` with mocked cron install, verify TOML file written
- `test_list_schedules_shows_entries` -- pre-populate TOML, invoke `["schedule", "list"]`, assert entries appear in output
- `test_list_schedules_empty` -- no TOML file, invoke list, assert "No active schedules" message
- `test_remove_schedule_deletes_entry` -- pre-populate, invoke remove, verify entry gone from TOML
- `test_remove_schedule_not_found` -- invoke remove with bogus ID, assert error message
- `test_cron_install_called` -- mock `subprocess.run`, invoke add, verify crontab command was called
- All tests mock `subprocess.run` to avoid actually modifying the system crontab

**Acceptance criteria:**
- [ ] `ideagen schedule add --daily --time 09:00 --domain software` persists to `~/.ideagen/schedules.toml` and installs a cron job
- [ ] `ideagen schedule list` shows all persisted schedules in a table
- [ ] `ideagen schedule remove <id>` removes from TOML and uninstalls cron entry
- [ ] All subprocess calls to `crontab` are mocked in tests
- [ ] Windows platform detected and warned (no cron available)
- [ ] 6 passing tests

---

## Step 6: Final Verification

**Goal:** Ensure all features work together and no regressions.

**What to do:**
1. Run full test suite: `pytest tests/ -v --tb=short`
2. Verify all new tests pass
3. Verify all existing tests still pass
4. Run `ideagen --help` and verify all subcommands appear
5. Run `ideagen sources list` -- verify output
6. Run `ideagen history show` with no args -- verify help/error message
7. Run `ideagen schedule list` -- verify empty state message

**Acceptance criteria:**
- [ ] `pytest tests/ -v` shows 0 failures
- [ ] All 4 new CLI features respond correctly to `--help`
- [ ] No import errors or circular dependencies

---

## Success Criteria (overall)

1. `ideagen sources list` shows all sources with enabled/disabled status from config
2. `ideagen history show <id>` displays full run details + idea cards
3. `ideagen schedule add/list/remove` persist to TOML and manage cron jobs
4. `ideagen run --cached` loads most recent scrape data from SQLite
5. `tests/conftest.py` has shared factories usable by all test modules
6. All tests pass, including ~16 new tests across the new features
7. Zero new dependencies added

---

## File Change Summary

| File | Action | Step |
|------|--------|------|
| `tests/conftest.py` | Rewrite (add shared fixtures) | 1 |
| `ideagen/cli/commands/sources_cmd.py` | Modify (add `list` command) | 2 |
| `tests/cli/test_sources_list.py` | Create | 2 |
| `ideagen/storage/base.py` | Modify (add 3 abstract methods) | 3, 4 |
| `ideagen/storage/sqlite.py` | Modify (add 3 methods) | 3, 4 |
| `ideagen/cli/commands/history.py` | Modify (add `show` command) | 3 |
| `tests/cli/test_history_show.py` | Create | 3 |
| `ideagen/core/service.py` | Modify (wire cached path) | 4 |
| `tests/storage/test_scrape_cache.py` | Create | 4 |
| `tests/core/test_service_cached.py` | Create | 4 |
| `ideagen/cli/schedule_store.py` | Create | 5 |
| `ideagen/cli/commands/schedule.py` | Rewrite | 5 |
| `tests/cli/test_schedule.py` | Create | 5 |
