"""
Tests for Binary Protocol Layer (Layer 0)
=========================================

Tests binary encoding/decoding, streaming, and performance.
"""

import pytest
import struct
import time

from otto.protocol.message_types import Message, MessageType, create_heartbeat, ProtocolError
from otto.protocol.layer0_binary import BinaryProtocol, BinaryProtocolError


class TestBinaryProtocol:
    """Tests for BinaryProtocol class."""

    @pytest.fixture
    def proto(self):
        """Create a BinaryProtocol instance."""
        return BinaryProtocol()

    def test_protocol_constants(self, proto):
        """Protocol constants should be correct."""
        assert proto.VERSION == 0x01
        assert proto.HEADER_SIZE == 7
        assert proto.MAX_PAYLOAD_SIZE == 10 * 1024 * 1024

    def test_encode_simple_message(self, proto):
        """Encode a simple message."""
        msg = Message(type=MessageType.HEARTBEAT)
        encoded = proto.encode(msg)

        # Should start with version byte
        assert encoded[0] == proto.VERSION
        # Should have at least header size
        assert len(encoded) >= proto.HEADER_SIZE

    def test_decode_simple_message(self, proto):
        """Decode a simple message."""
        msg = Message(type=MessageType.HEARTBEAT, payload={"load": 0.5})
        encoded = proto.encode(msg)
        decoded = proto.decode(encoded)

        assert decoded.type == MessageType.HEARTBEAT
        assert decoded.payload["load"] == 0.5

    def test_encode_decode_roundtrip(self, proto):
        """Message survives encode/decode roundtrip."""
        original = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {
                    "burnout_level": "green",
                    "mode": "focused",
                    "exchange_count": 42,
                }
            },
            source="test",
            sequence=10,
            priority=1,
        )

        encoded = proto.encode(original)
        decoded = proto.decode(encoded)

        assert decoded.type == original.type
        assert decoded.payload == original.payload
        assert decoded.source == original.source
        assert decoded.sequence == original.sequence
        assert decoded.priority == original.priority

    def test_encode_decode_all_message_types(self, proto):
        """All message types can be encoded and decoded."""
        for msg_type in MessageType:
            msg = Message(type=msg_type, payload={"test": True})
            encoded = proto.encode(msg)
            decoded = proto.decode(encoded)
            assert decoded.type == msg_type

    def test_decode_invalid_version_raises(self, proto):
        """Decoding invalid version raises error."""
        # Create a header with wrong version
        bad_header = struct.pack('>BHI', 0xFF, MessageType.HEARTBEAT.value, 0)
        with pytest.raises(BinaryProtocolError, match="Unsupported protocol version"):
            proto.decode(bad_header)

    def test_decode_truncated_header_raises(self, proto):
        """Decoding truncated header raises error."""
        with pytest.raises(BinaryProtocolError, match="Data too short"):
            proto.decode(b'\x01\x00')

    def test_decode_incomplete_message_raises(self, proto):
        """Decoding incomplete message raises error."""
        # Header says 100 bytes of payload, but only provide 10
        header = struct.pack('>BHI', 0x01, MessageType.HEARTBEAT.value, 100)
        incomplete = header + b'x' * 10
        with pytest.raises(BinaryProtocolError, match="Incomplete message"):
            proto.decode(incomplete)

    def test_decode_invalid_message_type_raises(self, proto):
        """Decoding invalid message type raises error."""
        # Use an invalid message type value
        import msgpack
        payload = msgpack.packb({})
        # Use actual payload length in header
        header = struct.pack('>BHI', 0x01, 0xFFFF, len(payload))
        # Can raise either BinaryProtocolError or ProtocolError
        with pytest.raises((BinaryProtocolError, ProtocolError), match="Invalid message type"):
            proto.decode(header + payload)


class TestBinaryProtocolStreaming:
    """Tests for streaming operations."""

    @pytest.fixture
    def proto(self):
        return BinaryProtocol()

    def test_stream_encode_single(self, proto):
        """Stream encode single message."""
        msg = Message(type=MessageType.HEARTBEAT)
        encoded = proto.stream_encode([msg])
        decoded = proto.stream_decode(encoded)

        assert len(decoded) == 1
        assert decoded[0].type == MessageType.HEARTBEAT

    def test_stream_encode_multiple(self, proto):
        """Stream encode multiple messages."""
        messages = [
            Message(type=MessageType.HEARTBEAT, payload={"seq": i})
            for i in range(5)
        ]

        encoded = proto.stream_encode(messages)
        decoded = proto.stream_decode(encoded)

        assert len(decoded) == 5
        for i, msg in enumerate(decoded):
            assert msg.type == MessageType.HEARTBEAT
            assert msg.payload["seq"] == i

    def test_stream_decode_mixed_types(self, proto):
        """Stream decode messages of different types."""
        messages = [
            Message(type=MessageType.HEARTBEAT),
            Message(type=MessageType.STATE_SYNC, payload={"state": {}}),
            Message(type=MessageType.ERROR, payload={"code": 500, "message": "err"}),
        ]

        encoded = proto.stream_encode(messages)
        decoded = proto.stream_decode(encoded)

        assert len(decoded) == 3
        assert decoded[0].type == MessageType.HEARTBEAT
        assert decoded[1].type == MessageType.STATE_SYNC
        assert decoded[2].type == MessageType.ERROR

    def test_stream_decode_empty(self, proto):
        """Stream decode empty data returns empty list."""
        decoded = proto.stream_decode(b'')
        assert decoded == []

    def test_stream_decode_truncated_raises(self, proto):
        """Stream decode truncated data raises error."""
        msg = Message(type=MessageType.HEARTBEAT)
        encoded = proto.encode(msg)
        truncated = encoded[:-5]  # Remove last 5 bytes

        with pytest.raises(BinaryProtocolError):
            proto.stream_decode(truncated)


