"""
Tests for lifecycle management module.

Tests:
- Lifecycle state transitions
- Shutdown handler registration and execution
- Signal handling setup
- Graceful shutdown with timeout
- Task tracking
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from otto.lifecycle import (
    LifecycleManager,
    LifecycleState,
    ShutdownContext,
    run_with_lifecycle,
)


class TestLifecycleState:
    """Test LifecycleState enum."""

    def test_state_values(self):
        """Should have correct state values."""
        assert LifecycleState.STARTING.value == "starting"
        assert LifecycleState.RUNNING.value == "running"
        assert LifecycleState.SHUTTING_DOWN.value == "shutting_down"
        assert LifecycleState.STOPPED.value == "stopped"


class TestShutdownContext:
    """Test ShutdownContext dataclass."""

    def test_default_values(self):
        """Should have correct defaults."""
        ctx = ShutdownContext()

        assert ctx.signal_received is None
        assert ctx.reason == "unknown"
        assert ctx.timeout == 10.0
        assert ctx.state_to_save is None

    def test_custom_values(self):
        """Should accept custom values."""
        ctx = ShutdownContext(
            signal_received="SIGTERM",
            reason="user_request",
            timeout=30.0,
            state_to_save={"key": "value"}
        )

        assert ctx.signal_received == "SIGTERM"
        assert ctx.reason == "user_request"
        assert ctx.timeout == 30.0
        assert ctx.state_to_save == {"key": "value"}


class TestLifecycleManager:
    """Test LifecycleManager class."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        lifecycle = LifecycleManager()

        assert lifecycle.state == LifecycleState.STARTING
        assert lifecycle.shutdown_timeout == 10.0
        assert lifecycle.handler_timeout == 5.0

    def test_custom_timeout(self):
        """Should accept custom timeout."""
        lifecycle = LifecycleManager(shutdown_timeout=30.0, handler_timeout=10.0)

        assert lifecycle.shutdown_timeout == 30.0
        assert lifecycle.handler_timeout == 10.0

    def test_is_running(self):
        """Should correctly report running state."""
        lifecycle = LifecycleManager()

        assert lifecycle.is_running is False
        lifecycle.mark_running()
        assert lifecycle.is_running is True

    def test_is_shutting_down(self):
        """Should correctly report shutting down state."""
        lifecycle = LifecycleManager()

        assert lifecycle.is_shutting_down is False
        lifecycle.state = LifecycleState.SHUTTING_DOWN
        assert lifecycle.is_shutting_down is True

    def test_is_stopped(self):
        """Should correctly report stopped state."""
        lifecycle = LifecycleManager()

        assert lifecycle.is_stopped is False
        lifecycle.state = LifecycleState.STOPPED
        assert lifecycle.is_stopped is True


class TestLifecycleShutdownHandlers:
    """Test shutdown handler registration and execution."""

    @pytest.mark.asyncio
    async def test_register_shutdown_handler(self):
        """Should register async shutdown handlers."""
        lifecycle = LifecycleManager()
        handler = AsyncMock()

        lifecycle.register_shutdown_handler(handler)

        assert len(lifecycle._shutdown_handlers) == 1

    @pytest.mark.asyncio
    async def test_register_sync_shutdown_handler(self):
        """Should register sync shutdown handlers."""
        lifecycle = LifecycleManager()
        handler = MagicMock()

        lifecycle.register_sync_shutdown_handler(handler)

        assert len(lifecycle._sync_shutdown_handlers) == 1

    @pytest.mark.asyncio
    async def test_shutdown_calls_handlers(self):
        """Should call all handlers during shutdown."""
        lifecycle = LifecycleManager()
        lifecycle.mark_running()

        handler1 = AsyncMock()
        handler2 = AsyncMock()
        sync_handler = MagicMock()

        lifecycle.register_shutdown_handler(handler1)
        lifecycle.register_shutdown_handler(handler2)
        lifecycle.register_sync_shutdown_handler(sync_handler)

        await lifecycle.shutdown(reason="test")

        handler1.assert_called_once()
        handler2.assert_called_once()
        sync_handler.assert_called_once()
        assert lifecycle.state == LifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_handlers_called_in_reverse_order(self):
        """Should call handlers in LIFO order."""
        lifecycle = LifecycleManager()
        lifecycle.mark_running()

        call_order = []

        async def handler1(ctx):
            call_order.append(1)

        async def handler2(ctx):
            call_order.append(2)

        lifecycle.register_shutdown_handler(handler1)
        lifecycle.register_shutdown_handler(handler2)

        await lifecycle.shutdown()

        # Should be called in reverse: 2, then 1
        assert call_order == [2, 1]

    @pytest.mark.asyncio
    async def test_handler_timeout(self):
        """Should timeout slow handlers."""
        lifecycle = LifecycleManager(handler_timeout=0.1)
        lifecycle.mark_running()

        async def slow_handler(ctx):
            await asyncio.sleep(10)  # Much longer than timeout

        lifecycle.register_shutdown_handler(slow_handler)

        # Should complete despite slow handler (with timeout)
        await asyncio.wait_for(lifecycle.shutdown(), timeout=1.0)
        assert lifecycle.state == LifecycleState.STOPPED

    @pytest.mark.asyncio
    async def test_handler_exception_continues(self):
        """Should continue to next handler if one fails."""
        lifecycle = LifecycleManager()
        lifecycle.mark_running()

        async def failing_handler(ctx):
            raise ValueError("Handler failed")

        successful_handler = AsyncMock()

        lifecycle.register_shutdown_handler(failing_handler)
        lifecycle.register_shutdown_handler(successful_handler)

        await lifecycle.shutdown()

        # Should still call successful handler and complete
        successful_handler.assert_called_once()
        assert lifecycle.state == LifecycleState.STOPPED


