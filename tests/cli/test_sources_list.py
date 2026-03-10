"""Tests for ideagen sources list command."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ideagen.cli.app import app
from ideagen.core.config import IdeaGenConfig, SourceConfig


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_sources_list_shows_all_sources(runner: CliRunner) -> None:
    """ideagen sources list shows all 4 registered source names."""
    result = runner.invoke(app, ["sources", "list"])
    assert result.exit_code == 0
    for name in ("hackernews", "reddit", "producthunt", "twitter"):
        assert name in result.output


def test_sources_list_shows_enabled_disabled(runner: CliRunner) -> None:
    """Sources list correctly marks enabled/disabled sources."""
    config = IdeaGenConfig(sources=SourceConfig(enabled=["hackernews"]))
    with patch("ideagen.cli.config_loader.load_config", return_value=config):
        result = runner.invoke(app, ["sources", "list"])

    assert result.exit_code == 0
    assert "hackernews" in result.output
    assert "enabled" in result.output
    assert "disabled" in result.output


def test_sources_list_all_disabled(runner: CliRunner) -> None:
    """When no sources are enabled, all show as disabled."""
    config = IdeaGenConfig(sources=SourceConfig(enabled=[]))
    with patch("ideagen.cli.config_loader.load_config", return_value=config):
        result = runner.invoke(app, ["sources", "list"])

    assert result.exit_code == 0
    # All 4 should be disabled
    assert result.output.count("disabled") == 4
