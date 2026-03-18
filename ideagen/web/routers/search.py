"""Idea search routes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ideagen.web.dependencies import get_storage, get_templates

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_class=HTMLResponse)
async def search_ideas(request: Request, q: str = ""):
    """Search ideas across all runs."""
    storage = get_storage()
    templates = get_templates()

    if not q.strip():
        return templates.TemplateResponse(request, "search/results.html", {
            "query": "",
            "ideas": [],
            "message": "Enter a search term",
        })

    ideas = await storage.search_ideas(q.strip())

    message = None
    if not ideas:
        message = f"No ideas matching '{q.strip()}'"

    return templates.TemplateResponse(request, "search/results.html", {
        "query": q.strip(),
        "ideas": ideas,
        "message": message,
    })
