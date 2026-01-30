"""
Tests for fallback strategies module.

Tests:
- CachedResult validity and age tracking
- FallbackResult metadata
- FallbackRegistry cache operations
- Fallback strategy registration and execution
- Synthetic result generation
- Cache → Fallback → Synthetic hierarchy
- GracefulDegradation coordination
- Statistics tracking
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from otto.fallback import (
    CachedResult,
    FallbackResult,
    FallbackRegistry,
    GracefulDegradation,
)


class TestCachedResult:
    """Test CachedResult dataclass."""

    def test_creation(self):
        """Should create cached result with fields."""
        cached = CachedResult(
            result={"key": "value"},
            cached_at=1000.0,
            task_hash="abc123",
            ttl=3600.0
        )

        assert cached.result == {"key": "value"}
        assert cached.cached_at == 1000.0
        assert cached.task_hash == "abc123"
        assert cached.ttl == 3600.0

    def test_default_ttl(self):
        """Should have default TTL of 1 hour."""
        cached = CachedResult(result={}, cached_at=0)

        assert cached.ttl == 3600.0

    def test_is_valid_fresh(self):
        """Should be valid when fresh."""
        cached = CachedResult(
            result={},
            cached_at=time.time(),
            ttl=3600.0
        )

        assert cached.is_valid() is True

    def test_is_valid_expired(self):
        """Should be invalid when expired."""
        cached = CachedResult(
            result={},
            cached_at=time.time() - 7200,  # 2 hours ago
            ttl=3600.0  # 1 hour TTL
        )

        assert cached.is_valid() is False

    def test_is_valid_custom_max_age(self):
        """Should respect custom max_age parameter."""
        cached = CachedResult(
            result={},
            cached_at=time.time() - 100,  # 100 seconds ago
            ttl=3600.0
        )

        assert cached.is_valid(max_age=200) is True
        assert cached.is_valid(max_age=50) is False

    def test_age_seconds(self):
        """Should calculate age correctly."""
        now = time.time()
        cached = CachedResult(result={}, cached_at=now - 60)

        age = cached.age_seconds
        assert 59 < age < 62  # Allow for timing variance


class TestFallbackResult:
    """Test FallbackResult dataclass."""

    def test_creation(self):
        """Should create fallback result with fields."""
        result = FallbackResult(
            result={"data": "value"},
            source="cache",
            reason="Agent timeout",
            age_seconds=30.5
        )

        assert result.result == {"data": "value"}
        assert result.source == "cache"
        assert result.reason == "Agent timeout"
        assert result.age_seconds == 30.5

    def test_to_dict(self):
        """Should convert to dict with metadata."""
        result = FallbackResult(
            result={"original": "data"},
            source="fallback",
            reason="Circuit breaker open",
            age_seconds=None
        )

        d = result.to_dict()

        assert d["original"] == "data"
        assert d["_fallback"]["source"] == "fallback"
        assert d["_fallback"]["reason"] == "Circuit breaker open"


class TestFallbackRegistryBasic:
    """Test basic FallbackRegistry functionality."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        registry = FallbackRegistry()

        assert registry.cache_ttl == 3600.0
        assert registry.max_cache_entries == 100
        assert registry.enable_synthetic is True

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        registry = FallbackRegistry(
            cache_ttl=1800.0,
            max_cache_entries=50,
            enable_synthetic=False
        )

        assert registry.cache_ttl == 1800.0
        assert registry.max_cache_entries == 50
        assert registry.enable_synthetic is False