class TestBinaryProtocolHelpers:
    """Tests for helper methods."""

    @pytest.fixture
    def proto(self):
        return BinaryProtocol()

    def test_peek_type(self, proto):
        """Peek at message type without full decode."""
        msg = Message(type=MessageType.AGENT_SPAWN, payload={"agent_type": "test", "task": "run"})
        encoded = proto.encode(msg)

        msg_type = proto.peek_type(encoded)
        assert msg_type == MessageType.AGENT_SPAWN

    def test_peek_type_truncated_raises(self, proto):
        """Peek on truncated data raises error."""
        with pytest.raises(BinaryProtocolError, match="too short"):
            proto.peek_type(b'\x01\x00')

    def test_get_message_length(self, proto):
        """Get total message length from header."""
        msg = Message(type=MessageType.HEARTBEAT, payload={"load": 0.5})
        encoded = proto.encode(msg)

        length = proto.get_message_length(encoded)
        assert length == len(encoded)

    def test_is_valid_header_true(self, proto):
        """Valid header returns True."""
        msg = Message(type=MessageType.HEARTBEAT)
        encoded = proto.encode(msg)
        assert proto.is_valid_header(encoded)

    def test_is_valid_header_false_short(self, proto):
        """Short data returns False."""
        assert not proto.is_valid_header(b'\x01\x00')

    def test_is_valid_header_false_bad_version(self, proto):
        """Bad version returns False."""
        bad_header = struct.pack('>BHI', 0xFF, MessageType.HEARTBEAT.value, 0)
        assert not proto.is_valid_header(bad_header)

    def test_is_valid_header_false_bad_type(self, proto):
        """Invalid message type returns False."""
        bad_header = struct.pack('>BHI', 0x01, 0xFFFF, 0)
        assert not proto.is_valid_header(bad_header)


class TestBinaryProtocolPayloads:
    """Tests for complex payload handling."""

    @pytest.fixture
    def proto(self):
        return BinaryProtocol()

    def test_nested_payload(self, proto):
        """Nested payload structures survive roundtrip."""
        msg = Message(
            type=MessageType.AGENT_RESULT,
            payload={
                "agent_id": "test-123",
                "status": "success",
                "result": {
                    "findings": [
                        {"type": "pattern", "data": {"nested": True}},
                        {"type": "insight", "data": {"value": 42}},
                    ],
                    "metadata": {
                        "duration": 1.5,
                        "tokens": 1000,
                    }
                },
                "files_modified": ["a.py", "b.py"],
            }
        )

        encoded = proto.encode(msg)
        decoded = proto.decode(encoded)

        assert decoded.payload["result"]["findings"][0]["data"]["nested"] is True
        assert decoded.payload["result"]["metadata"]["tokens"] == 1000

    def test_binary_data_in_payload(self, proto):
        """Binary data in payload survives roundtrip."""
        binary_content = b'\x00\x01\x02\xff\xfe\xfd'
        msg = Message(
            type=MessageType.KNOWLEDGE_STORE,
            payload={
                "path": "/test",
                "content": {"binary": binary_content},
            }
        )

        encoded = proto.encode(msg)
        decoded = proto.decode(encoded)

        assert decoded.payload["content"]["binary"] == binary_content

    def test_unicode_in_payload(self, proto):
        """Unicode strings survive roundtrip."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {
                    "message": "Hello, world! And love from Earth",
                }
            }
        )

        encoded = proto.encode(msg)
        decoded = proto.decode(encoded)

        assert decoded.payload["state"]["message"] == "Hello, world! And love from Earth"

    def test_empty_payload(self, proto):
        """Empty payload works correctly."""
        msg = Message(type=MessageType.HEARTBEAT, payload={})
        encoded = proto.encode(msg)
        decoded = proto.decode(encoded)

        # Payload may have default fields from Message.to_dict()
        assert decoded.type == MessageType.HEARTBEAT


class TestBinaryProtocolPerformance:
    """Performance benchmarks for binary protocol."""

    @pytest.fixture
    def proto(self):
        return BinaryProtocol()

    def test_encode_performance(self, proto):
        """Encode should complete in <1ms per message."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {
                    "burnout_level": "green",
                    "mode": "focused",
                    "exchange_count": 42,
                    "tasks_completed": 5,
                }
            }
        )

        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            proto.encode(msg)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0, f"Encode too slow: {avg_ms:.4f}ms average"

    def test_decode_performance(self, proto):
        """Decode should complete in <1ms per message."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {
                    "burnout_level": "green",
                    "mode": "focused",
                    "exchange_count": 42,
                    "tasks_completed": 5,
                }
            }
        )
        encoded = proto.encode(msg)

        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            proto.decode(encoded)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 1.0, f"Decode too slow: {avg_ms:.4f}ms average"

    def test_roundtrip_performance(self, proto):
        """Roundtrip should complete in <2ms per message."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {
                    "burnout_level": "green",
                    "mode": "focused",
                    "exchange_count": 42,
                }
            }
        )

        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            encoded = proto.encode(msg)
            proto.decode(encoded)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        assert avg_ms < 2.0, f"Roundtrip too slow: {avg_ms:.4f}ms average"

    def test_stream_performance(self, proto):
        """Stream operations should be efficient."""
        messages = [
            Message(type=MessageType.HEARTBEAT, payload={"seq": i})
            for i in range(100)
        ]

        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            encoded = proto.stream_encode(messages)
            proto.stream_decode(encoded)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / iterations) * 1000
        # 100 messages should take <50ms total
        assert avg_ms < 50.0, f"Stream too slow: {avg_ms:.4f}ms for 100 messages"
