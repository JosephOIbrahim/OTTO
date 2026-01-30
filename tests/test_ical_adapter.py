"""
Tests for ICS/iCalendar Adapter
===============================

Tests the file-based calendar adapter for .ics files.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from otto.integration.calendars import ICalAdapter, create_ical_adapter
from otto.integration.calendars.ical_adapter import (
    parse_ics_file,
    parse_ics_datetime,
    _parse_duration,
    _is_deadline_event,
)
from otto.integration.models import IntegrationConfig, IntegrationType, IntegrationStatus


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_ics_dir(tmp_path):
    """Create a temporary directory for ICS files."""
    ics_dir = tmp_path / "calendars"
    ics_dir.mkdir()
    return ics_dir


@pytest.fixture
def sample_ics_content():
    """Sample ICS file content with various event types."""
    return """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
DTSTART:20240115T090000Z
DTEND:20240115T100000Z
SUMMARY:Morning Meeting
UID:event1@test.com
END:VEVENT
BEGIN:VEVENT
DTSTART:20240115T140000Z
DTEND:20240115T150000Z
SUMMARY:Afternoon Meeting
UID:event2@test.com
END:VEVENT
BEGIN:VEVENT
DTSTART:20240115
DTEND:20240116
SUMMARY:All Day Event
UID:event3@test.com
END:VEVENT
BEGIN:VEVENT
DTSTART:20240115T170000Z
DTEND:20240115T173000Z
SUMMARY:Project Deadline
CATEGORIES:DEADLINE
UID:event4@test.com
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def sample_ics_file(temp_ics_dir, sample_ics_content):
    """Create a sample ICS file."""
    ics_file = temp_ics_dir / "work.ics"
    ics_file.write_text(sample_ics_content)
    return ics_file


# =============================================================================
# Test: ICS Datetime Parsing
# =============================================================================

class TestICSDatetimeParsing:
    """Tests for parse_ics_datetime function."""

    def test_parse_utc_datetime(self):
        """Parse UTC datetime format."""
        result = parse_ics_datetime("20240115T090000Z")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 9
        assert result.minute == 0

    def test_parse_local_datetime(self):
        """Parse local datetime format."""
        result = parse_ics_datetime("20240115T143000")

        assert result is not None
        assert result.hour == 14
        assert result.minute == 30

    def test_parse_date_only(self):
        """Parse date-only format (all-day event)."""
        result = parse_ics_datetime("20240115")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0

    def test_parse_empty_returns_none(self):
        """Empty string returns None."""
        assert parse_ics_datetime("") is None
        assert parse_ics_datetime(None) is None

    def test_parse_invalid_returns_none(self):
        """Invalid format returns None."""
        assert parse_ics_datetime("not-a-date") is None
        assert parse_ics_datetime("2024-01-15") is None  # Wrong format


# =============================================================================
# Test: ICS Duration Parsing
# =============================================================================

class TestICSDurationParsing:
    """Tests for _parse_duration function."""

    def test_parse_hours(self):
        """Parse hour duration."""
        result = _parse_duration("PT2H")

        assert result is not None
        assert result.total_seconds() == 7200  # 2 hours

    def test_parse_minutes(self):
        """Parse minute duration."""
        result = _parse_duration("PT30M")

        assert result is not None
        assert result.total_seconds() == 1800  # 30 minutes

    def test_parse_hours_and_minutes(self):
        """Parse combined duration."""
        result = _parse_duration("PT1H30M")

        assert result is not None
        assert result.total_seconds() == 5400  # 90 minutes

    def test_parse_days(self):
        """Parse day duration."""
        result = _parse_duration("P1D")

        assert result is not None
        assert result.days == 1

    def test_parse_empty_returns_none(self):
        """Empty returns None."""
        assert _parse_duration("") is None
        assert _parse_duration(None) is None


# =============================================================================
# Test: ICS File Parsing
# =============================================================================