class TestFallbackRegistryCache:
    """Test FallbackRegistry caching functionality."""

    def test_cache_result(self):
        """Should cache a result."""
        registry = FallbackRegistry()

        registry.cache_result("agent1", {"output": "data"})

        # Cache should have entry
        assert len(registry._cache["agent1"]) == 1

    def test_cache_result_with_task_hash(self):
        """Should store task hash with cached result."""
        registry = FallbackRegistry()

        registry.cache_result("agent1", {"output": "data"}, task_hash="hash123")

        cached = registry._cache["agent1"][0]
        assert cached.task_hash == "hash123"

    def test_cache_result_custom_ttl(self):
        """Should respect custom TTL."""
        registry = FallbackRegistry(cache_ttl=3600.0)

        registry.cache_result("agent1", {}, ttl=1800.0)

        cached = registry._cache["agent1"][0]
        assert cached.ttl == 1800.0

    def test_cache_trims_to_max(self):
        """Should trim cache to max_cache_entries."""
        registry = FallbackRegistry(max_cache_entries=3)

        for i in range(5):
            registry.cache_result("agent1", {"n": i})

        assert len(registry._cache["agent1"]) == 3

    def test_cache_most_recent_first(self):
        """Should keep most recent entries."""
        registry = FallbackRegistry(max_cache_entries=2)

        registry.cache_result("agent1", {"n": 1})
        registry.cache_result("agent1", {"n": 2})
        registry.cache_result("agent1", {"n": 3})

        # Most recent should be first
        assert registry._cache["agent1"][0].result["n"] == 3


class TestFallbackRegistryStrategies:
    """Test fallback strategy registration."""

    def test_register_fallback(self):
        """Should register fallback strategy."""
        registry = FallbackRegistry()

        def strategy(reason):
            return {"fallback": True}

        registry.register_fallback("agent1", strategy)

        assert "agent1" in registry._strategies

    def test_register_synthetic_template(self):
        """Should register synthetic template."""
        registry = FallbackRegistry()

        registry.register_synthetic_template("custom_agent", {
            "default": "value"
        })

        assert "custom_agent" in registry._synthetic_templates
        assert registry._synthetic_templates["custom_agent"]["synthetic"] is True


class TestFallbackRegistryTryFallback:
    """Test try_fallback functionality."""

    @pytest.mark.asyncio
    async def test_try_fallback_uses_cache(self):
        """Should return cached result first."""
        registry = FallbackRegistry()

        registry.cache_result("agent1", {"cached": "result"})

        result = await registry.try_fallback("agent1", "test reason")

        assert result.source == "cache"
        assert result.result["cached"] == "result"

    @pytest.mark.asyncio
    async def test_try_fallback_uses_strategy(self):
        """Should use fallback strategy when no cache."""
        registry = FallbackRegistry()

        def strategy(reason):
            return {"strategy": "result", "reason": reason}

        registry.register_fallback("agent1", strategy)

        result = await registry.try_fallback("agent1", "test reason")

        assert result.source == "fallback"
        assert result.result["strategy"] == "result"

    @pytest.mark.asyncio
    async def test_try_fallback_async_strategy(self):
        """Should handle async fallback strategies."""
        registry = FallbackRegistry()

        async def async_strategy(reason):
            await asyncio.sleep(0.01)
            return {"async": True}

        registry.register_fallback("agent1", async_strategy)

        result = await registry.try_fallback("agent1", "test")

        assert result.source == "fallback"
        assert result.result["async"] is True

    @pytest.mark.asyncio
    async def test_try_fallback_uses_synthetic(self):
        """Should use synthetic when no cache or strategy."""
        registry = FallbackRegistry()

        # Use default synthetic for known agent
        result = await registry.try_fallback("moe_router", "test")

        assert result.source == "synthetic"
        assert result.result["synthetic"] is True

    @pytest.mark.asyncio
    async def test_try_fallback_generic_synthetic(self):
        """Should use generic synthetic for unknown agent."""
        registry = FallbackRegistry()

        result = await registry.try_fallback("unknown_agent", "some reason")

        assert result.source == "synthetic"
        assert result.result["agent"] == "unknown_agent"
        assert result.result["fallback_exhausted"] is True

    @pytest.mark.asyncio
    async def test_try_fallback_respects_prefer_cache(self):
        """Should skip cache when prefer_cache=False."""
        registry = FallbackRegistry()

        registry.cache_result("agent1", {"cached": True})
        registry.register_fallback("agent1", lambda r: {"fallback": True})

        result = await registry.try_fallback(
            "agent1", "test", prefer_cache=False
        )

        assert result.source == "fallback"

    @pytest.mark.asyncio
    async def test_try_fallback_respects_max_cache_age(self):
        """Should skip old cache entries."""
        registry = FallbackRegistry()

        # Create old cached entry
        old_cached = CachedResult(
            result={"old": True},
            cached_at=time.time() - 1000,
            ttl=3600.0
        )
        registry._cache["agent1"].append(old_cached)

        registry.register_fallback("agent1", lambda r: {"fallback": True})

        result = await registry.try_fallback(
            "agent1", "test", max_cache_age=100
        )

        # Should skip old cache and use fallback
        assert result.source == "fallback"

    @pytest.mark.asyncio
    async def test_try_fallback_strategy_failure(self):
        """Should continue to synthetic when strategy fails."""
        registry = FallbackRegistry()

        def failing_strategy(reason):
            raise ValueError("Strategy failed")

        registry.register_fallback("moe_router", failing_strategy)

        result = await registry.try_fallback("moe_router", "test")

        # Should fall through to synthetic
        assert result.source == "synthetic"


