"""
Tests for Protocol Message Types
================================

Tests message creation, serialization, and validation.
"""

import pytest
import time
import uuid

from otto.protocol.message_types import (
    MessageType,
    Message,
    PAYLOAD_SCHEMAS,
    ProtocolError,
    create_state_sync,
    create_state_query,
    create_error,
    create_heartbeat,
)


class TestMessageType:
    """Tests for MessageType enum."""

    def test_message_type_values_are_unique(self):
        """All message type values must be unique."""
        values = [mt.value for mt in MessageType]
        assert len(values) == len(set(values))

    def test_message_type_categories(self):
        """Message types should be in correct categories."""
        # State operations: 0x0001-0x000F
        assert 0x0001 <= MessageType.STATE_SYNC.value <= 0x000F
        assert 0x0001 <= MessageType.STATE_QUERY.value <= 0x000F

        # Agent operations: 0x0010-0x001F
        assert 0x0010 <= MessageType.AGENT_SPAWN.value <= 0x001F
        assert 0x0010 <= MessageType.AGENT_RESULT.value <= 0x001F
        assert 0x0010 <= MessageType.AGENT_ABORT.value <= 0x001F

        # Protection operations: 0x0020-0x002F
        assert 0x0020 <= MessageType.PROTECTION_CHECK.value <= 0x002F
        assert 0x0020 <= MessageType.PROTECTION_OVERRIDE.value <= 0x002F

        # Knowledge operations: 0x0030-0x003F
        assert 0x0030 <= MessageType.KNOWLEDGE_QUERY.value <= 0x003F
        assert 0x0030 <= MessageType.KNOWLEDGE_STORE.value <= 0x003F

        # System operations: 0x00F0-0x00FF
        assert 0x00F0 <= MessageType.HEARTBEAT.value <= 0x00FF
        assert 0x00F0 <= MessageType.ERROR.value <= 0x00FF

    def test_all_types_have_schemas(self):
        """Every MessageType should have a schema defined."""
        for msg_type in MessageType:
            assert msg_type in PAYLOAD_SCHEMAS, f"Missing schema for {msg_type}"


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation_with_defaults(self):
        """Message can be created with minimal args."""
        msg = Message(type=MessageType.HEARTBEAT)

        assert msg.type == MessageType.HEARTBEAT
        assert msg.payload == {}
        assert msg.source == "otto"
        assert msg.timestamp > 0
        assert len(msg.correlation_id) == 36  # UUID format

    def test_message_creation_with_payload(self):
        """Message accepts custom payload."""
        payload = {"state": {"burnout_level": "green"}}
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload=payload
        )

        assert msg.payload == payload

    def test_message_creation_with_all_fields(self):
        """Message accepts all optional fields."""
        correlation_id = str(uuid.uuid4())
        timestamp = time.time()

        msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={"agent_type": "research", "task": "find patterns"},
            timestamp=timestamp,
            source="test_suite",
            correlation_id=correlation_id,
            sequence=42,
            priority=2,
        )

        assert msg.type == MessageType.AGENT_SPAWN
        assert msg.payload["agent_type"] == "research"
        assert msg.timestamp == timestamp
        assert msg.source == "test_suite"
        assert msg.correlation_id == correlation_id
        assert msg.sequence == 42
        assert msg.priority == 2

    def test_message_to_dict(self):
        """Message serializes to dict correctly."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={"state": {"mode": "focused"}},
            source="test",
        )

        d = msg.to_dict()

        assert d["type"] == MessageType.STATE_SYNC.value
        assert d["payload"] == {"state": {"mode": "focused"}}
        assert d["source"] == "test"
        assert "correlation_id" in d
        assert "timestamp" in d

    def test_message_from_dict(self):
        """Message deserializes from dict correctly."""
        data = {
            "type": MessageType.HEARTBEAT.value,
            "payload": {"load": 0.5},
            "timestamp": 1234567890.0,
            "source": "test",
            "correlation_id": "abc-123",
            "sequence": 1,
            "priority": 1,
        }

        msg = Message.from_dict(data)

        assert msg.type == MessageType.HEARTBEAT
        assert msg.payload == {"load": 0.5}
        assert msg.timestamp == 1234567890.0
        assert msg.source == "test"
        assert msg.correlation_id == "abc-123"
        assert msg.sequence == 1
        assert msg.priority == 1

    def test_message_from_dict_with_defaults(self):
        """Message.from_dict uses defaults for missing fields."""
        data = {
            "type": MessageType.HEARTBEAT.value,
        }

        msg = Message.from_dict(data)

        assert msg.type == MessageType.HEARTBEAT
        assert msg.payload == {}
        assert msg.source == "unknown"

    def test_message_from_dict_missing_type_raises(self):
        """Message.from_dict raises on missing type."""
        with pytest.raises(ProtocolError, match="Missing required field: type"):
            Message.from_dict({})

    def test_message_from_dict_invalid_type_raises(self):
        """Message.from_dict raises on invalid type."""
        with pytest.raises(ProtocolError, match="Invalid message type"):
            Message.from_dict({"type": 99999})

    def test_message_roundtrip(self):
        """Message survives to_dict/from_dict roundtrip."""
        original = Message(
            type=MessageType.AGENT_RESULT,
            payload={
                "agent_id": "agent-123",
                "status": "success",
                "result": {"findings": ["a", "b"]},
            },
            sequence=5,
            priority=1,
        )

        serialized = original.to_dict()
        restored = Message.from_dict(serialized)

        assert restored.type == original.type
        assert restored.payload == original.payload
        assert restored.sequence == original.sequence
        assert restored.priority == original.priority
        assert restored.correlation_id == original.correlation_id

    def test_message_checksum_deterministic(self):
        """Checksum is deterministic for same content."""
        msg1 = Message(
            type=MessageType.STATE_SYNC,
            payload={"state": {"mode": "focused"}},
            timestamp=1234567890.0,
        )
        msg2 = Message(
            type=MessageType.STATE_SYNC,
            payload={"state": {"mode": "focused"}},
            timestamp=1234567890.0,
        )

        assert msg1.checksum() == msg2.checksum()

    def test_message_checksum_differs_for_different_content(self):
        """Checksum differs for different content."""
        msg1 = Message(
            type=MessageType.STATE_SYNC,
            payload={"state": {"mode": "focused"}},
        )
        msg2 = Message(
            type=MessageType.STATE_SYNC,
            payload={"state": {"mode": "exploring"}},
        )

        assert msg1.checksum() != msg2.checksum()

    def test_message_reply_preserves_correlation_id(self):
        """Reply preserves correlation_id."""
        request = Message(type=MessageType.STATE_QUERY)
        response = request.reply(
            type=MessageType.STATE_SYNC,
            payload={"state": {}}
        )

        assert response.correlation_id == request.correlation_id
        assert response.type == MessageType.STATE_SYNC

    def test_message_is_error(self):
        """is_error identifies error messages."""
        error = Message(type=MessageType.ERROR, payload={"code": 500, "message": "fail"})
        normal = Message(type=MessageType.HEARTBEAT)

        assert error.is_error()
        assert not normal.is_error()

    def test_message_is_response_to(self):
        """is_response_to checks correlation_id."""
        request = Message(type=MessageType.STATE_QUERY)
        response = request.reply(type=MessageType.STATE_SYNC)
        unrelated = Message(type=MessageType.STATE_SYNC)

        assert response.is_response_to(request)
        assert not unrelated.is_response_to(request)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_create_state_sync(self):
        """create_state_sync creates correct message."""
        state_dict = {"burnout_level": "green", "mode": "focused"}
        msg = create_state_sync(state_dict, force=True)

        assert msg.type == MessageType.STATE_SYNC
        assert msg.payload["state"] == state_dict
        assert msg.payload["force"] is True

    def test_create_state_query(self):
        """create_state_query creates correct message."""
        msg = create_state_query(fields=["burnout_level", "mode"])

        assert msg.type == MessageType.STATE_QUERY
        assert msg.payload["fields"] == ["burnout_level", "mode"]

    def test_create_state_query_no_fields(self):
        """create_state_query works without fields."""
        msg = create_state_query()

        assert msg.type == MessageType.STATE_QUERY
        assert msg.payload == {}

    def test_create_error(self):
        """create_error creates correct message."""
        msg = create_error(500, "Internal error", {"detail": "stack trace"})

        assert msg.type == MessageType.ERROR
        assert msg.payload["code"] == 500
        assert msg.payload["message"] == "Internal error"
        assert msg.payload["data"]["detail"] == "stack trace"

    def test_create_heartbeat(self):
        """create_heartbeat creates correct message."""
        msg = create_heartbeat(load=0.75, uptime=3600.0)

        assert msg.type == MessageType.HEARTBEAT
        assert msg.payload["load"] == 0.75
        assert msg.payload["uptime"] == 3600.0

    def test_create_heartbeat_empty(self):
        """create_heartbeat works without args."""
        msg = create_heartbeat()

        assert msg.type == MessageType.HEARTBEAT
        assert msg.payload == {}
