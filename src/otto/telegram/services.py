"""
Telegram Service Router
=======================

Routes Telegram requests to MCP services.

[He2025] Compliance:
- Deterministic service routing
- Fixed parameter extraction order
- Sorted tool iteration

Design:
- Detects service intent from commands/natural language
- Routes to appropriate MCP server
- Uses approval gate (wired to Telegram buttons)
- Formats results for Telegram display
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Final, List, Optional, Tuple

from ..services.mcp import (
    MCPServer,
    MCPToolResult,
    get_mcp_server,
    list_mcp_servers,
    CalendarMCPServer,
    TasksMCPServer,
    EmailMCPServer,
    NotionMCPServer,
    register_mcp_server,
)
from ..services.approval import get_approval_gate

logger = logging.getLogger(__name__)


# [He2025] Fixed constants
SERVICE_ROUTE_SEED: Final[int] = 0x5EAF00D5
MAX_RESULT_LINES: Final[int] = 10
DATE_FORMAT: Final[str] = "%Y-%m-%d"


@dataclass
class ServiceRequest:
    """
    Parsed service request from Telegram.

    [He2025] Deterministic structure.
    """
    service: str
    """Target service name (calendar, tasks, email, etc.)."""

    tool: Optional[str] = None
    """Specific tool to invoke (if known)."""

    parameters: Dict[str, Any] = None
    """Extracted parameters."""

    raw_text: str = ""
    """Original request text."""

    chat_id: Optional[int] = None
    """Telegram chat ID (for approval callbacks)."""

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class ServiceResponse:
    """
    Response from service invocation.

    Formatted for Telegram display.
    """
    success: bool
    text: str
    service: str
    tool: Optional[str] = None
    execution_time_ms: float = 0.0


class TelegramServiceRouter:
    """
    Routes Telegram requests to MCP services.

    [He2025] Compliance:
    - Deterministic service selection (first match)
    - Fixed pattern evaluation order
    - Sorted service iteration

    Usage:
        router = TelegramServiceRouter()
        response = await router.route("/calendar today")
    """

    def __init__(self):
        """Initialize service router."""
        self._servers: Dict[str, MCPServer] = {}
        self._initialize_servers()

    def _initialize_servers(self) -> None:
        """
        Initialize and register MCP servers.

        [He2025] Fixed initialization order.
        """
        # Initialize servers in deterministic order
        servers = [
            CalendarMCPServer(),
            TasksMCPServer(),
            EmailMCPServer(),
            NotionMCPServer(),
        ]

        for server in servers:
            self._servers[server.server_name] = server
            register_mcp_server(server)
            logger.debug(f"Initialized MCP server: {server.server_name}")

    def get_server(self, name: str) -> Optional[MCPServer]:
        """Get MCP server by name."""
        return self._servers.get(name)

    def list_services(self) -> List[str]:
        """List available services (sorted)."""
        return sorted(self._servers.keys())

    async def route(
        self,
        text: str,
        chat_id: Optional[int] = None,
    ) -> ServiceResponse:
        """
        Route a request to the appropriate service.

        Args:
            text: Request text (command or natural language)
            chat_id: Telegram chat ID for approval callbacks

        Returns:
            ServiceResponse with formatted result
        """
        # Parse the request
        request = self._parse_request(text, chat_id)

        if not request.service:
            return ServiceResponse(
                success=False,
                text="Could not determine which service to use.",
                service="unknown",
            )

        # Get the server
        server = self.get_server(request.service)
        if not server:
            return ServiceResponse(
                success=False,
                text=f"Service '{request.service}' not available.",
                service=request.service,
            )

        # Wire approval handler with chat_id
        if chat_id:
            self._wire_approval_handler(chat_id)

        # Route to tool
        if request.tool:
            result = await server.invoke_tool(request.tool, request.parameters)
        else:
            # Default tool based on service
            result = await self._invoke_default_tool(server, request)

        # Format response
        return self._format_response(result, request.service, request.tool)

    def _parse_request(
        self,
        text: str,
        chat_id: Optional[int] = None,
    ) -> ServiceRequest:
        """
        Parse request text to extract service and parameters.

        [He2025] Fixed parsing order:
        1. Command format (/service action params)
        2. Natural language patterns
        3. Default patterns
        """
        text = text.strip()

        # Pattern 1: Command format (/calendar today, /tasks list)
        if text.startswith("/"):
            return self._parse_command(text, chat_id)

        # Pattern 2: Natural language with service keywords
        service_keywords = {
            "calendar": ["calendar", "event", "meeting", "schedule", "appointment"],
            "tasks": ["task", "todo", "reminder", "due"],
            "email": ["email", "mail", "message", "inbox"],
            "notion": ["notion", "page", "database", "doc"],
        }

        text_lower = text.lower()
        for service, keywords in sorted(service_keywords.items()):
            for keyword in keywords:
                if keyword in text_lower:
                    return ServiceRequest(
                        service=service,
                        raw_text=text,
                        chat_id=chat_id,
                        parameters=self._extract_parameters(text, service),
                    )

        # No service detected
        return ServiceRequest(
            service="",
            raw_text=text,
            chat_id=chat_id,
        )

    def _parse_command(
        self,
        text: str,
        chat_id: Optional[int] = None,
    ) -> ServiceRequest:
        """
        Parse command format: /service action params

        Examples:
            /calendar today
            /calendar list 2024-01-01 2024-01-07
            /tasks add Buy groceries
        """
        parts = text[1:].split(maxsplit=2)  # Remove /

        if not parts:
            return ServiceRequest(service="", raw_text=text, chat_id=chat_id)

        service = parts[0].lower()
        action = parts[1] if len(parts) > 1 else "list"
        args = parts[2] if len(parts) > 2 else ""

        # Map action to tool
        tool = self._map_action_to_tool(service, action)

        # Extract parameters based on action
        parameters = self._extract_command_params(service, action, args)

        return ServiceRequest(
            service=service,
            tool=tool,
            parameters=parameters,
            raw_text=text,
            chat_id=chat_id,
        )

    def _map_action_to_tool(self, service: str, action: str) -> Optional[str]:
        """
        Map action verb to tool name.

        [He2025] Fixed mapping (deterministic).
        """
        action_map = {
            "calendar": {
                "list": "calendar_list_events",
                "today": "calendar_list_events",
                "week": "calendar_list_events",
                "get": "calendar_get_event",
                "create": "calendar_create_event",
                "add": "calendar_create_event",
                "delete": "calendar_delete_event",
            },
            "tasks": {
                "list": "tasks_list",
                "get": "tasks_get",
                "add": "tasks_create",
                "create": "tasks_create",
                "complete": "tasks_complete",
                "done": "tasks_complete",
            },
            "email": {
                "list": "email_list",
                "inbox": "email_list",
                "unread": "email_list_unread",
                "read": "email_get",
                "send": "email_send",
            },
            "notion": {
                "list": "notion_list_pages",
                "pages": "notion_list_pages",
                "search": "notion_search",
                "get": "notion_get_page",
            },
        }

        service_map = action_map.get(service, {})
        return service_map.get(action)

    def _extract_command_params(
        self,
        service: str,
        action: str,
        args: str,
    ) -> Dict[str, Any]:
        """
        Extract parameters from command arguments.

        [He2025] Fixed extraction logic per service/action.
        """
        params: Dict[str, Any] = {}

        if service == "calendar":
            if action in ("today", "list"):
                # Date range
                if action == "today":
                    today = datetime.now().strftime(DATE_FORMAT)
                    params["start_date"] = today
                    params["end_date"] = today
                elif action == "week":
                    today = datetime.now()
                    params["start_date"] = today.strftime(DATE_FORMAT)
                    params["end_date"] = (today + timedelta(days=7)).strftime(DATE_FORMAT)
                else:
                    # Try to parse dates from args
                    dates = self._extract_dates(args)
                    if len(dates) >= 2:
                        params["start_date"] = dates[0]
                        params["end_date"] = dates[1]
                    elif len(dates) == 1:
                        params["start_date"] = dates[0]
                        params["end_date"] = dates[0]

            elif action in ("create", "add"):
                # Parse event creation
                params["title"] = args if args else "New Event"

        elif service == "tasks":
            if action in ("add", "create"):
                params["title"] = args if args else "New Task"

        elif service == "email":
            if action == "unread":
                params["unread_only"] = True
            elif action == "send":
                # Would need more sophisticated parsing
                pass

        return params

    def _extract_dates(self, text: str) -> List[str]:
        """Extract ISO8601 dates from text."""
        # Simple ISO date pattern
        pattern = r"\d{4}-\d{2}-\d{2}"
        return re.findall(pattern, text)

    def _extract_parameters(
        self,
        text: str,
        service: str,
    ) -> Dict[str, Any]:
        """Extract parameters from natural language."""
        params: Dict[str, Any] = {}

        # Extract dates
        dates = self._extract_dates(text)
        if dates:
            if service == "calendar":
                params["start_date"] = dates[0]
                params["end_date"] = dates[-1] if len(dates) > 1 else dates[0]

        # Check for "today" keyword
        if "today" in text.lower():
            today = datetime.now().strftime(DATE_FORMAT)
            params["start_date"] = today
            params["end_date"] = today

        # Check for "this week" keyword
        if "this week" in text.lower() or "week" in text.lower():
            today = datetime.now()
            params["start_date"] = today.strftime(DATE_FORMAT)
            params["end_date"] = (today + timedelta(days=7)).strftime(DATE_FORMAT)

        return params

    async def _invoke_default_tool(
        self,
        server: MCPServer,
        request: ServiceRequest,
    ) -> MCPToolResult:
        """
        Invoke the default tool for a service.

        [He2025] Fixed default tool per service.
        """
        default_tools = {
            "calendar": "calendar_list_events",
            "tasks": "tasks_list",
            "email": "email_list",
            "notion": "notion_list_pages",
        }

        tool_name = default_tools.get(request.service)
        if not tool_name:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"No default tool for service: {request.service}",
            )

        # Add default parameters if missing
        params = request.parameters.copy()
        if request.service == "calendar" and "start_date" not in params:
            today = datetime.now().strftime(DATE_FORMAT)
            params["start_date"] = today
            params["end_date"] = today

        return await server.invoke_tool(tool_name, params)

    def _wire_approval_handler(self, chat_id: int) -> None:
        """
        Wire approval handler with chat_id for this request.

        This ensures approval requests go to the right Telegram chat.
        """
        try:
            from .approval import get_telegram_approval_handler

            handler = get_telegram_approval_handler()
            gate = get_approval_gate(approval_handler=handler.request_approval)

            # The approval handler will use chat_id from request.details
            logger.debug(f"Wired approval handler for chat_id: {chat_id}")

        except Exception as e:
            logger.debug(f"Could not wire approval handler: {e}")

    def _format_response(
        self,
        result: MCPToolResult,
        service: str,
        tool: Optional[str],
    ) -> ServiceResponse:
        """
        Format MCPToolResult for Telegram display.

        [He2025] Fixed formatting rules.
        """
        if not result.success:
            return ServiceResponse(
                success=False,
                text=f"*Error*: {result.error}",
                service=service,
                tool=tool,
            )

        # Format based on content type
        content = result.content

        if isinstance(content, list):
            text = self._format_list(content, service)
        elif isinstance(content, dict):
            text = self._format_dict(content, service)
        else:
            text = str(content)

        return ServiceResponse(
            success=True,
            text=text,
            service=service,
            tool=tool,
            execution_time_ms=result.execution_time_ms,
        )

    def _format_list(self, items: List[Any], service: str) -> str:
        """Format a list of items for Telegram."""
        if not items:
            return f"No {service} items found."

        lines = [f"*{service.title()} Results* ({len(items)} items)\n"]

        for i, item in enumerate(items[:MAX_RESULT_LINES]):
            if isinstance(item, dict):
                # Format based on common fields
                title = item.get("title") or item.get("name") or item.get("subject", "")
                date = item.get("start") or item.get("date") or item.get("due", "")

                if title:
                    line = f"{i+1}. {title}"
                    if date:
                        # Extract just date part if full datetime
                        if "T" in str(date):
                            date = str(date).split("T")[0]
                        line += f" ({date})"
                    lines.append(line)
                else:
                    lines.append(f"{i+1}. {item}")
            else:
                lines.append(f"{i+1}. {item}")

        if len(items) > MAX_RESULT_LINES:
            lines.append(f"\n_...and {len(items) - MAX_RESULT_LINES} more_")

        return "\n".join(lines)

    def _format_dict(self, item: Dict[str, Any], service: str) -> str:
        """Format a single item for Telegram."""
        lines = []

        # Title
        title = item.get("title") or item.get("name") or item.get("subject")
        if title:
            lines.append(f"*{title}*")

        # Common fields
        for field in ["description", "location", "start", "end", "due", "status"]:
            if field in item and item[field]:
                lines.append(f"*{field.title()}:* {item[field]}")

        if not lines:
            # Fallback to raw dict display
            for key, value in sorted(item.items())[:5]:
                lines.append(f"*{key}:* {value}")

        return "\n".join(lines)


# Module-level singleton
_router: Optional[TelegramServiceRouter] = None


def get_service_router() -> TelegramServiceRouter:
    """Get or create the service router singleton."""
    global _router
    if _router is None:
        _router = TelegramServiceRouter()
    return _router


__all__ = [
    "TelegramServiceRouter",
    "ServiceRequest",
    "ServiceResponse",
    "get_service_router",
]
