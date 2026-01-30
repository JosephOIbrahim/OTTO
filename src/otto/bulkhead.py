"""
Bulkhead pattern for agent isolation in Framework Orchestrator.

Implements resource isolation to prevent one agent from starving others:
- Semaphore-based global concurrency control
- Per-agent queue depth limits
- Rejection when overloaded

The bulkhead pattern is named after ship bulkheads that prevent water
from flooding the entire ship if one compartment is breached.

References:
    [1] Nygard, M.T. (2007). "Release It! Design and Deploy Production-Ready Software"
        Pragmatic Bookshelf. ISBN: 978-0978739218
        - Bulkhead pattern (Chapter 5: Stability Patterns)
        - Named after ship compartmentalization to prevent cascading failures

Usage:
    bulkhead = BulkheadExecutor(max_concurrent=3, queue_size_per_agent=10)

    # Execute with isolation
    result = await bulkhead.execute_isolated(
        "moe_router",
        agent.execute(task, context)
    )

    # Check queue depth
    depth = bulkhead.get_queue_depth("moe_router")
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Awaitable
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class BulkheadRejected(Exception):
    """Raised when bulkhead rejects a request due to overload."""

    def __init__(self, agent_name: str, reason: str):
        self.agent_name = agent_name
        self.reason = reason
        super().__init__(f"Bulkhead rejected '{agent_name}': {reason}")


class BulkheadTimeout(Exception):
    """Raised when waiting for bulkhead times out."""

    def __init__(self, agent_name: str, timeout: float):
        self.agent_name = agent_name
        self.timeout = timeout
        super().__init__(f"Timeout waiting for bulkhead slot for '{agent_name}' after {timeout}s")


@dataclass
class BulkheadStats:
    """Statistics for bulkhead monitoring."""

    total_executed: int = 0
    total_rejected: int = 0
    total_timeouts: int = 0
    current_executing: int = 0
    max_concurrent_reached: int = 0
    queue_rejections: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


class BulkheadExecutor:
    """
    Resource isolation per agent using the bulkhead pattern.

    Prevents one agent from starving others by:
    1. Limiting global concurrent executions
    2. Limiting per-agent queue depth
    3. Rejecting requests when overloaded

    Thread-safe for concurrent access.
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        queue_size_per_agent: int = 10,
        acquire_timeout: float = 30.0,
        track_memory: bool = False
    ):
        """
        Initialize bulkhead executor.

        Args:
            max_concurrent: Maximum concurrent executions across all agents
            queue_size_per_agent: Maximum queued requests per agent
            acquire_timeout: Timeout for acquiring semaphore slot
            track_memory: Whether to track memory usage (adds overhead)
        """
        self.max_concurrent = max_concurrent
        self.queue_size_per_agent = queue_size_per_agent
        self.acquire_timeout = acquire_timeout
        self.track_memory = track_memory

        # Global semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Per-agent tracking
        self._agent_queues: Dict[str, int] = defaultdict(int)
        self._agent_executing: Dict[str, int] = defaultdict(int)

        # Statistics
        self._stats = BulkheadStats()

        # Thread safety
        self._lock = threading.Lock()

        logger.info(
            f"BulkheadExecutor initialized: max_concurrent={max_concurrent}, "
            f"queue_size_per_agent={queue_size_per_agent}"
        )

    def _check_queue_limit(self, agent_name: str) -> bool:
        """Check if agent queue is at capacity."""
        with self._lock:
            current = self._agent_queues.get(agent_name, 0)
            return current < self.queue_size_per_agent

    def _increment_queue(self, agent_name: str) -> None:
        """Increment agent queue count."""
        with self._lock:
            self._agent_queues[agent_name] += 1

    def _decrement_queue(self, agent_name: str) -> None:
        """Decrement agent queue count."""
        with self._lock:
            self._agent_queues[agent_name] = max(0, self._agent_queues.get(agent_name, 1) - 1)

    def _increment_executing(self, agent_name: str) -> None:
        """Mark agent as executing."""
        with self._lock:
            self._agent_executing[agent_name] += 1
            self._stats.current_executing += 1
            self._stats.max_concurrent_reached = max(
                self._stats.max_concurrent_reached,
                self._stats.current_executing
            )

    def _decrement_executing(self, agent_name: str) -> None:
        """Mark agent as done executing."""
        with self._lock:
            self._agent_executing[agent_name] = max(0, self._agent_executing.get(agent_name, 1) - 1)
            self._stats.current_executing = max(0, self._stats.current_executing - 1)

    async def execute_isolated(
        self,
        agent_name: str,
        coro: Awaitable[Any],
        timeout: Optional[float] = None
    ) -> Any:
        """
        Execute a coroutine with bulkhead isolation.

        Args:
            agent_name: Name of the agent (for queue tracking)
            coro: Coroutine to execute
            timeout: Override timeout for semaphore acquisition

        Returns:
            Result from the coroutine

        Raises:
            BulkheadRejected: If queue is full
            BulkheadTimeout: If timeout waiting for slot
        """
        timeout = timeout or self.acquire_timeout

        # Check queue limit before even trying to acquire
        if not self._check_queue_limit(agent_name):
            with self._lock:
                self._stats.total_rejected += 1
                self._stats.queue_rejections[agent_name] += 1
            logger.warning(f"Bulkhead rejected {agent_name}: queue full ({self.queue_size_per_agent})")
            raise BulkheadRejected(
                agent_name,
                f"Queue full (max {self.queue_size_per_agent})"
            )

        # Add to queue
        self._increment_queue(agent_name)

        try:
            # Try to acquire semaphore with timeout
            acquired = False
            start_time = time.time()

            try:
                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=timeout
                )
                acquired = True
            except asyncio.TimeoutError:
                with self._lock:
                    self._stats.total_timeouts += 1
                logger.warning(f"Bulkhead timeout for {agent_name} after {timeout}s")
                raise BulkheadTimeout(agent_name, timeout)

            # Mark as executing
            self._increment_executing(agent_name)
            wait_time = time.time() - start_time

            if wait_time > 1.0:
                logger.info(f"Agent {agent_name} waited {wait_time:.2f}s for bulkhead slot")

            try:
                # Execute the coroutine
                result = await coro

                # Record success
                with self._lock:
                    self._stats.total_executed += 1

                return result

            finally:
                # Mark as done executing
                self._decrement_executing(agent_name)

        finally:
            # Remove from queue
            self._decrement_queue(agent_name)

            # Release semaphore if acquired
            if acquired:
                self._semaphore.release()

    async def execute_with_priority(
        self,
        agent_name: str,
        coro: Awaitable[Any],
        priority: int = 5,
        timeout: Optional[float] = None
    ) -> Any:
        """
        Execute with priority (lower number = higher priority).

        Currently implements simple priority by adjusting timeout.
        Higher priority tasks get longer timeout to wait.

        Args:
            agent_name: Name of the agent
            coro: Coroutine to execute
            priority: Priority level (1-10, lower = higher priority)
            timeout: Base timeout

        Returns:
            Result from the coroutine
        """
        # Adjust timeout based on priority (higher priority gets more patience)
        base_timeout = timeout or self.acquire_timeout
        priority_multiplier = (11 - priority) / 5  # Range: 0.2 to 2.0
        adjusted_timeout = base_timeout * priority_multiplier

        return await self.execute_isolated(agent_name, coro, timeout=adjusted_timeout)

    def get_queue_depth(self, agent_name: str) -> int:
        """Get current queue depth for an agent."""
        with self._lock:
            return self._agent_queues.get(agent_name, 0)

    def get_executing_count(self, agent_name: str) -> int:
        """Get number of currently executing instances for an agent."""
        with self._lock:
            return self._agent_executing.get(agent_name, 0)

    def get_total_executing(self) -> int:
        """Get total number of currently executing agents."""
        with self._lock:
            return self._stats.current_executing

    def get_available_slots(self) -> int:
        """Get number of available execution slots."""
        return self.max_concurrent - self.get_total_executing()

    def get_stats(self) -> Dict[str, Any]:
        """Get bulkhead statistics."""
        with self._lock:
            return {
                "total_executed": self._stats.total_executed,
                "total_rejected": self._stats.total_rejected,
                "total_timeouts": self._stats.total_timeouts,
                "current_executing": self._stats.current_executing,
                "max_concurrent_reached": self._stats.max_concurrent_reached,
                "available_slots": self.max_concurrent - self._stats.current_executing,
                "queue_depths": dict(self._agent_queues),
                "executing_counts": dict(self._agent_executing),
                "queue_rejections": dict(self._stats.queue_rejections),
            }

    def is_healthy(self) -> bool:
        """Check if bulkhead is operating normally."""
        with self._lock:
            # Unhealthy if rejection rate is high
            if self._stats.total_executed > 0:
                rejection_rate = self._stats.total_rejected / (
                    self._stats.total_executed + self._stats.total_rejected
                )
                return rejection_rate < 0.5  # Unhealthy if >50% rejected
            return True

    def reset_stats(self) -> None:
        """Reset statistics (for testing)."""
        with self._lock:
            self._stats = BulkheadStats()


