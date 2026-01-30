"""
Tests for JSON schema validation module.

Tests:
- Schema definitions exist and are valid
- ValidationError dataclass
- SchemaValidationResult dataclass
- Type validation
- Required property validation
- Array item validation
- String constraints (minLength, pattern)
- Number constraints (minimum)
- Enum validation
- Domain config validation
- Principles validation
- State file validation
- Agent result validation
"""

import pytest
from typing import Dict, Any

from otto.schemas import (
    DOMAIN_CONFIG_SCHEMA,
    PRINCIPLES_SCHEMA,
    STATE_FILE_SCHEMA,
    AGENT_RESULT_SCHEMA,
    ValidationError,
    SchemaValidationResult,
    validate_type,
    validate_against_schema,
    validate_json_schema,
    validate_domain_config,
    validate_principles,
    validate_state_file,
    validate_agent_result,
)


class TestSchemaDefinitions:
    """Test that schema definitions exist and have required structure."""

    def test_domain_config_schema_exists(self):
        """Should have domain config schema."""
        assert DOMAIN_CONFIG_SCHEMA is not None
        assert DOMAIN_CONFIG_SCHEMA["type"] == "object"
        assert "name" in DOMAIN_CONFIG_SCHEMA["required"]

    def test_principles_schema_exists(self):
        """Should have principles schema."""
        assert PRINCIPLES_SCHEMA is not None
        assert PRINCIPLES_SCHEMA["type"] == "object"
        assert "principles" in PRINCIPLES_SCHEMA["required"]

    def test_state_file_schema_exists(self):
        """Should have state file schema."""
        assert STATE_FILE_SCHEMA is not None
        assert "iteration" in STATE_FILE_SCHEMA["required"]
        assert "master_checksum" in STATE_FILE_SCHEMA["required"]

    def test_agent_result_schema_exists(self):
        """Should have agent result schema."""
        assert AGENT_RESULT_SCHEMA is not None
        assert "agent_name" in AGENT_RESULT_SCHEMA["required"]
        assert "status" in AGENT_RESULT_SCHEMA["required"]


class TestValidationError:
    """Test ValidationError dataclass."""

    def test_creation(self):
        """Should create validation error with fields."""
        error = ValidationError(
            path="field.subfield",
            message="Invalid value",
            expected="string",
            actual="integer"
        )

        assert error.path == "field.subfield"
        assert error.message == "Invalid value"
        assert error.expected == "string"
        assert error.actual == "integer"

    def test_optional_fields(self):
        """Should allow optional expected/actual."""
        error = ValidationError(path="field", message="Missing")

        assert error.expected is None
        assert error.actual is None


class TestSchemaValidationResult:
    """Test SchemaValidationResult dataclass."""

    def test_valid_result(self):
        """Should create valid result with no errors."""
        result = SchemaValidationResult(valid=True, errors=[])

        assert result.valid is True
        assert result.errors == []

    def test_invalid_result(self):
        """Should create invalid result with errors."""
        errors = [
            ValidationError(path="field", message="Error 1"),
            ValidationError(path="other", message="Error 2"),
        ]
        result = SchemaValidationResult(valid=False, errors=errors)

        assert result.valid is False
        assert len(result.errors) == 2

    def test_error_messages(self):
        """Should return list of error messages."""
        errors = [
            ValidationError(path="a", message="Message 1"),
            ValidationError(path="b", message="Message 2"),
        ]
        result = SchemaValidationResult(valid=False, errors=errors)

        messages = result.error_messages
        assert messages == ["Message 1", "Message 2"]


