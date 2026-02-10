"""
JSON-RPC Layer (Layer 1)
========================

JSON-RPC 2.0 implementation for structured API communication.
Methods are namespaced with `otto.` prefix.

Methods:
    otto.status           - Get OTTO status
    otto.state.get        - Get cognitive state
    otto.state.update     - Update cognitive state
    otto.protect.check    - Check protection decision
    otto.session.start    - Start session
    otto.session.end      - End session
    otto.session.handoff  - Create handoff document
    otto.integration.list    - List configured integrations
    otto.integration.status  - Get integration health status
    otto.integration.sync    - Manually trigger sync
    otto.context.get         - Get external context

JSON-RPC 2.0 Spec: https://www.jsonrpc.org/specification

Determinism:
- Fixed method names and parameter schemas
- Deterministic error codes
- Ordered evaluation of batch requests
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# JSON-RPC Error Codes (from spec + custom)
# =============================================================================

# Standard JSON-RPC 2.0 error codes
PARSE_ERROR = -32700       # Invalid JSON
INVALID_REQUEST = -32600   # Not a valid JSON-RPC request
METHOD_NOT_FOUND = -32601  # Method does not exist
INVALID_PARAMS = -32602    # Invalid method parameters
INTERNAL_ERROR = -32603    # Internal error

# Custom OTTO error codes (-32000 to -32099 reserved for implementation)
PROTECTION_BLOCKED = -32001  # Protection engine blocked action
STATE_ERROR = -32002         # Cognitive state error
AGENT_ERROR = -32003         # Agent execution error
INTEGRATION_ERROR = -32004   # Integration error


class JSONRPCError(Exception):
    """
    JSON-RPC error with code and optional data.

    Standard error format from JSON-RPC 2.0 spec.
    """

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC error object."""
        error = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            error["data"] = self.data
        return error


# =============================================================================
# Request/Response Types
# =============================================================================

@dataclass
class JSONRPCRequest:
    """
    JSON-RPC 2.0 request object.

    Attributes:
        method: Method name (e.g., "otto.status")
        params: Method parameters (dict or list)
        id: Request identifier (optional for notifications)
        jsonrpc: Protocol version (always "2.0")
    """
    method: str
    params: Union[Dict[str, Any], List[Any]] = field(default_factory=dict)
    id: Optional[Union[str, int]] = None
    jsonrpc: str = "2.0"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JSONRPCRequest':
        """Parse request from dict."""
        if not isinstance(data, dict):
            raise JSONRPCError(INVALID_REQUEST, "Request must be an object")

        if data.get("jsonrpc") != "2.0":
            raise JSONRPCError(INVALID_REQUEST, "Invalid JSON-RPC version")

        method = data.get("method")
        if not isinstance(method, str):
            raise JSONRPCError(INVALID_REQUEST, "Method must be a string")

        params = data.get("params", {})
        if not isinstance(params, (dict, list)):
            raise JSONRPCError(INVALID_PARAMS, "Params must be object or array")

        return cls(
            method=method,
            params=params,
            id=data.get("id"),
        )

    def is_notification(self) -> bool:
        """Check if this is a notification (no id = no response expected)."""
        return self.id is None


