from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from ideagen.core.models import RunResult, IdeaReport, TrendingItem


class StorageBackend(ABC):
    @abstractmethod
    async def save_run(self, result: RunResult) -> str: ...

    @abstractmethod
    async def get_runs(self, offset: int = 0, limit: int = 20, **filters: Any) -> list[dict]: ...

    @abstractmethod
    async def get_idea(self, idea_id: str) -> IdeaReport | None: ...

    @abstractmethod
    async def search_ideas(self, query: str, offset: int = 0, limit: int = 50) -> list[IdeaReport]: ...

    @abstractmethod
    async def get_run_detail(self, run_id_prefix: str) -> dict | None: ...

    @abstractmethod
    async def save_scrape_cache(self, batch_id: str, source: str, items: list) -> None: ...

    @abstractmethod
    async def load_latest_scrape_cache(self) -> list: ...

    @abstractmethod
    async def find_runs_by_content_hash(self, content_hash: str, exclude_id: str | None = None) -> list[dict]: ...

    @abstractmethod
    async def find_runs_by_prefix(self, prefix: str) -> list[dict]: ...
