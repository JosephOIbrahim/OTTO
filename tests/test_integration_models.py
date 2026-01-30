"""
Tests for Integration Models
============================

Tests for context models, health status, and configuration.
"""

import pytest
from datetime import datetime, timedelta

from otto.integration import (
    IntegrationStatus,
    IntegrationType,
    ContextSignal,
    HealthStatus,
    CalendarEvent,
    CalendarContext,
    TaskSummary,
    TaskContext,
    ExternalContext,
    IntegrationConfig,
)


class TestIntegrationStatus:
    """Tests for IntegrationStatus enum."""

    def test_all_statuses_defined(self):
        """All expected statuses exist."""
        assert IntegrationStatus.HEALTHY
        assert IntegrationStatus.DEGRADED
        assert IntegrationStatus.ERROR
        assert IntegrationStatus.DISABLED
        assert IntegrationStatus.NOT_CONFIGURED

    def test_status_values(self):
        """Status values are strings."""
        assert IntegrationStatus.HEALTHY.value == "healthy"
        assert IntegrationStatus.ERROR.value == "error"


class TestHealthStatus:
    """Tests for HealthStatus."""

    def test_create_healthy(self):
        """Create healthy status."""
        status = HealthStatus(
            status=IntegrationStatus.HEALTHY,
            last_sync=datetime.now(),
        )
        assert status.is_available()
        assert status.error_message is None

    def test_create_error(self):
        """Create error status."""
        status = HealthStatus(
            status=IntegrationStatus.ERROR,
            error_message="Connection failed",
        )
        assert not status.is_available()
        assert status.error_message == "Connection failed"

    def test_degraded_is_available(self):
        """Degraded status is still available."""
        status = HealthStatus(status=IntegrationStatus.DEGRADED)
        assert status.is_available()

    def test_to_dict_from_dict_roundtrip(self):
        """Serialization roundtrip."""
        original = HealthStatus(
            status=IntegrationStatus.HEALTHY,
            last_sync=datetime(2024, 1, 15, 10, 30, 0),
        )
        data = original.to_dict()
        restored = HealthStatus.from_dict(data)

        assert restored.status == original.status
        assert restored.last_sync == original.last_sync


class TestCalendarEvent:
    """Tests for CalendarEvent."""

    def test_create_event(self):
        """Create calendar event."""
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)

        event = CalendarEvent(start=start, end=end)

        assert event.duration_minutes == 60
        assert not event.is_all_day
        assert not event.is_deadline

    def test_all_day_event(self):
        """Create all-day event."""
        event = CalendarEvent(
            start=datetime(2024, 1, 15),
            end=datetime(2024, 1, 16),
            is_all_day=True,
        )
        assert event.is_all_day

    def test_deadline_event(self):
        """Create deadline event."""
        event = CalendarEvent(
            start=datetime(2024, 1, 15, 17, 0, 0),
            end=datetime(2024, 1, 15, 17, 0, 0),
            is_deadline=True,
        )
        assert event.is_deadline

    def test_to_dict_from_dict_roundtrip(self):
        """Serialization roundtrip."""
        original = CalendarEvent(
            start=datetime(2024, 1, 15, 10, 0, 0),
            end=datetime(2024, 1, 15, 11, 0, 0),
            is_deadline=True,
        )
        data = original.to_dict()
        restored = CalendarEvent.from_dict(data)

        assert restored.start == original.start
        assert restored.end == original.end
        assert restored.is_deadline == original.is_deadline


class TestCalendarContext:
    """Tests for CalendarContext."""

    def test_empty_context(self):
        """Create empty context."""
        ctx = CalendarContext.empty()
        assert ctx.events_today == 0
        assert ctx.busy_level == "light"

    def test_busy_context(self):
        """Create busy context."""
        ctx = CalendarContext(
            events_today=5,
            total_busy_minutes_today=240,
            busy_level="heavy",
        )
        assert ctx.events_today == 5
        assert ctx.busy_level == "heavy"

    def test_get_signals_light(self):
        """Light calendar produces light signal."""
        ctx = CalendarContext(busy_level="light")
        signals = ctx.get_signals()
        assert ContextSignal.CALENDAR_LIGHT in signals

    def test_get_signals_heavy(self):
        """Heavy calendar produces busy signal."""
        ctx = CalendarContext(busy_level="heavy")
        signals = ctx.get_signals()
        assert ContextSignal.CALENDAR_BUSY in signals

    def test_get_signals_deadline(self):
        """Approaching deadline produces signal."""
        ctx = CalendarContext(next_deadline_in_hours=12)
        signals = ctx.get_signals()
        assert ContextSignal.DEADLINE_APPROACHING in signals

    def test_to_dict_excludes_raw_events(self):
        """Serialization excludes internal events list."""
        ctx = CalendarContext(events_today=3)
        data = ctx.to_dict()
        assert "_events" not in data


