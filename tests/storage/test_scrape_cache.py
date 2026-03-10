"""Tests for scrape cache save/load."""
from __future__ import annotations

import pytest
from pathlib import Path

from ideagen.storage.sqlite import SQLiteStorage
from tests.conftest import make_trending_item


@pytest.fixture
def tmp_storage(tmp_path: Path) -> SQLiteStorage:
    return SQLiteStorage(db_path=str(tmp_path / "test.db"))


@pytest.mark.asyncio
async def test_save_and_load_scrape_cache(tmp_storage: SQLiteStorage) -> None:
    """Saved cache items can be loaded back."""
    items_hn = [make_trending_item("HN Post 1", source="hackernews"), make_trending_item("HN Post 2", source="hackernews")]
    items_reddit = [make_trending_item("Reddit Post 1", source="reddit")]

    await tmp_storage.save_scrape_cache("batch-1", "hackernews", items_hn)
    await tmp_storage.save_scrape_cache("batch-1", "reddit", items_reddit)

    loaded = await tmp_storage.load_latest_scrape_cache()
    assert len(loaded) == 3
    titles = {item.title for item in loaded}
    assert "HN Post 1" in titles
    assert "Reddit Post 1" in titles


@pytest.mark.asyncio
async def test_load_latest_cache_empty_db(tmp_storage: SQLiteStorage) -> None:
    """Loading from empty cache returns empty list."""
    loaded = await tmp_storage.load_latest_scrape_cache()
    assert loaded == []


@pytest.mark.asyncio
async def test_load_latest_cache_returns_most_recent_batch(tmp_storage: SQLiteStorage) -> None:
    """When multiple batches exist, latest batch is returned."""
    old_items = [make_trending_item("Old Post", source="hackernews")]
    new_items = [make_trending_item("New Post", source="hackernews")]

    await tmp_storage.save_scrape_cache("batch-old", "hackernews", old_items)
    await tmp_storage.save_scrape_cache("batch-new", "hackernews", new_items)

    loaded = await tmp_storage.load_latest_scrape_cache()
    titles = {item.title for item in loaded}
    assert "New Post" in titles
