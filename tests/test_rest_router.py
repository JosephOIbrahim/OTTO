"""
Tests for OTTO Public REST API - Phase 3 REST Router
=====================================================

Tests for:
- Route matching and path parameters
- REST to JSON-RPC mapping
- Response formatting
- Error handling
- OpenAPI spec generation
"""

import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch

from otto.http_server import HTTPRequest, HTTPResponse
from otto.protocol.layer1_jsonrpc import JSONRPCHandler
from otto.api.scopes import APIScope
from otto.api.api_keys import APIKeyManager
from otto.api.rest_router import (
    Route,
    ROUTES,
    RESTRouter,
    create_rest_router,
)
from otto.api.openapi import generate_openapi_spec


# =============================================================================
# Route Tests
# =============================================================================

class TestRoute:
    """Tests for Route class."""

    def test_route_simple_match(self):
        """Route should match simple paths."""
        route = Route("GET", "/api/v1/status", "otto.status", APIScope.READ_STATUS)
        match = route.match("/api/v1/status")
        assert match == {}

    def test_route_no_match(self):
        """Route should return None for non-matching paths."""
        route = Route("GET", "/api/v1/status", "otto.status", APIScope.READ_STATUS)
        match = route.match("/api/v1/other")
        assert match is None

    def test_route_with_parameter(self):
        """Route should extract path parameters."""
        route = Route("DELETE", "/api/v1/agents/:id", "otto.agent.abort", APIScope.WRITE_AGENTS)
        match = route.match("/api/v1/agents/abc12345")
        assert match == {"id": "abc12345"}

    def test_route_parameter_no_match(self):
        """Route should not match if parameter position is wrong."""
        route = Route("DELETE", "/api/v1/agents/:id", "otto.agent.abort", APIScope.WRITE_AGENTS)
        match = route.match("/api/v1/agents")
        assert match is None

    def test_route_multiple_parameters(self):
        """Route should handle multiple parameters."""
        route = Route("GET", "/api/v1/:resource/:id", "otto.get", APIScope.READ_STATUS)
        match = route.match("/api/v1/agents/abc123")
        assert match == {"resource": "agents", "id": "abc123"}


class TestRoutes:
    """Tests for route registry."""

    def test_routes_not_empty(self):
        """ROUTES should have routes defined."""
        assert len(ROUTES) > 0

    def test_routes_cover_status(self):
        """Should have status routes."""
        methods = [r.jsonrpc_method for r in ROUTES]
        assert "otto.status" in methods
        assert "otto.ping" in methods
        assert "otto.methods" in methods

    def test_routes_cover_state(self):
        """Should have state routes."""
        methods = [r.jsonrpc_method for r in ROUTES]
        assert "otto.state.get" in methods
        assert "otto.state.update" in methods

    def test_routes_cover_agents(self):
        """Should have agent routes."""
        methods = [r.jsonrpc_method for r in ROUTES]
        assert "otto.agent.list" in methods
        assert "otto.agent.spawn" in methods
        assert "otto.agent.abort" in methods

    def test_routes_have_rate_limits(self):
        """All routes should have rate limits."""
        for route in ROUTES:
            assert route.rate_limit > 0

    def test_routes_have_scopes(self):
        """All routes should have required scopes."""
        for route in ROUTES:
            assert isinstance(route.required_scope, APIScope)


# =============================================================================
# REST Router Tests
# =============================================================================

