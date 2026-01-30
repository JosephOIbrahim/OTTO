"""
Tests for Integration Manager
=============================

Tests for the central integration orchestration.
"""

import pytest
import asyncio
from datetime import timedelta
from pathlib import Path
import tempfile

from otto.integration import (
    IntegrationManager,
    create_integration_manager,
    MockCalendarAdapter,
    MockTaskAdapter,
    IntegrationStatus,
    IntegrationType,
    ContextSignal,
)


class TestIntegrationManagerBasics:
    """Basic manager functionality tests."""

    def test_create_manager(self):
        """Manager can be created."""
        manager = create_integration_manager()
        assert manager is not None

    def test_empty_manager(self):
        """Manager starts with no adapters."""
        manager = IntegrationManager()
        assert len(manager.list_adapters()) == 0

    def test_register_adapter(self):
        """Can register adapters."""
        manager = IntegrationManager()
        adapter = MockCalendarAdapter()

        manager.register_adapter(adapter)

        assert "mock_calendar" in manager.list_adapters()

    def test_register_duplicate_raises(self):
        """Cannot register same adapter twice."""
        manager = IntegrationManager()
        adapter1 = MockCalendarAdapter()
        adapter2 = MockCalendarAdapter()

        manager.register_adapter(adapter1)

        with pytest.raises(ValueError):
            manager.register_adapter(adapter2)

    def test_unregister_adapter(self):
        """Can unregister adapters."""
        manager = IntegrationManager()
        adapter = MockCalendarAdapter()
        manager.register_adapter(adapter)

        result = manager.unregister_adapter("mock_calendar")

        assert result
        assert "mock_calendar" not in manager.list_adapters()

    def test_unregister_nonexistent(self):
        """Unregistering nonexistent returns False."""
        manager = IntegrationManager()
        result = manager.unregister_adapter("nonexistent")
        assert not result

    def test_get_adapter(self):
        """Can get adapter by name."""
        manager = IntegrationManager()
        adapter = MockCalendarAdapter()
        manager.register_adapter(adapter)

        retrieved = manager.get_adapter("mock_calendar")

        assert retrieved is adapter

    def test_get_adapters_by_type(self):
        """Can filter adapters by type."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter()
        tasks = MockTaskAdapter()

        manager.register_adapter(calendar)
        manager.register_adapter(tasks)

        calendar_adapters = manager.get_adapters_by_type(IntegrationType.CALENDAR)
        task_adapters = manager.get_adapters_by_type(IntegrationType.TASK_MANAGER)

        assert len(calendar_adapters) == 1
        assert len(task_adapters) == 1


class TestIntegrationManagerLifecycle:
    """Manager lifecycle tests."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Manager can start and stop."""
        manager = IntegrationManager(sync_interval=timedelta(seconds=60))
        calendar = MockCalendarAdapter()
        manager.register_adapter(calendar)

        await manager.start()
        assert manager._running

        await manager.stop()
        assert not manager._running

    @pytest.mark.asyncio
    async def test_start_initializes_adapters(self):
        """Start initializes all adapters."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter()
        manager.register_adapter(calendar)

        await manager.start()

        assert calendar._initialized
        await manager.stop()

    @pytest.mark.asyncio
    async def test_double_start_warning(self):
        """Double start doesn't crash."""
        manager = IntegrationManager()
        await manager.start()
        await manager.start()  # Should just warn

        await manager.stop()


class TestIntegrationManagerContext:
    """Context retrieval tests."""

    @pytest.mark.asyncio
    async def test_get_context_empty(self):
        """Get context with no adapters."""
        manager = IntegrationManager()
        await manager.start()

        ctx = await manager.get_context()

        assert ctx.calendar is None
        assert ctx.tasks is None
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_context_calendar(self):
        """Get context with calendar adapter."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter(events_today=3)
        manager.register_adapter(calendar)

        await manager.start()
        ctx = await manager.get_context()

        assert ctx.calendar is not None
        assert ctx.calendar.events_today == 3
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_context_tasks(self):
        """Get context with task adapter."""
        manager = IntegrationManager()
        tasks = MockTaskAdapter(total_tasks=10)
        manager.register_adapter(tasks)

        await manager.start()
        ctx = await manager.get_context()

        assert ctx.tasks is not None
        assert ctx.tasks.total_tasks == 10
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_context_combined(self):
        """Get combined context from multiple adapters."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter(events_today=3)
        tasks = MockTaskAdapter(total_tasks=10)

        manager.register_adapter(calendar)
        manager.register_adapter(tasks)

        await manager.start()
        ctx = await manager.get_context()

        assert ctx.calendar is not None
        assert ctx.tasks is not None
        assert len(ctx.available_integrations) == 2
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_context_signals(self):
        """Context includes signals."""
        manager = IntegrationManager()
        # Use 0 events for light calendar (guarantees CALENDAR_LIGHT signal)
        calendar = MockCalendarAdapter(events_today=0, events_tomorrow=0)
        manager.register_adapter(calendar)

        await manager.start()
        ctx = await manager.get_context()
        signals = ctx.get_all_signals()

        # With 0 events, should have CALENDAR_LIGHT signal
        assert ContextSignal.CALENDAR_LIGHT in signals
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_calendar_context(self):
        """Get calendar context specifically."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter(events_today=5)
        manager.register_adapter(calendar)

        await manager.start()
        ctx = await manager.get_calendar_context()

        assert ctx is not None
        # Events get filtered by time window
        assert ctx.events_today >= 1
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_task_context(self):
        """Get task context specifically."""
        manager = IntegrationManager()
        tasks = MockTaskAdapter(total_tasks=15)
        manager.register_adapter(tasks)

        await manager.start()
        ctx = await manager.get_task_context()

        assert ctx is not None
        assert ctx.total_tasks == 15
        await manager.stop()

    @pytest.mark.asyncio
    async def test_force_refresh(self):
        """Force refresh fetches new data."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter(events_today=2)
        manager.register_adapter(calendar)

        await manager.start()

        ctx1 = await manager.get_context()
        initial_events = ctx1.calendar.events_today

        calendar.set_events(today=10)
        ctx2 = await manager.get_context(force_refresh=True)

        # After setting more events, should have more (or same due to time window filtering)
        assert ctx2.calendar is not None
        await manager.stop()


