"""
Tests for Status Renderer

Tests the mobile-compatible status rendering abstraction.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from otto.cli.status_renderer import (
    StatusRenderer,
    StatusRenderConfig,
    get_status_renderer,
    set_status_renderer,
    reset_status_renderer,
    render_status,
    render_status_json,
    read_cognitive_state,
    MODE_SYMBOLS,
    MOMENTUM_BARS,
    ALTITUDE_SHORT,
)
from otto.output import (
    OutputFormatter,
    PlainFormatter,
    JSONFormatter,
    StatusData,
    get_formatter,
    set_formatter,
    reset_formatter,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_state_file():
    """Create a temporary state file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "burnout_level": "YELLOW",
            "decision_mode": "delegate",
            "momentum_phase": "building",
            "energy_level": "medium",
            "working_memory_used": 1,
            "tangent_budget": 3,
            "altitude": "15000ft",
            "paradigm": "Mycelium",
            "goal": "Test goal",
            "exchange_count": 5,
        }, f)
        f.flush()
        yield Path(f.name)

    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def renderer(temp_state_file):
    """Create renderer with temp state file."""
    config = StatusRenderConfig(state_file=temp_state_file)
    return StatusRenderer(config=config)


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global instances before each test."""
    reset_status_renderer()
    reset_formatter()
    yield
    reset_status_renderer()
    reset_formatter()


# =============================================================================
# StatusRenderConfig Tests
# =============================================================================

class TestStatusRenderConfig:
    """Tests for StatusRenderConfig."""

    def test_default_state_file(self):
        """Default state file is set correctly."""
        config = StatusRenderConfig()
        expected = Path.home() / ".orchestra" / "state" / "cognitive_state.json"
        assert config.state_file == expected

    def test_custom_state_file(self, temp_state_file):
        """Custom state file is used."""
        config = StatusRenderConfig(state_file=temp_state_file)
        assert config.state_file == temp_state_file

    def test_default_flags(self):
        """Default flags are True."""
        config = StatusRenderConfig()
        assert config.include_goal is True
        assert config.include_paradigm is True
        assert config.include_memory is True
        assert config.include_tangent is True

    def test_custom_flags(self):
        """Custom flags are respected."""
        config = StatusRenderConfig(
            include_goal=False,
            include_paradigm=False,
            include_memory=False,
            include_tangent=False,
        )
        assert config.include_goal is False
        assert config.include_paradigm is False
        assert config.include_memory is False
        assert config.include_tangent is False


# =============================================================================
# StatusRenderer Tests
# =============================================================================

class TestStatusRenderer:
    """Tests for StatusRenderer."""

    def test_read_state_from_file(self, renderer):
        """Reads state from file correctly."""
        state = renderer.read_state()

        assert state["burnout_level"] == "YELLOW"
        assert state["decision_mode"] == "delegate"
        assert state["momentum_phase"] == "building"
        assert state["altitude"] == "15000ft"
        assert state["goal"] == "Test goal"

    def test_read_state_defaults_on_missing_file(self):
        """Returns defaults when file doesn't exist."""
        config = StatusRenderConfig(state_file=Path("/nonexistent/file.json"))
        renderer = StatusRenderer(config=config)

        state = renderer.read_state()

        assert state["burnout_level"] == "GREEN"
        assert state["decision_mode"] == "work"
        assert state["momentum_phase"] == "rolling"

    def test_read_state_defaults_on_invalid_json(self, temp_state_file):
        """Returns defaults when file has invalid JSON."""
        # Write invalid JSON
        with open(temp_state_file, 'w') as f:
            f.write("not valid json {{{")

        config = StatusRenderConfig(state_file=temp_state_file)
        renderer = StatusRenderer(config=config)

        state = renderer.read_state()

        assert state["burnout_level"] == "GREEN"  # Default

    def test_state_to_status_data(self, renderer):
        """Converts state dict to StatusData correctly."""
        state = renderer.read_state()
        status_data = renderer.state_to_status_data(state)

        assert isinstance(status_data, StatusData)
        assert status_data.burnout == "YELLOW"
        assert status_data.momentum == "building"
        assert status_data.energy == "medium"
        assert status_data.altitude == "15000ft"
        assert status_data.expert == "delegate"
        assert status_data.goal == "Test goal"
        assert status_data.exchange_count == 5

    def test_state_to_status_data_defaults(self):
        """Uses defaults for missing fields."""
        renderer = StatusRenderer()
        status_data = renderer.state_to_status_data({})

        assert status_data.burnout == "GREEN"
        assert status_data.momentum == "rolling"
        assert status_data.energy == "high"

    def test_render_uses_formatter(self, renderer):
        """Render uses the formatter."""
        formatter = PlainFormatter()
        output = renderer.render(formatter=formatter)

        assert "YELLOW" in output
        assert "building" in output

    def test_render_with_json_formatter(self, renderer):
        """Render works with JSON formatter."""
        formatter = JSONFormatter()
        output = renderer.render(formatter=formatter)

        # Should be valid JSON
        data = json.loads(output)
        assert data["burnout"] == "YELLOW"
        assert data["momentum"] == "building"

    def test_render_short(self, renderer):
        """Render short format."""
        output = renderer.render_short()

        assert output == "[Y]"

    def test_render_short_all_burnout_levels(self):
        """Short format works for all burnout levels."""
        renderer = StatusRenderer()

        for level, expected in [("GREEN", "[G]"), ("YELLOW", "[Y]"),
                                ("ORANGE", "[O]"), ("RED", "[R]")]:
            output = renderer.render_short({"burnout_level": level})
            assert output == expected

    def test_render_prompt(self, renderer):
        """Render prompt format."""
        output = renderer.render_prompt()

        assert "[YELLOW]" in output
        assert "DELEGATE" in output
        assert "=" in output  # building momentum bar

    def test_render_full(self, renderer):
        """Render full format."""
        output = renderer.render_full()

        assert "[YELLOW]" in output
        assert "DELEGATE" in output
        assert "BUILDING" in output
        assert "15K" in output
        assert "1/3" in output
        assert "T:3" in output
        assert "MYCELIUM" in output

    def test_render_full_without_optional_fields(self, temp_state_file):
        """Full format respects config flags."""
        config = StatusRenderConfig(
            state_file=temp_state_file,
            include_memory=False,
            include_tangent=False,
            include_paradigm=False,
        )
        renderer = StatusRenderer(config=config)

        output = renderer.render_full()

        assert "1/3" not in output
        assert "T:3" not in output
        assert "MYCELIUM" not in output

    def test_render_json(self, renderer):
        """Render JSON format."""
        output = renderer.render_json()

        data = json.loads(output)
        assert data["burnout_level"] == "YELLOW"

    def test_render_json_deterministic(self, renderer):
        """JSON output is deterministic (sorted keys)."""
        output1 = renderer.render_json()
        output2 = renderer.render_json()

        assert output1 == output2

        # Verify keys are sorted
        data = json.loads(output1)
        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_to_dict_returns_copy(self, renderer):
        """to_dict returns a copy, not the original."""
        state1 = renderer.to_dict()
        state2 = renderer.to_dict()

        state1["burnout_level"] = "MODIFIED"
        assert state2["burnout_level"] == "YELLOW"


