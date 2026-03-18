"""Tests for get_runs_count()."""
from __future__ import annotations

import pytest

from ideagen.storage.sqlite import SQLiteStorage
from tests.conftest import make_run


class TestGetRunsCount:
    async def test_empty_db_returns_zero(self):
        storage = SQLiteStorage(db_path=":memory:")
        try:
            count = await storage.get_runs_count()
            assert count == 0
        finally:
            await storage.close()

    async def test_five_inserts_returns_five(self):
        storage = SQLiteStorage(db_path=":memory:")
        try:
            for i in range(5):
                run = make_run(title=f"Idea {i}", content_hash=f"hash_{i}")
                await storage.save_run(run)
            count = await storage.get_runs_count()
            assert count == 5
        finally:
            await storage.close()

    async def test_count_after_single_insert(self):
        storage = SQLiteStorage(db_path=":memory:")
        try:
            run = make_run(title="Solo Idea")
            await storage.save_run(run)
            count = await storage.get_runs_count()
            assert count == 1
        finally:
            await storage.close()