class TestFallbackRegistryStats:
    """Test statistics functionality."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Should track cache hits and misses."""
        registry = FallbackRegistry()

        registry.cache_result("agent1", {"cached": True})

        # Hit
        await registry.try_fallback("agent1", "test")
        # Miss (no cache for agent2)
        await registry.try_fallback("agent2", "test")

        stats = registry.get_stats()

        assert stats["cache_hits"] >= 1
        assert stats["cache_misses"] >= 1

    @pytest.mark.asyncio
    async def test_stats_fallback_uses(self):
        """Should track fallback uses."""
        registry = FallbackRegistry()
        registry.register_fallback("agent1", lambda r: {})

        await registry.try_fallback("agent1", "test")

        stats = registry.get_stats()
        assert stats["fallback_uses"] >= 1

    @pytest.mark.asyncio
    async def test_stats_synthetic_uses(self):
        """Should track synthetic uses."""
        registry = FallbackRegistry()

        await registry.try_fallback("moe_router", "test")

        stats = registry.get_stats()
        assert stats["synthetic_uses"] >= 1

    def test_reset_stats(self):
        """Should reset all statistics."""
        registry = FallbackRegistry()
        registry._cache_hits = 10
        registry._fallback_uses = 5

        registry.reset_stats()

        stats = registry.get_stats()
        assert stats["cache_hits"] == 0
        assert stats["fallback_uses"] == 0


class TestFallbackRegistryClearCache:
    """Test cache clearing functionality."""

    def test_clear_specific_agent(self):
        """Should clear cache for specific agent."""
        registry = FallbackRegistry()

        registry.cache_result("agent1", {})
        registry.cache_result("agent2", {})

        count = registry.clear_cache("agent1")

        assert count == 1
        assert len(registry._cache["agent1"]) == 0
        assert len(registry._cache["agent2"]) == 1

    def test_clear_all_cache(self):
        """Should clear all cache."""
        registry = FallbackRegistry()

        registry.cache_result("agent1", {})
        registry.cache_result("agent2", {})

        count = registry.clear_cache()

        assert count == 2
        assert len(registry._cache) == 0


class TestFallbackRegistryDefaultSynthetics:
    """Test default synthetic templates."""

    def test_default_synthetics_exist(self):
        """Should have default synthetics for known agents."""
        registry = FallbackRegistry()

        assert "echo_curator" in registry._synthetic_templates
        assert "domain_intelligence" in registry._synthetic_templates
        assert "moe_router" in registry._synthetic_templates
        assert "world_modeler" in registry._synthetic_templates

    @pytest.mark.asyncio
    async def test_default_synthetic_moe_router(self):
        """Should return valid moe_router synthetic."""
        registry = FallbackRegistry()

        result = await registry.try_fallback("moe_router", "test")

        assert "selected_expert" in result.result
        assert result.result["synthetic"] is True


