"""
Protocol Router
===============

Routes incoming requests to the appropriate protocol handler based on
format detection. Integrates all protocol layers and provides
transformation between human-readable and structured formats.

Architecture:
    Incoming Request
          │
          ▼
    ┌─────────────────┐
    │ Protocol Router │ ← Detects format, routes to handler
    └─────────────────┘
          │
          ├── Binary (bytes starting with 0x01) ──► BinaryProtocol
          │
          ├── JSON-RPC (dict with "jsonrpc") ──► JSONRPCHandler
          │
          └── Text/Human (anything else) ──► Transform to Message

ThinkingMachines [He2025] Compliance:
- Fixed detection order (binary → jsonrpc → human)
- Deterministic format classification
- Layer isolation enforced
"""

import asyncio
from enum import Enum
from typing import Any, Dict, Optional, Union
import logging

from .message_types import Message, MessageType, ProtocolError
from .layer0_binary import BinaryProtocol, BinaryProtocolError
from .layer1_jsonrpc import JSONRPCHandler, JSONRPCError
from .agent_bridge import AgentProtocolBridge, AgentBridgeConfig

logger = logging.getLogger(__name__)


class ProtocolFormat(Enum):
    """Protocol format identifiers."""
    BINARY = "binary"      # MessagePack with binary header
    JSONRPC = "jsonrpc"    # JSON-RPC 2.0
    HUMAN = "human"        # Human-readable text


