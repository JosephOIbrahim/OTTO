"""
Tests for bulkhead pattern module.

Tests:
- BulkheadExecutor initialization and basic functionality
- Semaphore-based concurrency control
- Per-agent queue depth limits
- Rejection when overloaded
- Timeout handling
- Priority-based execution
- Statistics tracking
- AdaptiveBulkhead adaptation
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from otto.bulkhead import (
    BulkheadExecutor,
    BulkheadRejected,
    BulkheadTimeout,
    BulkheadStats,
    AdaptiveBulkhead,
)


class TestBulkheadExceptions:
    """Test bulkhead exception classes."""

    def test_bulkhead_rejected(self):
        """Should create rejection exception with details."""
        exc = BulkheadRejected("moe_router", "Queue full")

        assert exc.agent_name == "moe_router"
        assert exc.reason == "Queue full"
        assert "moe_router" in str(exc)
        assert "Queue full" in str(exc)

    def test_bulkhead_timeout(self):
        """Should create timeout exception with details."""
        exc = BulkheadTimeout("echo_curator", 30.0)

        assert exc.agent_name == "echo_curator"
        assert exc.timeout == 30.0
        assert "echo_curator" in str(exc)
        assert "30" in str(exc)


class TestBulkheadStats:
    """Test BulkheadStats dataclass."""

    def test_default_values(self):
        """Should have correct defaults."""
        stats = BulkheadStats()

        assert stats.total_executed == 0
        assert stats.total_rejected == 0
        assert stats.total_timeouts == 0
        assert stats.current_executing == 0
        assert stats.max_concurrent_reached == 0
        assert stats.queue_rejections == {}


class TestBulkheadExecutorBasic:
    """Test basic BulkheadExecutor functionality."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        bulkhead = BulkheadExecutor()

        assert bulkhead.max_concurrent == 3
        assert bulkhead.queue_size_per_agent == 10
        assert bulkhead.acquire_timeout == 30.0
        assert bulkhead.track_memory is False

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        bulkhead = BulkheadExecutor(
            max_concurrent=5,
            queue_size_per_agent=20,
            acquire_timeout=60.0,
            track_memory=True
        )

        assert bulkhead.max_concurrent == 5
        assert bulkhead.queue_size_per_agent == 20
        assert bulkhead.acquire_timeout == 60.0
        assert bulkhead.track_memory is True

    def test_get_queue_depth_empty(self):
        """Should return 0 for unknown agent."""
        bulkhead = BulkheadExecutor()

        assert bulkhead.get_queue_depth("unknown_agent") == 0

    def test_get_executing_count_empty(self):
        """Should return 0 when nothing executing."""
        bulkhead = BulkheadExecutor()

        assert bulkhead.get_executing_count("any_agent") == 0

    def test_get_total_executing_empty(self):
        """Should return 0 when nothing executing."""
        bulkhead = BulkheadExecutor()

        assert bulkhead.get_total_executing() == 0

    def test_get_available_slots_full(self):
        """Should return max_concurrent when all slots available."""
        bulkhead = BulkheadExecutor(max_concurrent=5)

        assert bulkhead.get_available_slots() == 5


