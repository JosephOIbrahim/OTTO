"""MCP tool definitions — OTTO's Model Context Protocol surface.

Defines the tool schemas that OTTO exposes via MCP.
Tools are the external interface; handlers live in server.py.

[He2025]: Tool definitions sorted by name at module load.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPToolDefinition:
    """Schema for a single MCP tool.

    Frozen — tool definitions are immutable once created.

    Attributes:
        name: Tool identifier (e.g., ``"otto_chat"``).
        description: Human-readable description (constitutional).
        input_schema: JSON Schema for the tool's input parameters.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


def get_tool_definitions() -> list[MCPToolDefinition]:
    """Return all OTTO MCP tool definitions.

    Returns sorted by name for [He2025] determinism.

    Returns:
        List of MCPToolDefinition in deterministic order.
    """
    tools = [
        MCPToolDefinition(
            name="otto_chat",
            description=(
                "Send a message to OTTO and get a response. "
                "OTTO routes your message through its cognitive engine "
                "to provide contextually appropriate support."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Your message to OTTO",
                    },
                },
                "required": ["message"],
            },
        ),
        MCPToolDefinition(
            name="otto_signals",
            description=(
                "Get current ambient signals from OTTO's services. "
                "Shows what OTTO is sensing about your environment "
                "without any identifying details."
            ),
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        MCPToolDefinition(
            name="otto_status",
            description=(
                "Get OTTO's current cognitive state. "
                "Shows the active expert mode, effort level, "
                "and session information."
            ),
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
    ]
    # [He2025]: Sorted by name
    return sorted(tools, key=lambda t: t.name)
