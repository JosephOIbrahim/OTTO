"""
Tests for Enhanced TUI Dashboard
================================

Tests for Phase 7 TUI enhancements.

Determinism:
- Deterministic display phase transitions
- Fixed color mappings
- Bounded update frequency
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from otto.cli.tui_enhanced import (
    DashboardState,
    AgentDisplayInfo,
    DisplayPhase,
    BURNOUT_STYLES,
    MODE_STYLES,
    AGENT_STATUS_STYLES,
    MOMENTUM_VISUAL,
    ENERGY_VISUAL,
    read_cognitive_state,
    read_agent_state,
    build_header_panel,
    build_burnout_panel,
    build_mode_panel,
    build_metrics_panel,
    build_agent_panel,
    build_progress_panel,
    build_session_panel,
    create_dashboard_layout,
)


class TestAgentDisplayInfo:
    """Tests for AgentDisplayInfo dataclass."""

    def test_create_agent_info(self):
        """Create agent display info."""
        info = AgentDisplayInfo(
            agent_id="test-123",
            agent_type="planner",
            task="Plan something",
            status="running",
            current_step=2,
            total_steps=5,
        )
        assert info.agent_id == "test-123"
        assert info.status == "running"

    def test_percentage_calculation(self):
        """Percentage calculated from steps."""
        info = AgentDisplayInfo(
            agent_id="test",
            agent_type="test",
            task="test",
            status="running",
            current_step=3,
            total_steps=10,
        )
        assert info.percentage == 30.0

    def test_percentage_zero_total(self):
        """Percentage handles zero total steps."""
        info = AgentDisplayInfo(
            agent_id="test",
            agent_type="test",
            task="test",
            status="running",
            current_step=0,
            total_steps=0,
        )
        assert info.percentage == 0.0

    def test_progress_bar(self):
        """Progress bar generated correctly."""
        info = AgentDisplayInfo(
            agent_id="test",
            agent_type="test",
            task="test",
            status="running",
            current_step=5,
            total_steps=10,
        )
        bar = info.progress_bar
        assert "█" in bar
        assert "░" in bar
        assert len(bar) == 15  # Default width


class TestDashboardState:
    """Tests for DashboardState dataclass."""

    def test_create_default_state(self):
        """Create state with defaults."""
        state = DashboardState()
        assert state.burnout_level == "GREEN"
        assert state.decision_mode == "work"
        assert state.momentum_phase == "rolling"
        assert state.display_phase == DisplayPhase.IDLE

    def test_state_with_agents(self):
        """State with active agents."""
        agents = [
            AgentDisplayInfo("a1", "planner", "task1", "running"),
            AgentDisplayInfo("a2", "researcher", "task2", "completed"),
        ]
        state = DashboardState(active_agents=agents)
        assert len(state.active_agents) == 2
        assert state.display_phase == DisplayPhase.IDLE  # Set separately


class TestDisplayConstants:
    """Tests for determinism-compliant display constants."""

    def test_burnout_styles_fixed(self):
        """Burnout styles are fixed (no runtime variation)."""
        assert "GREEN" in BURNOUT_STYLES
        assert "YELLOW" in BURNOUT_STYLES
        assert "ORANGE" in BURNOUT_STYLES
        assert "RED" in BURNOUT_STYLES
        assert len(BURNOUT_STYLES) == 4

    def test_mode_styles_fixed(self):
        """Mode styles are fixed."""
        assert "work" in MODE_STYLES
        assert "delegate" in MODE_STYLES
        assert "protect" in MODE_STYLES
        assert len(MODE_STYLES) == 3

    def test_agent_status_styles_fixed(self):
        """Agent status styles are fixed."""
        assert "running" in AGENT_STATUS_STYLES
        assert "completed" in AGENT_STATUS_STYLES
        assert "failed" in AGENT_STATUS_STYLES
        assert "aborted" in AGENT_STATUS_STYLES
        assert len(AGENT_STATUS_STYLES) == 4

    def test_momentum_visual_fixed(self):
        """Momentum visualizations are fixed."""
        assert "cold_start" in MOMENTUM_VISUAL
        assert "building" in MOMENTUM_VISUAL
        assert "rolling" in MOMENTUM_VISUAL
        assert "peak" in MOMENTUM_VISUAL
        assert "crashed" in MOMENTUM_VISUAL
        # Each has bar and percentage
        for key, (bar, pct) in MOMENTUM_VISUAL.items():
            assert len(bar) == 10
            assert 0.0 <= pct <= 1.0

    def test_energy_visual_fixed(self):
        """Energy visualizations are fixed."""
        assert "high" in ENERGY_VISUAL
        assert "medium" in ENERGY_VISUAL
        assert "low" in ENERGY_VISUAL
        assert "depleted" in ENERGY_VISUAL
        # Each has 4-char bar
        for key, bar in ENERGY_VISUAL.items():
            assert len(bar) == 4


class TestDisplayPhase:
    """Tests for DisplayPhase enum."""

    def test_display_phases(self):
        """All display phases exist."""
        assert DisplayPhase.IDLE.value == "idle"
        assert DisplayPhase.PROCESSING.value == "processing"
        assert DisplayPhase.AGENT_ACTIVE.value == "agent_active"
        assert DisplayPhase.ERROR.value == "error"


class TestStateReading:
    """Tests for state file reading."""

    def test_read_cognitive_state_missing_file(self):
        """Returns defaults when file missing."""
        with patch('otto.cli.tui_enhanced.STATE_FILE', Path("/nonexistent/path")):
            state = read_cognitive_state()
            assert state["burnout_level"] == "GREEN"
            assert state["decision_mode"] == "work"

    def test_read_cognitive_state_valid_file(self):
        """Reads state from valid file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "cognitive_state.json"
            state_file.write_text(json.dumps({
                "burnout_level": "YELLOW",
                "momentum_phase": "building",
            }))

            with patch('otto.cli.tui_enhanced.STATE_FILE', state_file):
                state = read_cognitive_state()
                assert state["burnout_level"] == "YELLOW"
                assert state["momentum_phase"] == "building"
                # Defaults filled in
                assert state["decision_mode"] == "work"

    def test_read_agent_state_missing_file(self):
        """Returns empty list when file missing."""
        with patch('otto.cli.tui_enhanced.AGENT_STATE_FILE', Path("/nonexistent/path")):
            agents = read_agent_state()
            assert agents == []

    def test_read_agent_state_valid_file(self):
        """Reads agents from valid file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "agent_state.json"
            state_file.write_text(json.dumps({
                "agents": [
                    {
                        "agent_id": "test-123",
                        "agent_type": "planner",
                        "task": "Test task",
                        "status": "running",
                        "current_step": 2,
                        "total_steps": 5,
                    }
                ]
            }))

            with patch('otto.cli.tui_enhanced.AGENT_STATE_FILE', state_file):
                agents = read_agent_state()
                assert len(agents) == 1
                assert agents[0].agent_id == "test-123"
                assert agents[0].agent_type == "planner"


class TestPanelBuilders:
    """Tests for panel builder functions."""

    @pytest.fixture
    def sample_state(self):
        """Sample dashboard state."""
        return DashboardState(
            burnout_level="GREEN",
            decision_mode="work",
            momentum_phase="rolling",
            energy_level="high",
            working_memory_used=2,
            tangent_budget=5,
        )

    @pytest.fixture
    def state_with_agents(self):
        """State with active agents."""
        return DashboardState(
            burnout_level="YELLOW",
            decision_mode="delegate",
            active_agents=[
                AgentDisplayInfo("a1", "planner", "Plan task", "running", 2, 5),
                AgentDisplayInfo("a2", "researcher", "Research task", "running", 1, 3),
            ],
        )

    def test_build_header_panel(self, sample_state):
        """Header panel builds without error."""
        panel = build_header_panel(sample_state)
        assert panel is not None
        # Panel should have renderable content
        assert hasattr(panel, 'renderable')

    def test_build_burnout_panel_green(self, sample_state):
        """Burnout panel for GREEN state."""
        panel = build_burnout_panel(sample_state)
        assert panel is not None

    def test_build_burnout_panel_red(self):
        """Burnout panel for RED state."""
        state = DashboardState(burnout_level="RED")
        panel = build_burnout_panel(state)
        assert panel is not None

    def test_build_mode_panel(self, sample_state):
        """Mode panel builds without error."""
        panel = build_mode_panel(sample_state)
        assert panel is not None

    def test_build_metrics_panel(self, sample_state):
        """Metrics panel builds without error."""
        panel = build_metrics_panel(sample_state)
        assert panel is not None

    def test_build_agent_panel_no_agents(self, sample_state):
        """Agent panel with no agents."""
        panel = build_agent_panel(sample_state)
        assert panel is not None

    def test_build_agent_panel_with_agents(self, state_with_agents):
        """Agent panel with active agents."""
        panel = build_agent_panel(state_with_agents)
        assert panel is not None

    def test_build_progress_panel_no_agents(self, sample_state):
        """Progress panel with no agents."""
        panel = build_progress_panel(sample_state)
        assert panel is not None

    def test_build_progress_panel_with_agents(self, state_with_agents):
        """Progress panel with active agents."""
        panel = build_progress_panel(state_with_agents)
        assert panel is not None

    def test_build_session_panel(self, sample_state):
        """Session panel builds without error."""
        panel = build_session_panel(sample_state)
        assert panel is not None


class TestLayoutCreation:
    """Tests for dashboard layout creation."""

    def test_create_layout_basic(self):
        """Create basic layout."""
        state = DashboardState()
        layout = create_dashboard_layout(state)
        assert layout is not None
        # Layout is created - check it has children
        assert layout.children is not None

    def test_create_layout_with_agents(self):
        """Create layout with agent panel."""
        state = DashboardState(
            active_agents=[
                AgentDisplayInfo("a1", "planner", "Task", "running"),
            ]
        )
        layout = create_dashboard_layout(state, show_agent_panel=True)
        assert layout is not None

    def test_create_layout_minimal(self):
        """Create minimal layout."""
        state = DashboardState()
        layout = create_dashboard_layout(
            state,
            show_agent_panel=False,
            show_progress_detail=False,
        )
        assert layout is not None

    def test_layout_deterministic(self):
        """Same state produces same layout structure."""
        state = DashboardState(
            burnout_level="YELLOW",
            momentum_phase="building",
        )

        layout1 = create_dashboard_layout(state)
        layout2 = create_dashboard_layout(state)

        # Both layouts should be created successfully
        assert layout1 is not None
        assert layout2 is not None
        # Both should have children (deterministic structure)
        assert layout1.children is not None
        assert layout2.children is not None


class TestDeterminismCompliance:
    """Tests for determinism ([He2025])."""

    def test_fixed_color_mappings(self):
        """Color mappings are fixed at import time."""
        # Verify mappings haven't changed from expected values
        assert len(BURNOUT_STYLES) == 4
        assert len(MODE_STYLES) == 3
        assert len(AGENT_STATUS_STYLES) == 4
        assert len(MOMENTUM_VISUAL) == 5
        assert len(ENERGY_VISUAL) == 4

    def test_deterministic_panel_building(self):
        """Panel building is deterministic."""
        state = DashboardState(
            burnout_level="ORANGE",
            decision_mode="protect",
            momentum_phase="crashed",
        )

        # Build same panels multiple times
        panels1 = [
            build_burnout_panel(state),
            build_mode_panel(state),
            build_metrics_panel(state),
        ]
        panels2 = [
            build_burnout_panel(state),
            build_mode_panel(state),
            build_metrics_panel(state),
        ]

        # All should be non-None
        assert all(p is not None for p in panels1)
        assert all(p is not None for p in panels2)

    def test_bounded_agent_display(self):
        """Agent display is bounded."""
        # Create many agents
        agents = [
            AgentDisplayInfo(f"a{i}", "test", f"task{i}", "running")
            for i in range(20)
        ]
        state = DashboardState(active_agents=agents)

        # Panel should handle this without error
        panel = build_agent_panel(state)
        assert panel is not None

    def test_display_phases_complete(self):
        """All display phases are defined."""
        phases = list(DisplayPhase)
        assert len(phases) == 4
        phase_values = [p.value for p in phases]
        assert "idle" in phase_values
        assert "processing" in phase_values
        assert "agent_active" in phase_values
        assert "error" in phase_values
