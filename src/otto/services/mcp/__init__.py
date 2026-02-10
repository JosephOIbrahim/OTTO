"""
OTTO MCP Server Layer
=====================

Model Context Protocol (MCP) servers that expose OTTO services
to Claude and other MCP-compatible clients.

Each MCP server:
- Exposes tools for specific service functionality
- Integrates with approval gate for sensitive operations
- Logs all operations to audit log
- Uses credential manager for API keys

Determinism:
- Deterministic tool registration
- Fixed response schemas
- Sorted iteration for tool listing
"""

from .base_mcp import (
    MCPServer,
    MCPTool,
    MCPResource,
    MCPToolResult,
    MCPServerError,
    MCPToolError,
    register_mcp_server,
    get_mcp_server,
    list_mcp_servers,
)

from .calendar_mcp import CalendarMCPServer
from .email_mcp import EmailMCPServer
from .tasks_mcp import TasksMCPServer
from .notion_mcp import NotionMCPServer
from .repos_mcp import ReposMCPServer

__all__ = [
    # Base
    "MCPServer",
    "MCPTool",
    "MCPResource",
    "MCPToolResult",
    "MCPServerError",
    "MCPToolError",
    "register_mcp_server",
    "get_mcp_server",
    "list_mcp_servers",
    # Servers
    "CalendarMCPServer",
    "EmailMCPServer",
    "TasksMCPServer",
    "NotionMCPServer",
    "ReposMCPServer",
]
