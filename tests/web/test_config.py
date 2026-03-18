"""Tests for config display routes."""
from __future__ import annotations

import pytest


class TestConfigView:
    async def test_config_returns_200(self, client):
        resp = await client.get("/config")
        assert resp.status_code == 200

    async def test_config_shows_provider(self, client):
        resp = await client.get("/config")
        assert "claude" in resp.text

    async def test_config_shows_sources(self, client):
        resp = await client.get("/config")
        assert "hackernews" in resp.text

    async def test_config_shows_storage_path(self, client):
        resp = await client.get("/config")
        assert "ideagen.db" in resp.text

    async def test_config_shows_generation_settings(self, client):
        resp = await client.get("/config")
        assert "10" in resp.text  # ideas_per_run default
        assert "0.85" in resp.text  # dedup_threshold default

    async def test_config_is_read_only(self, client):
        resp = await client.get("/config")
        assert "Read-only" in resp.text
