"""Tests for ideagen.utils.rate_limiter.RateLimiter."""
from __future__ import annotations

import asyncio
import time

import pytest

from ideagen.utils.rate_limiter import RateLimiter


# ---------------------------------------------------------------------------
# Constructor and initial state
# ---------------------------------------------------------------------------


class TestRateLimiterInit:
    def test_default_rate(self):
        rl = RateLimiter()
        assert rl._rate == 1.0

    def test_default_burst(self):
        rl = RateLimiter()
        assert rl._burst == 1

    def test_custom_rate(self):
        rl = RateLimiter(rate=5.0)
        assert rl._rate == 5.0

    def test_custom_burst(self):
        rl = RateLimiter(burst=10)
        assert rl._burst == 10

    def test_initial_tokens_equal_burst(self):
        rl = RateLimiter(burst=3)
        assert rl._tokens == 3.0

    def test_available_tokens_starts_at_burst(self):
        rl = RateLimiter(burst=5)
        assert rl.available_tokens >= 4.9  # slight tolerance for elapsed time


# ---------------------------------------------------------------------------
# available_tokens property
# ---------------------------------------------------------------------------


class TestAvailableTokens:
    def test_does_not_exceed_burst(self):
        rl = RateLimiter(rate=100.0, burst=3)
        # Even after waiting, tokens should be capped at burst
        assert rl.available_tokens <= 3.0

    def test_never_negative(self):
        rl = RateLimiter(rate=0.01, burst=1)
        assert rl.available_tokens >= 0.0

    def test_refills_over_time(self):
        rl = RateLimiter(rate=100.0, burst=5)
        rl._tokens = 0.0
        rl._last_refill = time.monotonic() - 0.1  # 0.1s ago @ 100/s = 10 tokens added, capped at 5
        assert rl.available_tokens >= 4.9


# ---------------------------------------------------------------------------
# acquire — basic token consumption
# ---------------------------------------------------------------------------


class TestAcquireBasic:
    @pytest.mark.asyncio
    async def test_acquire_single_token_immediate_when_full(self):
        rl = RateLimiter(rate=1.0, burst=1)
        start = time.monotonic()
        await rl.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.2  # Should be near-instant

    @pytest.mark.asyncio
    async def test_acquire_reduces_tokens_by_one(self):
        rl = RateLimiter(rate=1.0, burst=5)
        before = rl.available_tokens
        await rl.acquire()
        after = rl._tokens
        assert abs((before - after) - 1.0) < 0.1

    @pytest.mark.asyncio
    async def test_acquire_burst_tokens_sequentially(self):
        burst = 4
        rl = RateLimiter(rate=0.01, burst=burst)  # Very slow refill
        start = time.monotonic()
        for _ in range(burst):
            await rl.acquire()
        elapsed = time.monotonic() - start
        # All burst tokens should be available immediately
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_acquire_blocks_when_no_tokens(self):
        """Acquiring beyond burst should block and wait for refill."""
        rl = RateLimiter(rate=10.0, burst=1)  # 10 tokens/sec, burst=1
        # Drain the one available token
        await rl.acquire()
        # Next acquire should wait ~0.1s for refill at 10/sec
        start = time.monotonic()
        await rl.acquire()
        elapsed = time.monotonic() - start
        # Should have waited at least a bit but not too long
        assert elapsed >= 0.05
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_acquire_respects_rate(self):
        """With rate=5 (0.2s per token), acquiring 2 tokens beyond burst should take ~0.2s."""
        rl = RateLimiter(rate=5.0, burst=1)
        await rl.acquire()  # consume burst
        start = time.monotonic()
        await rl.acquire()  # should wait ~0.2s
        elapsed = time.monotonic() - start
        assert elapsed >= 0.15
        assert elapsed < 1.0


# ---------------------------------------------------------------------------
# acquire — concurrent access
# ---------------------------------------------------------------------------


class TestAcquireConcurrent:
    @pytest.mark.asyncio
    async def test_concurrent_acquires_are_serialized(self):
        """Multiple concurrent acquires should each get exactly one token."""
        rl = RateLimiter(rate=50.0, burst=3)
        results = []

        async def task(tid: int) -> None:
            await rl.acquire()
            results.append(tid)

        await asyncio.gather(*(task(i) for i in range(3)))
        assert len(results) == 3
        assert sorted(results) == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_no_tokens_granted_below_one(self):
        """After drain, each subsequent acquire should wait; tokens should not go negative."""
        rl = RateLimiter(rate=20.0, burst=2)
        await rl.acquire()
        await rl.acquire()
        # At this point tokens ~ 0; next acquire waits
        acquire_task = asyncio.create_task(rl.acquire())
        # Give it a moment to block
        await asyncio.sleep(0.01)
        assert not acquire_task.done()
        # Let it complete
        await asyncio.wait_for(acquire_task, timeout=1.0)
        assert rl._tokens >= 0.0


# ---------------------------------------------------------------------------
# _refill internal
# ---------------------------------------------------------------------------


class TestRefill:
    def test_refill_caps_at_burst(self):
        rl = RateLimiter(rate=1000.0, burst=3)
        rl._tokens = 0.0
        rl._last_refill = time.monotonic() - 10.0  # 10s ago @ 1000/s = 10000 tokens, capped at 3
        rl._refill()
        assert rl._tokens == 3.0

    def test_refill_adds_correct_amount(self):
        rl = RateLimiter(rate=2.0, burst=100)
        rl._tokens = 0.0
        rl._last_refill = time.monotonic() - 1.0  # 1s ago @ 2/s = 2 tokens
        rl._refill()
        assert abs(rl._tokens - 2.0) < 0.1

    def test_refill_updates_last_refill_time(self):
        rl = RateLimiter()
        old_time = rl._last_refill - 5.0
        rl._last_refill = old_time
        rl._refill()
        assert rl._last_refill > old_time

    def test_refill_does_not_decrease_tokens(self):
        rl = RateLimiter(rate=1.0, burst=10)
        rl._tokens = 5.0
        rl._last_refill = time.monotonic()  # Just now, so elapsed ~ 0
        rl._refill()
        assert rl._tokens >= 5.0
