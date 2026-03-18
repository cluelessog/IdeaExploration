"""Pipeline trigger and SSE streaming routes."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from starlette.responses import Response

from ideagen.core.models import Domain, PipelineEvent
from ideagen.web.dependencies import get_config, get_storage, get_templates
from ideagen.web.run_registry import (
    RunStatus,
    RunTask,
    can_start_run,
    create_run_task,
    get_run_task,
)

logger = logging.getLogger("ideagen")

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

DOMAIN_MAP = {
    "software": Domain.SOFTWARE_SAAS,
    "business": Domain.BROAD_BUSINESS,
    "content": Domain.CONTENT_MEDIA,
}


@router.get("/new", response_class=HTMLResponse)
async def new_pipeline(request: Request):
    """Show pipeline trigger form."""
    templates = get_templates()
    return templates.TemplateResponse(request, "pipeline/new.html", {
        "domains": list(DOMAIN_MAP.keys()),
    })


@router.post("/start")
async def start_pipeline(request: Request):
    """Trigger a new pipeline run."""
    form = await request.form()
    domain_str = str(form.get("domain", "software"))

    if not can_start_run():
        return Response(
            content="Too many concurrent runs. Please wait.",
            status_code=429,
            media_type="text/plain",
        )

    run_task = create_run_task(domain=domain_str)
    if run_task is None:
        return Response(
            content="Too many concurrent runs. Please wait.",
            status_code=429,
            media_type="text/plain",
        )

    # Start the pipeline in the background
    asyncio_task = asyncio.create_task(_run_pipeline(run_task))
    run_task.asyncio_task = asyncio_task

    return RedirectResponse(
        url=f"/pipeline/progress/{run_task.task_id}",
        status_code=303,
    )


@router.get("/progress/{task_id}", response_class=HTMLResponse)
async def pipeline_progress(request: Request, task_id: str):
    """Show pipeline progress page with SSE connection."""
    templates = get_templates()
    run_task = get_run_task(task_id)
    if run_task is None:
        return templates.TemplateResponse(request, "pipeline/progress.html", {
            "task_id": task_id,
            "error": "Run task not found",
        }, status_code=404)
    return templates.TemplateResponse(request, "pipeline/progress.html", {
        "task_id": task_id,
        "error": None,
    })


@router.get("/events/{task_id}")
async def pipeline_events(request: Request, task_id: str):
    """SSE endpoint for pipeline progress events."""
    run_task = get_run_task(task_id)
    if run_task is None:
        return Response(content="Task not found", status_code=404)

    # Support reconnection via Last-Event-ID
    last_id_header = request.headers.get("last-event-id")
    last_id = int(last_id_header) if last_id_header is not None else -1

    return StreamingResponse(
        _sse_generator(run_task, last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/cancel/{task_id}")
async def cancel_pipeline(request: Request, task_id: str):
    """Cancel a running pipeline."""
    run_task = get_run_task(task_id)
    if run_task is None:
        return Response(content="Task not found", status_code=404)

    if run_task.asyncio_task and not run_task.asyncio_task.done():
        run_task.asyncio_task.cancel()

    run_task.append_event({"event": "cancelled", "data": "Pipeline cancelled by user"})
    run_task.mark_completed(RunStatus.CANCELLED)

    return RedirectResponse(url=f"/pipeline/progress/{task_id}", status_code=303)


async def _sse_generator(run_task: RunTask, last_id: int):
    """Generate SSE events from the run task's replay buffer."""
    cursor = last_id + 1

    while True:
        # Replay any buffered events from cursor onward
        while cursor < len(run_task.events):
            event = run_task.events[cursor]
            yield _format_sse(event)
            cursor += 1

        # If the task is done and we've replayed everything, send done and stop
        if run_task.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
            break

        # Wait for new events
        try:
            await asyncio.wait_for(
                _wait_for_event(run_task),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            # Send keepalive comment
            yield ": keepalive\n\n"


async def _wait_for_event(run_task: RunTask) -> None:
    """Wait until a new event is signaled."""
    initial_count = len(run_task.events)
    while len(run_task.events) == initial_count:
        if run_task.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
            return
        await asyncio.sleep(0.05)


def _format_sse(event: dict) -> str:
    """Format a dict as an SSE message."""
    event_type = event.get("event", "message")
    data = event.get("data", "")
    if isinstance(data, dict):
        data = json.dumps(data)
    event_id = event.get("id", "")
    lines = [f"event: {event_type}", f"data: {data}", f"id: {event_id}", "", ""]
    return "\n".join(lines)


async def _run_pipeline(run_task: RunTask) -> None:
    """Execute the pipeline and publish events to the run task."""
    try:
        run_task.status = RunStatus.RUNNING
        run_task.append_event({"event": "status", "data": {"status": "running"}})

        domain = DOMAIN_MAP.get(run_task.domain, Domain.SOFTWARE_SAAS)
        config = get_config()
        storage = get_storage()

        # Build sources and provider
        from ideagen.sources.registry import get_sources_by_names
        from ideagen.providers.registry import get_provider
        from ideagen.core.service import IdeaGenService

        sources = get_sources_by_names(config.sources.enabled, source_config=config.sources)
        provider = get_provider(config.providers)
        service = IdeaGenService(
            sources=sources,
            provider=provider,
            storage=storage,
            config=config,
        )

        async for event in service.run(domain=domain):
            event_data = _pipeline_event_to_dict(event)
            run_task.append_event(event_data)

        run_task.append_event({"event": "done", "data": {"status": "completed"}})
        run_task.mark_completed(RunStatus.COMPLETED)

    except asyncio.CancelledError:
        run_task.append_event({"event": "cancelled", "data": "Pipeline cancelled"})
        run_task.mark_completed(RunStatus.CANCELLED)
    except Exception as e:
        logger.exception("Pipeline run failed")
        run_task.append_event({"event": "error", "data": {"error": str(e)}})
        run_task.mark_completed(RunStatus.FAILED)


def _pipeline_event_to_dict(event: PipelineEvent) -> dict:
    """Convert a PipelineEvent to an SSE-friendly dict."""
    data = event.model_dump(mode="json")
    return {
        "event": event.event_type,
        "data": data,
    }
