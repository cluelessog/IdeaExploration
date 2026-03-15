from __future__ import annotations

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from ideagen.core.models import (
    Domain,
    TrendingItem,
    CacheEmptyWarning,
    StageCompleted,
)
from ideagen.storage.sqlite import SQLiteStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(title: str, source: str = "hackernews") -> TrendingItem:
    return TrendingItem(
        title=title,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        source=source,
        score=42,
        timestamp=datetime(2025, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteStorage:
    db_file = tmp_path / "test.db"
    return SQLiteStorage(db_path=str(db_file))


# ---------------------------------------------------------------------------
# Core cache filtering tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_returns_only_matching_sources(storage: SQLiteStorage) -> None:
    """Cache PH+HN items, request only HN — get only HN items back."""
    batch_id = "batch-001"
    hn_items = [_make_item("HN Post 1", "hackernews"), _make_item("HN Post 2", "hackernews")]
    ph_items = [_make_item("PH Product 1", "producthunt")]

    await storage.save_scrape_cache(batch_id, "hackernews", hn_items)
    await storage.save_scrape_cache(batch_id, "producthunt", ph_items)

    result = await storage.load_latest_scrape_cache(source_names=["hackernews"])

    assert len(result) == 2
    assert all(item.source == "hackernews" for item in result)


@pytest.mark.asyncio
async def test_cache_mismatch_returns_empty(storage: SQLiteStorage) -> None:
    """Cache has PH, request HN — batch lacks HN so return empty list."""
    batch_id = "batch-002"
    ph_items = [_make_item("PH Product 1", "producthunt")]

    await storage.save_scrape_cache(batch_id, "producthunt", ph_items)

    result = await storage.load_latest_scrape_cache(source_names=["hackernews"])

    assert result == []


@pytest.mark.asyncio
async def test_cache_full_match(storage: SQLiteStorage) -> None:
    """Cache PH+HN, request PH+HN — get all items back."""
    batch_id = "batch-003"
    hn_items = [_make_item("HN Post 1", "hackernews")]
    ph_items = [_make_item("PH Product 1", "producthunt")]

    await storage.save_scrape_cache(batch_id, "hackernews", hn_items)
    await storage.save_scrape_cache(batch_id, "producthunt", ph_items)

    result = await storage.load_latest_scrape_cache(source_names=["hackernews", "producthunt"])

    assert len(result) == 2
    sources_returned = {item.source for item in result}
    assert sources_returned == {"hackernews", "producthunt"}


@pytest.mark.asyncio
async def test_cache_partial_match_warns(storage: SQLiteStorage, caplog: pytest.LogCaptureFixture) -> None:
    """Cache has only PH, request PH+HN — returns empty (not all sources present)."""
    import logging
    batch_id = "batch-004"
    ph_items = [_make_item("PH Product 1", "producthunt")]

    await storage.save_scrape_cache(batch_id, "producthunt", ph_items)

    with caplog.at_level(logging.WARNING, logger="ideagen"):
        result = await storage.load_latest_scrape_cache(source_names=["producthunt", "hackernews"])

    assert result == []
    assert any("hackernews" in msg for msg in caplog.messages)


@pytest.mark.asyncio
async def test_cache_no_filter_returns_all(storage: SQLiteStorage) -> None:
    """No source_names param — existing behavior preserved (returns all items)."""
    batch_id = "batch-005"
    hn_items = [_make_item("HN Post 1", "hackernews")]
    ph_items = [_make_item("PH Product 1", "producthunt")]

    await storage.save_scrape_cache(batch_id, "hackernews", hn_items)
    await storage.save_scrape_cache(batch_id, "producthunt", ph_items)

    result = await storage.load_latest_scrape_cache()

    assert len(result) == 2


@pytest.mark.asyncio
async def test_cache_empty_returns_empty(storage: SQLiteStorage) -> None:
    """No cached data returns empty regardless of source_names filter."""
    result = await storage.load_latest_scrape_cache(source_names=["hackernews"])
    assert result == []

    result2 = await storage.load_latest_scrape_cache()
    assert result2 == []


@pytest.mark.asyncio
async def test_cache_source_names_case_insensitive(storage: SQLiteStorage) -> None:
    """Source name matching is case-insensitive."""
    batch_id = "batch-006"
    hn_items = [_make_item("HN Post 1", "hackernews")]

    await storage.save_scrape_cache(batch_id, "hackernews", hn_items)

    result = await storage.load_latest_scrape_cache(source_names=["HackerNews"])

    assert len(result) == 1
    assert result[0].source == "hackernews"


# ---------------------------------------------------------------------------
# Service integration test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_service_passes_source_names_to_cache(tmp_path: Path) -> None:
    """IdeaGenService passes source names to load_latest_scrape_cache in cached mode."""
    from ideagen.core.service import IdeaGenService
    from ideagen.core.config import IdeaGenConfig
    from ideagen.sources.base import DataSource
    from ideagen.providers.base import AIProvider

    # Build a mock storage that records the call args
    mock_storage = MagicMock()
    mock_storage.load_latest_scrape_cache = AsyncMock(return_value=[])

    # Minimal mock source
    mock_source = MagicMock(spec=DataSource)

    # Minimal mock provider
    mock_provider = MagicMock(spec=AIProvider)

    service = IdeaGenService(
        sources={"hackernews": mock_source, "producthunt": mock_source},
        provider=mock_provider,
        storage=mock_storage,
        config=IdeaGenConfig(),
    )

    # Drain the async generator
    events = []
    async for event in service.run(cached=True):
        events.append(event)

    # Verify load_latest_scrape_cache was called with source_names
    mock_storage.load_latest_scrape_cache.assert_called_once()
    call_kwargs = mock_storage.load_latest_scrape_cache.call_args
    # Accept either positional or keyword argument
    passed_sources = (
        call_kwargs.kwargs.get("source_names")
        or (call_kwargs.args[0] if call_kwargs.args else None)
    )
    assert passed_sources is not None
    assert set(passed_sources) == {"hackernews", "producthunt"}
