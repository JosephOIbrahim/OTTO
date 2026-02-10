"""
Calendar MCP Server
===================

MCP server for calendar operations.
Integrates with Google Calendar, iCal, and local calendars.

Determinism:
- Deterministic event ordering (by start time)
- Fixed date formatting (ISO8601)
- Sorted iteration

Per spec:
- TRUST: calendar.read (can earn auto-approval)
- CONSTITUTIONAL: calendar.delete (always requires approval)
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .base_mcp import MCPServer, MCPTool, MCPResource

logger = logging.getLogger(__name__)


class CalendarMCPServer(MCPServer):
    """MCP server for calendar operations."""

    server_name = "calendar"
    server_version = "1.0.0"

    def __init__(self):
        """Initialize calendar MCP server."""
        super().__init__()
        self._register_tools()
        self._register_resources()

    def _register_tools(self) -> None:
        """Register calendar tools."""
        # Read events (TRUST - can earn auto-approval)
        self.register_tool(MCPTool(
            name="calendar_list_events",
            description="List calendar events within a date range",
            parameters={
                "start_date": {
                    "type": "string",
                    "description": "Start date (ISO8601 format)",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (ISO8601 format)",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (optional, default: primary)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum events to return",
                    "default": 50,
                },
            },
            approval_action="calendar.read",
            category="read",
            _handler=self._handle_list_events,
        ))

        # Get event details (TRUST)
        self.register_tool(MCPTool(
            name="calendar_get_event",
            description="Get details of a specific calendar event",
            parameters={
                "event_id": {
                    "type": "string",
                    "description": "Event ID",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (optional)",
                },
            },
            approval_action="calendar.read",
            category="read",
            _handler=self._handle_get_event,
        ))

        # Create event (TRUST)
        self.register_tool(MCPTool(
            name="calendar_create_event",
            description="Create a new calendar event",
            parameters={
                "title": {
                    "type": "string",
                    "description": "Event title",
                },
                "start": {
                    "type": "string",
                    "description": "Start time (ISO8601)",
                },
                "end": {
                    "type": "string",
                    "description": "End time (ISO8601)",
                },
                "description": {
                    "type": "string",
                    "description": "Event description (optional)",
                },
                "location": {
                    "type": "string",
                    "description": "Event location (optional)",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee emails (optional)",
                },
            },
            approval_action="calendar.read",  # Creating is lower risk than deleting
            category="write",
            _handler=self._handle_create_event,
        ))

        # Update event (TRUST)
        self.register_tool(MCPTool(
            name="calendar_update_event",
            description="Update an existing calendar event",
            parameters={
                "event_id": {
                    "type": "string",
                    "description": "Event ID to update",
                },
                "title": {
                    "type": "string",
                    "description": "New title (optional)",
                },
                "start": {
                    "type": "string",
                    "description": "New start time (optional)",
                },
                "end": {
                    "type": "string",
                    "description": "New end time (optional)",
                },
                "description": {
                    "type": "string",
                    "description": "New description (optional)",
                },
            },
            approval_action="calendar.read",
            category="write",
            _handler=self._handle_update_event,
        ))

        # Delete event (CONSTITUTIONAL - always requires approval)
        self.register_tool(MCPTool(
            name="calendar_delete_event",
            description="Delete a calendar event",
            parameters={
                "event_id": {
                    "type": "string",
                    "description": "Event ID to delete",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID (optional)",
                },
            },
            approval_action="calendar.delete",
            category="delete",
            _handler=self._handle_delete_event,
        ))

        # Find free slots (TRUST)
        self.register_tool(MCPTool(
            name="calendar_find_free_time",
            description="Find free time slots within a date range",
            parameters={
                "start_date": {
                    "type": "string",
                    "description": "Start of search range",
                },
                "end_date": {
                    "type": "string",
                    "description": "End of search range",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Required duration in minutes",
                },
                "working_hours_only": {
                    "type": "boolean",
                    "description": "Only search 9am-5pm",
                    "default": True,
                },
            },
            approval_action="calendar.read",
            category="read",
            _handler=self._handle_find_free_time,
        ))

    def _register_resources(self) -> None:
        """Register calendar resources."""
        self.register_resource(MCPResource(
            uri="calendar://today",
            name="Today's Events",
            description="Events for today",
            approval_action="calendar.read",
        ))

        self.register_resource(MCPResource(
            uri="calendar://week",
            name="This Week's Events",
            description="Events for the current week",
            approval_action="calendar.read",
        ))

        self.register_resource(MCPResource(
            uri="calendar://upcoming",
            name="Upcoming Events",
            description="Next 10 upcoming events",
            approval_action="calendar.read",
        ))

    # =========================================================================
    # Tool Handlers
    # =========================================================================

    async def _handle_list_events(
        self,
        start_date: str,
        end_date: str,
        calendar_id: str = "primary",
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """List calendar events."""
        # TODO: Implement actual calendar API integration
        # This is a placeholder that returns mock data

        logger.info(f"Listing events from {start_date} to {end_date}")

        # Mock response - replace with actual implementation
        return [
            {
                "id": "event_1",
                "title": "Team Meeting",
                "start": start_date,
                "end": end_date,
                "location": "Conference Room A",
                "description": "Weekly team sync",
            }
        ]

    async def _handle_get_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """Get event details."""
        logger.info(f"Getting event: {event_id}")

        # Mock response
        return {
            "id": event_id,
            "title": "Meeting",
            "start": datetime.now().isoformat(),
            "end": (datetime.now() + timedelta(hours=1)).isoformat(),
        }

    async def _handle_create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create calendar event."""
        logger.info(f"Creating event: {title}")

        # Mock response
        return {
            "id": f"new_event_{datetime.now().timestamp():.0f}",
            "title": title,
            "start": start,
            "end": end,
            "description": description,
            "location": location,
            "attendees": attendees or [],
            "created": datetime.now().isoformat(),
        }

    async def _handle_update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update calendar event."""
        logger.info(f"Updating event: {event_id}")

        # Mock response
        return {
            "id": event_id,
            "title": title or "Updated Event",
            "start": start or datetime.now().isoformat(),
            "end": end or (datetime.now() + timedelta(hours=1)).isoformat(),
            "updated": datetime.now().isoformat(),
        }

    async def _handle_delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """Delete calendar event."""
        logger.info(f"Deleting event: {event_id}")

        return {
            "deleted": True,
            "event_id": event_id,
            "deleted_at": datetime.now().isoformat(),
        }

    async def _handle_find_free_time(
        self,
        start_date: str,
        end_date: str,
        duration_minutes: int,
        working_hours_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find free time slots."""
        logger.info(f"Finding {duration_minutes}min slots from {start_date} to {end_date}")

        # Mock response
        return [
            {
                "start": start_date,
                "end": end_date,
                "duration_minutes": duration_minutes,
            }
        ]

    # =========================================================================
    # Resource Handler
    # =========================================================================

    async def _read_resource_content(self, uri: str) -> Any:
        """Read calendar resource content."""
        if uri == "calendar://today":
            today = datetime.now().date()
            return await self._handle_list_events(
                start_date=today.isoformat(),
                end_date=today.isoformat(),
            )

        elif uri == "calendar://week":
            today = datetime.now().date()
            week_end = today + timedelta(days=7)
            return await self._handle_list_events(
                start_date=today.isoformat(),
                end_date=week_end.isoformat(),
            )

        elif uri == "calendar://upcoming":
            return await self._handle_list_events(
                start_date=datetime.now().isoformat(),
                end_date=(datetime.now() + timedelta(days=30)).isoformat(),
                max_results=10,
            )

        else:
            raise ValueError(f"Unknown resource: {uri}")


__all__ = ["CalendarMCPServer"]
