"""Shared fixtures for web dashboard tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from ideagen.core.config import IdeaGenConfig
from ideagen.storage.sqlite import SQLiteStorage
from ideagen.web import dependencies
from ideagen.web.app import create_app
from ideagen.web.run_registry import clear_registry


@pytest.fixture
async def memory_storage():
    """In-memory SQLiteStorage for tests."""
    storage = SQLiteStorage(db_path=":memory:")
    yield storage
    await storage.close()


@pytest.fixture
async def test_config():
    """Default config for tests."""
    return IdeaGenConfig()


@pytest.fixture
async def app(memory_storage, test_config):
    """Create a test app with in-memory storage."""
    dependencies.reset()
    dependencies.configure(config=test_config, storage=memory_storage)
    clear_registry()
    application = create_app(allowed_hosts=["testserver", "localhost", "127.0.0.1"])
    yield application
    dependencies.reset()
    clear_registry()


@pytest.fixture
async def client(app):
    """httpx AsyncClient wired to the ASGI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