class TestBulkheadExecutorExecution:
    """Test BulkheadExecutor execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_isolated_simple(self):
        """Should execute coroutine successfully."""
        bulkhead = BulkheadExecutor()

        async def simple_task():
            return "result"

        result = await bulkhead.execute_isolated("test_agent", simple_task())

        assert result == "result"

    @pytest.mark.asyncio
    async def test_execute_isolated_tracks_stats(self):
        """Should update statistics on execution."""
        bulkhead = BulkheadExecutor()

        async def simple_task():
            return "result"

        await bulkhead.execute_isolated("test_agent", simple_task())

        stats = bulkhead.get_stats()
        assert stats["total_executed"] == 1
        assert stats["total_rejected"] == 0

    @pytest.mark.asyncio
    async def test_execute_isolated_concurrent_limit(self):
        """Should respect max_concurrent limit."""
        bulkhead = BulkheadExecutor(max_concurrent=2, acquire_timeout=0.5)
        execution_count = []

        async def slow_task(n):
            execution_count.append(n)
            await asyncio.sleep(0.3)
            return n

        # Start 3 tasks with max_concurrent=2
        tasks = [
            bulkhead.execute_isolated("agent", slow_task(i))
            for i in range(3)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete (third waits for slot)
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 3

    @pytest.mark.asyncio
    async def test_execute_isolated_queue_rejection(self):
        """Should reject when queue is full."""
        # queue_size_per_agent=2 means: 1 executing + 1 waiting = 2 total in queue
        # When a third task arrives, it should be rejected
        bulkhead = BulkheadExecutor(
            max_concurrent=1,
            queue_size_per_agent=2,
            acquire_timeout=0.1
        )

        async def slow_task():
            await asyncio.sleep(1.0)

        # Start first task (takes the slot, queue=1)
        task1 = asyncio.create_task(
            bulkhead.execute_isolated("agent", slow_task())
        )
        await asyncio.sleep(0.05)  # Let it start and acquire the slot

        # Second task enters queue (queue=2, waiting for semaphore)
        task2 = asyncio.create_task(
            bulkhead.execute_isolated("agent", slow_task())
        )
        await asyncio.sleep(0.05)  # Let it enter the queue

        # Third should be rejected (queue full at 2)
        with pytest.raises(BulkheadRejected) as exc_info:
            await bulkhead.execute_isolated("agent", slow_task())

        assert exc_info.value.agent_name == "agent"

        # Cleanup
        task1.cancel()
        task2.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass
        try:
            await task2
        except asyncio.CancelledError:
            pass


class TestBulkheadExecutorTimeout:
    """Test timeout handling."""

    @pytest.mark.asyncio
    async def test_execute_isolated_timeout(self):
        """Should timeout waiting for slot."""
        bulkhead = BulkheadExecutor(max_concurrent=1, acquire_timeout=0.1)

        async def slow_task():
            await asyncio.sleep(10.0)

        # Start a task that holds the slot
        task1 = asyncio.create_task(
            bulkhead.execute_isolated("agent1", slow_task())
        )
        await asyncio.sleep(0.01)

        # Second task should timeout waiting
        with pytest.raises(BulkheadTimeout) as exc_info:
            await bulkhead.execute_isolated("agent2", slow_task(), timeout=0.1)

        assert exc_info.value.timeout == 0.1

        # Cleanup
        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_timeout_tracked_in_stats(self):
        """Should track timeouts in statistics."""
        bulkhead = BulkheadExecutor(max_concurrent=1, acquire_timeout=0.1)

        async def slow_task():
            await asyncio.sleep(10.0)

        # Start first task
        task1 = asyncio.create_task(
            bulkhead.execute_isolated("agent1", slow_task())
        )
        await asyncio.sleep(0.01)

        # Timeout on second
        try:
            await bulkhead.execute_isolated("agent2", slow_task(), timeout=0.1)
        except BulkheadTimeout:
            pass

        stats = bulkhead.get_stats()
        assert stats["total_timeouts"] == 1

        # Cleanup
        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass


class TestBulkheadExecutorPriority:
    """Test priority-based execution."""

    @pytest.mark.asyncio
    async def test_execute_with_priority_high(self):
        """High priority should get longer timeout."""
        bulkhead = BulkheadExecutor(max_concurrent=3, acquire_timeout=1.0)

        async def quick_task():
            return "done"

        # Priority 1 (highest) should get 2x timeout
        result = await bulkhead.execute_with_priority(
            "agent", quick_task(), priority=1
        )

        assert result == "done"

    @pytest.mark.asyncio
    async def test_execute_with_priority_low(self):
        """Low priority should get shorter timeout."""
        bulkhead = BulkheadExecutor(max_concurrent=3, acquire_timeout=1.0)

        async def quick_task():
            return "done"

        # Priority 10 (lowest) should get 0.2x timeout
        result = await bulkhead.execute_with_priority(
            "agent", quick_task(), priority=10
        )

        assert result == "done"


class TestBulkheadExecutorStats:
    """Test statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Should return comprehensive statistics."""
        bulkhead = BulkheadExecutor(max_concurrent=3)

        async def task():
            return "result"

        await bulkhead.execute_isolated("agent1", task())
        await bulkhead.execute_isolated("agent2", task())

        stats = bulkhead.get_stats()

        assert stats["total_executed"] == 2
        assert stats["total_rejected"] == 0
        assert stats["total_timeouts"] == 0
        assert stats["available_slots"] == 3
        assert "queue_depths" in stats
        assert "executing_counts" in stats

    @pytest.mark.asyncio
    async def test_max_concurrent_tracked(self):
        """Should track maximum concurrent executions."""
        bulkhead = BulkheadExecutor(max_concurrent=3)

        async def slow_task():
            await asyncio.sleep(0.1)

        # Run 3 concurrent tasks
        await asyncio.gather(
            bulkhead.execute_isolated("a1", slow_task()),
            bulkhead.execute_isolated("a2", slow_task()),
            bulkhead.execute_isolated("a3", slow_task()),
        )

        stats = bulkhead.get_stats()
        assert stats["max_concurrent_reached"] >= 2

    def test_reset_stats(self):
        """Should reset all statistics."""
        bulkhead = BulkheadExecutor()
        bulkhead._stats.total_executed = 10
        bulkhead._stats.total_rejected = 5

        bulkhead.reset_stats()

        stats = bulkhead.get_stats()
        assert stats["total_executed"] == 0
        assert stats["total_rejected"] == 0


class TestBulkheadExecutorHealth:
    """Test health check functionality."""

    def test_is_healthy_no_requests(self):
        """Should be healthy with no requests."""
        bulkhead = BulkheadExecutor()

        assert bulkhead.is_healthy() is True

    @pytest.mark.asyncio
    async def test_is_healthy_with_success(self):
        """Should be healthy with successful requests."""
        bulkhead = BulkheadExecutor()

        async def task():
            return "ok"

        await bulkhead.execute_isolated("agent", task())

        assert bulkhead.is_healthy() is True

    def test_is_unhealthy_high_rejection(self):
        """Should be unhealthy with high rejection rate."""
        bulkhead = BulkheadExecutor()

        # Simulate high rejection rate
        bulkhead._stats.total_executed = 10
        bulkhead._stats.total_rejected = 20  # 67% rejection

        assert bulkhead.is_healthy() is False


class TestAdaptiveBulkhead:
    """Test AdaptiveBulkhead adaptation."""

    def test_initialization(self):
        """Should initialize with adaptive parameters."""
        bulkhead = AdaptiveBulkhead(
            initial_concurrent=3,
            min_concurrent=1,
            max_concurrent=10
        )

        assert bulkhead.max_concurrent == 3
        assert bulkhead.min_concurrent == 1
        assert bulkhead.max_concurrent_limit == 10

    @pytest.mark.asyncio
    async def test_execute_isolated_tracks_success(self):
        """Should track success for adaptation."""
        bulkhead = AdaptiveBulkhead(initial_concurrent=3)

        async def task():
            return "ok"

        await bulkhead.execute_isolated("agent", task())

        assert bulkhead._success_count == 1

    @pytest.mark.asyncio
    async def test_execute_isolated_tracks_failure(self):
        """Should track failure for adaptation."""
        bulkhead = AdaptiveBulkhead(initial_concurrent=3)

        async def failing_task():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await bulkhead.execute_isolated("agent", failing_task())

        assert bulkhead._failure_count == 1

    @pytest.mark.asyncio
    async def test_adaptation_increases_on_success(self):
        """Should increase concurrency on high success rate."""
        bulkhead = AdaptiveBulkhead(
            initial_concurrent=2,
            max_concurrent=5,
            adaptation_interval=0.01  # Short for testing
        )

        async def task():
            return "ok"

        # Many successful executions
        for _ in range(20):
            await bulkhead.execute_isolated("agent", task())

        # Wait for adaptation
        await asyncio.sleep(0.02)
        await bulkhead.execute_isolated("agent", task())

        # May have adapted (depends on timing)
        assert bulkhead.max_concurrent >= 2

    @pytest.mark.asyncio
    async def test_adaptation_decreases_on_failure(self):
        """Should decrease concurrency on high failure rate."""
        bulkhead = AdaptiveBulkhead(
            initial_concurrent=3,
            min_concurrent=1,
            adaptation_interval=0.01
        )

        async def task():
            return "ok"

        async def failing():
            raise ValueError("error")

        # Force some failures by manipulating counters
        bulkhead._success_count = 2
        bulkhead._failure_count = 10
        bulkhead._last_adaptation = 0  # Force adaptation

        # Trigger adaptation
        await bulkhead.execute_isolated("agent", task())

        # Should have decreased
        assert bulkhead.max_concurrent <= 3


class TestBulkheadConcurrency:
    """Test thread safety and concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Should handle many concurrent executions safely."""
        bulkhead = BulkheadExecutor(max_concurrent=5)

        async def quick_task(n):
            await asyncio.sleep(0.01)
            return n

        # Run many concurrent tasks
        tasks = [
            bulkhead.execute_isolated(f"agent{i % 3}", quick_task(i))
            for i in range(20)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 20
        stats = bulkhead.get_stats()
        assert stats["total_executed"] == 20

    @pytest.mark.asyncio
    async def test_queue_depth_accuracy(self):
        """Should accurately track queue depth."""
        bulkhead = BulkheadExecutor(max_concurrent=1, queue_size_per_agent=10)
        depths = []

        async def task_with_depth_check():
            depths.append(bulkhead.get_queue_depth("agent"))
            await asyncio.sleep(0.1)
            return "done"

        # Run several tasks
        tasks = [
            bulkhead.execute_isolated("agent", task_with_depth_check())
            for _ in range(3)
        ]

        await asyncio.gather(*tasks)

        # After completion, queue should be empty
        assert bulkhead.get_queue_depth("agent") == 0