class TestTaskSummary:
    """Tests for TaskSummary."""

    def test_create_task(self):
        """Create task summary."""
        task = TaskSummary(
            due_date=datetime(2024, 1, 15),
            priority="high",
        )
        assert task.priority == "high"
        assert not task.is_completed
        assert not task.is_overdue

    def test_overdue_task(self):
        """Create overdue task."""
        task = TaskSummary(
            due_date=datetime(2024, 1, 10),
            is_overdue=True,
        )
        assert task.is_overdue


class TestTaskContext:
    """Tests for TaskContext."""

    def test_empty_context(self):
        """Create empty context."""
        ctx = TaskContext.empty()
        assert ctx.total_tasks == 0
        assert ctx.load_level == "manageable"

    def test_overloaded_context(self):
        """Create overloaded context."""
        ctx = TaskContext(
            total_tasks=40,
            overdue_count=7,
            load_level="overloaded",
        )
        assert ctx.load_level == "overloaded"

    def test_get_signals_overload(self):
        """Overload produces signal."""
        ctx = TaskContext(overdue_count=6, load_level="overloaded")
        signals = ctx.get_signals()
        assert ContextSignal.TASK_OVERLOAD in signals

    def test_get_signals_manageable(self):
        """Manageable load produces signal."""
        ctx = TaskContext(load_level="manageable")
        signals = ctx.get_signals()
        assert ContextSignal.TASK_MANAGEABLE in signals


class TestExternalContext:
    """Tests for ExternalContext (aggregated)."""

    def test_empty_context(self):
        """Create empty context."""
        ctx = ExternalContext.empty()
        assert ctx.calendar is None
        assert ctx.tasks is None

    def test_combined_context(self):
        """Combine calendar and task context."""
        ctx = ExternalContext(
            calendar=CalendarContext(events_today=3),
            tasks=TaskContext(total_tasks=10),
            available_integrations=["mock_calendar", "mock_tasks"],
        )
        assert len(ctx.available_integrations) == 2

    def test_get_all_signals(self):
        """Get signals from all integrations."""
        ctx = ExternalContext(
            calendar=CalendarContext(busy_level="heavy"),
            tasks=TaskContext(load_level="light"),
        )
        signals = ctx.get_all_signals()

        assert ContextSignal.CALENDAR_BUSY in signals
        assert ContextSignal.TASK_MANAGEABLE in signals

    def test_unavailable_signal(self):
        """No integrations produces unavailable signal."""
        ctx = ExternalContext.empty()
        signals = ctx.get_all_signals()
        assert ContextSignal.CONTEXT_UNAVAILABLE in signals


class TestIntegrationConfig:
    """Tests for IntegrationConfig."""

    def test_create_config(self):
        """Create integration config."""
        config = IntegrationConfig(
            integration_type=IntegrationType.CALENDAR,
            service_name="google_calendar",
        )
        assert config.enabled
        assert config.sync_interval_minutes == 5

    def test_disabled_config(self):
        """Create disabled config."""
        config = IntegrationConfig(
            integration_type=IntegrationType.TASK_MANAGER,
            service_name="todoist",
            enabled=False,
        )
        assert not config.enabled

    def test_to_dict_from_dict_roundtrip(self):
        """Serialization roundtrip."""
        original = IntegrationConfig(
            integration_type=IntegrationType.CALENDAR,
            service_name="mock",
            sync_interval_minutes=10,
            settings={"timezone": "UTC"},
        )
        data = original.to_dict()
        restored = IntegrationConfig.from_dict(data)

        assert restored.integration_type == original.integration_type
        assert restored.service_name == original.service_name
        assert restored.settings == original.settings
