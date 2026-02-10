"""
OTTO TUI Dashboard Tests
========================

Comprehensive tests for TUI components with determinism verification.

Test Categories:
1. Constants integrity
2. State management (immutability, transitions)
3. Widget rendering (determinism)
4. Application logic
5. Determinism verification
"""

import pytest
import time
import hashlib
from typing import List, Tuple

from otto.tui.constants import (
    TUI_VERSION,
    HE2025_COMPLIANT,
    BURNOUT_LEVELS,
    BURNOUT_COLORS,
    BURNOUT_ICONS,
    BURNOUT_SEGMENTS,
    ENERGY_LEVELS,
    ENERGY_COLORS,
    MOMENTUM_PHASES,
    MOMENTUM_COLORS,
    MODES,
    MODE_COLORS,
    ALTITUDES,
    ALTITUDE_COLORS,
    PROJECT_STATUSES,
    ALERT_SEVERITIES,
    KEYBOARD_SHORTCUTS,
    WIDGET_ORDER,
    verify_constants_integrity,
)

from otto.tui.state import (
    CognitiveState,
    Project,
    Alert,
    TUIState,
    StateStore,
    get_store,
    reset_store,
    update_cognitive_state,
    update_projects,
    add_alert,
    set_connection_state,
    apply_state_update,
)

from otto.tui.widgets import (
    CognitiveStateWidget,
    ProjectCardWidget,
    AlertFeedWidget,
    CommandBarWidget,
)

from otto.tui.app import (
    OTTODashboard,
    create_dashboard,
)


# =============================================================================
# Constants Tests
# =============================================================================

class TestConstants:
    """Tests for TUI constants."""

    def test_version_defined(self):
        """Test version is defined."""
        assert TUI_VERSION is not None
        assert len(TUI_VERSION) > 0

    def test_he2025_compliance_flag(self):
        """Test Determinism flag is True."""
        assert HE2025_COMPLIANT is True

    def test_burnout_levels_complete(self):
        """Test all burnout levels have mappings."""
        for level in BURNOUT_LEVELS:
            assert level in BURNOUT_COLORS
            assert level in BURNOUT_ICONS
            assert level in BURNOUT_SEGMENTS

    def test_energy_levels_complete(self):
        """Test all energy levels have mappings."""
        for level in ENERGY_LEVELS:
            assert level in ENERGY_COLORS

    def test_momentum_phases_complete(self):
        """Test all momentum phases have mappings."""
        for phase in MOMENTUM_PHASES:
            assert phase in MOMENTUM_COLORS

    def test_modes_complete(self):
        """Test all modes have mappings."""
        for mode in MODES:
            assert mode in MODE_COLORS

    def test_constants_integrity_check(self):
        """Test constants integrity verification."""
        assert verify_constants_integrity() is True

    def test_keyboard_shortcuts_unique(self):
        """Test keyboard shortcuts are unique."""
        keys = [key for key, _, _ in KEYBOARD_SHORTCUTS]
        assert len(keys) == len(set(keys)), "Duplicate keyboard shortcuts"

    def test_widget_order_defined(self):
        """Test widget order is defined and non-empty."""
        assert len(WIDGET_ORDER) > 0
        assert "header" in WIDGET_ORDER
        assert "footer" in WIDGET_ORDER


# =============================================================================
# State Tests
# =============================================================================

