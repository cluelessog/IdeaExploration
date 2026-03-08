"""Tests for ideagen.sources.reddit — Reddit collector via old.reddit.com scraping."""
from __future__ import annotations

import pytest
import respx
import httpx

from ideagen.core.models import Domain, TrendingItem
from ideagen.sources.reddit import RedditSource, DOMAIN_SUBREDDITS


# ---------------------------------------------------------------------------
# HTML fixture helpers
# ---------------------------------------------------------------------------

def _make_post_html(
    fullname: str,
    title: str,
    post_url: str,
    score: int = 100,
    comments: int = 25,
    dt: str = "2024-01-15T10:00:00+00:00",
    flair: str = "",
) -> str:
    flair_html = f'<span class="linkflairlabel">{flair}</span>' if flair else ""
    return f"""
    <div class="thing" data-fullname="{fullname}">
        <a class="title" href="{post_url}">{title}</a>
        <div class="score unvoted" title="{score}"></div>
        <a class="comments">{comments} comments</a>
        <time datetime="{dt}"></time>
        {flair_html}
    </div>
    """


def _make_listing_html(*posts: str) -> str:
    body = "\n".join(posts)
    return f"<html><body><div id='siteTable'>{body}</div></body></html>"


REDDIT_BASE = "https://old.reddit.com"


# ---------------------------------------------------------------------------
# Class-level metadata
# ---------------------------------------------------------------------------


class TestRedditMetadata:
    def test_parser_version_is_1_0(self):
        assert RedditSource.PARSER_VERSION == "1.0"

    def test_name_property_is_reddit(self):
        source = RedditSource()
        assert source.name == "reddit"

    def test_is_datasource_subclass(self):
        from ideagen.sources.base import DataSource
        assert isinstance(RedditSource(), DataSource)


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_true_on_200(self):
        respx.get(f"{REDDIT_BASE}/r/programming/.json").mock(
            return_value=httpx.Response(200, json={"kind": "Listing"})
        )
        source = RedditSource()
        assert await source.is_available() is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_false_on_429(self):
        respx.get(f"{REDDIT_BASE}/r/programming/.json").mock(
            return_value=httpx.Response(429)
        )
        source = RedditSource()
        assert await source.is_available() is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_false_on_network_error(self):
        respx.get(f"{REDDIT_BASE}/r/programming/.json").mock(
            side_effect=httpx.ConnectError("refused")
        )
        source = RedditSource()
        assert await source.is_available() is False


# ---------------------------------------------------------------------------
# HTML parsing — _scrape_subreddit
# ---------------------------------------------------------------------------


