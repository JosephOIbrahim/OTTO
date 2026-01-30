"""
Fallback strategies for graceful degradation in Framework Orchestrator.

When agents fail, provides fallback behavior:
1. Try cached result (if available and fresh)
2. Try registered fallback strategy
3. Return synthetic minimal result

Prevents complete failure when individual components fail.

Usage:
    fallback = FallbackRegistry()

    # Register fallback for an agent
    fallback.register_fallback(
        "moe_router",
        lambda reason: {"selected_expert": "executor", "fallback": True}
    )

    # Cache a successful result
    fallback.cache_result("moe_router", successful_result)

    # Try fallback when agent fails
    result = await fallback.try_fallback("moe_router", "Circuit breaker open")
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Awaitable, Union
from collections import defaultdict
import threading
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class CachedResult:
    """A cached agent result with metadata."""

    result: Dict[str, Any]
    cached_at: float
    task_hash: Optional[str] = None
    ttl: float = 3600.0  # 1 hour default

    def is_valid(self, max_age: float = None) -> bool:
        """Check if cache entry is still valid."""
        max_age = max_age or self.ttl
        return time.time() - self.cached_at < max_age

    @property
    def age_seconds(self) -> float:
        """Get age of cached result in seconds."""
        return time.time() - self.cached_at


@dataclass
class FallbackResult:
    """Result from a fallback operation."""

    result: Dict[str, Any]
    source: str  # 'cache', 'fallback', 'synthetic'
    reason: str  # Why fallback was triggered
    age_seconds: Optional[float] = None  # For cached results

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with metadata."""
        return {
            **self.result,
            "_fallback": {
                "source": self.source,
                "reason": self.reason,
                "age_seconds": self.age_seconds,
            }
        }


FallbackStrategy = Union[
    Callable[[str], Dict[str, Any]],
    Callable[[str], Awaitable[Dict[str, Any]]]
]