class TestCognitiveState:
    """Tests for CognitiveState."""

    def test_default_creation(self):
        """Test default state creation."""
        state = CognitiveState()
        assert state.active_mode == "focused"
        assert state.burnout_level == "GREEN"
        assert state.energy_level == "high"
        assert state.momentum_phase == "cold_start"

    def test_frozen_immutability(self):
        """Test state is immutable."""
        state = CognitiveState()
        with pytest.raises(Exception):  # FrozenInstanceError
            state.burnout_level = "RED"

    def test_invalid_values_normalized(self):
        """Test invalid values are normalized to defaults."""
        state = CognitiveState(
            burnout_level="INVALID",
            energy_level="INVALID",
        )
        assert state.burnout_level == "GREEN"
        assert state.energy_level == "high"

    def test_checksum_deterministic(self):
        """
        Test checksum is deterministic.

        Determinism: Same state → same checksum.
        """
        state1 = CognitiveState(
            active_mode="focused",
            burnout_level="GREEN",
            energy_level="high",
        )
        state2 = CognitiveState(
            active_mode="focused",
            burnout_level="GREEN",
            energy_level="high",
        )

        assert state1.checksum() == state2.checksum()

    def test_checksum_different_for_different_states(self):
        """Test different states have different checksums."""
        state1 = CognitiveState(burnout_level="GREEN")
        state2 = CognitiveState(burnout_level="RED")

        assert state1.checksum() != state2.checksum()

    def test_to_dict_complete(self):
        """Test to_dict includes all fields."""
        state = CognitiveState()
        d = state.to_dict()

        assert "active_mode" in d
        assert "burnout_level" in d
        assert "energy_level" in d
        assert "momentum_phase" in d

    def test_from_dict_roundtrip(self):
        """Test from_dict/to_dict roundtrip."""
        original = CognitiveState(
            active_mode="exploring",
            burnout_level="YELLOW",
        )
        restored = CognitiveState.from_dict(original.to_dict())

        assert restored.active_mode == original.active_mode
        assert restored.burnout_level == original.burnout_level


class TestProject:
    """Tests for Project."""

    def test_creation(self):
        """Test project creation."""
        project = Project(
            id="p1",
            name="Test Project",
            status="FOCUS",
            progress=0.75,
        )

        assert project.id == "p1"
        assert project.status == "FOCUS"
        assert project.progress == 0.75

    def test_progress_clamped(self):
        """Test progress is clamped to [0, 1]."""
        project = Project(id="p1", name="Test", progress=1.5)
        assert project.progress == 1.0

        project2 = Project(id="p2", name="Test", progress=-0.5)
        assert project2.progress == 0.0


class TestAlert:
    """Tests for Alert."""

    def test_creation(self):
        """Test alert creation."""
        alert = Alert(
            id="a1",
            timestamp=1000.0,
            severity="warning",
            title="Test Alert",
            message="Test message",
        )

        assert alert.id == "a1"
        assert alert.severity == "warning"

    def test_from_dict(self):
        """Test from_dict creation."""
        data = {
            "id": "a1",
            "timestamp": 1000.0,
            "severity": "critical",
            "title": "Test",
            "message": "Message",
        }
        alert = Alert.from_dict(data)

        assert alert.severity == "critical"
        assert alert.title == "Test"


class TestTUIState:
    """Tests for TUIState."""

    def test_default_creation(self):
        """Test default state creation."""
        state = TUIState()
        assert state.connected is False
        assert len(state.projects) == 0
        assert len(state.alerts) == 0

    def test_get_focus_project(self):
        """Test get_focus_project returns correct project."""
        projects = (
            Project(id="p1", name="Background", status="BACKGROUND"),
            Project(id="p2", name="Focus", status="FOCUS"),
            Project(id="p3", name="Holding", status="HOLDING"),
        )
        state = TUIState(projects=projects)

        focus = state.get_focus_project()
        assert focus is not None
        assert focus.id == "p2"

    def test_get_recent_alerts_sorted(self):
        """
        Test get_recent_alerts returns sorted alerts.

        Determinism: Deterministic sort order.
        """
        alerts = (
            Alert(id="a1", timestamp=100.0, severity="info", title="Old", message=""),
            Alert(id="a3", timestamp=300.0, severity="info", title="Newest", message=""),
            Alert(id="a2", timestamp=200.0, severity="info", title="Middle", message=""),
        )
        state = TUIState(alerts=alerts)

        recent = state.get_recent_alerts(3)

        # Should be sorted by timestamp descending
        assert recent[0].id == "a3"
        assert recent[1].id == "a2"
        assert recent[2].id == "a1"


