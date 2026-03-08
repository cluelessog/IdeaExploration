"""Tests for ProductHuntSource and TwitterSource."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideagen.core.models import Domain, TrendingItem
from ideagen.sources.producthunt import ProductHuntSource
from ideagen.sources.twitter import TwitterSource, DOMAIN_QUERIES


# ---------------------------------------------------------------------------
# ProductHuntSource — basic attributes
# ---------------------------------------------------------------------------


class TestProductHuntSourceAttributes:
    def test_name_returns_producthunt(self):
        source = ProductHuntSource()
        assert source.name == "producthunt"

    def test_parser_version(self):
        assert ProductHuntSource.PARSER_VERSION == "1.0"

    def test_default_scrape_delay(self):
        source = ProductHuntSource()
        assert source._scrape_delay == 3.0

    def test_custom_scrape_delay(self):
        source = ProductHuntSource(scrape_delay=1.0)
        assert source._scrape_delay == 1.0

    def test_default_timeout(self):
        source = ProductHuntSource()
        assert source._timeout == 15.0

    def test_custom_timeout(self):
        source = ProductHuntSource(timeout=5.0)
        assert source._timeout == 5.0


# ---------------------------------------------------------------------------
# ProductHuntSource — is_available
# ---------------------------------------------------------------------------


class TestProductHuntIsAvailable:
    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client):
            source = ProductHuntSource()
            result = await source.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client):
            source = ProductHuntSource()
            result = await source.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client):
            source = ProductHuntSource()
            result = await source.is_available()
        assert result is False


# ---------------------------------------------------------------------------
# ProductHuntSource — _parse_next_data
# ---------------------------------------------------------------------------


def _make_next_data_html(posts: list[dict]) -> str:
    """Build minimal HTML with __NEXT_DATA__ containing product posts."""
    # Nest posts inside a typical Next.js page props shape
    next_data = {
        "props": {
            "pageProps": {
                "posts": {
                    "edges": [{"node": p} for p in posts]
                }
            }
        }
    }
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'


class TestProductHuntParseNextData:
    def test_parses_single_product(self):
        post = {
            "name": "SuperApp",
            "tagline": "The best app ever",
            "votesCount": 123,
            "slug": "superapp",
            "commentsCount": 10,
            "createdAt": "2026-03-08T00:00:00Z",
            "topics": {"edges": []},
            "thumbnail": None,
        }
        html = _make_next_data_html([post])
        source = ProductHuntSource()
        items = source._parse_next_data(html)
        assert len(items) == 1
        assert items[0].title == "SuperApp — The best app ever"
        assert items[0].score == 123
        assert items[0].source == "producthunt"
        assert items[0].url == "https://www.producthunt.com/posts/superapp"

    def test_title_without_tagline(self):
        post = {
            "name": "MinimalApp",
            "tagline": "",
            "votesCount": 5,
            "slug": "minimalapp",
            "commentsCount": 0,
            "createdAt": "2026-03-08T00:00:00Z",
            "topics": {"edges": []},
            "thumbnail": None,
        }
        html = _make_next_data_html([post])
        source = ProductHuntSource()
        items = source._parse_next_data(html)
        assert len(items) == 1
        assert items[0].title == "MinimalApp"

    def test_parses_multiple_products(self):
        posts = [
            {"name": f"App{i}", "tagline": f"Tag{i}", "votesCount": i * 10,
             "slug": f"app{i}", "commentsCount": 0, "createdAt": "2026-03-08T00:00:00Z",
             "topics": {"edges": []}, "thumbnail": None}
            for i in range(3)
        ]
        html = _make_next_data_html(posts)
        source = ProductHuntSource()
        items = source._parse_next_data(html)
        assert len(items) == 3

    def test_returns_empty_on_empty_html(self):
        source = ProductHuntSource()
        items = source._parse_next_data("<html><body></body></html>")
        assert items == []

    def test_returns_empty_on_malformed_json(self):
        html = '<script id="__NEXT_DATA__" type="application/json">{broken json</script>'
        source = ProductHuntSource()
        items = source._parse_next_data(html)
        assert items == []

    def test_skips_posts_without_name(self):
        post = {
            "name": "",
            "tagline": "No name here",
            "votesCount": 50,
            "slug": "noname",
            "commentsCount": 0,
            "createdAt": "2026-03-08T00:00:00Z",
            "topics": {"edges": []},
            "thumbnail": None,
        }
        html = _make_next_data_html([post])
        source = ProductHuntSource()
        items = source._parse_next_data(html)
        assert items == []

    def test_timestamp_parsed_correctly(self):
        post = {
            "name": "App",
            "tagline": "Tag",
            "votesCount": 1,
            "slug": "app",
            "commentsCount": 0,
            "createdAt": "2026-03-08T12:34:56Z",
            "topics": {"edges": []},
            "thumbnail": None,
        }
        html = _make_next_data_html([post])
        source = ProductHuntSource()
        items = source._parse_next_data(html)
        assert len(items) == 1
        assert items[0].timestamp.year == 2026
        assert items[0].timestamp.month == 3
        assert items[0].timestamp.day == 8

    def test_comment_count_stored(self):
        post = {
            "name": "App",
            "tagline": "Tag",
            "votesCount": 10,
            "slug": "app",
            "commentsCount": 42,
            "createdAt": "2026-03-08T00:00:00Z",
            "topics": {"edges": []},
            "thumbnail": None,
        }
        html = _make_next_data_html([post])
        source = ProductHuntSource()
        items = source._parse_next_data(html)
        assert items[0].comment_count == 42

    def test_metadata_contains_name_and_tagline(self):
        post = {
            "name": "MyProduct",
            "tagline": "Does stuff",
            "votesCount": 7,
            "slug": "myproduct",
            "commentsCount": 3,
            "createdAt": "2026-03-08T00:00:00Z",
            "topics": {"edges": []},
            "thumbnail": None,
        }
        html = _make_next_data_html([post])
        source = ProductHuntSource()
        items = source._parse_next_data(html)
        assert items[0].metadata["name"] == "MyProduct"
        assert items[0].metadata["tagline"] == "Does stuff"


# ---------------------------------------------------------------------------
# ProductHuntSource — _parse_html_cards fallback
# ---------------------------------------------------------------------------


class TestProductHuntParseHtmlCards:
    def test_returns_empty_on_empty_html(self):
        source = ProductHuntSource()
        items = source._parse_html_cards("<html><body></body></html>")
        assert items == []

    def test_returns_empty_on_blank_string(self):
        source = ProductHuntSource()
        items = source._parse_html_cards("")
        assert items == []

    def test_parses_anchor_with_posts_href(self):
        html = '<html><body><a href="/posts/cool-app">Cool App — Does things</a></body></html>'
        source = ProductHuntSource()
        items = source._parse_html_cards(html)
        assert len(items) == 1
        assert "cool-app" in items[0].url
        assert items[0].source == "producthunt"


# ---------------------------------------------------------------------------
# ProductHuntSource — collect integration (mocked network)
# ---------------------------------------------------------------------------


class TestProductHuntCollect:
    @pytest.mark.asyncio
    async def test_collect_returns_list(self):
        post = {
            "name": "TestProduct",
            "tagline": "Does something",
            "votesCount": 99,
            "slug": "testproduct",
            "commentsCount": 5,
            "createdAt": "2026-03-08T00:00:00Z",
            "topics": {"edges": []},
            "thumbnail": None,
        }
        html_content = _make_next_data_html([post])

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_content
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client), \
             patch("ideagen.sources.producthunt.asyncio.sleep", new_callable=AsyncMock):
            source = ProductHuntSource()
            items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0].source == "producthunt"

    @pytest.mark.asyncio
    async def test_collect_respects_limit(self):
        posts = [
            {"name": f"App{i}", "tagline": f"Tag{i}", "votesCount": i,
             "slug": f"app{i}", "commentsCount": 0, "createdAt": "2026-03-08T00:00:00Z",
             "topics": {"edges": []}, "thumbnail": None}
            for i in range(20)
        ]
        html_content = _make_next_data_html(posts)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html_content
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client), \
             patch("ideagen.sources.producthunt.asyncio.sleep", new_callable=AsyncMock):
            source = ProductHuntSource()
            items = await source.collect(Domain.SOFTWARE_SAAS, limit=5)

        assert len(items) <= 5

    @pytest.mark.asyncio
    async def test_collect_returns_empty_on_network_error(self):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Network error")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client):
            source = ProductHuntSource()
            items = await source.collect(Domain.SOFTWARE_SAAS)

        assert items == []

    @pytest.mark.asyncio
    async def test_collect_returns_empty_on_empty_page(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body>No products here</body></html>"
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client), \
             patch("ideagen.sources.producthunt.asyncio.sleep", new_callable=AsyncMock):
            source = ProductHuntSource()
            items = await source.collect(Domain.SOFTWARE_SAAS)

        assert items == []

    @pytest.mark.asyncio
    async def test_collect_all_domains(self):
        """collect() should work for all three domain values."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body></body></html>"
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client), \
             patch("ideagen.sources.producthunt.asyncio.sleep", new_callable=AsyncMock):
            source = ProductHuntSource()
            for domain in Domain:
                items = await source.collect(domain)
                assert isinstance(items, list)


