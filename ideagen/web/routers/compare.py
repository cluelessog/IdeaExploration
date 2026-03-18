"""Run comparison routes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ideagen.web.dependencies import get_storage, get_templates

router = APIRouter(prefix="/compare", tags=["compare"])


@router.get("", response_class=HTMLResponse)
async def compare_select(request: Request):
    """Show run selection form for comparison."""
    storage = get_storage()
    templates = get_templates()
    runs = await storage.get_runs(offset=0, limit=100)
    return templates.TemplateResponse(request, "compare/select.html", {
        "runs": runs,
    })


@router.get("/result", response_class=HTMLResponse)
async def compare_result(request: Request, run_a: str = "", run_b: str = ""):
    """Show comparison results."""
    from ideagen.core.comparison import compare_runs

    storage = get_storage()
    templates = get_templates()

    if not run_a or not run_b:
        return templates.TemplateResponse(request, "compare/result.html", {
            "error": "Please select two runs to compare",
            "result": None,
            "run_a": None,
            "run_b": None,
        })

    detail_a = await storage.get_run_detail(run_a)
    detail_b = await storage.get_run_detail(run_b)

    if detail_a is None:
        return templates.TemplateResponse(request, "compare/result.html", {
            "error": f"Run '{run_a}' not found",
            "result": None,
            "run_a": None,
            "run_b": None,
        }, status_code=404)

    if detail_b is None:
        return templates.TemplateResponse(request, "compare/result.html", {
            "error": f"Run '{run_b}' not found",
            "result": None,
            "run_a": None,
            "run_b": None,
        }, status_code=404)

    result = compare_runs(detail_a, detail_b)

    return templates.TemplateResponse(request, "compare/result.html", {
        "result": result,
        "run_a": detail_a,
        "run_b": detail_b,
        "error": None,
    })
