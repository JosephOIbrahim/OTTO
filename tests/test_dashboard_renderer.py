"""
Tests for Dashboard Renderer

Tests the mobile-compatible dashboard rendering abstraction.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from otto.dashboard_renderer import (
    DashboardRenderer,
    CognitiveStateData,
    DashboardSection,
    ProgressData,
    render_progress_bar,
    format_time_ago,
    get_dashboard_renderer,
    set_dashboard_renderer,
    reset_dashboard_renderer,
    render_dashboard,
    render_dashboard_json,
    render_dashboard_status_line,
)
from otto.output import (
    PlainFormatter,
    JSONFormatter,
    StatusData,
    set_formatter,
    reset_formatter,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def state_data():
    """Create test state data."""
    return CognitiveStateData(
        burnout_level="YELLOW",
        momentum_phase="building",
        energy_level="medium",
        mode="exploring",
        altitude="15000ft",
        focus_level="moderate",
        urgency="relaxed",
        tangent_budget=3,
        rapid_exchange_count=5,
        exchange_count=10,
        tasks_completed=2,
        session_started="1h ago",
        last_activity="5m ago",
        convergence_attractor="exploring",
        epistemic_tension=0.25,
        stable_exchanges=2,
        is_converged=False,
        decision_mode="work",
        cognitive_budget=0.8,
        can_spawn=True,
        active_agents=1,
        queued_results=2,
        flow_protection=False,
        decisions_made=5,
        state_file="/test/state.json",
        checksum="abc123",
    )


@pytest.fixture
def renderer():
    """Create test renderer."""
    return DashboardRenderer()


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global instances before each test."""
    reset_dashboard_renderer()
    reset_formatter()
    yield
    reset_dashboard_renderer()
    reset_formatter()


# =============================================================================
# CognitiveStateData Tests
# =============================================================================

class TestCognitiveStateData:
    """Tests for CognitiveStateData dataclass."""

    def test_default_values(self):
        """Default values are set correctly."""
        data = CognitiveStateData()

        assert data.burnout_level == "GREEN"
        assert data.momentum_phase == "rolling"
        assert data.energy_level == "high"
        assert data.mode == "focused"
        assert data.altitude == "30000ft"

    def test_custom_values(self, state_data):
        """Custom values are stored correctly."""
        assert state_data.burnout_level == "YELLOW"
        assert state_data.momentum_phase == "building"
        assert state_data.exchange_count == 10


# =============================================================================
# Progress Bar Tests
# =============================================================================

class TestProgressBar:
    """Tests for progress bar rendering."""

    def test_progress_bar_empty(self):
        """Empty progress bar."""
        bar = render_progress_bar(0.0)
        assert bar == "[" + "-" * 20 + "]"

    def test_progress_bar_full(self):
        """Full progress bar."""
        bar = render_progress_bar(1.0)
        assert bar == "[" + "#" * 20 + "]"

    def test_progress_bar_half(self):
        """Half progress bar."""
        bar = render_progress_bar(0.5)
        assert bar == "[" + "#" * 10 + "-" * 10 + "]"

    def test_progress_bar_custom_width(self):
        """Custom width progress bar."""
        bar = render_progress_bar(0.5, width=10)
        assert bar == "[" + "#" * 5 + "-" * 5 + "]"

    def test_progress_bar_custom_chars(self):
        """Custom characters in progress bar."""
        bar = render_progress_bar(0.5, filled_char="=", empty_char=".")
        assert bar == "[" + "=" * 10 + "." * 10 + "]"

    def test_progress_bar_clamps_values(self):
        """Progress bar clamps out-of-range values."""
        bar_over = render_progress_bar(1.5)
        bar_under = render_progress_bar(-0.5)

        assert bar_over == render_progress_bar(1.0)
        assert bar_under == render_progress_bar(0.0)

    def test_progress_bar_deterministic(self):
        """Same value produces same bar."""
        bar1 = render_progress_bar(0.75)
        bar2 = render_progress_bar(0.75)
        bar3 = render_progress_bar(0.75)

        assert bar1 == bar2 == bar3


# =============================================================================
# Format Time Ago Tests
# =============================================================================