# ---------------------------------------------------------------------------
# TwitterSource — basic attributes
# ---------------------------------------------------------------------------


class TestTwitterSourceAttributes:
    def test_name_returns_twitter(self):
        source = TwitterSource()
        assert source.name == "twitter"

    def test_parser_version(self):
        assert TwitterSource.PARSER_VERSION == "1.0"

    def test_default_scrape_delay(self):
        source = TwitterSource()
        assert source._scrape_delay == 3.0

    def test_custom_scrape_delay(self):
        source = TwitterSource(scrape_delay=1.0)
        assert source._scrape_delay == 1.0

    def test_default_timeout(self):
        source = TwitterSource()
        assert source._timeout == 15.0


# ---------------------------------------------------------------------------
# TwitterSource — domain queries
# ---------------------------------------------------------------------------


class TestDomainQueries:
    def test_all_domains_have_queries(self):
        for domain in Domain:
            assert domain in DOMAIN_QUERIES
            assert len(DOMAIN_QUERIES[domain]) > 0

    def test_software_saas_queries_not_empty(self):
        assert len(DOMAIN_QUERIES[Domain.SOFTWARE_SAAS]) >= 2

    def test_broad_business_queries_not_empty(self):
        assert len(DOMAIN_QUERIES[Domain.BROAD_BUSINESS]) >= 2

    def test_content_media_queries_not_empty(self):
        assert len(DOMAIN_QUERIES[Domain.CONTENT_MEDIA]) >= 2


