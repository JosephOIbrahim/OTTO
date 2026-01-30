"""
OTTO OS Integration Module
==========================

External service integrations for context gathering.

Philosophy:
    Integrations are INFORMATION SOURCES, not control mechanisms.
    They provide context to help OTTO make better decisions.

Privacy First:
    - Only metadata extraction (counts, dates, busy signals)
    - Never raw content (email bodies, message text)
    - Auth tokens in OS keychain (via encryption module)

Phase 5.1 (v0.2): Read-only calendar and task context
Phase 5.2 (v0.3): Task write-back with consent
Phase 5.3 (v0.4): Email/messaging metadata

Usage:
    from otto.integration import IntegrationManager, create_integration_manager

    # Create manager
    manager = create_integration_manager(otto_dir)

    # Register adapters
    manager.register_adapter(GoogleCalendarAdapter(config))

    # Start background sync
    await manager.start()

    # Get context
    context = await manager.get_context()
    signals = context.get_all_signals()

    # Stop
    await manager.stop()
"""

from .models import (
    # Enums
    IntegrationStatus,
    IntegrationType,
    ContextSignal,
    # Health
    HealthStatus,
    # Calendar
    CalendarEvent,
    CalendarContext,
    # Tasks
    TaskSummary,
    TaskContext,
    # Notes
    NotesContext,
    # Aggregated
    ExternalContext,
    # Config
    IntegrationConfig,
)

from .adapter import (
    IntegrationAdapter,
    IntegrationError,
    AuthenticationError,
    RateLimitError,
    ServiceUnavailableError,
)

from .manager import (
    IntegrationManager,
    create_integration_manager,
)

from .calendars import CalendarAdapter, ICalAdapter, create_ical_adapter
from .tasks import TaskAdapter, JsonTaskAdapter, create_json_task_adapter
from .notes import NotesAdapter, MarkdownNotesAdapter, create_markdown_adapter
from .testing import (
    MockCalendarAdapter,
    MockTaskAdapter,
    create_mock_calendar,
    create_mock_tasks,
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
    "CalendarAdapter",
    "ICalAdapter",
    "create_ical_adapter",
    # Tasks
    "TaskSummary",
    "TaskContext",
    "TaskAdapter",
    "JsonTaskAdapter",
    "create_json_task_adapter",
    # Notes
    "NotesContext",
    "NotesAdapter",
    "MarkdownNotesAdapter",
    "create_markdown_adapter",
    # Aggregated
    "ExternalContext",
    # Config
    "IntegrationConfig",
    # Adapter
    "IntegrationAdapter",
    "IntegrationError",
    "AuthenticationError",
    "RateLimitError",
    "ServiceUnavailableError",
    # Manager
    "IntegrationManager",
    "create_integration_manager",
    # Testing
    "MockCalendarAdapter",
    "MockTaskAdapter",
    "create_mock_calendar",
    "create_mock_tasks",
]
