"""
Tests for idempotency management module.

Tests:
- ExecutionStatus enum values
- ExecutionRecord tracking
- IdempotencyManager cache behavior
- Duplicate execution prevention
- Conflict handling
- Retry on failure
- Key generation
- Statistics tracking
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock

from otto.idempotency import (
    ExecutionStatus,
    ExecutionRecord,
    IdempotencyManager,
    IdempotencyConflict,
    generate_idempotency_key,
)


class TestExecutionStatus:
    """Test ExecutionStatus enum."""

    def test_status_values(self):
        """Should have correct status values."""
        assert ExecutionStatus.IN_PROGRESS.value == "in_progress"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"


class TestExecutionRecord:
    """Test ExecutionRecord dataclass."""

    def test_creation(self):
        """Should create record with fields."""
        record = ExecutionRecord(
            key="test-key",
            status=ExecutionStatus.IN_PROGRESS,
            started_at=1000.0,
        )

        assert record.key == "test-key"
        assert record.status == ExecutionStatus.IN_PROGRESS
        assert record.started_at == 1000.0
        assert record.completed_at is None
        assert record.result is None

    def test_age_seconds(self):
        """Should calculate age correctly."""
        record = ExecutionRecord(
            key="key",
            status=ExecutionStatus.COMPLETED,
            started_at=time.time() - 60
        )

        age = record.age_seconds
        assert 59 < age < 62

    def test_is_expired(self):
        """Should detect expired records."""
        old_record = ExecutionRecord(
            key="key",
            status=ExecutionStatus.COMPLETED,
            started_at=time.time() - 7200  # 2 hours ago
        )

        fresh_record = ExecutionRecord(
            key="key",
            status=ExecutionStatus.COMPLETED,
            started_at=time.time()
        )

        assert old_record.is_expired(3600) is True  # 1 hour TTL
        assert fresh_record.is_expired(3600) is False


class TestIdempotencyConflict:
    """Test IdempotencyConflict exception."""

    def test_creation(self):
        """Should create conflict with details."""
        exc = IdempotencyConflict("op-key", 1000.0)

        assert exc.key == "op-key"
        assert exc.started_at == 1000.0
        assert "op-key" in str(exc)


class TestIdempotencyManagerBasic:
    """Test basic IdempotencyManager functionality."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        manager = IdempotencyManager()

        assert manager.retention_seconds == 3600.0
        assert manager.max_entries == 10000
        assert manager.allow_retry_on_error is True
        assert manager.in_progress_timeout == 300.0

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        manager = IdempotencyManager(
            retention_seconds=1800.0,
            max_entries=5000,
            allow_retry_on_error=False,
            in_progress_timeout=60.0
        )

        assert manager.retention_seconds == 1800.0
        assert manager.max_entries == 5000
        assert manager.allow_retry_on_error is False


class TestIdempotencyManagerExecution:
    """Test execute_idempotent functionality."""

    @pytest.mark.asyncio
    async def test_execute_sync_function(self):
        """Should execute sync function."""
        manager = IdempotencyManager()

        def sync_func():
            return "sync_result"

        result = await manager.execute_idempotent("key1", sync_func)

        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_execute_async_function(self):
        """Should execute async function."""
        manager = IdempotencyManager()

        async def async_func():
            return "async_result"

        result = await manager.execute_idempotent("key2", async_func)

        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_returns_cached_result(self):
        """Should return cached result on second call."""
        manager = IdempotencyManager()
        call_count = [0]

        def counting_func():
            call_count[0] += 1
            return f"result_{call_count[0]}"

        # First call
        result1 = await manager.execute_idempotent("key3", counting_func)
        # Second call with same key
        result2 = await manager.execute_idempotent("key3", counting_func)

        assert result1 == "result_1"
        assert result2 == "result_1"  # Cached result
        assert call_count[0] == 1  # Only called once

    @pytest.mark.asyncio
    async def test_force_execute_bypasses_cache(self):
        """Should re-execute when force_execute=True."""
        manager = IdempotencyManager()
        call_count = [0]

        def counting_func():
            call_count[0] += 1
            return f"result_{call_count[0]}"

        # First call
        await manager.execute_idempotent("key4", counting_func)
        # Force re-execute
        result2 = await manager.execute_idempotent("key4", counting_func, force_execute=True)

        assert result2 == "result_2"
        assert call_count[0] == 2


