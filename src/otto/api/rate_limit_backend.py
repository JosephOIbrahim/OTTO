"""
Rate Limiter Backend Abstraction
================================

Provides pluggable backend interface for rate limiting.
Supports distributed rate limiting across multiple instances.

[He2025] Compliance:
- FIXED rate limit configurations
- DETERMINISTIC limit checking
- Backend-agnostic interface

Backends:
- InMemoryBackend: Default, single-instance (current behavior)
- RedisBackend: Distributed, multi-instance (interface only)

Usage:
    # Default in-memory backend
    backend = InMemoryRateLimitBackend()

    # Create rate limit middleware with backend
    middleware = RateLimitMiddleware(backend=backend)

    # Or use Redis for distributed limiting
    redis_backend = RedisRateLimitBackend(redis_url="redis://localhost:6379")
    middleware = RateLimitMiddleware(backend=redis_backend)
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Backend Interface
# =============================================================================

@dataclass
class RateLimitState:
    """
    Current state of a rate limit bucket.

    Immutable representation of rate limit state at a point in time.
    """
    key: str                      # Bucket identifier
    current_count: int            # Current request count in window
    limit: int                    # Maximum requests allowed
    window_seconds: float         # Time window in seconds
    window_start: float           # When current window started
    remaining: int                # Requests remaining
    reset_at: float               # When limit resets (Unix timestamp)

    @property
    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.remaining <= 0

    @property
    def retry_after(self) -> float:
        """Seconds until limit resets."""
        return max(0.0, self.reset_at - time.time())

    def to_headers(self) -> Dict[str, str]:
        """Convert to rate limit response headers."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }


class RateLimitBackend(ABC):
    """
    Abstract base class for rate limit backends.

    [He2025] Compliance:
    - Backend implementations must be DETERMINISTIC
    - Same key + config → same behavior
    - Atomic operations required

    Subclasses must implement:
    - check_and_increment(): Atomically check and increment counter
    - get_state(): Get current state for a key
    - reset(): Reset a rate limit bucket
    - cleanup(): Clean up expired entries
    """

    @abstractmethod
    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: float,
    ) -> Tuple[bool, RateLimitState]:
        """
        Atomically check rate limit and increment counter.

        This operation MUST be atomic to prevent race conditions.

        Args:
            key: Unique identifier for this rate limit bucket
            limit: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (allowed, state)
            - allowed: True if request should proceed
            - state: Current rate limit state
        """
        pass

    @abstractmethod
    async def get_state(self, key: str) -> Optional[RateLimitState]:
        """
        Get current state for a rate limit key.

        Args:
            key: Rate limit bucket identifier

        Returns:
            Current state or None if key doesn't exist
        """
        pass

    @abstractmethod
    async def reset(self, key: str) -> bool:
        """
        Reset a rate limit bucket.

        Args:
            key: Rate limit bucket identifier

        Returns:
            True if reset was successful
        """
        pass

    @abstractmethod
    async def cleanup(self, max_age_seconds: float) -> int:
        """
        Clean up expired rate limit entries.

        Args:
            max_age_seconds: Remove entries older than this

        Returns:
            Number of entries removed
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get backend statistics.

        Returns:
            Dict with backend-specific stats
        """
        pass


# =============================================================================
# In-Memory Backend
# =============================================================================

@dataclass
class _InMemoryBucket:
    """Internal bucket state for in-memory backend."""
    count: int = 0
    window_start: float = 0.0
    last_access: float = 0.0


