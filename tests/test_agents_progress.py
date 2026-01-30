"""
Tests for Progress Tracking
===========================

Tests for agent progress visibility.
"""

import pytest
from datetime import datetime, timedelta

from otto.agents.progress import (
    ProgressTracker,
    ProgressEvent,
    ProgressLevel,
    AgentTracker,
    get_progress_tracker,
)


class TestProgressEvent:
    """Tests for ProgressEvent."""

    def test_create_event(self):
        """Create progress event."""
        event = ProgressEvent(
            agent_id="test-123",
            agent_type="planner",
            event_type="step",
            message="Processing",
            current_step=2,
            total_steps=5,
            percentage=40.0,
        )
        assert event.agent_id == "test-123"
        assert event.percentage == 40.0

    def test_event_to_dict(self):
        """Event can be serialized."""
        event = ProgressEvent(
            agent_id="test-123",
            agent_type="planner",
            event_type="complete",
            message="Done",
        )
        data = event.to_dict()
        assert "agent_id" in data
        assert "timestamp" in data

    def test_event_format_terminal_start(self):
        """Format start event for terminal."""
        event = ProgressEvent(
            agent_id="test-123",
            agent_type="planner",
            event_type="start",
            message="Starting task",
        )
        display = event.format_terminal()
        assert "planner" in display.lower()
        assert "Starting" in display

    def test_event_format_terminal_step(self):
        """Format step event for terminal."""
        event = ProgressEvent(
            agent_id="test-123",
            agent_type="planner",
            event_type="step",
            message="Step 2",
            percentage=40.0,
        )
        display = event.format_terminal()
        assert "40%" in display
        assert "Step 2" in display

    def test_event_format_terminal_error(self):
        """Format error event for terminal."""
        event = ProgressEvent(
            agent_id="test-123",
            agent_type="planner",
            event_type="error",
            message="Something failed",
        )
        display = event.format_terminal()
        assert "ERROR" in display


class TestAgentTracker:
    """Tests for AgentTracker."""

    def test_create_tracker(self):
        """Create agent tracker."""
        tracker = AgentTracker(
            agent_id="test-123",
            agent_type="planner",
            task="Plan something",
            start_time=datetime.now(),
            total_steps=5,
        )
        assert tracker.status == "running"
        assert tracker.current_step == 0

    def test_tracker_duration(self):
        """Tracker calculates duration."""
        start = datetime.now() - timedelta(seconds=30)
        tracker = AgentTracker(
            agent_id="test-123",
            agent_type="planner",
            task="Plan something",
            start_time=start,
            total_steps=5,
        )
        duration = tracker.get_duration()
        assert duration >= 30

    def test_tracker_eta(self):
        """Tracker estimates time remaining."""
        start = datetime.now() - timedelta(seconds=30)
        tracker = AgentTracker(
            agent_id="test-123",
            agent_type="planner",
            task="Plan something",
            start_time=start,
            total_steps=10,
            current_step=5,
        )
        eta = tracker.get_eta_seconds()
        assert eta is not None
        # 5 steps took 30s, 5 remaining should take ~30s
        assert 20 <= eta <= 40


