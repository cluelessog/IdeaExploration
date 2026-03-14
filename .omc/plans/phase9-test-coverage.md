# Phase 9: Test Coverage & Quality — Implementation Plan

**Created:** 2026-03-12
**Revised:** 2026-03-12 (Revision 4 — fix Step 5 mock patch targets for lazy imports)
**Goal:** Raise test coverage from 84% to 90%+ by testing 8 low-coverage modules
**Constraint:** Test-only changes. No production code modifications. No new dependencies.
**Branch:** Create from `master`

### Revision 2 Changes

1. Interactive REPL: ~~patch module-level `Console()` with `Console(file=io.StringIO(), force_terminal=False)`~~ (reverted in Rev 3).
2. Callbacks: explicitly state mock target is `ideagen.cli.callbacks.setup_logging` (usage site, not definition site).
3. History tests: renamed `test_history_list.py` to `test_history.py`; consolidated all history tests there.
4. `_event_stream` helper moved to `tests/conftest.py` — all 6 steps are now independent.
5. Cron install: extend existing `test_cron_install_called` (line 113) instead of duplicating.
6. Added `test_renderer_stage_completed_without_stage_started` to Step 3 (formatters).
7. Prioritization: Steps 1+3 are highest ROI (behavior-focused). Steps 5+6 are lower priority (heavy mock coupling).

### Revision 3 Changes

1. **Step 5 Console capture reverted:** Rich Console lazily resolves `sys.stdout` at print time, so CliRunner captures module-level Console output transparently. Removed the `Console(file=io.StringIO())` patch. All assertions use `result.output` (consistent with every other CLI test). Added canary assertion to first test.
2. **Step 4 history file consolidation:** Merge existing `test_history_show.py` into `test_history.py` via `git mv`. The step now RENAME+EXTENDs instead of CREATE. Existing show tests are preserved alongside new list/prune tests.

### Revision 4 Changes

1. **Step 5 mock patch targets fixed for lazy imports:** `interactive_mode()` uses lazy imports *inside the function body* (lines 17-24), not module-level imports. Patching `ideagen.cli.commands.interactive.load_config` etc. would silently fail because those names are never bound as module attributes. The fixture now patches at the **source module** where each function is defined (e.g., `ideagen.cli.config_loader.load_config`, `ideagen.core.service.IdeaGenService`). Only `Prompt` stays patched at the usage site because it IS a module-level import (line 4).
2. **Test-specific patches added:** `test_interactive_generate_triggers_pipeline` needs `ideagen.cli.formatters.PipelineEventRenderer` patched. `test_interactive_export_calls_json_export` needs `ideagen.storage.json_export.export_run` patched.
3. **Lazy import rule documented:** Added explicit guidance for executors on how to determine correct patch targets for lazy vs. module-level imports.

---

## RALPLAN-DR Summary

### Principles

1. **Follow existing patterns** — All new tests must use the same conventions as existing tests (CliRunner for CLI, unittest.mock for internals, shared conftest factories, asyncio_mode="auto").
2. **Test behavior, not implementation** — Verify observable outputs (exit codes, printed text, return values, side effects) rather than internal state.
3. **Isolation** — Every test must mock external dependencies (subprocess, filesystem, imports) so the suite runs offline with no side effects.
4. **Incremental coverage** — Target the highest-impact uncovered branches first; each step is independently mergeable.
5. **Preserve green suite** — All 590 existing tests must continue to pass after each step.

### Decision Drivers

1. **Coverage ROI** — `interactive.py` (12%) and `callbacks.py` (0%) have the most uncovered lines; `registry.py` (29%) and `formatters.py` (38%) have the most uncovered branches.
2. **Test complexity** — The interactive REPL requires the most mock scaffolding (Prompt.ask loop, service, renderer). Other modules are straightforward CLI/unit tests.
3. **Mock coupling risk** — Steps 5+6 (interactive REPL, async bridge) require heavy mock scaffolding (Prompt.ask loop, signal handlers, crontab subprocess). Steps 1+3 are cleaner behavior tests with higher ROI.

### Viable Options

