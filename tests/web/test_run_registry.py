"""Tests for the run registry (bounded concurrency, TTL cleanup, replay buffer)."""
from __future__ import annotations

import time

import pytest

from ideagen.web.run_registry import (
    MAX_CONCURRENT_RUNS,
    COMPLETED_TTL_SECONDS,
    RunStatus,
    RunTask,
    _cleanup_expired,
    _registry,
    can_start_run,
    clear_registry,
    create_run_task,
    get_active_count,
    get_run_task,
    list_run_tasks,
)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


class TestCreateRunTask:
    def test_create_returns_run_task(self):
        task = create_run_task(domain="software")
        assert task is not None
        assert task.domain == "software"
        assert task.status == RunStatus.PENDING

    def test_create_generates_unique_ids(self):
        t1 = create_run_task(domain="software")
        t2 = create_run_task(domain="software")
        assert t1.task_id != t2.task_id

    def test_max_concurrent_respected(self):
        for _ in range(MAX_CONCURRENT_RUNS):
            task = create_run_task(domain="software")
            assert task is not None

        # 4th should fail
        task = create_run_task(domain="software")
        assert task is None

    def test_completed_task_frees_slot(self):
        tasks = []
        for _ in range(MAX_CONCURRENT_RUNS):
            t = create_run_task(domain="software")
            tasks.append(t)

        # Mark one complete
        tasks[0].mark_completed(RunStatus.COMPLETED)

        # Should be able to create another
        new_task = create_run_task(domain="software")
        assert new_task is not None


class TestCanStartRun:
    def test_true_when_empty(self):
        assert can_start_run() is True

    def test_false_when_full(self):
        for _ in range(MAX_CONCURRENT_RUNS):
            create_run_task(domain="software")
        assert can_start_run() is False


class TestGetRunTask:
    def test_returns_task_by_id(self):
        task = create_run_task(domain="software")
        found = get_run_task(task.task_id)
        assert found is task

    def test_returns_none_for_unknown_id(self):
        assert get_run_task("nonexistent") is None


class TestRunTaskReplayBuffer:
    def test_append_event_adds_to_buffer(self):
        task = RunTask(task_id="test-1")
        task.append_event({"event": "test", "data": "hello"})
        assert len(task.events) == 1
        assert task.events[0]["event"] == "test"
        assert task.events[0]["id"] == 0

    def test_events_get_monotonic_ids(self):
        task = RunTask(task_id="test-1")
        task.append_event({"event": "a", "data": "1"})
        task.append_event({"event": "b", "data": "2"})
        task.append_event({"event": "c", "data": "3"})
        assert [e["id"] for e in task.events] == [0, 1, 2]

    def test_mark_completed_sets_status(self):
        task = RunTask(task_id="test-1")
        task.mark_completed(RunStatus.COMPLETED)
        assert task.status == RunStatus.COMPLETED
        assert task.completed_at is not None


class TestCleanupExpired:
    def test_cleanup_removes_old_completed_tasks(self):
        task = create_run_task(domain="software")
        task.mark_completed(RunStatus.COMPLETED)
        # Simulate the task being old
        task.completed_at = time.monotonic() - COMPLETED_TTL_SECONDS - 60

        _cleanup_expired()
        assert get_run_task(task.task_id) is None

    def test_cleanup_keeps_recent_completed_tasks(self):
        task = create_run_task(domain="software")
        task.mark_completed(RunStatus.COMPLETED)
        # completed_at was just set (recent)

        _cleanup_expired()
        assert get_run_task(task.task_id) is not None

    def test_cleanup_keeps_running_tasks(self):
        task = create_run_task(domain="software")
        task.status = RunStatus.RUNNING

        _cleanup_expired()
        assert get_run_task(task.task_id) is not None


class TestListRunTasks:
    def test_returns_all_tasks(self):
        create_run_task(domain="software")
        create_run_task(domain="business")
        assert len(list_run_tasks()) == 2


class TestGetActiveCount:
    def test_counts_pending_and_running(self):
        t1 = create_run_task(domain="software")
        t2 = create_run_task(domain="software")
        t2.status = RunStatus.RUNNING
        t3 = create_run_task(domain="software")
        t3.mark_completed(RunStatus.COMPLETED)

        assert get_active_count() == 2  # pending + running