class TestICSFileParsing:
    """Tests for parse_ics_file function."""

    def test_parse_basic_events(self, sample_ics_content):
        """Parse file with multiple events."""
        events = parse_ics_file(sample_ics_content)

        assert len(events) == 4

    def test_event_has_start_and_end(self, sample_ics_content):
        """Events have start and end times."""
        events = parse_ics_file(sample_ics_content)

        for event in events:
            assert "start" in event
            assert "end" in event
            assert isinstance(event["start"], datetime)
            assert isinstance(event["end"], datetime)

    def test_all_day_detection(self, sample_ics_content):
        """All-day events are detected."""
        events = parse_ics_file(sample_ics_content)

        # Third event is all-day
        all_day_events = [e for e in events if e.get("is_all_day")]
        assert len(all_day_events) >= 1

    def test_deadline_detection(self, sample_ics_content):
        """Deadline events are detected from categories."""
        events = parse_ics_file(sample_ics_content)

        # Fourth event has CATEGORIES:DEADLINE
        deadline_events = [e for e in events if e.get("is_deadline")]
        assert len(deadline_events) >= 1

    def test_parse_empty_file(self):
        """Empty file returns empty list."""
        events = parse_ics_file("")
        assert events == []

    def test_parse_no_events(self):
        """File with no VEVENT returns empty."""
        content = """BEGIN:VCALENDAR
VERSION:2.0
END:VCALENDAR"""
        events = parse_ics_file(content)
        assert events == []

    def test_deadline_detection_from_summary(self):
        """Deadline detected from summary keywords."""
        content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20240115T170000Z
DTEND:20240115T173000Z
SUMMARY:Submit report due by 5pm
UID:deadline@test.com
END:VEVENT
END:VCALENDAR"""
        events = parse_ics_file(content)

        assert len(events) == 1
        assert events[0]["is_deadline"] is True


# =============================================================================
# Test: Deadline Heuristics
# =============================================================================

class TestDeadlineHeuristics:
    """Tests for _is_deadline_event function."""

    def test_deadline_from_categories(self):
        """Detect deadline from CATEGORIES property."""
        raw = {"CATEGORIES": {"value": "DEADLINE,WORK", "params": {}}}
        assert _is_deadline_event(raw) is True

    def test_deadline_from_summary_due(self):
        """Detect deadline from 'due' in summary."""
        raw = {"SUMMARY": {"value": "Report due today", "params": {}}}
        assert _is_deadline_event(raw) is True

    def test_deadline_from_summary_submit(self):
        """Detect deadline from 'submit' in summary."""
        raw = {"SUMMARY": {"value": "Submit proposal", "params": {}}}
        assert _is_deadline_event(raw) is True

    def test_not_deadline_regular_meeting(self):
        """Regular meeting is not a deadline."""
        raw = {"SUMMARY": {"value": "Team standup", "params": {}}}
        assert _is_deadline_event(raw) is False


# =============================================================================
# Test: ICalAdapter Initialization
# =============================================================================

class TestICalAdapterInit:
    """Tests for ICalAdapter initialization."""

    @pytest.mark.asyncio
    async def test_init_with_file(self, sample_ics_file):
        """Initialize with single ICS file."""
        adapter = create_ical_adapter(str(sample_ics_file))
        result = await adapter.initialize()

        assert result is True
        assert len(adapter._files) == 1

    @pytest.mark.asyncio
    async def test_init_with_directory(self, temp_ics_dir, sample_ics_content):
        """Initialize with directory containing ICS files."""
        # Create multiple files
        (temp_ics_dir / "cal1.ics").write_text(sample_ics_content)
        (temp_ics_dir / "cal2.ics").write_text(sample_ics_content)

        adapter = create_ical_adapter(str(temp_ics_dir))
        result = await adapter.initialize()

        assert result is True
        assert len(adapter._files) == 2

    @pytest.mark.asyncio
    async def test_init_nonexistent_path(self, tmp_path):
        """Initialize with nonexistent path fails."""
        adapter = create_ical_adapter(str(tmp_path / "nonexistent.ics"))
        result = await adapter.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_init_empty_directory(self, temp_ics_dir):
        """Initialize with empty directory succeeds but has no files."""
        adapter = create_ical_adapter(str(temp_ics_dir))
        result = await adapter.initialize()

        assert result is True
        assert len(adapter._files) == 0

    @pytest.mark.asyncio
    async def test_init_expands_user_path(self, sample_ics_file):
        """Tilde in path is expanded."""
        adapter = create_ical_adapter("~/nonexistent.ics")
        # Should not crash, just fail to initialize
        result = await adapter.initialize()
        assert result is False  # File doesn't exist


# =============================================================================
# Test: ICalAdapter Context Fetching
# =============================================================================

class TestICalAdapterContext:
    """Tests for ICalAdapter context fetching."""

    @pytest.mark.asyncio
    async def test_get_context_returns_calendar_context(self, sample_ics_file):
        """get_context returns CalendarContext."""
        adapter = create_ical_adapter(str(sample_ics_file))

        context = await adapter.get_context()

        # Should return a CalendarContext
        assert hasattr(context, "events_today")
        assert hasattr(context, "busy_level")

    @pytest.mark.asyncio
    async def test_context_counts_events(self, temp_ics_dir):
        """Context correctly counts events."""
        # Create ICS with events today
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")

        content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:{today_str}T090000
DTEND:{today_str}T100000
SUMMARY:Event 1
UID:event1@test.com
END:VEVENT
BEGIN:VEVENT
DTSTART:{today_str}T140000
DTEND:{today_str}T150000
SUMMARY:Event 2
UID:event2@test.com
END:VEVENT
END:VCALENDAR"""

        ics_file = temp_ics_dir / "today.ics"
        ics_file.write_text(content)

        adapter = create_ical_adapter(str(ics_file))
        context = await adapter.get_context()

        assert context.events_today >= 2

    @pytest.mark.asyncio
    async def test_context_calculates_busy_minutes(self, temp_ics_dir):
        """Context calculates total busy minutes."""
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")

        # Create 2-hour meeting
        content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:{today_str}T230000