class TestRESTRouter:
    """Tests for REST router."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock JSON-RPC handler."""
        handler = MagicMock(spec=JSONRPCHandler)
        handler.handle_request = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "result": {"status": "ok"},
            "id": "test",
        })
        return handler

    @pytest.fixture
    def router(self, mock_handler, tmp_path):
        """Create a router with mocked dependencies."""
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS, APIScope.READ_STATE, APIScope.READ_AGENTS},
        )
        return RESTRouter(
            jsonrpc_handler=mock_handler,
        ), manager, full_key

    @pytest.mark.asyncio
    async def test_health_endpoint(self, router):
        """Health endpoint should work without auth."""
        router_obj, _, _ = router
        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b"",
        )
        response = await router_obj.handle_request(request)
        assert response.status == 200
        data = json.loads(response.body)
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_options_returns_allowed_methods(self, router):
        """OPTIONS should return allowed methods."""
        router_obj, _, _ = router
        request = HTTPRequest(
            method="OPTIONS",
            path="/api/v1/status",
            headers={},
            body=b"",
        )
        response = await router_obj.handle_request(request)
        assert response.status == 204
        assert "Allow" in response.headers
        assert "GET" in response.headers["Allow"]

    @pytest.mark.asyncio
    async def test_cors_headers(self, router):
        """Responses should include CORS headers."""
        router_obj, _, _ = router
        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b"",
        )
        response = await router_obj.handle_request(request)
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    @pytest.mark.asyncio
    async def test_not_found_for_unknown_path(self, router):
        """Unknown path should return 404."""
        router_obj, manager, key = router
        request = HTTPRequest(
            method="GET",
            path="/api/v1/unknown",
            headers={"authorization": f"Bearer {key}"},
            body=b"",
        )

        # Need to use the router's own middleware with the right key manager
        from otto.api.middleware import create_api_middleware
        router_obj._middleware = create_api_middleware(key_manager=manager)

        response = await router_obj.handle_request(request)
        assert response.status == 404
        data = json.loads(response.body)
        assert data["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, router):
        """Wrong method should return 405."""
        router_obj, manager, key = router
        request = HTTPRequest(
            method="DELETE",  # status only supports GET
            path="/api/v1/status",
            headers={"authorization": f"Bearer {key}"},
            body=b"",
        )

        from otto.api.middleware import create_api_middleware
        router_obj._middleware = create_api_middleware(key_manager=manager)

        response = await router_obj.handle_request(request)
        assert response.status == 405
        assert "Allow" in response.headers

    @pytest.mark.asyncio
    async def test_unauthorized_without_key(self, router):
        """Request without API key should return 401."""
        router_obj, _, _ = router
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={},
            body=b"",
        )
        response = await router_obj.handle_request(request)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_successful_jsonrpc_call(self, router, mock_handler):
        """Successful request should call JSON-RPC handler."""
        router_obj, manager, key = router

        from otto.api.middleware import create_api_middleware
        router_obj._middleware = create_api_middleware(key_manager=manager)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {key}"},
            body=b"",
        )
        response = await router_obj.handle_request(request)

        assert response.status == 200
        mock_handler.handle_request.assert_called_once()

        # Verify JSON-RPC request format
        call_args = mock_handler.handle_request.call_args[0][0]
        assert call_args["jsonrpc"] == "2.0"
        assert call_args["method"] == "otto.status"

    @pytest.mark.asyncio
    async def test_path_params_passed_to_handler(self, router, mock_handler):
        """Path parameters should be passed to JSON-RPC handler."""
        router_obj, manager, _ = router

        # Create key with write access
        full_key, _ = manager.create(
            name="Write Key",
            scopes={APIScope.WRITE_AGENTS},
        )

        from otto.api.middleware import create_api_middleware
        router_obj._middleware = create_api_middleware(key_manager=manager)

        request = HTTPRequest(
            method="DELETE",
            path="/api/v1/agents/agent123",
            headers={"authorization": f"Bearer {full_key}"},
            body=b"",
        )
        response = await router_obj.handle_request(request)

        # Verify agent_id was passed
        call_args = mock_handler.handle_request.call_args[0][0]
        assert call_args["params"]["agent_id"] == "agent123"

    @pytest.mark.asyncio
    async def test_body_params_passed_to_handler(self, router, mock_handler):
        """Body parameters should be passed to JSON-RPC handler."""
        router_obj, manager, _ = router

        # Create key with write access
        full_key, _ = manager.create(
            name="Write Key",
            scopes={APIScope.WRITE_AGENTS},
        )

        from otto.api.middleware import create_api_middleware
        router_obj._middleware = create_api_middleware(key_manager=manager)

        # Use valid schema fields: 'task' (required) and 'type' (enum)
        request = HTTPRequest(
            method="POST",
            path="/api/v1/agents",
            headers={
                "authorization": f"Bearer {full_key}",
                "content-type": "application/json",
            },
            body=b'{"task": "Test task", "type": "general"}',
        )
        response = await router_obj.handle_request(request)

        call_args = mock_handler.handle_request.call_args[0][0]
        assert call_args["params"]["task"] == "Test task"
        assert call_args["params"]["type"] == "general"

    @pytest.mark.asyncio
    async def test_jsonrpc_error_mapped_to_http(self, router, mock_handler):
        """JSON-RPC error should be mapped to HTTP error."""
        router_obj, manager, key = router

        # Mock an error response
        mock_handler.handle_request.return_value = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,  # INVALID_PARAMS
                "message": "Invalid parameters",
            },
            "id": "test",
        }

        from otto.api.middleware import create_api_middleware
        router_obj._middleware = create_api_middleware(key_manager=manager)

        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {key}"},
            body=b"",
        )
        response = await router_obj.handle_request(request)

        assert response.status == 400
        data = json.loads(response.body)
        assert data["error"]["code"] == "INVALID_PARAMS"


