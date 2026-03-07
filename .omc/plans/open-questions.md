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
