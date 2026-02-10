"""
Real Integration Tests for OTTO Public REST API.

Unlike test_api_integration.py which uses mocks, these tests use the ACTUAL
JSON-RPC handler to verify end-to-end behavior.

Determinism:
- Tests verify batch-invariant behavior
- Same input → same output regardless of execution context
- Fixed evaluation order throughout the stack
"""

import asyncio
import json
import pytest
from typing import Dict, Any

from otto.http_server import (
    HTTPRequest,
    HTTPResponse,
    OperationalHTTPServer,
)
from otto.api import (
    APIScope,
    APIKeyManager,
    create_api_middleware,
)
from otto.api.rest_router import RESTRouter
from otto.protocol.layer1_jsonrpc import JSONRPCHandler


def create_real_router(key_manager: APIKeyManager) -> RESTRouter:
    """Create REST router with REAL JSON-RPC handler."""
    jsonrpc_handler = JSONRPCHandler()
    middleware = create_api_middleware(key_manager=key_manager)
    return RESTRouter(
        jsonrpc_handler=jsonrpc_handler,
        middleware=middleware,
    )


class TestRealJSONRPCIntegration:
    """Test REST API with real JSON-RPC handler."""

    @pytest.fixture
    def key_manager(self):
        """Create a key manager for testing."""
        return APIKeyManager(use_keyring=False)

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key with full permissions."""
        key, _ = key_manager.create(
            name="Real Integration Test Key",
            scopes={APIScope.ADMIN},
        )
        return key

    @pytest.fixture
    def rest_router(self, key_manager):
        """Create REST router with real JSON-RPC handler."""
        return create_real_router(key_manager)

    @pytest.mark.asyncio
    async def test_ping_real(self, api_key, rest_router):
        """Test otto.ping through REST API."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/ping",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["success"] is True
        # Ping returns "pong" string or {pong: true}
        data = body["data"]
        assert data == "pong" or (isinstance(data, dict) and data.get("pong") is True)

    @pytest.mark.asyncio
    async def test_status_real(self, api_key, rest_router):
        """Test otto.status through REST API."""
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
        # Status should have version info
        assert "version" in body["data"] or "status" in body["data"]

    @pytest.mark.asyncio
    async def test_methods_real(self, api_key, rest_router):
        """Test otto.methods through REST API."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/methods",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["success"] is True
        # Methods may be returned as list directly or as {"methods": [...]}
        data = body["data"]
        if isinstance(data, list):
            methods = data
        else:
            methods = data.get("methods", data)
        assert "otto.ping" in methods
        assert "otto.status" in methods

    @pytest.mark.asyncio
    async def test_agents_list_real(self, api_key, rest_router):
        """Test otto.agent.list through REST API."""
        request = HTTPRequest(
            method="GET",
            path="/api/v1/agents",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        response = await rest_router.handle_request(request)

        # Agent list may return 400 if agent bridge not configured
        # or 200 with agents list if configured
        body = json.loads(response.body)
        if response.status == 400:
            # Expected if agent bridge not configured
            assert body["error"]["code"] == "AGENT_ERROR"
        else:
            assert response.status == 200
            assert body["success"] is True
            # Should return agents list (may be empty)
            data = body["data"]
            if isinstance(data, dict):
                assert "agents" in data
                assert isinstance(data["agents"], list)
            else:
                # Might be list directly
                assert isinstance(data, list)


class TestDeterminismHe2025:
    """
    Test determinism principles.

    Key principle: Batch invariance - same input produces same output
    regardless of concurrent load or execution context.
    """

    @pytest.fixture
    def key_manager(self):
        """Create a key manager for testing."""
        return APIKeyManager(use_keyring=False)

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key."""
        key, _ = key_manager.create(
            name="Determinism Test Key",
            scopes={APIScope.READ_STATUS},
        )
        return key

    @pytest.fixture
    def rest_router(self, key_manager):
        """Create REST router with real handler."""
        return create_real_router(key_manager)

    def normalize_response(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize response for determinism comparison.

       , we expect structural determinism - the response
        structure and non-random data should be identical.

        Fields that are expected to vary:
        - timestamp (time of request) - in meta AND data
        - request_id (unique per request)
        - rate_limit_remaining (decrements per request)
        - rate_limit_reset (time-based)
        """
        normalized = json.loads(json.dumps(body))  # Deep copy
        if "meta" in normalized:
            normalized["meta"]["timestamp"] = "NORMALIZED"
            normalized["meta"]["request_id"] = "NORMALIZED"
            if "rate_limit_remaining" in normalized["meta"]:
                normalized["meta"]["rate_limit_remaining"] = "NORMALIZED"
            if "rate_limit_reset" in normalized["meta"]:
                normalized["meta"]["rate_limit_reset"] = "NORMALIZED"
        # Also normalize timestamp in data payload if present
        if "data" in normalized and isinstance(normalized["data"], dict):
            if "timestamp" in normalized["data"]:
                normalized["data"]["timestamp"] = "NORMALIZED"
        return normalized

    @pytest.mark.asyncio
    async def test_deterministic_routing(self, key_manager, api_key, rest_router):
        """
        Verify routing is deterministic.

        Principle: Fixed evaluation order ensures reproducibility.
        """
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        # Make 10 identical requests
        responses = []
        for _ in range(10):
            response = await rest_router.handle_request(request)
            body = json.loads(response.body)
            normalized = self.normalize_response(body)
            responses.append(normalized)

        # All normalized responses should be identical
        first = responses[0]
        for i, resp in enumerate(responses[1:], 1):
            assert resp == first, f"Response {i} differs from first response"

    @pytest.mark.asyncio
    async def test_deterministic_error_handling(self, rest_router):
        """
        Verify error responses are deterministic.

        Same invalid input should produce identical error response.
        """
        request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={},  # No auth - should fail
            body=b""
        )

        responses = []
        for _ in range(5):
            response = await rest_router.handle_request(request)
            body = json.loads(response.body)
            normalized = self.normalize_response(body)
            responses.append(normalized)

        first = responses[0]
        for resp in responses[1:]:
            assert resp == first

    @pytest.mark.asyncio
    async def test_route_resolution_order(self, rest_router):
        """
        Verify routes are evaluated in fixed order.

        requires fixed evaluation order for determinism.
        """
        from otto.api.rest_router import ROUTES

        # Routes should be in deterministic order
        route_order = [(r.method, r.path_pattern) for r in ROUTES]

        # Verify order is consistent across multiple accesses
        for _ in range(5):
            current_order = [(r.method, r.path_pattern) for r in ROUTES]
            assert current_order == route_order

    @pytest.mark.asyncio
    async def test_middleware_chain_order(self, key_manager):
        """
        Verify middleware executes in fixed order.

        requires fixed evaluation order.
        """
        from otto.api.middleware import create_api_middleware

        # Create multiple middleware chains
        chains = [create_api_middleware(key_manager=key_manager) for _ in range(3)]

        # Get first chain's order as reference
        first_chain_types = [type(m).__name__ for m in chains[0]._middleware]

        # All chains should have same order
        for chain in chains[1:]:
            middleware_types = [type(m).__name__ for m in chain._middleware]
            assert middleware_types == first_chain_types, \
                f"Middleware order not consistent: {middleware_types} != {first_chain_types}"

        # Verify the chain has expected middleware (order matters)
        # Order: SecurityHeaders -> Auth -> RateLimit -> Scope
        assert len(first_chain_types) >= 4, "Should have at least 4 middleware"
        # SecurityHeaders should be first (for response wrapping)
        assert "Security" in first_chain_types[0], "SecurityHeaders should be first"
        # Auth should come second, before rate limiting
        assert "Auth" in first_chain_types[1], "Auth should be second"


class TestConcurrentRequests:
    """
    Test behavior under concurrent load.

   , batch invariance means results should not depend
    on how many other requests are being processed.
    """

    @pytest.fixture
    def key_manager(self):
        """Create a key manager for testing."""
        return APIKeyManager(use_keyring=False)

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key."""
        key, _ = key_manager.create(
            name="Concurrent Test Key",
            scopes={APIScope.READ_STATUS},
        )
        return key

    @pytest.fixture
    def rest_router(self, key_manager):
        """Create REST router with real handler."""
        return create_real_router(key_manager)

    def normalize_response(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize response for comparison."""
        normalized = json.loads(json.dumps(body))
        if "meta" in normalized:
            normalized["meta"]["timestamp"] = "NORMALIZED"
            normalized["meta"]["request_id"] = "NORMALIZED"
            if "rate_limit_remaining" in normalized["meta"]:
                normalized["meta"]["rate_limit_remaining"] = "NORMALIZED"
            if "rate_limit_reset" in normalized["meta"]:
                normalized["meta"]["rate_limit_reset"] = "NORMALIZED"
        # Also normalize timestamp in data payload if present
        if "data" in normalized and isinstance(normalized["data"], dict):
            if "timestamp" in normalized["data"]:
                normalized["data"]["timestamp"] = "NORMALIZED"
        return normalized

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_result(self, api_key, rest_router):
        """
        Concurrent requests should produce same result as sequential.

        batch invariance: result should not depend on concurrent load.
        """
        request = HTTPRequest(
            method="GET",
            path="/api/v1/ping",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        # Sequential requests
        sequential_responses = []
        for _ in range(3):
            resp = await rest_router.handle_request(request)
            body = json.loads(resp.body)
            sequential_responses.append(self.normalize_response(body))

        # Concurrent requests
        tasks = [rest_router.handle_request(request) for _ in range(3)]
        concurrent_results = await asyncio.gather(*tasks)
        concurrent_responses = [
            self.normalize_response(json.loads(r.body))
            for r in concurrent_results
        ]

        # All should be structurally identical
        expected = sequential_responses[0]
        for resp in sequential_responses[1:] + concurrent_responses:
            assert resp == expected

    @pytest.mark.asyncio
    async def test_different_endpoints_concurrent(self, api_key, rest_router):
        """
        Different endpoints running concurrently should not interfere.
        """
        ping_request = HTTPRequest(
            method="GET",
            path="/api/v1/ping",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )
        status_request = HTTPRequest(
            method="GET",
            path="/api/v1/status",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )
        methods_request = HTTPRequest(
            method="GET",
            path="/api/v1/methods",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        # Run all concurrently
        tasks = [
            rest_router.handle_request(ping_request),
            rest_router.handle_request(status_request),
            rest_router.handle_request(methods_request),
        ]
        results = await asyncio.gather(*tasks)

        # Each should succeed
        for resp in results:
            assert resp.status == 200
            body = json.loads(resp.body)
            assert body["success"] is True


class TestHTTPServerRealIntegration:
    """Test full HTTP server integration with real handler."""

    @pytest.fixture
    def key_manager(self):
        """Create a key manager for testing."""
        return APIKeyManager(use_keyring=False)

    @pytest.fixture
    def api_key(self, key_manager):
        """Create a valid API key."""
        key, _ = key_manager.create(
            name="Server Test Key",
            scopes={APIScope.ADMIN},
        )
        return key

    @pytest.mark.asyncio
    async def test_server_with_real_handler(self, key_manager, api_key):
        """Test full stack: HTTP Server + REST Router + JSON-RPC Handler."""
        rest_router = create_real_router(key_manager)
        server = OperationalHTTPServer(
            port=18892,
            rest_router=rest_router
        )

        # Test through server's route method
        request = HTTPRequest(
            method="GET",
            path="/api/v1/ping",
            headers={"authorization": f"Bearer {api_key}"},
            body=b""
        )

        response = await server._route_request(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["success"] is True
        # Ping returns "pong" string or {pong: true}
        data = body["data"]
        assert data == "pong" or (isinstance(data, dict) and data.get("pong") is True)

    @pytest.mark.asyncio
    async def test_api_and_legacy_endpoints_coexist(self, key_manager, api_key):
        """
        Both /api/v1/* and legacy endpoints should work.

        fixed evaluation order: API routes checked first,
        then fall back to legacy routes.
        """
        rest_router = create_real_router(key_manager)
        server = OperationalHTTPServer(
            port=18893,
            rest_router=rest_router
        )

        # Test API endpoint
        api_request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b""
        )
        api_response = await server._route_request(api_request)
        assert api_response.status == 200
        api_body = json.loads(api_response.body)
        assert api_body["success"] is True

        # Test legacy endpoint
        legacy_request = HTTPRequest(
            method="GET",
            path="/health",
            headers={},
            body=b""
        )
        legacy_response = await server._route_request(legacy_request)
        assert legacy_response.status == 200
        legacy_body = json.loads(legacy_response.body)
        # Legacy endpoint has different format
        assert "status" in legacy_body or "healthy" in str(legacy_body)
