"""Registry for active and recently-completed pipeline runs.

Design:
- Max 3 concurrent runs (MAX_CONCURRENT_RUNS)
- Completed tasks kept for 30 minutes (COMPLETED_TTL_SECONDS) then cleaned up
- Each RunTask has a replay buffer (append-only list) for SSE reconnection
- asyncio.Event signals new events to waiting SSE clients
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("ideagen")

MAX_CONCURRENT_RUNS = 3
COMPLETED_TTL_SECONDS = 1800  # 30 minutes


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunTask:
    task_id: str
    domain: str = "software"
    status: RunStatus = RunStatus.PENDING
    events: list[dict] = field(default_factory=list)
    event_signal: asyncio.Event = field(default_factory=asyncio.Event)
    completed_at: float | None = None
    asyncio_task: asyncio.Task | None = field(default=None, repr=False)

    def append_event(self, event_data: dict) -> None:
        """Append an event to the replay buffer and signal waiting clients."""
        event_data["id"] = len(self.events)
        self.events.append(event_data)
        # Set signal so waiting SSE clients wake up; they will clear it after reading
        self.event_signal.set()

    def mark_completed(self, status: RunStatus = RunStatus.COMPLETED) -> None:
        self.status = status
        self.completed_at = time.monotonic()
        # Final signal so any waiting SSE clients unblock
        self.event_signal.set()


# --- Module-level registry ---

_registry: dict[str, RunTask] = {}


def get_active_count() -> int:
    return sum(1 for t in _registry.values() if t.status in (RunStatus.PENDING, RunStatus.RUNNING))


def can_start_run() -> bool:
    return get_active_count() < MAX_CONCURRENT_RUNS


def create_run_task(domain: str = "software") -> RunTask | None:
    """Create a new run task if capacity allows. Returns None if at max."""
    if not can_start_run():
        return None
    task_id = str(uuid.uuid4())
    task = RunTask(task_id=task_id, domain=domain)
    _registry[task_id] = task
    return task


def get_run_task(task_id: str) -> RunTask | None:
    return _registry.get(task_id)


def list_run_tasks() -> list[RunTask]:
    return list(_registry.values())


async def cleanup_task() -> None:
    """Background task that removes expired completed runs."""
    try:
        while True:
            await asyncio.sleep(60)
            _cleanup_expired()
    except asyncio.CancelledError:
        pass


def _cleanup_expired() -> None:
    now = time.monotonic()
    expired = [
        tid for tid, task in _registry.items()
        if task.completed_at is not None
        and (now - task.completed_at) > COMPLETED_TTL_SECONDS
    ]
    for tid in expired:
        del _registry[tid]


async def shutdown_registry() -> None:
    """Cancel all running tasks on shutdown."""
    for task in _registry.values():
        if task.asyncio_task and not task.asyncio_task.done():
            task.asyncio_task.cancel()
            try:
                await task.asyncio_task
            except (asyncio.CancelledError, Exception):
                pass


def clear_registry() -> None:
    """Clear all tasks (for testing)."""
    _registry.clear()
