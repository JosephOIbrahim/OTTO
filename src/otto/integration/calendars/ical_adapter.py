"""
ICS/iCalendar Adapter
=====================

File-based calendar adapter that reads .ics files.

This provides calendar context without requiring OAuth setup:
- Export your calendar as .ics from Google, Outlook, or Apple Calendar
- Point OTTO to the file path
- OTTO reads events and calculates context

Use Cases:
1. Quick setup without OAuth complexity
2. Calendars that don't have API access
3. Local/offline calendar files
4. Testing and development

Determinism:
- DETERMINISTIC: Same file → Same events → Same context
- FIXED: Parsing rules are immutable
- BOUNDED: Max events limit prevents memory issues
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..adapter import IntegrationError
from ..models import IntegrationConfig, IntegrationType
from .base import CalendarAdapter

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED - determinism compliant)
# =============================================================================

MAX_EVENTS_PER_FILE = 1000  # Prevent memory issues with huge calendars
MAX_FILES = 10              # Max .ics files to read
ENCODING = "utf-8"          # Standard iCalendar encoding


# =============================================================================
# ICS Parser (Minimal, No External Dependencies)
# =============================================================================

class ICSParseError(IntegrationError):
    """Error parsing ICS file."""
    pass


def parse_ics_datetime(value: str, params: Dict[str, str] = None) -> Optional[datetime]:
    """
    Parse iCalendar datetime value.

    Args:
        value: Date/datetime string (e.g., "20240115T090000Z" or "20240115")
        params: Optional parameters (e.g., {"TZID": "America/New_York"})

    Returns:
        Parsed datetime or None if invalid

    Formats supported:
    - "20240115T090000Z" - UTC datetime
    - "20240115T090000" - Local datetime
    - "20240115" - All-day date
    """
    if not value:
        return None

    value = value.strip()
    params = params or {}

    try:
        # All-day date format: YYYYMMDD
        if len(value) == 8 and value.isdigit():
            return datetime.strptime(value, "%Y%m%d")

        # DateTime format: YYYYMMDDTHHMMSS or YYYYMMDDTHHMMSSZ
        if "T" in value:
            if value.endswith("Z"):
                # UTC time
                dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
                return dt.replace(tzinfo=timezone.utc)
            else:
                # Local time (ignore TZID for simplicity in v1)
                return datetime.strptime(value, "%Y%m%dT%H%M%S")

    except ValueError as e:
        logger.debug(f"Failed to parse datetime '{value}': {e}")

    return None


def parse_ics_file(content: str) -> List[Dict[str, Any]]:
    """
    Parse ICS file content into event dictionaries.

    Args:
        content: Raw ICS file content

    Returns:
        List of event dictionaries with 'start', 'end', 'is_all_day', 'is_deadline'

    This is a minimal parser that handles common ICS patterns.
    Does not support:
    - Recurring events (RRULE) - would require complex expansion
    - Multiple timezones in one file
    - Non-VEVENT components (VTODO, VJOURNAL)
    """
    events = []
    lines = content.replace("\r\n ", "").replace("\r\n\t", "").split("\r\n")

    # Also handle Unix line endings
    if len(lines) == 1:
        lines = content.replace("\n ", "").replace("\n\t", "").split("\n")

    in_event = False
    current_event: Dict[str, Any] = {}

    for line in lines:
        line = line.strip()

        if line == "BEGIN:VEVENT":
            in_event = True
            current_event = {}

        elif line == "END:VEVENT":
            in_event = False
            if current_event:
                event = _build_event(current_event)
                if event:
                    events.append(event)
                    if len(events) >= MAX_EVENTS_PER_FILE:
                        logger.warning(f"Reached max events limit ({MAX_EVENTS_PER_FILE})")
                        break
            current_event = {}

        elif in_event and ":" in line:
            # Parse property
            key, value = line.split(":", 1)

            # Handle parameters (e.g., "DTSTART;TZID=America/New_York")
            params = {}
            if ";" in key:
                parts = key.split(";")
                key = parts[0]
                for param in parts[1:]:
                    if "=" in param:
                        pk, pv = param.split("=", 1)
                        params[pk] = pv

            current_event[key] = {"value": value, "params": params}

    return events


def _build_event(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Build event dict from raw ICS properties.

    Args:
        raw: Raw property dict from parsing

    Returns:
        Event dict with start, end, is_all_day, is_deadline
    """
    # Get DTSTART
    dtstart_prop = raw.get("DTSTART", {})
    dtstart = parse_ics_datetime(
        dtstart_prop.get("value", ""),
        dtstart_prop.get("params", {})
    )

    if not dtstart:
        return None

    # Get DTEND (or calculate from DURATION)
    dtend_prop = raw.get("DTEND", {})
    dtend = parse_ics_datetime(
        dtend_prop.get("value", ""),
        dtend_prop.get("params", {})
    )

    # If no DTEND, check for DURATION
    if not dtend:
        duration_prop = raw.get("DURATION", {})
        duration = _parse_duration(duration_prop.get("value", ""))
        if duration:
            dtend = dtstart + duration
        else:
            # Default to 1 hour for timed events, 1 day for all-day
            is_all_day = len(dtstart_prop.get("value", "")) == 8
            if is_all_day:
                dtend = dtstart + timedelta(days=1)
            else:
                dtend = dtstart + timedelta(hours=1)

    # Determine if all-day
    dtstart_value = dtstart_prop.get("value", "")
    is_all_day = len(dtstart_value) == 8 and dtstart_value.isdigit()

    # Check if deadline (heuristic: check categories or summary)
    is_deadline = _is_deadline_event(raw)

    return {
        "start": dtstart,
        "end": dtend,
        "is_all_day": is_all_day,
        "is_deadline": is_deadline,
    }


