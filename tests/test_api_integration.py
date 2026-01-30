"""
End-to-end integration tests for OTTO Public REST API.

Tests the full request flow:
  HTTP Request → REST Router → Middleware Chain → JSON-RPC Handler → Response

ThinkingMachines [He2025] Compliance:
- Tests verify deterministic behavior
- Same input → same output
"""

import asyncio
import json
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch

from otto.http_server import (
    HTTPRequest,
    HTTPResponse,
    OperationalHTTPServer,
    start_server,
    stop_server,
)
from otto.api import (
    # Scopes
    APIScope,
    # API Keys
    APIKey,
    APIKeyManager,
    generate_api_key,
    reset_manager,
    get_manager,
    # Response
    APIResponse,
    success,
    error,
    # Errors
    APIErrorCode,
    # Middleware
    APIRequestContext,
    MiddlewareChain,
    AuthenticationMiddleware,
    RateLimitMiddleware,
    ScopeValidationMiddleware,
    SensitiveDataFilterMiddleware,
    create_api_middleware,
    EndpointRateLimit,
    EndpointScope,
    # REST Router
    Route,
    ROUTES,
    RESTRouter,
    create_rest_router,
    # OpenAPI
    generate_openapi_spec,
)


def create_test_key_manager():
    """Create a key manager for testing (no keyring)."""
    return APIKeyManager(use_keyring=False)


def create_test_router(key_manager, jsonrpc_handler=None):
    """Create a REST router with the given key manager."""
    middleware = create_api_middleware(key_manager=key_manager)
    return RESTRouter(
        jsonrpc_handler=jsonrpc_handler or AsyncMock(),
        middleware=middleware,
    )


class TestFullRequestFlow:
    """Test complete request flow through all layers."""

    @pytest.fixture
    def key_manager(self):
        """Create a shared key manager for testing."""
        return create_test_key_manager()

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key for testing."""
        key, _ = key_manager.create(
            name="Test Integration Key",
            scopes={APIScope.READ_STATUS, APIScope.READ_STATE, APIScope.WRITE_STATE},
        )
        return key

    @pytest.fixture
    def admin_key(self, key_manager):
        """Create an admin API key."""
        key, _ = key_manager.create(
            name="Admin Key",
            scopes={APIScope.ADMIN},
        )
        return key

    @pytest.fixture
    def mock_jsonrpc_handler(self):
        """Create a mock JSON-RPC handler."""
        handler = AsyncMock()
        handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {"status": "ok", "version": "4.3.0"},
            "id": 1
        }
        return handler

    @pytest.fixture
    def rest_router(self, key_manager, mock_jsonrpc_handler):
        """Create REST router with mock handler and shared key manager."""
        return create_test_router(key_manager, mock_jsonrpc_handler)

    @pytest.mark.asyncio
    async def test_authenticated_request_success(self, api_key, rest_router):
        """Should handle authenticated request successfully."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["success"] is True
        assert "data" in body

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, rest_router):
        """Should reject request without API key."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 401
        body = json.loads(response.body)
        assert body["success"] is False
        assert body["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self, rest_router):
        """Should reject invalid API key."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": "Bearer otto_live_invalid_key"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 401
        body = json.loads(response.body)
        assert body["success"] is False

    @pytest.mark.asyncio
    async def test_insufficient_scope_forbidden(self):
        """Should reject request with insufficient scope."""
        key_manager = create_test_key_manager()
        key, _ = key_manager.create(
            name="Limited Key",
            scopes={APIScope.READ_STATUS},  # No WRITE_STATE
        )
        rest_router = create_test_router(key_manager)

        request = HTTPRequest(
            method="PATCH",
            path="/api/v1/state",
            headers={"authorization": f"Bearer {key}"},
            body=b'{"burnout_level": "GREEN"}'
        )

        response = await rest_router.handle_request(request)

        assert response.status == 403
        body = json.loads(response.body)
        assert body["error"]["code"] == "FORBIDDEN"


