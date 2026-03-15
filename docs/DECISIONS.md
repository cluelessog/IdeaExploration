# Decisions: IdeaExploration

> Log of significant plan changes and the reasoning behind them.
> This file survives session restarts — it's the project's institutional memory.

<!-- Format for each entry:

## [YYYY-MM-DD] — {{Decision Title}}

**Context**: What new information triggered this change?

**Old Plan**: What were we going to do before?

**New Plan**: What are we doing now instead?

**Rationale**: Why is the new plan better given the new information?

**Impact**: What in-progress work is affected? What needs to change?

-->

## [2026-03-10] — Scheduler: TOML+cron replaces APScheduler

**Context**: Phase 7 housekeeping identified APScheduler as an unused dependency adding complexity.

**Old Plan**: Use APScheduler for cross-platform scheduling.

**New Plan**: TOML-based schedule persistence with system cron. WSL detection warns users about cron limitations.

**Rationale**: APScheduler runs in-process (schedules lost on exit). TOML+cron is simpler, persistent, and avoids an unnecessary dependency.

**Impact**: Removed `apscheduler` dependency. Schedule store rewritten to use TOML. WSL warning added in Phase 10.

## [2026-03-15] — docs/ framework corrected to match actual state

**Context**: CC Project Framework auto-generated docs/PLAN.md and docs/STATUS.md with stale information — milestones 5-6 shown as in-progress when all phases 1-11 + audit are complete.

**Old Plan**: docs/ showed phases 2-3 with unchecked tasks, milestones 5-6 in-progress.

**New Plan**: Updated to reflect all phases complete, 746 tests, 95%+ coverage. Only Phase 11.5 (web dashboard) remains deferred.

**Rationale**: Stale status files would mislead the cross-project dashboard and future sessions.

**Impact**: No code changes. docs/PLAN.md, docs/STATUS.md, and docs/DECISIONS.md updated.