**Option A: Single test file per module (Chosen)**
- Create one new test file per untested module, co-located in `tests/cli/` or `tests/providers/`
- Pros: Clear 1:1 mapping, easy to run individually, follows existing project structure
- Cons: Some files will be small (callbacks.py needs only 2 tests)

**Option B: Group all new tests into one file**
- Pros: Single file to manage
- Cons: Violates project convention (every module has its own test file), harder to isolate failures

**Selected: Option A** — Matches the existing 1:1 test file convention in the project.

---

## ADR

- **Decision:** Create 5 new test files, rename+extend 1 existing file, extend 3 others (including conftest), to cover 8 low-coverage modules.
- **Drivers:** Coverage gap analysis from master plan; 90% target; test-only constraint.
- **Alternatives considered:** Single mega-test-file (rejected: violates project convention); production code refactoring to make code more testable (rejected: constraint prohibits production changes).
- **Why chosen:** Minimal risk, follows existing patterns, each step is independently verifiable. All 6 steps are parallel (no inter-step dependencies).
- **Consequences:** ~65 new test functions across 5 new files, 1 renamed+extended file, and 3 extended files. Coverage should reach 90%+. Steps 1+3 prioritized for highest ROI; Steps 5+6 deprioritized due to mock coupling.
- **Follow-ups:** After Phase 9, Phase 10 (robustness & polish) becomes unblocked.

---

## Step 1: Provider Registry Tests

**File:** `tests/providers/test_registry.py` (NEW)
**Source:** `ideagen/providers/registry.py` (29% -> ~95%)
**Priority:** HIGH (best behavior-testing ROI alongside Step 3) — 6 clear branches, all easily testable

### Tests to Write

```
test_get_provider_returns_claude_by_default
    - ProviderConfig(default="claude") -> returns ClaudeProvider instance
    - Acceptance: isinstance(result, ClaudeProvider)

test_get_provider_openai_import_error
    - Mock sys.modules to make openai import fail
    - Acceptance: raises ConfigError with "pip install ideagen[openai]"

test_get_provider_openai_missing_api_key
    - OpenAI importable but config.openai_api_key is None
    - Acceptance: raises ConfigError with "OPENAI_API_KEY"

test_get_provider_openai_success
    - Mock openai import + provide api_key
    - Acceptance: returns OpenAIProvider instance

test_get_provider_gemini_import_error
    - Mock sys.modules to make google.genai import fail
    - Acceptance: raises ConfigError with "pip install ideagen[gemini]"

test_get_provider_gemini_missing_api_key
    - Gemini importable but config.gemini_api_key is None
    - Acceptance: raises ConfigError with "GEMINI_API_KEY"

test_get_provider_gemini_success
    - Mock gemini import + provide api_key
    - Acceptance: returns GeminiProvider instance

test_get_provider_unknown_name
    - ProviderConfig(default="llama") -> raises ConfigError
    - Acceptance: raises ConfigError with "Unknown provider: llama"
```

### Acceptance Criteria
- All 8 tests pass
- `providers/registry.py` coverage >= 95%
- Existing provider tests unaffected

---

## Step 2: CLI Callbacks Tests

**File:** `tests/cli/test_callbacks.py` (NEW)
**Source:** `ideagen/cli/callbacks.py` (0% -> 100%)
**Priority:** High — 0% coverage, trivial to test

### Mock Target

**Important:** Mock `ideagen.cli.callbacks.setup_logging` (the usage-site import), NOT `ideagen.utils.logging.setup_logging` (the definition site). The callbacks module imports setup_logging at its own module level, so the patch must target where it is looked up.

### Tests to Write

```
test_verbose_callback_sets_debug_level
    - Call verbose_callback(True)
    - Mock target: "ideagen.cli.callbacks.setup_logging"
    - Acceptance: setup_logging called with level=logging.DEBUG

test_verbose_callback_false_is_noop
    - Call verbose_callback(False)
    - Mock target: "ideagen.cli.callbacks.setup_logging"
    - Acceptance: setup_logging NOT called

test_quiet_callback_sets_warning_level
    - Call quiet_callback(True)
    - Mock target: "ideagen.cli.callbacks.setup_logging"
    - Acceptance: setup_logging called with level=logging.WARNING

test_quiet_callback_false_is_noop
    - Call quiet_callback(False)
    - Mock target: "ideagen.cli.callbacks.setup_logging"
    - Acceptance: setup_logging NOT called
```

