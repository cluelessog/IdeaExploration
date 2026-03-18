"""FastAPI application factory for the IdeaGen web dashboard."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ideagen.web.dependencies import get_templates, lifespan

_HERE = Path(__file__).resolve().parent


def create_app(*, allowed_hosts: list[str] | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="IdeaGen Dashboard", lifespan=lifespan)

    # DNS rebinding protection
    hosts = allowed_hosts or ["localhost", "127.0.0.1"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    # Static files
    app.mount("/static", StaticFiles(directory=str(_HERE / "static")), name="static")

    # Register routers (lazy imports keep startup quick when web deps missing)
    from ideagen.web.routers.runs import router as runs_router
    from ideagen.web.routers.pipeline import router as pipeline_router
    from ideagen.web.routers.compare import router as compare_router
    from ideagen.web.routers.search import router as search_router
    from ideagen.web.routers.config import router as config_router

    app.include_router(runs_router)
    app.include_router(pipeline_router)
    app.include_router(compare_router)
    app.include_router(search_router)
    app.include_router(config_router)

    @app.get("/")
    async def index(request: Request):
        templates = get_templates()
        return templates.TemplateResponse(request, "index.html")

    return app