class TestStateStore:
    """Tests for StateStore."""

    def setup_method(self):
        """Reset store before each test."""
        reset_store()

    def test_initial_state(self):
        """Test initial state."""
        store = get_store()
        assert store.state is not None
        assert store.state.cognitive.burnout_level == "GREEN"

    def test_dispatch_cognitive_update(self):
        """Test dispatching cognitive update."""
        store = get_store()

        store.dispatch("COGNITIVE_UPDATE", {
            "burnout_level": "YELLOW",
        })

        assert store.state.cognitive.burnout_level == "YELLOW"

    def test_dispatch_alert_add(self):
        """Test dispatching alert add."""
        store = get_store()

        store.dispatch("ALERT_ADD", {
            "id": "test_alert",
            "timestamp": 1000.0,
            "severity": "warning",
            "title": "Test",
            "message": "Test message",
        })

        assert len(store.state.alerts) == 1
        assert store.state.alerts[0].id == "test_alert"

    def test_subscribe_notification(self):
        """Test subscriber receives updates."""
        store = get_store()
        notifications = []

        store.subscribe(lambda state: notifications.append(state))

        store.dispatch("COGNITIVE_UPDATE", {"burnout_level": "ORANGE"})

        assert len(notifications) == 1
        assert notifications[0].cognitive.burnout_level == "ORANGE"

    def test_state_checksum_changes(self):
        """Test state checksum changes on update."""
        store = get_store()
        checksum1 = store.get_state_checksum()

        store.dispatch("COGNITIVE_UPDATE", {"burnout_level": "RED"})
        checksum2 = store.get_state_checksum()

        assert checksum1 != checksum2


# =============================================================================
# Widget Tests
# =============================================================================

class TestCognitiveStateWidget:
    """Tests for CognitiveStateWidget."""

    def test_render_produces_panel(self):
        """Test render produces a Panel."""
        from rich.panel import Panel

        widget = CognitiveStateWidget()
        result = widget.render()

        assert isinstance(result, Panel)

    def test_render_deterministic(self):
        """
        Test render is deterministic.

        Determinism: Same state → same output.
        """
        state = CognitiveState(
            active_mode="focused",
            burnout_level="GREEN",
            energy_level="high",
        )

        widget1 = CognitiveStateWidget(state)
        widget2 = CognitiveStateWidget(state)

        # Render both
        panel1 = widget1.render()
        panel2 = widget2.render()

        # Compare rendered content (title should be same)
        assert str(panel1.title) == str(panel2.title)

    def test_update_returns_new_widget(self):
        """Test update returns new widget instance."""
        widget1 = CognitiveStateWidget()
        widget2 = widget1.update(CognitiveState(burnout_level="RED"))

        assert widget1 is not widget2


class TestProjectCardWidget:
    """Tests for ProjectCardWidget."""

    def test_render_with_no_project(self):
        """Test render when no focus project."""
        from rich.panel import Panel

        widget = ProjectCardWidget(project=None)
        result = widget.render()

        assert isinstance(result, Panel)

    def test_render_with_project(self):
        """Test render with focus project."""
        from rich.panel import Panel

        project = Project(
            id="p1",
            name="Test Project",
            status="FOCUS",
            progress=0.5,
        )
        widget = ProjectCardWidget(project=project)
        result = widget.render()

        assert isinstance(result, Panel)

    def test_progress_bar_deterministic(self):
        """
        Test progress bar is deterministic.

        Determinism: Same progress → same bar.
        """
        project = Project(id="p1", name="Test", status="FOCUS", progress=0.75)

        widget1 = ProjectCardWidget(project=project)
        widget2 = ProjectCardWidget(project=project)

        bar1 = widget1._render_progress_bar(0.75)
        bar2 = widget2._render_progress_bar(0.75)

        assert str(bar1) == str(bar2)


class TestAlertFeedWidget:
    """Tests for AlertFeedWidget."""

    def test_render_empty(self):
        """Test render with no alerts."""
        from rich.panel import Panel

        widget = AlertFeedWidget(alerts=())
        result = widget.render()

        assert isinstance(result, Panel)

    def test_render_with_alerts(self):
        """Test render with alerts."""
        from rich.panel import Panel

        alerts = (
            Alert(id="a1", timestamp=100.0, severity="info", title="Test", message=""),
        )
        widget = AlertFeedWidget(alerts=alerts)
        result = widget.render()

        assert isinstance(result, Panel)

    def test_alerts_sorted_deterministically(self):
        """
        Test alerts are sorted deterministically.

        Determinism: Same alerts → same order.
        """
        alerts = (
            Alert(id="a1", timestamp=100.0, severity="info", title="A", message=""),
            Alert(id="a2", timestamp=200.0, severity="info", title="B", message=""),
            Alert(id="a3", timestamp=100.0, severity="info", title="C", message=""),  # Same timestamp as a1
        )

        widget1 = AlertFeedWidget(alerts=alerts)
        widget2 = AlertFeedWidget(alerts=alerts)

        # Render and compare
        panel1 = widget1.render()
        panel2 = widget2.render()

        # Titles should be identical (indicating same order)
        assert str(panel1.title) == str(panel2.title)