# ---------------------------------------------------------------------------
# TwitterSource — is_available
# ---------------------------------------------------------------------------


class TestTwitterIsAvailable:
    @pytest.mark.asyncio
    async def test_returns_false_when_neither_library_importable(self):
        with patch.dict("sys.modules", {"snscrape": None, "snscrape.modules": None,
                                         "snscrape.modules.twitter": None,
                                         "ntscraper": None}):
            source = TwitterSource()
            result = await source.is_available()
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_snscrape_importable(self):
        mock_snscrape = MagicMock()
        with patch.dict("sys.modules", {"snscrape": mock_snscrape,
                                         "snscrape.modules": mock_snscrape,
                                         "snscrape.modules.twitter": mock_snscrape}):
            source = TwitterSource()
            result = await source.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_ntscraper_importable(self):
        mock_ntscraper = MagicMock()
        mock_ntscraper.Nitter = MagicMock()
        with patch.dict("sys.modules", {"snscrape": None, "snscrape.modules": None,
                                         "snscrape.modules.twitter": None,
                                         "ntscraper": mock_ntscraper}):
            source = TwitterSource()
            result = await source.is_available()
        assert result is True


# ---------------------------------------------------------------------------
# TwitterSource — collect returns list when libraries unavailable
# ---------------------------------------------------------------------------


