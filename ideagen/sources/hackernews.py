from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
import httpx
from ideagen.core.models import TrendingItem, Domain
from ideagen.sources.base import DataSource
from ideagen.utils.retry import with_retry

logger = logging.getLogger("ideagen")

# Domain -> keyword filters for relevance
DOMAIN_KEYWORDS: dict[Domain, list[str]] = {
    Domain.SOFTWARE_SAAS: ["saas", "software", "startup", "api", "developer", "dev", "tool", "app", "platform", "cloud", "ai", "ml", "automation"],
    Domain.BROAD_BUSINESS: ["business", "startup", "market", "revenue", "growth", "sales", "customer", "product", "launch"],
    Domain.CONTENT_MEDIA: ["content", "media", "creator", "video", "podcast", "newsletter", "blog", "social", "audience"],
}

class HackerNewsSource(DataSource):
    PARSER_VERSION = "1.0"
    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "hackernews"

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{self.BASE_URL}/topstories.json")
                return resp.status_code == 200
        except Exception:
            return False

    @with_retry(max_retries=2, base_delay=1.0)
    async def _fetch_story_ids(self, client: httpx.AsyncClient, story_type: str = "topstories") -> list[int]:
        resp = await client.get(f"{self.BASE_URL}/{story_type}.json")
        resp.raise_for_status()
        return resp.json()

    @with_retry(max_retries=2, base_delay=0.5)
    async def _fetch_item(self, client: httpx.AsyncClient, item_id: int) -> dict[str, Any] | None:
        resp = await client.get(f"{self.BASE_URL}/item/{item_id}.json")
        resp.raise_for_status()
        return resp.json()

    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
        keywords = DOMAIN_KEYWORDS.get(domain, [])
        sem = asyncio.Semaphore(10)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            story_ids = await self._fetch_story_ids(client, "topstories")
            fetch_count = min(limit * 3, len(story_ids))

            async def _fetch_one(story_id: int) -> TrendingItem | None:
                async with sem:
                    try:
                        data = await self._fetch_item(client, story_id)
                        if not data or not data.get("title"):
                            return None

                        title = data.get("title", "")
                        url = data.get("url", f"https://news.ycombinator.com/item?id={story_id}")

                        if keywords:
                            title_lower = title.lower()
                            if not any(kw in title_lower for kw in keywords):
                                return None

                        return TrendingItem(
                            title=title,
                            url=url,
                            score=data.get("score", 0),
                            source="hackernews",
                            timestamp=datetime.fromtimestamp(data.get("time", 0), tz=timezone.utc),
                            comment_count=data.get("descendants", 0),
                            metadata={"hn_id": story_id, "type": data.get("type", "story"), "by": data.get("by", "")},
                        )
                    except Exception as e:
                        logger.warning(f"Failed to fetch HN item {story_id}: {e}")
                        return None

            results = await asyncio.gather(*[_fetch_one(sid) for sid in story_ids[:fetch_count]])

        items = [r for r in results if r is not None]
        return items[:limit]
