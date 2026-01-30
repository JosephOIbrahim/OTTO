"""
Rate limiting for Framework Orchestrator.

Implements token-bucket algorithm with adaptive backpressure:
- Configurable rate (tokens per second)
- Burst capacity for handling spikes
- Adaptive mode that adjusts based on success rate

Prevents system overload from excessive requests.

Usage:
    limiter = RateLimiter(rate=100.0, burst_size=50)

    # Acquire before processing
    wait_time = await limiter.acquire()
    if wait_time > 0:
        print(f"Rate limited, waited {wait_time}s")

    # Process request...
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import threading

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and blocking is disabled."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.2f}s")


@dataclass
class RateLimiterStats:
    """Statistics for rate limiter monitoring."""

    total_requests: int = 0
    total_allowed: int = 0
    total_limited: int = 0
    total_wait_time: float = 0.0
    max_wait_time: float = 0.0
    current_tokens: float = 0.0


class RateLimiter:
    """
    Token-bucket rate limiter with optional adaptive backpressure.

    The token bucket algorithm:
    - Bucket holds up to `burst_size` tokens
    - Tokens added at `rate` per second
    - Each request consumes tokens (default 1.0)
    - If not enough tokens, wait or reject

    Adaptive mode:
    - Monitors success/failure rates
    - Reduces rate when failures increase
    - Increases rate when successful

    Thread-safe for concurrent access.
    """

    def __init__(
        self,
        rate: float = 100.0,
        burst_size: int = 50,
        adaptive: bool = False,
        min_rate: float = 10.0,
        max_rate: float = 500.0,
        block: bool = True,
        max_wait: float = 30.0
    ):
        """
        Initialize rate limiter.

        Args:
            rate: Tokens added per second (requests/sec)
            burst_size: Maximum tokens (burst capacity)
            adaptive: Whether to adapt rate based on success/failure
            min_rate: Minimum rate for adaptive mode
            max_rate: Maximum rate for adaptive mode
            block: Whether to block (True) or raise (False) when limited
            max_wait: Maximum time to wait when blocking
        """
        self.rate = rate
        self.burst_size = burst_size
        self.adaptive = adaptive
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.block = block
        self.max_wait = max_wait

        # Token bucket state
        self._tokens = float(burst_size)
        self._last_update = time.time()

        # Adaptive mode state
        self._success_count = 0
        self._failure_count = 0
        self._last_adaptation = time.time()
        self._adaptation_interval = 60.0  # seconds

        # Statistics
        self._stats = RateLimiterStats()

        # Thread safety
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()

        logger.info(
            f"RateLimiter initialized: rate={rate}/s, burst={burst_size}, "
            f"adaptive={adaptive}"
        )

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._last_update = now

        # Add tokens based on time and rate
        self._tokens = min(
            self.burst_size,
            self._tokens + elapsed * self.rate
        )

    def _try_acquire_sync(self, tokens: float) -> float:
        """
        Try to acquire tokens synchronously.

        Returns:
            Wait time in seconds (0 if acquired immediately)
        """
        with self._lock:
            self._refill_tokens()
            self._stats.total_requests += 1
            self._stats.current_tokens = self._tokens

            if self._tokens >= tokens:
                self._tokens -= tokens
                self._stats.total_allowed += 1
                return 0.0
            else:
                # Calculate wait time
                deficit = tokens - self._tokens
                wait_time = deficit / self.rate
                self._stats.total_limited += 1
                return wait_time

    async def acquire(self, tokens: float = 1.0) -> float:
        """
        Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (default 1.0)

        Returns:
            Time spent waiting (0 if no wait needed)

        Raises:
            RateLimitExceeded: If blocking is disabled and no tokens available
        """
        async with self._async_lock:
            wait_time = self._try_acquire_sync(tokens)

            if wait_time <= 0:
                return 0.0

            if not self.block:
                raise RateLimitExceeded(wait_time)

            # Limit maximum wait
            if wait_time > self.max_wait:
                raise RateLimitExceeded(wait_time)

            # Wait and record
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

            # Now acquire tokens
            with self._lock:
                self._refill_tokens()
                self._tokens -= tokens
                self._stats.total_wait_time += wait_time
                self._stats.max_wait_time = max(self._stats.max_wait_time, wait_time)

            return wait_time

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if acquired, False if rate limited
        """
        wait_time = self._try_acquire_sync(tokens)
        return wait_time <= 0

    def record_success(self) -> None:
        """Record a successful request (for adaptive mode)."""
        if not self.adaptive:
            return
        with self._lock:
            self._success_count += 1
            self._maybe_adapt()

    def record_failure(self) -> None:
        """Record a failed request (for adaptive mode)."""
        if not self.adaptive:
            return
        with self._lock:
            self._failure_count += 1
            self._maybe_adapt()

    def _maybe_adapt(self) -> None:
        """Check if adaptation is needed and apply."""
        now = time.time()
        if now - self._last_adaptation < self._adaptation_interval:
            return

        total = self._success_count + self._failure_count
        if total < 10:  # Need minimum samples
            return

        success_rate = self._success_count / total

        # Adapt rate based on success rate
        if success_rate > 0.95 and self.rate < self.max_rate:
            # High success, try increasing
            new_rate = min(self.rate * 1.2, self.max_rate)
            logger.info(f"Rate limiter adapting UP: {self.rate:.1f} -> {new_rate:.1f}/s")
            self.rate = new_rate
        elif success_rate < 0.8 and self.rate > self.min_rate:
            # High failure, reduce
            new_rate = max(self.rate * 0.8, self.min_rate)
            logger.info(f"Rate limiter adapting DOWN: {self.rate:.1f} -> {new_rate:.1f}/s")
            self.rate = new_rate

        # Reset counters
        self._success_count = 0
        self._failure_count = 0
        self._last_adaptation = now

    def get_tokens_available(self) -> float:
        """Get number of tokens currently available."""
        with self._lock:
            self._refill_tokens()
            return self._tokens

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self._lock:
            total = self._stats.total_requests
            limited_rate = self._stats.total_limited / total if total > 0 else 0.0

            return {
                "current_rate": self.rate,
                "burst_size": self.burst_size,
                "tokens_available": self._tokens,
                "total_requests": self._stats.total_requests,
                "total_allowed": self._stats.total_allowed,
                "total_limited": self._stats.total_limited,
                "limited_rate": limited_rate,
                "total_wait_time": self._stats.total_wait_time,
                "max_wait_time": self._stats.max_wait_time,
                "adaptive": self.adaptive,
            }

    def reset(self) -> None:
        """Reset rate limiter state (for testing)."""
        with self._lock:
            self._tokens = float(self.burst_size)
            self._last_update = time.time()
            self._success_count = 0
            self._failure_count = 0
            self._stats = RateLimiterStats()


