from __future__ import annotations
import logging
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup
from ideagen.core.models import TrendingItem, Domain
from ideagen.sources.base import DataSource
from ideagen.utils.retry import with_retry

logger = logging.getLogger("ideagen")

DOMAIN_SUBREDDITS: dict[Domain, list[str]] = {
    Domain.SOFTWARE_SAAS: ["SaaS", "startups", "Entrepreneur", "webdev", "programming"],
    Domain.BROAD_BUSINESS: ["smallbusiness", "Entrepreneur", "startups", "business"],
    Domain.CONTENT_MEDIA: ["content_marketing", "NewTubers", "podcasting", "blogging"],
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

class RedditSource(DataSource):
    PARSER_VERSION = "1.0"
    BASE_URL = "https://old.reddit.com"

    def __init__(self, subreddits: list[str] | None = None, scrape_delay: float = 2.0, timeout: float = 15.0):
        self._subreddits = subreddits
        self._scrape_delay = scrape_delay
        self._timeout = timeout
        self._ua_index = 0

    @property
    def name(self) -> str:
        return "reddit"

    def _get_user_agent(self) -> str:
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/r/programming/.json",
                    headers={"User-Agent": self._get_user_agent()},
                    follow_redirects=True,
                )
                return resp.status_code == 200
        except Exception:
            return False

    @with_retry(max_retries=2, base_delay=2.0)
    async def _scrape_subreddit(self, client: httpx.AsyncClient, subreddit: str, limit: int) -> list[TrendingItem]:
        """Scrape a subreddit's hot posts from old.reddit.com."""
        items: list[TrendingItem] = []
        url = f"{self.BASE_URL}/r/{subreddit}/hot/"
        headers = {"User-Agent": self._get_user_agent()}

        resp = await client.get(url, headers=headers, follow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.find_all("div", class_="thing", attrs={"data-fullname": True})

        for post in posts[:limit]:
            try:
                title_el = post.find("a", class_="title")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                post_url = title_el.get("href", "")
                if post_url.startswith("/"):
                    post_url = f"https://www.reddit.com{post_url}"

                score_el = post.find("div", class_="score unvoted")
                score_text = score_el.get("title", "0") if score_el else "0"
                try:
                    score = int(score_text)
                except (ValueError, TypeError):
                    score = 0

                comments_el = post.find("a", class_="comments")
                comment_text = comments_el.get_text(strip=True) if comments_el else "0 comments"
                comment_count = 0
                try:
                    comment_count = int(comment_text.split()[0])
                except (ValueError, IndexError):
                    pass

                time_el = post.find("time")
                timestamp = datetime.now(tz=timezone.utc)
                if time_el and time_el.get("datetime"):
                    try:
                        timestamp = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                flair_el = post.find("span", class_="linkflairlabel")
                flair = flair_el.get_text(strip=True) if flair_el else ""

                item = TrendingItem(
                    title=title,
                    url=post_url,
                    score=score,
                    source="reddit",
                    timestamp=timestamp,
                    comment_count=comment_count,
                    metadata={
                        "subreddit": subreddit,
                        "flair": flair,
                        "fullname": post.get("data-fullname", ""),
                    },
                )
                items.append(item)
            except Exception as e:
                logger.warning(f"Failed to parse Reddit post in r/{subreddit}: {e}")
                continue

        return items

    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]:
        subreddits = self._subreddits or DOMAIN_SUBREDDITS.get(domain, ["startups"])
        all_items: list[TrendingItem] = []
        per_sub_limit = max(limit // len(subreddits), 10)

        import asyncio
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for sub in subreddits:
                try:
                    items = await self._scrape_subreddit(client, sub, per_sub_limit)
                    all_items.extend(items)
                except Exception as e:
                    logger.warning(f"Failed to scrape r/{sub}: {e}")
                    continue
                # Polite delay between subreddits
                if self._scrape_delay > 0:
                    await asyncio.sleep(self._scrape_delay)

        # Sort by score descending and limit
        all_items.sort(key=lambda x: x.score, reverse=True)
        return all_items[:limit]