### Acceptance Criteria
- All 4 tests pass
- `cli/callbacks.py` coverage = 100%

---

## Step 3: Formatters Tests

**File:** `tests/cli/test_formatters.py` (NEW)
**Source:** `ideagen/cli/formatters.py` (38% -> ~95%)
**Priority:** HIGH (best behavior-testing ROI alongside Step 1)
**Depends on:** conftest factories (make_run, make_report), conftest `_event_stream` helper

### Tests to Write

```
test_format_run_summary_returns_table
    - Call format_run_summary(make_run()) -> returns Rich Table
    - Acceptance: isinstance(result, Table); table title is "IdeaGen Run Summary"

test_format_run_summary_contains_all_metrics
    - Render table to string via Console(file=StringIO)
    - Acceptance: output contains domain value, sources, item counts, timestamp

test_format_idea_card_returns_panel
    - Call format_idea_card(make_report()) -> returns Rich Panel
    - Acceptance: isinstance(result, Panel)

test_format_idea_card_contains_all_sections
    - Render panel to string
    - Acceptance: output contains problem, solution, market, feasibility, monetization, WTP score

test_format_idea_card_empty_competitors
    - make_report with competitors=[]
    - Acceptance: output contains "None identified"

test_format_idea_card_with_target_segments
    - make_report with target_segments=[WTPSegment(...)]
    - Acceptance: panel subtitle contains segment name

test_renderer_handles_stage_started_and_completed
    - Create async generator yielding StageStarted + StageCompleted
    - Acceptance: render() completes without error, returns None (no PipelineComplete)

test_renderer_handles_source_failed
    - Yield SourceFailed event
    - Acceptance: console output contains "WARNING" and source name

test_renderer_handles_idea_generated
    - Yield IdeaGenerated event with make_idea()
    - Acceptance: console output contains idea title and "Idea 1/"

test_renderer_handles_pipeline_complete
    - Yield PipelineComplete with make_run()
    - Acceptance: render() returns the RunResult

test_renderer_full_pipeline_sequence
    - Yield StageStarted -> StageCompleted -> IdeaGenerated -> PipelineComplete
    - Acceptance: returns RunResult; no exceptions

test_renderer_stage_completed_without_stage_started
    - Yield only a StageCompleted event (no preceding StageStarted)
    - Acceptance: render() completes without exception when current_task is None
    - Rationale: Guards against KeyError/AttributeError if stage tracking dict is empty
```

### Shared Helper: `_event_stream` (in `tests/conftest.py`)

The async event stream helper is defined in `tests/conftest.py` so all steps can use it independently:

```python
async def _event_stream(*events):
    for event in events:
        yield event
```

This removes the dependency between Step 5 and Step 3 — all 6 steps are now fully independent.

### Acceptance Criteria
- All 12 tests pass
- `cli/formatters.py` coverage >= 90%
- PipelineEventRenderer.render() fully exercised

---

## Step 4: History and Config Command Tests

**File:** `tests/cli/test_history.py` (RENAME+EXTEND — `git mv test_history_show.py test_history.py`, then add new tests)
**Source:** `ideagen/cli/commands/history.py` (59% -> ~95%)
**Depends on:** conftest tmp_storage, make_run

**File (extend):** `tests/cli/test_cli_e2e.py` (existing)
**Source:** `ideagen/cli/commands/config_cmd.py` (62% -> ~90%)

**Consolidation:** The existing `test_history_show.py` already tests the `show` subcommand. Rename it to `test_history.py` via `git mv tests/cli/test_history_show.py tests/cli/test_history.py`, then append the new list/prune tests below. This avoids confusing coexistence of `test_history.py` and `test_history_show.py`. All existing show tests are preserved.

### History Tests to Write (`test_history.py`)

