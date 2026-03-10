"""Tests for ProductHuntSource and TwitterSource."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ideagen.core.models import Domain, TrendingItem
from ideagen.sources.producthunt import ProductHuntSource
from ideagen.sources.twitter import TwitterSource, DOMAIN_QUERIES


# ---------------------------------------------------------------------------
# Helper: build Atom feed XML
# ---------------------------------------------------------------------------

def _make_feed_xml(entries: list[dict]) -> str:
    """Build minimal Atom feed XML with product entries."""
    items_xml = ""
    for e in entries:
        title = e.get("title", "")
        href = e.get("href", "https://www.producthunt.com")
        published = e.get("published", "2026-03-08T00:00:00-08:00")
        tagline = e.get("tagline", "")
        post_id = e.get("post_id", "12345")
        author = e.get("author", "Test Author")
        content_html = f"&lt;p&gt;{tagline}&lt;/p&gt;" if tagline else ""
        items_xml += f"""
  <entry>
    <id>tag:www.producthunt.com,2005:Post/{post_id}</id>
    <published>{published}</published>
    <updated>{published}</updated>
    <link rel="alternate" type="text/html" href="{href}"/>
    <title>{title}</title>
    <content type="html">{content_html}</content>
    <author><name>{author}</name></author>
  </entry>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US" xmlns="http://www.w3.org/2005/Atom">
  <id>tag:www.producthunt.com,2005:/feed</id>
  <title>Product Hunt</title>
  <updated>2026-03-08T00:01:00-08:00</updated>{items_xml}
</feed>"""


# ---------------------------------------------------------------------------
# ProductHuntSource — basic attributes
# ---------------------------------------------------------------------------


class TestProductHuntSourceAttributes:
    def test_name_returns_producthunt(self):
        source = ProductHuntSource()
        assert source.name == "producthunt"

    def test_parser_version(self):
        assert ProductHuntSource.PARSER_VERSION == "2.0"

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
# ProductHuntSource — _parse_feed
# ---------------------------------------------------------------------------


class TestProductHuntParseFeed:
    def test_parses_single_product(self):
        xml = _make_feed_xml([{
            "title": "SuperApp",
            "tagline": "The best app ever",
            "href": "https://www.producthunt.com/products/superapp",
            "post_id": "100",
            "author": "Jane Doe",
        }])
        source = ProductHuntSource()
        items = source._parse_feed(xml)
        assert len(items) == 1
        assert items[0].title == "SuperApp — The best app ever"
        assert items[0].source == "producthunt"
        assert items[0].url == "https://www.producthunt.com/products/superapp"
        assert items[0].metadata["name"] == "SuperApp"
        assert items[0].metadata["tagline"] == "The best app ever"
        assert items[0].metadata["post_id"] == "100"
        assert items[0].metadata["author"] == "Jane Doe"

    def test_title_without_tagline(self):
        xml = _make_feed_xml([{
            "title": "MinimalApp",
            "tagline": "",
            "href": "https://www.producthunt.com/products/minimal",
        }])
        source = ProductHuntSource()
        items = source._parse_feed(xml)
        assert len(items) == 1
        assert items[0].title == "MinimalApp"

    def test_parses_multiple_products(self):
        entries = [{"title": f"App{i}", "tagline": f"Tag{i}", "post_id": str(i)} for i in range(5)]
        xml = _make_feed_xml(entries)
        source = ProductHuntSource()
        items = source._parse_feed(xml)
        assert len(items) == 5

    def test_returns_empty_on_empty_feed(self):
        xml = _make_feed_xml([])
        source = ProductHuntSource()
        items = source._parse_feed(xml)
        assert items == []

    def test_returns_empty_on_malformed_xml(self):
        source = ProductHuntSource()
        items = source._parse_feed("<broken>xml<<<<")
        assert items == []

    def test_skips_entries_without_title(self):
        xml = _make_feed_xml([{"title": "", "tagline": "No title"}])
        source = ProductHuntSource()
        items = source._parse_feed(xml)
        assert items == []

    def test_timestamp_parsed_correctly(self):
        xml = _make_feed_xml([{
            "title": "App",
            "published": "2026-03-08T12:34:56-08:00",
        }])
        source = ProductHuntSource()
        items = source._parse_feed(xml)
        assert len(items) == 1
        assert items[0].timestamp.year == 2026
        assert items[0].timestamp.month == 3
        assert items[0].timestamp.day == 8

    def test_score_is_zero_from_feed(self):
        xml = _make_feed_xml([{"title": "App"}])
        source = ProductHuntSource()
        items = source._parse_feed(xml)
        assert items[0].score == 0


# ---------------------------------------------------------------------------
# ProductHuntSource — collect (mocked network)
# ---------------------------------------------------------------------------


class TestProductHuntCollect:
    @pytest.mark.asyncio
    async def test_collect_returns_list(self):
        xml = _make_feed_xml([{"title": "TestProduct", "tagline": "Does something"}])

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client):
            source = ProductHuntSource()
            items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0].source == "producthunt"

    @pytest.mark.asyncio
    async def test_collect_respects_limit(self):
        entries = [{"title": f"App{i}", "tagline": f"Tag{i}"} for i in range(20)]
        xml = _make_feed_xml(entries)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client):
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
    async def test_collect_returns_empty_on_empty_feed(self):
        xml = _make_feed_xml([])

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client):
            source = ProductHuntSource()
            items = await source.collect(Domain.SOFTWARE_SAAS)

        assert items == []

    @pytest.mark.asyncio
    async def test_collect_all_domains(self):
        xml = _make_feed_xml([{"title": "App"}])

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = xml
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("ideagen.sources.producthunt.httpx.AsyncClient", return_value=mock_client):
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
        assert TwitterSource.PARSER_VERSION == "1.1"

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
# TwitterSource — collect
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
