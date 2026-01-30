"""
True End-to-End Tests for OTTO Public REST API.

Unlike other test files that call methods directly, these tests:
1. Start an ACTUAL HTTP server on a real port
2. Make REAL HTTP requests over the network
3. Verify the COMPLETE stack from TCP to response

ThinkingMachines [He2025] Compliance:
- Tests verify batch invariance under real network conditions
- Same request → same response regardless of network timing
- Fixed behavior across sequential and concurrent HTTP requests

Prerequisites:
- httpx library (pip install httpx)
"""

import asyncio
import json
import pytest
import socket
from contextlib import closing
from typing import AsyncGenerator, Tuple

import httpx

from otto.http_server import OperationalHTTPServer, start_server, stop_server
from otto.api import (
    APIScope,
    APIKeyManager,
    create_api_middleware,
    RESTRouter,
)
from otto.api.rest_router import create_rest_router
from otto.protocol.layer1_jsonrpc import JSONRPCHandler


# =============================================================================
# Utilities
# =============================================================================

def find_free_port() -> int:
    """Find an available port for testing."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def key_manager():
    """Create API key manager for testing."""
    return APIKeyManager(use_keyring=False)


@pytest.fixture
def api_key(key_manager):
    """Create a valid API key with admin permissions."""
    key, _ = key_manager.create(
        name="E2E Test Key",
        scopes={APIScope.ADMIN},
    )
    return key


@pytest.fixture
def read_only_key(key_manager):
    """Create a read-only API key."""
    key, _ = key_manager.create(
        name="Read Only Key",
        scopes={APIScope.READ_STATUS},
    )
    return key


@pytest.fixture
async def server_with_api(key_manager) -> AsyncGenerator[Tuple[OperationalHTTPServer, int], None]:
    """
    Start a real HTTP server with REST API on a random port.

    Yields (server, port) tuple.
    """
    port = find_free_port()

    # Create real REST router with real JSON-RPC handler
    jsonrpc_handler = JSONRPCHandler()
    middleware = create_api_middleware(key_manager=key_manager)
    rest_router = RESTRouter(
        jsonrpc_handler=jsonrpc_handler,
        middleware=middleware,
    )

    server = await start_server(
        port=port,
        host='127.0.0.1',
        rest_router=rest_router,
    )

    # Give server a moment to fully start
    await asyncio.sleep(0.05)

    try:
        yield server, port
    finally:
        await stop_server(server)


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for testing."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


# =============================================================================
# Basic Connectivity Tests
# =============================================================================

class TestServerConnectivity:
    """Test basic server connectivity and health endpoints."""

    @pytest.mark.asyncio
    async def test_server_starts_and_responds(self, server_with_api, client):
        """Server should start and respond to requests."""
        server, port = server_with_api

        response = await client.get(f"http://127.0.0.1:{port}/health")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_legacy_endpoints_work(self, server_with_api, client):
        """Legacy endpoints (/health, /live, /ready) should work."""
        server, port = server_with_api
        base_url = f"http://127.0.0.1:{port}"

        # Test all legacy endpoints
        endpoints = ["/health", "/live", "/ready"]
        for endpoint in endpoints:
            response = await client.get(f"{base_url}{endpoint}")
            assert response.status_code == 200, f"Failed: {endpoint}"

    @pytest.mark.asyncio
    async def test_api_v1_health_no_auth(self, server_with_api, client):
        """API health endpoint should work without auth."""
        server, port = server_with_api

        response = await client.get(f"http://127.0.0.1:{port}/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_api_v1_openapi_no_auth(self, server_with_api, client):
        """OpenAPI spec should be accessible without auth."""
        server, port = server_with_api

        response = await client.get(f"http://127.0.0.1:{port}/api/v1/openapi.json")

        assert response.status_code == 200
        body = response.json()
        assert "openapi" in body
        assert body["openapi"].startswith("3.")


# =============================================================================
# Authentication Tests (Real HTTP)
# =============================================================================

class TestRealHTTPAuthentication:
    """Test authentication over real HTTP connections."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_requires_auth(self, server_with_api, client):
        """Protected endpoints should require authentication."""
        server, port = server_with_api

        response = await client.get(f"http://127.0.0.1:{port}/api/v1/status")

        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert "error" in body

    @pytest.mark.asyncio
    async def test_valid_bearer_token_works(self, server_with_api, client, api_key):
        """Valid Bearer token should authenticate successfully."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/status",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_rejected(self, server_with_api, client):
        """Invalid Bearer token should be rejected."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/status",
            headers={"Authorization": "Bearer otto_live_invalid_00000000"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_auth_header_rejected(self, server_with_api, client):
        """Malformed Authorization header should be rejected."""
        server, port = server_with_api

        # Missing "Bearer" prefix
        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/status",
            headers={"Authorization": "otto_live_abc123_xyz"}
        )

        assert response.status_code == 401


