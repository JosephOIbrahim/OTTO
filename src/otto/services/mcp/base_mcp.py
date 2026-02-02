"""
MCP Server Base Class
=====================

Base class for all OTTO MCP servers.
Provides standardized tool registration, approval integration,
and audit logging.

ThinkingMachines [He2025] Compliance:
- Deterministic tool registration order
- Fixed response schemas
- Sorted iteration
- No timing randomness

Reference: https://modelcontextprotocol.io/specification
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Final, List, Optional, TypeVar, Awaitable

logger = logging.getLogger(__name__)


# === Constants (Fixed per [He2025]) ===

MCP_VERSION: Final[str] = "1.0.0"
TOOL_HASH_ALGORITHM: Final[str] = "sha256"


class MCPServerError(Exception):
    """Base exception for MCP server errors."""
    pass


class MCPToolError(MCPServerError):
    """Error during tool execution."""
    pass


class MCPResourceError(MCPServerError):
    """Error accessing resource."""
    pass


@dataclass
class MCPTool:
    """
    MCP Tool definition.

    Per MCP spec: Tools are functions that can be invoked by the client.
    """

    name: str
    """Tool name (must be unique within server)."""

    description: str
    """Human-readable description."""

    parameters: Dict[str, Any]
    """JSON Schema for tool parameters."""

    # Approval integration
    approval_action: Optional[str] = None
    """Approval action to check before execution (None = no approval needed)."""

    # Metadata
    category: str = "general"
    """Tool category for organization."""

    requires_credentials: bool = False
    """Whether this tool needs credentials."""

    # Internal
    _handler: Optional[Callable[..., Awaitable[Any]]] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to MCP tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.parameters,
            },
        }

    def get_checksum(self) -> str:
        """Get deterministic checksum of tool definition."""
        data = f"{self.name}|{self.description}|{json.dumps(self.parameters, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class MCPResource:
    """
    MCP Resource definition.

    Per MCP spec: Resources are data that can be read by the client.
    """

    uri: str
    """Resource URI (e.g., 'calendar://events/today')."""

    name: str
    """Human-readable name."""

    description: str
    """Resource description."""

    mime_type: str = "application/json"
    """MIME type of resource content."""

    # Approval integration
    approval_action: Optional[str] = None
    """Approval action to check before access."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to MCP resource schema."""
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


@dataclass
class MCPToolResult:
    """Result from tool execution."""

    success: bool
    """Whether execution succeeded."""

    content: Any
    """Result content."""

    content_type: str = "text"
    """Content type: text, json, binary."""

    error: Optional[str] = None
    """Error message if failed."""

    # Metadata
    tool_name: str = ""
    execution_time_ms: float = 0.0
    approval_id: Optional[str] = None

    def to_mcp_response(self) -> Dict[str, Any]:
        """Convert to MCP response format."""
        if self.success:
            if self.content_type == "json":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(self.content, indent=2),
                        }
                    ],
                    "isError": False,
                }
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": str(self.content),
                        }
                    ],
                    "isError": False,
                }
        else:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {self.error}",
                    }
                ],
                "isError": True,
            }


