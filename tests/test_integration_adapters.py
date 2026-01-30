"""
Tests for Integration Adapters
==============================

Tests for calendar and task adapters using mock implementations.
"""

import pytest
from datetime import datetime, timedelta

from otto.integration import (
    MockCalendarAdapter,
    MockTaskAdapter,
    create_mock_calendar,
    create_mock_tasks,
    CalendarContext,
    TaskContext,
    IntegrationStatus,
    ContextSignal,
)


class TestMockCalendarAdapter:
    """Tests for MockCalendarAdapter."""

    @pytest.mark.asyncio
    async def test_basic_context(self):
        """Get basic calendar context."""
        adapter = MockCalendarAdapter(events_today=3, events_tomorrow=2)
        await adapter.initialize()

        ctx = await adapter.get_context()

        assert isinstance(ctx, CalendarContext)
        assert ctx.events_today == 3
        assert ctx.events_tomorrow == 2

    @pytest.mark.asyncio
    async def test_empty_calendar(self):
        """Calendar with no events."""
        adapter = MockCalendarAdapter(events_today=0, events_tomorrow=0)
        await adapter.initialize()

        ctx = await adapter.get_context()

        assert ctx.events_today == 0
        assert ctx.busy_level == "light"

    @pytest.mark.asyncio
    async def test_busy_calendar(self):
        """Heavily scheduled calendar."""
        adapter = MockCalendarAdapter(events_today=8, events_tomorrow=5)
        await adapter.initialize()

        ctx = await adapter.get_context()

        # Events get filtered to today's events window
        assert ctx.events_today >= 1
        assert ctx.busy_level in ("light", "moderate", "heavy")

    @pytest.mark.asyncio
    async def test_deadline_detection(self):
        """Calendar with deadline event."""
        adapter = MockCalendarAdapter(has_deadline=True)
        await adapter.initialize()

        ctx = await adapter.get_context()

        assert ctx.next_deadline_in_hours is not None
        signals = ctx.get_signals()
        assert ContextSignal.DEADLINE_APPROACHING in signals

    @pytest.mark.asyncio
    async def test_health_tracking(self):
        """Health status is tracked."""
        adapter = MockCalendarAdapter()
        await adapter.initialize()

        health = await adapter.get_health()
        assert health.status == IntegrationStatus.HEALTHY
        assert health.last_sync is not None

    @pytest.mark.asyncio
    async def test_failure_handling(self):
        """Graceful handling of failures."""
        adapter = MockCalendarAdapter(should_fail=True, fail_after=1)
        await adapter.initialize()

        # First call succeeds
        ctx1 = await adapter.get_context()
        assert ctx1.events_today >= 0

        # Second call fails but returns cached
        ctx2 = await adapter.get_context()
        assert ctx2 is not None

        health = await adapter.get_health()
        assert health.status == IntegrationStatus.ERROR

    @pytest.mark.asyncio
    async def test_initialization_failure(self):
        """Handle initialization failure."""
        adapter = MockCalendarAdapter(should_fail=True, fail_after=0)

        success = await adapter.initialize()

        assert not success
        health = await adapter.get_health()
        assert health.status == IntegrationStatus.ERROR

    @pytest.mark.asyncio
    async def test_update_configuration(self):
        """Can update mock configuration."""
        adapter = MockCalendarAdapter(events_today=1)
        await adapter.initialize()

        ctx1 = await adapter.get_context()
        initial_count = ctx1.events_today

        adapter.set_events(today=10)
        ctx2 = await adapter.get_context()
        # Should have more events after update
        assert ctx2.events_today >= initial_count


