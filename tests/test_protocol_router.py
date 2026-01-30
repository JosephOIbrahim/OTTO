"""
Tests for Protocol Router
=========================

Tests format detection, routing, and layer integration.
"""

import pytest
import struct

from otto.protocol.protocol_router import ProtocolFormat, ProtocolRouter
from otto.protocol.message_types import Message, MessageType
from otto.protocol.layer0_binary import BinaryProtocol


class TestProtocolFormatDetection:
    """Tests for format detection."""

    @pytest.fixture
    def router(self):
        return ProtocolRouter()

    def test_detect_binary_format(self, router):
        """Binary data with version byte detected as BINARY."""
        # Create valid binary header
        header = struct.pack('>BHI', 0x01, MessageType.HEARTBEAT.value, 0)
        assert router.detect_format(header) == ProtocolFormat.BINARY

    def test_detect_binary_with_payload(self, router):
        """Binary message with payload detected as BINARY."""
        proto = BinaryProtocol()
        msg = Message(type=MessageType.HEARTBEAT)
        encoded = proto.encode(msg)
        assert router.detect_format(encoded) == ProtocolFormat.BINARY

    def test_detect_jsonrpc_dict(self, router):
        """Dict with jsonrpc key detected as JSONRPC."""
        request = {
            "jsonrpc": "2.0",
            "method": "otto.status",
            "id": 1,
        }
        assert router.detect_format(request) == ProtocolFormat.JSONRPC

    def test_detect_jsonrpc_string(self, router):
        """JSON string detected as JSONRPC."""
        request = '{"jsonrpc": "2.0", "method": "otto.status", "id": 1}'
        assert router.detect_format(request) == ProtocolFormat.JSONRPC

    def test_detect_jsonrpc_batch(self, router):
        """JSON-RPC batch detected as JSONRPC."""
        requests = [
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 1},
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 2},
        ]
        assert router.detect_format(requests) == ProtocolFormat.JSONRPC

    def test_detect_human_text(self, router):
        """Plain text detected as HUMAN."""
        assert router.detect_format("How are you doing?") == ProtocolFormat.HUMAN

    def test_detect_human_bytes_no_version(self, router):
        """Bytes without version byte detected as HUMAN."""
        # Bytes that don't start with 0x01
        data = b'\x00\x01\x02\x03'
        assert router.detect_format(data) == ProtocolFormat.HUMAN

    def test_detect_dict_without_jsonrpc(self, router):
        """Dict without jsonrpc key treated as JSONRPC (best guess)."""
        data = {"foo": "bar"}
        # Router defaults to JSONRPC for dicts
        assert router.detect_format(data) == ProtocolFormat.JSONRPC


class TestProtocolRouterRouting:
    """Tests for request routing."""

    @pytest.fixture
    def router(self):
        return ProtocolRouter()

    @pytest.mark.asyncio
    async def test_route_jsonrpc_request(self, router):
        """JSON-RPC request routed correctly."""
        request = {
            "jsonrpc": "2.0",
            "method": "otto.ping",
            "id": 1,
        }
        response = await router.route(request)

        assert response["result"] == "pong"
        assert response["id"] == 1

    @pytest.mark.asyncio
    async def test_route_binary_heartbeat(self, router):
        """Binary heartbeat request routed correctly."""
        proto = BinaryProtocol()
        msg = Message(type=MessageType.HEARTBEAT)
        encoded = proto.encode(msg)

        response_bytes = await router.route(encoded)

        # Decode response
        response_msg = proto.decode(response_bytes)
        assert response_msg.type == MessageType.HEARTBEAT

    @pytest.mark.asyncio
    async def test_route_human_text(self, router):
        """Human text request routed correctly."""
        response = await router.route("Hello, how are you?")

        # Should get a human-readable response
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_route_jsonrpc_batch(self, router):
        """JSON-RPC batch routed correctly."""
        requests = [
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 1},
            {"jsonrpc": "2.0", "method": "otto.ping", "id": 2},
        ]
        responses = await router.route(requests)

        assert len(responses) == 2
        assert responses[0]["result"] == "pong"
        assert responses[1]["result"] == "pong"


class TestProtocolRouterTransformUp:
    """Tests for Message to human transformation."""

    @pytest.fixture
    def router(self):
        return ProtocolRouter()

    def test_transform_up_heartbeat(self, router):
        """Heartbeat transforms to OK."""
        msg = Message(type=MessageType.HEARTBEAT)
        result = router.transform_up(msg)
        assert result == "OK"

    def test_transform_up_error(self, router):
        """Error message transforms to error text."""
        msg = Message(
            type=MessageType.ERROR,
            payload={"code": 500, "message": "Something went wrong"}
        )
        result = router.transform_up(msg)
        assert "Something went wrong" in result

    def test_transform_up_protection_check(self, router):
        """Protection check transforms to action text."""
        msg = Message(
            type=MessageType.PROTECTION_CHECK,
            payload={"action": "suggest_break", "message": "Take a breather"}
        )
        result = router.transform_up(msg)
        assert "suggest_break" in result

    def test_transform_up_unknown_type(self, router):
        """Unknown type shows type name."""
        msg = Message(type=MessageType.AGENT_SPAWN, payload={})
        result = router.transform_up(msg)
        assert "AGENT_SPAWN" in result


