from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from ideagen.core.models import (
    Domain,
    Idea,
    IdeaReport,
    MarketAnalysis,
    FeasibilityScore,
    MonetizationAngle,
    RunResult,
)
from ideagen.storage.sqlite import SQLiteStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_idea(title: str = "Test Idea") -> Idea:
    return Idea(
        title=title,
        problem_statement="A real problem",
        solution="A clever solution",
        domain=Domain.SOFTWARE_SAAS,
        novelty_score=7.5,
        content_hash="abc123",
        tags=["saas", "productivity"],
    )


def _make_report(title: str = "Test Idea", wtp_score: float = 4.2) -> IdeaReport:
    return IdeaReport(
        idea=_make_idea(title),
        market_analysis=MarketAnalysis(
            target_audience="Developers",
            market_size_estimate="$1B",
            competitors=["CompA"],
            differentiation="Better UX",
        ),
        feasibility=FeasibilityScore(
            complexity=5,
            time_to_mvp="3 months",
            suggested_tech_stack=["Python", "FastAPI"],
            risks=["Market fit"],
        ),
        monetization=MonetizationAngle(
            revenue_model="SaaS",
            pricing_strategy="Freemium",
            estimated_revenue_potential="$100k ARR",
        ),
        wtp_score=wtp_score,
    )


def _make_run(title: str = "Test Idea", timestamp: datetime | None = None) -> RunResult:
    return RunResult(
        ideas=[_make_report(title)],
        sources_used=["hackernews", "reddit"],
        domain=Domain.SOFTWARE_SAAS,
        timestamp=timestamp or datetime.now(),
        config_snapshot={"model": "gpt-4o"},
        content_hash="run_hash_001",
        total_items_scraped=42,
        total_after_dedup=30,
    )


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteStorage:
    db_file = tmp_path / "test.db"
    return SQLiteStorage(db_path=str(db_file))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_database_auto_created(tmp_path: Path) -> None:
    """Database file is created automatically on first use."""
    db_file = tmp_path / "subdir" / "nested" / "ideagen.db"
    storage = SQLiteStorage(db_path=str(db_file))
    run = _make_run()
    await storage.save_run(run)
    assert db_file.exists()


@pytest.mark.asyncio
async def test_schema_version_set(storage: SQLiteStorage) -> None:
    """Schema version row is inserted on first init."""
    import aiosqlite
    run = _make_run()
    await storage.save_run(run)

    async with aiosqlite.connect(str(storage._db_path)) as db:
        cursor = await db.execute("SELECT version FROM schema_version LIMIT 1")
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == 1


@pytest.mark.asyncio
async def test_save_run_and_get_runs_round_trip(storage: SQLiteStorage) -> None:
    """save_run persists a run; get_runs returns it."""
    run = _make_run()
    run_id = await storage.save_run(run)
    assert run_id  # non-empty UUID string

    runs = await storage.get_runs()
    assert len(runs) == 1
    stored = runs[0]
    assert stored["id"] == run_id
    assert stored["domain"] == Domain.SOFTWARE_SAAS.value
    assert stored["ideas_count"] == 1
    assert stored["total_items_scraped"] == 42
    assert stored["total_after_dedup"] == 30


@pytest.mark.asyncio
async def test_get_idea_returns_correct_report(storage: SQLiteStorage) -> None:
    """get_idea reconstructs the full IdeaReport from the stored JSON."""
    run = _make_run("My Special Idea")
    await storage.save_run(run)

    runs = await storage.get_runs()
    run_id = runs[0]["id"]

    import aiosqlite
    async with aiosqlite.connect(str(storage._db_path)) as db:
        cursor = await db.execute("SELECT id FROM ideas WHERE run_id = ?", (run_id,))
        row = await cursor.fetchone()
    idea_id = row[0]

    report = await storage.get_idea(idea_id)
    assert report is not None
    assert report.idea.title == "My Special Idea"
    assert report.idea.domain == Domain.SOFTWARE_SAAS
    assert report.wtp_score == pytest.approx(4.2)


