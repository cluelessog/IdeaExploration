"""Config display routes (read-only)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ideagen.web.dependencies import get_config, get_templates

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_class=HTMLResponse)
async def view_config(request: Request):
    """Display current configuration (read-only)."""
    config = get_config()
    templates = get_templates()

    return templates.TemplateResponse(request, "config/view.html", {
        "config": config,
    })
