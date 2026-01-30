"""
Tests for JSON-RPC Layer (Layer 1)
==================================

Tests JSON-RPC 2.0 compliance, method handlers, and error handling.
"""

import pytest
import json

from otto.protocol.layer1_jsonrpc import (
    JSONRPCHandler,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    create_request,
    create_notification,
    is_error_response,
    get_error_code,
)


class TestJSONRPCRequest:
    """Tests for JSONRPCRequest parsing."""

    def test_parse_valid_request(self):
        """Parse a valid JSON-RPC request."""
        data = {
            "jsonrpc": "2.0",
            "method": "otto.status",
            "id": 1,
        }
        req = JSONRPCRequest.from_dict(data)

        assert req.method == "otto.status"
        assert req.id == 1
        assert req.params == {}

    def test_parse_request_with_params(self):
        """Parse request with parameters."""
        data = {
            "jsonrpc": "2.0",
            "method": "otto.state.get",
            "params": {"fields": ["burnout_level", "mode"]},
            "id": 2,
        }
        req = JSONRPCRequest.from_dict(data)

        assert req.method == "otto.state.get"
        assert req.params == {"fields": ["burnout_level", "mode"]}

    def test_parse_notification(self):
        """Parse notification (no id)."""
        data = {
            "jsonrpc": "2.0",
            "method": "otto.ping",
        }
        req = JSONRPCRequest.from_dict(data)

        assert req.is_notification()
        assert req.id is None

    def test_parse_invalid_jsonrpc_version(self):
        """Invalid JSON-RPC version raises error."""
        data = {
            "jsonrpc": "1.0",
            "method": "test",
        }
        with pytest.raises(JSONRPCError) as exc_info:
            JSONRPCRequest.from_dict(data)
        assert exc_info.value.code == INVALID_REQUEST

    def test_parse_missing_method(self):
        """Missing method raises error."""
        data = {
            "jsonrpc": "2.0",
            "id": 1,
        }
        with pytest.raises(JSONRPCError) as exc_info:
            JSONRPCRequest.from_dict(data)
        assert exc_info.value.code == INVALID_REQUEST

    def test_parse_invalid_params_type(self):
        """Invalid params type raises error."""
        data = {
            "jsonrpc": "2.0",
            "method": "test",
            "params": "invalid",
            "id": 1,
        }
        with pytest.raises(JSONRPCError) as exc_info:
            JSONRPCRequest.from_dict(data)
        assert exc_info.value.code == INVALID_PARAMS


class TestJSONRPCResponse:
    """Tests for JSONRPCResponse."""

    def test_success_response(self):
        """Create success response."""
        response = JSONRPCResponse.success(1, {"status": "ok"})
        d = response.to_dict()

        assert d["jsonrpc"] == "2.0"
        assert d["id"] == 1
        assert d["result"] == {"status": "ok"}
        assert "error" not in d

    def test_failure_response(self):
        """Create error response."""
        error = JSONRPCError(INTERNAL_ERROR, "Something went wrong")
        response = JSONRPCResponse.failure(1, error)
        d = response.to_dict()

        assert d["jsonrpc"] == "2.0"
        assert d["id"] == 1
        assert d["error"]["code"] == INTERNAL_ERROR
        assert d["error"]["message"] == "Something went wrong"
        assert "result" not in d


class TestJSONRPCError:
    """Tests for JSONRPCError."""

    def test_error_with_data(self):
        """Error can include additional data."""
        error = JSONRPCError(
            INTERNAL_ERROR,
            "Failed",
            data={"detail": "stack trace here"}
        )
        d = error.to_dict()

        assert d["code"] == INTERNAL_ERROR
        assert d["message"] == "Failed"
        assert d["data"]["detail"] == "stack trace here"

    def test_error_without_data(self):
        """Error without data omits data field."""
        error = JSONRPCError(METHOD_NOT_FOUND, "Method not found")
        d = error.to_dict()

        assert d["code"] == METHOD_NOT_FOUND
        assert "data" not in d


