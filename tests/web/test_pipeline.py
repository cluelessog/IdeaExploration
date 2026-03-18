"""Tests for pipeline trigger, progress, and SSE streaming."""
from __future__ import annotations

import asyncio
import json

import pytest

from ideagen.web.run_registry import (
    RunStatus,
    RunTask,
    clear_registry,
    create_run_task,
    get_run_task,
)
from ideagen.web.routers.pipeline import _format_sse, _pipeline_event_to_dict
from ideagen.core.models import StageStarted, StageCompleted


class TestPipelineNewForm:
    async def test_new_form_returns_200(self, client):
        resp = await client.get("/pipeline/new")
        assert resp.status_code == 200
        assert "domain" in resp.text
        assert "software" in resp.text

    async def test_new_form_has_all_domains(self, client):
        resp = await client.get("/pipeline/new")
        assert "software" in resp.text
        assert "business" in resp.text
        assert "content" in resp.text


class TestPipelineStart:
    async def test_start_returns_303_redirect(self, client):
        resp = await client.post(
            "/pipeline/start",
            data={"domain": "software"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/pipeline/progress/" in resp.headers["location"]

    async def test_start_max_concurrent_returns_429(self, client):
        # Fill up all 3 slots
        for _ in range(3):
            task = create_run_task(domain="software")
            assert task is not None

        resp = await client.post(
            "/pipeline/start",
            data={"domain": "software"},
            follow_redirects=False,
        )
        assert resp.status_code == 429


class TestPipelineProgress:
    async def test_progress_page_returns_200(self, client):
        task = create_run_task(domain="software")
        resp = await client.get(f"/pipeline/progress/{task.task_id}")
        assert resp.status_code == 200
        assert task.task_id in resp.text

    async def test_progress_unknown_task_returns_404(self, client):
        resp = await client.get("/pipeline/progress/nonexistent-id")
        assert resp.status_code == 404


class TestPipelineEvents:
    async def test_events_unknown_task_returns_404(self, client):
        resp = await client.get("/pipeline/events/nonexistent-id")
        assert resp.status_code == 404

    async def test_events_stream_completed_task(self, client):
        task = create_run_task(domain="software")
        task.append_event({"event": "stage_started", "data": {"stage": "collect"}})
        task.append_event({"event": "stage_completed", "data": {"stage": "collect", "duration_ms": 100}})
        task.append_event({"event": "done", "data": {"status": "completed"}})
        task.mark_completed(RunStatus.COMPLETED)

        resp = await client.get(f"/pipeline/events/{task.task_id}")
        assert resp.status_code == 200
        text = resp.text
        assert "event: stage_started" in text
        assert "event: stage_completed" in text
        assert "event: done" in text

    async def test_events_reconnection_with_last_event_id(self, client):
        task = create_run_task(domain="software")
        task.append_event({"event": "stage_started", "data": {"stage": "collect"}})
        task.append_event({"event": "stage_completed", "data": {"stage": "collect", "duration_ms": 100}})
        task.append_event({"event": "done", "data": {"status": "completed"}})
        task.mark_completed(RunStatus.COMPLETED)

        # Reconnect after event 0 — should skip event 0
        resp = await client.get(
            f"/pipeline/events/{task.task_id}",
            headers={"last-event-id": "0"},
        )
        assert resp.status_code == 200
        text = resp.text
        # Event 0 (stage_started) should NOT be repeated at the start
        lines = text.strip().split("\n")
        # First event line should be stage_completed (id: 1)
        assert "event: stage_completed" in lines[0]

    async def test_events_reconnection_after_completion_replays_buffer(self, client):
        task = create_run_task(domain="software")
        task.append_event({"event": "stage_started", "data": {"stage": "collect"}})
        task.append_event({"event": "done", "data": {"status": "completed"}})
        task.mark_completed(RunStatus.COMPLETED)

        # Reconnect with no Last-Event-ID — should replay entire buffer
        resp = await client.get(f"/pipeline/events/{task.task_id}")
        assert resp.status_code == 200
        assert "event: stage_started" in resp.text
        assert "event: done" in resp.text


class TestPipelineCancel:
    async def test_cancel_returns_redirect(self, client):
        task = create_run_task(domain="software")
        resp = await client.post(
            f"/pipeline/cancel/{task.task_id}",
            follow_redirects=False,
        )
        assert resp.status_code == 303

    async def test_cancel_marks_task_cancelled(self, client):
        task = create_run_task(domain="software")
        await client.post(
            f"/pipeline/cancel/{task.task_id}",
            follow_redirects=False,
        )
        updated = get_run_task(task.task_id)
        assert updated.status == RunStatus.CANCELLED

    async def test_cancel_emits_final_event(self, client):
        task = create_run_task(domain="software")
        await client.post(
            f"/pipeline/cancel/{task.task_id}",
            follow_redirects=False,
        )
        # Check that a cancelled event was appended
        events = [e["event"] for e in task.events]
        assert "cancelled" in events

    async def test_cancel_unknown_task_returns_404(self, client):
        resp = await client.post("/pipeline/cancel/nonexistent", follow_redirects=False)
        assert resp.status_code == 404


class TestFormatSSE:
    def test_format_sse_basic(self):
        result = _format_sse({"event": "test", "data": "hello", "id": 0})
        assert "event: test" in result
        assert "data: hello" in result
        assert "id: 0" in result

    def test_format_sse_dict_data(self):
        result = _format_sse({"event": "test", "data": {"key": "val"}, "id": 1})
        assert "data: {" in result
        parsed = json.loads(result.split("data: ")[1].split("\n")[0])
        assert parsed["key"] == "val"


class TestPipelineEventToDict:
    def test_stage_started(self):
        event = StageStarted(stage="collect", metadata={"sources": ["hn"]})
        result = _pipeline_event_to_dict(event)
        assert result["event"] == "stage_started"
        assert result["data"]["stage"] == "collect"

    def test_stage_completed(self):
        event = StageCompleted(stage="collect", duration_ms=500, metadata={})
        result = _pipeline_event_to_dict(event)
        assert result["event"] == "stage_completed"
        assert result["data"]["duration_ms"] == 500
