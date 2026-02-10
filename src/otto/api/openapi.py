"""
OpenAPI 3.0 Specification Generator for OTTO Public REST API
============================================================

Generates OpenAPI 3.0 spec from route definitions.

The spec is auto-generated and served at /api/v1/openapi.json.

Determinism:
- DETERMINISTIC: same routes → same spec
"""

import json
from typing import Any, Dict, List, Optional

from .scopes import APIScope


def generate_openapi_spec(routes: Optional[List] = None) -> Dict[str, Any]:
    """
    Generate OpenAPI 3.0 specification.

    Args:
        routes: List of Route objects (uses ROUTES if not provided)

    Returns:
        OpenAPI 3.0 spec as dict
    """
    if routes is None:
        from .rest_router import ROUTES
        routes = ROUTES

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "OTTO OS Public REST API",
            "description": "REST API for third-party integrations with OTTO OS cognitive state management.",
            "version": "1.0.0",
            "contact": {
                "name": "OTTO OS",
                "url": "https://github.com/otto-os/otto",
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
        },
        "servers": [
            {
                "url": "http://localhost:8080",
                "description": "Local development server",
            },
        ],
        "paths": {},
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "API key in Bearer format: `Bearer otto_live_xxx...`",
                },
                "apiKeyHeader": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API key in X-API-Key header",
                },
            },
            "schemas": _generate_schemas(),
            "responses": _generate_responses(),
        },
        "security": [
            {"bearerAuth": []},
            {"apiKeyHeader": []},
        ],
        "tags": [
            {"name": "Status", "description": "System status endpoints"},
            {"name": "State", "description": "Cognitive state management"},
            {"name": "Sessions", "description": "Session lifecycle"},
            {"name": "Agents", "description": "Agent management"},
            {"name": "Integrations", "description": "External integrations"},
            {"name": "Protection", "description": "Burnout protection"},
        ],
    }

    # Generate paths from routes
    for route in routes:
        path = route.path_pattern.replace(":id", "{id}")
        method = route.method.lower()

        if path not in spec["paths"]:
            spec["paths"][path] = {}

        spec["paths"][path][method] = _generate_operation(route)

    # Add special endpoints
    spec["paths"]["/api/v1/health"] = {
        "get": {
            "summary": "Health check",
            "description": "Returns API health status. Does not require authentication.",
            "tags": ["Status"],
            "security": [],
            "responses": {
                "200": {
                    "description": "API is healthy",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/HealthResponse"},
                        },
                    },
                },
            },
        },
    }

    spec["paths"]["/api/v1/openapi.json"] = {
        "get": {
            "summary": "OpenAPI specification",
            "description": "Returns this OpenAPI 3.0 specification. Does not require authentication.",
            "tags": ["Status"],
            "security": [],
            "responses": {
                "200": {
                    "description": "OpenAPI specification",
                    "content": {
                        "application/json": {
                            "schema": {"type": "object"},
                        },
                    },
                },
            },
        },
    }

    return spec


def _generate_operation(route) -> Dict[str, Any]:
    """Generate OpenAPI operation for a route."""
    # Determine tag from method name
    tag = _get_tag(route.jsonrpc_method)

    operation = {
        "summary": _get_summary(route.jsonrpc_method),
        "description": _get_description(route.jsonrpc_method, route.required_scope),
        "tags": [tag],
        "operationId": route.jsonrpc_method.replace(".", "_"),
        "responses": {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/APIResponse"},
                    },
                },
            },
            "401": {"$ref": "#/components/responses/Unauthorized"},
            "403": {"$ref": "#/components/responses/Forbidden"},
            "429": {"$ref": "#/components/responses/RateLimited"},
            "500": {"$ref": "#/components/responses/InternalError"},
        },
    }

    # Add path parameters
    if ":id" in route.path_pattern:
        operation["parameters"] = [
            {
                "name": "id",
                "in": "path",
                "required": True,
                "description": "Resource identifier",
                "schema": {"type": "string"},
            },
        ]

    # Add request body for POST/PATCH
    if route.method in ("POST", "PATCH"):
        operation["requestBody"] = _get_request_body(route.jsonrpc_method)

    return operation


def _get_tag(method: str) -> str:
    """Get tag from JSON-RPC method name."""
    if method.startswith("otto.status") or method in ("otto.ping", "otto.methods"):
        return "Status"
    elif method.startswith("otto.state"):
        return "State"
    elif method.startswith("otto.session"):
        return "Sessions"
    elif method.startswith("otto.agent"):
        return "Agents"
    elif method.startswith("otto.integration") or method.startswith("otto.context"):
        return "Integrations"
    elif method.startswith("otto.protect"):
        return "Protection"
    return "Other"


def _get_summary(method: str) -> str:
    """Get operation summary from JSON-RPC method name."""
    summaries = {
        "otto.status": "Get OTTO status",
        "otto.ping": "Ping the API",
        "otto.methods": "List available methods",
        "otto.state.get": "Get cognitive state",
        "otto.state.update": "Update cognitive state",
        "otto.protect.check": "Check protection decision",
        "otto.session.start": "Start new session",
        "otto.session.end": "End current session",
        "otto.agent.list": "List agents",
        "otto.agent.spawn": "Spawn new agent",
        "otto.agent.abort": "Abort agent",
        "otto.integration.list": "List integrations",
        "otto.integration.sync": "Trigger integration sync",
        "otto.context.get": "Get external context",
    }
    return summaries.get(method, method)