class TestIdempotencyManagerFailure:
    """Test failure handling."""

    @pytest.mark.asyncio
    async def test_records_failure(self):
        """Should record failed execution."""
        manager = IdempotencyManager()

        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await manager.execute_idempotent("fail_key", failing_func)

        status = manager.get_status("fail_key")
        assert status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_retry_on_failure_allowed(self):
        """Should allow retry when allow_retry_on_error=True."""
        manager = IdempotencyManager(allow_retry_on_error=True)
        call_count = [0]

        def eventually_succeeds():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("first attempt fails")
            return "success"

        # First call fails
        with pytest.raises(ValueError):
            await manager.execute_idempotent("retry_key", eventually_succeeds)

        # Second call should retry and succeed
        result = await manager.execute_idempotent("retry_key", eventually_succeeds)

        assert result == "success"
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_retry_on_failure_disabled(self):
        """Should not retry when allow_retry_on_error=False."""
        manager = IdempotencyManager(allow_retry_on_error=False)

        def failing_func():
            raise ValueError("permanent failure")

        # First call fails
        with pytest.raises(ValueError):
            await manager.execute_idempotent("no_retry_key", failing_func)

        # Second call should raise without retrying
        with pytest.raises(Exception) as exc_info:
            await manager.execute_idempotent("no_retry_key", lambda: "never called")

        assert "Previous execution failed" in str(exc_info.value)


class TestIdempotencyManagerConcurrency:
    """Test concurrent execution handling."""

    @pytest.mark.asyncio
    async def test_concurrent_same_key_second_waits(self):
        """Second concurrent call should wait for first to complete."""
        manager = IdempotencyManager()
        execution_order = []

        async def slow_func():
            execution_order.append("started")
            await asyncio.sleep(0.1)
            execution_order.append("completed")
            return "result"

        # Start two concurrent executions
        task1 = asyncio.create_task(
            manager.execute_idempotent("concurrent_key", slow_func)
        )
        await asyncio.sleep(0.01)  # Let first start
        task2 = asyncio.create_task(
            manager.execute_idempotent("concurrent_key", slow_func)
        )

        results = await asyncio.gather(task1, task2)

        # Both should get same result
        assert results[0] == "result"
        assert results[1] == "result"
        # Function should only be called once (second gets cached result)
        assert execution_order.count("started") == 1


class TestIdempotencyManagerStatus:
    """Test status retrieval."""

    @pytest.mark.asyncio
    async def test_get_status_completed(self):
        """Should return COMPLETED for finished operation."""
        manager = IdempotencyManager()

        await manager.execute_idempotent("status_key", lambda: "result")

        status = manager.get_status("status_key")
        assert status == ExecutionStatus.COMPLETED

    def test_get_status_nonexistent(self):
        """Should return None for unknown key."""
        manager = IdempotencyManager()

        status = manager.get_status("unknown_key")
        assert status is None

    @pytest.mark.asyncio
    async def test_get_result(self):
        """Should return result for completed operation."""
        manager = IdempotencyManager()

        await manager.execute_idempotent("result_key", lambda: {"data": "value"})

        result = manager.get_result("result_key")
        assert result == {"data": "value"}

    def test_get_result_nonexistent(self):
        """Should return None for unknown key."""
        manager = IdempotencyManager()

        result = manager.get_result("unknown")
        assert result is None