class TestCommandBarWidget:
    """Tests for CommandBarWidget."""

    def test_render(self):
        """Test render produces Panel."""
        from rich.panel import Panel

        widget = CommandBarWidget(connected=True)
        result = widget.render()

        assert isinstance(result, Panel)

    def test_shortcuts_from_constants(self):
        """Test shortcuts rendered from constants."""
        widget = CommandBarWidget()
        shortcuts_text = widget._render_shortcuts()

        # Should contain all shortcut keys
        text_str = str(shortcuts_text)
        for key, _, _ in KEYBOARD_SHORTCUTS:
            assert key in text_str


# =============================================================================
# Application Tests
# =============================================================================

class TestOTTODashboard:
    """Tests for OTTODashboard."""

    def setup_method(self):
        """Reset store before each test."""
        reset_store()

    def test_create_dashboard(self):
        """Test dashboard creation."""
        dashboard = create_dashboard()
        assert dashboard is not None

    def test_render_produces_layout(self):
        """Test render produces a Layout."""
        from rich.layout import Layout

        dashboard = create_dashboard()
        result = dashboard.render()

        assert isinstance(result, Layout)

    def test_command_handlers_defined(self):
        """Test all command handlers are defined."""
        dashboard = create_dashboard()

        # All keyboard shortcuts should have handlers
        for _, command, _ in KEYBOARD_SHORTCUTS:
            assert command in dashboard._command_handlers

    def test_handle_key_valid(self):
        """Test handling valid key."""
        dashboard = create_dashboard()
        store = get_store()

        # Press 'h' for health
        initial_alert_count = len(store.state.alerts)
        dashboard.handle_key('h')

        # Should have added an alert
        assert len(store.state.alerts) > initial_alert_count

    def test_handle_quit(self):
        """Test quit command."""
        dashboard = create_dashboard()
        dashboard._running = True

        dashboard.handle_key('q')

        assert dashboard._running is False


# =============================================================================
# Determinism Tests
# =============================================================================