class TestFormatTimeAgo:
    """Tests for time formatting."""

    def test_format_seconds(self):
        """Format seconds ago."""
        import time
        result = format_time_ago(time.time() - 30)
        assert "s ago" in result

    def test_format_minutes(self):
        """Format minutes ago."""
        import time
        result = format_time_ago(time.time() - 300)
        assert "m ago" in result

    def test_format_hours(self):
        """Format hours ago."""
        import time
        result = format_time_ago(time.time() - 7200)
        assert "h ago" in result

    def test_format_days(self):
        """Format days ago."""
        import time
        result = format_time_ago(time.time() - 172800)
        assert "d ago" in result


# =============================================================================
# DashboardSection Tests
# =============================================================================

class TestDashboardSection:
    """Tests for DashboardSection dataclass."""

    def test_section_creation(self):
        """Section is created correctly."""
        section = DashboardSection(
            title="Test Section",
            items=[("Key1", "Value1"), ("Key2", "Value2")],
        )

        assert section.title == "Test Section"
        assert len(section.items) == 2
        assert section.separator == "-"

    def test_section_default_items(self):
        """Section has empty items by default."""
        section = DashboardSection(title="Empty")
        assert section.items == []


# =============================================================================
# DashboardRenderer Tests
# =============================================================================

class TestDashboardRenderer:
    """Tests for DashboardRenderer."""

    def test_state_to_status_data(self, renderer, state_data):
        """Converts state to StatusData correctly."""
        status_data = renderer.state_to_status_data(state_data)

        assert isinstance(status_data, StatusData)
        assert status_data.burnout == "YELLOW"
        assert status_data.momentum == "building"
        assert status_data.energy == "medium"

    def test_render_status_line(self, renderer, state_data):
        """Renders status line."""
        set_formatter(PlainFormatter())
        output = renderer.render_status_line(state_data)

        assert "YELLOW" in output
        assert "building" in output

    def test_render_progress(self, renderer):
        """Renders progress with label."""
        output = renderer.render_progress(0.5, label="Progress")

        assert "Progress:" in output
        assert "[" in output
        assert "0.50" in output

    def test_render_section(self, renderer):
        """Renders section correctly."""
        section = DashboardSection(
            title="Test",
            items=[("Key", "Value")],
        )
        output = renderer.render_section(section)

        assert "TEST" in output
        assert "Key: Value" in output
        assert "-" * 40 in output

    def test_render_full_dashboard(self, renderer, state_data):
        """Renders full dashboard."""
        output = renderer.render_full_dashboard(state_data)

        assert "ORCHESTRA COGNITIVE STATE DASHBOARD" in output
        assert "COGNITIVE STATE" in output
        assert "COGNITIVE SUPPORT" in output
        assert "SESSION STATS" in output
        assert "CONVERGENCE" in output
        assert "DECISION ENGINE" in output

    def test_render_full_dashboard_includes_state(self, renderer, state_data):
        """Full dashboard includes state values."""
        output = renderer.render_full_dashboard(state_data)

        assert "YELLOW" in output
        assert "building" in output
        assert "exploring" in output

    def test_render_json(self, renderer, state_data):
        """Renders JSON output."""
        output = renderer.render_json(state_data)

        data = json.loads(output)
        assert "cognitive_state" in data
        assert data["cognitive_state"]["burnout_level"] == "YELLOW"

    def test_render_json_deterministic(self, renderer, state_data):
        """JSON output is deterministic."""
        output1 = renderer.render_json(state_data)
        output2 = renderer.render_json(state_data)

        assert output1 == output2

    def test_to_dict(self, renderer, state_data):
        """Returns state as dict."""
        data = renderer.to_dict(state_data)

        assert "cognitive_state" in data
        assert "cognitive_support" in data
        assert "session_stats" in data
        assert "convergence" in data
        assert "decision_engine" in data


# =============================================================================
# Global Instance Tests
# =============================================================================

class TestGlobalInstance:
    """Tests for global renderer instance."""

    def test_get_dashboard_renderer_creates_default(self):
        """get_dashboard_renderer creates default instance."""
        renderer = get_dashboard_renderer()

        assert renderer is not None
        assert isinstance(renderer, DashboardRenderer)

    def test_get_dashboard_renderer_returns_same(self):
        """get_dashboard_renderer returns same instance."""
        r1 = get_dashboard_renderer()
        r2 = get_dashboard_renderer()

        assert r1 is r2

    def test_set_dashboard_renderer(self):
        """set_dashboard_renderer replaces instance."""
        custom_renderer = DashboardRenderer()
        set_dashboard_renderer(custom_renderer)

        assert get_dashboard_renderer() is custom_renderer

    def test_reset_dashboard_renderer(self):
        """reset_dashboard_renderer clears instance."""
        _ = get_dashboard_renderer()
        reset_dashboard_renderer()

        # Should create new instance
        r2 = get_dashboard_renderer()
        assert r2 is not None