class TestJSONRPCHandler:
    """Tests for JSONRPCHandler."""

    @pytest.fixture
    def handler(self):
        """Create a JSONRPCHandler instance."""
        return JSONRPCHandler()

    @pytest.mark.asyncio
    async def test_handle_ping(self, handler):
        """Handle otto.ping returns pong."""
        request = {
            "jsonrpc": "2.0",
            "method": "otto.ping",
            "id": 1,
        }
        response = await handler.handle_request(request)

        assert response["result"] == "pong"
        assert response["id"] == 1

    @pytest.mark.asyncio
    async def test_handle_status(self, handler):
        """Handle otto.status returns status info."""
        request = {
            "jsonrpc": "2.0",
            "method": "otto.status",
            "id": 1,
        }
        response = await handler.handle_request(request)

        assert response["result"]["status"] == "ok"
        assert "timestamp" in response["result"]

    @pytest.mark.asyncio
    async def test_handle_methods(self, handler):
        """Handle otto.methods returns available methods."""
        request = {
            "jsonrpc": "2.0",
            "method": "otto.methods",
            "id": 1,
        }
        response = await handler.handle_request(request)

        methods = response["result"]
        assert "otto.ping" in methods
        assert "otto.status" in methods
        assert "otto.methods" in methods

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self, handler):
        """Unknown method returns METHOD_NOT_FOUND error."""
        request = {
            "jsonrpc": "2.0",
            "method": "otto.nonexistent",
            "id": 1,
        }
        response = await handler.handle_request(request)

        assert is_error_response(response)
        assert get_error_code(response) == METHOD_NOT_FOUND

    @pytest.mark.asyncio
    async def test_handle_json_string(self, handler):
        """Can handle JSON string input."""
        request = json.dumps({
            "jsonrpc": "2.0",
            "method": "otto.ping",
            "id": 1,
        })
        response = await handler.handle_request(request)

        assert response["result"] == "pong"

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, handler):
        """Invalid JSON returns PARSE_ERROR."""
        response = await handler.handle_request("not valid json{{{")

        assert is_error_response(response)
        assert get_error_code(response) == PARSE_ERROR

    @pytest.mark.asyncio
    async def test_handle_notification_no_response(self, handler):
        """Notifications return None (no response)."""
        request = {
            "jsonrpc": "2.0",
            "method": "otto.ping",
            # No id = notification
        }
        response = await handler.handle_request(request)

        assert response is None

    @pytest.mark.asyncio
    async def test_register_custom_method(self, handler):
        """Can register custom methods."""
        async def custom_handler(name: str):
            return f"Hello, {name}!"

        handler.register("custom.greet", custom_handler)

        request = {
            "jsonrpc": "2.0",
            "method": "custom.greet",
            "params": {"name": "World"},
            "id": 1,
        }
        response = await handler.handle_request(request)

        assert response["result"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_register_sync_method(self, handler):
        """Can register synchronous methods."""
        def sync_handler(x: int, y: int):
            return x + y

        handler.register("math.add", sync_handler)

        request = {
            "jsonrpc": "2.0",
            "method": "math.add",
            "params": {"x": 5, "y": 3},
            "id": 1,
        }
        response = await handler.handle_request(request)

        assert response["result"] == 8

    @pytest.mark.asyncio
    async def test_unregister_method(self, handler):
        """Can unregister methods."""
        handler.register("temp.method", lambda: "temp")
        assert handler.unregister("temp.method")
        assert not handler.unregister("temp.method")  # Already removed

        request = {
            "jsonrpc": "2.0",
            "method": "temp.method",
            "id": 1,
        }
        response = await handler.handle_request(request)
        assert is_error_response(response)


class TestJSONRPCBatch:
    """Tests for batch request handling."""

    @pytest.fixture
    def handler(self):
        return JSONRPCHandler()

    @pytest.mark.asyncio
    async def test_batch_requests(self, handler):
        """Handle batch of requests."""
        requests = [
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 1},
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 2},
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 3},
        ]
        responses = await handler.handle_batch(requests)

        assert len(responses) == 3
        for resp in responses:
            assert resp["result"] == "pong"

    @pytest.mark.asyncio
    async def test_batch_mixed_success_error(self, handler):
        """Batch with mixed success and error."""
        requests = [
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 1},
            {"jsonrpc": "2.0", "method": "otto.nonexistent", "id": 2},
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 3},
        ]
        responses = await handler.handle_batch(requests)

        assert len(responses) == 3
        assert responses[0]["result"] == "pong"
        assert is_error_response(responses[1])
        assert responses[2]["result"] == "pong"

    @pytest.mark.asyncio
    async def test_batch_with_notifications(self, handler):
        """Batch with notifications excludes them from response."""
        requests = [
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 1},
            {"jsonrpc": "2.0", "method": "otto.ping"},  # notification
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 2},
        ]
        responses = await handler.handle_batch(requests)

        # Should only have 2 responses (notifications excluded)
        assert len(responses) == 2

    @pytest.mark.asyncio
    async def test_batch_empty(self, handler):
        """Empty batch returns error."""
        responses = await handler.handle_batch([])

        assert len(responses) == 1
        assert is_error_response(responses[0])

    @pytest.mark.asyncio
    async def test_batch_all_notifications(self, handler):
        """Batch of only notifications returns None."""
        requests = [
            {"jsonrpc": "2.0", "method": "otto.ping"},
            {"jsonrpc": "2.0", "method": "otto.ping"},
        ]
        responses = await handler.handle_batch(requests)

        assert responses is None