class AdaptiveBulkhead(BulkheadExecutor):
    """
    Adaptive bulkhead that adjusts limits based on system load.

    Monitors success/failure rates and adjusts:
    - max_concurrent: Based on throughput
    - queue_size: Based on wait times

    Use when load patterns vary significantly.
    """

    def __init__(
        self,
        initial_concurrent: int = 3,
        min_concurrent: int = 1,
        max_concurrent: int = 10,
        queue_size_per_agent: int = 10,
        adaptation_interval: float = 60.0,
        **kwargs
    ):
        """
        Initialize adaptive bulkhead.

        Args:
            initial_concurrent: Starting concurrency limit
            min_concurrent: Minimum concurrency limit
            max_concurrent: Maximum concurrency limit
            queue_size_per_agent: Queue size per agent
            adaptation_interval: Seconds between adaptations
        """
        super().__init__(
            max_concurrent=initial_concurrent,
            queue_size_per_agent=queue_size_per_agent,
            **kwargs
        )
        self.min_concurrent = min_concurrent
        self.max_concurrent_limit = max_concurrent
        self.adaptation_interval = adaptation_interval

        self._last_adaptation = time.time()
        self._success_count = 0
        self._failure_count = 0

    def _maybe_adapt(self) -> None:
        """Check if adaptation is needed and apply."""
        now = time.time()
        if now - self._last_adaptation < self.adaptation_interval:
            return

        with self._lock:
            total = self._success_count + self._failure_count
            if total == 0:
                return

            success_rate = self._success_count / total

            # Adapt concurrency based on success rate
            current = self.max_concurrent

            if success_rate > 0.95 and current < self.max_concurrent_limit:
                # High success rate, try increasing
                new_limit = min(current + 1, self.max_concurrent_limit)
                logger.info(f"Bulkhead adapting: {current} -> {new_limit} (success_rate={success_rate:.2%})")
                self._semaphore = asyncio.Semaphore(new_limit)
                self.max_concurrent = new_limit
            elif success_rate < 0.8 and current > self.min_concurrent:
                # Low success rate, reduce
                new_limit = max(current - 1, self.min_concurrent)
                logger.info(f"Bulkhead adapting: {current} -> {new_limit} (success_rate={success_rate:.2%})")
                self._semaphore = asyncio.Semaphore(new_limit)
                self.max_concurrent = new_limit

            # Reset counters
            self._success_count = 0
            self._failure_count = 0
            self._last_adaptation = now

    async def execute_isolated(
        self,
        agent_name: str,
        coro: Awaitable[Any],
        timeout: Optional[float] = None
    ) -> Any:
        """Execute with adaptive behavior."""
        self._maybe_adapt()

        try:
            result = await super().execute_isolated(agent_name, coro, timeout)
            with self._lock:
                self._success_count += 1
            return result
        except Exception:
            with self._lock:
                self._failure_count += 1
            raise