class MCPServer(ABC):
    """
    Base class for MCP servers.

    Subclasses implement specific service functionality.
    All tools are automatically integrated with:
    - Approval gate (for sensitive operations)
    - Audit log (all operations logged)
    - Credential manager (secure API key access)

    Example:
        class MyMCPServer(MCPServer):
            server_name = "my_service"
            server_version = "1.0.0"

            def __init__(self):
                super().__init__()
                self._register_tools()

            def _register_tools(self):
                self.register_tool(MCPTool(
                    name="my_tool",
                    description="Does something",
                    parameters={...},
                    _handler=self._handle_my_tool,
                ))

            async def _handle_my_tool(self, **params) -> Any:
                ...
    """

    server_name: str = "base"
    server_version: str = "1.0.0"

    def __init__(self):
        """Initialize MCP server."""
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}

        # Service dependencies (lazy-loaded)
        self._approval_gate = None
        self._audit_log = None
        self._credential_manager = None
        self._memory = None

        # Actor ID for audit/approval
        self.actor_id = f"mcp.{self.server_name}"

    # =========================================================================
    # Tool Registration
    # =========================================================================

    def register_tool(self, tool: MCPTool) -> None:
        """
        Register a tool.

        Per [He2025]: Tools are stored in deterministic order.
        """
        if tool.name in self._tools:
            raise MCPServerError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool
        logger.debug(f"[{self.server_name}] Registered tool: {tool.name}")

    def register_resource(self, resource: MCPResource) -> None:
        """Register a resource."""
        if resource.uri in self._resources:
            raise MCPServerError(f"Resource already registered: {resource.uri}")

        self._resources[resource.uri] = resource
        logger.debug(f"[{self.server_name}] Registered resource: {resource.uri}")

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[MCPTool]:
        """
        List all tools.

        Per [He2025]: Returns in deterministic order (sorted by name).
        """
        return [self._tools[k] for k in sorted(self._tools.keys())]

    def list_resources(self) -> List[MCPResource]:
        """List all resources (sorted by URI)."""
        return [self._resources[k] for k in sorted(self._resources.keys())]

    # =========================================================================
    # Tool Execution
    # =========================================================================

    async def invoke_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> MCPToolResult:
        """
        Invoke a tool.

        Handles:
        - Tool lookup
        - Approval gate check
        - Execution
        - Audit logging

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            MCPToolResult with success/failure
        """
        start_time = datetime.now()

        # Get tool
        tool = self.get_tool(name)
        if tool is None:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Tool not found: {name}",
                tool_name=name,
            )

        # Check approval if needed
        approval_id = None
        if tool.approval_action:
            try:
                gate = self._get_approval_gate()
                await gate.request_approval(
                    action=tool.approval_action,
                    actor=self.actor_id,
                    service=self.server_name,
                    resource=name,
                    details={"arguments": arguments},
                )
            except Exception as e:
                return MCPToolResult(
                    success=False,
                    content=None,
                    error=f"Approval denied: {e}",
                    tool_name=name,
                )

        # Execute tool
        try:
            if tool._handler is None:
                raise MCPToolError(f"Tool has no handler: {name}")

            result = await tool._handler(**arguments)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Audit success
            self._log_tool_invocation(tool, arguments, True, None)

            return MCPToolResult(
                success=True,
                content=result,
                content_type="json" if isinstance(result, (dict, list)) else "text",
                tool_name=name,
                execution_time_ms=execution_time,
                approval_id=approval_id,
            )

        except Exception as e:
            logger.error(f"[{self.server_name}] Tool error {name}: {e}")

            # Audit failure
            self._log_tool_invocation(tool, arguments, False, str(e))

            return MCPToolResult(
                success=False,
                content=None,
                error=str(e),
                tool_name=name,
            )

    # =========================================================================
    # Resource Access
    # =========================================================================

    async def read_resource(self, uri: str) -> MCPToolResult:
        """
        Read a resource.

        Args:
            uri: Resource URI

        Returns:
            MCPToolResult with resource content
        """
        resource = self._resources.get(uri)
        if resource is None:
            return MCPToolResult(
                success=False,
                content=None,
                error=f"Resource not found: {uri}",
            )

        # Check approval if needed
        if resource.approval_action:
            try:
                gate = self._get_approval_gate()
                await gate.request_approval(
                    action=resource.approval_action,
                    actor=self.actor_id,
                    service=self.server_name,
                    resource=uri,
                )
            except Exception as e:
                return MCPToolResult(
                    success=False,
                    content=None,
                    error=f"Approval denied: {e}",
                )

        # Read resource
        try:
            content = await self._read_resource_content(uri)

            # Audit
            self._log_resource_access(uri, True, None)

            return MCPToolResult(
                success=True,
                content=content,
                content_type="json" if isinstance(content, (dict, list)) else "text",
            )

        except Exception as e:
            self._log_resource_access(uri, False, str(e))

            return MCPToolResult(
                success=False,
                content=None,
                error=str(e),
            )

    @abstractmethod
    async def _read_resource_content(self, uri: str) -> Any:
        """Read resource content. Implemented by subclasses."""
        pass

    # =========================================================================
    # MCP Protocol
    # =========================================================================

    def get_server_info(self) -> Dict[str, Any]:
        """Get MCP server info."""
        return {
            "name": self.server_name,
            "version": self.server_version,
            "protocolVersion": MCP_VERSION,
        }

    def get_capabilities(self) -> Dict[str, Any]:
        """Get MCP server capabilities."""
        return {
            "tools": {"listChanged": True},
            "resources": {"subscribe": False, "listChanged": True},
        }

    def list_tools_mcp(self) -> Dict[str, Any]:
        """Get tools in MCP format."""
        return {
            "tools": [tool.to_dict() for tool in self.list_tools()]
        }

    def list_resources_mcp(self) -> Dict[str, Any]:
        """Get resources in MCP format."""
        return {
            "resources": [resource.to_dict() for resource in self.list_resources()]
        }

    # =========================================================================
    # Service Dependencies (Lazy Loading)
    # =========================================================================

    def _get_approval_gate(self):
        """Get approval gate (lazy load)."""
        if self._approval_gate is None:
            from ..approval import get_approval_gate
            self._approval_gate = get_approval_gate()
        return self._approval_gate

    def _get_audit_log(self):
        """Get audit log (lazy load)."""
        if self._audit_log is None:
            from ..audit import get_audit_log
            self._audit_log = get_audit_log()
        return self._audit_log

    def _get_credential_manager(self):
        """Get credential manager (lazy load)."""
        if self._credential_manager is None:
            from ..credentials import get_credential_manager
            self._credential_manager = get_credential_manager()
        return self._credential_manager

    def _get_memory(self):
        """Get unified memory interface (lazy load)."""
        if self._memory is None:
            from ...memory import get_memory
            self._memory = get_memory()
        return self._memory

    def _log_tool_invocation(
        self,
        tool: MCPTool,
        arguments: Dict[str, Any],
        success: bool,
        error: Optional[str],
    ) -> None:
        """
        Log tool invocation to audit log and memory.

        Per [He2025]: Deterministic logging - no timing randomness.
        """
        try:
            from ..audit import AuditAction

            audit = self._get_audit_log()
            audit.log(
                action=AuditAction.MCP_TOOL_INVOKE,
                actor=self.actor_id,
                service=self.server_name,
                resource=tool.name,
                details={"arguments_keys": list(arguments.keys())},
                success=success,
                error=error,
            )
        except Exception as e:
            logger.warning(f"Failed to log tool invocation: {e}")

        # Record to memory system (pheromone trails)
        try:
            from ...memory import Episode, Outcome, get_memory

            memory = self._get_memory()

            # Create episode for episodic memory
            episode = Episode(
                type=f"{self.server_name}.{tool.name}",
                data={"arguments_keys": sorted(arguments.keys())},  # Sorted per [He2025]
                outcome=Outcome.SUCCESS if success else Outcome.FAILURE,
                actor=self.actor_id,
                service=self.server_name,
                resource=tool.name,
            )
            memory.record_episode(episode)

            # Deposit trail for procedural memory (auto-approval)
            outcome = Outcome.SUCCESS if success else Outcome.FAILURE
            memory.deposit_trail(
                action=f"{self.server_name}.{tool.name}",
                outcome=outcome,
            )

        except Exception as e:
            logger.debug(f"Memory recording skipped: {e}")

    def _log_resource_access(
        self,
        uri: str,
        success: bool,
        error: Optional[str],
    ) -> None:
        """Log resource access to audit log."""
        try:
            from ..audit import AuditAction

            audit = self._get_audit_log()
            audit.log(
                action=AuditAction.MCP_RESOURCE_READ,
                actor=self.actor_id,
                service=self.server_name,
                resource=uri,
                success=success,
                error=error,
            )
        except Exception as e:
            logger.warning(f"Failed to log resource access: {e}")


# === Global MCP Server Registry ===

_servers: Dict[str, MCPServer] = {}


def register_mcp_server(server: MCPServer) -> None:
    """Register an MCP server globally."""
    _servers[server.server_name] = server
    logger.info(f"Registered MCP server: {server.server_name}")


def get_mcp_server(name: str) -> Optional[MCPServer]:
    """Get MCP server by name."""
    return _servers.get(name)


def list_mcp_servers() -> List[str]:
    """List all registered MCP server names (sorted)."""
    return sorted(_servers.keys())


__all__ = [
    "MCPServer",
    "MCPTool",
    "MCPResource",
    "MCPToolResult",
    "MCPServerError",
    "MCPToolError",
    "MCPResourceError",
    "register_mcp_server",
    "get_mcp_server",
    "list_mcp_servers",
]