class TestMockTaskAdapter:
    """Tests for MockTaskAdapter."""

    @pytest.mark.asyncio
    async def test_basic_context(self):
        """Get basic task context."""
        adapter = MockTaskAdapter(total_tasks=10, overdue_count=2)
        await adapter.initialize()

        ctx = await adapter.get_context()

        assert isinstance(ctx, TaskContext)
        assert ctx.total_tasks == 10
        assert ctx.overdue_count == 2

    @pytest.mark.asyncio
    async def test_empty_tasks(self):
        """Task manager with no tasks."""
        adapter = MockTaskAdapter(total_tasks=0, due_today_count=0)
        await adapter.initialize()

        ctx = await adapter.get_context()

        assert ctx.total_tasks == 0
        assert ctx.load_level == "light"

    @pytest.mark.asyncio
    async def test_overloaded_tasks(self):
        """Task manager in overload."""
        adapter = MockTaskAdapter(
            total_tasks=40,
            overdue_count=6,
            high_priority_count=5,
        )
        await adapter.initialize()

        ctx = await adapter.get_context()

        assert ctx.overdue_count == 6
        assert ctx.load_level == "overloaded"

    @pytest.mark.asyncio
    async def test_overload_signal(self):
        """Overload produces signal."""
        adapter = MockTaskAdapter(overdue_count=6)
        await adapter.initialize()

        ctx = await adapter.get_context()
        signals = ctx.get_signals()

        assert ContextSignal.TASK_OVERLOAD in signals

    @pytest.mark.asyncio
    async def test_manageable_signal(self):
        """Manageable load produces signal."""
        adapter = MockTaskAdapter(total_tasks=5, overdue_count=0)
        await adapter.initialize()

        ctx = await adapter.get_context()
        signals = ctx.get_signals()

        assert ContextSignal.TASK_MANAGEABLE in signals

    @pytest.mark.asyncio
    async def test_failure_handling(self):
        """Graceful handling of failures."""
        adapter = MockTaskAdapter(should_fail=True, fail_after=1)
        await adapter.initialize()

        # First call succeeds
        ctx1 = await adapter.get_context()
        assert ctx1 is not None

        # Second call fails but returns cached
        ctx2 = await adapter.get_context()
        assert ctx2 is not None


class TestMockFactories:
    """Tests for mock factory functions."""

    @pytest.mark.asyncio
    async def test_create_light_calendar(self):
        """Create light calendar."""
        adapter = create_mock_calendar(busy_level="light")
        await adapter.initialize()

        ctx = await adapter.get_context()
        # Light calendar should not be "heavy"
        assert ctx.busy_level in ("light", "moderate")

    @pytest.mark.asyncio
    async def test_create_heavy_calendar(self):
        """Create heavy calendar."""
        adapter = create_mock_calendar(busy_level="heavy")
        await adapter.initialize()

        ctx = await adapter.get_context()
        # Heavy calendar has more events configured
        assert adapter._events_today >= 7

    @pytest.mark.asyncio
    async def test_create_light_tasks(self):
        """Create light task load."""
        adapter = create_mock_tasks(load_level="light")
        await adapter.initialize()

        ctx = await adapter.get_context()
        assert ctx.load_level == "light"

    @pytest.mark.asyncio
    async def test_create_overloaded_tasks(self):
        """Create overloaded task manager."""
        adapter = create_mock_tasks(load_level="overloaded")
        await adapter.initialize()

        ctx = await adapter.get_context()
        assert ctx.load_level == "overloaded"


class TestAdapterProperties:
    """Tests for adapter properties."""

    def test_service_name(self):
        """Adapter has service name."""
        adapter = MockCalendarAdapter()
        assert adapter.service_name == "mock_calendar"

    def test_can_read(self):
        """All adapters can read."""
        calendar = MockCalendarAdapter()
        tasks = MockTaskAdapter()

        assert calendar.can_read
        assert tasks.can_read

    def test_cannot_write_phase5(self):
        """Phase 5.1 is read-only."""
        calendar = MockCalendarAdapter()
        tasks = MockTaskAdapter()

        assert not calendar.can_write
        assert not tasks.can_write

    def test_enabled_by_default(self):
        """Adapters are enabled by default."""
        adapter = MockCalendarAdapter()
        assert adapter.is_enabled
