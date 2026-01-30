"""
Input validation and sanitization for Framework Orchestrator.

Provides:
- Task input validation
- Path sanitization for logging
- Context validation
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    valid: bool
    sanitized: Optional[str] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {', '.join(errors)}")


def validate_task(
    task: str,
    max_length: int = 10000,
    allow_empty: bool = False
) -> ValidationResult:
    """
    Validate and sanitize a task string.

    Checks:
    - Not None
    - Length within limits
    - No null bytes
    - Whitespace normalized

    Args:
        task: Task string to validate
        max_length: Maximum allowed length (default: 10000)
        allow_empty: Whether to allow empty tasks (default: False)

    Returns:
        ValidationResult with valid flag, sanitized string, and any errors
    """
    errors = []

    # Check for None
    if task is None:
        errors.append("Task cannot be None")
        return ValidationResult(valid=False, errors=errors)

    # Check type
    if not isinstance(task, str):
        errors.append(f"Task must be string, got {type(task).__name__}")
        return ValidationResult(valid=False, errors=errors)

    # Check for null bytes (potential security issue)
    if '\x00' in task:
        errors.append("Task contains null bytes")
        return ValidationResult(valid=False, errors=errors)

    # Normalize whitespace
    sanitized = ' '.join(task.split())

    # Check empty
    if not allow_empty and not sanitized:
        errors.append("Task cannot be empty")
        return ValidationResult(valid=False, sanitized=sanitized, errors=errors)

    # Check length (after normalization)
    if len(sanitized) > max_length:
        errors.append(f"Task exceeds maximum length ({len(sanitized)} > {max_length})")
        return ValidationResult(valid=False, sanitized=sanitized, errors=errors)

    return ValidationResult(valid=True, sanitized=sanitized, errors=[])


def sanitize_path_for_logging(
    path: Path,
    home_replacement: str = "~"
) -> str:
    """
    Sanitize a path for safe logging.

    Replaces home directory with ~ to prevent path disclosure.

    Args:
        path: Path to sanitize
        home_replacement: String to replace home directory with

    Returns:
        Sanitized path string
    """
    path_str = str(path)
    home = str(Path.home())

    if path_str.startswith(home):
        return home_replacement + path_str[len(home):]

    return path_str


def sanitize_error_message(
    message: str,
    paths_to_sanitize: Optional[List[Path]] = None
) -> str:
    """
    Sanitize an error message to prevent sensitive data disclosure.

    Args:
        message: Error message to sanitize
        paths_to_sanitize: Additional paths to sanitize (besides home)

    Returns:
        Sanitized error message
    """
    result = message

    # Always sanitize home directory
    home = str(Path.home())
    result = result.replace(home, "~")

    # Sanitize additional paths
    if paths_to_sanitize:
        for path in paths_to_sanitize:
            result = result.replace(str(path), sanitize_path_for_logging(path))

    return result


def validate_context(
    context: Dict[str, Any],
    required_keys: Optional[List[str]] = None,
    max_depth: int = 10
) -> ValidationResult:
    """
    Validate a context dictionary.

    Args:
        context: Context dictionary to validate
        required_keys: Keys that must be present
        max_depth: Maximum nesting depth

    Returns:
        ValidationResult
    """
    errors = []

    if context is None:
        errors.append("Context cannot be None")
        return ValidationResult(valid=False, errors=errors)

    if not isinstance(context, dict):
        errors.append(f"Context must be dict, got {type(context).__name__}")
        return ValidationResult(valid=False, errors=errors)

    # Check required keys
    if required_keys:
        missing = [k for k in required_keys if k not in context]
        if missing:
            errors.append(f"Missing required keys: {', '.join(missing)}")

    # Check depth
    def check_depth(obj, current_depth):
        if current_depth > max_depth:
            return False
        if isinstance(obj, dict):
            return all(check_depth(v, current_depth + 1) for v in obj.values())
        if isinstance(obj, (list, tuple)):
            return all(check_depth(v, current_depth + 1) for v in obj)
        return True

    if not check_depth(context, 0):
        errors.append(f"Context exceeds maximum nesting depth ({max_depth})")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_agent_name(name: str) -> ValidationResult:
    """
    Validate an agent name.

    Agent names must:
    - Be non-empty
    - Contain only alphanumeric characters, underscores, and hyphens
    - Start with a letter or underscore
    - Be <= 64 characters

    Args:
        name: Agent name to validate

    Returns:
        ValidationResult
    """
    errors = []

    if not name:
        errors.append("Agent name cannot be empty")
        return ValidationResult(valid=False, errors=errors)

    if len(name) > 64:
        errors.append(f"Agent name too long ({len(name)} > 64)")

    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', name):
        errors.append(
            "Agent name must start with letter/underscore and contain only "
            "alphanumeric characters, underscores, and hyphens"
        )

    return ValidationResult(
        valid=len(errors) == 0,
        sanitized=name,
        errors=errors
    )


def validate_domain_config(config: Dict[str, Any]) -> ValidationResult:
    """
    Validate a domain configuration dictionary.

    Required structure:
    - name: string
    - keywords: list of strings
    - specialists: list of dicts with 'name' and 'keywords'

    Args:
        config: Domain configuration to validate

    Returns:
        ValidationResult
    """
    errors = []

    if not isinstance(config, dict):
        errors.append(f"Config must be dict, got {type(config).__name__}")
        return ValidationResult(valid=False, errors=errors)

    # Check required fields
    if 'name' not in config:
        errors.append("Missing required field: name")
    elif not isinstance(config['name'], str):
        errors.append("Field 'name' must be string")

    if 'keywords' in config:
        if not isinstance(config['keywords'], list):
            errors.append("Field 'keywords' must be list")
        elif not all(isinstance(k, str) for k in config['keywords']):
            errors.append("All keywords must be strings")

    if 'specialists' in config:
        if not isinstance(config['specialists'], list):
            errors.append("Field 'specialists' must be list")
        else:
            for i, spec in enumerate(config['specialists']):
                if not isinstance(spec, dict):
                    errors.append(f"Specialist {i} must be dict")
                elif 'name' not in spec:
                    errors.append(f"Specialist {i} missing 'name'")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def truncate_for_logging(
    text: str,
    max_length: int = 200,
    suffix: str = "..."
) -> str:
    """
    Truncate text for safe logging.

    Args:
        text: Text to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix
