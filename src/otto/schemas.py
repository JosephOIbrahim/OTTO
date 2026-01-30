"""
JSON Schema definitions and validation for Framework Orchestrator.

Provides schemas for:
- Domain configurations
- Principles files
- State files
- Agent results
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# Schema definitions using a simplified format
# (jsonschema library can be added later for full validation)

DOMAIN_CONFIG_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {
            "type": "string",
            "minLength": 1,
            "description": "Domain name"
        },
        "description": {
            "type": "string",
            "description": "Domain description"
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Keywords for routing"
        },
        "specialists": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "analysis_focus": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "description": "Domain specialists"
        }
    }
}

PRINCIPLES_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["principles"],
    "properties": {
        "principles": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "integer", "minimum": 1},
                    "triggers": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "description": "Constitutional principles"
        },
        "recovery_protocol": {
            "type": "object",
            "properties": {
                "triggers": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
    }
}

STATE_FILE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["iteration", "timestamp", "master_checksum"],
    "properties": {
        "iteration": {
            "type": "integer",
            "minimum": 0
        },
        "task": {
            "type": "string"
        },
        "timestamp": {
            "type": "number"
        },
        "total_execution_time_ms": {
            "type": "number",
            "minimum": 0
        },
        "agents_executed": {
            "type": "integer",
            "minimum": 0
        },
        "agents_succeeded": {
            "type": "integer",
            "minimum": 0
        },
        "master_checksum": {
            "type": "string",
            "pattern": "^[a-f0-9]+$"
        },
        "reproducibility_proof": {
            "type": "string"
        },
        "agent_results": {
            "type": "object",
            "additionalProperties": {
                "type": "object"
            }
        },
        "agent_checksums": {
            "type": "object",
            "additionalProperties": {
                "type": "string"
            }
        }
    }
}

AGENT_RESULT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["agent_name", "status", "checksum"],
    "properties": {
        "agent_name": {
            "type": "string"
        },
        "status": {
            "type": "string",
            "enum": ["pending", "running", "completed", "failed"]
        },
        "output": {
            "type": "object"
        },
        "checksum": {
            "type": "string",
            "pattern": "^[a-f0-9]+$"
        },
        "execution_time": {
            "type": "number",
            "minimum": 0
        },
        "error": {
            "type": ["string", "null"]
        }
    }
}


@dataclass
class ValidationError:
    """Details about a validation error."""
    path: str  # JSON path to the error (e.g., "specialists[0].name")
    message: str  # Error message
    expected: Optional[str] = None  # Expected value/type
    actual: Optional[str] = None  # Actual value/type


@dataclass
class SchemaValidationResult:
    """Result of schema validation."""
    valid: bool
    errors: List[ValidationError]

    @property
    def error_messages(self) -> List[str]:
        """Get list of error messages."""
        return [e.message for e in self.errors]


def validate_type(value: Any, expected_type: str, path: str) -> List[ValidationError]:
    """Validate a value against an expected type."""
    errors = []

    type_map = {
        'string': str,
        'integer': int,
        'number': (int, float),
        'boolean': bool,
        'array': list,
        'object': dict,
        'null': type(None)
    }

    # Handle union types like ["string", "null"]
    if isinstance(expected_type, list):
        valid = any(
            isinstance(value, type_map.get(t, object))
            for t in expected_type
        )
        if not valid:
            errors.append(ValidationError(
                path=path,
                message=f"Expected one of {expected_type}, got {type(value).__name__}",
                expected=str(expected_type),
                actual=type(value).__name__
            ))
        return errors

    expected_python_type = type_map.get(expected_type)
    if expected_python_type and not isinstance(value, expected_python_type):
        errors.append(ValidationError(
            path=path,
            message=f"Expected {expected_type}, got {type(value).__name__}",
            expected=expected_type,
            actual=type(value).__name__
        ))

    return errors


def validate_against_schema(
    data: Any,
    schema: Dict[str, Any],
    path: str = ""
) -> List[ValidationError]:
    """
    Validate data against a JSON schema.

    This is a simplified validator that handles common cases.
    For full JSON Schema support, use the jsonschema library.

    Args:
        data: Data to validate
        schema: JSON schema
        path: Current path in the data structure

    Returns:
        List of validation errors
    """
    errors = []

    # Get schema type
    schema_type = schema.get('type')

    # Handle type validation
    if schema_type:
        errors.extend(validate_type(data, schema_type, path))
        if errors:
            return errors  # Stop if type is wrong

    # Handle required properties for objects
    if schema_type == 'object' and isinstance(data, dict):
        required = schema.get('required', [])
        for prop in required:
            if prop not in data:
                errors.append(ValidationError(
                    path=f"{path}.{prop}" if path else prop,
                    message=f"Missing required property: {prop}"
                ))

        # Validate properties
        properties = schema.get('properties', {})
        for prop_name, prop_schema in properties.items():
            if prop_name in data:
                prop_path = f"{path}.{prop_name}" if path else prop_name
                errors.extend(validate_against_schema(
                    data[prop_name],
                    prop_schema,
                    prop_path
                ))

    # Handle array items
    if schema_type == 'array' and isinstance(data, list):
        items_schema = schema.get('items')
        if items_schema:
            for i, item in enumerate(data):
                item_path = f"{path}[{i}]"
                errors.extend(validate_against_schema(
                    item,
                    items_schema,
                    item_path
                ))

    # Handle string constraints
    if schema_type == 'string' and isinstance(data, str):
        min_length = schema.get('minLength')
        if min_length and len(data) < min_length:
            errors.append(ValidationError(
                path=path,
                message=f"String too short (min {min_length})",
                expected=f">= {min_length} chars",
                actual=f"{len(data)} chars"
            ))

        pattern = schema.get('pattern')
        if pattern:
            import re
            if not re.match(pattern, data):
                errors.append(ValidationError(
                    path=path,
                    message=f"String does not match pattern: {pattern}"
                ))

    # Handle number constraints
    if schema_type in ('integer', 'number') and isinstance(data, (int, float)):
        minimum = schema.get('minimum')
        if minimum is not None and data < minimum:
            errors.append(ValidationError(
                path=path,
                message=f"Value {data} is less than minimum {minimum}"
            ))

    # Handle enum
    enum_values = schema.get('enum')
    if enum_values and data not in enum_values:
        errors.append(ValidationError(
            path=path,
            message=f"Value must be one of {enum_values}",
            actual=str(data)
        ))

    return errors


def validate_json_schema(
    data: Any,
    schema: Dict[str, Any]
) -> SchemaValidationResult:
    """
    Validate data against a JSON schema.

    Args:
        data: Data to validate
        schema: JSON schema definition

    Returns:
        SchemaValidationResult with valid flag and any errors
    """
    errors = validate_against_schema(data, schema)
    return SchemaValidationResult(valid=len(errors) == 0, errors=errors)


def validate_domain_config(data: Any) -> SchemaValidationResult:
    """Validate a domain configuration."""
    return validate_json_schema(data, DOMAIN_CONFIG_SCHEMA)


def validate_principles(data: Any) -> SchemaValidationResult:
    """Validate a principles file."""
    return validate_json_schema(data, PRINCIPLES_SCHEMA)


def validate_state_file(data: Any) -> SchemaValidationResult:
    """Validate an orchestrator state file."""
    return validate_json_schema(data, STATE_FILE_SCHEMA)


def validate_agent_result(data: Any) -> SchemaValidationResult:
    """Validate an agent result."""
    return validate_json_schema(data, AGENT_RESULT_SCHEMA)
