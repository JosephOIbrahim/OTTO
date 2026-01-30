"""
Tests for HTTP server module.

Tests:
- HTTP request parsing
- HTTP response formatting
- Endpoint handlers (/health, /ready, /live, /metrics)
- Route handling
- Server start/stop
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, AsyncMock

from otto.http_server import (
    HTTPRequest,
    HTTPResponse,
    OperationalHTTPServer,
    start_server,
    stop_server,
)


class TestHTTPRequest:
    """Test HTTPRequest dataclass."""

    def test_creation(self):
        """Should create request with all fields."""
        request = HTTPRequest(
            method="GET",
            path="/health",
            headers={"content-type": "application/json"},
            body=b'{"key": "value"}'
        )

        assert request.method == "GET"
        assert request.path == "/health"
        assert request.headers["content-type"] == "application/json"
        assert request.body == b'{"key": "value"}'


class TestHTTPResponse:
    """Test HTTPResponse dataclass."""

    def test_creation(self):
        """Should create response with defaults."""
        response = HTTPResponse(
            status=200,
            content_type="text/plain",
            body="OK"
        )

        assert response.status == 200
        assert response.content_type == "text/plain"
        assert response.body == "OK"
        assert response.headers == {}

    def test_to_bytes(self):
        """Should convert to HTTP bytes format."""
        response = HTTPResponse(
            status=200,
            content_type="text/plain",
            body="OK"
        )

        data = response.to_bytes()

        assert b"HTTP/1.1 200 OK" in data
        assert b"Content-Type: text/plain" in data
        assert b"Content-Length: 2" in data
        assert data.endswith(b"OK")

    def test_to_bytes_with_custom_headers(self):
        """Should include custom headers."""
        response = HTTPResponse(
            status=200,
            content_type="application/json",
            body='{}',
            headers={"X-Custom": "value"}
        )

        data = response.to_bytes()

        assert b"X-Custom: value" in data


class TestOperationalHTTPServer:
    """Test OperationalHTTPServer class."""

    def test_initialization(self):
        """Should initialize with correct defaults."""
        server = OperationalHTTPServer()

        assert server.host == "0.0.0.0"
        assert server.port == 8080
        assert server.health_checker is None
        assert server.metrics is None

    def test_initialization_with_components(self):
        """Should accept health checker and metrics."""
        health = MagicMock()
        metrics = MagicMock()

        server = OperationalHTTPServer(
            port=9090,
            health_checker=health,
            metrics=metrics
        )

        assert server.port == 9090
        assert server.health_checker is health
        assert server.metrics is metrics


class TestHealthEndpoint:
    """Test /health endpoint handler."""

    def test_health_without_checker(self):
        """Should return basic status without health checker."""
        server = OperationalHTTPServer()
        request = HTTPRequest(method="GET", path="/health", headers={}, body=b"")

        response = server._handle_health(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["status"] == "healthy"

    def test_health_with_healthy_checker(self):
        """Should return full health status when healthy."""
        health_checker = MagicMock()
        report = MagicMock()
        report.is_ready = True
        report.to_dict.return_value = {
            "status": "healthy",
            "components": []
        }
        health_checker.check_health.return_value = report

        server = OperationalHTTPServer(health_checker=health_checker)
        request = HTTPRequest(method="GET", path="/health", headers={}, body=b"")

        response = server._handle_health(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["status"] == "healthy"

    def test_health_with_unhealthy_checker(self):
        """Should return 503 when not ready."""
        health_checker = MagicMock()
        report = MagicMock()
        report.is_ready = False
        report.to_dict.return_value = {
            "status": "unhealthy",
            "components": []
        }
        health_checker.check_health.return_value = report

        server = OperationalHTTPServer(health_checker=health_checker)
        request = HTTPRequest(method="GET", path="/health", headers={}, body=b"")

        response = server._handle_health(request)

        assert response.status == 503


class TestReadyEndpoint:
    """Test /ready endpoint handler."""

    def test_ready_without_checker(self):
        """Should return ready without health checker."""
        server = OperationalHTTPServer()
        request = HTTPRequest(method="GET", path="/ready", headers={}, body=b"")

        response = server._handle_ready(request)

        assert response.status == 200
        assert response.body == "ready"

    def test_ready_when_ready(self):
        """Should return 200 when ready."""
        health_checker = MagicMock()
        health_checker.get_ready_status.return_value = True

        server = OperationalHTTPServer(health_checker=health_checker)
        request = HTTPRequest(method="GET", path="/ready", headers={}, body=b"")

        response = server._handle_ready(request)

        assert response.status == 200

    def test_ready_when_not_ready(self):
        """Should return 503 when not ready."""
        health_checker = MagicMock()
        health_checker.get_ready_status.return_value = False

        server = OperationalHTTPServer(health_checker=health_checker)
        request = HTTPRequest(method="GET", path="/ready", headers={}, body=b"")

        response = server._handle_ready(request)

        assert response.status == 503


class TestLiveEndpoint:
    """Test /live endpoint handler."""

    def test_live_always_returns_ok(self):
        """Should always return 200 if server is running."""
        server = OperationalHTTPServer()
        request = HTTPRequest(method="GET", path="/live", headers={}, body=b"")

        response = server._handle_live(request)

        assert response.status == 200
        assert response.body == "alive"


class TestMetricsEndpoint:
    """Test /metrics endpoint handler."""

    def test_metrics_without_metrics_instance(self):
        """Should return placeholder without metrics."""
        server = OperationalHTTPServer()
        request = HTTPRequest(method="GET", path="/metrics", headers={}, body=b"")

        response = server._handle_metrics(request)

        assert response.status == 200
        assert "No metrics" in response.body

    def test_metrics_with_metrics_instance(self):
        """Should return Prometheus format."""
        metrics = MagicMock()
        metrics.export_prometheus.return_value = "# HELP test_metric Help\ntest_metric 42"

        server = OperationalHTTPServer(metrics=metrics)
        request = HTTPRequest(method="GET", path="/metrics", headers={}, body=b"")

        response = server._handle_metrics(request)

        assert response.status == 200
        assert "text/plain" in response.content_type
        assert "test_metric 42" in response.body


class TestRouting:
    """Test request routing."""

    @pytest.mark.asyncio
    async def test_route_known_path(self):
        """Should route to correct handler."""
        server = OperationalHTTPServer()
        request = HTTPRequest(method="GET", path="/live", headers={}, body=b"")

        response = await server._route_request(request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_route_unknown_path(self):
        """Should return 404 for unknown paths."""
        server = OperationalHTTPServer()
        request = HTTPRequest(method="GET", path="/unknown", headers={}, body=b"")

        response = await server._route_request(request)

        assert response.status == 404
        body = json.loads(response.body)
        assert body["error"] == "Not found"
        assert "/health" in body["available_endpoints"]

    @pytest.mark.asyncio
    async def test_add_custom_route(self):
        """Should allow adding custom routes."""
        server = OperationalHTTPServer()

        def custom_handler(request):
            return HTTPResponse(status=200, content_type="text/plain", body="custom")

        server.add_route("/custom", custom_handler)

        request = HTTPRequest(method="GET", path="/custom", headers={}, body=b"")
        response = await server._route_request(request)

        assert response.status == 200
        assert response.body == "custom"


class TestServerStartStop:
    """Test server start and stop."""

    @pytest.mark.asyncio
    async def test_start_server(self):
        """Should start server on specified port."""
        server = await start_server(port=18080)

        assert server._running is True
        assert server.port == 18080

        await stop_server(server)

    @pytest.mark.asyncio
    async def test_stop_server(self):
        """Should stop server gracefully."""
        server = await start_server(port=18081)
        await stop_server(server)

        assert server._running is False