class TestValidateType:
    """Test type validation."""

    def test_string_valid(self):
        """Should pass for valid string."""
        errors = validate_type("hello", "string", "field")
        assert len(errors) == 0

    def test_string_invalid(self):
        """Should fail for non-string."""
        errors = validate_type(123, "string", "field")
        assert len(errors) == 1
        assert "string" in errors[0].expected

    def test_integer_valid(self):
        """Should pass for valid integer."""
        errors = validate_type(42, "integer", "field")
        assert len(errors) == 0

    def test_number_accepts_float(self):
        """Should accept float for number type."""
        errors = validate_type(3.14, "number", "field")
        assert len(errors) == 0

    def test_number_accepts_int(self):
        """Should accept int for number type."""
        errors = validate_type(42, "number", "field")
        assert len(errors) == 0

    def test_boolean_valid(self):
        """Should pass for valid boolean."""
        errors = validate_type(True, "boolean", "field")
        assert len(errors) == 0

    def test_array_valid(self):
        """Should pass for valid array."""
        errors = validate_type([1, 2, 3], "array", "field")
        assert len(errors) == 0

    def test_object_valid(self):
        """Should pass for valid object."""
        errors = validate_type({"key": "value"}, "object", "field")
        assert len(errors) == 0

    def test_null_valid(self):
        """Should pass for null."""
        errors = validate_type(None, "null", "field")
        assert len(errors) == 0

    def test_union_type(self):
        """Should accept union types."""
        errors = validate_type("string", ["string", "null"], "field")
        assert len(errors) == 0

        errors = validate_type(None, ["string", "null"], "field")
        assert len(errors) == 0

    def test_union_type_fail(self):
        """Should fail when not matching any union type."""
        errors = validate_type(123, ["string", "null"], "field")
        assert len(errors) == 1