```
test_history_list_shows_runs
    - Save 2 runs to tmp storage, invoke "history list" with mocked config
    - Acceptance: exit_code 0; output contains both run timestamps

test_history_list_empty_shows_message
    - Empty storage, invoke "history list"
    - Acceptance: exit_code 0; output contains "No runs found"

test_history_list_respects_limit
    - Save 5 runs, invoke with --limit 2
    - Acceptance: output shows exactly 2 run rows

test_history_list_respects_offset
    - Save 3 runs, invoke with --offset 1
    - Acceptance: first run is skipped

test_history_prune_deletes_old_runs
    - Save a run, invoke "history prune --older-than 0d"
    - Acceptance: exit_code 0; output contains "Deleted"

test_history_prune_no_matches
    - Save a fresh run, invoke "history prune --older-than 999d"
    - Acceptance: exit_code 0; output contains "Deleted 0"
```

### Config Show Test (add to `test_cli_e2e.py`)

```
test_config_show_displays_json
    - Invoke "config show" with mocked config
    - Acceptance: exit_code 0; output contains "claude" (default provider)

test_config_show_redacts_api_keys
    - Config with openai_api_key="sk-secret", invoke "config show"
    - Acceptance: output contains "REDACTED"; does NOT contain "sk-secret"
```

### Acceptance Criteria
- All 8 tests pass
- `cli/commands/history.py` coverage >= 90% (list_runs + prune_history now covered)
- `cli/commands/config_cmd.py` coverage >= 85% (show_config now covered)

---

## Step 5: Interactive REPL Tests

**File:** `tests/cli/test_interactive.py` (NEW)
**Source:** `ideagen/cli/commands/interactive.py` (12% -> ~80%)
**Priority:** LOW (heavy mock coupling — see Prioritization note below)
**Depends on:** conftest factories, conftest `_event_stream` helper

### Mock Strategy

The REPL uses `rich.prompt.Prompt.ask()` for input. Mock it to return a sequence of commands, then `quit`.

**Console capture:** Rich Console lazily resolves `sys.stdout` at print time (not at `__init__` time), so CliRunner's stdout redirect captures module-level Console output transparently. No Console patching needed. Use `result.output` for all assertions, consistent with every other CLI test in the project.

**CRITICAL -- Lazy import patching rule:** `interactive_mode()` uses **lazy imports inside the function body** (lines 17-24 of `interactive.py`). These names (`load_config`, `get_sources_by_names`, `get_provider`, `IdeaGenService`, `PipelineEventRenderer`, `format_idea_card`, `format_run_summary`, `CancellationToken`, `Domain`) are NOT bound as module-level attributes of `ideagen.cli.commands.interactive`. Patching at `ideagen.cli.commands.interactive.load_config` would silently do nothing -- the function would still import and call the real `load_config`.

The correct approach: patch each function **at its definition site** (the source module). When `interactive_mode()` executes `from ideagen.cli.config_loader import load_config`, Python looks up `load_config` in `ideagen.cli.config_loader` -- so that is where the mock must intercept it.

Only `Prompt` (line 4: `from rich.prompt import Prompt`) is a module-level import, so it CAN be patched at the usage site: `ideagen.cli.commands.interactive.Prompt`.

```python
@pytest.fixture
def mock_repl_deps():
    """Patch all heavy dependencies so interactive_mode runs in isolation.

    IMPORTANT: interactive_mode() uses lazy imports inside the function body,
    so we patch at the SOURCE MODULE (where the function is defined), not at
    the usage site. Only Prompt is a module-level import and is patched at
    the usage site.
    """
    with (
        patch("ideagen.cli.config_loader.load_config") as mock_config,
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.providers.registry.get_provider", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService") as mock_svc,
        patch("ideagen.cli.commands.interactive.Prompt") as mock_prompt,
    ):
        mock_config.return_value = IdeaGenConfig()
        yield {
            "config": mock_config,
            "service": mock_svc,
            "prompt": mock_prompt,
        }
```

**Patch target reference table:**

