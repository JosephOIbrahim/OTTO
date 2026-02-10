"""
Tests for InputValidationMiddleware

Tests request body validation against JSON schemas.

Determinism: Verifies FIXED schemas, DETERMINISTIC validation.
"""

import pytest
from typing import Dict, Any

from otto.api import (
    InputValidationMiddleware,
    APIRequestContext,
    create_api_middleware,
    APIKeyManager,
    STATE_UPDATE_SCHEMA,
    AGENT_SPAWN_SCHEMA,
    AGENT_ABORT_SCHEMA,
    SESSION_START_SCHEMA,
    SESSION_END_SCHEMA,
    PROTECTION_CHECK_SCHEMA,
    INTEGRATION_SYNC_SCHEMA,
    ENDPOINT_SCHEMAS,
    get_schema_for_endpoint,
)
from otto.http_server import HTTPRequest, HTTPResponse


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def validation_middleware() -> InputValidationMiddleware:
    """Create input validation middleware."""
    return InputValidationMiddleware()


@pytest.fixture
def non_strict_middleware() -> InputValidationMiddleware:
    """Create non-strict input validation middleware."""
    return InputValidationMiddleware(strict=False)


def create_request_context(
    method: str,
    path: str,
    body: Dict[str, Any] | None = None,
) -> APIRequestContext:
    """Create request context with body."""
    import json

    headers = {"content-type": "application/json"}
    body_bytes = json.dumps(body).encode() if body else b""

    request = HTTPRequest(
        method=method,
        path=path,
        headers=headers,
        body=body_bytes,
    )

    ctx = APIRequestContext.from_http_request(request)
    ctx.body = body  # Set body directly for testing
    return ctx


# =============================================================================
# Test: Schema Registry
# =============================================================================

class TestSchemaRegistry:
    """Test schema registry and lookup."""

    def test_endpoint_schemas_exist(self):
        """All expected endpoints have schemas."""
        expected = [
            "PATCH:/api/v1/state",
            "POST:/api/v1/agents",
            "DELETE:/api/v1/agents/:id",
            "POST:/api/v1/sessions",
            "DELETE:/api/v1/sessions/current",
            "POST:/api/v1/protection/check",
            "POST:/api/v1/integrations/sync",
        ]
        for endpoint in expected:
            assert endpoint in ENDPOINT_SCHEMAS, f"Missing schema for {endpoint}"

    def test_get_schema_exact_match(self):
        """get_schema_for_endpoint returns schema for exact match."""
        schema = get_schema_for_endpoint("PATCH", "/api/v1/state")
        assert schema is not None
        assert schema == STATE_UPDATE_SCHEMA

    def test_get_schema_with_id(self):
        """get_schema_for_endpoint normalizes IDs."""
        schema = get_schema_for_endpoint("DELETE", "/api/v1/agents/abc12345def67890")
        assert schema is not None
        assert schema == AGENT_ABORT_SCHEMA

    def test_get_schema_not_found(self):
        """get_schema_for_endpoint returns None for unknown endpoints."""
        schema = get_schema_for_endpoint("GET", "/api/v1/unknown")
        assert schema is None

    def test_get_schema_wrong_method(self):
        """get_schema_for_endpoint returns None for wrong method."""
        # GET /api/v1/state has no schema (only PATCH does)
        schema = get_schema_for_endpoint("GET", "/api/v1/state")
        assert schema is None


# =============================================================================
# Test: State Update Validation
# =============================================================================

