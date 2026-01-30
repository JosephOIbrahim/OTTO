"""
Calendar Adapter Base
=====================

Base class for all calendar integrations.

Provides common logic for:
- Converting raw events to privacy-safe CalendarEvent
- Calculating busy level
- Detecting deadlines
- Conflict detection
"""

import logging
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional

from ..adapter import IntegrationAdapter
from ..models import (
    CalendarContext,
    CalendarEvent,
    IntegrationConfig,
    IntegrationType,
)

logger = logging.getLogger(__name__)


class CalendarAdapter(IntegrationAdapter[CalendarContext]):
    """
    Base class for calendar integrations.

    Subclasses implement service-specific API calls,
    while this base provides common context calculation.

    Example:
        class GoogleCalendarAdapter(CalendarAdapter):
            SERVICE_NAME = "google_calendar"

            async def _fetch_raw_events(self, start, end) -> List[dict]:
                # Call Google Calendar API
                ...
    """

    INTEGRATION_TYPE = IntegrationType.CALENDAR
    SUPPORTS_WRITE = False  # Phase 5.1 is read-only

    # Busy level thresholds (minutes of meetings)
    BUSY_THRESHOLD_LIGHT = 60      # < 1 hour = light
    BUSY_THRESHOLD_MODERATE = 180  # < 3 hours = moderate
    # >= 3 hours = heavy

    def __init__(self, config: IntegrationConfig):
        """Initialize calendar adapter."""
        super().__init__(config)

    # =========================================================================
    # Abstract Methods (Subclass Must Implement)
    # =========================================================================

    @abstractmethod
    async def _fetch_raw_events(
        self,
        start: datetime,
        end: datetime,
    ) -> List[dict]:
        """
        Fetch raw events from calendar API.

        Args:
            start: Start of time range
            end: End of time range

        Returns:
            List of raw event dictionaries from API

        Each event dict should have at minimum:
        - "start": ISO datetime string or {"dateTime": ..., "date": ...}
        - "end": ISO datetime string or {"dateTime": ..., "date": ...}

        Optional fields:
        - "is_deadline": bool (if service supports marking deadlines)
        """
        pass

    # =========================================================================
    # IntegrationAdapter Implementation
    # =========================================================================

    async def _fetch_context(self) -> CalendarContext:
        """
        Fetch and process calendar context.

        Returns:
            CalendarContext with aggregated calendar info
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_end = today_start + timedelta(days=2)

        # Fetch events for today and tomorrow
        raw_events = await self._fetch_raw_events(today_start, tomorrow_end)

        # Convert to CalendarEvent objects
        events = self._parse_events(raw_events)

        # Calculate context
        return self._calculate_context(events, now)

    def _create_empty_context(self) -> CalendarContext:
        """Create empty calendar context."""
        return CalendarContext.empty()

    # =========================================================================
    # Event Parsing
    # =========================================================================

    def _parse_events(self, raw_events: List[dict]) -> List[CalendarEvent]:
        """
        Parse raw events into CalendarEvent objects.

        Args:
            raw_events: List of raw event dictionaries

        Returns:
            List of CalendarEvent objects
        """
        events = []

        for raw in raw_events:
            try:
                event = self._parse_single_event(raw)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse event: {e}")
                continue

        # Sort by start time
        events.sort(key=lambda e: e.start)

        # Detect conflicts
        self._detect_conflicts(events)

        return events

    def _parse_single_event(self, raw: dict) -> Optional[CalendarEvent]:
        """
        Parse a single raw event.

        Args:
            raw: Raw event dictionary

        Returns:
            CalendarEvent or None if parsing fails
        """
        # Handle different datetime formats
        start = self._parse_datetime(raw.get("start"))
        end = self._parse_datetime(raw.get("end"))

        if not start or not end:
            return None

        # Check if all-day event
        is_all_day = self._is_all_day(raw)

        # Check if deadline (if service supports it)
        is_deadline = raw.get("is_deadline", False)

        return CalendarEvent(
            start=start,
            end=end,
            is_all_day=is_all_day,
            is_deadline=is_deadline,
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
                return datetime.fromisoformat(dt_value.replace("Z", "+00:00"))
            except ValueError:
                return None

        if isinstance(dt_value, dict):
            # Google Calendar format: {"dateTime": "...", "timeZone": "..."}
            # or {"date": "2024-01-15"} for all-day
            if "dateTime" in dt_value:
                return self._parse_datetime(dt_value["dateTime"])
            if "date" in dt_value:
                try:
                    return datetime.strptime(dt_value["date"], "%Y-%m-%d")
                except ValueError:
                    return None

        return None

    def _is_all_day(self, raw: dict) -> bool:
        """Check if event is all-day."""
        start = raw.get("start")
        if isinstance(start, dict) and "date" in start and "dateTime" not in start:
            return True
        return False

    def _detect_conflicts(self, events: List[CalendarEvent]) -> None:
        """
        Detect overlapping events and mark conflicts.

        Args:
            events: List of events (modified in place)
        """
        for i, event in enumerate(events):
            if event.is_all_day:
                continue

            for other in events[i + 1:]:
                if other.is_all_day:
                    continue

                # Check overlap
                if event.start < other.end and other.start < event.end:
                    event.has_conflicts = True
                    other.has_conflicts = True

    # =========================================================================
    # Context Calculation
    # =========================================================================

    def _calculate_context(
        self,
        events: List[CalendarEvent],
        now: datetime,
    ) -> CalendarContext:
        """
        Calculate calendar context from events.

        Args:
            events: List of CalendarEvent objects
            now: Current datetime

        Returns:
            CalendarContext with calculated values
        """
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        tomorrow_start = today_end
        tomorrow_end = tomorrow_start + timedelta(days=1)

        # Filter events by day
        today_events = [
            e for e in events
            if e.start < today_end and e.end > today_start
        ]
        tomorrow_events = [
            e for e in events
            if e.start < tomorrow_end and e.end > tomorrow_start
        ]

        # Calculate busy minutes today (excluding all-day)
        busy_minutes = sum(
            e.duration_minutes for e in today_events
            if not e.is_all_day and e.end > now
        )

        # Find next event
        future_events = [e for e in events if e.start > now and not e.is_all_day]
        next_event_minutes = None
        if future_events:
            next_event = min(future_events, key=lambda e: e.start)
            next_event_minutes = int((next_event.start - now).total_seconds() / 60)

        # Find next deadline
        deadlines = [e for e in events if e.is_deadline and e.start > now]
        next_deadline_hours = None
        if deadlines:
            next_deadline = min(deadlines, key=lambda e: e.start)
            next_deadline_hours = int((next_deadline.start - now).total_seconds() / 3600)

        # Check for conflicts today
        has_conflicts = any(e.has_conflicts for e in today_events)

        # Calculate busy level
        busy_level = self._calculate_busy_level(busy_minutes)

        return CalendarContext(
            events_today=len(today_events),
            events_tomorrow=len(tomorrow_events),
            total_busy_minutes_today=busy_minutes,
            next_event_in_minutes=next_event_minutes,
            next_deadline_in_hours=next_deadline_hours,
            has_conflicts_today=has_conflicts,
            busy_level=busy_level,
            _events=events,
        )

    def _calculate_busy_level(self, busy_minutes: int) -> str:
        """
        Calculate busy level from total busy minutes.

        Args:
            busy_minutes: Total meeting minutes today

        Returns:
            "light", "moderate", or "heavy"
        """
        if busy_minutes < self.BUSY_THRESHOLD_LIGHT:
            return "light"
        if busy_minutes < self.BUSY_THRESHOLD_MODERATE:
            return "moderate"
        return "heavy"


__all__ = ["CalendarAdapter"]