def _parse_duration(value: str) -> Optional[timedelta]:
    """
    Parse ICS DURATION format.

    Args:
        value: Duration string (e.g., "PT1H30M", "P1D")

    Returns:
        timedelta or None
    """
    if not value:
        return None

    # Simple duration parsing (P[n]D or PT[n]H[n]M)
    try:
        days = 0
        hours = 0
        minutes = 0

        # Match days
        day_match = re.search(r"(\d+)D", value)
        if day_match:
            days = int(day_match.group(1))

        # Match hours
        hour_match = re.search(r"(\d+)H", value)
        if hour_match:
            hours = int(hour_match.group(1))

        # Match minutes
        min_match = re.search(r"(\d+)M", value)
        if min_match:
            minutes = int(min_match.group(1))

        if days or hours or minutes:
            return timedelta(days=days, hours=hours, minutes=minutes)

    except (ValueError, AttributeError):
        pass

    return None


def _is_deadline_event(raw: Dict[str, Any]) -> bool:
    """
    Heuristically determine if event is a deadline.

    Args:
        raw: Raw event properties

    Returns:
        True if likely a deadline

    Heuristics:
    - CATEGORIES contains "deadline"
    - SUMMARY contains "deadline", "due", "submit"
    """
    # Check categories
    categories = raw.get("CATEGORIES", {}).get("value", "").lower()
    if "deadline" in categories:
        return True

    # Check summary (title)
    summary = raw.get("SUMMARY", {}).get("value", "").lower()
    deadline_words = ["deadline", "due", "submit", "expires", "final"]
    if any(word in summary for word in deadline_words):
        return True

    return False


# =============================================================================
# ICalAdapter
# =============================================================================

