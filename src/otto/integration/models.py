"""
Integration Models
==================

Data structures for external integration context.

Philosophy:
- Integrations are INFORMATION SOURCES, not control mechanisms
- Privacy-first: Only metadata, never raw content
- Graceful degradation: Missing integrations don't break OTTO
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class IntegrationStatus(Enum):
    """Health status of an integration."""
    HEALTHY = "healthy"           # Working normally
    DEGRADED = "degraded"         # Partial functionality
    ERROR = "error"               # Not working
    DISABLED = "disabled"         # Manually disabled
    NOT_CONFIGURED = "not_configured"  # No credentials


class IntegrationType(Enum):
    """Categories of integrations."""
    CALENDAR = "calendar"
    TASK_MANAGER = "task_manager"
    NOTES = "notes"
    # Future phases:
    # EMAIL = "email"           # Phase 5.3
    # MESSAGING = "messaging"   # Phase 5.3


class ContextSignal(Enum):
    """
    Signals derived from external context.

    These feed into PRISM signal detection and protection decisions.
    """
    CALENDAR_BUSY = "calendar_busy"           # Many meetings today
    CALENDAR_LIGHT = "calendar_light"         # Few/no meetings
    DEADLINE_APPROACHING = "deadline_approaching"  # Deadline within 24h
    TASK_OVERLOAD = "task_overload"           # Many overdue tasks
    TASK_MANAGEABLE = "task_manageable"       # Tasks under control
    NOTES_RICH = "notes_rich"                 # Good knowledge base available
    NOTES_SPARSE = "notes_sparse"             # Limited notes context
    NOTES_RECENT_ACTIVITY = "notes_recent"    # Recent note activity
    CONTEXT_UNAVAILABLE = "context_unavailable"   # Integration down


@dataclass
class HealthStatus:
    """
    Health status of an integration.

    Attributes:
        status: Current health state
        last_sync: When context was last retrieved
        error_message: If status is ERROR, what went wrong
        retry_after: If errored, when to retry
    """
    status: IntegrationStatus
    last_sync: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_after: Optional[datetime] = None

    def is_available(self) -> bool:
        """Check if integration is usable."""
        return self.status in (IntegrationStatus.HEALTHY, IntegrationStatus.DEGRADED)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "error_message": self.error_message,
            "retry_after": self.retry_after.isoformat() if self.retry_after else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthStatus":
        """Deserialize from dictionary."""
        return cls(
            status=IntegrationStatus(data["status"]),
            last_sync=datetime.fromisoformat(data["last_sync"]) if data.get("last_sync") else None,
            error_message=data.get("error_message"),
            retry_after=datetime.fromisoformat(data["retry_after"]) if data.get("retry_after") else None,
        )


# =============================================================================
# Calendar Context Models
# =============================================================================

@dataclass
class CalendarEvent:
    """
    Minimal event representation (privacy-first).

    NOTE: We intentionally do NOT include:
    - Event title (could contain sensitive info)
    - Description/notes
    - Attendee details
    - Location specifics

    We only track:
    - Time blocks (for busy detection)
    - Whether it's a deadline vs meeting
    """
    start: datetime
    end: datetime
    is_all_day: bool = False
    is_deadline: bool = False  # vs regular meeting
    has_conflicts: bool = False  # Overlaps with other events

    @property
    def duration_minutes(self) -> int:
        """Event duration in minutes."""
        return int((self.end - self.start).total_seconds() / 60)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "is_all_day": self.is_all_day,
            "is_deadline": self.is_deadline,
            "has_conflicts": self.has_conflicts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarEvent":
        """Deserialize from dictionary."""
        return cls(
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            is_all_day=data.get("is_all_day", False),
            is_deadline=data.get("is_deadline", False),
            has_conflicts=data.get("has_conflicts", False),
        )


@dataclass
class CalendarContext:
    """
    Aggregated calendar context for cognitive state.

    This is what flows into PRISM/protection decisions.
    """
    # Event summaries (not raw events for privacy)
    events_today: int = 0
    events_tomorrow: int = 0
    total_busy_minutes_today: int = 0

    # Key signals
    next_event_in_minutes: Optional[int] = None  # Minutes until next event
    next_deadline_in_hours: Optional[int] = None  # Hours until next deadline
    has_conflicts_today: bool = False

    # Derived signals
    busy_level: str = "light"  # "light", "moderate", "heavy"

    # Raw events (for internal use only, not exposed)
    _events: List[CalendarEvent] = field(default_factory=list, repr=False)

    def get_signals(self) -> List[ContextSignal]:
        """Extract context signals for PRISM."""
        signals = []

        if self.busy_level == "heavy":
            signals.append(ContextSignal.CALENDAR_BUSY)
        elif self.busy_level == "light":
            signals.append(ContextSignal.CALENDAR_LIGHT)

        if self.next_deadline_in_hours is not None and self.next_deadline_in_hours <= 24:
            signals.append(ContextSignal.DEADLINE_APPROACHING)

        return signals

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (excluding raw events)."""
        return {
            "events_today": self.events_today,
            "events_tomorrow": self.events_tomorrow,
            "total_busy_minutes_today": self.total_busy_minutes_today,
            "next_event_in_minutes": self.next_event_in_minutes,
            "next_deadline_in_hours": self.next_deadline_in_hours,
            "has_conflicts_today": self.has_conflicts_today,
            "busy_level": self.busy_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarContext":
        """Deserialize from dictionary."""
        return cls(
            events_today=data.get("events_today", 0),
            events_tomorrow=data.get("events_tomorrow", 0),
            total_busy_minutes_today=data.get("total_busy_minutes_today", 0),
            next_event_in_minutes=data.get("next_event_in_minutes"),
            next_deadline_in_hours=data.get("next_deadline_in_hours"),
            has_conflicts_today=data.get("has_conflicts_today", False),
            busy_level=data.get("busy_level", "light"),
        )

    @classmethod
    def empty(cls) -> "CalendarContext":
        """Create empty context (when calendar unavailable)."""
        return cls()


# =============================================================================
# Task Context Models
# =============================================================================

@dataclass
class TaskSummary:
    """
    Minimal task representation (privacy-first).

    NOTE: We intentionally do NOT include:
    - Task title/description
    - Project details
    - Notes or comments

    We only track:
    - Due dates (for deadline detection)
    - Priority level
    - Completion status
    """
    due_date: Optional[datetime] = None
    is_overdue: bool = False
    priority: str = "normal"  # "low", "normal", "high", "urgent"
    is_completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_overdue": self.is_overdue,
            "priority": self.priority,
            "is_completed": self.is_completed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskSummary":
        """Deserialize from dictionary."""
        return cls(
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            is_overdue=data.get("is_overdue", False),
            priority=data.get("priority", "normal"),
            is_completed=data.get("is_completed", False),
        )


@dataclass
class TaskContext:
    """
    Aggregated task context for cognitive state.
    """
    # Counts (privacy-safe)
    total_tasks: int = 0
    overdue_count: int = 0
    due_today_count: int = 0
    due_this_week_count: int = 0
    high_priority_count: int = 0

    # Key signals
    oldest_overdue_days: Optional[int] = None  # Days since oldest overdue
    next_deadline_in_hours: Optional[int] = None

    # Derived signals
    load_level: str = "manageable"  # "light", "manageable", "heavy", "overloaded"

    def get_signals(self) -> List[ContextSignal]:
        """Extract context signals for PRISM."""
        signals = []

        if self.load_level == "overloaded" or self.overdue_count >= 5:
            signals.append(ContextSignal.TASK_OVERLOAD)
        elif self.load_level in ("light", "manageable"):
            signals.append(ContextSignal.TASK_MANAGEABLE)

        if self.next_deadline_in_hours is not None and self.next_deadline_in_hours <= 24:
            signals.append(ContextSignal.DEADLINE_APPROACHING)

        return signals

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_tasks": self.total_tasks,
            "overdue_count": self.overdue_count,
            "due_today_count": self.due_today_count,
            "due_this_week_count": self.due_this_week_count,
            "high_priority_count": self.high_priority_count,
            "oldest_overdue_days": self.oldest_overdue_days,
            "next_deadline_in_hours": self.next_deadline_in_hours,
            "load_level": self.load_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        """Deserialize from dictionary."""
        return cls(
            total_tasks=data.get("total_tasks", 0),
            overdue_count=data.get("overdue_count", 0),
            due_today_count=data.get("due_today_count", 0),
            due_this_week_count=data.get("due_this_week_count", 0),
            high_priority_count=data.get("high_priority_count", 0),
            oldest_overdue_days=data.get("oldest_overdue_days"),
            next_deadline_in_hours=data.get("next_deadline_in_hours"),
            load_level=data.get("load_level", "manageable"),
        )

    @classmethod
    def empty(cls) -> "TaskContext":
        """Create empty context (when task manager unavailable)."""
        return cls()


# =============================================================================
# Notes Context Models
# =============================================================================

@dataclass
class NotesContext:
    """
    Aggregated notes context for cognitive state.

    Privacy-first: We only track metadata, never note content.
    - File counts and distribution
    - Topic categories (from folder structure)
    - Recency of activity
    - Availability for search

    NOTE: We intentionally do NOT include:
    - Note titles or content
    - Personal information
    - Specific file paths
    """
    # Counts (privacy-safe)
    total_notes: int = 0
    notes_modified_today: int = 0
    notes_modified_this_week: int = 0

    # Topic distribution (from folder names, not content)
    topic_counts: Dict[str, int] = field(default_factory=dict)

    # Key signals
    has_searchable_notes: bool = False
    most_recent_activity_hours: Optional[int] = None  # Hours since last modification

    # Derived signals
    richness_level: str = "sparse"  # "sparse", "moderate", "rich"

    def get_signals(self) -> List["ContextSignal"]:
        """Extract context signals for PRISM."""
        signals = []

        if self.richness_level == "rich":
            signals.append(ContextSignal.NOTES_RICH)
        elif self.richness_level == "sparse":
            signals.append(ContextSignal.NOTES_SPARSE)

        if self.notes_modified_today > 0:
            signals.append(ContextSignal.NOTES_RECENT_ACTIVITY)

        return signals

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_notes": self.total_notes,
            "notes_modified_today": self.notes_modified_today,
            "notes_modified_this_week": self.notes_modified_this_week,
            "topic_counts": self.topic_counts,
            "has_searchable_notes": self.has_searchable_notes,
            "most_recent_activity_hours": self.most_recent_activity_hours,
            "richness_level": self.richness_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotesContext":
        """Deserialize from dictionary."""
        return cls(
            total_notes=data.get("total_notes", 0),
            notes_modified_today=data.get("notes_modified_today", 0),
            notes_modified_this_week=data.get("notes_modified_this_week", 0),
            topic_counts=data.get("topic_counts", {}),
            has_searchable_notes=data.get("has_searchable_notes", False),
            most_recent_activity_hours=data.get("most_recent_activity_hours"),
            richness_level=data.get("richness_level", "sparse"),
        )

    @classmethod
    def empty(cls) -> "NotesContext":
        """Create empty context (when notes unavailable)."""
        return cls()


# =============================================================================
# Aggregated External Context
# =============================================================================

@dataclass
class ExternalContext:
    """
    Combined context from all integrations.

    This is the single source of truth for external signals
    that flows into CognitiveState.
    """
    calendar: Optional[CalendarContext] = None
    tasks: Optional[TaskContext] = None
    notes: Optional[NotesContext] = None

    # Metadata
    last_updated: Optional[datetime] = None
    available_integrations: List[str] = field(default_factory=list)

    def get_all_signals(self) -> List[ContextSignal]:
        """Get all context signals from all integrations."""
        signals = []

        if self.calendar:
            signals.extend(self.calendar.get_signals())
        if self.tasks:
            signals.extend(self.tasks.get_signals())
        if self.notes:
            signals.extend(self.notes.get_signals())

        # If no integrations available, add that signal
        if not self.calendar and not self.tasks and not self.notes:
            signals.append(ContextSignal.CONTEXT_UNAVAILABLE)

        return signals

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "calendar": self.calendar.to_dict() if self.calendar else None,
            "tasks": self.tasks.to_dict() if self.tasks else None,
            "notes": self.notes.to_dict() if self.notes else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "available_integrations": self.available_integrations,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExternalContext":
        """Deserialize from dictionary."""
        return cls(
            calendar=CalendarContext.from_dict(data["calendar"]) if data.get("calendar") else None,
            tasks=TaskContext.from_dict(data["tasks"]) if data.get("tasks") else None,
            notes=NotesContext.from_dict(data["notes"]) if data.get("notes") else None,
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None,
            available_integrations=data.get("available_integrations", []),
        )

    @classmethod
    def empty(cls) -> "ExternalContext":
        """Create empty context."""
        return cls()


# =============================================================================
# Configuration Models
# =============================================================================

@dataclass
class IntegrationConfig:
    """
    Configuration for a single integration.

    Auth tokens are stored in OS keyring (via encryption module),
    not in this config.
    """
    integration_type: IntegrationType
    service_name: str  # e.g., "google_calendar", "todoist"
    enabled: bool = True

    # Sync settings
    sync_interval_minutes: int = 5
    last_sync: Optional[datetime] = None

    # Service-specific settings (non-sensitive)
    settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "integration_type": self.integration_type.value,
            "service_name": self.service_name,
            "enabled": self.enabled,
            "sync_interval_minutes": self.sync_interval_minutes,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntegrationConfig":
        """Deserialize from dictionary."""
        return cls(
            integration_type=IntegrationType(data["integration_type"]),
            service_name=data["service_name"],
            enabled=data.get("enabled", True),
            sync_interval_minutes=data.get("sync_interval_minutes", 5),
            last_sync=datetime.fromisoformat(data["last_sync"]) if data.get("last_sync") else None,
            settings=data.get("settings", {}),
        )


__all__ = [
    # Enums
    "IntegrationStatus",
    "IntegrationType",
    "ContextSignal",
    # Health
    "HealthStatus",
    # Calendar
    "CalendarEvent",
    "CalendarContext",
    # Tasks
    "TaskSummary",
    "TaskContext",
    # Notes
    "NotesContext",
    # Aggregated
    "ExternalContext",
    # Config
    "IntegrationConfig",
]