| Import in `interactive_mode()` | Patch target | Why |
|---|----|---|
| `from ideagen.cli.config_loader import load_config` | `ideagen.cli.config_loader.load_config` | Lazy import -- patch at source |
| `from ideagen.sources.registry import get_sources_by_names` | `ideagen.sources.registry.get_sources_by_names` | Lazy import -- patch at source |
| `from ideagen.providers.registry import get_provider` | `ideagen.providers.registry.get_provider` | Lazy import -- patch at source |
| `from ideagen.core.service import IdeaGenService` | `ideagen.core.service.IdeaGenService` | Lazy import -- patch at source |
| `from ideagen.cli.formatters import PipelineEventRenderer` | `ideagen.cli.formatters.PipelineEventRenderer` | Lazy import -- patch at source (only needed in generate tests) |
| `from ideagen.cli.formatters import format_idea_card` | `ideagen.cli.formatters.format_idea_card` | Lazy import -- patch at source (only needed in detail tests, if needed) |
| `from ideagen.cli.formatters import format_run_summary` | `ideagen.cli.formatters.format_run_summary` | Lazy import -- patch at source (only needed in generate tests, if needed) |
| `from ideagen.storage.json_export import export_run` | `ideagen.storage.json_export.export_run` | Lazy import -- patch at source (only needed in export tests) |
| `from rich.prompt import Prompt` (line 4, MODULE-LEVEL) | `ideagen.cli.commands.interactive.Prompt` | Module-level import -- patch at usage site |

**Assertion pattern:** Use `result.output` as with all other CLI tests:
```python
result = runner.invoke(app, ["interactive"])
assert "text" in result.output
```

### Tests to Write

```
test_interactive_quit_exits_cleanly
    - Prompt.ask returns "quit"
    - Acceptance: CLI runner exit_code 0; output contains "Goodbye"
    - CANARY: assert "Interactive Mode" in result.output, "Rich Console output not captured by CliRunner"

test_interactive_exit_command
    - Prompt.ask returns "exit"
    - Acceptance: exit_code 0; output contains "Goodbye"

test_interactive_shows_welcome_banner
    - Prompt.ask returns "quit" immediately
    - Acceptance: output contains "Interactive Mode" and "Commands:"

test_interactive_unknown_command_shows_help
    - Prompt.ask returns "foobar", then "quit"
    - Acceptance: output contains "generate" and "list" and "detail"

test_interactive_generate_triggers_pipeline
    - Mock Prompt.ask to return "generate" then "quit"
    - Additional patch: "ideagen.cli.formatters.PipelineEventRenderer" (lazy import, patch at source)
    - Mock PipelineEventRenderer instance's render() to return make_run()
    - Acceptance: service.run() was called; output contains "IdeaGen Run Summary"

test_interactive_list_without_generate_warns
    - Prompt.ask returns "list", then "quit"
    - Acceptance: output contains "No ideas yet"

test_interactive_list_shows_ideas_after_generate
    - Prompt.ask returns "generate", "list", "quit"
    - Additional patch: "ideagen.cli.formatters.PipelineEventRenderer" (lazy import, patch at source)
    - Mock pipeline to return a run with ideas
    - Acceptance: output contains idea title, WTP score

test_interactive_detail_shows_idea_card
    - Prompt.ask returns "generate", "detail 1", "quit"
    - Additional patch: "ideagen.cli.formatters.PipelineEventRenderer" (lazy import, patch at source)
    - Acceptance: output contains idea problem statement

test_interactive_detail_invalid_index
    - Prompt.ask returns "generate", "detail 99", "quit"
    - Additional patch: "ideagen.cli.formatters.PipelineEventRenderer" (lazy import, patch at source)
    - Acceptance: output contains "Usage: detail <number>"

test_interactive_detail_without_generate_warns
    - Prompt.ask returns "detail 1", "quit"
    - Acceptance: output contains "No ideas yet"

test_interactive_export_calls_json_export
    - Prompt.ask returns "generate", "export", "quit"
    - Additional patch: "ideagen.storage.json_export.export_run" (lazy import, patch at source)
    - Mock export_run to return a Path
    - Acceptance: export_run called; output contains "Exported"

test_interactive_export_without_generate_warns
    - Prompt.ask returns "export", "quit"
    - Acceptance: output contains "No results to export"

test_interactive_eof_exits_gracefully
    - Prompt.ask raises EOFError
    - Acceptance: exit_code 0; output contains "Goodbye"

test_interactive_keyboard_interrupt_exits
    - Prompt.ask raises KeyboardInterrupt
    - Acceptance: exit_code 0; output contains "Goodbye"
```