class TestHTMLParsing:
    @pytest.mark.asyncio
    @respx.mock
    async def test_parses_title_and_url(self):
        html = _make_listing_html(
            _make_post_html("t3_abc1", "How I built a SaaS in a weekend", "https://example.com/post1", score=200)
        )
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        assert len(items) == 1
        assert items[0].title == "How I built a SaaS in a weekend"
        assert items[0].url == "https://example.com/post1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_parses_score(self):
        html = _make_listing_html(
            _make_post_html("t3_abc2", "Some startup post", "/r/startups/comments/abc2", score=999)
        )
        respx.get(f"{REDDIT_BASE}/r/startups/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["startups"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "startups", limit=10)

        assert items[0].score == 999

    @pytest.mark.asyncio
    @respx.mock
    async def test_parses_comment_count(self):
        html = _make_listing_html(
            _make_post_html("t3_abc3", "SaaS idea discussion", "https://example.com/p3", comments=42)
        )
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        assert items[0].comment_count == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_parses_timestamp(self):
        html = _make_listing_html(
            _make_post_html("t3_abc4", "SaaS launch post", "https://example.com/p4", dt="2024-03-01T12:00:00+00:00")
        )
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        from datetime import datetime, timezone
        assert items[0].timestamp == datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    @respx.mock
    async def test_parses_flair(self):
        html = _make_listing_html(
            _make_post_html("t3_abc5", "Show and tell post", "https://example.com/p5", flair="Show HN")
        )
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        assert items[0].metadata["flair"] == "Show HN"

    @pytest.mark.asyncio
    @respx.mock
    async def test_prepends_reddit_domain_to_relative_urls(self):
        html = _make_listing_html(
            _make_post_html("t3_abc6", "Relative URL post", "/r/SaaS/comments/abc6/title/")
        )
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        assert items[0].url.startswith("https://www.reddit.com")

    @pytest.mark.asyncio
    @respx.mock
    async def test_stores_fullname_in_metadata(self):
        html = _make_listing_html(
            _make_post_html("t3_xyz99", "SaaS product launch", "https://example.com/p99")
        )
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        assert items[0].metadata["fullname"] == "t3_xyz99"
        assert items[0].metadata["subreddit"] == "SaaS"

    @pytest.mark.asyncio
    @respx.mock
    async def test_source_field_is_reddit(self):
        html = _make_listing_html(
            _make_post_html("t3_src1", "Startup story", "https://example.com/src1")
        )
        respx.get(f"{REDDIT_BASE}/r/startups/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["startups"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "startups", limit=10)

        assert items[0].source == "reddit"


# ---------------------------------------------------------------------------
# Malformed HTML handling
# ---------------------------------------------------------------------------


class TestMalformedHTML:
    @pytest.mark.asyncio
    @respx.mock
    async def test_skips_posts_without_title_element(self):
        # A "thing" div with no .title anchor
        malformed = '<div class="thing" data-fullname="t3_bad1"><div class="score unvoted" title="10"></div></div>'
        good = _make_post_html("t3_good1", "Valid startup post", "https://example.com/good1")
        html = _make_listing_html(malformed, good)

        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        assert len(items) == 1
        assert items[0].metadata["fullname"] == "t3_good1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_empty_html_page(self):
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text="<html><body></body></html>")
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        assert items == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_non_numeric_score_gracefully(self):
        # score title is non-numeric ("•" is what reddit shows when score is hidden)
        post_html = """
        <div class="thing" data-fullname="t3_ns1">
            <a class="title" href="https://example.com/ns1">SaaS launch announcement</a>
            <div class="score unvoted" title="•"></div>
            <a class="comments">5 comments</a>
        </div>
        """
        html = _make_listing_html(post_html)
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        assert len(items) == 1
        assert items[0].score == 0  # default on parse failure

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_malformed_timestamp_gracefully(self):
        post_html = """
        <div class="thing" data-fullname="t3_ts1">
            <a class="title" href="https://example.com/ts1">Startup saas post</a>
            <div class="score unvoted" title="50"></div>
            <a class="comments">3 comments</a>
            <time datetime="not-a-valid-date"></time>
        </div>
        """
        html = _make_listing_html(post_html)
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["SaaS"], scrape_delay=0)
        async with httpx.AsyncClient() as client:
            items = await source._scrape_subreddit(client, "SaaS", limit=10)

        # Should still return item with a fallback timestamp (datetime.now)
        assert len(items) == 1
        assert items[0].timestamp is not None


# ---------------------------------------------------------------------------
# collect — full pipeline
# ---------------------------------------------------------------------------