class TestCreateRESTRouter:
    """Tests for router factory function."""

    def test_creates_router_with_default_routes(self):
        """Factory should create router with default routes."""
        router = create_rest_router()
        assert len(router._routes) == len(ROUTES)

    def test_creates_router_with_custom_routes(self):
        """Factory should accept custom routes."""
        custom = Route("GET", "/api/v1/custom", "otto.custom", APIScope.READ_STATUS)
        router = create_rest_router(custom_routes=[custom])
        assert len(router._routes) == len(ROUTES) + 1


# =============================================================================
# OpenAPI Tests
# =============================================================================

class TestOpenAPISpec:
    """Tests for OpenAPI spec generation."""

    def test_generates_valid_spec(self):
        """Should generate valid OpenAPI 3.0 spec."""
        spec = generate_openapi_spec()
        assert spec["openapi"] == "3.0.3"
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec

    def test_spec_has_info(self):
        """Spec should have info section."""
        spec = generate_openapi_spec()
        assert spec["info"]["title"] == "OTTO OS Public REST API"
        assert "version" in spec["info"]

    def test_spec_has_security_schemes(self):
        """Spec should define security schemes."""
        spec = generate_openapi_spec()
        schemes = spec["components"]["securitySchemes"]
        assert "bearerAuth" in schemes
        assert "apiKeyHeader" in schemes

    def test_spec_has_all_routes(self):
        """Spec should include all routes."""
        spec = generate_openapi_spec()
        paths = spec["paths"]

        # Check some key endpoints
        assert "/api/v1/status" in paths
        assert "/api/v1/state" in paths
        assert "/api/v1/agents" in paths
        assert "/api/v1/health" in paths

    def test_spec_has_correct_methods(self):
        """Each path should have correct HTTP methods."""
        spec = generate_openapi_spec()

        # /status is GET only
        assert "get" in spec["paths"]["/api/v1/status"]

        # /state has GET and PATCH
        assert "get" in spec["paths"]["/api/v1/state"]
        assert "patch" in spec["paths"]["/api/v1/state"]

        # /agents has GET and POST
        assert "get" in spec["paths"]["/api/v1/agents"]
        assert "post" in spec["paths"]["/api/v1/agents"]

    def test_spec_has_path_parameters(self):
        """Parameterized paths should have parameter definitions."""
        spec = generate_openapi_spec()

        # /agents/{id} should have id parameter
        agent_delete = spec["paths"]["/api/v1/agents/{id}"]["delete"]
        assert "parameters" in agent_delete
        param_names = [p["name"] for p in agent_delete["parameters"]]
        assert "id" in param_names

    def test_spec_has_request_bodies(self):
        """POST/PATCH endpoints should have request bodies."""
        spec = generate_openapi_spec()

        # POST /agents should have request body
        agent_post = spec["paths"]["/api/v1/agents"]["post"]
        assert "requestBody" in agent_post

        # PATCH /state should have request body
        state_patch = spec["paths"]["/api/v1/state"]["patch"]
        assert "requestBody" in state_patch

    def test_spec_has_responses(self):
        """Endpoints should have response definitions."""
        spec = generate_openapi_spec()

        status_get = spec["paths"]["/api/v1/status"]["get"]
        assert "responses" in status_get
        assert "200" in status_get["responses"]
        assert "401" in status_get["responses"]
        assert "429" in status_get["responses"]

    def test_spec_has_tags(self):
        """Spec should have tag definitions."""
        spec = generate_openapi_spec()
        assert "tags" in spec
        tag_names = [t["name"] for t in spec["tags"]]
        assert "Status" in tag_names
        assert "State" in tag_names
        assert "Agents" in tag_names

    def test_spec_operations_have_tags(self):
        """Operations should have tags."""
        spec = generate_openapi_spec()

        status_get = spec["paths"]["/api/v1/status"]["get"]
        assert "tags" in status_get
        assert "Status" in status_get["tags"]

    def test_spec_public_endpoints_no_security(self):
        """Public endpoints should have empty security."""
        spec = generate_openapi_spec()

        health_get = spec["paths"]["/api/v1/health"]["get"]
        assert health_get.get("security") == []

    def test_spec_schemas_defined(self):
        """Component schemas should be defined."""
        spec = generate_openapi_spec()
        schemas = spec["components"]["schemas"]

        assert "APIResponse" in schemas
        assert "CognitiveState" in schemas
        assert "StateUpdate" in schemas
        assert "AgentSpawn" in schemas