### Acceptance Criteria
- All 14 tests pass
- `cli/commands/interactive.py` coverage >= 75%
- REPL loop branches (generate, list, detail, export, quit, unknown, EOF, KeyboardInterrupt) all exercised

---

## Step 6: Schedule Store Cron + Async Bridge Tests

**File (extend):** `tests/cli/test_schedule.py` (existing)
**Source:** `ideagen/cli/schedule_store.py` (73% -> ~95%)

**File:** `tests/cli/test_async_bridge.py` (NEW)
**Source:** `ideagen/cli/async_bridge.py` (75% -> ~95%)

**Priority:** LOW (heavy mock coupling — see Prioritization note below)

### Schedule Store Tests to Add

**Note on existing overlap:** `test_cron_install_called` already exists at `test_schedule.py:113` and covers the basic cron install path. Do NOT create a new `test_install_cron_success` that duplicates it. Instead, extend the existing test with more specific assertions (verify cron expression content, verify crontab write payload). The tests below are all NEW branches not covered by the existing test.

```
test_build_cron_expression_daily
    - _build_cron_expression("daily", "09:30") == "30 9 * * *"
    - Acceptance: exact string match

test_build_cron_expression_weekly
    - _build_cron_expression("weekly", "14:00") == "0 14 * * 1"
    - Acceptance: exact string match

test_build_cron_expression_unknown_defaults_daily
    - _build_cron_expression("monthly", "08:00") == "0 8 * * *"
    - Acceptance: falls through to daily default

test_find_ideagen_bin_found
    - Mock shutil.which to return "/usr/local/bin/ideagen"
    - Acceptance: returns "/usr/local/bin/ideagen"

test_find_ideagen_bin_not_found
    - Mock shutil.which to return None
    - Acceptance: returns "ideagen" (fallback)

EXTEND test_cron_install_called (existing, line 113)
    - Add assertions to the existing test: verify the cron expression written
      to crontab contains the correct schedule and ideagen command
    - Acceptance: existing test still passes; new assertions verify cron line content

test_install_cron_windows_returns_false
    - Mock sys.platform = "win32"
    - Acceptance: returns False; subprocess.run NOT called

test_install_cron_crontab_fails_returns_false
    - Mock subprocess.run to raise CalledProcessError
    - Acceptance: returns False

test_install_cron_no_existing_crontab
    - Mock crontab -l to return non-zero (no crontab)
    - Acceptance: returns True; new crontab starts clean

test_uninstall_cron_success
    - Mock crontab -l with a line containing "ideagen-test1234"
    - Acceptance: returns True; filtered crontab written back

test_uninstall_cron_not_found
    - Mock crontab -l with no matching line
    - Acceptance: returns False

test_uninstall_cron_windows_returns_false
    - Mock sys.platform = "win32"
    - Acceptance: returns False

test_uninstall_cron_crontab_error
    - Mock crontab -l to return non-zero
    - Acceptance: returns False
```

### Async Bridge Tests (`test_async_bridge.py`)

```
test_run_async_returns_coroutine_result
    - async def coro(): return 42
    - Acceptance: run_async(coro()) == 42

test_run_async_without_cancellation_token
    - No token passed
    - Acceptance: returns result; no signal handler installed

test_run_async_keyboard_interrupt_with_token
    - Coroutine raises KeyboardInterrupt, token provided
    - Acceptance: returns None; token.is_cancelled is True

test_run_async_keyboard_interrupt_without_token
    - Coroutine raises KeyboardInterrupt, no token
    - Acceptance: returns None

test_run_async_closes_loop
    - After call completes, verify loop is closed
    - Acceptance: loop.is_closed() is True (verify via side effect)

test_run_async_signal_handler_sets_cancel
    - On non-win32, with token, verify signal handler is registered
    - Acceptance: loop.add_signal_handler was called with SIGINT
    - Note: May need to mock sys.platform for cross-platform CI
```