class TestStateUpdateValidation:
    """Test STATE_UPDATE_SCHEMA validation."""

    @pytest.mark.asyncio
    async def test_valid_state_update(self, validation_middleware):
        """Valid state update body passes validation."""
        ctx = create_request_context(
            "PATCH", "/api/v1/state",
            body={
                "session_goal": "Complete API implementation",
                "active_mode": "focused",
            }
        )

        result = await validation_middleware.process(ctx)
        assert result is None  # No error

    @pytest.mark.asyncio
    async def test_invalid_mode_value(self, validation_middleware):
        """Invalid enum value fails validation."""
        ctx = create_request_context(
            "PATCH", "/api/v1/state",
            body={"active_mode": "invalid_mode"}
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "must be one of" in result.body

    @pytest.mark.asyncio
    async def test_goal_too_long(self, validation_middleware):
        """String exceeding maxLength fails validation."""
        ctx = create_request_context(
            "PATCH", "/api/v1/state",
            body={"session_goal": "x" * 501}  # Exceeds 500 char limit
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "exceeds maximum" in result.body

    @pytest.mark.asyncio
    async def test_unknown_field_strict(self, validation_middleware):
        """Unknown field fails in strict mode."""
        ctx = create_request_context(
            "PATCH", "/api/v1/state",
            body={"unknown_field": "value"}
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "unknown field" in result.body.lower()

    @pytest.mark.asyncio
    async def test_unknown_field_non_strict(self, non_strict_middleware):
        """Unknown field passes in non-strict mode."""
        ctx = create_request_context(
            "PATCH", "/api/v1/state",
            body={"unknown_field": "value"}
        )

        result = await non_strict_middleware.process(ctx)
        assert result is None  # No error


# =============================================================================
# Test: Agent Spawn Validation
# =============================================================================

class TestAgentSpawnValidation:
    """Test AGENT_SPAWN_SCHEMA validation."""

    @pytest.mark.asyncio
    async def test_valid_agent_spawn(self, validation_middleware):
        """Valid agent spawn body passes validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={
                "task": "Analyze the codebase",
                "type": "researcher",
                "priority": 5,
            }
        )

        result = await validation_middleware.process(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_required_task(self, validation_middleware):
        """Missing required field fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={"type": "researcher"}  # Missing 'task'
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "required" in result.body.lower()

    @pytest.mark.asyncio
    async def test_task_too_short(self, validation_middleware):
        """Task shorter than minLength fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": ""}  # Empty string
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "shorter than minimum" in result.body

    @pytest.mark.asyncio
    async def test_task_too_long(self, validation_middleware):
        """Task exceeding maxLength fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": "x" * 1001}  # Exceeds 1000 char limit
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "exceeds maximum" in result.body

    @pytest.mark.asyncio
    async def test_invalid_agent_type(self, validation_middleware):
        """Invalid agent type fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": "Do something", "type": "invalid_type"}
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400

    @pytest.mark.asyncio
    async def test_priority_below_minimum(self, validation_middleware):
        """Priority below minimum fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": "Do something", "priority": 0}
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "less than minimum" in result.body

    @pytest.mark.asyncio
    async def test_priority_above_maximum(self, validation_middleware):
        """Priority above maximum fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": "Do something", "priority": 11}
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "exceeds maximum" in result.body


# =============================================================================
# Test: Type Validation
# =============================================================================

class TestTypeValidation:
    """Test type checking for different field types."""

    @pytest.mark.asyncio
    async def test_wrong_type_string(self, validation_middleware):
        """Number when string expected fails validation."""
        ctx = create_request_context(
            "PATCH", "/api/v1/state",
            body={"session_goal": 123}  # Should be string
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "expected string" in result.body

    @pytest.mark.asyncio
    async def test_wrong_type_integer(self, validation_middleware):
        """String when integer expected fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": "Do something", "priority": "high"}  # Should be int
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "expected integer" in result.body

    @pytest.mark.asyncio
    async def test_boolean_not_integer(self, validation_middleware):
        """Boolean is not a valid integer."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": "Do something", "priority": True}
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400


# =============================================================================
# Test: Array Validation
# =============================================================================

class TestArrayValidation:
    """Test array validation."""

    @pytest.mark.asyncio
    async def test_valid_array(self, validation_middleware):
        """Valid array passes validation."""
        ctx = create_request_context(
            "POST", "/api/v1/integrations/sync",
            body={"integrations": ["github", "slack"]}
        )

        result = await validation_middleware.process(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_array_too_many_items(self, validation_middleware):
        """Array exceeding maxItems fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/integrations/sync",
            body={"integrations": [f"integration_{i}" for i in range(25)]}  # Max is 20
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "exceeds maximum" in result.body

    @pytest.mark.asyncio
    async def test_array_wrong_type(self, validation_middleware):
        """Non-array when array expected fails validation."""
        ctx = create_request_context(
            "POST", "/api/v1/integrations/sync",
            body={"integrations": "not_an_array"}
        )

        result = await validation_middleware.process(ctx)
        assert result is not None
        assert result.status == 400
        assert "expected array" in result.body


# =============================================================================
# Test: No Body / No Schema
# =============================================================================

class TestNoBodyNoSchema:
    """Test behavior when no body or no schema."""

    @pytest.mark.asyncio
    async def test_no_body_no_schema(self, validation_middleware):
        """No body and no schema passes validation."""
        ctx = create_request_context("GET", "/api/v1/status", body=None)

        result = await validation_middleware.process(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_schema_for_endpoint(self, validation_middleware):
        """Endpoint without schema passes validation."""
        ctx = create_request_context(
            "GET", "/api/v1/unknown",
            body={"any": "data"}
        )

        result = await validation_middleware.process(ctx)
        assert result is None  # No schema, so no validation

    @pytest.mark.asyncio
    async def test_empty_body_object(self, validation_middleware):
        """Empty body object passes when no required fields."""
        ctx = create_request_context(
            "PATCH", "/api/v1/state",
            body={}  # Empty, but STATE_UPDATE has no required fields
        )

        result = await validation_middleware.process(ctx)
        assert result is None


# =============================================================================
# Test: Determinism
# =============================================================================

class TestDeterminism:
    """Test Determinism."""

    def test_schemas_are_fixed(self):
        """Schemas should be identical across instantiations."""
        mw1 = InputValidationMiddleware()
        mw2 = InputValidationMiddleware()

        # Get same schema
        schema1 = mw1._get_schema("PATCH", "/api/v1/state")
        schema2 = mw2._get_schema("PATCH", "/api/v1/state")

        assert schema1 == schema2

    @pytest.mark.asyncio
    async def test_validation_is_deterministic(self):
        """Same input produces same validation result."""
        mw1 = InputValidationMiddleware()
        mw2 = InputValidationMiddleware()

        # Valid input
        ctx1 = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": "Test task"}
        )
        ctx2 = create_request_context(
            "POST", "/api/v1/agents",
            body={"task": "Test task"}
        )

        result1 = await mw1.process(ctx1)
        result2 = await mw2.process(ctx2)

        assert result1 == result2 == None

    @pytest.mark.asyncio
    async def test_error_is_deterministic(self):
        """Same invalid input produces same error."""
        mw1 = InputValidationMiddleware()
        mw2 = InputValidationMiddleware()

        ctx1 = create_request_context(
            "POST", "/api/v1/agents",
            body={}  # Missing required 'task'
        )
        ctx2 = create_request_context(
            "POST", "/api/v1/agents",
            body={}
        )

        result1 = await mw1.process(ctx1)
        result2 = await mw2.process(ctx2)

        assert result1.status == result2.status == 400


# =============================================================================
# Test: Error Response Format
# =============================================================================

class TestErrorResponseFormat:
    """Test error response structure."""

    @pytest.mark.asyncio
    async def test_error_response_status(self, validation_middleware):
        """Validation error returns 400 status."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={}
        )

        result = await validation_middleware.process(ctx)
        assert result.status == 400

    @pytest.mark.asyncio
    async def test_error_response_content_type(self, validation_middleware):
        """Validation error returns JSON content type."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={}
        )

        result = await validation_middleware.process(ctx)
        assert result.content_type == "application/json"

    @pytest.mark.asyncio
    async def test_error_response_contains_errors(self, validation_middleware):
        """Validation error response contains error details."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={}
        )

        result = await validation_middleware.process(ctx)
        import json
        body = json.loads(result.body)

        assert "error" in body
        assert body["error"] is not None


# =============================================================================
# Test: create_api_middleware Integration
# =============================================================================

class TestCreateApiMiddlewareIntegration:
    """Test InputValidationMiddleware in the middleware chain."""

    def test_included_by_default(self, tmp_path):
        """Input validation is included by default."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        chain = create_api_middleware(key_manager=manager)

        has_validation = any(
            isinstance(mw, InputValidationMiddleware)
            for mw in chain._middleware
        )
        assert has_validation

    def test_can_disable(self, tmp_path):
        """Input validation can be disabled."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        chain = create_api_middleware(
            key_manager=manager,
            include_input_validation=False,
        )

        has_validation = any(
            isinstance(mw, InputValidationMiddleware)
            for mw in chain._middleware
        )
        assert not has_validation

    def test_validation_is_last(self, tmp_path):
        """Input validation should be last in processing order."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        chain = create_api_middleware(key_manager=manager)

        # Find index of validation middleware
        for i, mw in enumerate(chain._middleware):
            if isinstance(mw, InputValidationMiddleware):
                validation_index = i
                break

        # Should be last (after security, auth, rate limit, scope)
        assert validation_index == len(chain._middleware) - 1


# =============================================================================
# Test: Nested Object Validation
# =============================================================================

class TestNestedObjectValidation:
    """Test validation of nested objects."""

    @pytest.mark.asyncio
    async def test_nested_object_valid(self, validation_middleware):
        """Valid nested object passes validation."""
        ctx = create_request_context(
            "POST", "/api/v1/agents",
            body={
                "task": "Analyze code",
                "config": {"depth": 5, "verbose": True}
            }
        )

        result = await validation_middleware.process(ctx)
        assert result is None

    @pytest.mark.asyncio
    async def test_context_object_valid(self, validation_middleware):
        """Valid context object passes validation."""
        ctx = create_request_context(
            "POST", "/api/v1/sessions",
            body={
                "goal": "Complete implementation",
                "context": {"project": "OTTO_OS", "phase": 1}
            }
        )

        result = await validation_middleware.process(ctx)
        assert result is None


# =============================================================================
# Test: All Schema Validation
# =============================================================================

class TestAllSchemas:
    """Test all defined schemas work correctly."""

    @pytest.mark.parametrize("method,path,valid_body", [
        ("PATCH", "/api/v1/state", {"active_mode": "focused"}),
        ("POST", "/api/v1/agents", {"task": "Test task"}),
        ("DELETE", "/api/v1/agents/abc12345def67890", {"reason": "Testing"}),
        ("POST", "/api/v1/sessions", {"goal": "Test session"}),
        ("DELETE", "/api/v1/sessions/current", {"save_state": True}),
        ("POST", "/api/v1/protection/check", {"action": "spawn_agent"}),
        ("POST", "/api/v1/integrations/sync", {"integrations": ["github"]}),
    ])
    @pytest.mark.asyncio
    async def test_valid_body_passes(
        self,
        validation_middleware,
        method: str,
        path: str,
        valid_body: Dict[str, Any],
    ):
        """Valid body passes validation for all schemas."""
        ctx = create_request_context(method, path, body=valid_body)
        result = await validation_middleware.process(ctx)
        assert result is None, f"Validation failed for {method} {path}: {result.body if result else ''}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