class TestValidateAgainstSchema:
    """Test schema validation."""

    def test_simple_object(self):
        """Should validate simple object."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            }
        }
        data = {"name": "test"}

        errors = validate_against_schema(data, schema)
        assert len(errors) == 0

    def test_required_missing(self):
        """Should fail when required property missing."""
        schema = {
            "type": "object",
            "required": ["name", "value"],
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "integer"}
            }
        }
        data = {"name": "test"}  # Missing "value"

        errors = validate_against_schema(data, schema)
        assert len(errors) == 1
        assert "value" in errors[0].message

    def test_nested_object(self):
        """Should validate nested objects."""
        schema = {
            "type": "object",
            "properties": {
                "outer": {
                    "type": "object",
                    "properties": {
                        "inner": {"type": "string"}
                    }
                }
            }
        }
        data = {"outer": {"inner": 123}}  # Wrong type

        errors = validate_against_schema(data, schema)
        assert len(errors) == 1
        assert "outer.inner" in errors[0].path

    def test_array_items(self):
        """Should validate array items."""
        schema = {
            "type": "array",
            "items": {"type": "string"}
        }
        data = ["a", "b", 123, "d"]  # Third item is wrong type

        errors = validate_against_schema(data, schema)
        assert len(errors) == 1
        assert "[2]" in errors[0].path

    def test_min_length(self):
        """Should validate minLength constraint."""
        schema = {
            "type": "string",
            "minLength": 3
        }

        errors = validate_against_schema("ab", schema)
        assert len(errors) == 1

        errors = validate_against_schema("abc", schema)
        assert len(errors) == 0

    def test_pattern(self):
        """Should validate pattern constraint."""
        schema = {
            "type": "string",
            "pattern": "^[a-f0-9]+$"
        }

        errors = validate_against_schema("abc123", schema)
        assert len(errors) == 0

        errors = validate_against_schema("xyz", schema)
        assert len(errors) == 1

    def test_minimum(self):
        """Should validate minimum constraint."""
        schema = {
            "type": "integer",
            "minimum": 0
        }

        errors = validate_against_schema(-1, schema)
        assert len(errors) == 1

        errors = validate_against_schema(0, schema)
        assert len(errors) == 0

    def test_enum(self):
        """Should validate enum constraint."""
        schema = {
            "type": "string",
            "enum": ["a", "b", "c"]
        }

        errors = validate_against_schema("b", schema)
        assert len(errors) == 0

        errors = validate_against_schema("x", schema)
        assert len(errors) == 1


class TestValidateJsonSchema:
    """Test validate_json_schema function."""

    def test_returns_result(self):
        """Should return SchemaValidationResult."""
        schema = {"type": "object"}
        result = validate_json_schema({}, schema)

        assert isinstance(result, SchemaValidationResult)

    def test_valid_data(self):
        """Should return valid=True for valid data."""
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}}
        }
        result = validate_json_schema({"name": "test"}, schema)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_data(self):
        """Should return valid=False for invalid data."""
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}}
        }
        result = validate_json_schema({}, schema)

        assert result.valid is False
        assert len(result.errors) > 0


class TestValidateDomainConfig:
    """Test domain config validation."""

    def test_valid_minimal(self):
        """Should accept minimal valid config."""
        config = {"name": "test_domain"}

        result = validate_domain_config(config)

        assert result.valid is True

    def test_valid_full(self):
        """Should accept full config."""
        config = {
            "name": "vfx",
            "description": "VFX domain",
            "keywords": ["render", "simulation"],
            "specialists": [
                {
                    "name": "lighting",
                    "keywords": ["hdri", "exposure"],
                    "tools": ["karma", "mantra"]
                }
            ]
        }

        result = validate_domain_config(config)

        assert result.valid is True

    def test_missing_name(self):
        """Should reject config without name."""
        config = {"description": "No name"}

        result = validate_domain_config(config)

        assert result.valid is False

    def test_empty_name(self):
        """Should reject empty name."""
        config = {"name": ""}

        result = validate_domain_config(config)

        assert result.valid is False


class TestValidatePrinciples:
    """Test principles file validation."""

    def test_valid_principles(self):
        """Should accept valid principles."""
        data = {
            "principles": [
                {"id": "safety", "name": "Safety First"},
                {"id": "quality", "name": "Quality Matters", "priority": 1}
            ]
        }

        result = validate_principles(data)

        assert result.valid is True

    def test_missing_principles(self):
        """Should reject missing principles array."""
        data = {"recovery_protocol": {}}

        result = validate_principles(data)

        assert result.valid is False

    def test_principle_missing_id(self):
        """Should reject principle without id."""
        data = {
            "principles": [
                {"name": "Missing ID"}
            ]
        }

        result = validate_principles(data)

        assert result.valid is False


class TestValidateStateFile:
    """Test state file validation."""

    def test_valid_state(self):
        """Should accept valid state file."""
        state = {
            "iteration": 1,
            "timestamp": 1234567890.0,
            "master_checksum": "abc123def456"
        }

        result = validate_state_file(state)

        assert result.valid is True

    def test_valid_full_state(self):
        """Should accept full state file."""
        state = {
            "iteration": 5,
            "task": "process data",
            "timestamp": 1234567890.0,
            "total_execution_time_ms": 1500.5,
            "agents_executed": 3,
            "agents_succeeded": 3,
            "master_checksum": "abc123",
            "reproducibility_proof": "hash_chain",
            "agent_results": {
                "agent1": {"output": "result"}
            },
            "agent_checksums": {
                "agent1": "def456"
            }
        }

        result = validate_state_file(state)

        assert result.valid is True

    def test_missing_required(self):
        """Should reject missing required fields."""
        state = {"iteration": 1}  # Missing timestamp and checksum

        result = validate_state_file(state)

        assert result.valid is False

    def test_negative_iteration(self):
        """Should reject negative iteration."""
        state = {
            "iteration": -1,
            "timestamp": 123.0,
            "master_checksum": "abc"
        }

        result = validate_state_file(state)

        assert result.valid is False

    def test_invalid_checksum_pattern(self):
        """Should reject invalid checksum pattern."""
        state = {
            "iteration": 1,
            "timestamp": 123.0,
            "master_checksum": "not-hex-XYZ!"
        }

        result = validate_state_file(state)

        assert result.valid is False


class TestValidateAgentResult:
    """Test agent result validation."""

    def test_valid_result(self):
        """Should accept valid agent result."""
        result_data = {
            "agent_name": "moe_router",
            "status": "completed",
            "checksum": "abc123"
        }

        result = validate_agent_result(result_data)

        assert result.valid is True

    def test_valid_full_result(self):
        """Should accept full agent result."""
        result_data = {
            "agent_name": "echo_curator",
            "status": "completed",
            "output": {"data": "value"},
            "checksum": "def456",
            "execution_time": 150.5,
            "error": None
        }

        result = validate_agent_result(result_data)

        assert result.valid is True

    def test_invalid_status(self):
        """Should reject invalid status."""
        result_data = {
            "agent_name": "agent",
            "status": "unknown_status",
            "checksum": "abc"
        }

        result = validate_agent_result(result_data)

        assert result.valid is False

    def test_missing_required(self):
        """Should reject missing required fields."""
        result_data = {
            "agent_name": "agent"
            # Missing status and checksum
        }

        result = validate_agent_result(result_data)

        assert result.valid is False

