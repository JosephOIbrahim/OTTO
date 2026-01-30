"""
Tests for validation module.
"""

import pytest
from pathlib import Path

from otto.validation import (
    validate_task,
    validate_context,
    validate_agent_name,
    validate_domain_config,
    sanitize_path_for_logging,
    sanitize_error_message,
    truncate_for_logging,
    ValidationResult,
    ValidationError,
)


class TestValidateTask:
    """Tests for validate_task function."""

    def test_valid_task(self):
        """Should validate a normal task."""
        result = validate_task("Analyze this code")

        assert result.valid is True
        assert result.sanitized == "Analyze this code"
        assert result.errors == []

    def test_whitespace_normalization(self):
        """Should normalize whitespace."""
        result = validate_task("  Multiple   spaces   here  ")

        assert result.valid is True
        assert result.sanitized == "Multiple spaces here"

    def test_rejects_none(self):
        """Should reject None input."""
        result = validate_task(None)

        assert result.valid is False
        assert "cannot be None" in result.errors[0]

    def test_rejects_empty(self):
        """Should reject empty task by default."""
        result = validate_task("")

        assert result.valid is False
        assert "cannot be empty" in result.errors[0]

    def test_allows_empty_when_configured(self):
        """Should allow empty task when allow_empty=True."""
        result = validate_task("", allow_empty=True)

        assert result.valid is True
        assert result.sanitized == ""

    def test_rejects_null_bytes(self):
        """Should reject tasks with null bytes."""
        result = validate_task("Hello\x00World")

        assert result.valid is False
        assert "null bytes" in result.errors[0]

    def test_rejects_too_long(self):
        """Should reject tasks exceeding max length."""
        long_task = "x" * 11000
        result = validate_task(long_task, max_length=10000)

        assert result.valid is False
        assert "maximum length" in result.errors[0]

    def test_accepts_at_max_length(self):
        """Should accept tasks at exactly max length."""
        task = "x" * 100
        result = validate_task(task, max_length=100)

        assert result.valid is True


class TestValidateContext:
    """Tests for validate_context function."""

    def test_valid_context(self):
        """Should validate a normal context."""
        result = validate_context({"seed": 42, "mode": "test"})

        assert result.valid is True

    def test_rejects_none(self):
        """Should reject None context."""
        result = validate_context(None)

        assert result.valid is False
        assert "cannot be None" in result.errors[0]

    def test_rejects_non_dict(self):
        """Should reject non-dict context."""
        result = validate_context("not a dict")

        assert result.valid is False
        assert "must be dict" in result.errors[0]

    def test_checks_required_keys(self):
        """Should check for required keys."""
        result = validate_context(
            {"a": 1},
            required_keys=["a", "b", "c"]
        )

        assert result.valid is False
        assert "Missing required keys" in result.errors[0]
        assert "b" in result.errors[0]
        assert "c" in result.errors[0]

    def test_checks_max_depth(self):
        """Should reject deeply nested contexts."""
        # Create deeply nested dict
        nested = {"level": 0}
        current = nested
        for i in range(15):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        result = validate_context(nested, max_depth=10)

        assert result.valid is False
        assert "depth" in result.errors[0]


class TestValidateAgentName:
    """Tests for validate_agent_name function."""

    def test_valid_name(self):
        """Should validate a normal agent name."""
        result = validate_agent_name("echo_curator")

        assert result.valid is True

    def test_valid_name_with_hyphen(self):
        """Should allow hyphens."""
        result = validate_agent_name("my-agent-name")

        assert result.valid is True

    def test_rejects_empty(self):
        """Should reject empty name."""
        result = validate_agent_name("")

        assert result.valid is False

    def test_rejects_too_long(self):
        """Should reject names over 64 chars."""
        result = validate_agent_name("x" * 65)

        assert result.valid is False
        assert "too long" in result.errors[0]

    def test_rejects_invalid_start(self):
        """Should reject names starting with number."""
        result = validate_agent_name("123agent")

        assert result.valid is False

    def test_rejects_special_chars(self):
        """Should reject special characters."""
        result = validate_agent_name("agent@name")

        assert result.valid is False


class TestValidateDomainConfig:
    """Tests for validate_domain_config function."""

    def test_valid_config(self):
        """Should validate a proper domain config."""
        config = {
            "name": "vfx",
            "keywords": ["houdini", "nuke"],
            "specialists": [
                {"name": "lighting", "keywords": ["light", "render"]}
            ]
        }

        result = validate_domain_config(config)

        assert result.valid is True

    def test_requires_name(self):
        """Should require name field."""
        config = {"keywords": ["test"]}

        result = validate_domain_config(config)

        assert result.valid is False
        assert "name" in result.errors[0].lower()

    def test_validates_keywords_type(self):
        """Should validate keywords is a list."""
        config = {
            "name": "test",
            "keywords": "not a list"
        }

        result = validate_domain_config(config)

        assert result.valid is False
        assert "list" in result.errors[0].lower()


class TestSanitizePath:
    """Tests for path sanitization functions."""

    def test_sanitize_home_path(self):
        """Should replace home directory with ~."""
        home = Path.home()
        test_path = home / "Documents" / "secret.txt"

        result = sanitize_path_for_logging(test_path)

        assert str(home) not in result
        assert result.startswith("~")

    def test_preserves_non_home_path(self):
        """Should preserve paths not under home."""
        test_path = Path("/var/log/app.log")

        result = sanitize_path_for_logging(test_path)

        assert result == str(test_path)

    def test_sanitize_error_message(self):
        """Should sanitize paths in error messages."""
        home = str(Path.home())
        message = f"Failed to read {home}/secret/file.txt"

        result = sanitize_error_message(message)

        assert home not in result
        assert "~/secret/file.txt" in result


class TestTruncateForLogging:
    """Tests for truncate_for_logging function."""

    def test_short_text_unchanged(self):
        """Should not truncate short text."""
        text = "Short text"

        result = truncate_for_logging(text, max_length=100)

        assert result == text

    def test_truncates_long_text(self):
        """Should truncate and add suffix."""
        text = "This is a very long text that should be truncated"

        result = truncate_for_logging(text, max_length=20)

        assert len(result) == 20
        assert result.endswith("...")

    def test_custom_suffix(self):
        """Should use custom suffix."""
        text = "Long text to truncate"

        result = truncate_for_logging(text, max_length=15, suffix="[...]")

        assert result.endswith("[...]")

    def test_exact_length(self):
        """Should handle exact length text."""
        text = "Exactly 10"  # 10 chars

        result = truncate_for_logging(text, max_length=10)

        assert result == text
