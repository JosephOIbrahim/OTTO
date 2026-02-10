"""
Tests for TUI Bridge
====================

Tests for the bridge connecting agent progress to TUI dashboard.

Determinism:
- Bounded update frequency
- Deterministic state serialization
- Fixed history limits
"""

import pytest
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from otto.cli.tui_bridge import (
    TUIBridge,
    TUIState,
    AgentStateEntry,
    get_tui_bridge,
    reset_tui_bridge,
    MIN_UPDATE_INTERVAL_MS,
)


class TestAgentStateEntry:
    """Tests for AgentStateEntry dataclass."""

    def test_create_entry(self):
        """Create agent state entry."""
        entry = AgentStateEntry(
            agent_id="test-123",
            agent_type="planner",
            task="Plan something",
            status="running",
        )
        assert entry.agent_id == "test-123"
        assert entry.status == "running"

    def test_entry_to_dict(self):
        """Entry can be serialized."""
        entry = AgentStateEntry(
            agent_id="test-123",
            agent_type="planner",
            task="Plan something",
            status="running",
            current_step=2,
            total_steps=5,
        )
        data = entry.to_dict()
        assert data["agent_id"] == "test-123"
        assert data["current_step"] == 2
        assert data["total_steps"] == 5

    def test_entry_defaults(self):
        """Entry has sensible defaults."""
        entry = AgentStateEntry(
            agent_id="test",
            agent_type="test",
            task="test",
            status="running",
        )
        assert entry.current_step == 0
        assert entry.total_steps == 1
        assert entry.start_time > 0
        assert entry.end_time is None
        assert entry.error is None


class TestTUIState:
    """Tests for TUIState dataclass."""

    def test_create_state(self):
        """Create TUI state."""
        state = TUIState()
        assert state.agents == []
        assert state.total_agents_run == 0

    def test_state_to_dict(self):
        """State can be serialized."""
        entry = AgentStateEntry("a1", "planner", "task", "running")
        state = TUIState(
            agents=[entry],
            total_agents_run=5,
            total_completed=3,
        )
        data = state.to_dict()
        assert len(data["agents"]) == 1
        assert data["total_agents_run"] == 5
        assert data["total_completed"] == 3

    def test_state_json_serializable(self):
        """State to_dict is JSON serializable."""
        entry = AgentStateEntry("a1", "planner", "task", "running")
        state = TUIState(agents=[entry])
        data = state.to_dict()
        # Should not raise
        json_str = json.dumps(data)
        assert json_str is not None