class TestProgressTracker:
    """Tests for ProgressTracker."""

    def test_start_agent(self):
        """Start tracking an agent."""
        tracker = ProgressTracker()
        agent_tracker = tracker.start_agent(
            "test-123", "planner", "Plan task", 5
        )

        assert agent_tracker.agent_id == "test-123"
        assert "test-123" in [a.agent_id for a in tracker.get_all_agents()]

    def test_update_progress(self):
        """Update agent progress."""
        tracker = ProgressTracker()
        tracker.start_agent("test-123", "planner", "Plan task", 5)

        tracker.update_progress("test-123", 2, "Step 2")

        agent = tracker.get_agent("test-123")
        assert agent.current_step == 2

    def test_complete_agent(self):
        """Complete an agent."""
        tracker = ProgressTracker()
        tracker.start_agent("test-123", "planner", "Plan task", 5)

        tracker.complete_agent("test-123", success=True, message="Done")

        agent = tracker.get_agent("test-123")
        assert agent.status == "completed"

    def test_abort_agent(self):
        """Abort an agent."""
        tracker = ProgressTracker()
        tracker.start_agent("test-123", "planner", "Plan task", 5)

        tracker.abort_agent("test-123", "User cancelled")

        agent = tracker.get_agent("test-123")
        assert agent.status == "aborted"

    def test_get_running_agents(self):
        """Get only running agents."""
        tracker = ProgressTracker()
        tracker.start_agent("running-1", "planner", "Task 1", 5)
        tracker.start_agent("running-2", "researcher", "Task 2", 5)
        tracker.start_agent("done", "planner", "Task 3", 5)
        tracker.complete_agent("done", success=True)

        running = tracker.get_running_agents()
        assert len(running) == 2
        assert all(a.status == "running" for a in running)

    def test_progress_callbacks(self):
        """Progress triggers callbacks."""
        tracker = ProgressTracker(level=ProgressLevel.DETAILED)
        events = []
        tracker.on_progress(lambda e: events.append(e))

        tracker.start_agent("test-123", "planner", "Task", 5)
        tracker.update_progress("test-123", 1, "Step 1")
        tracker.complete_agent("test-123", success=True)

        # Should have start, step, and complete events
        assert len(events) >= 2

    def test_milestone(self):
        """Milestones are always emitted."""
        tracker = ProgressTracker(level=ProgressLevel.MINIMAL)
        events = []
        tracker.on_progress(lambda e: events.append(e))

        tracker.start_agent("test-123", "planner", "Task", 5)
        tracker.milestone("test-123", "Important milestone!")

        # Milestone should be emitted even at MINIMAL level
        milestone_events = [e for e in events if e.event_type == "milestone"]
        assert len(milestone_events) == 1

    def test_warning(self):
        """Warnings are tracked."""
        tracker = ProgressTracker()
        events = []
        tracker.on_progress(lambda e: events.append(e))

        tracker.start_agent("test-123", "planner", "Task", 5)
        tracker.warning("test-123", "Something concerning")

        warning_events = [e for e in events if e.event_type == "warning"]
        assert len(warning_events) == 1

    def test_format_status(self):
        """Format status for display."""
        tracker = ProgressTracker()
        tracker.start_agent("test-123", "planner", "Task 1", 5)
        tracker.update_progress("test-123", 2, "Step 2")

        status = tracker.format_status()
        assert "Active agents" in status or "planner" in status

    def test_format_summary(self):
        """Format summary for display."""
        tracker = ProgressTracker()
        tracker.start_agent("test-1", "planner", "Task 1", 5)
        tracker.start_agent("test-2", "researcher", "Task 2", 5)
        tracker.complete_agent("test-2", success=True)

        summary = tracker.format_summary()
        assert "1 running" in summary or "running" in summary

    def test_cleanup_completed(self):
        """Cleanup old completed agents."""
        tracker = ProgressTracker()
        tracker.start_agent("old", "planner", "Old task", 5)
        tracker.complete_agent("old", success=True)

        # Manually set end_time to past
        agent = tracker.get_agent("old")
        agent.end_time = datetime.now() - timedelta(hours=2)

        tracker.cleanup_completed(max_age_seconds=3600)

        assert tracker.get_agent("old") is None

    def test_recent_events(self):
        """Get recent events."""
        tracker = ProgressTracker()
        tracker.start_agent("test-123", "planner", "Task", 5)
        tracker.update_progress("test-123", 1, "Step 1")
        tracker.update_progress("test-123", 2, "Step 2")

        recent = tracker.get_recent_events(count=2)
        assert len(recent) <= 2

    def test_remove_callback(self):
        """Remove a callback."""
        tracker = ProgressTracker()
        events = []
        callback = lambda e: events.append(e)

        tracker.on_progress(callback)
        tracker.start_agent("test-1", "planner", "Task", 5)

        tracker.remove_callback(callback)
        tracker.start_agent("test-2", "planner", "Task", 5)

        # Should only have events from first agent
        assert len([e for e in events if e.agent_id == "test-2"]) == 0

    def test_progress_levels(self):
        """Different progress levels control emission."""
        # MINIMAL - only start/complete
        minimal = ProgressTracker(level=ProgressLevel.MINIMAL)
        minimal_events = []
        minimal.on_progress(lambda e: minimal_events.append(e))

        minimal.start_agent("test", "planner", "Task", 10)
        for i in range(1, 10):
            minimal.update_progress("test", i, f"Step {i}")
        minimal.complete_agent("test", success=True)

        # VERBOSE - everything
        verbose = ProgressTracker(level=ProgressLevel.VERBOSE)
        verbose_events = []
        verbose.on_progress(lambda e: verbose_events.append(e))

        verbose.start_agent("test", "planner", "Task", 10)
        for i in range(1, 10):
            verbose.update_progress("test", i, f"Step {i}")
        verbose.complete_agent("test", success=True)

        # Verbose should have more events than minimal
        assert len(verbose_events) > len(minimal_events)


class TestGlobalTracker:
    """Tests for global tracker singleton."""

    def test_get_global_tracker(self):
        """Get global tracker instance."""
        tracker1 = get_progress_tracker()
        tracker2 = get_progress_tracker()
        assert tracker1 is tracker2