class SlidingWindowLimiter:
    """
    Sliding window rate limiter (more accurate than token bucket).

    Tracks exact timestamps of requests in a sliding window.
    More memory intensive but precise.
    """

    def __init__(
        self,
        rate: int,
        window_seconds: float = 1.0,
        block: bool = True,
        max_wait: float = 30.0
    ):
        """
        Initialize sliding window limiter.

        Args:
            rate: Maximum requests per window
            window_seconds: Size of sliding window
            block: Whether to block when limited
            max_wait: Maximum wait time
        """
        self.rate = rate
        self.window_seconds = window_seconds
        self.block = block
        self.max_wait = max_wait

        self._timestamps: list[float] = []
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    def _cleanup_old(self) -> None:
        """Remove timestamps outside window."""
        now = time.time()
        cutoff = now - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]

    async def acquire(self) -> float:
        """
        Acquire permission to proceed.

        Returns:
            Wait time (0 if no wait)

        Raises:
            RateLimitExceeded: If blocking disabled and limited
        """
        async with self._async_lock:
            with self._lock:
                self._cleanup_old()
                now = time.time()

                if len(self._timestamps) < self.rate:
                    self._timestamps.append(now)
                    return 0.0

                # Calculate when oldest request will expire
                oldest = self._timestamps[0]
                wait_time = (oldest + self.window_seconds) - now

                if wait_time <= 0:
                    self._timestamps.append(now)
                    return 0.0

                if not self.block:
                    raise RateLimitExceeded(wait_time)

                if wait_time > self.max_wait:
                    raise RateLimitExceeded(wait_time)

            # Wait outside lock
            await asyncio.sleep(wait_time)

            with self._lock:
                self._cleanup_old()
                self._timestamps.append(time.time())

            return wait_time

    def get_current_rate(self) -> float:
        """Get current request rate."""
        with self._lock:
            self._cleanup_old()
            return len(self._timestamps) / self.window_seconds


class CompositeRateLimiter:
    """
    Composite rate limiter that applies multiple limits.

    Useful for layered rate limiting:
    - Per-agent limits
    - Global limits
    - Burst vs sustained limits
    """

    def __init__(self):
        """Initialize composite limiter."""
        self._limiters: Dict[str, RateLimiter] = {}
        self._async_lock = asyncio.Lock()

    def add_limiter(self, name: str, limiter: RateLimiter) -> None:
        """Add a named rate limiter."""
        self._limiters[name] = limiter

    def remove_limiter(self, name: str) -> None:
        """Remove a rate limiter."""
        self._limiters.pop(name, None)

    async def acquire(self, tokens: float = 1.0) -> float:
        """
        Acquire from all limiters.

        Returns:
            Total wait time
        """
        async with self._async_lock:
            total_wait = 0.0

            for name, limiter in self._limiters.items():
                try:
                    wait = await limiter.acquire(tokens)
                    total_wait += wait
                except RateLimitExceeded:
                    raise

            return total_wait

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats from all limiters."""
        return {name: limiter.get_stats() for name, limiter in self._limiters.items()}
