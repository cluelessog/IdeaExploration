"""Extra tests for run_registry to cover shutdown and cleanup edge cases."""
from __future__ import annotations

import asyncio

import pytest

from ideagen.web.run_registry import (
    RunStatus,
    clear_registry,
    create_run_task,
    shutdown_registry,
    cleanup_task,
)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


class TestShutdownRegistry:
    async def test_shutdown_cancels_running_tasks(self):
        task = create_run_task(domain="software")

        async def fake_work():
            await asyncio.sleep(100)

        task.asyncio_task = asyncio.create_task(fake_work())
        await shutdown_registry()
        assert task.asyncio_task.done()

    async def test_shutdown_with_no_tasks(self):
        # Should not raise
        await shutdown_registry()


class TestCleanupTask:
    async def test_cleanup_task_can_be_cancelled(self):
        t = asyncio.create_task(cleanup_task())
        await asyncio.sleep(0.1)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        assert t.done()
