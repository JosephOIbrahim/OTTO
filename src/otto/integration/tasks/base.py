"""
Task Adapter Base
=================

Base class for all task manager integrations.

Provides common logic for:
- Converting raw tasks to privacy-safe TaskSummary
- Calculating load level
- Detecting overdue tasks
- Priority aggregation
"""

import logging
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional

from ..adapter import IntegrationAdapter
from ..models import (
    IntegrationConfig,
    IntegrationType,
    TaskContext,
    TaskSummary,
)

logger = logging.getLogger(__name__)


class TaskAdapter(IntegrationAdapter[TaskContext]):
    """
    Base class for task manager integrations.

    Subclasses implement service-specific API calls,
    while this base provides common context calculation.

    Example:
        class TodoistAdapter(TaskAdapter):
            SERVICE_NAME = "todoist"

            async def _fetch_raw_tasks(self) -> List[dict]:
                # Call Todoist API
                ...
    """

    INTEGRATION_TYPE = IntegrationType.TASK_MANAGER
    SUPPORTS_WRITE = False  # Phase 5.1 is read-only

    # Load level thresholds (number of tasks)
    LOAD_THRESHOLD_LIGHT = 5       # <= 5 = light
    LOAD_THRESHOLD_MANAGEABLE = 15  # <= 15 = manageable
    LOAD_THRESHOLD_HEAVY = 30       # <= 30 = heavy
    # > 30 = overloaded

    # Overdue thresholds
    OVERDUE_CONCERNING = 3  # 3+ overdue = concerning
    OVERDUE_CRITICAL = 5    # 5+ overdue = task overload signal

    def __init__(self, config: IntegrationConfig):
        """Initialize task adapter."""
        super().__init__(config)

    # =========================================================================
    # Abstract Methods (Subclass Must Implement)
    # =========================================================================

    @abstractmethod
    async def _fetch_raw_tasks(self) -> List[dict]:
        """
        Fetch raw tasks from task manager API.

        Returns:
            List of raw task dictionaries from API

        Each task dict should have at minimum:
        - "due_date": ISO datetime string or None
        - "priority": int or string (normalized to "low"/"normal"/"high"/"urgent")
        - "is_completed": bool

        The adapter should only fetch incomplete tasks
        (or filter out completed ones before returning).
        """
        pass

    # =========================================================================
    # IntegrationAdapter Implementation
    # =========================================================================

    async def _fetch_context(self) -> TaskContext:
        """
        Fetch and process task context.

        Returns:
            TaskContext with aggregated task info
        """
        raw_tasks = await self._fetch_raw_tasks()

        # Convert to TaskSummary objects
        tasks = self._parse_tasks(raw_tasks)

        # Calculate context
        return self._calculate_context(tasks)

    def _create_empty_context(self) -> TaskContext:
        """Create empty task context."""
        return TaskContext.empty()

    # =========================================================================
    # Task Parsing
    # =========================================================================

    def _parse_tasks(self, raw_tasks: List[dict]) -> List[TaskSummary]:
        """
        Parse raw tasks into TaskSummary objects.

        Args:
            raw_tasks: List of raw task dictionaries

        Returns:
            List of TaskSummary objects
        """
        now = datetime.now()
        tasks = []

        for raw in raw_tasks:
            try:
                task = self._parse_single_task(raw, now)
                if task:
                    tasks.append(task)
            except Exception as e:
                logger.warning(f"Failed to parse task: {e}")
                continue

        return tasks

    def _parse_single_task(self, raw: dict, now: datetime) -> Optional[TaskSummary]:
        """
        Parse a single raw task.

        Args:
            raw: Raw task dictionary
            now: Current datetime

        Returns:
            TaskSummary or None if parsing fails
        """
        # Parse due date
        due_date = self._parse_datetime(raw.get("due_date"))

        # Check if overdue
        is_overdue = False
        if due_date and due_date < now:
            is_overdue = True

        # Normalize priority
        priority = self._normalize_priority(raw.get("priority"))

        # Check completion status
        is_completed = raw.get("is_completed", False)

        return TaskSummary(
            due_date=due_date,
            is_overdue=is_overdue,
            priority=priority,
            is_completed=is_completed,
        )

    def _parse_datetime(self, dt_value) -> Optional[datetime]:
        """
        Parse datetime from various formats.

        Args:
            dt_value: Datetime value (string, dict, or datetime)

        Returns:
            datetime object or None
        """
        if dt_value is None:
            return None

        if isinstance(dt_value, datetime):
            return dt_value

        if isinstance(dt_value, str):
            try:
                # Try ISO format
                return datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
            except ValueError:
                pass
            try:
                # Try date-only format
                return datetime.strptime(dt_value, "%Y-%m-%d")
            except ValueError:
                return None

        return None

    def _normalize_priority(self, priority) -> str:
        """
        Normalize priority to standard values.

        Args:
            priority: Priority from API (int, string, etc.)

        Returns:
            One of: "low", "normal", "high", "urgent"
        """
        if priority is None:
            return "normal"

        if isinstance(priority, int):
            # Common numeric priority schemes
            if priority <= 1:
                return "low"
            if priority <= 2:
                return "normal"
            if priority <= 3:
                return "high"
            return "urgent"

        if isinstance(priority, str):
            priority = priority.lower()
            if priority in ("low", "1", "p4"):
                return "low"
            if priority in ("normal", "medium", "2", "p3"):
                return "normal"
            if priority in ("high", "3", "p2"):
                return "high"
            if priority in ("urgent", "critical", "4", "p1"):
                return "urgent"

        return "normal"

    # =========================================================================
    # Context Calculation
    # =========================================================================

    def _calculate_context(self, tasks: List[TaskSummary]) -> TaskContext:
        """
        Calculate task context from task list.

        Args:
            tasks: List of TaskSummary objects

        Returns:
            TaskContext with calculated values
        """
        now = datetime.now()
        today_end = now.replace(hour=23, minute=59, second=59)
        week_end = now + timedelta(days=7)

        # Filter incomplete tasks only
        active_tasks = [t for t in tasks if not t.is_completed]

        # Count overdue
        overdue = [t for t in active_tasks if t.is_overdue]
        overdue_count = len(overdue)

        # Find oldest overdue
        oldest_overdue_days = None
        if overdue:
            oldest = min(t.due_date for t in overdue if t.due_date)
            oldest_overdue_days = (now - oldest).days

        # Count due today
        due_today = [
            t for t in active_tasks
            if t.due_date and not t.is_overdue and t.due_date <= today_end
        ]
        due_today_count = len(due_today)

        # Count due this week
        due_this_week = [
            t for t in active_tasks
            if t.due_date and t.due_date <= week_end
        ]
        due_this_week_count = len(due_this_week)

        # Count high priority
        high_priority = [
            t for t in active_tasks
            if t.priority in ("high", "urgent")
        ]
        high_priority_count = len(high_priority)

        # Find next deadline
        future_deadlines = [
            t for t in active_tasks
            if t.due_date and t.due_date > now
        ]
        next_deadline_hours = None
        if future_deadlines:
            next_task = min(future_deadlines, key=lambda t: t.due_date)
            next_deadline_hours = int((next_task.due_date - now).total_seconds() / 3600)

        # Calculate load level
        load_level = self._calculate_load_level(
            total=len(active_tasks),
            overdue=overdue_count,
            high_priority=high_priority_count,
        )

        return TaskContext(
            total_tasks=len(active_tasks),
            overdue_count=overdue_count,
            due_today_count=due_today_count,
            due_this_week_count=due_this_week_count,
            high_priority_count=high_priority_count,
            oldest_overdue_days=oldest_overdue_days,
            next_deadline_in_hours=next_deadline_hours,
            load_level=load_level,
        )

    def _calculate_load_level(
        self,
        total: int,
        overdue: int,
        high_priority: int,
    ) -> str:
        """
        Calculate load level from task metrics.

        Args:
            total: Total active tasks
            overdue: Number of overdue tasks
            high_priority: Number of high/urgent priority tasks

        Returns:
            "light", "manageable", "heavy", or "overloaded"
        """
        # Critical overdue triggers overload
        if overdue >= self.OVERDUE_CRITICAL:
            return "overloaded"

        # Calculate weighted score
        score = total + (overdue * 3) + (high_priority * 2)

        if score <= self.LOAD_THRESHOLD_LIGHT:
            return "light"
        if score <= self.LOAD_THRESHOLD_MANAGEABLE:
            return "manageable"
        if score <= self.LOAD_THRESHOLD_HEAVY:
            return "heavy"
        return "overloaded"


__all__ = ["TaskAdapter"]
