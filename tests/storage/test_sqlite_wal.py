"""Tests for SQLite WAL mode."""
from __future__ import annotations

import pytest

from ideagen.storage.sqlite import SQLiteStorage


class TestWALMode:
    async def test_file_backed_db_uses_wal(self, tmp_path):
        db_path = str(tmp_path / "test_wal.db")
        storage = SQLiteStorage(db_path=db_path)
        db = await storage._ensure_db()
        try:
            cursor = await db.execute("PRAGMA journal_mode")
            row = await cursor.fetchone()
            assert row[0] == "wal"
        finally:
            await storage._release_db(db)

    async def test_memory_db_does_not_use_wal(self):
        storage = SQLiteStorage(db_path=":memory:")
        db = await storage._ensure_db()
        try:
            cursor = await db.execute("PRAGMA journal_mode")
            row = await cursor.fetchone()
            # :memory: databases use "memory" journal mode
            assert row[0] == "memory"
        finally:
            await storage._release_db(db)
            await storage.close()