# =============================================================================
# API Endpoint Tests (Real HTTP)
# =============================================================================

class TestRealHTTPEndpoints:
    """Test API endpoints over real HTTP connections."""

    @pytest.mark.asyncio
    async def test_ping_endpoint(self, server_with_api, client, api_key):
        """GET /api/v1/ping should return pong."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/ping",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data == "pong" or (isinstance(data, dict) and data.get("pong") is True)

    @pytest.mark.asyncio
    async def test_status_endpoint(self, server_with_api, client, api_key):
        """GET /api/v1/status should return status info."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/status",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert "data" in body

    @pytest.mark.asyncio
    async def test_methods_endpoint(self, server_with_api, client, api_key):
        """GET /api/v1/methods should return method list."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/methods",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        # Methods may be list or dict
        data = body["data"]
        if isinstance(data, list):
            methods = data
        else:
            methods = data.get("methods", data)

        assert "otto.ping" in methods

    @pytest.mark.asyncio
    async def test_404_for_unknown_endpoint(self, server_with_api, client, api_key):
        """Unknown API endpoint should return 404."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/nonexistent",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_405_for_wrong_method(self, server_with_api, client, api_key):
        """Wrong HTTP method should return 405."""
        server, port = server_with_api

        # POST to a GET-only endpoint
        response = await client.post(
            f"http://127.0.0.1:{port}/api/v1/ping",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 405


# =============================================================================
# Response Format Tests
# =============================================================================

class TestResponseFormat:
    """Test response format over real HTTP connections."""

    @pytest.mark.asyncio
    async def test_response_has_correct_content_type(self, server_with_api, client, api_key):
        """Response should have application/json content type."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/status",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    @pytest.mark.asyncio
    async def test_response_envelope_structure(self, server_with_api, client, api_key):
        """Response should have standard envelope structure."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/status",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        body = response.json()

        # Required envelope fields
        assert "success" in body
        assert "data" in body or "error" in body
        assert "meta" in body

        # Meta fields
        meta = body["meta"]
        assert "timestamp" in meta
        assert "version" in meta
        assert "request_id" in meta

    @pytest.mark.asyncio
    async def test_error_response_structure(self, server_with_api, client):
        """Error response should have correct structure."""
        server, port = server_with_api

        # No auth - should fail
        response = await client.get(f"http://127.0.0.1:{port}/api/v1/status")

        body = response.json()

        assert body["success"] is False
        assert "error" in body
        error = body["error"]
        assert "code" in error
        assert "message" in error


# =============================================================================
# Determinism Tests [He2025] - Real Network
# =============================================================================

class TestNetworkDeterminism:
    """
    Test determinism under real network conditions.

    [He2025] Batch Invariance: Same input → same output regardless of
    network timing, connection reuse, or concurrent requests.
    """

    def normalize_response(self, body: dict) -> dict:
        """Normalize response for comparison (remove expected variance)."""
        normalized = json.loads(json.dumps(body))
        if "meta" in normalized:
            for field in ["timestamp", "request_id", "rate_limit_remaining", "rate_limit_reset"]:
                if field in normalized["meta"]:
                    normalized["meta"][field] = "NORMALIZED"
        if "data" in normalized and isinstance(normalized["data"], dict):
            if "timestamp" in normalized["data"]:
                normalized["data"]["timestamp"] = "NORMALIZED"
        return normalized

    @pytest.mark.asyncio
    async def test_sequential_requests_deterministic(self, server_with_api, client, api_key):
        """
        Sequential requests should produce identical responses.

        [He2025]: Fixed evaluation order ensures reproducibility.
        """
        server, port = server_with_api
        url = f"http://127.0.0.1:{port}/api/v1/status"
        headers = {"Authorization": f"Bearer {api_key}"}

        responses = []
        for _ in range(5):
            response = await client.get(url, headers=headers)
            body = response.json()
            normalized = self.normalize_response(body)
            responses.append(normalized)

        # All should be identical
        first = responses[0]
        for i, resp in enumerate(responses[1:], 1):
            assert resp == first, f"Response {i} differs from first"

    @pytest.mark.asyncio
    async def test_concurrent_requests_deterministic(self, server_with_api, client, api_key):
        """
        Concurrent requests should produce same results as sequential.

        [He2025] Batch Invariance: Results should not depend on concurrent load.
        """
        server, port = server_with_api
        url = f"http://127.0.0.1:{port}/api/v1/ping"
        headers = {"Authorization": f"Bearer {api_key}"}

        # Sequential baseline
        sequential_response = await client.get(url, headers=headers)
        sequential = self.normalize_response(sequential_response.json())

        # Concurrent requests
        async def make_request():
            response = await client.get(url, headers=headers)
            return self.normalize_response(response.json())

        concurrent_results = await asyncio.gather(
            make_request(),
            make_request(),
            make_request(),
            make_request(),
            make_request(),
        )

        # All should match sequential baseline
        for result in concurrent_results:
            assert result == sequential

    @pytest.mark.asyncio
    async def test_different_batch_sizes_same_result(self, server_with_api, api_key):
        """
        Different batch sizes should not affect individual results.

        [He2025]: Batch size should not affect output.
        """
        server, port = server_with_api
        url = f"http://127.0.0.1:{port}/api/v1/health"

        async def make_batch(size: int) -> list:
            async with httpx.AsyncClient(timeout=10.0) as client:
                tasks = [client.get(url) for _ in range(size)]
                results = await asyncio.gather(*tasks)
                return [self.normalize_response(r.json()) for r in results]

        # Different batch sizes
        batch_1 = await make_batch(1)
        batch_5 = await make_batch(5)
        batch_10 = await make_batch(10)

        # All should be identical
        reference = batch_1[0]
        for result in batch_1 + batch_5 + batch_10:
            assert result == reference

    @pytest.mark.asyncio
    async def test_new_connections_same_result(self, server_with_api, api_key):
        """
        Fresh connections should produce same results as reused connections.

        [He2025]: Connection state should not affect output.
        """
        server, port = server_with_api
        url = f"http://127.0.0.1:{port}/api/v1/health"

        results = []

        # Each request with a NEW client (new connection)
        for _ in range(3):
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                results.append(self.normalize_response(response.json()))

        # Compare all
        first = results[0]
        for result in results[1:]:
            assert result == first


# =============================================================================
# Scope Enforcement Tests (Real HTTP)
# =============================================================================

class TestScopeEnforcement:
    """Test scope enforcement over real HTTP connections."""

    @pytest.mark.asyncio
    async def test_read_only_key_can_read(self, server_with_api, client, read_only_key):
        """Read-only key should access read endpoints."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/status",
            headers={"Authorization": f"Bearer {read_only_key}"}
        )

        assert response.status_code == 200


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling over real HTTP connections."""

    @pytest.mark.asyncio
    async def test_malformed_json_body_handled(self, server_with_api, client, api_key):
        """Malformed JSON body should be handled gracefully (not crash server)."""
        server, port = server_with_api

        # Send malformed JSON to an endpoint
        response = await client.post(
            f"http://127.0.0.1:{port}/api/v1/sessions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            content=b"{ invalid json"
        )

        # Server should not crash - response should be valid HTTP
        # (actual status code depends on endpoint design)
        assert response.status_code in [200, 400, 500]
        # Server should still be responsive after
        health_response = await client.get(f"http://127.0.0.1:{port}/api/v1/health")
        assert health_response.status_code == 200

    @pytest.mark.asyncio
    async def test_server_handles_empty_body(self, server_with_api, client, api_key):
        """Server should handle empty body gracefully."""
        server, port = server_with_api

        response = await client.get(
            f"http://127.0.0.1:{port}/api/v1/ping",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        assert response.status_code == 200


# =============================================================================
# Connection Handling Tests
# =============================================================================

class TestConnectionHandling:
    """Test HTTP connection handling."""

    @pytest.mark.asyncio
    async def test_multiple_requests_same_connection(self, server_with_api, api_key):
        """Multiple requests on same connection should work."""
        server, port = server_with_api

        async with httpx.AsyncClient(timeout=10.0) as client:
            for _ in range(10):
                response = await client.get(
                    f"http://127.0.0.1:{port}/api/v1/health"
                )
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_server_survives_client_disconnect(self, server_with_api, api_key):
        """Server should survive client disconnection."""
        server, port = server_with_api

        # First client connects and disconnects
        async with httpx.AsyncClient(timeout=10.0) as client1:
            response1 = await client1.get(f"http://127.0.0.1:{port}/api/v1/health")
            assert response1.status_code == 200

        # Client1 is now disconnected
        # New client should still work
        async with httpx.AsyncClient(timeout=10.0) as client2:
            response2 = await client2.get(f"http://127.0.0.1:{port}/api/v1/health")
            assert response2.status_code == 200


# =============================================================================
# Load Test (Lightweight)
# =============================================================================

class TestLightweightLoad:
    """Lightweight load tests to verify stability."""

    @pytest.mark.asyncio
    async def test_handles_rapid_requests(self, server_with_api, client, api_key):
        """Server should handle rapid sequential requests."""
        server, port = server_with_api
        url = f"http://127.0.0.1:{port}/api/v1/health"

        # 50 rapid requests
        for _ in range(50):
            response = await client.get(url)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_handles_concurrent_burst(self, server_with_api, api_key):
        """Server should handle concurrent request burst."""
        server, port = server_with_api
        url = f"http://127.0.0.1:{port}/api/v1/health"

        async def make_request(client):
            return await client.get(url)

        async with httpx.AsyncClient(timeout=10.0) as client:
            # 20 concurrent requests
            tasks = [make_request(client) for _ in range(20)]
            results = await asyncio.gather(*tasks)

            # All should succeed
            for result in results:
                assert result.status_code == 200
