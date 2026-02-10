"""MCP interface — Model Context Protocol surface for OTTO.

Exposes OTTO's cognitive engine as MCP tools for integration
with Claude Code and other MCP-compatible clients.

Components:
    MCPToolDefinition  — Schema for a single tool
    MCPToolResult      — Result from a tool invocation
    OTTOMCPHandler     — Dispatches tool calls to OTTO
    get_tool_definitions — Returns all available tools
"""

from otto.mcp.tools import MCPToolDefinition, get_tool_definitions
from otto.mcp.server import MCPToolResult, OTTOMCPHandler

__all__ = [
    "MCPToolDefinition",
    "MCPToolResult",
    "OTTOMCPHandler",
    "get_tool_definitions",
]