def _get_description(method: str, scope: APIScope) -> str:
    """Get operation description."""
    base = _get_summary(method)
    return f"{base}.\n\nRequired scope: `{scope.value}`"


def _get_request_body(method: str) -> Dict[str, Any]:
    """Get request body schema for method."""
    schemas = {
        "otto.state.update": {
            "description": "State fields to update",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/StateUpdate"},
                },
            },
        },
        "otto.protect.check": {
            "description": "Action to check",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ProtectionCheck"},
                },
            },
        },
        "otto.session.start": {
            "description": "Session parameters",
            "required": False,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/SessionStart"},
                },
            },
        },
        "otto.agent.spawn": {
            "description": "Agent spawn parameters",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/AgentSpawn"},
                },
            },
        },
        "otto.integration.sync": {
            "description": "Sync parameters",
            "required": False,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/IntegrationSync"},
                },
            },
        },
    }

    return schemas.get(method, {
        "description": "Request body",
        "content": {
            "application/json": {
                "schema": {"type": "object"},
            },
        },
    })


def _generate_schemas() -> Dict[str, Any]:
    """Generate component schemas."""
    return {
        "APIResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "data": {"type": "object", "nullable": True},
                "error": {
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "details": {"type": "object", "nullable": True},
                    },
                },
                "meta": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "number"},
                        "version": {"type": "string"},
                        "request_id": {"type": "string"},
                        "rate_limit_remaining": {"type": "integer", "nullable": True},
                        "rate_limit_reset": {"type": "number", "nullable": True},
                    },
                },
            },
            "required": ["success", "meta"],
        },
        "HealthResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "data": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["healthy"]},
                        "timestamp": {"type": "number"},
                        "version": {"type": "string"},
                    },
                },
            },
        },
        "CognitiveState": {
            "type": "object",
            "properties": {
                "burnout_level": {
                    "type": "string",
                    "enum": ["GREEN", "YELLOW", "ORANGE", "RED"],
                    "description": "Current burnout level (sensitive)",
                },
                "energy_level": {
                    "type": "string",
                    "enum": ["high", "medium", "low", "depleted"],
                    "description": "Current energy level (sensitive)",
                },
                "momentum_phase": {
                    "type": "string",
                    "enum": ["cold_start", "building", "rolling", "peak", "crashed"],
                    "description": "Current momentum phase (sensitive)",
                },
                "decision_mode": {
                    "type": "string",
                    "enum": ["work", "delegate", "protect"],
                },
                "session_goal": {"type": "string", "nullable": True},
                "current_task": {"type": "string", "nullable": True},
            },
        },
        "StateUpdate": {
            "type": "object",
            "properties": {
                "burnout_level": {
                    "type": "string",
                    "enum": ["GREEN", "YELLOW", "ORANGE", "RED"],
                },
                "energy_level": {
                    "type": "string",
                    "enum": ["high", "medium", "low", "depleted"],
                },
                "momentum_phase": {
                    "type": "string",
                    "enum": ["cold_start", "building", "rolling", "peak", "crashed"],
                },
                "decision_mode": {
                    "type": "string",
                    "enum": ["work", "delegate", "protect"],
                },
            },
            "additionalProperties": True,
        },
        "ProtectionCheck": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to check (e.g., 'spawn_agent')",
                },
                "context": {
                    "type": "object",
                    "nullable": True,
                    "description": "Additional context for the check",
                },
            },
            "required": ["action"],
        },
        "SessionStart": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Session goal",
                },
            },
        },
        "AgentSpawn": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Task for the agent",
                },
                "agent_type": {
                    "type": "string",
                    "default": "general",
                    "description": "Type of agent to spawn",
                },
                "context": {
                    "type": "object",
                    "nullable": True,
                    "description": "Additional context",
                },
                "timeout": {
                    "type": "number",
                    "nullable": True,
                    "description": "Timeout in seconds",
                },
            },
            "required": ["task"],
        },
        "IntegrationSync": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "nullable": True,
                    "description": "Specific service to sync (all if not specified)",
                },
            },
        },
    }


def _generate_responses() -> Dict[str, Any]:
    """Generate common response definitions."""
    return {
        "Unauthorized": {
            "description": "Authentication required or invalid API key",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "enum": [False]},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "enum": ["UNAUTHORIZED"]},
                                    "message": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "headers": {
                "WWW-Authenticate": {
                    "description": "Authentication method",
                    "schema": {"type": "string", "example": "Bearer"},
                },
            },
        },
        "Forbidden": {
            "description": "Insufficient permissions (scope required)",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "enum": [False]},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "enum": ["FORBIDDEN"]},
                                    "message": {"type": "string"},
                                    "details": {
                                        "type": "object",
                                        "properties": {
                                            "required_scope": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "RateLimited": {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "enum": [False]},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "enum": ["RATE_LIMITED"]},
                                    "message": {"type": "string"},
                                    "details": {
                                        "type": "object",
                                        "properties": {
                                            "retry_after": {"type": "number"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "headers": {
                "Retry-After": {
                    "description": "Seconds to wait before retrying",
                    "schema": {"type": "integer"},
                },
            },
        },
        "InternalError": {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "enum": [False]},
                            "error": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "string", "enum": ["INTERNAL_ERROR"]},
                                    "message": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    }


__all__ = [
    "generate_openapi_spec",
]
