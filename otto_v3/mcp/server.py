"""MCP server handler — dispatches tool calls to OTTO.

Routes MCP tool invocations to the appropriate OTTO subsystems.
The handler is stateless — it delegates to ChatSession and
ServiceRegistry for actual processing.

All user-facing strings are constitutional:
    - No clinical language
    - No minimizing language
    - Dignity-first framing

Tool dispatch uses sorted comparison, not dict lookup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from otto_v3.mcp.tools import MCPToolDefinition, get_tool_definitions
from otto_v3.ui.chat import ChatSession
from otto_v3.ui.dashboard import CognitiveSummary, DashboardState


@dataclass(frozen=True)
class MCPToolResult:
    """Result from an MCP tool invocation.

    Attributes:
        content: Response text.
        is_error: Whether this is an error response.
        metadata: Optional metadata about the invocation.
    """

    content: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class OTTOMCPHandler:
    """Dispatches MCP tool calls to OTTO subsystems.

    Args:
        session: Active ChatSession for conversation.
    """

    def __init__(self, session: ChatSession) -> None:
        self._session = session

    @staticmethod
    def list_tools() -> list[MCPToolDefinition]:
        """Return available tool definitions."""
        return get_tool_definitions()

    def handle(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Dispatch a tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool input arguments.

        Returns:
            MCPToolResult with response content.
        """
        # Explicit dispatch, not dict-based
        if tool_name == "otto_chat":
            return self._handle_chat(arguments)
        if tool_name == "otto_signals":
            return self._handle_signals(arguments)
        if tool_name == "otto_status":
            return self._handle_status(arguments)

        return MCPToolResult(
            content=f"Unknown tool: {tool_name}",
            is_error=True,
        )

    def _handle_chat(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Handle otto_chat tool invocation."""
        message = arguments.get("message", "")
        if not message.strip():
            return MCPToolResult(
                content="Please provide a message.",
                is_error=True,
            )

        response = self._session.send(message)
        return MCPToolResult(
            content=response.content,
            metadata=response.metadata,
        )

    def _handle_signals(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Handle otto_signals tool invocation."""
        registry = self._session.services
        if registry is None:
            return MCPToolResult(
                content="No services are currently active.",
            )

        signals = registry.get_all_signals()
        if not signals:
            return MCPToolResult(
                content="No signals detected right now.",
            )

        # Format signals for display — sorted by category for determinism
        lines = []
        for sig in sorted(signals, key=lambda s: s.category):
            lines.append(f"{sig.category}: {sig.value} ({sig.confidence:.0%})")

        return MCPToolResult(
            content="\n".join(lines),
            metadata={"signal_count": len(signals)},
        )

    def _handle_status(self, arguments: dict[str, Any]) -> MCPToolResult:
        """Handle otto_status tool invocation."""
        duration = self._session.session_duration_minutes()
        exchanges = self._session.exchange_count

        parts = [
            f"Session: {exchanges} exchanges, {duration:.0f} minutes",
            f"Ready to help.",
        ]

        return MCPToolResult(
            content="\n".join(parts),
            metadata={
                "exchange_count": exchanges,
                "duration_minutes": round(duration, 1),
            },
        )
