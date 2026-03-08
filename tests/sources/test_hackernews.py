"""Tests for ideagen.sources.hackernews — HackerNews collector."""
from __future__ import annotations

import pytest
import respx
import httpx

from ideagen.core.models import Domain, TrendingItem
from ideagen.sources.hackernews import HackerNewsSource, DOMAIN_KEYWORDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_story(item_id: int, title: str, score: int = 100, descendants: int = 20, url: str = "https://example.com") -> dict:
    return {
        "id": item_id,
        "title": title,
        "url": url,
        "score": score,
        "descendants": descendants,
        "time": 1700000000,
        "type": "story",
        "by": "testuser",
    }


HN_BASE = "https://hacker-news.firebaseio.com/v0"


# ---------------------------------------------------------------------------
# Class-level metadata
# ---------------------------------------------------------------------------


class TestHackerNewsMetadata:
    def test_parser_version_is_1_0(self):
        assert HackerNewsSource.PARSER_VERSION == "1.0"

    def test_name_property_is_hackernews(self):
        source = HackerNewsSource()
        assert source.name == "hackernews"

    def test_is_datasource_subclass(self):
        from ideagen.sources.base import DataSource
        assert isinstance(HackerNewsSource(), DataSource)


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_true_on_200(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[1, 2, 3])
        )
        source = HackerNewsSource()
        assert await source.is_available() is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_false_on_500(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(500)
        )
        source = HackerNewsSource()
        assert await source.is_available() is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_false_on_network_error(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        source = HackerNewsSource()
        assert await source.is_available() is False


# ---------------------------------------------------------------------------
# collect — basic return values
# ---------------------------------------------------------------------------


class TestCollect:
    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_returns_trending_items(self):
        story_ids = [1001, 1002]
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=story_ids)
        )
        respx.get(f"{HN_BASE}/item/1001.json").mock(
            return_value=httpx.Response(200, json=_make_story(1001, "Show HN: AI tool for developers", score=500))
        )
        respx.get(f"{HN_BASE}/item/1002.json").mock(
            return_value=httpx.Response(200, json=_make_story(1002, "New SaaS platform launches", score=300))
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert len(items) > 0
        for item in items:
            assert isinstance(item, TrendingItem)
            assert item.source == "hackernews"

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_populates_metadata_fields(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[2001])
        )
        respx.get(f"{HN_BASE}/item/2001.json").mock(
            return_value=httpx.Response(200, json=_make_story(2001, "Show HN: AI saas tool", score=250, descendants=42))
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=5)

        assert len(items) == 1
        item = items[0]
        assert item.metadata["hn_id"] == 2001
        assert item.metadata["type"] == "story"
        assert item.metadata["by"] == "testuser"
        assert item.score == 250
        assert item.comment_count == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_uses_hn_fallback_url_when_no_url(self):
        story_data = {
            "id": 3001,
            "title": "Ask HN: best developer tool",
            "score": 100,
            "descendants": 10,
            "time": 1700000000,
            "type": "ask",
            "by": "user",
            # no "url" key — should fall back to HN item URL
        }
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[3001])
        )
        respx.get(f"{HN_BASE}/item/3001.json").mock(
            return_value=httpx.Response(200, json=story_data)
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=5)

        assert len(items) == 1
        assert "news.ycombinator.com/item?id=3001" in items[0].url

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_respects_limit(self):
        # 10 stories, all match keywords, limit=3
        story_ids = list(range(4001, 4011))
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=story_ids)
        )
        for sid in story_ids:
            respx.get(f"{HN_BASE}/item/{sid}.json").mock(
                return_value=httpx.Response(200, json=_make_story(sid, f"ai tool {sid}", score=100))
            )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=3)

        assert len(items) <= 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_skips_items_without_title(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[5001, 5002])
        )
        respx.get(f"{HN_BASE}/item/5001.json").mock(
            return_value=httpx.Response(200, json={"id": 5001, "score": 10})  # no title
        )
        respx.get(f"{HN_BASE}/item/5002.json").mock(
            return_value=httpx.Response(200, json=_make_story(5002, "SaaS platform for developers", score=200))
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert all(item.metadata["hn_id"] != 5001 for item in items)

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_skips_null_item_response(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[6001])
        )
        respx.get(f"{HN_BASE}/item/6001.json").mock(
            return_value=httpx.Response(200, json=None)
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert items == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_returns_empty_list_when_no_stories(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[])
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert items == []


# ---------------------------------------------------------------------------
# Domain keyword filtering
# ---------------------------------------------------------------------------


class TestDomainKeywordFiltering:
    @pytest.mark.asyncio
    @respx.mock
    async def test_filters_out_irrelevant_titles_for_software_saas(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[7001, 7002])
        )
        respx.get(f"{HN_BASE}/item/7001.json").mock(
            return_value=httpx.Response(
                200, json=_make_story(7001, "Interesting history of ancient Rome", score=300)
            )
        )
        respx.get(f"{HN_BASE}/item/7002.json").mock(
            return_value=httpx.Response(
                200, json=_make_story(7002, "New AI tool for developers", score=200)
            )
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        titles = [i.title for i in items]
        assert "Interesting history of ancient Rome" not in titles
        assert "New AI tool for developers" in titles

    @pytest.mark.asyncio
    @respx.mock
    async def test_filters_by_business_keywords(self):
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[8001, 8002])
        )
        respx.get(f"{HN_BASE}/item/8001.json").mock(
            return_value=httpx.Response(
                200, json=_make_story(8001, "How we grew revenue 10x in startup", score=400)
            )
        )
        respx.get(f"{HN_BASE}/item/8002.json").mock(
            return_value=httpx.Response(
                200, json=_make_story(8002, "Unrelated cooking recipe post", score=50)
            )
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.BROAD_BUSINESS, limit=10)

        titles = [i.title for i in items]
        assert any("revenue" in t.lower() or "startup" in t.lower() for t in titles)
        assert "Unrelated cooking recipe post" not in titles

    @pytest.mark.asyncio
    @respx.mock
    async def test_domain_keywords_dict_covers_all_domains(self):
        for domain in Domain:
            assert domain in DOMAIN_KEYWORDS
            assert len(DOMAIN_KEYWORDS[domain]) > 0


