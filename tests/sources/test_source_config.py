"""Tests verifying SourceConfig fields are threaded through to source constructors."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ideagen.core.config import SourceConfig
from ideagen.sources.reddit import RedditSource
from ideagen.sources.registry import get_sources_by_names
from ideagen.sources.twitter import TwitterSource


class TestSourceRegistryPassesConfig:
    """Verify SourceConfig fields reach source constructors via registry."""

    def test_source_registry_passes_config(self):
        """get_sources_by_names forwards a SourceConfig to source constructors."""
        cfg = SourceConfig(
            scrape_delay=5.0,
            reddit_subreddits=["python", "django"],
        )
        sources = get_sources_by_names(["reddit", "twitter"], source_config=cfg)
        reddit = sources["reddit"]
        assert isinstance(reddit, RedditSource)
        assert reddit._scrape_delay == 5.0

    def test_reddit_receives_custom_subreddits(self):
        """Config subreddits list is forwarded to RedditSource."""
        cfg = SourceConfig(reddit_subreddits=["python", "django", "fastapi"])
        sources = get_sources_by_names(["reddit"], source_config=cfg)
        reddit = sources["reddit"]
        assert isinstance(reddit, RedditSource)
        assert reddit._subreddits == ["python", "django", "fastapi"]

    def test_scrape_delay_passed_to_reddit(self):
        """scrape_delay from SourceConfig is forwarded to RedditSource."""
        cfg = SourceConfig(scrape_delay=7.5)
        sources = get_sources_by_names(["reddit"], source_config=cfg)
        assert sources["reddit"]._scrape_delay == 7.5

    def test_scrape_delay_passed_to_twitter(self):
        """scrape_delay from SourceConfig is forwarded to TwitterSource."""
        cfg = SourceConfig(scrape_delay=4.2)
        sources = get_sources_by_names(["twitter"], source_config=cfg)
        assert isinstance(sources["twitter"], TwitterSource)
        assert sources["twitter"]._scrape_delay == 4.2

    def test_default_config_still_works(self):
        """Calling get_sources_by_names without source_config uses defaults (backward compat)."""
        sources = get_sources_by_names(["reddit", "twitter"])
        assert "reddit" in sources
        assert "twitter" in sources
        reddit = sources["reddit"]
        twitter = sources["twitter"]
        # Defaults from each constructor
        assert reddit._scrape_delay == 2.0
        assert reddit._subreddits is None
        assert twitter._scrape_delay == 3.0

    def test_run_command_threads_source_config(self):
        """CLI run_command passes config.sources to get_sources_by_names."""
        from typer.testing import CliRunner
        from ideagen.cli.app import app

        runner = CliRunner()

        # run.py uses lazy imports; patch at the module where the symbol lives
        with patch("ideagen.sources.registry.get_sources_by_names") as mock_get_sources, \
             patch("ideagen.providers.registry.get_provider", return_value=MagicMock()), \
             patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()), \
             patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()), \
             patch("ideagen.cli.formatters.PipelineEventRenderer", return_value=MagicMock()):
            mock_get_sources.return_value = {}
            runner.invoke(app, ["run", "--dry-run"])

        # Verify source_config kwarg was passed
        assert mock_get_sources.called
        call_kwargs = mock_get_sources.call_args
        assert "source_config" in call_kwargs.kwargs, (
            "run_command should pass source_config= to get_sources_by_names"
        )
