"""
Mock Adapters for Testing
=========================

Mock implementations of calendar and task adapters for testing
without real external service connections.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from .adapter import IntegrationAdapter
from .calendars.base import CalendarAdapter
from .tasks.base import TaskAdapter
from .models import (
    CalendarContext,
    CalendarEvent,
    HealthStatus,
    IntegrationConfig,
    IntegrationStatus,
    IntegrationType,
    TaskContext,
    TaskSummary,
)


class MockCalendarAdapter(CalendarAdapter):
    """
    Mock calendar adapter for testing.

    Generates fake events based on configuration.

    Example:
        config = IntegrationConfig(
            integration_type=IntegrationType.CALENDAR,
            service_name="mock_calendar",
            settings={"events_today": 3, "busy_level": "moderate"}
        )
        adapter = MockCalendarAdapter(config)
        context = await adapter.get_context()
    """

    SERVICE_NAME = "mock_calendar"
    INTEGRATION_TYPE = IntegrationType.CALENDAR

    def __init__(
        self,
        config: IntegrationConfig = None,
        events_today: int = 2,
        events_tomorrow: int = 1,
        next_event_minutes: int = 60,
        has_deadline: bool = False,
        should_fail: bool = False,
        fail_after: int = 0,
    ):
        """
        Initialize mock calendar adapter.

        Args:
            config: Integration config (created if not provided)
            events_today: Number of events today
            events_tomorrow: Number of events tomorrow
            next_event_minutes: Minutes until next event
            has_deadline: Whether to include a deadline
            should_fail: Whether to simulate errors
            fail_after: Fail after this many successful calls
        """
        if config is None:
            config = IntegrationConfig(
                integration_type=IntegrationType.CALENDAR,
                service_name=self.SERVICE_NAME,
            )
        super().__init__(config)

        self._events_today = events_today
        self._events_tomorrow = events_tomorrow
        self._next_event_minutes = next_event_minutes
        self._has_deadline = has_deadline
        self._should_fail = should_fail
        self._fail_after = fail_after
        self._call_count = 0

    async def initialize(self) -> bool:
        """Initialize mock adapter (always succeeds)."""
        if self._should_fail and self._fail_after == 0:
            self._health = HealthStatus(
                status=IntegrationStatus.ERROR,
                error_message="Mock initialization failure",
            )
            return False

        self._health = HealthStatus(
            status=IntegrationStatus.HEALTHY,
            last_sync=datetime.now(),
        )
        self._initialized = True
        return True

    async def _fetch_raw_events(
        self,
        start: datetime,
        end: datetime,
    ) -> List[dict]:
        """Generate mock events."""
        self._call_count += 1

        if self._should_fail and self._call_count > self._fail_after:
            from .adapter import ServiceUnavailableError
            raise ServiceUnavailableError("Mock service unavailable")

        now = datetime.now()
        events = []

        # Generate today's events - ensure they stay within today
        today_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        for i in range(self._events_today):
            # Space events throughout the day, starting from 9am
            event_start = today_start + timedelta(hours=i * 2)
            # Ensure event ends before midnight
            event_end = min(
                event_start + timedelta(minutes=30),
                now.replace(hour=23, minute=30, second=0, microsecond=0)
            )
            events.append({
                "start": event_start.isoformat(),
                "end": event_end.isoformat(),
            })

        # Generate tomorrow's events
        tomorrow = now + timedelta(days=1)
        tomorrow_start = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
        for i in range(self._events_tomorrow):
            event_start = tomorrow_start + timedelta(hours=i * 2)
            events.append({
                "start": event_start.isoformat(),
                "end": (event_start + timedelta(hours=1)).isoformat(),
            })

        # Add deadline if requested
        if self._has_deadline:
            deadline = now + timedelta(hours=12)
            events.append({
                "start": deadline.isoformat(),
                "end": deadline.isoformat(),
                "is_deadline": True,
            })

        return events

    def set_events(
        self,
        today: int = None,
        tomorrow: int = None,
        next_minutes: int = None,
    ) -> None:
        """Update mock event configuration."""
        if today is not None:
            self._events_today = today
        if tomorrow is not None:
            self._events_tomorrow = tomorrow
        if next_minutes is not None:
            self._next_event_minutes = next_minutes

    def set_failure_mode(self, should_fail: bool, fail_after: int = 0) -> None:
        """Configure failure behavior."""
        self._should_fail = should_fail
        self._fail_after = fail_after
        self._call_count = 0


class MockTaskAdapter(TaskAdapter):
    """
    Mock task adapter for testing.

    Generates fake tasks based on configuration.

    Example:
        config = IntegrationConfig(
            integration_type=IntegrationType.TASK_MANAGER,
            service_name="mock_tasks",
        )
        adapter = MockTaskAdapter(config, total_tasks=10, overdue=2)
        context = await adapter.get_context()
    """

    SERVICE_NAME = "mock_tasks"
    INTEGRATION_TYPE = IntegrationType.TASK_MANAGER

    def __init__(
        self,
        config: IntegrationConfig = None,
        total_tasks: int = 5,
        overdue_count: int = 0,
        due_today_count: int = 1,
        high_priority_count: int = 0,
        should_fail: bool = False,
        fail_after: int = 0,
    ):
        """
        Initialize mock task adapter.

        Args:
            config: Integration config (created if not provided)
            total_tasks: Total number of incomplete tasks
            overdue_count: Number of overdue tasks
            due_today_count: Number of tasks due today
            high_priority_count: Number of high/urgent priority tasks
            should_fail: Whether to simulate errors
            fail_after: Fail after this many successful calls
        """
        if config is None:
            config = IntegrationConfig(
                integration_type=IntegrationType.TASK_MANAGER,
                service_name=self.SERVICE_NAME,
            )
        super().__init__(config)

        self._total_tasks = total_tasks
        self._overdue_count = overdue_count
        self._due_today_count = due_today_count
        self._high_priority_count = high_priority_count
        self._should_fail = should_fail
        self._fail_after = fail_after
        self._call_count = 0

    async def initialize(self) -> bool:
        """Initialize mock adapter (always succeeds)."""
        if self._should_fail and self._fail_after == 0:
            self._health = HealthStatus(
                status=IntegrationStatus.ERROR,
                error_message="Mock initialization failure",
            )
            return False

        self._health = HealthStatus(
            status=IntegrationStatus.HEALTHY,
            last_sync=datetime.now(),
        )
        self._initialized = True
        return True

    async def _fetch_raw_tasks(self) -> List[dict]:
        """Generate mock tasks."""
        self._call_count += 1

        if self._should_fail and self._call_count > self._fail_after:
            from .adapter import ServiceUnavailableError
            raise ServiceUnavailableError("Mock service unavailable")

        now = datetime.now()
        tasks = []

        # Generate overdue tasks
        for i in range(self._overdue_count):
            tasks.append({
                "due_date": (now - timedelta(days=i + 1)).isoformat(),
                "priority": "normal",
                "is_completed": False,
            })

        # Generate due today tasks
        today_end = now.replace(hour=23, minute=59, second=59)
        for i in range(self._due_today_count):
            tasks.append({
                "due_date": today_end.isoformat(),
                "priority": "normal",
                "is_completed": False,
            })

        # Generate high priority tasks
        for i in range(self._high_priority_count):
            tasks.append({
                "due_date": (now + timedelta(days=2)).isoformat(),
                "priority": "high" if i % 2 == 0 else "urgent",
                "is_completed": False,
            })

        # Generate remaining tasks (no due date)
        remaining = self._total_tasks - len(tasks)
        for i in range(max(0, remaining)):
            tasks.append({
                "due_date": None,
                "priority": "normal",
                "is_completed": False,
            })

        return tasks

    def set_tasks(
        self,
        total: int = None,
        overdue: int = None,
        due_today: int = None,
        high_priority: int = None,
    ) -> None:
        """Update mock task configuration."""
        if total is not None:
            self._total_tasks = total
        if overdue is not None:
            self._overdue_count = overdue
        if due_today is not None:
            self._due_today_count = due_today
        if high_priority is not None:
            self._high_priority_count = high_priority

    def set_failure_mode(self, should_fail: bool, fail_after: int = 0) -> None:
        """Configure failure behavior."""
        self._should_fail = should_fail
        self._fail_after = fail_after
        self._call_count = 0


def create_mock_calendar(
    events_today: int = 2,
    busy_level: str = "light",
    has_deadline: bool = False,
) -> MockCalendarAdapter:
    """
    Factory for creating mock calendar with preset busy level.

    Args:
        events_today: Base number of events
        busy_level: "light", "moderate", or "heavy"
        has_deadline: Include deadline event

    Returns:
        Configured MockCalendarAdapter
    """
    # Adjust events based on busy level
    if busy_level == "moderate":
        events_today = max(events_today, 4)
    elif busy_level == "heavy":
        events_today = max(events_today, 7)

    return MockCalendarAdapter(
        events_today=events_today,
        events_tomorrow=max(1, events_today // 2),
        has_deadline=has_deadline,
    )


def create_mock_tasks(
    load_level: str = "manageable",
    overdue: int = 0,
) -> MockTaskAdapter:
    """
    Factory for creating mock task adapter with preset load level.

    Args:
        load_level: "light", "manageable", "heavy", or "overloaded"
        overdue: Number of overdue tasks

    Returns:
        Configured MockTaskAdapter
    """
    if load_level == "light":
        return MockTaskAdapter(total_tasks=3, overdue_count=overdue)
    elif load_level == "manageable":
        return MockTaskAdapter(total_tasks=10, overdue_count=overdue, due_today_count=2)
    elif load_level == "heavy":
        return MockTaskAdapter(
            total_tasks=25,
            overdue_count=max(overdue, 2),
            due_today_count=5,
            high_priority_count=3,
        )
    else:  # overloaded
        return MockTaskAdapter(
            total_tasks=40,
            overdue_count=max(overdue, 5),
            due_today_count=10,
            high_priority_count=8,
        )


__all__ = [
    "MockCalendarAdapter",
    "MockTaskAdapter",
    "create_mock_calendar",
    "create_mock_tasks",
]
