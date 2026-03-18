"""Shared dependencies for the web dashboard (singleton storage, config, templates)."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from ideagen.core.config import IdeaGenConfig
from ideagen.storage.sqlite import SQLiteStorage

_HERE = Path(__file__).resolve().parent

# --- Singletons (module-level, one per process) ---

_storage: SQLiteStorage | None = None
_config: IdeaGenConfig | None = None
_templates: Jinja2Templates | None = None


def configure(config: IdeaGenConfig | None = None, storage: SQLiteStorage | None = None) -> None:
    """Allow external code (tests, CLI) to inject config/storage before app starts."""
    global _config, _storage
    if config is not None:
        _config = config
    if storage is not None:
        _storage = storage


def get_config() -> IdeaGenConfig:
    global _config
    if _config is None:
        from ideagen.cli.config_loader import load_config
        _config = load_config()
    return _config


def get_storage() -> SQLiteStorage:
    """Return the singleton storage instance."""
    global _storage
    if _storage is None:
        cfg = get_config()
        _storage = SQLiteStorage(db_path=cfg.storage.database_path)
    return _storage


def get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        _templates = Jinja2Templates(directory=str(_HERE / "templates"))
    return _templates


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle for the FastAPI app."""
    from ideagen.web.run_registry import cleanup_task, shutdown_registry

    # Start background cleanup task for expired run tasks
    task = asyncio.create_task(cleanup_task())
    yield
    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await shutdown_registry()
    # Close storage if we own it
    storage = get_storage()
    await storage.close()


def reset() -> None:
    """Reset singletons (for testing)."""
    global _storage, _config, _templates
    _storage = None
    _config = None
    _templates = None
