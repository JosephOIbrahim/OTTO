"""
Protocol Validator
==================

Validates message payloads against defined schemas.

Provides:
- Required field checking
- Type validation
- Enum value validation
- Custom validation rules

Determinism:
- Fixed schema definitions (never change at runtime)
- Deterministic validation order
- Consistent error reporting
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import logging

from .message_types import Message, MessageType, PAYLOAD_SCHEMAS

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    Result of message validation.

    Attributes:
        valid: Whether the message is valid
        errors: List of validation errors
        warnings: List of validation warnings
    """
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """ValidationResult is truthy if valid."""
        return self.valid

    def add_error(self, error: str) -> None:
        """Add an error and mark as invalid."""
        self.errors.append(error)
        self.valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning (doesn't affect validity)."""
        self.warnings.append(warning)

    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """Merge another result into this one."""
        self.valid = self.valid and other.valid
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        return self


class ProtocolValidator:
    """
    Validates messages against protocol schemas.

    Checks:
    - Required fields are present
    - Field types match schema
    - Enum values are valid
    - Custom validation rules per message type

    Example:
        >>> validator = ProtocolValidator()
        >>> msg = Message(type=MessageType.STATE_SYNC, payload={"state": {}})
        >>> result = validator.validate_message(msg)
        >>> if not result:
        ...     print(result.errors)
    """

    # Type mapping for validation
    TYPE_MAP = {
        "string": str,
        "object": dict,
        "array": list,
        "boolean": bool,
        "number": (int, float),
        "integer": int,
    }

    def __init__(self, strict: bool = False):
        """
        Initialize validator.

        Args:
            strict: If True, treat unknown fields as errors
        """
        self.strict = strict
        self._custom_validators: Dict[MessageType, callable] = {}

    def validate_message(self, message: Message) -> ValidationResult:
        """
        Validate a message against its schema.

        Args:
            message: Message to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(valid=True)

        # Check message type has schema
        if message.type not in PAYLOAD_SCHEMAS:
            result.add_error(f"Unknown message type: {message.type}")
            return result

        schema = PAYLOAD_SCHEMAS[message.type]

        # Validate required fields
        result.merge(self._validate_required(message.payload, schema))

        # Validate field types
        result.merge(self._validate_types(message.payload, schema))

        # Check for unknown fields (always warns, strict mode also errors)
        result.merge(self._validate_no_unknown(message.payload, schema))

        # Run custom validators
        if message.type in self._custom_validators:
            custom_result = self._custom_validators[message.type](message)
            result.merge(custom_result)

        return result

    def _validate_required(
        self,
        payload: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> ValidationResult:
        """Validate required fields are present."""
        result = ValidationResult(valid=True)

        required = schema.get("required", [])
        for field_name in required:
            if field_name not in payload:
                result.add_error(f"Missing required field: {field_name}")

        return result

    def _validate_types(
        self,
        payload: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> ValidationResult:
        """Validate field types match schema."""
        result = ValidationResult(valid=True)

        properties = schema.get("properties", {})
        for field_name, value in payload.items():
            if field_name not in properties:
                continue

            field_spec = properties[field_name]
            expected_type = field_spec.get("type")

            if expected_type:
                if not self._check_type(value, expected_type):
                    result.add_error(
                        f"Field '{field_name}' has wrong type: "
                        f"expected {expected_type}, got {type(value).__name__}"
                    )

            # Validate enum values
            if "enum" in field_spec:
                if value not in field_spec["enum"]:
                    result.add_error(
                        f"Field '{field_name}' has invalid value: "
                        f"'{value}' not in {field_spec['enum']}"
                    )

            # Validate array items
            if expected_type == "array" and "items" in field_spec:
                items_result = self._validate_array_items(
                    field_name, value, field_spec["items"]
                )
                result.merge(items_result)

        return result

    def _validate_array_items(
        self,
        field_name: str,
        array: list,
        items_spec: Dict[str, Any]
    ) -> ValidationResult:
        """Validate array item types."""
        result = ValidationResult(valid=True)

        expected_type = items_spec.get("type")
        if not expected_type:
            return result

        for i, item in enumerate(array):
            if not self._check_type(item, expected_type):
                result.add_error(
                    f"Field '{field_name}[{i}]' has wrong type: "
                    f"expected {expected_type}, got {type(item).__name__}"
                )

        return result

    def _validate_no_unknown(
        self,
        payload: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> ValidationResult:
        """Check for unknown fields (strict mode)."""
        result = ValidationResult(valid=True)

        known_fields: Set[str] = set()
        known_fields.update(schema.get("required", []))
        known_fields.update(schema.get("optional", []))
        known_fields.update(schema.get("properties", {}).keys())

        for field_name in payload:
            if field_name not in known_fields:
                result.add_warning(f"Unknown field: {field_name}")
                if self.strict:
                    result.add_error(f"Unknown field not allowed: {field_name}")

        return result

    def _check_type(self, value: Any, expected: str) -> bool:
        """Check if value matches expected type."""
        expected_types = self.TYPE_MAP.get(expected)
        if expected_types is None:
            return True  # Unknown type, pass
        return isinstance(value, expected_types)

    def register_validator(
        self,
        msg_type: MessageType,
        validator: callable
    ) -> None:
        """
        Register a custom validator for a message type.

        Args:
            msg_type: Message type to validate
            validator: Callable that takes Message and returns ValidationResult
        """
        self._custom_validators[msg_type] = validator

    def validate_state_sync(self, message: Message) -> ValidationResult:
        """Custom validator for STATE_SYNC messages."""
        result = ValidationResult(valid=True)

        state = message.payload.get("state", {})
        if not isinstance(state, dict):
            result.add_error("state must be a dictionary")
            return result

        # Validate known state fields
        valid_burnout = {"green", "yellow", "orange", "red"}
        if "burnout_level" in state:
            if state["burnout_level"] not in valid_burnout:
                result.add_error(
                    f"Invalid burnout_level: {state['burnout_level']}"
                )

        valid_modes = {"focused", "exploring", "teaching", "recovery"}
        if "mode" in state:
            if state["mode"] not in valid_modes:
                result.add_error(f"Invalid mode: {state['mode']}")

        valid_energy = {"high", "medium", "low", "depleted"}
        if "energy_level" in state:
            if state["energy_level"] not in valid_energy:
                result.add_error(f"Invalid energy_level: {state['energy_level']}")

        return result

    def validate_agent_spawn(self, message: Message) -> ValidationResult:
        """Custom validator for AGENT_SPAWN messages."""
        result = ValidationResult(valid=True)

        agent_type = message.payload.get("agent_type", "")
        if not agent_type:
            result.add_error("agent_type cannot be empty")

        task = message.payload.get("task", "")
        if not task:
            result.add_error("task cannot be empty")

        # Validate timeout if provided
        timeout = message.payload.get("timeout")
        if timeout is not None:
            if not isinstance(timeout, (int, float)):
                result.add_error("timeout must be a number")
            elif timeout <= 0:
                result.add_error("timeout must be positive")

        return result


def validate_message(message: Message, strict: bool = False) -> ValidationResult:
    """
    Convenience function to validate a message.

    Args:
        message: Message to validate
        strict: If True, reject unknown fields

    Returns:
        ValidationResult
    """
    validator = ProtocolValidator(strict=strict)
    return validator.validate_message(message)


def is_valid_message(message: Message) -> bool:
    """Check if a message is valid."""
    return validate_message(message).valid


__all__ = [
    "ValidationResult",
    "ProtocolValidator",
    "validate_message",
    "is_valid_message",
]
