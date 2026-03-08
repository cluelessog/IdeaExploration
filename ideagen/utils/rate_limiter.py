from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Token bucket rate limiter for async operations."""

    def __init__(self, rate: float = 1.0, burst: int = 1):
        """
        Args:
            rate: Tokens per second
            burst: Maximum tokens in bucket
        """
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available."""
        async with self._lock:
            self._refill()
            while self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait_time)
                self._refill()
            self._tokens -= 1.0

    @property
    def available_tokens(self) -> float:
        self._refill()
        return self._tokens