class TestTwitterCollect:
    @pytest.mark.asyncio
    async def test_collect_returns_empty_when_no_library(self):
        with patch.dict("sys.modules", {"snscrape": None, "snscrape.modules": None,
                                         "snscrape.modules.twitter": None,
                                         "ntscraper": None}):
            source = TwitterSource()
            items = await source.collect(Domain.SOFTWARE_SAAS)
        assert items == []

    @pytest.mark.asyncio
    async def test_collect_returns_list(self):
        with patch.dict("sys.modules", {"snscrape": None, "snscrape.modules": None,
                                         "snscrape.modules.twitter": None,
                                         "ntscraper": None}):
            source = TwitterSource()
            result = await source.collect(Domain.BROAD_BUSINESS)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_try_snscrape_returns_empty_on_import_error(self):
        with patch.dict("sys.modules", {"snscrape": None, "snscrape.modules": None,
                                         "snscrape.modules.twitter": None}):
            source = TwitterSource()
            items = await source._try_snscrape(Domain.SOFTWARE_SAAS, 10)
        assert items == []

    @pytest.mark.asyncio
    async def test_try_ntscraper_returns_empty_on_import_error(self):
        with patch.dict("sys.modules", {"ntscraper": None}):
            source = TwitterSource()
            items = await source._try_ntscraper(Domain.SOFTWARE_SAAS, 10)
        assert items == []

    @pytest.mark.asyncio
    async def test_collect_with_ntscraper_mock(self):
        mock_nitter = MagicMock()
        mock_nitter.get_tweets.return_value = {
            "tweets": [
                {
                    "text": "I wish there was a better tool for X",
                    "link": "https://twitter.com/user/status/1",
                    "stats": {"likes": "42", "comments": "5"},
                    "user": {"name": "testuser"},
                }
            ]
        }
        mock_ntscraper_module = MagicMock()
        mock_ntscraper_module.Nitter.return_value = mock_nitter

        with patch.dict("sys.modules", {"snscrape": None, "snscrape.modules": None,
                                         "snscrape.modules.twitter": None,
                                         "ntscraper": mock_ntscraper_module}):
            source = TwitterSource()
            items = await source._try_ntscraper(Domain.SOFTWARE_SAAS, 10)

        assert len(items) >= 1
        assert items[0].source == "twitter"
        assert items[0].score == 42
        assert items[0].comment_count == 5

    @pytest.mark.asyncio
    async def test_ntscraper_skips_empty_tweet_text(self):
        mock_nitter = MagicMock()
        mock_nitter.get_tweets.return_value = {
            "tweets": [
                {"text": "", "link": "", "stats": {}, "user": {}},
                {"text": "Real tweet", "link": "https://t.co/x", "stats": {"likes": "1", "comments": "0"}, "user": {"name": "u"}},
            ]
        }
        mock_ntscraper_module = MagicMock()
        mock_ntscraper_module.Nitter.return_value = mock_nitter

        with patch.dict("sys.modules", {"snscrape": None, "snscrape.modules": None,
                                         "snscrape.modules.twitter": None,
                                         "ntscraper": mock_ntscraper_module}):
            source = TwitterSource()
            items = await source._try_ntscraper(Domain.SOFTWARE_SAAS, 10)

        assert all(item.title != "" for item in items)

    @pytest.mark.asyncio
    async def test_collect_respects_limit(self):
        mock_nitter = MagicMock()
        mock_nitter.get_tweets.return_value = {
            "tweets": [
                {
                    "text": f"Tweet {i}",
                    "link": f"https://twitter.com/u/status/{i}",
                    "stats": {"likes": str(i), "comments": "0"},
                    "user": {"name": "u"},
                }
                for i in range(30)
            ]
        }
        mock_ntscraper_module = MagicMock()
        mock_ntscraper_module.Nitter.return_value = mock_nitter

        with patch.dict("sys.modules", {"snscrape": None, "snscrape.modules": None,
                                         "snscrape.modules.twitter": None,
                                         "ntscraper": mock_ntscraper_module}):
            source = TwitterSource()
            items = await source.collect(Domain.SOFTWARE_SAAS, limit=5)

        assert len(items) <= 5