class TestLifecycleTaskTracking:
    """Test task tracking functionality."""

    @pytest.mark.asyncio
    async def test_track_task(self):
        """Should track pending tasks."""
        lifecycle = LifecycleManager()

        async def sample_task():
            await asyncio.sleep(0.1)

        task = asyncio.create_task(sample_task())
        lifecycle.track_task(task)

        assert len(lifecycle._pending_tasks) == 1

        await task  # Let it complete
        await asyncio.sleep(0)  # Let done callback run

        # Should auto-remove when done
        assert len(lifecycle._pending_tasks) == 0

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_tasks(self):
        """Should wait for pending tasks during shutdown."""
        lifecycle = LifecycleManager()
        lifecycle.mark_running()

        completed = []

        async def tracked_task():
            await asyncio.sleep(0.1)
            completed.append(True)

        task = asyncio.create_task(tracked_task())
        lifecycle.track_task(task)

        await lifecycle.shutdown()

        assert completed == [True]

    @pytest.mark.asyncio
    async def test_shutdown_cancels_slow_tasks(self):
        """Should cancel tasks that exceed shutdown timeout."""
        lifecycle = LifecycleManager(shutdown_timeout=0.1)
        lifecycle.mark_running()

        async def very_slow_task():
            await asyncio.sleep(100)

        task = asyncio.create_task(very_slow_task())
        lifecycle.track_task(task)

        await lifecycle.shutdown()

        assert task.cancelled() or task.done()
        assert lifecycle.state == LifecycleState.STOPPED


class TestShutdownIdempotency:
    """Test shutdown idempotency."""

    @pytest.mark.asyncio
    async def test_multiple_shutdown_calls(self):
        """Should handle multiple shutdown calls gracefully."""
        lifecycle = LifecycleManager()
        lifecycle.mark_running()

        handler = AsyncMock()
        lifecycle.register_shutdown_handler(handler)

        # Call shutdown multiple times
        await lifecycle.shutdown()
        await lifecycle.shutdown()
        await lifecycle.shutdown()

        # Handler should only be called once
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_after_stopped(self):
        """Should handle shutdown call when already stopped."""
        lifecycle = LifecycleManager()
        lifecycle.state = LifecycleState.STOPPED

        handler = AsyncMock()
        lifecycle.register_shutdown_handler(handler)

        await lifecycle.shutdown()

        # Should not call handlers
        handler.assert_not_called()


class TestRunWithLifecycle:
    """Test run_with_lifecycle helper."""

    @pytest.mark.asyncio
    async def test_run_with_lifecycle(self):
        """Should run coroutine with lifecycle management."""
        result = []

        async def main():
            result.append("started")
            return "done"

        outcome = await run_with_lifecycle(main())

        assert outcome == "done"
        assert result == ["started"]

    @pytest.mark.asyncio
    async def test_run_with_lifecycle_custom_timeout(self):
        """Should accept custom timeouts."""
        async def main():
            return True

        outcome = await run_with_lifecycle(
            main(),
            shutdown_timeout=30.0,
            handler_timeout=10.0
        )

        assert outcome is True