# =============================================================================
# Data Mappings Tests
# =============================================================================

class TestDataMappings:
    """Tests for data mapping constants."""

    def test_mode_symbols(self):
        """Mode symbols are defined."""
        assert "work" in MODE_SYMBOLS
        assert "delegate" in MODE_SYMBOLS
        assert "protect" in MODE_SYMBOLS

    def test_momentum_bars(self):
        """Momentum bars are defined."""
        assert "cold_start" in MOMENTUM_BARS
        assert "building" in MOMENTUM_BARS
        assert "rolling" in MOMENTUM_BARS
        assert "peak" in MOMENTUM_BARS
        assert "crashed" in MOMENTUM_BARS

    def test_altitude_short(self):
        """Altitude short forms are defined."""
        assert ALTITUDE_SHORT["30000ft"] == "30K"
        assert ALTITUDE_SHORT["15000ft"] == "15K"
        assert ALTITUDE_SHORT["5000ft"] == "5K"
        assert ALTITUDE_SHORT["Ground"] == "GND"


# =============================================================================
# Global Instance Tests
# =============================================================================

class TestGlobalInstance:
    """Tests for global renderer instance."""

    def test_get_status_renderer_creates_default(self):
        """get_status_renderer creates default instance."""
        renderer = get_status_renderer()

        assert renderer is not None
        assert isinstance(renderer, StatusRenderer)

    def test_get_status_renderer_returns_same_instance(self):
        """get_status_renderer returns same instance."""
        renderer1 = get_status_renderer()
        renderer2 = get_status_renderer()

        assert renderer1 is renderer2

    def test_set_status_renderer(self, temp_state_file):
        """set_status_renderer replaces instance."""
        config = StatusRenderConfig(state_file=temp_state_file)
        custom_renderer = StatusRenderer(config=config)

        set_status_renderer(custom_renderer)

        assert get_status_renderer() is custom_renderer

    def test_reset_status_renderer(self):
        """reset_status_renderer clears instance."""
        _ = get_status_renderer()
        reset_status_renderer()

        # Should create new instance
        renderer2 = get_status_renderer()
        assert renderer2 is not None


