"""Tests for ideagen.sources.registry."""
from __future__ import annotations

import pytest

from ideagen.sources.base import DataSource
from ideagen.sources.hackernews import HackerNewsSource
from ideagen.sources.producthunt import ProductHuntSource
from ideagen.sources.registry import (
    get_all_sources,
    get_available_source_names,
    get_sources_by_names,
)
from ideagen.sources.twitter import TwitterSource


# ---------------------------------------------------------------------------
# get_available_source_names
# ---------------------------------------------------------------------------


class TestGetAvailableSourceNames:
    def test_returns_list(self):
        names = get_available_source_names()
        assert isinstance(names, list)

    def test_returns_four_names(self):
        names = get_available_source_names()
        assert len(names) == 4

    def test_contains_hackernews(self):
        assert "hackernews" in get_available_source_names()

    def test_contains_reddit(self):
        assert "reddit" in get_available_source_names()

    def test_contains_producthunt(self):
        assert "producthunt" in get_available_source_names()

    def test_contains_twitter(self):
        assert "twitter" in get_available_source_names()


# ---------------------------------------------------------------------------
# get_all_sources
# ---------------------------------------------------------------------------


class TestGetAllSources:
    def test_returns_dict(self):
        sources = get_all_sources()
        assert isinstance(sources, dict)

    def test_returns_four_sources(self):
        sources = get_all_sources()
        assert len(sources) == 4

    def test_all_values_are_datasource_instances(self):
        sources = get_all_sources()
        for name, source in sources.items():
            assert isinstance(source, DataSource), f"{name} is not a DataSource"

    def test_hackernews_key_maps_to_hackernews_source(self):
        sources = get_all_sources()
        assert isinstance(sources["hackernews"], HackerNewsSource)

    def test_producthunt_key_maps_to_producthunt_source(self):
        sources = get_all_sources()
        assert isinstance(sources["producthunt"], ProductHuntSource)

    def test_twitter_key_maps_to_twitter_source(self):
        sources = get_all_sources()
        assert isinstance(sources["twitter"], TwitterSource)

    def test_names_match_source_name_property(self):
        sources = get_all_sources()
        for key, source in sources.items():
            assert source.name == key

    def test_kwargs_forwarded_to_hackernews(self):
        sources = get_all_sources(timeout=99.0)
        hn = sources["hackernews"]
        assert isinstance(hn, HackerNewsSource)
        # HackerNewsSource accepts timeout kwarg
        assert hn._timeout == 99.0

    def test_kwargs_forwarded_to_producthunt(self):
        sources = get_all_sources(timeout=99.0)
        ph = sources["producthunt"]
        assert isinstance(ph, ProductHuntSource)
        assert ph._timeout == 99.0


# ---------------------------------------------------------------------------
# get_sources_by_names
# ---------------------------------------------------------------------------


class TestGetSourcesByNames:
    def test_returns_dict(self):
        result = get_sources_by_names(["hackernews"])
        assert isinstance(result, dict)

    def test_single_valid_name(self):
        result = get_sources_by_names(["hackernews"])
        assert "hackernews" in result
        assert isinstance(result["hackernews"], HackerNewsSource)

    def test_multiple_valid_names(self):
        result = get_sources_by_names(["hackernews", "producthunt"])
        assert len(result) == 2
        assert "hackernews" in result
        assert "producthunt" in result

    def test_all_four_valid_names(self):
        result = get_sources_by_names(["hackernews", "reddit", "producthunt", "twitter"])
        assert len(result) == 4

    def test_invalid_name_omitted(self):
        result = get_sources_by_names(["hackernews", "nonexistent"])
        assert "hackernews" in result
        assert "nonexistent" not in result

    def test_only_invalid_names_returns_empty(self):
        result = get_sources_by_names(["bogus", "fake"])
        assert result == {}

    def test_empty_list_returns_empty(self):
        result = get_sources_by_names([])
        assert result == {}

    def test_duplicate_names_returns_one_entry(self):
        result = get_sources_by_names(["hackernews", "hackernews"])
        # dict keys are unique, so second assignment overwrites first
        assert len(result) == 1
        assert "hackernews" in result

    def test_all_returned_values_are_datasource_instances(self):
        result = get_sources_by_names(["hackernews", "producthunt", "twitter"])
        for source in result.values():
            assert isinstance(source, DataSource)

    def test_invalid_name_logs_warning(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="ideagen"):
            get_sources_by_names(["unknownsource"])
        assert any("Unknown source" in rec.message for rec in caplog.records)