# ---------------------------------------------------------------------------
# Network error handling
# ---------------------------------------------------------------------------


class TestNetworkErrorHandling:
    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_continues_when_individual_item_fetch_fails(self, monkeypatch):
        import asyncio

        async def _noop_sleep(_delay: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[9001, 9002])
        )
        respx.get(f"{HN_BASE}/item/9001.json").mock(
            side_effect=httpx.ConnectError("failed")
        )
        respx.get(f"{HN_BASE}/item/9002.json").mock(
            return_value=httpx.Response(200, json=_make_story(9002, "SaaS tool for automation", score=150))
        )

        source = HackerNewsSource()
        # Should not raise, should return the successful item
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert len(items) == 1
        assert items[0].metadata["hn_id"] == 9002

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_continues_when_item_returns_500(self, monkeypatch):
        import asyncio

        async def _noop_sleep(_delay: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[10001, 10002])
        )
        # 10001 returns 500 on all retries
        respx.get(f"{HN_BASE}/item/10001.json").mock(
            return_value=httpx.Response(500)
        )
        respx.get(f"{HN_BASE}/item/10002.json").mock(
            return_value=httpx.Response(200, json=_make_story(10002, "AI platform launch", score=200))
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        # 10002 should still be collected
        assert any(item.metadata["hn_id"] == 10002 for item in items)

    @pytest.mark.asyncio
    @respx.mock
    async def test_item_timestamp_defaults_to_epoch_when_time_is_zero(self):
        story = _make_story(11001, "developer tool saas", score=100)
        story["time"] = 0
        respx.get(f"{HN_BASE}/topstories.json").mock(
            return_value=httpx.Response(200, json=[11001])
        )
        respx.get(f"{HN_BASE}/item/11001.json").mock(
            return_value=httpx.Response(200, json=story)
        )

        source = HackerNewsSource()
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=5)

        assert len(items) == 1
        from datetime import timezone
        assert items[0].timestamp.tzinfo is not None
