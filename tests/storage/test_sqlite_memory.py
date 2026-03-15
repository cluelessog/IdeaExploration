"""Tests for SQLiteStorage with :memory: databases.

The bug: _initialized is an instance flag, but each method call opens a NEW
aiosqlite.connect(":memory:") — which creates a fresh empty database — then
closes it. The flag from the first call skips schema creation on the next call,
which then operates on an empty (tableless) database.
"""
from __future__ import annotations

import pytest
from pathlib import Path

from ideagen.core.models import Domain, RunResult
from ideagen.storage.sqlite import SQLiteStorage

from tests.storage.test_sqlite import _make_run, _make_report


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_db_persists_across_calls() -> None:
    """save_run followed by get_runs on :memory: storage returns saved data."""
    storage = SQLiteStorage(db_path=":memory:")
    run = _make_run("Memory Persistence Test")
    run_id = await storage.save_run(run)

    runs = await storage.get_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
    assert runs[0]["domain"] == Domain.SOFTWARE_SAAS.value


@pytest.mark.asyncio
async def test_memory_db_schema_created_once() -> None:
    """Tables still exist after a second _ensure_db call (schema not lost)."""
    storage = SQLiteStorage(db_path=":memory:")

    # First call creates schema
    db1 = await storage._ensure_db()
    # Second call must see the same tables (not a fresh empty DB)
    db2 = await storage._ensure_db()

    cursor = await db2.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
    )
    row = await cursor.fetchone()
    assert row is not None, "runs table must exist on second _ensure_db call"


@pytest.mark.asyncio
async def test_file_db_unaffected(tmp_path: Path) -> None:
    """Existing file-based DB behaviour is unchanged."""
    db_file = tmp_path / "test.db"
    storage = SQLiteStorage(db_path=str(db_file))

    run = _make_run("File DB Idea")
    run_id = await storage.save_run(run)

    # File is created
    assert db_file.exists()

    runs = await storage.get_runs()
    assert len(runs) == 1
    assert runs[0]["id"] == run_id