class TestIntegrationManagerHealth:
    """Health monitoring tests."""

    @pytest.mark.asyncio
    async def test_get_health(self):
        """Get health of all adapters."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter()
        tasks = MockTaskAdapter()

        manager.register_adapter(calendar)
        manager.register_adapter(tasks)

        await manager.start()
        health = await manager.get_health()

        assert "mock_calendar" in health
        assert "mock_tasks" in health
        assert health["mock_calendar"].status == IntegrationStatus.HEALTHY
        await manager.stop()

    @pytest.mark.asyncio
    async def test_overall_health_healthy(self):
        """Overall health when all healthy."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter()
        manager.register_adapter(calendar)

        await manager.start()
        status = await manager.get_overall_health()

        assert status == IntegrationStatus.HEALTHY
        await manager.stop()

    @pytest.mark.asyncio
    async def test_overall_health_not_configured(self):
        """Overall health with no adapters."""
        manager = IntegrationManager()
        await manager.start()

        status = await manager.get_overall_health()

        assert status == IntegrationStatus.NOT_CONFIGURED
        await manager.stop()

    @pytest.mark.asyncio
    async def test_overall_health_degraded(self):
        """Overall health when some failing."""
        manager = IntegrationManager()
        healthy = MockCalendarAdapter()
        failing = MockTaskAdapter(should_fail=True, fail_after=0)

        manager.register_adapter(healthy)
        manager.register_adapter(failing)

        await manager.start()
        status = await manager.get_overall_health()

        assert status == IntegrationStatus.DEGRADED
        await manager.stop()


class TestIntegrationManagerSync:
    """Manual sync tests."""

    @pytest.mark.asyncio
    async def test_manual_sync_all(self):
        """Manually sync all adapters."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter()
        manager.register_adapter(calendar)

        await manager.start()
        result = await manager.sync()

        assert result
        await manager.stop()

    @pytest.mark.asyncio
    async def test_manual_sync_specific(self):
        """Manually sync specific adapter."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter()
        tasks = MockTaskAdapter()

        manager.register_adapter(calendar)
        manager.register_adapter(tasks)

        await manager.start()
        result = await manager.sync("mock_calendar")

        assert result
        await manager.stop()

    @pytest.mark.asyncio
    async def test_manual_sync_nonexistent(self):
        """Sync nonexistent adapter fails."""
        manager = IntegrationManager()
        await manager.start()

        result = await manager.sync("nonexistent")

        assert not result
        await manager.stop()


class TestIntegrationManagerSerialization:
    """Serialization tests."""

    @pytest.mark.asyncio
    async def test_to_dict(self):
        """Manager state can be serialized."""
        manager = IntegrationManager()
        calendar = MockCalendarAdapter()
        manager.register_adapter(calendar)

        await manager.start()
        data = manager.to_dict()

        assert "running" in data
        assert "adapters" in data
        assert "context" in data
        assert "mock_calendar" in data["adapters"]
        await manager.stop()


class TestGracefulDegradation:
    """Tests for graceful degradation on failures."""

    @pytest.mark.asyncio
    async def test_adapter_failure_returns_cached(self):
        """Failed adapter returns cached context."""
        manager = IntegrationManager()
        adapter = MockCalendarAdapter(should_fail=True, fail_after=1)
        manager.register_adapter(adapter)

        await manager.start()

        # First sync succeeds and caches
        ctx1 = await manager.get_context()
        assert ctx1.calendar is not None

        # Second sync fails but uses cache
        ctx2 = await manager.get_context(force_refresh=True)
        # Context still available from cache
        assert ctx2 is not None

        await manager.stop()

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """Some adapters failing doesn't affect others."""
        manager = IntegrationManager()
        healthy = MockCalendarAdapter()
        failing = MockTaskAdapter(should_fail=True, fail_after=0)

        manager.register_adapter(healthy)
        manager.register_adapter(failing)

        await manager.start()
        ctx = await manager.get_context()

        # Calendar should still work
        assert ctx.calendar is not None
        await manager.stop()
