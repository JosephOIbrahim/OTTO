"""
JSON Schemas for OTTO API Input Validation
==========================================

Defines validation schemas for API request bodies.

[He2025] Compliance: FIXED schemas, DETERMINISTIC validation.
"""

from typing import Dict, Any


# =============================================================================
# State Update Schema
# =============================================================================

STATE_UPDATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "session_goal": {
            "type": "string",
            "maxLength": 500,
            "description": "Goal for the current session",
        },
        "active_mode": {
            "type": "string",
            "enum": ["focused", "exploring", "teaching", "recovery"],
            "description": "Active cognitive mode",
        },
        "energy_level": {
            "type": "string",
            "enum": ["high", "medium", "low", "depleted"],
            "description": "Current energy level",
        },
        "burnout_level": {
            "type": "string",
            "enum": ["GREEN", "YELLOW", "ORANGE", "RED"],
            "description": "Burnout warning level",
        },
    },
    "additionalProperties": False,
}


# =============================================================================
# Agent Schemas
# =============================================================================

AGENT_SPAWN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["task"],
    "properties": {
        "task": {
            "type": "string",
            "minLength": 1,
            "maxLength": 1000,
            "description": "Task description for the agent",
        },
        "type": {
            "type": "string",
            "enum": ["researcher", "coder", "reviewer", "analyst", "general"],
            "description": "Type of agent to spawn",
        },
        "priority": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "description": "Task priority (1=lowest, 10=highest)",
        },
        "timeout": {
            "type": "integer",
            "minimum": 1,
            "maximum": 3600,
            "description": "Timeout in seconds (max 1 hour)",
        },
        "config": {
            "type": "object",
            "description": "Additional agent configuration",
            "additionalProperties": True,
        },
    },
    "additionalProperties": False,
}

AGENT_ABORT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "reason": {
            "type": "string",
            "maxLength": 500,
            "description": "Reason for aborting the agent",
        },
        "force": {
            "type": "boolean",
            "description": "Force immediate termination",
        },
    },
    "additionalProperties": False,
}


# =============================================================================
# Session Schemas
# =============================================================================

SESSION_START_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "goal": {
            "type": "string",
            "maxLength": 500,
            "description": "Session goal",
        },
        "mode": {
            "type": "string",
            "enum": ["focused", "exploring", "teaching", "recovery"],
            "description": "Initial cognitive mode",
        },
        "context": {
            "type": "object",
            "description": "Additional context for the session",
            "additionalProperties": True,
        },
    },
    "additionalProperties": False,
}

SESSION_END_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "maxLength": 1000,
            "description": "Session summary",
        },
        "save_state": {
            "type": "boolean",
            "description": "Whether to save session state",
        },
    },
    "additionalProperties": False,
}


# =============================================================================
# Protection Schema
# =============================================================================

PROTECTION_CHECK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "maxLength": 200,
            "description": "Action to check",
        },
        "context": {
            "type": "object",
            "description": "Context for the protection check",
            "additionalProperties": True,
        },
    },
    "additionalProperties": False,
}


# =============================================================================
# Integration Schema
# =============================================================================

INTEGRATION_SYNC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "integrations": {
            "type": "array",
            "items": {
                "type": "string",
            },
            "maxItems": 20,
            "description": "List of integrations to sync",
        },
        "force": {
            "type": "boolean",
            "description": "Force sync even if recently synced",
        },
    },
    "additionalProperties": False,
}


# =============================================================================
# Schema Registry
# =============================================================================

# Map endpoint patterns to schemas
# Format: "METHOD:path" -> schema
ENDPOINT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    # State
    "PATCH:/api/v1/state": STATE_UPDATE_SCHEMA,

    # Agents
    "POST:/api/v1/agents": AGENT_SPAWN_SCHEMA,
    "DELETE:/api/v1/agents/:id": AGENT_ABORT_SCHEMA,

    # Sessions
    "POST:/api/v1/sessions": SESSION_START_SCHEMA,
    "DELETE:/api/v1/sessions/current": SESSION_END_SCHEMA,

    # Protection
    "POST:/api/v1/protection/check": PROTECTION_CHECK_SCHEMA,

    # Integrations
    "POST:/api/v1/integrations/sync": INTEGRATION_SYNC_SCHEMA,
}


def get_schema_for_endpoint(method: str, path: str) -> Dict[str, Any] | None:
    """
    Get validation schema for an endpoint.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path

    Returns:
        Schema dict if found, None otherwise
    """
    # Try exact match
    key = f"{method}:{path}"
    if key in ENDPOINT_SCHEMAS:
        return ENDPOINT_SCHEMAS[key]

    # Try pattern match (replace IDs with :id)
    normalized = _normalize_path(path)
    key = f"{method}:{normalized}"
    if key in ENDPOINT_SCHEMAS:
        return ENDPOINT_SCHEMAS[key]

    return None


def _normalize_path(path: str) -> str:
    """Normalize path by replacing IDs with :id."""
    parts = path.split("/")
    normalized = []
    for part in parts:
        # If it looks like an ID (alphanumeric, 8+ chars), replace
        if part and len(part) >= 8 and part.isalnum():
            normalized.append(":id")
        else:
            normalized.append(part)
    return "/".join(normalized)


__all__ = [
    # Schemas
    "STATE_UPDATE_SCHEMA",
    "AGENT_SPAWN_SCHEMA",
    "AGENT_ABORT_SCHEMA",
    "SESSION_START_SCHEMA",
    "SESSION_END_SCHEMA",
    "PROTECTION_CHECK_SCHEMA",
    "INTEGRATION_SYNC_SCHEMA",

    # Registry
    "ENDPOINT_SCHEMAS",
    "get_schema_for_endpoint",
]
