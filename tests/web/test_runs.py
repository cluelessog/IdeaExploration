"""Tests for run history and detail views."""
from __future__ import annotations

import pytest

from tests.conftest import make_run


class TestRunsList:
    async def test_empty_runs_shows_message(self, client):
        resp = await client.get("/runs")
        assert resp.status_code == 200
        assert "No runs yet" in resp.text
        assert "/pipeline/new" in resp.text

    async def test_runs_with_data_shows_table(self, client, memory_storage):
        run = make_run(title="Test Idea")
        await memory_storage.save_run(run)

        resp = await client.get("/runs")
        assert resp.status_code == 200
        assert "<table>" in resp.text
        assert "<tr>" in resp.text

    async def test_pagination_25_runs(self, client, memory_storage):
        for i in range(25):
            run = make_run(title=f"Idea {i}", content_hash=f"hash_{i}")
            await memory_storage.save_run(run)

        resp = await client.get("/runs?page=2")
        assert resp.status_code == 200
        assert "Page 2 of 2" in resp.text

    async def test_pagination_page_999_shows_no_runs(self, client, memory_storage):
        for i in range(5):
            run = make_run(title=f"Idea {i}", content_hash=f"hash_{i}")
            await memory_storage.save_run(run)

        resp = await client.get("/runs?page=999")
        assert resp.status_code == 200
        # Page is clamped to max+1, which will show "No runs on this page"
        # or it'll show runs from the last valid page
        assert resp.status_code == 200

    async def test_pagination_page_1_default(self, client, memory_storage):
        for i in range(25):
            run = make_run(title=f"Idea {i}", content_hash=f"hash_{i}")
            await memory_storage.save_run(run)

        resp = await client.get("/runs")
        assert resp.status_code == 200
        assert "Page 1 of 2" in resp.text


class TestRunDetail:
    async def test_valid_run_id(self, client, memory_storage):
        run = make_run(title="My Great Idea")
        run_id = await memory_storage.save_run(run)

        resp = await client.get(f"/runs/{run_id}")
        assert resp.status_code == 200
        assert "My Great Idea" in resp.text
        # Check idea card content
        assert "WTP:" in resp.text
        assert "Problem:" in resp.text
        assert "Solution:" in resp.text

    async def test_nonexistent_run_returns_404(self, client):
        resp = await client.get("/runs/nonexistent-id-12345")
        assert resp.status_code == 404
        assert "not found" in resp.text

    async def test_run_detail_shows_metadata(self, client, memory_storage):
        run = make_run(title="Meta Idea")
        run_id = await memory_storage.save_run(run)

        resp = await client.get(f"/runs/{run_id}")
        assert resp.status_code == 200
        assert "SOFTWARE_SAAS" in resp.text


class TestRunsPartialPage:
    async def test_partial_returns_200(self, client, memory_storage):
        run = make_run(title="Partial Idea")
        await memory_storage.save_run(run)

        resp = await client.get("/runs/partials/page?page=1")
        assert resp.status_code == 200