class FallbackRegistry:
    """
    Registry for fallback strategies and cached results.

    Provides graceful degradation when agents fail:
    1. Cache: Use recent successful results
    2. Fallback: Use registered fallback strategies
    3. Synthetic: Generate minimal valid result

    Thread-safe for concurrent access.
    """

    # Default synthetic results for known agents
    DEFAULT_SYNTHETICS = {
        "echo_curator": {
            "memory_architecture": "LIVRPS",
            "active_mode": "focused_recall",
            "effective_tokens": 4096,
            "synthetic": True,
        },
        "domain_intelligence": {
            "detected_domains": ["general"],
            "primary_domain": "general",
            "detected_specialists": [],
            "domain_task_detected": False,
            "synthetic": True,
        },
        "moe_router": {
            "selected_expert": "executor",
            "bounded_scores": {"executor": 1.0},
            "safety_floors_applied": True,
            "synthetic": True,
        },
        "world_modeler": {
            "entities_detected": [],
            "causal_chains": [],
            "composite_energy": 0.5,
            "synthetic": True,
        },
        "code_generator": {
            "generation_method": "synthetic_fallback",
            "fitness_score": 0.0,
            "synthetic": True,
        },
        "determinism_guard": {
            "determinism_config": {"seed": 42},
            "reproducibility_guaranteed": False,
            "synthetic": True,
        },
        "self_reflector": {
            "overall_constitutional_score": 0.5,
            "violations_detected": [],
            "synthetic": True,
        },
    }

    def __init__(
        self,
        cache_ttl: float = 3600.0,
        max_cache_entries: int = 100,
        enable_synthetic: bool = True
    ):
        """
        Initialize fallback registry.

        Args:
            cache_ttl: Default cache TTL in seconds
            max_cache_entries: Maximum entries per agent in cache
            enable_synthetic: Whether to use synthetic fallbacks
        """
        self.cache_ttl = cache_ttl
        self.max_cache_entries = max_cache_entries
        self.enable_synthetic = enable_synthetic

        # Storage
        self._strategies: Dict[str, FallbackStrategy] = {}
        self._cache: Dict[str, list[CachedResult]] = defaultdict(list)
        self._synthetic_templates: Dict[str, Dict[str, Any]] = self.DEFAULT_SYNTHETICS.copy()

        # Statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._fallback_uses = 0
        self._synthetic_uses = 0

        # Thread safety
        self._lock = threading.Lock()

        logger.info("FallbackRegistry initialized")

    def register_fallback(
        self,
        agent_name: str,
        strategy: FallbackStrategy
    ) -> None:
        """
        Register a fallback strategy for an agent.

        Args:
            agent_name: Name of the agent
            strategy: Function that takes reason string and returns result dict
        """
        with self._lock:
            self._strategies[agent_name] = strategy
        logger.info(f"Registered fallback strategy for {agent_name}")

    def register_synthetic_template(
        self,
        agent_name: str,
        template: Dict[str, Any]
    ) -> None:
        """
        Register a synthetic result template for an agent.

        Args:
            agent_name: Name of the agent
            template: Template dictionary for synthetic results
        """
        with self._lock:
            self._synthetic_templates[agent_name] = {**template, "synthetic": True}
        logger.info(f"Registered synthetic template for {agent_name}")

    def cache_result(
        self,
        agent_name: str,
        result: Dict[str, Any],
        task_hash: str = None,
        ttl: float = None
    ) -> None:
        """
        Cache a successful agent result.

        Args:
            agent_name: Name of the agent
            result: Successful result to cache
            task_hash: Optional hash of the task (for cache key)
            ttl: Optional TTL override
        """
        with self._lock:
            cache_list = self._cache[agent_name]

            # Create cached entry
            cached = CachedResult(
                result=result,
                cached_at=time.time(),
                task_hash=task_hash,
                ttl=ttl or self.cache_ttl
            )

            # Add to cache (most recent first)
            cache_list.insert(0, cached)

            # Trim to max entries
            while len(cache_list) > self.max_cache_entries:
                cache_list.pop()

        logger.debug(f"Cached result for {agent_name}")

    def _get_cached_result(
        self,
        agent_name: str,
        task_hash: str = None,
        max_age: float = None
    ) -> Optional[CachedResult]:
        """Get a cached result if available and valid."""
        with self._lock:
            cache_list = self._cache.get(agent_name, [])

            for cached in cache_list:
                # Check validity
                if not cached.is_valid(max_age):
                    continue

                # If task_hash specified, prefer exact match
                if task_hash and cached.task_hash == task_hash:
                    self._cache_hits += 1
                    return cached

            # Return most recent valid if no exact match
            for cached in cache_list:
                if cached.is_valid(max_age):
                    self._cache_hits += 1
                    return cached

            self._cache_misses += 1
            return None

    async def try_fallback(
        self,
        agent_name: str,
        reason: str,
        task_hash: str = None,
        prefer_cache: bool = True,
        max_cache_age: float = None
    ) -> FallbackResult:
        """
        Try to get a fallback result for a failed agent.

        Order of attempts:
        1. Cache (if prefer_cache and available)
        2. Registered fallback strategy
        3. Synthetic result

        Args:
            agent_name: Name of the failed agent
            reason: Why fallback is needed
            task_hash: Optional task hash for cache lookup
            prefer_cache: Whether to try cache first
            max_cache_age: Maximum age for cached results

        Returns:
            FallbackResult with result and metadata
        """
        logger.info(f"Trying fallback for {agent_name}: {reason}")

        # 1. Try cache first (if preferred)
        if prefer_cache:
            cached = self._get_cached_result(agent_name, task_hash, max_cache_age)
            if cached:
                logger.info(f"Using cached result for {agent_name} (age: {cached.age_seconds:.1f}s)")
                return FallbackResult(
                    result=cached.result,
                    source="cache",
                    reason=reason,
                    age_seconds=cached.age_seconds
                )

        # 2. Try registered fallback strategy
        with self._lock:
            strategy = self._strategies.get(agent_name)

        if strategy:
            try:
                result = strategy(reason)
                # Handle async strategies
                if asyncio.iscoroutine(result):
                    result = await result

                with self._lock:
                    self._fallback_uses += 1

                logger.info(f"Using fallback strategy for {agent_name}")
                return FallbackResult(
                    result=result,
                    source="fallback",
                    reason=reason
                )
            except Exception as e:
                logger.warning(f"Fallback strategy for {agent_name} failed: {e}")

        # 3. Try synthetic result
        if self.enable_synthetic:
            with self._lock:
                template = self._synthetic_templates.get(agent_name)

            if template:
                with self._lock:
                    self._synthetic_uses += 1

                logger.info(f"Using synthetic result for {agent_name}")
                return FallbackResult(
                    result=template.copy(),
                    source="synthetic",
                    reason=reason
                )

        # 4. Last resort: generic synthetic
        logger.warning(f"No fallback available for {agent_name}, using generic synthetic")
        return FallbackResult(
            result={
                "agent": agent_name,
                "error": reason,
                "synthetic": True,
                "fallback_exhausted": True,
            },
            source="synthetic",
            reason=reason
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get fallback statistics."""
        with self._lock:
            total_requests = self._cache_hits + self._cache_misses
            cache_hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

            return {
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_hit_rate": cache_hit_rate,
                "fallback_uses": self._fallback_uses,
                "synthetic_uses": self._synthetic_uses,
                "registered_strategies": list(self._strategies.keys()),
                "cached_agents": list(self._cache.keys()),
                "cache_sizes": {k: len(v) for k, v in self._cache.items()},
            }

    def clear_cache(self, agent_name: str = None) -> int:
        """
        Clear cache entries.

        Args:
            agent_name: Specific agent to clear, or None for all

        Returns:
            Number of entries cleared
        """
        with self._lock:
            if agent_name:
                count = len(self._cache.get(agent_name, []))
                self._cache[agent_name] = []
                return count
            else:
                count = sum(len(v) for v in self._cache.values())
                self._cache.clear()
                return count

    def reset_stats(self) -> None:
        """Reset statistics (for testing)."""
        with self._lock:
            self._cache_hits = 0
            self._cache_misses = 0
            self._fallback_uses = 0
            self._synthetic_uses = 0


class GracefulDegradation:
    """
    Higher-level graceful degradation coordinator.

    Combines fallback registry with status tracking to provide
    degraded service levels when components fail.
    """

    def __init__(self, fallback_registry: FallbackRegistry = None):
        """
        Initialize graceful degradation.

        Args:
            fallback_registry: Fallback registry to use
        """
        self.fallback = fallback_registry or FallbackRegistry()
        self._degraded_agents: Dict[str, str] = {}  # agent -> reason
        self._lock = threading.Lock()

    def mark_degraded(self, agent_name: str, reason: str) -> None:
        """Mark an agent as operating in degraded mode."""
        with self._lock:
            self._degraded_agents[agent_name] = reason
        logger.warning(f"Agent {agent_name} marked as degraded: {reason}")

    def clear_degraded(self, agent_name: str) -> None:
        """Clear degraded status for an agent."""
        with self._lock:
            self._degraded_agents.pop(agent_name, None)
        logger.info(f"Agent {agent_name} no longer degraded")

    def is_degraded(self, agent_name: str = None) -> bool:
        """Check if agent (or system) is degraded."""
        with self._lock:
            if agent_name:
                return agent_name in self._degraded_agents
            return len(self._degraded_agents) > 0

    def get_degraded_agents(self) -> Dict[str, str]:
        """Get all degraded agents and reasons."""
        with self._lock:
            return dict(self._degraded_agents)

    def get_service_level(self) -> str:
        """Get current service level based on degradation."""
        with self._lock:
            count = len(self._degraded_agents)
            if count == 0:
                return "full"
            elif count <= 2:
                return "degraded"
            else:
                return "minimal"

    async def execute_with_degradation(
        self,
        agent_name: str,
        coro: Awaitable[Dict[str, Any]],
        cache_success: bool = True
    ) -> Dict[str, Any]:
        """
        Execute agent with automatic degradation handling.

        Args:
            agent_name: Name of the agent
            coro: Coroutine to execute
            cache_success: Whether to cache successful results

        Returns:
            Agent result (possibly from fallback)
        """
        try:
            result = await coro

            # Cache successful result
            if cache_success:
                self.fallback.cache_result(agent_name, result)

            # Clear any degraded status
            self.clear_degraded(agent_name)

            return result

        except Exception as e:
            reason = str(e)
            self.mark_degraded(agent_name, reason)

            # Try fallback
            fallback_result = await self.fallback.try_fallback(agent_name, reason)
            return fallback_result.to_dict()
