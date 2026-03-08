from __future__ import annotations
from abc import ABC, abstractmethod
from ideagen.core.models import TrendingItem, Domain


class DataSource(ABC):
    PARSER_VERSION: str = "1.0"

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def collect(self, domain: Domain, limit: int = 50) -> list[TrendingItem]: ...

    @abstractmethod
    async def is_available(self) -> bool: ...
