from __future__ import annotations

import logging
from datetime import datetime, timezone

from ideagen.core.models import Domain, TrendingItem
from ideagen.sources.base import DataSource
from ideagen.utils.retry import with_retry

logger = logging.getLogger("ideagen")

DOMAIN_QUERIES: dict[Domain, list[str]] = {
    Domain.SOFTWARE_SAAS: ["SaaS pain point", "startup idea", "I wish there was", "developer tool"],
    Domain.BROAD_BUSINESS: ["business idea", "side hustle", "market gap", "customer complaint"],
    Domain.CONTENT_MEDIA: ["content creator struggle", "newsletter idea", "podcast topic", "YouTube niche"],
}


class TwitterSource(DataSource):
    PARSER_VERSION = "1.0"

    def __init__(self, scrape_delay: float = 3.0, timeout: float = 15.0):
        self._scrape_delay = scrape_delay
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "twitter"

    async def is_available(self) -> bool:
        """Check if snscrape or ntscraper is importable."""
        try:
            import snscrape.modules.twitter  # noqa: F401
            return True
        except ImportError:
            pass
        try:
            from ntscraper import Nitter  # noqa: F401
            return True
        except ImportError:
            pass
        return False

    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
        """Try snscrape first, fall back to ntscraper."""
        items = await self._try_snscrape(domain, limit)
        if not items:
            items = await self._try_ntscraper(domain, limit)
        if not items:
            logger.warning("Twitter: both snscrape and ntscraper unavailable or returned no results")
        return items

    async def _try_snscrape(self, domain: Domain, limit: int) -> list[TrendingItem]:
        try:
            import snscrape.modules.twitter as sntwitter
        except ImportError:
            return []

        items: list[TrendingItem] = []
        queries = DOMAIN_QUERIES.get(domain, ["startup idea"])
        per_query = max(limit // len(queries), 5)

        for query in queries:
            try:
                scraper = sntwitter.TwitterSearchScraper(f"{query} lang:en")
                count = 0
                for tweet in scraper.get_items():
                    if count >= per_query:
                        break
                    item = TrendingItem(
                        title=tweet.rawContent[:280] if hasattr(tweet, "rawContent") else str(tweet),
                        url=tweet.url if hasattr(tweet, "url") else "",
                        score=getattr(tweet, "likeCount", 0) or 0,
                        source="twitter",
                        timestamp=getattr(tweet, "date", datetime.now(tz=timezone.utc)),
                        comment_count=getattr(tweet, "replyCount", 0) or 0,
                        metadata={
                            "author": getattr(tweet, "user", {}).username
                            if hasattr(getattr(tweet, "user", None), "username")
                            else "",
                            "retweets": getattr(tweet, "retweetCount", 0) or 0,
                            "query": query,
                        },
                    )
                    items.append(item)
                    count += 1
            except Exception as e:
                logger.warning(f"snscrape failed for query '{query}': {e}")
                continue

        return items[:limit]

    async def _try_ntscraper(self, domain: Domain, limit: int) -> list[TrendingItem]:
        try:
            from ntscraper import Nitter
        except ImportError:
            return []

        items: list[TrendingItem] = []
        queries = DOMAIN_QUERIES.get(domain, ["startup idea"])

        try:
            scraper = Nitter()
            for query in queries[:2]:  # Limit queries for ntscraper
                try:
                    tweets = scraper.get_tweets(query, mode="term", number=min(limit, 20))
                    for tweet_data in tweets.get("tweets", []):
                        text = tweet_data.get("text", "")
                        if not text:
                            continue
                        stats = tweet_data.get("stats") or {}
                        likes_raw = stats.get("likes", "0") if stats else "0"
                        comments_raw = stats.get("comments", "0") if stats else "0"
                        item = TrendingItem(
                            title=text[:280],
                            url=tweet_data.get("link", ""),
                            score=int(str(likes_raw).replace(",", "")) if likes_raw else 0,
                            source="twitter",
                            timestamp=datetime.now(tz=timezone.utc),
                            comment_count=int(str(comments_raw).replace(",", "")) if comments_raw else 0,
                            metadata={
                                "author": (tweet_data.get("user") or {}).get("name", ""),
                                "query": query,
                            },
                        )
                        items.append(item)
                except Exception as e:
                    logger.warning(f"ntscraper failed for query '{query}': {e}")
                    continue
        except Exception as e:
            logger.warning(f"ntscraper initialization failed: {e}")

        return items[:limit]