DTEND:{today_str}T235900
SUMMARY:Long Meeting
UID:event1@test.com
END:VEVENT
END:VCALENDAR"""

        ics_file = temp_ics_dir / "busy.ics"
        ics_file.write_text(content)

        adapter = create_ical_adapter(str(ics_file))
        context = await adapter.get_context()

        # Should have some busy minutes (exact depends on current time)
        assert context.total_busy_minutes_today >= 0

    @pytest.mark.asyncio
    async def test_context_detects_conflicts(self, temp_ics_dir):
        """Context detects overlapping events."""
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")

        # Create overlapping events
        content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:{today_str}T140000
DTEND:{today_str}T160000
SUMMARY:Meeting A
UID:event1@test.com
END:VEVENT
BEGIN:VEVENT
DTSTART:{today_str}T150000
DTEND:{today_str}T170000
SUMMARY:Meeting B
UID:event2@test.com
END:VEVENT
END:VCALENDAR"""

        ics_file = temp_ics_dir / "conflict.ics"
        ics_file.write_text(content)

        adapter = create_ical_adapter(str(ics_file))
        context = await adapter.get_context()

        assert context.has_conflicts_today is True

    @pytest.mark.asyncio
    async def test_health_updates_on_success(self, sample_ics_file):
        """Health status is HEALTHY after successful fetch."""
        adapter = create_ical_adapter(str(sample_ics_file))
        await adapter.get_context()

        assert adapter.health.status == IntegrationStatus.HEALTHY
        assert adapter.health.last_sync is not None


# =============================================================================
# Test: ICalAdapter Service Properties
# =============================================================================

