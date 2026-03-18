"""Run history and detail routes."""
from __future__ import annotations

import math

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ideagen.web.dependencies import get_storage, get_templates

router = APIRouter(prefix="/runs", tags=["runs"])

PAGE_SIZE = 20


@router.get("", response_class=HTMLResponse)
async def list_runs(request: Request, page: int = 1):
    """Paginated run history list."""
    storage = get_storage()
    templates = get_templates()

    total = await storage.get_runs_count()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, total_pages + 1))

    offset = (page - 1) * PAGE_SIZE
    runs = await storage.get_runs(offset=offset, limit=PAGE_SIZE)

    return templates.TemplateResponse(request, "runs/list.html", {
        "runs": runs,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/partials/page", response_class=HTMLResponse)
async def runs_page_partial(request: Request, page: int = 1):
    """htmx partial for paginated run rows."""
    storage = get_storage()
    templates = get_templates()

    total = await storage.get_runs_count()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, total_pages + 1))

    offset = (page - 1) * PAGE_SIZE
    runs = await storage.get_runs(offset=offset, limit=PAGE_SIZE)

    return templates.TemplateResponse(request, "runs/list.html", {
        "runs": runs,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


@router.get("/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    """Run detail view with idea cards."""
    storage = get_storage()
    templates = get_templates()

    detail = await storage.get_run_detail(run_id)
    if detail is None:
        return templates.TemplateResponse(request, "runs/detail.html", {
            "run": None,
            "error": f"Run '{run_id}' not found",
        }, status_code=404)

    return templates.TemplateResponse(request, "runs/detail.html", {
        "run": detail,
        "ideas": detail.get("ideas", []),
        "error": None,
    })