class ProtocolRouter:
    """
    Routes requests to the appropriate protocol handler.

    Automatically detects incoming format and dispatches to the correct
    handler. Supports transformation between protocol layers.

    Example:
        >>> router = ProtocolRouter()
        >>> # JSON-RPC request
        >>> result = await router.route({
        ...     "jsonrpc": "2.0",
        ...     "method": "otto.status",
        ...     "id": 1
        ... })
        >>> # Binary request
        >>> result = await router.route(binary_data)
    """

    def __init__(
        self,
        state_manager=None,
        protection_engine=None,
        render=None,
        decision_engine=None,
        coordinator=None,
        agent_bridge_config: AgentBridgeConfig = None,
    ):
        """
        Initialize protocol router.

        Args:
            state_manager: Optional CognitiveStateManager instance
            protection_engine: Optional ProtectionEngine instance
            render: Optional HumanRender instance
            decision_engine: Optional DecisionEngine for agent routing decisions
            coordinator: Optional AgentCoordinator for agent lifecycle
            agent_bridge_config: Optional AgentBridgeConfig
        """
        self.state_manager = state_manager
        self.protection_engine = protection_engine
        self.render = render

        # Initialize protocol handlers
        self.binary = BinaryProtocol()
        self.jsonrpc = JSONRPCHandler()

        # Initialize agent bridge
        self.agent_bridge = AgentProtocolBridge(
            decision_engine=decision_engine,
            coordinator=coordinator,
            state_manager=state_manager,
            config=agent_bridge_config,
        )

        # Wire handlers to implementations
        self._wire_handlers()

    def _wire_handlers(self) -> None:
        """Connect JSON-RPC handlers to real implementations."""
        self.jsonrpc._state_manager = self.state_manager
        self.jsonrpc._protection_engine = self.protection_engine
        self.jsonrpc._render = self.render
        self.jsonrpc._agent_bridge = self.agent_bridge

    def detect_format(self, data: Union[bytes, str, dict]) -> ProtocolFormat:
        """
        Detect the protocol format of incoming data.

        Detection order (first match wins):
        1. Binary: bytes starting with version byte 0x01
        2. JSON-RPC: dict/str containing "jsonrpc"
        3. Human: anything else

        Args:
            data: Incoming request data

        Returns:
            Detected ProtocolFormat
        """
        # Binary detection: bytes starting with version byte
        if isinstance(data, bytes):
            if len(data) >= 1 and data[0:1] == b'\x01':
                return ProtocolFormat.BINARY

        # JSON-RPC detection: dict with jsonrpc key
        if isinstance(data, dict):
            if "jsonrpc" in data:
                return ProtocolFormat.JSONRPC
            # List of dicts (batch)
            return ProtocolFormat.JSONRPC  # Could also be human, but prefer JSONRPC

        if isinstance(data, list):
            # Batch request
            if data and isinstance(data[0], dict) and "jsonrpc" in data[0]:
                return ProtocolFormat.JSONRPC

        # String could be JSON-RPC JSON or human text
        if isinstance(data, str):
            stripped = data.strip()
            if stripped.startswith('{') or stripped.startswith('['):
                # Likely JSON-RPC
                return ProtocolFormat.JSONRPC

        # Default to human
        return ProtocolFormat.HUMAN

    async def route(self, request: Any) -> Any:
        """
        Route request to appropriate handler based on format.

        Args:
            request: Incoming request (bytes, dict, or str)

        Returns:
            Response in the same format as the request
        """
        fmt = self.detect_format(request)
        logger.debug(f"Routing request as {fmt.value}")

        if fmt == ProtocolFormat.BINARY:
            return await self._handle_binary(request)
        elif fmt == ProtocolFormat.JSONRPC:
            return await self._handle_jsonrpc(request)
        else:
            return await self._handle_human(request)

    async def _handle_binary(self, data: bytes) -> bytes:
        """
        Handle binary protocol request.

        Args:
            data: Binary request data

        Returns:
            Binary response data
        """
        try:
            # Decode message
            message = self.binary.decode(data)

            # Process message
            response_msg = await self._process_message(message)

            # Encode response
            return self.binary.encode(response_msg)

        except BinaryProtocolError as e:
            # Return error message
            error_msg = Message(
                type=MessageType.ERROR,
                payload={
                    "code": -1,
                    "message": str(e),
                },
                correlation_id=getattr(e, 'correlation_id', None) or ''
            )
            return self.binary.encode(error_msg)

    async def _handle_jsonrpc(self, request: Union[dict, str, list]) -> Optional[dict]:
        """
        Handle JSON-RPC request.

        Args:
            request: JSON-RPC request dict, JSON string, or batch list

        Returns:
            JSON-RPC response dict or None for notifications
        """
        return await self.jsonrpc.handle_request(request)

    async def _handle_human(self, text: str) -> str:
        """
        Handle human-readable text input.

        Transforms to structured message, processes, and transforms back.

        Args:
            text: Human text input

        Returns:
            Human-readable response
        """
        # For now, route to JSON-RPC status
        response = await self.jsonrpc.handle_request({
            "jsonrpc": "2.0",
            "method": "otto.status",
            "id": "human-request",
        })

        if response and "result" in response:
            return self._format_human_response(response["result"])

        return "I'm here."

    async def _process_message(self, message: Message) -> Message:
        """
        Process a structured Message and return response.

        Routes based on message type to appropriate handler.

        Args:
            message: Incoming Message

        Returns:
            Response Message
        """
        if message.type == MessageType.STATE_QUERY:
            return await self._handle_state_query(message)

        elif message.type == MessageType.STATE_SYNC:
            return await self._handle_state_sync(message)

        elif message.type == MessageType.PROTECTION_CHECK:
            return await self._handle_protection_check(message)

        elif message.type == MessageType.HEARTBEAT:
            return message.reply(
                MessageType.HEARTBEAT,
                {"status": "ok"}
            )

        elif message.type in (MessageType.AGENT_SPAWN, MessageType.AGENT_RESULT, MessageType.AGENT_ABORT):
            # Route agent messages to the agent bridge
            return await self.agent_bridge.handle_message(message)

        else:
            # Unknown message type
            return message.reply(
                MessageType.ERROR,
                {
                    "code": -1,
                    "message": f"Unhandled message type: {message.type}",
                }
            )

    async def _handle_state_query(self, message: Message) -> Message:
        """Handle STATE_QUERY message."""
        if not self.state_manager:
            return message.reply(
                MessageType.ERROR,
                {"code": -2, "message": "State manager not configured"}
            )

        state = self.state_manager.get_state()
        fields = message.payload.get("fields")

        state_dict = state.to_dict()
        if fields:
            state_dict = {k: v for k, v in state_dict.items() if k in fields}

        return message.reply(
            MessageType.STATE_SYNC,
            {"state": state_dict}
        )

    async def _handle_state_sync(self, message: Message) -> Message:
        """Handle STATE_SYNC message."""
        if not self.state_manager:
            return message.reply(
                MessageType.ERROR,
                {"code": -2, "message": "State manager not configured"}
            )

        state_data = message.payload.get("state", {})
        self.state_manager.batch_update(state_data)

        return message.reply(
            MessageType.STATE_SYNC,
            {"state": self.state_manager.get_state().to_dict()}
        )

    async def _handle_protection_check(self, message: Message) -> Message:
        """Handle PROTECTION_CHECK message."""
        if not self.protection_engine:
            return message.reply(
                MessageType.PROTECTION_CHECK,
                {
                    "action": "allow",
                    "message": "",
                    "can_override": True,
                }
            )

        state = self.state_manager.get_state() if self.state_manager else None
        decision = self.protection_engine.check(state)

        return message.reply(
            MessageType.PROTECTION_CHECK,
            decision.to_dict()
        )

    def _format_human_response(self, result: Dict[str, Any]) -> str:
        """Format a result dict as human-readable text."""
        if self.render and self.state_manager:
            state = self.state_manager.get_state()
            return self.render.render_status(state)

        # Basic formatting
        status = result.get("status", "ok")
        return f"Status: {status}"

    def transform_up(self, message: Message) -> str:
        """
        Transform Message to human-readable string.

        Used when sending structured data to human interface.

        Args:
            message: Structured Message

        Returns:
            Human-readable string
        """
        if message.type == MessageType.STATE_SYNC:
            if self.render and self.state_manager:
                from ..cognitive_state import CognitiveState
                state_data = message.payload.get("state", {})
                state = CognitiveState.from_dict(state_data)
                return self.render.render_status(state)
            return f"State updated: {message.payload.get('state', {}).get('mode', 'unknown')}"

        elif message.type == MessageType.ERROR:
            return f"Error: {message.payload.get('message', 'Unknown error')}"

        elif message.type == MessageType.HEARTBEAT:
            return "OK"

        elif message.type == MessageType.PROTECTION_CHECK:
            action = message.payload.get("action", "unknown")
            msg = message.payload.get("message", "")
            if msg:
                return f"{action}: {msg}"
            return action

        else:
            return f"[{message.type.name}]"

    def transform_down(self, text: str, signals=None) -> Message:
        """
        Transform human text to structured Message.

        Used when receiving human input for structured processing.

        Args:
            text: Human text input
            signals: Optional SignalVector from PRISM detector

        Returns:
            Structured Message
        """
        text_lower = text.lower().strip()

        # Detect common patterns
        if any(word in text_lower for word in ["status", "how are", "state"]):
            return Message(
                type=MessageType.STATE_QUERY,
                payload={}
            )

        if any(word in text_lower for word in ["break", "stop", "tired"]):
            return Message(
                type=MessageType.PROTECTION_CHECK,
                payload={"action": "break_request"}
            )

        if signals:
            # Use signals to determine message type
            if signals.user_wants_break():
                return Message(
                    type=MessageType.PROTECTION_CHECK,
                    payload={"action": "break"}
                )

        # Default to heartbeat (keep-alive)
        return Message(
            type=MessageType.HEARTBEAT,
            payload={}
        )


__all__ = [
    "ProtocolFormat",
    "ProtocolRouter",
]