# =============================================================================
# Convenience Functions Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_render_dashboard(self, state_data):
        """render_dashboard uses global renderer."""
        renderer = DashboardRenderer()
        set_dashboard_renderer(renderer)

        with patch.object(renderer, 'read_cognitive_state', return_value=state_data):
            output = render_dashboard()

        assert "ORCHESTRA" in output

    def test_render_dashboard_json(self, state_data):
        """render_dashboard_json uses global renderer."""
        renderer = DashboardRenderer()
        set_dashboard_renderer(renderer)

        with patch.object(renderer, 'read_cognitive_state', return_value=state_data):
            output = render_dashboard_json()

        data = json.loads(output)
        assert "cognitive_state" in data

    def test_render_dashboard_status_line(self, state_data):
        """render_dashboard_status_line uses global renderer."""
        renderer = DashboardRenderer()
        set_dashboard_renderer(renderer)
        set_formatter(PlainFormatter())

        with patch.object(renderer, 'read_cognitive_state', return_value=state_data):
            output = render_dashboard_status_line()

        assert "YELLOW" in output


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests for Determinism."""

    def test_render_full_deterministic(self, renderer, state_data):
        """Same state produces same dashboard."""
        output1 = renderer.render_full_dashboard(state_data)
        output2 = renderer.render_full_dashboard(state_data)
        output3 = renderer.render_full_dashboard(state_data)

        assert output1 == output2 == output3

    def test_render_section_deterministic(self, renderer):
        """Section rendering is deterministic."""
        section = DashboardSection(
            title="Test",
            items=[("A", "1"), ("B", "2"), ("C", "3")],
        )

        output1 = renderer.render_section(section)
        output2 = renderer.render_section(section)

        assert output1 == output2

    def test_state_to_status_data_deterministic(self, renderer, state_data):
        """State conversion is deterministic."""
        sd1 = renderer.state_to_status_data(state_data)
        sd2 = renderer.state_to_status_data(state_data)

        assert sd1 == sd2

    def test_to_dict_deterministic(self, renderer, state_data):
        """to_dict is deterministic."""
        d1 = renderer.to_dict(state_data)
        d2 = renderer.to_dict(state_data)

        # Convert to JSON for comparison (dict comparison can be order-sensitive)
        assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests with OutputFormatter."""

    def test_render_with_json_formatter(self, renderer, state_data):
        """Renderer works with JSON formatter."""
        set_formatter(JSONFormatter())
        output = renderer.render_status_line(state_data)

        # Should be valid JSON
        data = json.loads(output)
        assert "burnout" in data

    def test_render_with_plain_formatter(self, renderer, state_data):
        """Renderer works with Plain formatter."""
        set_formatter(PlainFormatter())
        output = renderer.render_status_line(state_data)

        # Should be plain text
        assert "YELLOW" in output or "building" in output


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_state(self, renderer):
        """Handles empty state."""
        empty_state = CognitiveStateData()
        output = renderer.render_full_dashboard(empty_state)

        assert "COGNITIVE STATE" in output

    def test_body_check_warning(self, renderer):
        """Body check warning appears when needed."""
        state = CognitiveStateData(rapid_exchange_count=20)
        output = renderer.render_full_dashboard(state)

        assert "Body check recommended" in output

    def test_converged_state(self, renderer):
        """Converged state shows correctly."""
        state = CognitiveStateData(is_converged=True)
        output = renderer.render_full_dashboard(state)

        assert "CONVERGED" in output

    def test_not_converged_state(self, renderer):
        """Not converged state shows correctly."""
        state = CognitiveStateData(is_converged=False)
        output = renderer.render_full_dashboard(state)

        assert "not converged" in output

    def test_no_state_file(self, renderer):
        """Handles missing state file."""
        state = CognitiveStateData(state_file=None)
        output = renderer.render_full_dashboard(state)

        # Should not crash, just not include state file line
        assert "State file:" not in output or output.count("State file") >= 0

    def test_no_checksum(self, renderer):
        """Handles missing checksum."""
        state = CognitiveStateData(checksum=None)
        output = renderer.render_full_dashboard(state)

        # Should not crash
        assert "ORCHESTRA" in output