class TestProtocolRouterTransformDown:
    """Tests for human to Message transformation."""

    @pytest.fixture
    def router(self):
        return ProtocolRouter()

    def test_transform_down_status_query(self, router):
        """Status-related text becomes STATE_QUERY."""
        msg = router.transform_down("What's the status?")
        assert msg.type == MessageType.STATE_QUERY

    def test_transform_down_break_request(self, router):
        """Break-related text becomes PROTECTION_CHECK."""
        msg = router.transform_down("I need a break")
        assert msg.type == MessageType.PROTECTION_CHECK

    def test_transform_down_default(self, router):
        """Unrecognized text becomes HEARTBEAT."""
        msg = router.transform_down("Random gibberish here")
        assert msg.type == MessageType.HEARTBEAT


class TestProtocolRouterIntegration:
    """Integration tests with handlers wired up."""

    @pytest.fixture
    def router(self):
        return ProtocolRouter()

    @pytest.mark.asyncio
    async def test_jsonrpc_status_without_state_manager(self, router):
        """Status works without state manager."""
        response = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.status",
            "id": 1,
        })

        assert response["result"]["status"] == "ok"
        # No cognitive_state key since no manager configured
        assert "cognitive_state" not in response["result"]

    @pytest.mark.asyncio
    async def test_binary_state_query_without_manager(self, router):
        """STATE_QUERY returns error without state manager."""
        proto = BinaryProtocol()
        msg = Message(type=MessageType.STATE_QUERY, payload={})
        encoded = proto.encode(msg)

        response_bytes = await router.route(encoded)
        response_msg = proto.decode(response_bytes)

        assert response_msg.type == MessageType.ERROR

    @pytest.mark.asyncio
    async def test_binary_heartbeat_roundtrip(self, router):
        """Heartbeat message roundtrip works."""
        proto = BinaryProtocol()

        # Create and send heartbeat
        original = Message(
            type=MessageType.HEARTBEAT,
            payload={"load": 0.5}
        )
        encoded = proto.encode(original)

        # Route and decode response
        response_bytes = await router.route(encoded)
        response = proto.decode(response_bytes)

        # Response should be heartbeat with status
        assert response.type == MessageType.HEARTBEAT
        assert response.correlation_id == original.correlation_id


class _MockBurnoutLevel:
    value = "green"

class _MockMomentumPhase:
    value = "rolling"

class _MockEnergyLevel:
    value = "medium"

class _MockMode:
    value = "focused"

class _MockState:
    """Mock cognitive state."""
    burnout_level = _MockBurnoutLevel()
    momentum_phase = _MockMomentumPhase()
    energy_level = _MockEnergyLevel()
    mode = _MockMode()

    def to_dict(self):
        return {
            "burnout_level": "green",
            "mode": "focused",
            "exchange_count": 5,
        }


class TestProtocolRouterWithStateManger:
    """Tests with a mocked state manager."""

    MockState = _MockState

    class MockStateManager:
        """Mock state manager."""
        def get_state(self):
            return _MockState()

        def batch_update(self, updates):
            pass

    @pytest.fixture
    def router_with_state(self):
        return ProtocolRouter(state_manager=self.MockStateManager())

    @pytest.mark.asyncio
    async def test_jsonrpc_status_with_state(self, router_with_state):
        """Status includes cognitive state when manager configured."""
        response = await router_with_state.route({
            "jsonrpc": "2.0",
            "method": "otto.status",
            "id": 1,
        })

        assert "cognitive_state" in response["result"]
        assert response["result"]["cognitive_state"]["burnout_level"] == "green"

    @pytest.mark.asyncio
    async def test_jsonrpc_state_get(self, router_with_state):
        """state.get returns full state."""
        response = await router_with_state.route({
            "jsonrpc": "2.0",
            "method": "otto.state.get",
            "id": 1,
        })

        assert response["result"]["burnout_level"] == "green"
        assert response["result"]["mode"] == "focused"

    @pytest.mark.asyncio
    async def test_jsonrpc_state_get_fields(self, router_with_state):
        """state.get with fields returns subset."""
        response = await router_with_state.route({
            "jsonrpc": "2.0",
            "method": "otto.state.get",
            "params": {"fields": ["burnout_level"]},
            "id": 1,
        })

        assert "burnout_level" in response["result"]
        # Other fields should be filtered out
        assert "mode" not in response["result"]

    @pytest.mark.asyncio
    async def test_binary_state_query_with_manager(self, router_with_state):
        """STATE_QUERY works with state manager."""
        proto = BinaryProtocol()
        msg = Message(type=MessageType.STATE_QUERY, payload={})
        encoded = proto.encode(msg)

        response_bytes = await router_with_state.route(encoded)
        response = proto.decode(response_bytes)

        assert response.type == MessageType.STATE_SYNC
        assert response.payload["state"]["burnout_level"] == "green"