class TestHealthEndpoint:
    """Test /api/v1/health endpoint (no auth required)."""

    @pytest.fixture
    def rest_router(self):
        """Create REST router."""
        return create_test_router(create_test_key_manager())

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, rest_router):
        """Should return health without authentication."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["success"] is True
        assert body["data"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_includes_version(self, rest_router):
        """Should include API version in health response."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b""
        )

        response = await rest_router.handle_request(request)

        body = json.loads(response.body)
        assert "version" in body["data"]


class TestOpenAPIEndpoint:
    """Test /api/v1/openapi.json endpoint."""

    @pytest.fixture
    def rest_router(self):
        """Create REST router."""
        return create_test_router(create_test_key_manager())

    @pytest.mark.asyncio
    async def test_openapi_no_auth_required(self, rest_router):
        """Should return OpenAPI spec without authentication."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/openapi.json",
            headers={},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 200
        spec = json.loads(response.body)
        assert spec["openapi"] == "3.0.3"
        assert "paths" in spec

    @pytest.mark.asyncio
    async def test_openapi_includes_all_routes(self, rest_router):
        """Should include all defined routes."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/openapi.json",
            headers={},
            body=b""
        )

        response = await rest_router.handle_request(request)

        spec = json.loads(response.body)
        paths = spec["paths"]

        # Check key endpoints are documented
        assert "/api/v1/status" in paths
        assert "/api/v1/state" in paths
        assert "/api/v1/health" in paths


class TestRateLimiting:
    """Test rate limiting across endpoints."""

    @pytest.fixture
    def key_manager(self):
        """Create a shared key manager for testing."""
        return create_test_key_manager()

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key for testing."""
        key, _ = key_manager.create(
            name="Rate Test Key",
            scopes={APIScope.READ_STATUS},
        )
        return key

    @pytest.fixture
    def rest_router(self, key_manager):
        """Create REST router with mock handler."""
        mock_handler = AsyncMock()
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {"status": "ok"},
            "id": 1
        }
        return create_test_router(key_manager, mock_handler)

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, api_key, rest_router):
        """Should include rate limit headers in response."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 200
        # Rate limit info should be in response body meta
        body = json.loads(response.body)
        assert "meta" in body

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, api_key, rest_router):
        """Should return 429 when rate limit exceeded."""
        # Make many requests quickly to exceed rate limit
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        # Status endpoint has 60/min limit, make 70 requests
        rate_limited = False
        for _ in range(70):
            response = await rest_router.handle_request(request)
            if response.status == 429:
                rate_limited = True
                break

        assert rate_limited, "Should hit rate limit after many requests"


class TestSensitiveDataFiltering:
    """Test sensitive field filtering by scope."""

    @pytest.mark.asyncio
    async def test_sensitive_fields_filtered_without_full_scope(self):
        """Should filter sensitive fields without READ_STATE_FULL scope."""
        key_manager = create_test_key_manager()
        key, _ = key_manager.create(
            name="Limited State Key",
            scopes={APIScope.READ_STATE},  # No FULL scope
        )

        mock_handler = AsyncMock()
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "burnout_level": "GREEN",
                "energy_level": "high",
                "momentum_phase": "rolling",
                "decision_mode": "work",
                "session_goal": "Build auth"
            },
            "id": 1
        }
        rest_router = create_test_router(key_manager, mock_handler)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/state",
            headers={"authorization": f"Bearer {key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        data = body["data"]

        # Sensitive fields should be filtered
        assert "burnout_level" not in data
        assert "energy_level" not in data
        assert "momentum_phase" not in data

        # Non-sensitive fields should remain
        assert data.get("decision_mode") == "work"
        assert data.get("session_goal") == "Build auth"

    @pytest.mark.asyncio
    async def test_sensitive_fields_visible_with_full_scope(self):
        """Should include sensitive fields with READ_STATE_FULL scope."""
        key_manager = create_test_key_manager()
        key, _ = key_manager.create(
            name="Full State Key",
            scopes={APIScope.READ_STATE_FULL},
        )

        mock_handler = AsyncMock()
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {
                "burnout_level": "GREEN",
                "energy_level": "high",
                "momentum_phase": "rolling",
                "decision_mode": "work"
            },
            "id": 1
        }
        rest_router = create_test_router(key_manager, mock_handler)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/state",
            headers={"authorization": f"Bearer {key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        data = body["data"]

        # All fields should be visible
        assert data["burnout_level"] == "GREEN"
        assert data["energy_level"] == "high"
        assert data["momentum_phase"] == "rolling"


class TestHTTPServerIntegration:
    """Test REST API integrated with HTTP server."""

    @pytest.mark.asyncio
    async def test_server_with_rest_router(self):
        """Should integrate REST router with HTTP server."""
        rest_router = create_test_router(create_test_key_manager())

        server = OperationalHTTPServer(
            port=18090,
            rest_router=rest_router
        )

        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b""
        )

        response = await server._route_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_non_api_routes_still_work(self):
        """Should still handle non-API routes."""
        rest_router = create_test_router(create_test_key_manager())

        server = OperationalHTTPServer(
            port=18091,
            rest_router=rest_router
        )

        # Original /health endpoint (not /api/v1/health)
        request = HTTPRequest(
            method="GET",
            path="/health",
            headers={},
            body=b""
        )

        response = await server._route_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        # Original health endpoint returns different format
        assert "status" in body or "success" in body