class InMemoryRateLimitBackend(RateLimitBackend):
    """
    In-memory rate limit backend using sliding window.

    Suitable for single-instance deployments.
    State is lost on restart.

    [He2025] Compliance:
    - FIXED window algorithm (sliding window)
    - DETERMINISTIC bucket management
    - Thread-safe via asyncio lock
    """

    def __init__(self, cleanup_threshold: int = 10000):
        """
        Initialize in-memory backend.

        Args:
            cleanup_threshold: Trigger cleanup when buckets exceed this count
        """
        self._buckets: Dict[str, _InMemoryBucket] = {}
        self._lock = asyncio.Lock()
        self._cleanup_threshold = cleanup_threshold
        self._total_requests = 0
        self._total_allowed = 0
        self._total_denied = 0

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: float,
    ) -> Tuple[bool, RateLimitState]:
        """Check and increment rate limit counter."""
        async with self._lock:
            self._total_requests += 1
            now = time.time()

            # Get or create bucket
            if key not in self._buckets:
                self._buckets[key] = _InMemoryBucket(
                    count=0,
                    window_start=now,
                    last_access=now,
                )

            bucket = self._buckets[key]

            # Check if window has expired
            window_end = bucket.window_start + window_seconds
            if now >= window_end:
                # Reset window
                bucket.count = 0
                bucket.window_start = now

            bucket.last_access = now

            # Check limit
            allowed = bucket.count < limit
            if allowed:
                bucket.count += 1
                self._total_allowed += 1
            else:
                self._total_denied += 1

            # Build state
            state = RateLimitState(
                key=key,
                current_count=bucket.count,
                limit=limit,
                window_seconds=window_seconds,
                window_start=bucket.window_start,
                remaining=max(0, limit - bucket.count),
                reset_at=bucket.window_start + window_seconds,
            )

            # Trigger cleanup if needed
            if len(self._buckets) > self._cleanup_threshold:
                asyncio.create_task(self._cleanup_old_buckets(window_seconds * 2))

            return allowed, state

    async def get_state(self, key: str) -> Optional[RateLimitState]:
        """Get current state for a key."""
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                return None

            # We don't know the original limit/window, return partial state
            return RateLimitState(
                key=key,
                current_count=bucket.count,
                limit=0,  # Unknown
                window_seconds=0,  # Unknown
                window_start=bucket.window_start,
                remaining=0,  # Unknown
                reset_at=0,  # Unknown
            )

    async def reset(self, key: str) -> bool:
        """Reset a rate limit bucket."""
        async with self._lock:
            if key in self._buckets:
                del self._buckets[key]
                return True
            return False

    async def cleanup(self, max_age_seconds: float) -> int:
        """Clean up old buckets."""
        return await self._cleanup_old_buckets(max_age_seconds)

    async def _cleanup_old_buckets(self, max_age_seconds: float) -> int:
        """Internal cleanup implementation."""
        async with self._lock:
            now = time.time()
            cutoff = now - max_age_seconds
            old_keys = [
                k for k, b in self._buckets.items()
                if b.last_access < cutoff
            ]
            for key in old_keys:
                del self._buckets[key]

            if old_keys:
                logger.debug(f"Cleaned up {len(old_keys)} expired rate limit buckets")

            return len(old_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get backend statistics."""
        return {
            "backend": "in_memory",
            "bucket_count": len(self._buckets),
            "cleanup_threshold": self._cleanup_threshold,
            "total_requests": self._total_requests,
            "total_allowed": self._total_allowed,
            "total_denied": self._total_denied,
            "denial_rate": (
                self._total_denied / self._total_requests
                if self._total_requests > 0 else 0.0
            ),
        }


# =============================================================================
# Redis Backend (Interface)
# =============================================================================

class RedisRateLimitBackend(RateLimitBackend):
    """
    Redis-backed rate limit backend for distributed limiting.

    Uses Redis MULTI/EXEC for atomic operations.
    Supports multiple OTTO instances sharing rate limits.

    [He2025] Compliance:
    - FIXED Lua scripts (no runtime variation)
    - DETERMINISTIC atomic operations
    - Consistent hashing for key distribution

    Note: This is the interface definition. Full implementation
    requires redis-py async client to be installed.

    Usage:
        backend = RedisRateLimitBackend(
            redis_url="redis://localhost:6379/0",
            key_prefix="otto:ratelimit:",
        )
    """

    # [He2025] FIXED Lua script for atomic check-and-increment
    # This script is loaded once and cached by Redis
    _CHECK_AND_INCREMENT_SCRIPT = """
    local key = KEYS[1]
    local limit = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local now = tonumber(ARGV[3])

    -- Get current window data
    local data = redis.call('HMGET', key, 'count', 'window_start')
    local count = tonumber(data[1]) or 0
    local window_start = tonumber(data[2]) or now

    -- Check if window expired
    if now >= window_start + window then
        count = 0
        window_start = now
    end

    -- Check limit and increment
    local allowed = 0
    if count < limit then
        count = count + 1
        allowed = 1
    end

    -- Update Redis
    redis.call('HMSET', key, 'count', count, 'window_start', window_start)
    redis.call('EXPIRE', key, math.ceil(window * 2))

    return {allowed, count, window_start}
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "otto:ratelimit:",
        connection_pool_size: int = 10,
    ):
        """
        Initialize Redis backend.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for all rate limit keys
            connection_pool_size: Max connections in pool
        """
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._pool_size = connection_pool_size
        self._client = None
        self._script_sha = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure Redis connection is established."""
        if self._initialized:
            return

        try:
            import redis.asyncio as redis
        except ImportError:
            raise ImportError(
                "redis package required for RedisRateLimitBackend. "
                "Install with: pip install redis"
            )

        self._client = redis.from_url(
            self._redis_url,
            max_connections=self._pool_size,
        )

        # Load and cache the Lua script
        self._script_sha = await self._client.script_load(
            self._CHECK_AND_INCREMENT_SCRIPT
        )
        self._initialized = True
        logger.info(f"Redis rate limit backend initialized: {self._redis_url}")

    def _make_key(self, key: str) -> str:
        """Create full Redis key with prefix."""
        return f"{self._key_prefix}{key}"

    async def check_and_increment(
        self,
        key: str,
        limit: int,
        window_seconds: float,
    ) -> Tuple[bool, RateLimitState]:
        """Check and increment using Redis Lua script."""
        await self._ensure_initialized()

        redis_key = self._make_key(key)
        now = time.time()

        # Execute atomic Lua script
        result = await self._client.evalsha(
            self._script_sha,
            1,  # Number of keys
            redis_key,
            limit,
            window_seconds,
            now,
        )

        allowed = result[0] == 1
        count = int(result[1])
        window_start = float(result[2])

        state = RateLimitState(
            key=key,
            current_count=count,
            limit=limit,
            window_seconds=window_seconds,
            window_start=window_start,
            remaining=max(0, limit - count),
            reset_at=window_start + window_seconds,
        )

        return allowed, state

    async def get_state(self, key: str) -> Optional[RateLimitState]:
        """Get current state from Redis."""
        await self._ensure_initialized()

        redis_key = self._make_key(key)
        data = await self._client.hmget(redis_key, "count", "window_start")

        if data[0] is None:
            return None

        return RateLimitState(
            key=key,
            current_count=int(data[0]),
            limit=0,  # Unknown
            window_seconds=0,  # Unknown
            window_start=float(data[1]) if data[1] else 0,
            remaining=0,  # Unknown
            reset_at=0,  # Unknown
        )

    async def reset(self, key: str) -> bool:
        """Reset rate limit in Redis."""
        await self._ensure_initialized()

        redis_key = self._make_key(key)
        result = await self._client.delete(redis_key)
        return result > 0

    async def cleanup(self, max_age_seconds: float) -> int:
        """
        Clean up expired entries.

        Note: Redis handles expiration automatically via EXPIRE.
        This method is a no-op but maintained for interface compatibility.
        """
        return 0  # Redis handles expiration

    def get_stats(self) -> Dict[str, Any]:
        """Get backend statistics."""
        return {
            "backend": "redis",
            "redis_url": self._redis_url,
            "key_prefix": self._key_prefix,
            "pool_size": self._pool_size,
            "initialized": self._initialized,
        }


# =============================================================================
# Backend Factory
# =============================================================================

def create_rate_limit_backend(
    backend_type: str = "memory",
    **kwargs: Any,
) -> RateLimitBackend:
    """
    Factory function to create rate limit backends.

    [He2025] FIXED backend types - no runtime registration.

    Args:
        backend_type: One of "memory" or "redis"
        **kwargs: Backend-specific arguments

    Returns:
        Configured RateLimitBackend

    Raises:
        ValueError: If backend_type is unknown
    """
    if backend_type == "memory":
        return InMemoryRateLimitBackend(
            cleanup_threshold=kwargs.get("cleanup_threshold", 10000),
        )
    elif backend_type == "redis":
        return RedisRateLimitBackend(
            redis_url=kwargs.get("redis_url", "redis://localhost:6379/0"),
            key_prefix=kwargs.get("key_prefix", "otto:ratelimit:"),
            connection_pool_size=kwargs.get("connection_pool_size", 10),
        )
    else:
        raise ValueError(
            f"Unknown backend type: {backend_type}. "
            f"Supported: memory, redis"
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # State
    "RateLimitState",

    # Base class
    "RateLimitBackend",

    # Implementations
    "InMemoryRateLimitBackend",
    "RedisRateLimitBackend",

    # Factory
    "create_rate_limit_backend",
]