@pytest.mark.asyncio
async def test_get_idea_missing_returns_none(storage: SQLiteStorage) -> None:
    """get_idea returns None for an unknown id."""
    result = await storage.get_idea("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_search_ideas_by_title(storage: SQLiteStorage) -> None:
    """search_ideas finds ideas whose title matches the query."""
    await storage.save_run(_make_run("Invoice Automation Tool"))
    await storage.save_run(_make_run("Customer Feedback Dashboard"))

    results = await storage.search_ideas("Invoice")
    assert len(results) == 1
    assert results[0].idea.title == "Invoice Automation Tool"


@pytest.mark.asyncio
async def test_search_ideas_by_problem_statement(storage: SQLiteStorage) -> None:
    """search_ideas matches against problem_statement field."""
    report = _make_report("Generic Title")
    report = report.model_copy(
        update={"idea": report.idea.model_copy(update={"problem_statement": "unique_needle_problem"})}
    )
    run = RunResult(
        ideas=[report],
        sources_used=[],
        domain=Domain.SOFTWARE_SAAS,
    )
    await storage.save_run(run)

    results = await storage.search_ideas("unique_needle_problem")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_ideas_by_solution(storage: SQLiteStorage) -> None:
    """search_ideas matches against solution field."""
    report = _make_report("Generic Title 2")
    report = report.model_copy(
        update={"idea": report.idea.model_copy(update={"solution": "unique_needle_solution"})}
    )
    run = RunResult(
        ideas=[report],
        sources_used=[],
        domain=Domain.SOFTWARE_SAAS,
    )
    await storage.save_run(run)

    results = await storage.search_ideas("unique_needle_solution")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_search_ideas_no_match(storage: SQLiteStorage) -> None:
    """search_ideas returns empty list when nothing matches."""
    await storage.save_run(_make_run("Some Idea"))
    results = await storage.search_ideas("zzz_no_match_zzz")
    assert results == []


@pytest.mark.asyncio
async def test_pagination_offset_limit(storage: SQLiteStorage) -> None:
    """get_runs respects offset and limit parameters."""
    for i in range(5):
        await storage.save_run(_make_run(f"Idea {i}"))

    page1 = await storage.get_runs(offset=0, limit=2)
    page2 = await storage.get_runs(offset=2, limit=2)
    page3 = await storage.get_runs(offset=4, limit=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1

    # No duplicates across pages
    ids = {r["id"] for r in page1 + page2 + page3}
    assert len(ids) == 5


@pytest.mark.asyncio
async def test_search_ideas_pagination(storage: SQLiteStorage) -> None:
    """search_ideas respects offset and limit."""
    for i in range(6):
        await storage.save_run(_make_run(f"Matching Idea {i}"))

    all_results = await storage.search_ideas("Matching", offset=0, limit=100)
    assert len(all_results) == 6

    page = await storage.search_ideas("Matching", offset=0, limit=3)
    assert len(page) == 3

    page2 = await storage.search_ideas("Matching", offset=3, limit=3)
    assert len(page2) == 3

    ids_page1 = {r.idea.title for r in page}
    ids_page2 = {r.idea.title for r in page2}
    assert ids_page1.isdisjoint(ids_page2)


@pytest.mark.asyncio
async def test_delete_runs_older_than(storage: SQLiteStorage) -> None:
    """delete_runs_older_than removes old runs and their ideas."""
    old_ts = datetime.now() - timedelta(days=40)
    new_ts = datetime.now() - timedelta(days=1)

    await storage.save_run(_make_run("Old Idea", timestamp=old_ts))
    await storage.save_run(_make_run("New Idea", timestamp=new_ts))

    deleted = await storage.delete_runs_older_than(days=30)
    assert deleted == 1

    runs = await storage.get_runs()
    assert len(runs) == 1
    assert runs[0]["domain"] == Domain.SOFTWARE_SAAS.value

    # Verify associated ideas were also deleted
    import aiosqlite
    async with aiosqlite.connect(str(storage._db_path)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM ideas")
        row = await cursor.fetchone()
    # Only the new run's idea remains
    assert row[0] == 1


@pytest.mark.asyncio
async def test_delete_runs_older_than_none_deleted(storage: SQLiteStorage) -> None:
    """delete_runs_older_than returns 0 when no runs qualify."""
    await storage.save_run(_make_run())
    deleted = await storage.delete_runs_older_than(days=365)
    assert deleted == 0


# ---------------------------------------------------------------------------
# find_runs_by_content_hash tests (Phase 10.1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_runs_by_content_hash_finds_match(storage: SQLiteStorage) -> None:
    """find_runs_by_content_hash returns runs with matching hash."""
    run1 = _make_run("Idea A")
    run1.content_hash = "duplicate_hash"
    await storage.save_run(run1)

    run2 = _make_run("Idea B")
    run2.content_hash = "duplicate_hash"
    await storage.save_run(run2)

    matches = await storage.find_runs_by_content_hash("duplicate_hash")
    assert len(matches) == 2


@pytest.mark.asyncio
async def test_find_runs_by_content_hash_excludes_self(storage: SQLiteStorage) -> None:
    """find_runs_by_content_hash with exclude_id omits the specified run."""
    run = _make_run("Idea A")
    run.content_hash = "my_hash"
    run_id = await storage.save_run(run)

    matches = await storage.find_runs_by_content_hash("my_hash", exclude_id=run_id)
    assert len(matches) == 0


@pytest.mark.asyncio
async def test_find_runs_by_content_hash_no_match(storage: SQLiteStorage) -> None:
    """find_runs_by_content_hash returns empty list for unique hash."""
    run = _make_run("Idea A")
    run.content_hash = "unique_hash"
    await storage.save_run(run)

    matches = await storage.find_runs_by_content_hash("nonexistent_hash")
    assert matches == []


# ---------------------------------------------------------------------------
# find_runs_by_prefix tests (Phase 10.3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_runs_by_prefix_single_match(storage: SQLiteStorage) -> None:
    """find_runs_by_prefix returns a single matching run."""
    run_id = await storage.save_run(_make_run("Idea A"))
    matches = await storage.find_runs_by_prefix(run_id[:8])
    assert len(matches) == 1
    assert matches[0]["id"] == run_id


@pytest.mark.asyncio
async def test_find_runs_by_prefix_multiple_matches(storage: SQLiteStorage) -> None:
    """find_runs_by_prefix returns all matching runs ordered by timestamp DESC."""
    import aiosqlite

    # Insert two runs with known IDs sharing a prefix
    run1 = _make_run("Old Idea")
    run1_ts = datetime(2024, 1, 1).isoformat()
    run2 = _make_run("New Idea")
    run2_ts = datetime(2024, 6, 1).isoformat()

    db = await storage._ensure_db()
    try:
        await db.execute(
            "INSERT INTO runs (id, timestamp, domain, sources_used, ideas_count, total_items_scraped, total_after_dedup, content_hash, config_snapshot) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("aaa-old-run", run1_ts, "SOFTWARE_SAAS", "hackernews", 1, 42, 30, "h1", "{}"),
        )
        await db.execute(
            "INSERT INTO runs (id, timestamp, domain, sources_used, ideas_count, total_items_scraped, total_after_dedup, content_hash, config_snapshot) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("aaa-new-run", run2_ts, "SOFTWARE_SAAS", "hackernews", 1, 42, 30, "h2", "{}"),
        )
        await db.commit()
    finally:
        await db.close()

    matches = await storage.find_runs_by_prefix("aaa")
    assert len(matches) == 2
    # Most recent first
    assert matches[0]["id"] == "aaa-new-run"
    assert matches[1]["id"] == "aaa-old-run"


@pytest.mark.asyncio
async def test_find_runs_by_prefix_no_match(storage: SQLiteStorage) -> None:
    """find_runs_by_prefix returns empty list for non-matching prefix."""
    await storage.save_run(_make_run("Idea A"))
    matches = await storage.find_runs_by_prefix("zzz-nonexistent")
    assert matches == []