class TestIdempotencyManagerInvalidation:
    """Test cache invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate(self):
        """Should invalidate cached result."""
        manager = IdempotencyManager()

        await manager.execute_idempotent("inv_key", lambda: "first")

        removed = manager.invalidate("inv_key")
        assert removed is True

        status = manager.get_status("inv_key")
        assert status is None

    def test_invalidate_nonexistent(self):
        """Should return False for unknown key."""
        manager = IdempotencyManager()

        removed = manager.invalidate("unknown")
        assert removed is False


class TestIdempotencyManagerStats:
    """Test statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Should track cache hits and misses."""
        manager = IdempotencyManager()

        # Miss
        await manager.execute_idempotent("stats_key", lambda: "result")
        # Hit
        await manager.execute_idempotent("stats_key", lambda: "result")
        # Another miss
        await manager.execute_idempotent("stats_key2", lambda: "result2")

        stats = manager.get_stats()

        assert stats["cache_misses"] == 2
        assert stats["cache_hits"] == 1
        assert stats["total_entries"] == 2

    @pytest.mark.asyncio
    async def test_stats_status_counts(self):
        """Should count statuses."""
        manager = IdempotencyManager()

        await manager.execute_idempotent("ok1", lambda: "ok")
        await manager.execute_idempotent("ok2", lambda: "ok")

        try:
            await manager.execute_idempotent("fail1", lambda: (_ for _ in ()).throw(ValueError()))
        except ValueError:
            pass

        stats = manager.get_stats()

        assert stats["status_counts"]["completed"] == 2
        assert stats["status_counts"]["failed"] == 1


class TestIdempotencyManagerClear:
    """Test clearing functionality."""

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Should clear all records."""
        manager = IdempotencyManager()

        await manager.execute_idempotent("key1", lambda: "1")
        await manager.execute_idempotent("key2", lambda: "2")
        await manager.execute_idempotent("key3", lambda: "3")

        count = manager.clear()

        assert count == 3
        assert manager.get_stats()["total_entries"] == 0


class TestIdempotencyManagerCleanup:
    """Test automatic cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Should clean up expired entries."""
        manager = IdempotencyManager(retention_seconds=0.1)

        await manager.execute_idempotent("expire_key", lambda: "result")

        # Wait for expiration
        await asyncio.sleep(0.2)

        # Get should trigger cleanup
        result = manager._get_record("expire_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_over_max(self):
        """Should clean up when over max_entries."""
        manager = IdempotencyManager(max_entries=3)

        for i in range(5):
            await manager.execute_idempotent(f"max_key_{i}", lambda: f"result_{i}")

        stats = manager.get_stats()
        assert stats["total_entries"] <= 3


class TestIdempotencyManagerTimeout:
    """Test in-progress timeout handling."""

    @pytest.mark.asyncio
    async def test_in_progress_timeout(self):
        """Should mark timed-out in-progress as failed."""
        manager = IdempotencyManager(in_progress_timeout=0.1)

        # Manually create an old in-progress record
        manager._executions["timeout_key"] = ExecutionRecord(
            key="timeout_key",
            status=ExecutionStatus.IN_PROGRESS,
            started_at=time.time() - 1.0  # 1 second ago, past 0.1s timeout
        )

        # Get should detect timeout
        record = manager._get_record("timeout_key")

        assert record.status == ExecutionStatus.FAILED
        assert "Timed out" in record.error


class TestGenerateIdempotencyKey:
    """Test key generation function."""

    def test_generates_deterministic_key(self):
        """Should generate same key for same inputs."""
        key1 = generate_idempotency_key("agent", "task", 1)
        key2 = generate_idempotency_key("agent", "task", 1)

        assert key1 == key2

    def test_different_inputs_different_keys(self):
        """Should generate different keys for different inputs."""
        key1 = generate_idempotency_key("agent1", "task", 1)
        key2 = generate_idempotency_key("agent2", "task", 1)
        key3 = generate_idempotency_key("agent1", "task", 2)

        assert key1 != key2
        assert key1 != key3

    def test_key_length(self):
        """Should generate 32-character key."""
        key = generate_idempotency_key("agent", "task", 1)

        assert len(key) == 32

    def test_key_with_extra(self):
        """Should include extra data in key generation."""
        key1 = generate_idempotency_key("agent", "task", 1, extra={"mode": "test"})
        key2 = generate_idempotency_key("agent", "task", 1, extra={"mode": "prod"})

        assert key1 != key2