### Acceptance Criteria
- All 18 new tests pass + 1 existing test extended with stronger assertions (19 total test functions touched)
- `cli/schedule_store.py` coverage >= 90% (install_cron, uninstall_cron, _build_cron_expression, _find_ideagen_bin)
- `cli/async_bridge.py` coverage >= 90% (signal handler branch, KeyboardInterrupt with/without token)
- Existing `test_cron_install_called` still passes with the added assertions

---

## Task Flow & Dependencies

```
Step 1: Provider Registry     (independent — start immediately)  [HIGH PRIORITY]
Step 2: CLI Callbacks          (independent — start immediately)
Step 3: Formatters             (independent — start immediately)  [HIGH PRIORITY]
Step 4: History + Config       (independent — start immediately)
Step 5: Interactive REPL       (independent — start immediately)  [LOW PRIORITY]
Step 6: Schedule Cron + Bridge (independent — start immediately)  [LOW PRIORITY]
```

All 6 steps are fully independent and can run in parallel. The `_event_stream` helper lives in `tests/conftest.py`, removing the previous Step 5 -> Step 3 dependency.

### Prioritization

**Steps 1 + 3 (registry + formatters) have the best behavior-testing ROI.** They test real branching logic with minimal mock scaffolding and cover the most impactful uncovered code paths.

**Steps 5 + 6 (interactive REPL + async bridge) are lower priority.** They require heavy mock coupling (Prompt.ask loop, signal handlers, crontab subprocess calls) which makes the tests more brittle and less valuable as regression guards. Implement them last, and consider dropping individual tests if mock complexity becomes excessive during execution.

---

## File Change Summary

| Action | File | Tests Added |
|--------|------|-------------|
| CREATE | `tests/providers/test_registry.py` | 8 |
| CREATE | `tests/cli/test_callbacks.py` | 4 |
| CREATE | `tests/cli/test_formatters.py` | 12 |
| RENAME+EXTEND | `tests/cli/test_history_show.py` -> `tests/cli/test_history.py` | 6 new (existing show tests preserved) |
| EXTEND | `tests/cli/test_cli_e2e.py` | 2 |
| CREATE | `tests/cli/test_interactive.py` | 14 |
| EXTEND | `tests/cli/test_schedule.py` | 12 new + 1 extended |
| CREATE | `tests/cli/test_async_bridge.py` | 6 |
| EXTEND | `tests/conftest.py` | 0 (adds `_event_stream` helper) |
| **TOTAL** | **5 new + 4 extended/renamed** | **~65 tests** |

No production files modified. No new dependencies.

---

## Success Criteria

- [ ] All ~65 new tests pass
- [ ] All 590 existing tests still pass (total: ~655)
- [ ] Overall coverage >= 90%
- [ ] Every module in the gap table reaches >= 60% coverage
- [ ] `providers/registry.py` >= 95%
- [ ] `cli/callbacks.py` = 100%
- [ ] `cli/formatters.py` >= 90%
- [ ] `cli/commands/history.py` >= 90%
- [ ] `cli/commands/config_cmd.py` >= 85%
- [ ] `cli/commands/interactive.py` >= 75%
- [ ] `cli/schedule_store.py` >= 90%
- [ ] `cli/async_bridge.py` >= 90%

---

## Guardrails

### Must Have
- Every test is isolated (no network, no disk side effects outside tmp_path)
- Every test has a clear assertion (no empty test bodies)
- Test names describe the behavior being verified
- Mock patterns match existing codebase conventions (unittest.mock, not monkeypatch for CLI tests)

### Must NOT Have
- No changes to any file under `ideagen/` (production code)
- No new pip dependencies
- No tests that depend on external services or API keys
- No tests that modify global state without cleanup
- No sleep() calls in tests
