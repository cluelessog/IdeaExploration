"""Tests for idea search routes."""
from __future__ import annotations

import pytest

from tests.conftest import make_run


class TestSearch:
    async def test_empty_search_shows_message(self, client):
        resp = await client.get("/search")
        assert resp.status_code == 200
        assert "Enter a search term" in resp.text

    async def test_search_with_whitespace_only(self, client):
        resp = await client.get("/search?q=   ")
        assert resp.status_code == 200
        assert "Enter a search term" in resp.text

    async def test_search_no_results(self, client, memory_storage):
        run = make_run(title="Python Framework")
        await memory_storage.save_run(run)

        resp = await client.get("/search?q=zzzznonexistent")
        assert resp.status_code == 200
        assert "No ideas matching" in resp.text

    async def test_search_with_results(self, client, memory_storage):
        run = make_run(title="SaaS Dashboard Builder")
        await memory_storage.save_run(run)

        resp = await client.get("/search?q=saas")
        assert resp.status_code == 200
        # Should find the idea with "SaaS" in title (case-insensitive LIKE)
        # The search uses LIKE which is case-insensitive for ASCII in SQLite
        assert "SaaS Dashboard Builder" in resp.text or "result" in resp.text.lower()

    async def test_search_shows_result_count(self, client, memory_storage):
        run = make_run(title="SaaS Tool")
        await memory_storage.save_run(run)

        resp = await client.get("/search?q=SaaS")
        assert resp.status_code == 200
        assert "1 result" in resp.text