class ICalAdapter(CalendarAdapter):
    """
    ICS/iCalendar file-based calendar adapter.

    Reads .ics files from a configured directory and provides
    calendar context without requiring OAuth or API access.

    Config Settings:
        ics_path: Path to .ics file or directory containing .ics files

    Example:
        config = IntegrationConfig(
            integration_type=IntegrationType.CALENDAR,
            service_name="ical",
            settings={"ics_path": "~/.calendars/work.ics"}
        )
        adapter = ICalAdapter(config)
        context = await adapter.get_context()
    """

    SERVICE_NAME = "ical"
    INTEGRATION_TYPE = IntegrationType.CALENDAR
    SUPPORTS_WRITE = False  # Read-only in Phase 5.1

    def __init__(self, config: IntegrationConfig):
        """
        Initialize ICS adapter.

        Args:
            config: Configuration with 'ics_path' in settings
        """
        super().__init__(config)
        self._ics_path: Optional[Path] = None
        self._files: List[Path] = []

    # =========================================================================
    # IntegrationAdapter Implementation
    # =========================================================================

    async def initialize(self) -> bool:
        """
        Initialize adapter by validating the ICS path.

        Returns:
            True if path exists and contains valid .ics files
        """
        ics_path_str = self.config.settings.get("ics_path")
        if not ics_path_str:
            logger.error("ICalAdapter: No 'ics_path' in config settings")
            return False

        # Expand user path
        self._ics_path = Path(ics_path_str).expanduser()

        if not self._ics_path.exists():
            logger.error(f"ICalAdapter: Path does not exist: {self._ics_path}")
            return False

        # Find .ics files
        if self._ics_path.is_file():
            if self._ics_path.suffix.lower() == ".ics":
                self._files = [self._ics_path]
            else:
                logger.error(f"ICalAdapter: Not an ICS file: {self._ics_path}")
                return False
        else:
            # Directory - find all .ics files
            self._files = sorted(self._ics_path.glob("*.ics"))[:MAX_FILES]

        if not self._files:
            logger.warning(f"ICalAdapter: No .ics files found in {self._ics_path}")
            # Still return True - adapter works, just no events
            return True

        logger.info(f"ICalAdapter: Found {len(self._files)} ICS file(s)")
        return True

    async def _fetch_raw_events(
        self,
        start: datetime,
        end: datetime,
    ) -> List[dict]:
        """
        Fetch events from ICS files within the time range.

        Args:
            start: Start of time range
            end: End of time range

        Returns:
            List of event dictionaries
        """
        all_events: List[dict] = []

        for ics_file in self._files:
            try:
                events = self._read_ics_file(ics_file, start, end)
                all_events.extend(events)
            except Exception as e:
                logger.warning(f"Failed to read {ics_file}: {e}")
                continue

        logger.debug(f"ICalAdapter: Found {len(all_events)} events in range")
        return all_events

    def _read_ics_file(
        self,
        path: Path,
        start: datetime,
        end: datetime,
    ) -> List[dict]:
        """
        Read and filter events from a single ICS file.

        Args:
            path: Path to ICS file
            start: Filter start
            end: Filter end

        Returns:
            Filtered event list
        """
        try:
            content = path.read_text(encoding=ENCODING)
        except UnicodeDecodeError:
            # Try latin-1 as fallback
            content = path.read_text(encoding="latin-1")

        events = parse_ics_file(content)

        # Filter to date range
        filtered = []
        for event in events:
            event_start = event.get("start")
            event_end = event.get("end")

            if not event_start or not event_end:
                continue

            # Make timezone-naive for comparison
            if event_start.tzinfo:
                event_start = event_start.replace(tzinfo=None)
            if event_end.tzinfo:
                event_end = event_end.replace(tzinfo=None)

            # Check overlap with range
            if event_start < end and event_end > start:
                filtered.append(event)

        return filtered


def create_ical_adapter(ics_path: str) -> ICalAdapter:
    """
    Factory function to create an ICalAdapter.

    Args:
        ics_path: Path to ICS file or directory

    Returns:
        Configured ICalAdapter
    """
    config = IntegrationConfig(
        integration_type=IntegrationType.CALENDAR,
        service_name="ical",
        settings={"ics_path": ics_path},
    )
    return ICalAdapter(config)


__all__ = [
    "ICalAdapter",
    "create_ical_adapter",
    "parse_ics_file",
    "parse_ics_datetime",
]
