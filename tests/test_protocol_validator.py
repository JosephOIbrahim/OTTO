"""
Tests for Protocol Validator
============================

Tests schema validation, type checking, and custom validators.
"""

import pytest

from otto.protocol.message_types import Message, MessageType
from otto.protocol.validator import (
    ProtocolValidator,
    ValidationResult,
    validate_message,
    is_valid_message,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_result_valid_by_default(self):
        """Fresh result is valid."""
        result = ValidationResult(valid=True)
        assert result.valid
        assert bool(result)

    def test_add_error_makes_invalid(self):
        """Adding error makes result invalid."""
        result = ValidationResult(valid=True)
        result.add_error("Something wrong")

        assert not result.valid
        assert not bool(result)
        assert "Something wrong" in result.errors

    def test_add_warning_keeps_valid(self):
        """Adding warning keeps result valid."""
        result = ValidationResult(valid=True)
        result.add_warning("Minor issue")

        assert result.valid
        assert "Minor issue" in result.warnings

    def test_merge_results(self):
        """Merge combines errors and warnings."""
        result1 = ValidationResult(valid=True)
        result1.add_warning("warn1")

        result2 = ValidationResult(valid=True)
        result2.add_error("err1")

        result1.merge(result2)

        assert not result1.valid
        assert "warn1" in result1.warnings
        assert "err1" in result1.errors


class TestProtocolValidator:
    """Tests for ProtocolValidator."""

    @pytest.fixture
    def validator(self):
        return ProtocolValidator()

    @pytest.fixture
    def strict_validator(self):
        return ProtocolValidator(strict=True)

    def test_validate_heartbeat_valid(self, validator):
        """Valid heartbeat passes validation."""
        msg = Message(type=MessageType.HEARTBEAT, payload={})
        result = validator.validate_message(msg)
        assert result.valid

    def test_validate_heartbeat_with_load(self, validator):
        """Heartbeat with optional load passes."""
        msg = Message(
            type=MessageType.HEARTBEAT,
            payload={"load": 0.75, "uptime": 3600.0}
        )
        result = validator.validate_message(msg)
        assert result.valid

    def test_validate_state_sync_valid(self, validator):
        """Valid STATE_SYNC passes validation."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {
                    "burnout_level": "green",
                    "mode": "focused",
                }
            }
        )
        result = validator.validate_message(msg)
        assert result.valid

    def test_validate_state_sync_missing_required(self, validator):
        """STATE_SYNC without state field fails."""
        msg = Message(type=MessageType.STATE_SYNC, payload={})
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("state" in e for e in result.errors)

    def test_validate_state_query_empty_valid(self, validator):
        """STATE_QUERY with no fields is valid."""
        msg = Message(type=MessageType.STATE_QUERY, payload={})
        result = validator.validate_message(msg)
        assert result.valid

    def test_validate_state_query_with_fields(self, validator):
        """STATE_QUERY with fields list is valid."""
        msg = Message(
            type=MessageType.STATE_QUERY,
            payload={"fields": ["burnout_level", "mode"]}
        )
        result = validator.validate_message(msg)
        assert result.valid

    def test_validate_agent_spawn_valid(self, validator):
        """Valid AGENT_SPAWN passes."""
        msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={
                "agent_type": "research",
                "task": "Find patterns in data",
            }
        )
        result = validator.validate_message(msg)
        assert result.valid

    def test_validate_agent_spawn_missing_required(self, validator):
        """AGENT_SPAWN without required fields fails."""
        msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={"agent_type": "research"}  # Missing task
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("task" in e for e in result.errors)

    def test_validate_agent_result_valid(self, validator):
        """Valid AGENT_RESULT passes."""
        msg = Message(
            type=MessageType.AGENT_RESULT,
            payload={
                "agent_id": "agent-123",
                "status": "success",
                "result": {"findings": []},
            }
        )
        result = validator.validate_message(msg)
        assert result.valid

    def test_validate_error_valid(self, validator):
        """Valid ERROR message passes."""
        msg = Message(
            type=MessageType.ERROR,
            payload={
                "code": -32600,
                "message": "Invalid request",
            }
        )
        result = validator.validate_message(msg)
        assert result.valid

    def test_validate_error_missing_code(self, validator):
        """ERROR without code fails."""
        msg = Message(
            type=MessageType.ERROR,
            payload={"message": "Error occurred"}
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("code" in e for e in result.errors)


class TestTypeValidation:
    """Tests for type checking."""

    @pytest.fixture
    def validator(self):
        return ProtocolValidator()

    def test_wrong_type_string(self, validator):
        """Wrong type for string field fails."""
        msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={
                "agent_type": 123,  # Should be string
                "task": "test",
            }
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("agent_type" in e and "type" in e for e in result.errors)

    def test_wrong_type_array(self, validator):
        """Wrong type for array field fails."""
        msg = Message(
            type=MessageType.STATE_QUERY,
            payload={
                "fields": "not-an-array"  # Should be array
            }
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("fields" in e for e in result.errors)

    def test_wrong_array_item_type(self, validator):
        """Wrong type for array items fails."""
        msg = Message(
            type=MessageType.STATE_QUERY,
            payload={
                "fields": ["burnout", 123, "mode"]  # 123 should be string
            }
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("fields[1]" in e for e in result.errors)

    def test_number_accepts_int_and_float(self, validator):
        """Number type accepts both int and float."""
        msg = Message(
            type=MessageType.HEARTBEAT,
            payload={
                "load": 0.5,  # float
                "uptime": 3600,  # int
            }
        )
        result = validator.validate_message(msg)
        assert result.valid


class TestStrictMode:
    """Tests for strict validation mode."""

    @pytest.fixture
    def strict_validator(self):
        return ProtocolValidator(strict=True)

    @pytest.fixture
    def lenient_validator(self):
        return ProtocolValidator(strict=False)

    def test_strict_rejects_unknown_fields(self, strict_validator):
        """Strict mode rejects unknown fields."""
        msg = Message(
            type=MessageType.HEARTBEAT,
            payload={
                "load": 0.5,
                "unknown_field": "value",
            }
        )
        result = strict_validator.validate_message(msg)

        assert not result.valid
        assert any("unknown_field" in e for e in result.errors)

    def test_lenient_allows_unknown_fields(self, lenient_validator):
        """Lenient mode allows unknown fields."""
        msg = Message(
            type=MessageType.HEARTBEAT,
            payload={
                "load": 0.5,
                "unknown_field": "value",
            }
        )
        result = lenient_validator.validate_message(msg)

        assert result.valid
        assert any("unknown_field" in w for w in result.warnings)


class TestCustomValidators:
    """Tests for custom validators."""

    @pytest.fixture
    def validator(self):
        v = ProtocolValidator()
        v.register_validator(MessageType.STATE_SYNC, v.validate_state_sync)
        v.register_validator(MessageType.AGENT_SPAWN, v.validate_agent_spawn)
        return v

    def test_state_sync_invalid_burnout(self, validator):
        """Invalid burnout level fails custom validation."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {"burnout_level": "purple"}  # Invalid
            }
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("burnout_level" in e for e in result.errors)

    def test_state_sync_invalid_mode(self, validator):
        """Invalid mode fails custom validation."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {"mode": "hyperfocused"}  # Invalid
            }
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("mode" in e for e in result.errors)

    def test_state_sync_valid_values(self, validator):
        """Valid state values pass custom validation."""
        msg = Message(
            type=MessageType.STATE_SYNC,
            payload={
                "state": {
                    "burnout_level": "green",
                    "mode": "focused",
                    "energy_level": "high",
                }
            }
        )
        result = validator.validate_message(msg)
        assert result.valid

    def test_agent_spawn_empty_type(self, validator):
        """Empty agent_type fails custom validation."""
        msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={
                "agent_type": "",
                "task": "do something",
            }
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("agent_type" in e for e in result.errors)

    def test_agent_spawn_negative_timeout(self, validator):
        """Negative timeout fails custom validation."""
        msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={
                "agent_type": "research",
                "task": "find patterns",
                "timeout": -5,
            }
        )
        result = validator.validate_message(msg)

        assert not result.valid
        assert any("timeout" in e for e in result.errors)


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_validate_message_function(self):
        """validate_message function works."""
        msg = Message(type=MessageType.HEARTBEAT, payload={})
        result = validate_message(msg)
        assert result.valid

    def test_validate_message_strict(self):
        """validate_message with strict mode."""
        msg = Message(
            type=MessageType.HEARTBEAT,
            payload={"unknown": "value"}
        )
        result = validate_message(msg, strict=True)
        assert not result.valid

    def test_is_valid_message_true(self):
        """is_valid_message returns True for valid."""
        msg = Message(type=MessageType.HEARTBEAT, payload={})
        assert is_valid_message(msg)

    def test_is_valid_message_false(self):
        """is_valid_message returns False for invalid."""
        msg = Message(type=MessageType.STATE_SYNC, payload={})
        assert not is_valid_message(msg)
