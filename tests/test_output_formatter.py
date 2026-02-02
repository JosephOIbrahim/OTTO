"""
Tests for Output Formatter Abstraction
======================================

Tests the output formatter interface and implementations.

[He2025] Compliance:
- Tests verify deterministic behavior
- Same inputs → same outputs
"""

import json
import os
from unittest.mock import patch

import pytest

from otto.output import (
    OutputFormatter,
    OutputFormat,
    PlainFormatter,
    JSONFormatter,
    get_formatter,
    set_formatter,
    reset_formatter,
)
from otto.output.formatter import (
    StatusData,
    AlertData,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def plain_formatter():
    """Create a plain formatter."""
    return PlainFormatter()


@pytest.fixture
def json_formatter():
    """Create a JSON formatter."""
    return JSONFormatter(indent=2)


@pytest.fixture
def json_compact_formatter():
    """Create a compact JSON formatter."""
    return JSONFormatter(indent=None)


@pytest.fixture
def sample_status():
    """Create sample status data."""
    return StatusData(
        burnout="GREEN",
        momentum="rolling",
        energy="high",
        altitude="15000ft",
        expert="Direct",
        goal="Build auth system",
        exchange_count=10,
    )


@pytest.fixture
def sample_alert():
    """Create sample alert data."""
    return AlertData(
        level="warning",
        message="Burnout level increasing",
        timestamp="2025-01-15T10:30:00",
        source="BurnoutMonitor",
    )


@pytest.fixture
def sample_state():
    """Create sample cognitive state."""
    return {
        "active_mode": "focused",
        "active_paradigm": "Cortex",
        "burnout_level": "GREEN",
        "momentum_phase": "rolling",
        "tangent_budget": 4,
    }


@pytest.fixture(autouse=True)
def reset_global():
    """Reset global formatter before and after each test."""
    reset_formatter()
    yield
    reset_formatter()


# =============================================================================
# StatusData Tests
# =============================================================================

class TestStatusData:
    """Tests for StatusData dataclass."""

    def test_create_status(self):
        """Test creating status data."""
        status = StatusData(
            burnout="YELLOW",
            momentum="building",
            energy="medium",
        )

        assert status.burnout == "YELLOW"
        assert status.momentum == "building"
        assert status.energy == "medium"
        assert status.altitude == "30000ft"  # default
        assert status.expert == "Direct"  # default
        assert status.goal is None  # default

    def test_status_defaults(self):
        """Test status data defaults."""
        status = StatusData()

        assert status.burnout == "GREEN"
        assert status.momentum == "cold_start"
        assert status.energy == "medium"
        assert status.exchange_count == 0


# =============================================================================
# AlertData Tests
# =============================================================================

class TestAlertData:
    """Tests for AlertData dataclass."""

    def test_create_alert(self):
        """Test creating alert data."""
        alert = AlertData(
            level="error",
            message="Connection failed",
        )

        assert alert.level == "error"
        assert alert.message == "Connection failed"
        assert alert.timestamp is None
        assert alert.source is None

    def test_create_alert_with_all_fields(self):
        """Test creating alert with all fields."""
        alert = AlertData(
            level="critical",
            message="System overload",
            timestamp="2025-01-15T12:00:00",
            source="SystemMonitor",
        )

        assert alert.level == "critical"
        assert alert.timestamp == "2025-01-15T12:00:00"
        assert alert.source == "SystemMonitor"


# =============================================================================
# PlainFormatter Tests
# =============================================================================

class TestPlainFormatter:
    """Tests for PlainFormatter."""

    def test_format_type(self, plain_formatter):
        """Test format type is PLAIN."""
        assert plain_formatter.format_type == OutputFormat.PLAIN

    def test_format_status(self, plain_formatter, sample_status):
        """Test status formatting."""
        output = plain_formatter.format_status(sample_status)

        assert "Goal: Build auth system" in output
        assert "Direct" in output
        assert "15000ft" in output
        assert "GREEN" in output
        assert "rolling" in output

    def test_format_status_without_goal(self, plain_formatter):
        """Test status formatting without goal."""
        status = StatusData(burnout="YELLOW", momentum="building")
        output = plain_formatter.format_status(status)

        assert "Goal:" not in output
        assert "YELLOW" in output
        assert "building" in output

    def test_format_status_line(self, plain_formatter, sample_status):
        """Test compact status line formatting."""
        output = plain_formatter.format_status_line(sample_status)

        assert "Direct" in output
        assert "15000ft" in output
        assert "GREEN" in output
        assert "rolling" in output
        # Compact version should not include goal
        assert "Build auth" not in output

    def test_format_alert(self, plain_formatter, sample_alert):
        """Test alert formatting."""
        output = plain_formatter.format_alert(sample_alert)

        assert "[WARN]" in output
        assert "Burnout level increasing" in output
        assert "2025-01-15T10:30:00" in output
        assert "BurnoutMonitor" in output

    def test_format_alert_minimal(self, plain_formatter):
        """Test minimal alert formatting."""
        alert = AlertData(level="info", message="Status update")
        output = plain_formatter.format_alert(alert)

        assert "[INFO]" in output
        assert "Status update" in output

    def test_format_alert_levels(self, plain_formatter):
        """Test all alert levels."""
        levels = {
            "info": "[INFO]",
            "warning": "[WARN]",
            "error": "[ERROR]",
            "critical": "[CRITICAL]",
            "unknown": "[ALERT]",
        }

        for level, expected_prefix in levels.items():
            alert = AlertData(level=level, message="test")
            output = plain_formatter.format_alert(alert)
            assert expected_prefix in output

    def test_format_state(self, plain_formatter, sample_state):
        """Test state formatting."""
        output = plain_formatter.format_state(sample_state)

        assert "active_mode: focused" in output
        assert "active_paradigm: Cortex" in output
        assert "burnout_level: GREEN" in output

    def test_format_state_nested(self, plain_formatter):
        """Test nested state formatting."""
        state = {
            "cognitive": {"mode": "focused", "paradigm": "Cortex"},
            "simple": "value",
        }
        output = plain_formatter.format_state(state)

        assert "cognitive:" in output
        assert "mode: focused" in output
        assert "simple: value" in output

    def test_format_state_list(self, plain_formatter):
        """Test state with list values."""
        state = {"tags": ["urgent", "important", "todo"]}
        output = plain_formatter.format_state(state)

        assert "tags:" in output
        assert "urgent" in output
        assert "important" in output


# =============================================================================
# JSONFormatter Tests
# =============================================================================

class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_type(self, json_formatter):
        """Test format type is JSON."""
        assert json_formatter.format_type == OutputFormat.JSON

    def test_format_status(self, json_formatter, sample_status):
        """Test status JSON formatting."""
        output = json_formatter.format_status(sample_status)
        data = json.loads(output)

        assert data["type"] == "status"
        assert data["burnout"] == "GREEN"
        assert data["momentum"] == "rolling"
        assert data["energy"] == "high"
        assert data["altitude"] == "15000ft"
        assert data["expert"] == "Direct"
        assert data["goal"] == "Build auth system"
        assert data["exchange_count"] == 10
        assert data["time_estimate_min"] == 45  # 10 * 4.5

    def test_format_status_compact(self, json_compact_formatter, sample_status):
        """Test compact JSON formatting."""
        output = json_compact_formatter.format_status(sample_status)
        # Compact should have no newlines
        assert "\n" not in output
        # But should still be valid JSON
        data = json.loads(output)
        assert data["type"] == "status"

    def test_format_alert(self, json_formatter, sample_alert):
        """Test alert JSON formatting."""
        output = json_formatter.format_alert(sample_alert)
        data = json.loads(output)

        assert data["type"] == "alert"
        assert data["level"] == "warning"
        assert data["message"] == "Burnout level increasing"
        assert data["timestamp"] == "2025-01-15T10:30:00"
        assert data["source"] == "BurnoutMonitor"

    def test_format_state(self, json_formatter, sample_state):
        """Test state JSON formatting."""
        output = json_formatter.format_state(sample_state)
        data = json.loads(output)

        assert data["type"] == "state"
        assert data["data"]["active_mode"] == "focused"
        assert data["data"]["burnout_level"] == "GREEN"

    def test_format_status_line(self, json_formatter, sample_status):
        """Test compact JSON status line."""
        output = json_formatter.format_status_line(sample_status)
        data = json.loads(output)

        assert data["expert"] == "Direct"
        assert data["altitude"] == "15000ft"
        assert data["burnout"] == "GREEN"
        assert "goal" not in data  # Compact should exclude

    def test_format_dashboard(self, json_formatter, sample_status, sample_alert, sample_state):
        """Test full dashboard JSON formatting."""
        output = json_formatter.format_dashboard(
            sample_status,
            [sample_alert],
            sample_state,
        )
        data = json.loads(output)

        assert data["type"] == "dashboard"
        assert data["status"]["burnout"] == "GREEN"
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["level"] == "warning"
        assert data["state"]["active_mode"] == "focused"

    def test_sort_keys_determinism(self, json_formatter):
        """Test that keys are sorted for determinism."""
        state = {"z_field": 1, "a_field": 2, "m_field": 3}
        output = json_formatter.format_state(state)

        # Keys should appear in sorted order
        a_pos = output.index("a_field")
        m_pos = output.index("m_field")
        z_pos = output.index("z_field")

        assert a_pos < m_pos < z_pos


# =============================================================================
# Global Instance Tests
# =============================================================================

class TestGlobalInstance:
    """Tests for global formatter instance."""

    def test_get_formatter_creates_instance(self):
        """Test that get_formatter creates a formatter."""
        formatter = get_formatter()
        assert isinstance(formatter, OutputFormatter)

    def test_get_formatter_returns_same_instance(self):
        """Test singleton behavior."""
        formatter1 = get_formatter()
        formatter2 = get_formatter()
        assert formatter1 is formatter2

    def test_set_formatter_replaces_instance(self, json_formatter):
        """Test that set_formatter replaces the global instance."""
        set_formatter(json_formatter)
        assert get_formatter() is json_formatter

    def test_reset_formatter(self, json_formatter):
        """Test resetting the global instance."""
        set_formatter(json_formatter)
        reset_formatter()

        # Should create new instance
        formatter = get_formatter()
        assert formatter is not json_formatter

    def test_env_json_format(self):
        """Test JSON formatter from environment."""
        with patch.dict(os.environ, {"OTTO_OUTPUT_FORMAT": "json"}):
            reset_formatter()
            formatter = get_formatter()
            assert formatter.format_type == OutputFormat.JSON

    def test_env_plain_format(self):
        """Test plain formatter from environment."""
        with patch.dict(os.environ, {"OTTO_OUTPUT_FORMAT": "plain"}):
            reset_formatter()
            formatter = get_formatter()
            assert formatter.format_type == OutputFormat.PLAIN

    def test_env_ansi_fallback(self):
        """Test ANSI falls back to plain (mobile-safe)."""
        with patch.dict(os.environ, {"OTTO_OUTPUT_FORMAT": "ansi"}):
            reset_formatter()
            formatter = get_formatter()
            # Should fall back to plain for mobile safety
            assert formatter.format_type == OutputFormat.PLAIN


# =============================================================================
# [He2025] Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests verifying [He2025] compliant determinism."""

    def test_same_input_same_output_plain(self, plain_formatter, sample_status):
        """Test that same status produces same output."""
        results = []
        for _ in range(10):
            results.append(plain_formatter.format_status(sample_status))

        # All results should be identical
        assert len(set(results)) == 1

    def test_same_input_same_output_json(self, json_formatter, sample_status):
        """Test that same status produces same JSON output."""
        results = []
        for _ in range(10):
            results.append(json_formatter.format_status(sample_status))

        # All results should be identical
        assert len(set(results)) == 1

    def test_formatter_selection_deterministic(self):
        """Test that formatter selection is deterministic."""
        formatters = []
        for _ in range(10):
            reset_formatter()
            with patch.dict(os.environ, {"OTTO_OUTPUT_FORMAT": "json"}):
                formatters.append(get_formatter().format_type)

        # All selections should be identical
        assert len(set(formatters)) == 1
        assert formatters[0] == OutputFormat.JSON

    def test_state_key_order_deterministic(self, json_formatter):
        """Test that state keys are always in same order."""
        state = {"zebra": 1, "apple": 2, "mango": 3}

        results = []
        for _ in range(10):
            results.append(json_formatter.format_state(state))

        # All results should be identical (sorted keys)
        assert len(set(results)) == 1


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_state(self, plain_formatter):
        """Test formatting empty state."""
        output = plain_formatter.format_state({})
        assert output == ""

    def test_unicode_message(self, plain_formatter):
        """Test unicode in alert message."""
        alert = AlertData(
            level="info",
            message="状态更新 🚀 مرحبا",
        )
        output = plain_formatter.format_alert(alert)
        assert "状态更新" in output
        assert "🚀" in output

    def test_special_characters_in_goal(self, plain_formatter):
        """Test special characters in goal."""
        status = StatusData(
            goal="Fix bug #123 (critical!) & deploy",
        )
        output = plain_formatter.format_status(status)
        assert "Fix bug #123" in output
        assert "(critical!)" in output

    def test_very_long_message(self, plain_formatter):
        """Test very long alert message."""
        message = "x" * 10000
        alert = AlertData(level="info", message=message)
        output = plain_formatter.format_alert(alert)
        assert message in output

    def test_null_values_in_state(self, json_formatter):
        """Test null values in state."""
        state = {"key": None, "other": "value"}
        output = json_formatter.format_state(state)
        data = json.loads(output)
        assert data["data"]["key"] is None

    def test_nested_state_determinism(self, json_formatter):
        """Test deeply nested state is deterministic."""
        state = {
            "level1": {
                "level2": {
                    "z": 3, "a": 1, "m": 2
                }
            }
        }
        results = [json_formatter.format_state(state) for _ in range(10)]
        assert len(set(results)) == 1

    def test_empty_alerts_in_dashboard(self, plain_formatter, sample_status, sample_state):
        """Test dashboard with no alerts."""
        output = plain_formatter.format_dashboard(sample_status, [], sample_state)
        assert "Alerts:" not in output

    def test_multiple_alerts_in_dashboard(self, json_formatter, sample_status, sample_state):
        """Test dashboard with multiple alerts."""
        alerts = [
            AlertData(level="info", message="Info 1"),
            AlertData(level="warning", message="Warning 1"),
            AlertData(level="error", message="Error 1"),
        ]
        output = json_formatter.format_dashboard(sample_status, alerts, sample_state)
        data = json.loads(output)
        assert len(data["alerts"]) == 3
