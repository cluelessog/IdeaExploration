"""Tests for run comparison routes."""
from __future__ import annotations

import pytest

from tests.conftest import make_run, make_report


class TestCompareSelect:
    async def test_select_page_returns_200(self, client):
        resp = await client.get("/compare")
        assert resp.status_code == 200

    async def test_select_page_no_runs(self, client):
        resp = await client.get("/compare")
        assert "No runs available" in resp.text

    async def test_select_page_with_runs(self, client, memory_storage):
        run = make_run(title="Idea A")
        await memory_storage.save_run(run)
        resp = await client.get("/compare")
        assert resp.status_code == 200
        assert "run_a" in resp.text


class TestCompareResult:
    async def test_missing_params_shows_error(self, client):
        resp = await client.get("/compare/result")
        assert resp.status_code == 200
        assert "Please select two runs" in resp.text

    async def test_nonexistent_run_a_returns_404(self, client):
        resp = await client.get("/compare/result?run_a=nonexistent&run_b=also-nonexistent")
        assert resp.status_code == 404

    async def test_nonexistent_run_b_returns_404(self, client, memory_storage):
        run = make_run(title="Idea A")
        run_id = await memory_storage.save_run(run)
        resp = await client.get(f"/compare/result?run_a={run_id}&run_b=nonexistent")
        assert resp.status_code == 404

    async def test_valid_comparison(self, client, memory_storage):
        run_a = make_run(title="Idea A")
        run_b = make_run(title="Idea B")
        id_a = await memory_storage.save_run(run_a)
        id_b = await memory_storage.save_run(run_b)

        resp = await client.get(f"/compare/result?run_a={id_a}&run_b={id_b}")
        assert resp.status_code == 200
        # Both runs should be shown
        assert id_a[:12] in resp.text
        assert id_b[:12] in resp.text

    async def test_identical_runs_shows_identical(self, client, memory_storage):
        run_a = make_run(title="Same Idea")
        run_b = make_run(title="Same Idea")
        id_a = await memory_storage.save_run(run_a)
        id_b = await memory_storage.save_run(run_b)

        resp = await client.get(f"/compare/result?run_a={id_a}&run_b={id_b}")
        assert resp.status_code == 200
        assert "identical" in resp.text.lower() or "Common" in resp.text

    async def test_different_runs_shows_added_removed(self, client, memory_storage):
        from ideagen.core.models import RunResult, Domain
        report_a = make_report(title="Automated Email Marketing Platform", wtp_score=4.0)
        report_b = make_report(title="Zero-Code Mobile App Builder", wtp_score=4.0)
        run_a = RunResult(
            ideas=[report_a], sources_used=["hn"], domain=Domain.SOFTWARE_SAAS,
            content_hash="diff_a", total_items_scraped=10, total_after_dedup=5,
        )
        run_b = RunResult(
            ideas=[report_b], sources_used=["hn"], domain=Domain.SOFTWARE_SAAS,
            content_hash="diff_b", total_items_scraped=10, total_after_dedup=5,
        )
        id_a = await memory_storage.save_run(run_a)
        id_b = await memory_storage.save_run(run_b)

        resp = await client.get(f"/compare/result?run_a={id_a}&run_b={id_b}")
        assert resp.status_code == 200
        assert "Added" in resp.text or "Removed" in resp.text

    async def test_score_changes_shown(self, client, memory_storage):
        from ideagen.core.models import RunResult, Domain
        from tests.conftest import make_report
        report_a = make_report(title="Same Idea", wtp_score=3.0)
        report_b = make_report(title="Same Idea", wtp_score=5.0)
        run_a = RunResult(
            ideas=[report_a], sources_used=["hn"], domain=Domain.SOFTWARE_SAAS,
            content_hash="a1", total_items_scraped=10, total_after_dedup=5,
        )
        run_b = RunResult(
            ideas=[report_b], sources_used=["hn"], domain=Domain.SOFTWARE_SAAS,
            content_hash="b1", total_items_scraped=10, total_after_dedup=5,
        )
        id_a = await memory_storage.save_run(run_a)
        id_b = await memory_storage.save_run(run_b)

        resp = await client.get(f"/compare/result?run_a={id_a}&run_b={id_b}")
        assert resp.status_code == 200
        assert "Score" in resp.text or "compare-added" in resp.text
