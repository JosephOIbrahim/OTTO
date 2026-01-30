"""
Tests for logging setup module.

Tests:
- JSON formatter output
- Text formatter output
- Correlation ID injection
- Context adapter
- Logger configuration
"""

import json
import logging
import pytest
from unittest.mock import patch

from otto.logging_setup import (
    JSONFormatter,
    TextFormatter,
    ContextAdapter,
    setup_logging,
    get_logger,
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
)


class TestCorrelationId:
    """Test correlation ID functions."""

    def test_get_correlation_id_default(self):
        """Should return None when not set."""
        clear_correlation_id()
        assert get_correlation_id() is None

    def test_set_correlation_id(self):
        """Should set and retrieve correlation ID."""
        cid = set_correlation_id("test-123")

        assert cid == "test-123"
        assert get_correlation_id() == "test-123"

        clear_correlation_id()

    def test_set_correlation_id_auto_generate(self):
        """Should auto-generate ID when None."""
        clear_correlation_id()
        cid = set_correlation_id()

        assert cid is not None
        assert len(cid) == 8  # Short UUID format
        assert get_correlation_id() == cid

        clear_correlation_id()

    def test_clear_correlation_id(self):
        """Should clear correlation ID."""
        set_correlation_id("test-456")
        clear_correlation_id()

        assert get_correlation_id() is None


class TestJSONFormatter:
    """Test JSON log formatter."""

    def test_basic_format(self):
        """Should format as valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "Test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_includes_correlation_id(self):
        """Should include correlation ID when set."""
        formatter = JSONFormatter()
        set_correlation_id("corr-789")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["correlation_id"] == "corr-789"

        clear_correlation_id()

    def test_includes_extra_fields(self):
        """Should include extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None
        )
        record.agent_name = "echo_curator"
        record.task_hash = "abc123"

        output = formatter.format(record)
        data = json.loads(output)

        assert data["agent_name"] == "echo_curator"
        assert data["task_hash"] == "abc123"

    def test_includes_exception_info(self):
        """Should include exception info."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "Test error" in data["exception"]["message"]


class TestTextFormatter:
    """Test text log formatter."""

    def test_basic_format(self):
        """Should format as readable text."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)

        assert "INFO" in output
        assert "Test message" in output

    def test_includes_correlation_id(self):
        """Should include correlation ID in text output."""
        formatter = TextFormatter()
        set_correlation_id("text-cid")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None
        )

        output = formatter.format(record)

        assert "cid=text-cid" in output

        clear_correlation_id()

    def test_includes_context(self):
        """Should include context fields."""
        formatter = TextFormatter()
        clear_correlation_id()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None
        )
        record.agent_name = "moe_router"
        record.phase = "activate"

        output = formatter.format(record)

        assert "agent=moe_router" in output
        assert "phase=activate" in output


class TestContextAdapter:
    """Test context adapter."""

    def test_injects_context(self):
        """Should inject context into log messages."""
        base_logger = logging.getLogger("test_context")
        adapter = ContextAdapter(base_logger, {"agent_name": "test_agent"})

        # Process a message
        msg, kwargs = adapter.process("Test message", {})

        assert kwargs["extra"]["agent_name"] == "test_agent"

    def test_merges_with_existing_extra(self):
        """Should merge context with existing extra."""
        base_logger = logging.getLogger("test_context2")
        adapter = ContextAdapter(base_logger, {"agent_name": "test_agent"})

        msg, kwargs = adapter.process("Test", {"extra": {"task_hash": "abc"}})

        assert kwargs["extra"]["agent_name"] == "test_agent"
        assert kwargs["extra"]["task_hash"] == "abc"


class TestSetupLogging:
    """Test logging setup function."""

    def test_setup_text_format(self):
        """Should configure text formatter."""
        logger = setup_logging(level="DEBUG", log_format="text", module_name="test_text")

        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, TextFormatter)

    def test_setup_json_format(self):
        """Should configure JSON formatter."""
        logger = setup_logging(level="INFO", log_format="json", module_name="test_json")

        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, JSONFormatter)


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_without_context(self):
        """Should return plain logger."""
        logger = get_logger("test_plain")

        assert isinstance(logger, logging.Logger)

    def test_get_logger_with_context(self):
        """Should return context adapter."""
        logger = get_logger("test_adapted", {"agent_name": "test"})

        assert isinstance(logger, ContextAdapter)