class TestCollect:
    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_returns_trending_items(self):
        html = _make_listing_html(
            _make_post_html("t3_c1", "We launched a SaaS", "https://example.com/c1", score=500),
            _make_post_html("t3_c2", "Startup growth story", "https://example.com/c2", score=300),
        )
        # SOFTWARE_SAAS domain uses ["SaaS", "startups", "Entrepreneur", "webdev", "programming"]
        for sub in ["SaaS", "startups", "Entrepreneur", "webdev", "programming"]:
            respx.get(f"{REDDIT_BASE}/r/{sub}/hot/").mock(
                return_value=httpx.Response(200, text=html)
            )

        source = RedditSource(scrape_delay=0)
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=20)

        assert len(items) > 0
        for item in items:
            assert isinstance(item, TrendingItem)
            assert item.source == "reddit"

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_sorts_by_score_descending(self):
        html_saas = _make_listing_html(
            _make_post_html("t3_s1", "Low score post", "https://example.com/s1", score=10),
        )
        html_startups = _make_listing_html(
            _make_post_html("t3_s2", "High score post", "https://example.com/s2", score=9999),
        )
        respx.get(f"{REDDIT_BASE}/r/SaaS/hot/").mock(return_value=httpx.Response(200, text=html_saas))
        respx.get(f"{REDDIT_BASE}/r/startups/hot/").mock(return_value=httpx.Response(200, text=html_startups))
        respx.get(f"{REDDIT_BASE}/r/Entrepreneur/hot/").mock(return_value=httpx.Response(200, text="<html></html>"))
        respx.get(f"{REDDIT_BASE}/r/webdev/hot/").mock(return_value=httpx.Response(200, text="<html></html>"))
        respx.get(f"{REDDIT_BASE}/r/programming/hot/").mock(return_value=httpx.Response(200, text="<html></html>"))

        source = RedditSource(scrape_delay=0)
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=50)

        assert len(items) >= 2
        scores = [item.score for item in items]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_respects_limit(self):
        # Each subreddit returns 5 posts; with 5 subs that's 25 total; limit=5
        posts = [
            _make_post_html(f"t3_lim{i}", f"Post number {i}", f"https://example.com/lim{i}", score=100 - i)
            for i in range(5)
        ]
        html = _make_listing_html(*posts)

        for sub in ["SaaS", "startups", "Entrepreneur", "webdev", "programming"]:
            respx.get(f"{REDDIT_BASE}/r/{sub}/hot/").mock(
                return_value=httpx.Response(200, text=html)
            )

        source = RedditSource(scrape_delay=0)
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=5)

        assert len(items) <= 5

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_uses_custom_subreddits(self):
        html = _make_listing_html(
            _make_post_html("t3_cust1", "Custom subreddit post", "https://example.com/cust1", score=100)
        )
        respx.get(f"{REDDIT_BASE}/r/mycustom/hot/").mock(
            return_value=httpx.Response(200, text=html)
        )

        source = RedditSource(subreddits=["mycustom"], scrape_delay=0)
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert len(items) == 1
        assert items[0].metadata["subreddit"] == "mycustom"

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_continues_when_one_subreddit_fails(self, monkeypatch):
        import asyncio

        async def _noop_sleep(_delay: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

        html_good = _make_listing_html(
            _make_post_html("t3_ok1", "Good subreddit post", "https://example.com/ok1", score=200)
        )
        respx.get(f"{REDDIT_BASE}/r/failsub/hot/").mock(
            return_value=httpx.Response(503)
        )
        respx.get(f"{REDDIT_BASE}/r/goodsub/hot/").mock(
            return_value=httpx.Response(200, text=html_good)
        )

        source = RedditSource(subreddits=["failsub", "goodsub"], scrape_delay=0)
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert len(items) == 1
        assert items[0].metadata["subreddit"] == "goodsub"

    @pytest.mark.asyncio
    @respx.mock
    async def test_collect_returns_empty_list_when_all_subreddits_fail(self, monkeypatch):
        import asyncio

        async def _noop_sleep(_delay: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

        respx.get(f"{REDDIT_BASE}/r/sub1/hot/").mock(return_value=httpx.Response(503))
        respx.get(f"{REDDIT_BASE}/r/sub2/hot/").mock(return_value=httpx.Response(503))

        source = RedditSource(subreddits=["sub1", "sub2"], scrape_delay=0)
        items = await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert items == []


# ---------------------------------------------------------------------------
# Polite scrape delay
# ---------------------------------------------------------------------------


class TestScrapeDelay:
    @pytest.mark.asyncio
    @respx.mock
    async def test_delay_called_between_subreddits(self, monkeypatch):
        sleep_calls: list[float] = []

        import asyncio

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        html = _make_listing_html(
            _make_post_html("t3_d1", "Delayed post", "https://example.com/d1")
        )
        respx.get(f"{REDDIT_BASE}/r/sub_a/hot/").mock(return_value=httpx.Response(200, text=html))
        respx.get(f"{REDDIT_BASE}/r/sub_b/hot/").mock(return_value=httpx.Response(200, text=html))

        source = RedditSource(subreddits=["sub_a", "sub_b"], scrape_delay=1.5)
        await source.collect(Domain.SOFTWARE_SAAS, limit=20)

        # sleep should have been called twice (once after each subreddit including the last)
        assert len(sleep_calls) == 2
        assert all(d == 1.5 for d in sleep_calls)

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_delay_when_scrape_delay_is_zero(self, monkeypatch):
        sleep_calls: list[float] = []

        import asyncio

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        html = _make_listing_html(
            _make_post_html("t3_nd1", "No delay post", "https://example.com/nd1")
        )
        respx.get(f"{REDDIT_BASE}/r/subx/hot/").mock(return_value=httpx.Response(200, text=html))

        source = RedditSource(subreddits=["subx"], scrape_delay=0)
        await source.collect(Domain.SOFTWARE_SAAS, limit=10)

        assert sleep_calls == []


# ---------------------------------------------------------------------------
# DOMAIN_SUBREDDITS coverage
# ---------------------------------------------------------------------------


class TestDomainSubreddits:
    def test_covers_all_domains(self):
        for domain in Domain:
            assert domain in DOMAIN_SUBREDDITS
            assert len(DOMAIN_SUBREDDITS[domain]) > 0

    def test_software_saas_includes_saas(self):
        assert "SaaS" in DOMAIN_SUBREDDITS[Domain.SOFTWARE_SAAS]

    def test_broad_business_includes_entrepreneur(self):
        assert "Entrepreneur" in DOMAIN_SUBREDDITS[Domain.BROAD_BUSINESS]

    def test_content_media_includes_podcasting(self):
        assert "podcasting" in DOMAIN_SUBREDDITS[Domain.CONTENT_MEDIA]
