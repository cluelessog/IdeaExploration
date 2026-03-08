from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from ideagen.core.models import RunResult, IdeaReport


class StorageBackend(ABC):
    @abstractmethod
    async def save_run(self, result: RunResult) -> str: ...

    @abstractmethod
    async def get_runs(self, offset: int = 0, limit: int = 20, **filters: Any) -> list[dict]: ...

    @abstractmethod
    async def get_idea(self, idea_id: str) -> IdeaReport | None: ...

    @abstractmethod
    async def search_ideas(self, query: str, offset: int = 0, limit: int = 50) -> list[IdeaReport]: ...