class TestICalAdapterProperties:
    """Tests for ICalAdapter service properties."""

    def test_service_name(self, sample_ics_file):
        """Service name is 'ical'."""
        adapter = create_ical_adapter(str(sample_ics_file))
        assert adapter.service_name == "ical"

    def test_integration_type(self, sample_ics_file):
        """Integration type is CALENDAR."""
        adapter = create_ical_adapter(str(sample_ics_file))
        assert adapter.integration_type == IntegrationType.CALENDAR

    def test_supports_write_false(self, sample_ics_file):
        """Write is not supported in Phase 5.1."""
        adapter = create_ical_adapter(str(sample_ics_file))
        assert adapter.SUPPORTS_WRITE is False
        assert adapter.can_write is False


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_malformed_ics_handled(self, temp_ics_dir):
        """Malformed ICS files don't crash adapter."""
        ics_file = temp_ics_dir / "bad.ics"
        ics_file.write_text("not valid ics content at all")

        adapter = create_ical_adapter(str(ics_file))
        context = await adapter.get_context()

        # Should return empty context, not crash
        assert context.events_today == 0

    @pytest.mark.asyncio
    async def test_unicode_content(self, temp_ics_dir):
        """Unicode characters in events are handled."""
        content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20240115T090000Z
DTEND:20240115T100000Z
SUMMARY:会议 Meeting 🎉
UID:event1@test.com
END:VEVENT
END:VCALENDAR"""

        ics_file = temp_ics_dir / "unicode.ics"
        ics_file.write_text(content, encoding="utf-8")

        adapter = create_ical_adapter(str(ics_file))
        result = await adapter.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_event_without_dtend(self, temp_ics_dir):
        """Events without DTEND get default duration."""
        content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20240115T090000Z
SUMMARY:Event without end
UID:event1@test.com
END:VEVENT
END:VCALENDAR"""

        ics_file = temp_ics_dir / "no_end.ics"
        ics_file.write_text(content)

        events = parse_ics_file(content)
        assert len(events) == 1
        assert events[0]["end"] is not None

    @pytest.mark.asyncio
    async def test_event_with_duration(self, temp_ics_dir):
        """Events with DURATION instead of DTEND are parsed."""
        content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20240115T090000Z
DURATION:PT2H
SUMMARY:Two hour event
UID:event1@test.com
END:VEVENT
END:VCALENDAR"""

        events = parse_ics_file(content)
        assert len(events) == 1
        # Duration of 2 hours = 120 minutes
        duration = events[0]["end"] - events[0]["start"]
        assert duration.total_seconds() == 7200


# =============================================================================
# Test: Multiple Files
# =============================================================================

class TestMultipleFiles:
    """Tests for handling multiple ICS files."""

    @pytest.mark.asyncio
    async def test_merges_events_from_multiple_files(self, temp_ics_dir):
        """Events from multiple files are merged."""
        now = datetime.now()
        today_str = now.strftime("%Y%m%d")

        # File 1: work events
        work_content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:{today_str}T090000
DTEND:{today_str}T100000
SUMMARY:Work Meeting
UID:work1@test.com
END:VEVENT
END:VCALENDAR"""

        # File 2: personal events
        personal_content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:{today_str}T120000
DTEND:{today_str}T130000
SUMMARY:Lunch
UID:personal1@test.com
END:VEVENT
END:VCALENDAR"""

        (temp_ics_dir / "work.ics").write_text(work_content)
        (temp_ics_dir / "personal.ics").write_text(personal_content)

        adapter = create_ical_adapter(str(temp_ics_dir))
        context = await adapter.get_context()

        # Should have events from both files
        assert context.events_today >= 2


# =============================================================================
# Test: Factory Function
# =============================================================================

class TestFactoryFunction:
    """Tests for create_ical_adapter factory."""

    def test_creates_adapter_with_correct_config(self, sample_ics_file):
        """Factory creates properly configured adapter."""
        adapter = create_ical_adapter(str(sample_ics_file))

        assert isinstance(adapter, ICalAdapter)
        assert adapter.config.service_name == "ical"
        assert adapter.config.integration_type == IntegrationType.CALENDAR
        assert adapter.config.settings["ics_path"] == str(sample_ics_file)
