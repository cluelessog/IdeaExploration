from __future__ import annotations
import asyncio
import functools
import logging
import random
from typing import Any, Callable, TypeVar

logger = logging.getLogger("ideagen")
F = TypeVar("F", bound=Callable[..., Any])


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__} after {delay:.1f}s: {e}")
                        await asyncio.sleep(delay)
            raise last_exception  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator
