"""Tests for the FastAPI app foundation, index page, static files, and middleware."""
from __future__ import annotations

import pytest


class TestIndexPage:
    async def test_index_returns_200(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200

    async def test_index_contains_nav_links(self, client):
        resp = await client.get("/")
        html = resp.text
        assert "/runs" in html
        assert "/compare" in html
        assert "/config" in html
        assert "/pipeline/new" in html

    async def test_index_contains_title(self, client):
        resp = await client.get("/")
        assert "IdeaGen Dashboard" in resp.text


class TestStaticFiles:
    async def test_pico_css_returns_200(self, client):
        resp = await client.get("/static/pico.min.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers["content-type"]

    async def test_htmx_js_returns_200(self, client):
        resp = await client.get("/static/htmx.min.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers["content-type"]

    async def test_app_css_returns_200(self, client):
        resp = await client.get("/static/app.css")
        assert resp.status_code == 200


class TestTrustedHostMiddleware:
    async def test_localhost_allowed(self, client):
        resp = await client.get("/", headers={"Host": "localhost"})
        assert resp.status_code == 200

    async def test_evil_host_rejected(self, client):
        resp = await client.get("/", headers={"Host": "evil.com"})
        assert resp.status_code == 400


class TestSingleton:
    def test_get_storage_returns_same_instance(self, memory_storage):
        from ideagen.web.dependencies import get_storage
        s1 = get_storage()
        s2 = get_storage()
        assert s1 is s2