class TestGracefulDegradationBasic:
    """Test basic GracefulDegradation functionality."""

    def test_initialization(self):
        """Should initialize with fallback registry."""
        degradation = GracefulDegradation()

        assert degradation.fallback is not None

    def test_initialization_custom_registry(self):
        """Should accept custom fallback registry."""
        registry = FallbackRegistry()
        degradation = GracefulDegradation(fallback_registry=registry)

        assert degradation.fallback is registry


class TestGracefulDegradationStatus:
    """Test degradation status tracking."""

    def test_mark_degraded(self):
        """Should mark agent as degraded."""
        degradation = GracefulDegradation()

        degradation.mark_degraded("agent1", "timeout")

        assert degradation.is_degraded("agent1") is True
        assert degradation.is_degraded() is True  # System is degraded

    def test_clear_degraded(self):
        """Should clear degraded status."""
        degradation = GracefulDegradation()

        degradation.mark_degraded("agent1", "error")
        degradation.clear_degraded("agent1")

        assert degradation.is_degraded("agent1") is False

    def test_get_degraded_agents(self):
        """Should return all degraded agents."""
        degradation = GracefulDegradation()

        degradation.mark_degraded("agent1", "reason1")
        degradation.mark_degraded("agent2", "reason2")

        degraded = degradation.get_degraded_agents()

        assert len(degraded) == 2
        assert degraded["agent1"] == "reason1"
        assert degraded["agent2"] == "reason2"


class TestGracefulDegradationServiceLevel:
    """Test service level determination."""

    def test_service_level_full(self):
        """Should be full when nothing degraded."""
        degradation = GracefulDegradation()

        assert degradation.get_service_level() == "full"

    def test_service_level_degraded(self):
        """Should be degraded with 1-2 agents down."""
        degradation = GracefulDegradation()

        degradation.mark_degraded("agent1", "error")

        assert degradation.get_service_level() == "degraded"

    def test_service_level_minimal(self):
        """Should be minimal with 3+ agents down."""
        degradation = GracefulDegradation()

        degradation.mark_degraded("agent1", "error")
        degradation.mark_degraded("agent2", "error")
        degradation.mark_degraded("agent3", "error")

        assert degradation.get_service_level() == "minimal"


class TestGracefulDegradationExecution:
    """Test execute_with_degradation functionality."""

    @pytest.mark.asyncio
    async def test_execute_success_caches(self):
        """Should cache successful results."""
        degradation = GracefulDegradation()

        async def successful_coro():
            return {"success": True}

        result = await degradation.execute_with_degradation(
            "agent1", successful_coro()
        )

        assert result["success"] is True
        # Should be cached
        assert len(degradation.fallback._cache["agent1"]) == 1

    @pytest.mark.asyncio
    async def test_execute_success_clears_degraded(self):
        """Should clear degraded status on success."""
        degradation = GracefulDegradation()
        degradation.mark_degraded("agent1", "previous error")

        async def successful_coro():
            return {"ok": True}

        await degradation.execute_with_degradation("agent1", successful_coro())

        assert degradation.is_degraded("agent1") is False

    @pytest.mark.asyncio
    async def test_execute_failure_marks_degraded(self):
        """Should mark as degraded on failure."""
        degradation = GracefulDegradation()

        async def failing_coro():
            raise ValueError("Agent failed")

        result = await degradation.execute_with_degradation(
            "moe_router", failing_coro()
        )

        assert degradation.is_degraded("moe_router") is True
        # Should return fallback result
        assert "_fallback" in result

    @pytest.mark.asyncio
    async def test_execute_no_cache_on_flag(self):
        """Should not cache when cache_success=False."""
        degradation = GracefulDegradation()

        async def coro():
            return {"data": True}

        await degradation.execute_with_degradation(
            "agent1", coro(), cache_success=False
        )

        assert len(degradation.fallback._cache.get("agent1", [])) == 0

