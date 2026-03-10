from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from xml.etree import ElementTree

import httpx

from ideagen.core.models import Domain, TrendingItem
from ideagen.sources.base import DataSource
from ideagen.utils.retry import with_retry

logger = logging.getLogger("ideagen")

FEED_URL = "https://www.producthunt.com/feed"
BASE_URL = "https://www.producthunt.com"
ATOM_NS = "http://www.w3.org/2005/Atom"


class ProductHuntSource(DataSource):
    PARSER_VERSION = "2.0"

    def __init__(self, timeout: float = 15.0):
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "producthunt"

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(FEED_URL, follow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False

    @with_retry(max_retries=2, base_delay=2.0)
    async def _fetch_feed(self, client: httpx.AsyncClient) -> str:
        resp = await client.get(FEED_URL, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; IdeaGen/0.1)",
            "Accept": "application/atom+xml, application/xml, text/xml",
        })
        resp.raise_for_status()
        return resp.text

    def _parse_feed(self, xml_text: str) -> list[TrendingItem]:
        """Parse Atom feed XML into TrendingItems."""
        items: list[TrendingItem] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"ProductHunt feed parse error: {e}")
            return items

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            try:
                title_el = entry.find(f"{{{ATOM_NS}}}title")
                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                if not title:
                    continue

                link_el = entry.find(f"{{{ATOM_NS}}}link")
                url = link_el.get("href", BASE_URL) if link_el is not None else BASE_URL

                # Extract tagline from content HTML
                content_el = entry.find(f"{{{ATOM_NS}}}content")
                tagline = ""
                if content_el is not None and content_el.text:
                    # Content is HTML like <p>tagline</p><p>links</p>
                    # Extract first <p> text
                    p_match = re.search(r"<p>\s*(.*?)\s*</p>", content_el.text)
                    if p_match:
                        tagline = re.sub(r"<[^>]+>", "", p_match.group(1)).strip()

                display_title = f"{title} — {tagline}" if tagline else title

                # Parse timestamp
                published_el = entry.find(f"{{{ATOM_NS}}}published")
                timestamp = datetime.now(tz=timezone.utc)
                if published_el is not None and published_el.text:
                    try:
                        timestamp = datetime.fromisoformat(published_el.text)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

                # Extract PH post ID from entry id tag
                id_el = entry.find(f"{{{ATOM_NS}}}id")
                post_id = ""
                if id_el is not None and id_el.text:
                    id_match = re.search(r"Post/(\d+)", id_el.text)
                    post_id = id_match.group(1) if id_match else ""

                author_el = entry.find(f"{{{ATOM_NS}}}author/{{{ATOM_NS}}}name")
                author = author_el.text.strip() if author_el is not None and author_el.text else ""

                items.append(TrendingItem(
                    title=display_title,
                    url=url,
                    score=0,  # Feed doesn't include vote counts
                    source="producthunt",
                    timestamp=timestamp,
                    comment_count=0,
                    metadata={
                        "name": title,
                        "tagline": tagline,
                        "post_id": post_id,
                        "author": author,
                    },
                ))
            except Exception as e:
                logger.debug(f"ProductHunt entry parse error: {e}")
                continue

        return items

    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
        items: list[TrendingItem] = []

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                xml_text = await self._fetch_feed(client)
                items = self._parse_feed(xml_text)

                if not items:
                    logger.warning("ProductHunt: no products found in feed")

        except httpx.HTTPStatusError as e:
            logger.warning(f"ProductHunt HTTP error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.warning(f"ProductHunt request error: {e}")
        except Exception as e:
            logger.warning(f"ProductHunt collect error: {e}")

        return items[:limit]