@pytest.mark.determinism
class TestHe2025Compliance:
    """
    Tests verifying Determinism.

    These tests verify that the TUI produces identical output
    for identical input, with no runtime variation.
    """

    def test_widget_order_is_fixed(self):
        """Test widget order is a tuple (immutable, ordered)."""
        assert isinstance(WIDGET_ORDER, tuple)

    def test_constants_are_immutable(self):
        """Test constants are tuples (immutable)."""
        assert isinstance(BURNOUT_LEVELS, tuple)
        assert isinstance(ENERGY_LEVELS, tuple)
        assert isinstance(MOMENTUM_PHASES, tuple)
        assert isinstance(MODES, tuple)
        assert isinstance(KEYBOARD_SHORTCUTS, tuple)

    def test_state_immutable(self):
        """Test state objects are immutable."""
        state = CognitiveState()

        # Should raise error on mutation attempt
        with pytest.raises(Exception):
            state.burnout_level = "RED"

    def test_alert_sorting_stable(self):
        """
        Test alert sorting is stable for equal timestamps.

        Determinism: Secondary sort by ID for stability.
        """
        alerts = (
            Alert(id="a3", timestamp=100.0, severity="info", title="", message=""),
            Alert(id="a1", timestamp=100.0, severity="info", title="", message=""),
            Alert(id="a2", timestamp=100.0, severity="info", title="", message=""),
        )

        state = TUIState(alerts=alerts)
        recent = state.get_recent_alerts(3)

        # Should be sorted by ID for stability
        ids = [a.id for a in recent]
        assert ids == ["a1", "a2", "a3"]

    def test_render_multiple_times_identical(self):
        """
        Test rendering same state multiple times produces identical output.

        Determinism: No runtime variation in rendering.
        """
        state = CognitiveState(
            active_mode="focused",
            burnout_level="GREEN",
            energy_level="high",
            momentum_phase="rolling",
        )

        widget = CognitiveStateWidget(state)

        # Render 10 times
        renders = [str(widget.render()) for _ in range(10)]

        # All should be identical
        for render in renders[1:]:
            assert render == renders[0]

    def test_state_transitions_deterministic(self):
        """
        Test state transitions are deterministic.

        Determinism: Same update → same result.
        """
        # Test that the same update produces the same cognitive state
        # Note: We compare cognitive checksums, not full state checksums,
        # because session_start_time differs between stores (expected behavior)

        state1 = CognitiveState(
            active_mode="focused",
            burnout_level="YELLOW",
            energy_level="high",
            session_start_time=1000.0,  # Fixed time for comparison
        )

        state2 = CognitiveState(
            active_mode="focused",
            burnout_level="YELLOW",
            energy_level="high",
            session_start_time=1000.0,  # Same fixed time
        )

        # Same inputs should produce same checksums
        assert state1.checksum() == state2.checksum()

        # Different inputs should produce different checksums
        state3 = CognitiveState(
            active_mode="exploring",  # Different mode
            burnout_level="YELLOW",
            energy_level="high",
            session_start_time=1000.0,
        )
        assert state1.checksum() != state3.checksum()

    def test_no_dict_iteration_without_sorting(self):
        """
        Test alert data uses tuple of tuples, not dict iteration.

        Determinism: Dict iteration order is implementation-defined.
        """
        alert = Alert(
            id="a1",
            timestamp=100.0,
            severity="info",
            title="Test",
            message="",
            data=(("key1", "value1"), ("key2", "value2")),
        )

        # data should be a tuple of tuples
        assert isinstance(alert.data, tuple)
        for item in alert.data:
            assert isinstance(item, tuple)

    def test_fixed_evaluation_order(self):
        """
        Test state dispatch has fixed evaluation order.

        Determinism: Fixed order prevents batch-variance.
        """
        reset_store()
        store = get_store()

        events = []

        def listener(state):
            events.append(state.cognitive.burnout_level)

        store.subscribe(listener)

        # Dispatch in specific order
        store.dispatch("COGNITIVE_UPDATE", {"burnout_level": "YELLOW"})
        store.dispatch("COGNITIVE_UPDATE", {"burnout_level": "ORANGE"})
        store.dispatch("COGNITIVE_UPDATE", {"burnout_level": "RED"})

        # Events should be in dispatch order
        assert events == ["YELLOW", "ORANGE", "RED"]

    def test_keyboard_shortcuts_fixed_order(self):
        """
        Test keyboard shortcuts are in fixed order.

        Determinism: Tuple ordering is deterministic.
        """
        # KEYBOARD_SHORTCUTS is a tuple, so iteration order is fixed
        keys = [key for key, _, _ in KEYBOARD_SHORTCUTS]

        # Iterate multiple times
        for _ in range(10):
            new_keys = [key for key, _, _ in KEYBOARD_SHORTCUTS]
            assert new_keys == keys


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for TUI."""

    def test_render_performance(self):
        """Test render completes quickly."""
        dashboard = create_dashboard()

        import time
        start = time.time()

        for _ in range(100):
            dashboard.render()

        elapsed = time.time() - start

        # 100 renders should complete in < 1 second
        assert elapsed < 1.0

    def test_state_update_performance(self):
        """Test state updates are fast."""
        reset_store()
        store = get_store()

        import time
        start = time.time()

        for i in range(1000):
            store.dispatch("COGNITIVE_UPDATE", {
                "burnout_level": "GREEN" if i % 2 == 0 else "YELLOW",
            })

        elapsed = time.time() - start

        # 1000 updates should complete in < 1 second
        assert elapsed < 1.0

    def test_alert_feed_performance(self):
        """Test alert feed with many alerts."""
        alerts = tuple(
            Alert(
                id=f"a{i}",
                timestamp=float(i),
                severity="info",
                title=f"Alert {i}",
                message="",
            )
            for i in range(100)
        )

        widget = AlertFeedWidget(alerts=alerts)

        import time
        start = time.time()

        for _ in range(100):
            widget.render()

        elapsed = time.time() - start

        # 100 renders of 100 alerts should complete in < 1 second
        assert elapsed < 1.0