@dataclass
class JSONRPCResponse:
    """
    JSON-RPC 2.0 response object.

    Either result or error is set, never both.
    """
    id: Optional[Union[str, int]]
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-RPC response object."""
        response = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
        }
        if self.error is not None:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response

    @classmethod
    def success(cls, id: Any, result: Any) -> 'JSONRPCResponse':
        """Create a success response."""
        return cls(id=id, result=result)

    @classmethod
    def failure(cls, id: Any, error: JSONRPCError) -> 'JSONRPCResponse':
        """Create an error response."""
        return cls(id=id, error=error.to_dict())


# =============================================================================
# JSON-RPC Handler
# =============================================================================

class JSONRPCHandler:
    """
    JSON-RPC 2.0 request handler.

    Registers methods with `otto.` namespace and dispatches requests.
    Supports both synchronous and asynchronous method handlers.

    Example:
        >>> handler = JSONRPCHandler()
        >>> response = await handler.handle_request({
        ...     "jsonrpc": "2.0",
        ...     "method": "otto.status",
        ...     "id": 1
        ... })
        >>> print(response)
        {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": 1}
    """

    def __init__(self):
        """Initialize handler with empty method registry."""
        self._methods: Dict[str, Callable] = {}
        self._state_manager = None
        self._protection_engine = None
        self._render = None
        self._agent_bridge = None
        self._integration_manager = None

        # Register built-in methods
        self._register_builtin_methods()

    def _register_builtin_methods(self) -> None:
        """Register otto.* methods."""
        self.register("otto.status", self._handle_status)
        self.register("otto.state.get", self._handle_state_get)
        self.register("otto.state.update", self._handle_state_update)
        self.register("otto.protect.check", self._handle_protect_check)
        self.register("otto.session.start", self._handle_session_start)
        self.register("otto.session.end", self._handle_session_end)
        self.register("otto.session.handoff", self._handle_session_handoff)
        self.register("otto.ping", self._handle_ping)
        self.register("otto.methods", self._handle_methods)
        # Agent methods
        self.register("otto.agent.spawn", self._handle_agent_spawn)
        self.register("otto.agent.status", self._handle_agent_status)
        self.register("otto.agent.list", self._handle_agent_list)
        self.register("otto.agent.abort", self._handle_agent_abort)
        # Integration methods (Phase 5)
        self.register("otto.integration.list", self._handle_integration_list)
        self.register("otto.integration.status", self._handle_integration_status)
        self.register("otto.integration.sync", self._handle_integration_sync)
        self.register("otto.context.get", self._handle_context_get)

    def register(self, name: str, handler: Callable) -> None:
        """
        Register a method handler.

        Args:
            name: Method name (e.g., "otto.custom.method")
            handler: Sync or async callable
        """
        self._methods[name] = handler
        logger.debug(f"Registered JSON-RPC method: {name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister a method handler.

        Args:
            name: Method name to unregister

        Returns:
            True if method was unregistered
        """
        if name in self._methods:
            del self._methods[name]
            return True
        return False

    async def handle_request(self, request: Union[dict, str]) -> Optional[dict]:
        """
        Handle a JSON-RPC request.

        Args:
            request: Request dict or JSON string

        Returns:
            Response dict (None for notifications)
        """
        # Parse JSON if string
        if isinstance(request, str):
            try:
                request = json.loads(request)
            except json.JSONDecodeError as e:
                return JSONRPCResponse.failure(
                    None,
                    JSONRPCError(PARSE_ERROR, f"Parse error: {e}")
                ).to_dict()

        # Handle batch requests
        if isinstance(request, list):
            return await self.handle_batch(request)

        # Parse and validate request
        try:
            req = JSONRPCRequest.from_dict(request)
        except JSONRPCError as e:
            return JSONRPCResponse.failure(
                request.get("id") if isinstance(request, dict) else None,
                e
            ).to_dict()

        # Execute method
        try:
            result = await self._execute_method(req.method, req.params)

            # No response for notifications
            if req.is_notification():
                return None

            return JSONRPCResponse.success(req.id, result).to_dict()

        except JSONRPCError as e:
            if req.is_notification():
                return None
            return JSONRPCResponse.failure(req.id, e).to_dict()

        except Exception as e:
            logger.exception(f"Internal error handling {req.method}")
            if req.is_notification():
                return None
            return JSONRPCResponse.failure(
                req.id,
                JSONRPCError(INTERNAL_ERROR, str(e))
            ).to_dict()

    async def handle_batch(self, requests: list) -> list:
        """
        Handle batch of requests.

        Per JSON-RPC 2.0 spec, batch requests are processed in order
        but may be executed concurrently.

        Args:
            requests: List of request dicts

        Returns:
            List of response dicts (excluding notifications)
        """
        if not requests:
            return [JSONRPCResponse.failure(
                None,
                JSONRPCError(INVALID_REQUEST, "Empty batch")
            ).to_dict()]

        # Process all requests concurrently
        tasks = [self.handle_request(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None (notification responses) and exceptions
        responses = []
        for result in results:
            if result is None:
                continue
            if isinstance(result, Exception):
                responses.append(JSONRPCResponse.failure(
                    None,
                    JSONRPCError(INTERNAL_ERROR, str(result))
                ).to_dict())
            else:
                responses.append(result)

        return responses if responses else None

    async def _execute_method(self, method: str, params: Union[dict, list]) -> Any:
        """Execute a registered method."""
        if method not in self._methods:
            raise JSONRPCError(METHOD_NOT_FOUND, f"Method not found: {method}")

        handler = self._methods[method]

        # Call with params
        if isinstance(params, dict):
            if asyncio.iscoroutinefunction(handler):
                return await handler(**params)
            return handler(**params)
        else:
            if asyncio.iscoroutinefunction(handler):
                return await handler(*params)
            return handler(*params)

    # =========================================================================
    # Built-in Method Handlers
    # =========================================================================

    async def _handle_status(self) -> Dict[str, Any]:
        """Handle otto.status - Get OTTO status."""
        status = {
            "status": "ok",
            "version": "0.1.0",
            "timestamp": time.time(),
        }

        if self._state_manager:
            state = self._state_manager.get_state()
            status["cognitive_state"] = {
                "burnout_level": state.burnout_level.value,
                "momentum_phase": state.momentum_phase.value,
                "energy_level": state.energy_level.value,
                "mode": state.mode.value,
            }

        return status

    async def _handle_state_get(self, fields: List[str] = None) -> Dict[str, Any]:
        """Handle otto.state.get - Get cognitive state."""
        if not self._state_manager:
            raise JSONRPCError(STATE_ERROR, "State manager not configured")

        state = self._state_manager.get_state()
        state_dict = state.to_dict()

        if fields:
            return {k: v for k, v in state_dict.items() if k in fields}
        return state_dict

    async def _handle_state_update(self, **updates) -> Dict[str, Any]:
        """Handle otto.state.update - Update cognitive state."""
        if not self._state_manager:
            raise JSONRPCError(STATE_ERROR, "State manager not configured")

        self._state_manager.batch_update(updates)
        return {"updated": list(updates.keys())}

    async def _handle_protect_check(
        self,
        action: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle otto.protect.check - Check protection decision."""
        if not self._protection_engine:
            # Return allow if no protection engine configured
            return {
                "action": "allow",
                "message": "",
                "can_override": True,
            }

        state = self._state_manager.get_state() if self._state_manager else None
        decision = self._protection_engine.check(state)
        return decision.to_dict()

    async def _handle_session_start(self, goal: str = None) -> Dict[str, Any]:
        """Handle otto.session.start - Start new session."""
        if self._state_manager:
            state = self._state_manager.get_state()
            state.session_start = time.time()
            state.exchange_count = 0
            self._state_manager.save()

        return {
            "started": True,
            "timestamp": time.time(),
            "goal": goal,
        }

    async def _handle_session_end(self) -> Dict[str, Any]:
        """Handle otto.session.end - End current session."""
        if self._state_manager:
            self._state_manager.save()

        return {
            "ended": True,
            "timestamp": time.time(),
        }

    async def _handle_session_handoff(self) -> Dict[str, Any]:
        """Handle otto.session.handoff - Create handoff document."""
        handoff = {
            "timestamp": time.time(),
            "state": None,
            "message": "Session saved. Pick up anytime.",
        }

        if self._state_manager:
            state = self._state_manager.get_state()
            handoff["state"] = state.to_dict()

        if self._render:
            handoff["message"] = self._render.render_goodbye(
                self._state_manager.get_state() if self._state_manager else None
            )

        return handoff

    async def _handle_ping(self) -> str:
        """Handle otto.ping - Simple ping/pong."""
        return "pong"

    async def _handle_methods(self) -> List[str]:
        """Handle otto.methods - List available methods."""
        return sorted(self._methods.keys())

    # =========================================================================
    # Agent Method Handlers
    # =========================================================================

    async def _handle_agent_spawn(
        self,
        task: str,
        agent_type: str = "general",
        context: Dict[str, Any] = None,
        timeout: float = None
    ) -> Dict[str, Any]:
        """Handle otto.agent.spawn - Spawn a new agent."""
        if not self._agent_bridge:
            raise JSONRPCError(AGENT_ERROR, "Agent bridge not configured")

        from .message_types import Message, MessageType

        payload = {
            "agent_type": agent_type,
            "task": task,
        }
        if context:
            payload["context"] = context
        if timeout:
            payload["timeout"] = timeout

        msg = Message(type=MessageType.AGENT_SPAWN, payload=payload)
        response = await self._agent_bridge.handle_message(msg)

        return response.payload

    async def _handle_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """Handle otto.agent.status - Get agent status."""
        if not self._agent_bridge:
            raise JSONRPCError(AGENT_ERROR, "Agent bridge not configured")

        status = self._agent_bridge.get_agent_status(agent_id)
        if status is None:
            raise JSONRPCError(AGENT_ERROR, f"Unknown agent: {agent_id}")

        return status

    async def _handle_agent_list(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Handle otto.agent.list - List agents."""
        if not self._agent_bridge:
            raise JSONRPCError(AGENT_ERROR, "Agent bridge not configured")

        if active_only:
            return self._agent_bridge.get_active_agents()
        return self._agent_bridge.get_all_agents()

    async def _handle_agent_abort(self, agent_id: str, reason: str = None) -> Dict[str, Any]:
        """Handle otto.agent.abort - Abort an agent."""
        if not self._agent_bridge:
            raise JSONRPCError(AGENT_ERROR, "Agent bridge not configured")

        from .message_types import Message, MessageType

        payload = {"agent_id": agent_id}
        if reason:
            payload["reason"] = reason

        msg = Message(type=MessageType.AGENT_ABORT, payload=payload)
        response = await self._agent_bridge.handle_message(msg)

        return response.payload

    # =========================================================================
    # Integration Method Handlers (Phase 5)
    # =========================================================================

    async def _handle_integration_list(self) -> List[Dict[str, Any]]:
        """Handle otto.integration.list - List configured integrations."""
        if not self._integration_manager:
            return []

        adapters = []
        for name in self._integration_manager.list_adapters():
            adapter = self._integration_manager.get_adapter(name)
            if adapter:
                adapters.append(adapter.to_dict())

        return adapters

    async def _handle_integration_status(
        self,
        service_name: str = None
    ) -> Dict[str, Any]:
        """Handle otto.integration.status - Get integration health status."""
        if not self._integration_manager:
            return {"status": "not_configured", "adapters": {}}

        overall = await self._integration_manager.get_overall_health()
        health = await self._integration_manager.get_health()

        result = {
            "status": overall.value,
            "adapters": {
                name: h.to_dict()
                for name, h in health.items()
            },
        }

        if service_name:
            adapter_health = health.get(service_name)
            if adapter_health:
                return adapter_health.to_dict()
            raise JSONRPCError(INTEGRATION_ERROR, f"Unknown integration: {service_name}")

        return result

    async def _handle_integration_sync(
        self,
        service_name: str = None
    ) -> Dict[str, Any]:
        """Handle otto.integration.sync - Manually trigger sync."""
        if not self._integration_manager:
            raise JSONRPCError(INTEGRATION_ERROR, "Integration manager not configured")

        success = await self._integration_manager.sync(service_name)

        return {
            "success": success,
            "service": service_name or "all",
            "timestamp": time.time(),
        }

    async def _handle_context_get(
        self,
        integration_type: str = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Handle otto.context.get - Get external context."""
        if not self._integration_manager:
            return {"available": False, "context": None}

        context = await self._integration_manager.get_context(force_refresh=force_refresh)

        if integration_type:
            if integration_type == "calendar" and context.calendar:
                return {
                    "available": True,
                    "type": "calendar",
                    "context": context.calendar.to_dict(),
                }
            elif integration_type == "task_manager" and context.tasks:
                return {
                    "available": True,
                    "type": "task_manager",
                    "context": context.tasks.to_dict(),
                }
            else:
                return {"available": False, "type": integration_type, "context": None}

        return {
            "available": bool(context.available_integrations),
            "context": context.to_dict(),
            "signals": [s.value for s in context.get_all_signals()],
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def create_request(
    method: str,
    params: Dict[str, Any] = None,
    id: Union[str, int] = None
) -> Dict[str, Any]:
    """Create a JSON-RPC request dict."""
    request = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params:
        request["params"] = params
    if id is not None:
        request["id"] = id
    return request


def create_notification(method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create a JSON-RPC notification (request without id)."""
    request = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params:
        request["params"] = params
    return request


def is_error_response(response: Dict[str, Any]) -> bool:
    """Check if response is an error."""
    return "error" in response


def get_error_code(response: Dict[str, Any]) -> Optional[int]:
    """Get error code from response."""
    if "error" in response:
        return response["error"].get("code")
    return None


__all__ = [
    # Error codes
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "PROTECTION_BLOCKED",
    "STATE_ERROR",
    "AGENT_ERROR",
    "INTEGRATION_ERROR",

    # Classes
    "JSONRPCError",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCHandler",

    # Helpers
    "create_request",
    "create_notification",
    "is_error_response",
    "get_error_code",
]