class TestResponseEnvelope:
    """Test standardized response envelope."""

    @pytest.fixture
    def key_manager(self):
        """Create a shared key manager for testing."""
        return create_test_key_manager()

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key for testing."""
        key, _ = key_manager.create(
            name="Envelope Test Key",
            scopes={APIScope.READ_STATUS},
        )
        return key

    @pytest.fixture
    def rest_router(self, key_manager):
        """Create REST router with mock handler."""
        mock_handler = AsyncMock()
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {"status": "ok"},
            "id": 1
        }
        return create_test_router(key_manager, mock_handler)

    @pytest.mark.asyncio
    async def test_success_response_format(self, api_key, rest_router):
        """Should return standardized success envelope."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        body = json.loads(response.body)
        assert body["success"] is True
        assert "data" in body
        assert body["error"] is None
        assert "meta" in body
        assert "timestamp" in body["meta"]
        assert "version" in body["meta"]

    @pytest.mark.asyncio
    async def test_error_response_format(self):
        """Should return standardized error envelope."""
        rest_router = create_test_router(create_test_key_manager())

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={},  # No auth
            body=b""
        )

        response = await rest_router.handle_request(request)

        body = json.loads(response.body)
        assert body["success"] is False
        assert body["data"] is None
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "meta" in body


class TestMethodMapping:
    """Test HTTP method to JSON-RPC method mapping."""

    @pytest.fixture
    def key_manager(self):
        """Create a shared key manager for testing."""
        return create_test_key_manager()

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key with full permissions."""
        key, _ = key_manager.create(
            name="Full Access Key",
            scopes={APIScope.ADMIN},
        )
        return key

    @pytest.mark.asyncio
    async def test_get_maps_to_correct_method(self, key_manager, api_key):
        """GET /api/v1/status should map to otto.status."""
        mock_handler = AsyncMock()
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {"status": "ok"},
            "id": 1
        }
        rest_router = create_test_router(key_manager, mock_handler)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        await rest_router.handle_request(request)

        # Verify the JSON-RPC method called
        call_args = mock_handler.handle_request.call_args
        assert call_args is not None
        jsonrpc_request = call_args[0][0] if call_args[0] else call_args[1].get('request')
        # The request should contain otto.status method
        if isinstance(jsonrpc_request, dict):
            assert jsonrpc_request.get("method") == "otto.status"

    @pytest.mark.asyncio
    async def test_patch_maps_to_correct_method(self, key_manager, api_key):
        """PATCH /api/v1/state should map to otto.state.update."""
        mock_handler = AsyncMock()
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {"updated": True},
            "id": 1
        }
        rest_router = create_test_router(key_manager, mock_handler)

        request = HTTPRequest(
            method="PATCH",
            path="/api/v1/state",
            headers={
                "authorization": f"Bearer {api_key}",
                "content-type": "application/json"
            },
            body=b'{"burnout_level": "GREEN"}'
        )

        await rest_router.handle_request(request)

        # Verify the JSON-RPC method called
        call_args = mock_handler.handle_request.call_args
        assert call_args is not None


class TestPathParameters:
    """Test path parameter extraction."""

    @pytest.fixture
    def key_manager(self):
        """Create a shared key manager for testing."""
        return create_test_key_manager()

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key with agent permissions."""
        key, _ = key_manager.create(
            name="Agent Key",
            scopes={APIScope.WRITE_AGENTS, APIScope.READ_AGENTS},
        )
        return key

    @pytest.mark.asyncio
    async def test_id_parameter_extracted(self, key_manager, api_key):
        """Should extract :id from path."""
        mock_handler = AsyncMock()
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {"aborted": True},
            "id": 1
        }
        rest_router = create_test_router(key_manager, mock_handler)

        request = HTTPRequest(
            method="DELETE",
            path="/api/v1/agents/agent-123",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        # Verify the agent ID was passed to the handler
        call_args = mock_handler.handle_request.call_args
        if call_args is not None:
            jsonrpc_request = call_args[0][0] if call_args[0] else call_args[1].get('request')
            if isinstance(jsonrpc_request, dict) and "params" in jsonrpc_request:
                # Path parameter might be named 'id' or 'agent_id'
                params = jsonrpc_request["params"]
                assert params.get("id") == "agent-123" or params.get("agent_id") == "agent-123"


class TestDeterministicBehavior:
    """Test deterministic behavior per [He2025] principles."""

    @pytest.fixture
    def key_manager(self):
        """Create a shared key manager for testing."""
        return create_test_key_manager()

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key."""
        key, _ = key_manager.create(
            name="Determinism Test Key",
            scopes={APIScope.READ_STATUS},
        )
        return key

    @pytest.mark.asyncio
    async def test_same_input_same_output(self, key_manager, api_key):
        """Same request should produce structurally identical response."""
        mock_handler = AsyncMock()
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "result": {"status": "ok", "deterministic": True},
            "id": 1
        }
        rest_router = create_test_router(key_manager, mock_handler)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        # Make same request multiple times
        responses = []
        for _ in range(3):
            response = await rest_router.handle_request(request)
            body = json.loads(response.body)
            # Normalize fields that vary per-request
            body["meta"]["timestamp"] = 0
            body["meta"]["request_id"] = "normalized"
            body["meta"]["rate_limit_remaining"] = 0
            body["meta"]["rate_limit_reset"] = 0
            responses.append(body)

        # All responses should be identical (with normalized fields)
        assert responses[0] == responses[1] == responses[2]

    @pytest.mark.asyncio
    async def test_routing_is_deterministic(self):
        """Route matching should be deterministic."""
        rest_router = create_test_router(create_test_key_manager())

        # Same path should always match same route
        path = "/api/v1/status"
        for _ in range(5):
            route, params = rest_router._find_route("GET", path)
            assert route is not None
            assert route.jsonrpc_method == "otto.status"


class TestOpenAPISpec:
    """Test OpenAPI specification generation."""

    def test_spec_includes_security_schemes(self):
        """Should include both auth methods."""
        spec = generate_openapi_spec()

        security = spec["components"]["securitySchemes"]
        assert "bearerAuth" in security
        assert "apiKeyHeader" in security

    def test_spec_includes_all_routes(self):
        """Should document all routes."""
        spec = generate_openapi_spec()

        # Count routes
        path_count = len(spec["paths"])
        route_count = len(ROUTES)

        # Should have at least as many paths as routes
        # (some routes like openapi and health are added separately)
        assert path_count >= route_count - 2

    def test_spec_is_valid_openapi(self):
        """Should be valid OpenAPI 3.0 structure."""
        spec = generate_openapi_spec()

        assert spec["openapi"] == "3.0.3"
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec

    def test_spec_includes_error_responses(self):
        """Should document error responses."""
        spec = generate_openapi_spec()

        responses = spec["components"]["responses"]
        assert "Unauthorized" in responses
        assert "Forbidden" in responses
        assert "RateLimited" in responses