# =============================================================================
# Integration Tests
# =============================================================================

class TestRouterIntegration:
    """Integration tests for full request flow."""

    @pytest.fixture
    def full_router(self, tmp_path):
        """Create a router with real JSON-RPC handler."""
        handler = JSONRPCHandler()
        manager = APIKeyManager(keys_dir=tmp_path, use_keyring=False)
        full_key, key = manager.create(
            name="Test Key",
            scopes={APIScope.ADMIN},
        )

        from otto.api.middleware import create_api_middleware
        router = RESTRouter(jsonrpc_handler=handler)
        router._middleware = create_api_middleware(key_manager=manager)

        return router, full_key

    @pytest.mark.asyncio
    async def test_ping_endpoint(self, full_router):
        """Ping endpoint should return pong."""
        router, key = full_router
        request = HTTPRequest(
            method="GET",
            path="/api/v1/ping",
            headers={"authorization": f"Bearer {key}"},
            body=b"",
        )
        response = await router.handle_request(request)
        assert response.status == 200
        data = json.loads(response.body)
        assert data["success"] is True
        assert data["data"] == "pong"

    @pytest.mark.asyncio
    async def test_methods_endpoint(self, full_router):
        """Methods endpoint should return available methods."""
        router, key = full_router
        request = HTTPRequest(
            method="GET",
            path="/api/v1/methods",
            headers={"authorization": f"Bearer {key}"},
            body=b"",
        )
        response = await router.handle_request(request)
        assert response.status == 200
        data = json.loads(response.body)
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert "otto.status" in data["data"]

    @pytest.mark.asyncio
    async def test_status_endpoint(self, full_router):
        """Status endpoint should return status."""
        router, key = full_router
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {key}"},
            body=b"",
        )
        response = await router.handle_request(request)
        assert response.status == 200
        data = json.loads(response.body)
        assert data["success"] is True
        assert "status" in data["data"]
