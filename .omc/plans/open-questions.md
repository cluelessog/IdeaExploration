# Open Questions

## IdeaGen Implementation - 2026-03-06

All previously open questions have been resolved in Revision 2 of the plan. Decisions are documented in the "Resolved Decisions" table in the plan file.

### Resolved (2026-03-06, Revision 2)

- [x] Should the scheduler use APScheduler instead of system cron? -- **Decision: APScheduler.** Cross-platform support (Windows/Mac/Linux) without system cron dependency.
- [x] What is the preferred TOML library? -- **Decision: `tomllib` (stdlib 3.11+) + `tomli-w` for writing.** Zero-dependency for reads; `tomli-w` only needed by CLI config commands.
- [x] Should AI analysis prompts be customizable by the user? -- **Decision: Fixed in code with optional override directory `~/.ideagen/prompts/`.** Reliable defaults with escape hatch for power users.
- [x] How aggressive should deduplication be? -- **Decision: Fuzzy title match with `rapidfuzz` (threshold 0.85).** Good balance of accuracy vs cost; no LLM call needed. Separate from AI clustering.
- [x] What minimum Python version to target? -- **Decision: 3.11 minimum.** Required for `tomllib` in stdlib; broad enough adoption.
- [x] Should interactive REPL use prompt_toolkit or Rich prompts? -- **Decision: Rich prompts for v1.** Keep it simple; `prompt_toolkit` can be added later.
- [x] Should scoring use a separate cheaper model call or be bundled? -- **Decision: Bundled with synthesis prompt; separate call for top-K refinement only.** Reduces API costs for bulk scoring.

### Remaining Considerations (Non-Blocking)

- [ ] APScheduler runs in-process -- schedules only persist while process is running. A future daemon mode may be needed for persistent scheduling. -- Non-blocking for v1; document the limitation.
- [ ] `rapidfuzz` is a compiled C extension -- may require build tools on some platforms. Consider documenting build prerequisites or providing a pure-Python fallback. -- Non-blocking; document in README.

## ideagen-feature-gaps - 2026-03-10

- [ ] `scrape_cache` table has `run_id NOT NULL` FK -- should we make it nullable to allow saving cache before `save_run` assigns a run_id, or use a placeholder UUID? — Placeholder UUID is recommended to avoid schema migration, but changes the semantics of `run_id` in that table.
- [ ] Should `--cached` fail loudly (exit with error) when no cache exists, or silently proceed with empty data? — Current plan: silently proceed (matches existing stub behavior). Loud failure would be more user-friendly.
- [ ] For `history show`, should prefix matching be strict (exactly 8 chars) or flexible (any prefix length)? — Plan says flexible LIKE prefix. Worth confirming UX preference since short prefixes could match multiple runs.
- [ ] Schedule cron approach assumes Linux/macOS. On WSL2 (this dev environment), `crontab` may not be available. — Should schedule store also support systemd timers as a fallback, or is cron-only with a warning acceptable for v1?
- [ ] Should `tests/storage/test_sqlite.py` be refactored to use the new shared `conftest.py` helpers? — Plan recommends leaving existing tests as-is to minimize churn. The duplicate helpers will coexist.

## Phase 9: Test Coverage - 2026-03-12 (Revision 4)

- [ ] Interactive REPL test for `export` command depends on `ideagen.storage.json_export.export_run` — need to verify the module exists and its signature matches the mock. If it has changed, adjust the mock accordingly. — Could cause test failures if export_run signature differs from what interactive.py expects. (Step 5 is low-priority; validate before implementing.) **Note (Rev 4):** Correct patch target is now `ideagen.storage.json_export.export_run` (source module), confirmed from interactive.py line 94.
- [ ] Async bridge signal handler test (`test_run_async_signal_handler_sets_cancel`) requires non-win32 platform — this dev environment is WSL2 (Linux). If CI runs on Windows, this test needs a `@pytest.mark.skipif(sys.platform == "win32")` guard. — Could cause CI failures on Windows runners. (Step 6 is low-priority; validate before implementing.)
- [ ] The `install_cron` and `uninstall_cron` tests mock `sys.platform` — need to verify the mock approach works correctly since `sys.platform` is checked at module level in some Python versions. Using `unittest.mock.patch` on `ideagen.cli.schedule_store.sys` is the safe pattern. — Incorrect mocking could leave tests passing locally but failing in CI. (Step 6 is low-priority; validate before implementing.)
- [x] Interactive REPL `Console()` capture — ~~Revision 2 specifies patching console with StringIO~~ **Resolved in Revision 3:** Rich Console lazily resolves `sys.stdout` at print time, so CliRunner captures output transparently. No Console patching needed. Canary assertion added to `test_interactive_quit_exits_cleanly`.
- [x] Interactive REPL mock patch targets — ~~Revisions 1-3 patched at usage site `ideagen.cli.commands.interactive.X`~~ **Resolved in Revision 4:** `interactive_mode()` uses lazy imports inside the function body (lines 17-24). Patching at the usage site silently fails. All patches now target the source module (e.g., `ideagen.cli.config_loader.load_config`). Only `Prompt` stays at usage site (module-level import, line 4). Full patch target reference table added to Step 5.
