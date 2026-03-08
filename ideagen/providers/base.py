from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        user_prompt: str,
        response_type: type[T],
        system_prompt: str | None = None,
    ) -> T: ...
