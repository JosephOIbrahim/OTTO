"""
Protocol Module
===============

Implements the OTTO OS communication protocol layers:

Layer 2: JSON-RPC (structured requests/responses)
Layer 1: Binary Protocol (MessagePack for speed)

Architecture:
    User Interface (CLI/TUI)
        │
        ▼
    Human Render (dignity-first)
        │
        ▼
    OTTO Core (JSON-RPC)      ◄── This module
        │
        ▼
    Agent Kernel (Binary)     ◄── This module
        │
        ▼
    Persistence (file_ops)

Each layer only talks to adjacent layers (layer isolation).
"""

__version__ = "0.7.0"

# Message Types
from .message_types import (
    MessageType,
    Message,
    PAYLOAD_SCHEMAS,
    ProtocolError,
)

# Binary Protocol (Layer 0)
from .layer0_binary import (
    BinaryProtocol,
    BinaryProtocolError,
)

# JSON-RPC Layer (Layer 1)
from .layer1_jsonrpc import (
    JSONRPCHandler,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)

# Protocol Router (Layer Integration)
from .protocol_router import (
    ProtocolFormat,
    ProtocolRouter,
)

# Validation
from .validator import (
    ValidationResult,
    ProtocolValidator,
)

# Agent Bridge
from .agent_bridge import (
    AgentProtocolBridge,
    AgentBridgeConfig,
    AgentBridgeError,
    SpawnStatus,
    SpawnedAgent,
    create_agent_bridge,
)

# Protocol Factory
from .protocol_factory import (
    create_protocol_router,
    create_minimal_router,
    create_router_with_state,
)

# Agent Executors
from .agent_executors import (
    explore_executor,
    implement_executor,
    review_executor,
    research_executor,
    general_executor,
    get_executor,
    list_executors,
    EXECUTOR_REGISTRY,
)

__all__ = [
    # Version
    "__version__",

    # Message Types
    "MessageType",
    "Message",
    "PAYLOAD_SCHEMAS",
    "ProtocolError",

    # Binary Protocol
    "BinaryProtocol",
    "BinaryProtocolError",

    # JSON-RPC
    "JSONRPCHandler",
    "JSONRPCError",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",

    # Router
    "ProtocolFormat",
    "ProtocolRouter",

    # Validation
    "ValidationResult",
    "ProtocolValidator",

    # Agent Bridge
    "AgentProtocolBridge",
    "AgentBridgeConfig",
    "AgentBridgeError",
    "SpawnStatus",
    "SpawnedAgent",
    "create_agent_bridge",

    # Protocol Factory
    "create_protocol_router",
    "create_minimal_router",
    "create_router_with_state",

    # Agent Executors
    "explore_executor",
    "implement_executor",
    "review_executor",
    "research_executor",
    "general_executor",
    "get_executor",
    "list_executors",
    "EXECUTOR_REGISTRY",
]
