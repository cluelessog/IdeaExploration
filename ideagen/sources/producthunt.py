from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ideagen.core.models import Domain, TrendingItem
from ideagen.sources.base import DataSource
from ideagen.utils.retry import with_retry

logger = logging.getLogger("ideagen")

BASE_URL = "https://www.producthunt.com"
_RATE_LIMIT_DELAY = 3.0


class ProductHuntSource(DataSource):
    PARSER_VERSION = "1.0"

    def __init__(self, scrape_delay: float = _RATE_LIMIT_DELAY, timeout: float = 15.0):
        self._scrape_delay = scrape_delay
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "producthunt"

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(BASE_URL, follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False

    @with_retry(max_retries=2, base_delay=2.0)
    async def _fetch_homepage(self, client: httpx.AsyncClient) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        resp = await client.get(BASE_URL, headers=headers, follow_redirects=True)
        resp.raise_for_status()
        return resp.text

    def _parse_json_ld(self, html: str) -> list[dict[str, Any]]:
        """Extract structured data from <script type='application/ld+json'> tags."""
        products: list[dict[str, Any]] = []
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") in ("Product", "SoftwareApplication"):
                            products.append(item)
                elif isinstance(data, dict) and data.get("@type") in ("Product", "SoftwareApplication"):
                    products.append(data)
            except (json.JSONDecodeError, TypeError):
                continue
        return products

    def _parse_next_data(self, html: str) -> list[TrendingItem]:
        """Extract products from Next.js __NEXT_DATA__ script tag."""
        items: list[TrendingItem] = []
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if not match:
            return items

        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            return items

        # Navigate nested Next.js data structure looking for posts/products
        posts = self._extract_posts_from_next_data(data)
        for post in posts:
            item = self._post_to_trending_item(post)
            if item:
                items.append(item)
        return items

    def _extract_posts_from_next_data(self, data: Any) -> list[dict[str, Any]]:
        """Recursively search Next.js data for product post objects."""
        posts: list[dict[str, Any]] = []
        if isinstance(data, dict):
            # Look for typical PH post structure
            if "name" in data and "tagline" in data and "votesCount" in data:
                posts.append(data)
                return posts
            for value in data.values():
                posts.extend(self._extract_posts_from_next_data(value))
        elif isinstance(data, list):
            for item in data:
                posts.extend(self._extract_posts_from_next_data(item))
        return posts

    def _post_to_trending_item(self, post: dict[str, Any]) -> TrendingItem | None:
        name = post.get("name", "").strip()
        tagline = post.get("tagline", "").strip()
        if not name:
            return None

        title = f"{name} — {tagline}" if tagline else name
        slug = post.get("slug", "")
        url = f"{BASE_URL}/posts/{slug}" if slug else BASE_URL
        votes = post.get("votesCount", 0) or 0

        topics = [t.get("name", "") for t in (post.get("topics", {}).get("edges", []) or []) if isinstance(t, dict)]
        topic_nodes = [e.get("node", e) for e in topics] if topics and isinstance(topics[0], dict) else topics
        tags = [t for t in topic_nodes if isinstance(t, str) and t]

        created_at_str = post.get("createdAt") or post.get("featuredAt", "")
        try:
            timestamp = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")) if created_at_str else datetime.now(tz=timezone.utc)
        except (ValueError, AttributeError):
            timestamp = datetime.now(tz=timezone.utc)

        return TrendingItem(
            title=title,
            url=url,
            score=int(votes),
            source="producthunt",
            timestamp=timestamp,
            comment_count=post.get("commentsCount", 0) or 0,
            metadata={
                "name": name,
                "tagline": tagline,
                "topics": tags,
                "thumbnail": (post.get("thumbnail") or {}).get("url", "") if isinstance(post.get("thumbnail"), dict) else "",
            },
        )

    def _parse_html_cards(self, html: str) -> list[TrendingItem]:
        """Fallback: parse product cards from HTML structure."""
        items: list[TrendingItem] = []
        soup = BeautifulSoup(html, "html.parser")

        # PH uses data-test attributes on product items
        cards = soup.find_all("div", attrs={"data-test": re.compile(r"post-item")})
        if not cards:
            # Try class-based fallback — PH uses hashed classnames, so look for anchor tags with /posts/
            cards = soup.find_all("a", href=re.compile(r"^/posts/"))

        for card in cards:
            try:
                if card.name == "a":
                    href = card.get("href", "")
                    text = card.get_text(separator=" ", strip=True)
                    if not text:
                        continue
                    items.append(TrendingItem(
                        title=text[:280],
                        url=f"{BASE_URL}{href}",
                        score=0,
                        source="producthunt",
                        timestamp=datetime.now(tz=timezone.utc),
                        metadata={},
                    ))
                else:
                    name_el = card.find(attrs={"data-test": "post-name"}) or card.find("h3") or card.find("h2")
                    name = name_el.get_text(strip=True) if name_el else ""
                    if not name:
                        continue
                    tagline_el = card.find(attrs={"data-test": "post-tagline"}) or card.find("p")
                    tagline = tagline_el.get_text(strip=True) if tagline_el else ""
                    title = f"{name} — {tagline}" if tagline else name

                    link_el = card.find("a", href=re.compile(r"^/posts/"))
                    url = f"{BASE_URL}{link_el['href']}" if link_el else BASE_URL

                    vote_el = card.find(attrs={"data-test": re.compile(r"vote")})
                    score = 0
                    if vote_el:
                        vote_text = re.sub(r"[^\d]", "", vote_el.get_text())
                        score = int(vote_text) if vote_text else 0

                    items.append(TrendingItem(
                        title=title,
                        url=url,
                        score=score,
                        source="producthunt",
                        timestamp=datetime.now(tz=timezone.utc),
                        metadata={"tagline": tagline},
                    ))
            except Exception as e:
                logger.debug(f"ProductHunt card parse error: {e}")
                continue

        return items

    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
        items: list[TrendingItem] = []

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                html = await self._fetch_homepage(client)
                await asyncio.sleep(self._scrape_delay)

                # Try Next.js data first (most structured)
                items = self._parse_next_data(html)

                # Fall back to HTML card parsing if Next.js data yielded nothing
                if not items:
                    logger.debug("ProductHunt: __NEXT_DATA__ parse yielded nothing, trying HTML cards")
                    items = self._parse_html_cards(html)

                if not items:
                    logger.warning("ProductHunt: no products found — page structure may have changed")

        except httpx.HTTPStatusError as e:
            logger.warning(f"ProductHunt HTTP error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.warning(f"ProductHunt request error: {e}")
        except Exception as e:
            logger.warning(f"ProductHunt collect error: {e}")

        return items[:limit]
