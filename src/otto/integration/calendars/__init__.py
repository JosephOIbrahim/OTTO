"""
Calendar Adapters
=================

Adapters for calendar services (Google Calendar, Outlook, Apple Calendar).

Available Adapters:
- CalendarAdapter: Base class for all calendar adapters
- ICalAdapter: File-based adapter for .ics files (no OAuth required)
"""

from .base import CalendarAdapter
from .ical_adapter import ICalAdapter, create_ical_adapter

__all__ = [
    "CalendarAdapter",
    "ICalAdapter",
    "create_ical_adapter",
]