# =============================================================================
# Convenience Functions Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_render_status(self, temp_state_file):
        """render_status uses global renderer."""
        config = StatusRenderConfig(state_file=temp_state_file)
        renderer = StatusRenderer(config=config)
        set_status_renderer(renderer)

        output = render_status()

        assert "YELLOW" in output or "building" in output

    def test_render_status_json(self, temp_state_file):
        """render_status_json uses global renderer."""
        config = StatusRenderConfig(state_file=temp_state_file)
        renderer = StatusRenderer(config=config)
        set_status_renderer(renderer)

        output = render_status_json()
        data = json.loads(output)

        assert data["burnout_level"] == "YELLOW"

    def test_read_cognitive_state(self, temp_state_file):
        """read_cognitive_state uses global renderer."""
        config = StatusRenderConfig(state_file=temp_state_file)
        renderer = StatusRenderer(config=config)
        set_status_renderer(renderer)

        state = read_cognitive_state()

        assert state["burnout_level"] == "YELLOW"


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests for Determinism."""

    def test_render_deterministic(self, renderer):
        """Same state produces same output."""
        state = renderer.read_state()

        output1 = renderer.render(state)
        output2 = renderer.render(state)
        output3 = renderer.render(state)

        assert output1 == output2 == output3

    def test_state_to_status_data_deterministic(self, renderer):
        """State conversion is deterministic."""
        state = renderer.read_state()

        data1 = renderer.state_to_status_data(state)
        data2 = renderer.state_to_status_data(state)

        assert data1 == data2

    def test_json_output_deterministic(self, renderer):
        """JSON output is deterministic."""
        output1 = renderer.render_json()
        output2 = renderer.render_json()

        assert output1 == output2

    def test_render_full_deterministic(self, renderer):
        """Full render is deterministic."""
        output1 = renderer.render_full()
        output2 = renderer.render_full()

        assert output1 == output2


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests with OutputFormatter."""

    def test_render_with_global_formatter(self, temp_state_file):
        """Renderer uses global formatter."""
        config = StatusRenderConfig(state_file=temp_state_file)
        renderer = StatusRenderer(config=config)

        # Set global formatter to JSON
        set_formatter(JSONFormatter())

        output = renderer.render()
        data = json.loads(output)

        assert data["burnout"] == "YELLOW"

    def test_renderer_with_custom_formatter(self, renderer):
        """Renderer uses custom formatter when provided."""
        custom_formatter = JSONFormatter()
        output = renderer.render(formatter=custom_formatter)

        data = json.loads(output)
        assert "burnout" in data

    def test_formatter_override_at_render_time(self, renderer):
        """Formatter can be overridden at render time."""
        # Set global to Plain
        set_formatter(PlainFormatter())

        # Render with JSON override
        json_formatter = JSONFormatter()
        output = renderer.render(formatter=json_formatter)

        # Should be JSON, not plain
        data = json.loads(output)
        assert "burnout" in data