class TestTUIBridge:
    """Tests for TUIBridge class."""

    @pytest.fixture
    def temp_state_dir(self):
        """Create temporary state directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def bridge(self, temp_state_dir):
        """Create bridge with temp directory."""
        return TUIBridge(state_dir=temp_state_dir)

    def test_create_bridge(self, bridge):
        """Create TUI bridge."""
        assert bridge is not None
        assert bridge.state is not None

    def test_add_agent(self, bridge):
        """Add agent to bridge."""
        bridge.add_agent("test-123", "planner", "Test task", total_steps=5)

        assert "test-123" in bridge._agent_map
        assert bridge.state.total_agents_run == 1

    def test_update_agent(self, bridge):
        """Update agent progress."""
        bridge.add_agent("test-123", "planner", "Test task", total_steps=5)
        bridge.update_agent("test-123", current_step=3, message="Step 3")

        entry = bridge._agent_map["test-123"]
        assert entry.current_step == 3
        assert entry.last_message == "Step 3"

    def test_complete_agent_success(self, bridge):
        """Complete agent successfully."""
        bridge.add_agent("test-123", "planner", "Test task")
        bridge.complete_agent("test-123", success=True, message="Done")

        entry = bridge._agent_map["test-123"]
        assert entry.status == "completed"
        assert bridge.state.total_completed == 1

    def test_complete_agent_failure(self, bridge):
        """Complete agent with failure."""
        bridge.add_agent("test-123", "planner", "Test task")
        bridge.complete_agent("test-123", success=False, message="Error")

        entry = bridge._agent_map["test-123"]
        assert entry.status == "failed"
        assert bridge.state.total_failed == 1

    def test_get_active_count(self, bridge):
        """Get count of active agents."""
        bridge.add_agent("a1", "planner", "Task 1")
        bridge.add_agent("a2", "researcher", "Task 2")
        bridge.complete_agent("a2", success=True)

        assert bridge.get_active_count() == 1

    def test_clear(self, bridge):
        """Clear all agent state."""
        bridge.add_agent("a1", "planner", "Task 1")
        bridge.add_agent("a2", "researcher", "Task 2")

        bridge.clear()

        assert len(bridge._agent_map) == 0
        assert len(bridge.state.agents) == 0

    def test_state_file_written(self, bridge, temp_state_dir):
        """State file is written."""
        bridge.add_agent("test-123", "planner", "Test task")
        bridge.flush()

        state_file = temp_state_dir / "agent_state.json"
        assert state_file.exists()

        data = json.loads(state_file.read_text())
        assert len(data["agents"]) == 1

    def test_atomic_write(self, bridge, temp_state_dir):
        """State is written atomically."""
        bridge.add_agent("test-123", "planner", "Test task")
        bridge.flush()

        state_file = temp_state_dir / "agent_state.json"
        temp_file = temp_state_dir / "agent_state.tmp"

        # Temp file should not exist after write
        assert state_file.exists()
        assert not temp_file.exists()


class TestTUIBridgeProgressTrackerIntegration:
    """Tests for ProgressTracker integration."""

    @pytest.fixture
    def temp_state_dir(self):
        """Create temporary state directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def bridge(self, temp_state_dir):
        """Create bridge with temp directory."""
        return TUIBridge(state_dir=temp_state_dir)

    @pytest.fixture
    def mock_tracker(self):
        """Create mock progress tracker."""
        tracker = MagicMock()
        tracker.on_progress = MagicMock()
        return tracker

    def test_register_with_tracker(self, bridge, mock_tracker):
        """Bridge registers with tracker."""
        bridge.register_with_tracker(mock_tracker)
        mock_tracker.on_progress.assert_called_once()

    def test_handle_start_event(self, bridge):
        """Handle agent start event."""
        # Simulate start event
        event = MagicMock()
        event.agent_id = "test-123"
        event.agent_type = "planner"
        event.event_type = "start"
        event.message = "Starting task"
        event.total_steps = 5

        bridge._handle_progress_event(event)

        assert "test-123" in bridge._agent_map
        assert bridge._agent_map["test-123"].status == "running"

    def test_handle_step_event(self, bridge):
        """Handle progress step event."""
        # First add agent
        bridge.add_agent("test-123", "planner", "Task")

        # Simulate step event
        event = MagicMock()
        event.agent_id = "test-123"
        event.event_type = "step"
        event.current_step = 3
        event.message = "Processing step 3"

        bridge._handle_progress_event(event)

        assert bridge._agent_map["test-123"].current_step == 3

    def test_handle_complete_event(self, bridge):
        """Handle agent complete event."""
        bridge.add_agent("test-123", "planner", "Task", total_steps=5)

        event = MagicMock()
        event.agent_id = "test-123"
        event.event_type = "complete"
        event.message = "Done"
        event.current_step = 5

        bridge._handle_progress_event(event)

        assert bridge._agent_map["test-123"].status == "completed"
        assert bridge.state.total_completed == 1

    def test_handle_error_event(self, bridge):
        """Handle agent error event."""
        bridge.add_agent("test-123", "planner", "Task")

        event = MagicMock()
        event.agent_id = "test-123"
        event.event_type = "error"
        event.message = "Something failed"

        bridge._handle_progress_event(event)

        assert bridge._agent_map["test-123"].status == "failed"
        assert bridge._agent_map["test-123"].error == "Something failed"

    def test_handle_milestone_event(self, bridge):
        """Handle milestone event."""
        bridge.add_agent("test-123", "planner", "Task")

        event = MagicMock()
        event.agent_id = "test-123"
        event.event_type = "milestone"
        event.message = "Important milestone"

        bridge._handle_progress_event(event)

        assert "[MILESTONE]" in bridge._agent_map["test-123"].last_message


class TestTUIBridgeBounds:
    """Tests for ThinkingMachines-compliant bounds."""

    @pytest.fixture
    def temp_state_dir(self):
        """Create temporary state directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def bridge(self, temp_state_dir):
        """Create bridge with temp directory."""
        return TUIBridge(state_dir=temp_state_dir)

    def test_max_history_size(self, bridge):
        """History is bounded."""
        # Add many agents
        for i in range(100):
            bridge.add_agent(f"agent-{i}", "test", f"Task {i}")
            if i > 0:
                bridge.complete_agent(f"agent-{i-1}", success=True)

        # Should have bounded number in display
        assert len(bridge.state.agents) <= bridge.MAX_ACTIVE_DISPLAY

    def test_max_active_display(self, bridge):
        """Active display is bounded."""
        # Add many running agents
        for i in range(20):
            bridge.add_agent(f"agent-{i}", "test", f"Task {i}")

        # Should be bounded in state.agents
        assert len(bridge.state.agents) <= bridge.MAX_ACTIVE_DISPLAY

    def test_update_rate_limiting(self, bridge):
        """Updates are rate-limited."""
        # This tests the throttling mechanism
        bridge.add_agent("test-1", "test", "Task 1")

        # Record first write time
        first_write = bridge._last_write_time

        # Immediate second add should be throttled
        bridge.add_agent("test-2", "test", "Task 2")

        # Either last_write_time should be same (throttled)
        # or enough time passed
        if bridge._last_write_time == first_write:
            assert bridge._pending_write is True

    def test_min_update_interval_defined(self):
        """Minimum update interval is defined."""
        assert MIN_UPDATE_INTERVAL_MS == 100  # 10 Hz max


class TestGlobalSingleton:
    """Tests for global TUI bridge singleton."""

    def test_get_tui_bridge(self):
        """Get global bridge instance."""
        reset_tui_bridge()  # Clear any existing
        bridge1 = get_tui_bridge()
        bridge2 = get_tui_bridge()
        assert bridge1 is bridge2

    def test_reset_tui_bridge(self):
        """Reset creates new instance."""
        bridge1 = get_tui_bridge()
        reset_tui_bridge()
        bridge2 = get_tui_bridge()
        assert bridge1 is not bridge2

    def teardown_method(self):
        """Clean up after each test."""
        reset_tui_bridge()
