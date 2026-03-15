# Open Questions

## IdeaGen Implementation - 2026-03-06

All previously open questions have been resolved in Revision 2 of the plan. Decisions are documented in the "Resolved Decisions" table in the plan file.

### Resolved (2026-03-06, Revision 2)

- [x] Should the scheduler use APScheduler instead of system cron? -- **Decision (revised): TOML+cron.** APScheduler was initially chosen but removed in Phase 7 — it runs in-process (schedules lost on exit). TOML persistence + system cron is simpler and persistent. WSL detection added in Phase 10.
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

## Phase 10-11: Robustness & Capabilities - 2026-03-14

### Resolved (2026-03-14, Revision 2 — Architect + Critic feedback)

- [x] Should `DuplicateRunWarning` be a `PipelineEvent` subclass or a simple logger.warning? — **Decision: PipelineEvent subclass in `ideagen/core/models.py`.** Consistent with all other event types (SourceFailed, CacheEmptyWarning). Service layer owns the event stream; CLI renderer just displays it. Keeps warning logic in one layer.
- [x] For `compare` command (11.3), should idea matching use exact title match or fuzzy match? — **Decision: Fuzzy match from day one using `rapidfuzz.fuzz.ratio()` with 0.85 default threshold.** Exact matching produces misleading diffs when titles have minor wording changes across runs. The rapidfuzz + 0.85 pattern is already proven in `dedup.py`. `--threshold` CLI flag exposed for tunability.
- [x] Should `--format json` suppress ALL Rich output (including errors) or only progress spinners? — **Decision: Use an inline async consumer instead of PipelineEventRenderer entirely.** When `--format` is json or markdown, a 5-line `_consume_pipeline()` function iterates events directly — no Rich objects instantiated at all. Errors from the pipeline itself propagate as exceptions (normal Python error handling), not Rich console output.
- [x] Where should `DuplicateRunWarning` model be defined? — **Decision: `ideagen/core/models.py`.** Consistent with StageStarted, StageCompleted, SourceFailed, IdeaGenerated, PipelineComplete all being in models.py. Architect suggested CLI layer as alternative but service-layer placement was chosen for consistency.
- [x] Should `service.py` capture `save_run()` return value? — **Decision: Yes.** Line 182 changes to `run_id = await self._storage.save_run(result)` so the generated UUID can be passed as `exclude_id` to `find_runs_by_content_hash()`.
- [x] How to handle double-warning for unknown sources in 11.2? — **Decision: Registry-only warning, CLI only on total failure.** `get_sources_by_names()` already logs `logger.warning(f"Unknown source: {name}")`. CLI does NOT add its own warning for individual unknowns. CLI only intervenes when ALL requested sources are unknown (error exit listing valid names).

### Remaining (Non-Blocking)

- [ ] For `prompts init` (11.4), should template files contain the full default prompt text or just a comment explaining the format? — Full default text is more useful as a starting point but creates maintenance burden if defaults change. Plan recommends full text with a header comment noting the version.
- [ ] Both `MockStorage` classes in test files are manually kept in sync with `StorageBackend` ABC. Consider extracting a shared `MockStorage` to `tests/conftest.py` to avoid future breakage when new abstract methods are added. — Non-blocking for this phase; worth doing as housekeeping afterward.

## Audit Fixes Plan - 2026-03-15

- [ ] Phase 1 TODO 1.1: Should `--cached` with partial source match (e.g., cache has PH+HN, request PH+HN+Reddit) return the partial data or fail? — Plan says return empty with warning (strict match). An alternative is returning available sources with a warning about missing ones. Impacts whether users can incrementally add sources with `--cached`.
- [ ] Phase 1 TODO 1.3: For `:memory:` SQLite, should the persistent connection be held open indefinitely or should we use a connection pool? — Holding one connection open is simplest for test usage (primary :memory: use case). Production always uses file-backed DB. If :memory: is ever used in production, a pool would be needed.
- [ ] Phase 3 TODO 3.3: When removing schema duplication from ClaudeProvider, should OpenAI and Gemini providers also be audited for the same pattern? — Plan says yes (check all providers). Need to verify whether those providers also append schema independently.
- [ ] Phase 4 TODO 4.1: DryRunProvider approach vs lazy construction — DryRunProvider is more explicit but adds a class. Lazy construction (move get_provider inside the async function) is less code but changes the error timing for real runs. Plan recommends DryRunProvider for clarity.
- [ ] Phase 4 TODO 4.3: Should invalid domain be a hard error (exit 1) or a warning with fallback? — Plan says hard error. Current behavior (silent fallback) is explicitly called out as a bug. Changing to hard error is a behavioral change users might notice.
- [ ] Phase 5 TODO 5.1: Config error behavior — should invalid config abort (exit 1) or warn and use defaults? — Both are defensible. Aborting is safer (user knows config is broken). Warning + defaults matches current behavior but with visibility. Plan recommends warning + defaults for backward compatibility.
