"""
Tests for rate limiting module.

Tests:
- Token bucket algorithm
- Blocking vs non-blocking modes
- Burst capacity
- Statistics tracking
- Adaptive rate adjustment
"""

import asyncio
import time
import pytest

from otto.rate_limit import (
    RateLimiter,
    RateLimitExceeded,
    RateLimiterStats,
)


class TestRateLimiterBasic:
    """Test basic RateLimiter functionality."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        limiter = RateLimiter(rate=100.0, burst_size=50)

        assert limiter.rate == 100.0
        assert limiter.burst_size == 50
        assert limiter.block is True
        assert limiter.adaptive is False

    def test_try_acquire_within_burst(self):
        """Should immediately acquire within burst capacity."""
        limiter = RateLimiter(rate=10.0, burst_size=5)

        # First 5 should succeed immediately
        for _ in range(5):
            assert limiter.try_acquire() is True

    def test_try_acquire_exceeds_burst(self):
        """Should fail when exceeding burst without waiting."""
        limiter = RateLimiter(rate=10.0, burst_size=3)

        # Drain burst capacity
        for _ in range(3):
            limiter.try_acquire()

        # 4th should fail
        assert limiter.try_acquire() is False


class TestRateLimiterAsync:
    """Test async RateLimiter functionality."""

    @pytest.mark.asyncio
    async def test_acquire_within_burst(self):
        """Should immediately acquire within burst capacity."""
        limiter = RateLimiter(rate=100.0, burst_size=10)

        wait_time = await limiter.acquire()
        assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_acquire_with_blocking(self):
        """Should block and wait when rate limited."""
        limiter = RateLimiter(rate=100.0, burst_size=1, block=True)

        # First acquire should be instant
        wait1 = await limiter.acquire()
        assert wait1 == 0.0

        # Second should block briefly
        start = time.time()
        wait2 = await limiter.acquire()
        elapsed = time.time() - start

        # Should have waited (approximately 0.01s at 100/s rate)
        assert elapsed > 0
        assert wait2 > 0

    @pytest.mark.asyncio
    async def test_acquire_non_blocking_raises(self):
        """Should raise RateLimitExceeded when not blocking."""
        limiter = RateLimiter(rate=10.0, burst_size=1, block=False)

        # Drain capacity
        await limiter.acquire()

        # Should raise on next acquire
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.acquire()

        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_acquire_max_wait_exceeded(self):
        """Should raise when wait would exceed max_wait."""
        limiter = RateLimiter(rate=1.0, burst_size=1, block=True, max_wait=0.1)

        # Drain capacity
        await limiter.acquire()

        # Next would need to wait ~1s but max_wait is 0.1s
        with pytest.raises(RateLimitExceeded):
            await limiter.acquire()


class TestRateLimiterTokenRefill:
    """Test token refill mechanism."""

    def test_tokens_refill_over_time(self):
        """Tokens should refill based on rate."""
        limiter = RateLimiter(rate=100.0, burst_size=10)

        # Drain all tokens
        for _ in range(10):
            limiter.try_acquire()

        assert limiter.try_acquire() is False

        # Wait for refill (100/s = 1 token per 10ms)
        time.sleep(0.05)  # Should refill ~5 tokens

        # Should be able to acquire some tokens now
        assert limiter.try_acquire() is True

    def test_tokens_cap_at_burst(self):
        """Tokens should not exceed burst_size."""
        limiter = RateLimiter(rate=1000.0, burst_size=5)

        # Wait a bit
        time.sleep(0.1)

        # Force refill check
        limiter._refill_tokens()

        # Should be capped at burst_size
        assert limiter._tokens <= limiter.burst_size


class TestRateLimiterStats:
    """Test statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Should track request statistics."""
        limiter = RateLimiter(rate=100.0, burst_size=5)

        # Make some requests
        await limiter.acquire()
        await limiter.acquire()
        limiter.try_acquire()

        stats = limiter.get_stats()

        assert stats['total_requests'] >= 3
        assert stats['total_allowed'] >= 3

    @pytest.mark.asyncio
    async def test_stats_limited_tracking(self):
        """Should track rate limited requests."""
        limiter = RateLimiter(rate=10.0, burst_size=1, block=True, max_wait=1.0)

        # First is instant
        await limiter.acquire()

        # Second triggers limit
        await limiter.acquire()

        stats = limiter.get_stats()

        assert stats['total_limited'] >= 1
        assert stats['total_wait_time'] > 0


class TestRateLimiterMultipleTokens:
    """Test acquiring multiple tokens at once."""

    def test_acquire_multiple_tokens(self):
        """Should be able to acquire multiple tokens at once."""
        limiter = RateLimiter(rate=100.0, burst_size=10)

        # Acquire 5 tokens at once
        assert limiter.try_acquire(tokens=5.0) is True

        # Only 5 left
        assert limiter.try_acquire(tokens=5.0) is True

        # None left
        assert limiter.try_acquire(tokens=1.0) is False

    @pytest.mark.asyncio
    async def test_async_acquire_multiple_tokens(self):
        """Should handle async acquisition of multiple tokens."""
        limiter = RateLimiter(rate=100.0, burst_size=10)

        wait = await limiter.acquire(tokens=5.0)
        assert wait == 0.0

        wait = await limiter.acquire(tokens=5.0)
        assert wait == 0.0


class TestRateLimiterConcurrency:
    """Test concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_acquires(self):
        """Should handle concurrent acquire calls safely."""
        limiter = RateLimiter(rate=1000.0, burst_size=100)

        async def acquire_many(n):
            for _ in range(n):
                await limiter.acquire()

        # Run multiple concurrent tasks
        await asyncio.gather(
            acquire_many(20),
            acquire_many(20),
            acquire_many(20),
        )

        stats = limiter.get_stats()
        assert stats['total_requests'] == 60