class TestJSONRPCHelpers:
    """Tests for helper functions."""

    def test_create_request(self):
        """create_request creates valid request."""
        req = create_request("otto.status", params={"verbose": True}, id=42)

        assert req["jsonrpc"] == "2.0"
        assert req["method"] == "otto.status"
        assert req["params"] == {"verbose": True}
        assert req["id"] == 42

    def test_create_request_minimal(self):
        """create_request without optional args."""
        req = create_request("otto.ping")

        assert req["jsonrpc"] == "2.0"
        assert req["method"] == "otto.ping"
        assert "params" not in req
        assert "id" not in req

    def test_create_notification(self):
        """create_notification creates request without id."""
        req = create_notification("otto.ping")

        assert req["jsonrpc"] == "2.0"
        assert req["method"] == "otto.ping"
        assert "id" not in req

    def test_is_error_response_true(self):
        """is_error_response identifies error responses."""
        response = {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid"},
            "id": 1,
        }
        assert is_error_response(response)

    def test_is_error_response_false(self):
        """is_error_response identifies success responses."""
        response = {
            "jsonrpc": "2.0",
            "result": "ok",
            "id": 1,
        }
        assert not is_error_response(response)

    def test_get_error_code(self):
        """get_error_code extracts error code."""
        response = {
            "jsonrpc": "2.0",
            "error": {"code": METHOD_NOT_FOUND, "message": "Not found"},
            "id": 1,
        }
        assert get_error_code(response) == METHOD_NOT_FOUND

    def test_get_error_code_none(self):
        """get_error_code returns None for success."""
        response = {
            "jsonrpc": "2.0",
            "result": "ok",
            "id": 1,
        }
        assert get_error_code(response) is None


class TestJSONRPCPositionalParams:
    """Tests for positional parameter handling."""

    @pytest.fixture
    def handler(self):
        handler = JSONRPCHandler()

        def add(a, b):
            return a + b

        handler.register("math.add", add)
        return handler

    @pytest.mark.asyncio
    async def test_positional_params(self, handler):
        """Methods can accept positional params."""
        request = {
            "jsonrpc": "2.0",
            "method": "math.add",
            "params": [5, 3],
            "id": 1,
        }
        response = await handler.handle_request(request)

        assert response["result"] == 8

    @pytest.mark.asyncio
    async def test_named_params(self, handler):
        """Methods can accept named params."""
        request = {
            "jsonrpc": "2.0",
            "method": "math.add",
            "params": {"a": 5, "b": 3},
            "id": 1,
        }
        response = await handler.handle_request(request)

        assert response["result"] == 8
