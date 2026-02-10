"""
Message Type Definitions
========================

Defines the core message types for OTTO OS inter-layer communication.

Message Categories:
- STATE (0x00XX): Cognitive state synchronization
- AGENT (0x00X0): Agent lifecycle management
- PROTECTION (0x002X): Protection engine communication
- KNOWLEDGE (0x003X): Knowledge graph queries
- CONTEXT (0x004X): External integration context (Phase 5)
- SYSTEM (0x00FX): Heartbeat, errors, control

Determinism:
- Fixed type values (never change once assigned)
- Deterministic serialization (sorted keys)
- Checksum generation for message integrity
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Any, Optional


class ProtocolError(Exception):
    """Base exception for protocol errors."""
    pass


class MessageType(IntEnum):
    """
    Message type identifiers for protocol communication.

    Organized by category:
    - 0x0001-0x000F: State operations
    - 0x0010-0x001F: Agent operations
    - 0x0020-0x002F: Protection operations
    - 0x0030-0x003F: Knowledge operations
    - 0x0040-0x004F: Context operations (Phase 5 integrations)
    - 0x00F0-0x00FF: System operations
    """
    # State operations (0x0001-0x000F)
    STATE_SYNC = 0x0001        # Carries CognitiveState.to_dict()
    STATE_QUERY = 0x0002       # Returns current state

    # Agent operations (0x0010-0x001F)
    AGENT_SPAWN = 0x0010       # Payload: agent_type, task, context
    AGENT_RESULT = 0x0011      # Payload: result, files_modified, errors
    AGENT_ABORT = 0x0012       # Payload: agent_id, reason

    # Protection operations (0x0020-0x002F)
    PROTECTION_CHECK = 0x0020  # Returns ProtectionDecision.to_dict()
    PROTECTION_OVERRIDE = 0x0021  # User override acknowledgment

    # Knowledge operations (0x0030-0x003F)
    KNOWLEDGE_QUERY = 0x0030   # Query knowledge graph
    KNOWLEDGE_STORE = 0x0031   # Store new knowledge

    # Context operations (0x0040-0x004F) - Phase 5 integrations
    CONTEXT_SYNC = 0x0040      # External context update
    CONTEXT_QUERY = 0x0041     # Request current context
    CONTEXT_SUBSCRIBE = 0x0042  # Subscribe to context updates
    CONTEXT_ERROR = 0x004F     # Integration error

    # System operations (0x00F0-0x00FF)
    HEARTBEAT = 0x00F0         # Keep-alive
    ERROR = 0x00FF             # Error response


@dataclass
class Message:
    """
    Core message structure for protocol communication.

    A Message is the atomic unit of communication between protocol layers.
    It carries a typed payload with metadata for tracing and correlation.

    Attributes:
        type: MessageType identifying the message category
        payload: Dict containing message-specific data
        timestamp: Unix timestamp of message creation
        source: Identifier of the message source
        correlation_id: UUID for request-response correlation
        sequence: Optional sequence number for ordered delivery
        priority: Message priority (0=normal, 1=high, 2=critical)

    Example:
        >>> msg = Message(
        ...     type=MessageType.STATE_SYNC,
        ...     payload={"state": state.to_dict()}
        ... )
        >>> encoded = msg.to_dict()
        >>> decoded = Message.from_dict(encoded)
    """
    type: MessageType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "otto"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence: Optional[int] = None
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize message to dictionary.

        Returns:
            Dict with deterministically ordered keys
        """
        return {
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "sequence": self.sequence,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """
        Deserialize message from dictionary.

        Args:
            data: Dict containing message fields

        Returns:
            Message instance

        Raises:
            ProtocolError: If required fields are missing or invalid
        """
        try:
            msg_type = data.get("type")
            if msg_type is None:
                raise ProtocolError("Missing required field: type")

            return cls(
                type=MessageType(msg_type),
                payload=data.get("payload", {}),
                timestamp=data.get("timestamp", time.time()),
                source=data.get("source", "unknown"),
                correlation_id=data.get("correlation_id", str(uuid.uuid4())),
                sequence=data.get("sequence"),
                priority=data.get("priority", 0),
            )
        except ValueError as e:
            raise ProtocolError(f"Invalid message type: {e}") from e

    def checksum(self) -> str:
        """
        Generate deterministic checksum of message content.

        Uses SHA-256 truncated to 16 hex chars for compact representation.
        Includes type, payload, and timestamp for uniqueness.

        Returns:
            16-character hex string
        """
        content = {
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def reply(
        self,
        type: MessageType,
        payload: Dict[str, Any] = None
    ) -> 'Message':
        """
        Create a reply message with the same correlation_id.

        Args:
            type: MessageType for the reply
            payload: Reply payload

        Returns:
            New Message with matching correlation_id
        """
        return Message(
            type=type,
            payload=payload or {},
            source="otto",
            correlation_id=self.correlation_id,
        )

    def is_error(self) -> bool:
        """Check if this is an error message."""
        return self.type == MessageType.ERROR

    def is_response_to(self, request: 'Message') -> bool:
        """Check if this message is a response to the given request."""
        return self.correlation_id == request.correlation_id


# =============================================================================
# Payload Schemas
# =============================================================================

PAYLOAD_SCHEMAS: Dict[MessageType, Dict[str, Any]] = {
    MessageType.STATE_SYNC: {
        "required": ["state"],
        "optional": ["force"],
        "properties": {
            "state": {"type": "object", "description": "CognitiveState.to_dict()"},
            "force": {"type": "boolean", "description": "Force sync even if unchanged"},
        }
    },

    MessageType.STATE_QUERY: {
        "required": [],
        "optional": ["fields"],
        "properties": {
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific fields to return (all if omitted)"
            },
        }
    },

    MessageType.AGENT_SPAWN: {
        "required": ["agent_type", "task"],
        "optional": ["context", "timeout", "priority"],
        "properties": {
            "agent_type": {"type": "string", "description": "Type of agent to spawn"},
            "task": {"type": "string", "description": "Task description"},
            "context": {"type": "object", "description": "Agent context data"},
            "timeout": {"type": "number", "description": "Timeout in seconds"},
            "priority": {"type": "integer", "description": "Spawn priority"},
        }
    },

    MessageType.AGENT_RESULT: {
        "required": ["agent_id", "status"],
        "optional": ["result", "files_modified", "errors", "duration"],
        "properties": {
            "agent_id": {"type": "string", "description": "Agent identifier"},
            "status": {"type": "string", "enum": ["success", "failure", "timeout"]},
            "result": {"type": "object", "description": "Agent result data"},
            "files_modified": {"type": "array", "items": {"type": "string"}},
            "errors": {"type": "array", "items": {"type": "string"}},
            "duration": {"type": "number", "description": "Execution time in seconds"},
        }
    },

    MessageType.AGENT_ABORT: {
        "required": ["agent_id"],
        "optional": ["reason"],
        "properties": {
            "agent_id": {"type": "string", "description": "Agent to abort"},
            "reason": {"type": "string", "description": "Abort reason"},
        }
    },

    MessageType.PROTECTION_CHECK: {
        "required": ["action"],
        "optional": ["context", "signals"],
        "properties": {
            "action": {"type": "string", "description": "Action to check"},
            "context": {"type": "object", "description": "Additional context"},
            "signals": {"type": "object", "description": "Signal vector data"},
        }
    },

    MessageType.PROTECTION_OVERRIDE: {
        "required": ["decision_id"],
        "optional": ["reason"],
        "properties": {
            "decision_id": {"type": "string", "description": "Decision being overridden"},
            "reason": {"type": "string", "description": "Override reason"},
        }
    },

    MessageType.KNOWLEDGE_QUERY: {
        "required": ["query"],
        "optional": ["path", "confidence_threshold"],
        "properties": {
            "query": {"type": "string", "description": "Search query or path"},
            "path": {"type": "string", "description": "Direct path for O(1) lookup"},
            "confidence_threshold": {"type": "number", "description": "Min confidence"},
        }
    },

    MessageType.KNOWLEDGE_STORE: {
        "required": ["path", "content"],
        "optional": ["triggers", "confidence"],
        "properties": {
            "path": {"type": "string", "description": "Knowledge path"},
            "content": {"type": "object", "description": "Knowledge content"},
            "triggers": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
        }
    },

    MessageType.CONTEXT_SYNC: {
        "required": ["context"],
        "optional": ["source", "force"],
        "properties": {
            "context": {"type": "object", "description": "ExternalContext.to_dict()"},
            "source": {"type": "string", "description": "Which integration triggered sync"},
            "force": {"type": "boolean", "description": "Force sync even if unchanged"},
        }
    },

    MessageType.CONTEXT_QUERY: {
        "required": [],
        "optional": ["integration_type", "force_refresh"],
        "properties": {
            "integration_type": {
                "type": "string",
                "enum": ["calendar", "task_manager", "notes"],
                "description": "Specific integration type to query"
            },
            "force_refresh": {"type": "boolean", "description": "Force refresh from external service"},
        }
    },

    MessageType.CONTEXT_SUBSCRIBE: {
        "required": [],
        "optional": ["integration_types", "min_interval"],
        "properties": {
            "integration_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Integration types to subscribe to"
            },
            "min_interval": {"type": "number", "description": "Min seconds between updates"},
        }
    },

    MessageType.CONTEXT_ERROR: {
        "required": ["integration", "error_type"],
        "optional": ["message", "retry_after"],
        "properties": {
            "integration": {"type": "string", "description": "Integration that failed"},
            "error_type": {
                "type": "string",
                "enum": ["auth", "rate_limit", "unavailable", "unknown"],
                "description": "Type of error"
            },
            "message": {"type": "string", "description": "Error message"},
            "retry_after": {"type": "number", "description": "Seconds until retry"},
        }
    },

    MessageType.HEARTBEAT: {
        "required": [],
        "optional": ["load", "uptime"],
        "properties": {
            "load": {"type": "number", "description": "Current load percentage"},
            "uptime": {"type": "number", "description": "Uptime in seconds"},
        }
    },

    MessageType.ERROR: {
        "required": ["code", "message"],
        "optional": ["data", "source_type"],
        "properties": {
            "code": {"type": "integer", "description": "Error code"},
            "message": {"type": "string", "description": "Error message"},
            "data": {"type": "object", "description": "Additional error data"},
            "source_type": {"type": "integer", "description": "Original message type"},
        }
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def create_state_sync(state_dict: Dict[str, Any], force: bool = False) -> Message:
    """Create a STATE_SYNC message."""
    return Message(
        type=MessageType.STATE_SYNC,
        payload={"state": state_dict, "force": force}
    )


def create_state_query(fields: list = None) -> Message:
    """Create a STATE_QUERY message."""
    payload = {}
    if fields:
        payload["fields"] = fields
    return Message(type=MessageType.STATE_QUERY, payload=payload)


def create_error(code: int, message: str, data: Dict = None) -> Message:
    """Create an ERROR message."""
    payload = {"code": code, "message": message}
    if data:
        payload["data"] = data
    return Message(type=MessageType.ERROR, payload=payload)


def create_heartbeat(load: float = None, uptime: float = None) -> Message:
    """Create a HEARTBEAT message."""
    payload = {}
    if load is not None:
        payload["load"] = load
    if uptime is not None:
        payload["uptime"] = uptime
    return Message(type=MessageType.HEARTBEAT, payload=payload)


def create_context_sync(context_dict: Dict[str, Any], source: str = None) -> Message:
    """Create a CONTEXT_SYNC message."""
    payload = {"context": context_dict}
    if source:
        payload["source"] = source
    return Message(type=MessageType.CONTEXT_SYNC, payload=payload)


def create_context_query(
    integration_type: str = None,
    force_refresh: bool = False
) -> Message:
    """Create a CONTEXT_QUERY message."""
    payload = {}
    if integration_type:
        payload["integration_type"] = integration_type
    if force_refresh:
        payload["force_refresh"] = force_refresh
    return Message(type=MessageType.CONTEXT_QUERY, payload=payload)


def create_context_error(
    integration: str,
    error_type: str,
    message: str = None,
    retry_after: float = None
) -> Message:
    """Create a CONTEXT_ERROR message."""
    payload = {"integration": integration, "error_type": error_type}
    if message:
        payload["message"] = message
    if retry_after is not None:
        payload["retry_after"] = retry_after
    return Message(type=MessageType.CONTEXT_ERROR, payload=payload)


__all__ = [
    "MessageType",
    "Message",
    "PAYLOAD_SCHEMAS",
    "ProtocolError",
    "create_state_sync",
    "create_state_query",
    "create_error",
    "create_heartbeat",
    "create_context_sync",
    "create_context_query",
    "create_context_error",
]
