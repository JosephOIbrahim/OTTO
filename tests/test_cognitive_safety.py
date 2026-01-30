"""
Tests for Cognitive Safety Module.

Tests burnout cascade, recovery options, working memory limits,
and other cognitive safety constraints.

ThinkingMachines [He2025] compliance:
- Fixed constraint values
- Deterministic behavior
- Binary toggle (ON/OFF)
"""

import pytest
from unittest.mock import MagicMock, patch

from otto.adhd_support import (
    # New names (preferred)
    CognitiveSafetyConstraints,
    CognitiveSafetyCheckResult,
    CognitiveSafetyManager,
    create_cognitive_safety_manager,
    # Backward compatibility aliases
    ADHDConstraints,
    ADHDCheckResult,
    ADHDSupportManager,
    create_adhd_manager,
    # Shared
    RecoveryOption,
    RECOVERY_OPTIONS,
    WorkingMemoryTracker,
)
from otto.cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel


class TestCognitiveSafetyConstraints:
    """Test cognitive safety constraint constants."""

    def test_working_memory_limit_fixed(self):
        """Working memory limit is exactly 3."""
        assert CognitiveSafetyConstraints.WORKING_MEMORY_LIMIT == 3

    def test_body_check_interval_fixed(self):
        """Body check interval is exactly 20."""
        assert CognitiveSafetyConstraints.BODY_CHECK_INTERVAL == 20

    def test_tangent_budget_fixed(self):
        """Default tangent budget is exactly 5."""
        assert CognitiveSafetyConstraints.DEFAULT_TANGENT_BUDGET == 5

    def test_depth_limits_fixed(self):
        """Depth limits are deterministic."""
        assert CognitiveSafetyConstraints.MAX_DEPTH_DEPLETED == "minimal"
        assert CognitiveSafetyConstraints.MAX_DEPTH_LOW_ENERGY == "standard"
        assert CognitiveSafetyConstraints.MAX_DEPTH_BURNOUT == "standard"


class TestBackwardCompatibility:
    """Test that old names work as aliases."""

    def test_adhd_constraints_alias(self):
        """ADHDConstraints is an alias for CognitiveSafetyConstraints."""
        assert ADHDConstraints is CognitiveSafetyConstraints
        assert ADHDConstraints.WORKING_MEMORY_LIMIT == 3

    def test_adhd_check_result_alias(self):
        """ADHDCheckResult is an alias for CognitiveSafetyCheckResult."""
        assert ADHDCheckResult is CognitiveSafetyCheckResult

    def test_adhd_support_manager_alias(self):
        """ADHDSupportManager is an alias for CognitiveSafetyManager."""
        assert ADHDSupportManager is CognitiveSafetyManager

    def test_create_adhd_manager_works(self):
        """create_adhd_manager() still works."""
        state = MagicMock()
        state.adhd_enabled = True
        manager = create_adhd_manager(state)
        assert isinstance(manager, CognitiveSafetyManager)


class TestRecoveryOptions:
    """Test recovery option definitions."""

    def test_all_options_defined(self):
        """All RecoveryOption enum values have entries."""
        for option in RecoveryOption:
            assert option in RECOVERY_OPTIONS
            assert "label" in RECOVERY_OPTIONS[option]
            assert "description" in RECOVERY_OPTIONS[option]
            assert "action" in RECOVERY_OPTIONS[option]

    def test_done_today_option(self):
        """Done for today saves state."""
        option = RECOVERY_OPTIONS[RecoveryOption.DONE_TODAY]
        assert option["action"] == "save_and_exit"

    def test_scope_cut_option(self):
        """Scope cut reduces requirements."""
        option = RECOVERY_OPTIONS[RecoveryOption.SCOPE_CUT]
        assert option["action"] == "reduce_scope"


class TestCognitiveSafetyCheckResult:
    """Test CognitiveSafetyCheckResult dataclass."""

    def test_default_values(self):
        """Default values are safe."""
        result = CognitiveSafetyCheckResult()

        assert result.working_memory_exceeded is False
        assert result.body_check_needed is False
        assert result.recovery_needed is False
        assert result.depth_limit == "deep"

    def test_to_dict(self):
        """Serializes correctly."""
        result = CognitiveSafetyCheckResult(
            working_memory_exceeded=True,
            working_memory_items=4
        )

        d = result.to_dict()
        assert d["working_memory_exceeded"] is True
        assert d["working_memory_items"] == 4


class TestWorkingMemoryTracker:
    """Test working memory tracking."""

    def test_initial_empty(self):
        """Starts empty."""
        tracker = WorkingMemoryTracker()
        assert tracker.get_count() == 0

    def test_add_item(self):
        """Can add items."""
        tracker = WorkingMemoryTracker()

        tracker.add("task1")
        assert tracker.get_count() == 1

        tracker.add("task2")
        assert tracker.get_count() == 2

    def test_exceeds_limit_fifo(self):
        """FIFO overflow when exceeding limit."""
        tracker = WorkingMemoryTracker()

        # Add up to limit
        for i in range(CognitiveSafetyConstraints.WORKING_MEMORY_LIMIT):
            tracker.add(f"item_{i}")

        assert tracker.is_at_capacity() is True

        # Add one more - should drop first
        success, dropped = tracker.add("overflow")
        assert success is True
        assert dropped == "item_0"

    def test_remove_item(self):
        """Can remove items."""
        tracker = WorkingMemoryTracker()

        tracker.add("task1")
        tracker.add("task2")
        tracker.remove("task1")

        assert tracker.get_count() == 1

    def test_clear_all(self):
        """Can clear all items."""
        tracker = WorkingMemoryTracker()

        for i in range(3):
            tracker.add(f"item_{i}")

        tracker.clear()
        assert tracker.get_count() == 0


class TestCognitiveSafetyManager:
    """Test CognitiveSafetyManager."""

    def test_enabled_by_default_false(self):
        """Manager disabled by default."""
        manager = CognitiveSafetyManager()
        assert manager.enabled is False

    def test_toggle_enabled(self):
        """Can toggle enabled state."""
        manager = CognitiveSafetyManager(enabled=False)
        manager.set_enabled(True)
        assert manager.enabled is True

    def test_disabled_mode_allows_ultradeep(self):
        """Disabled manager allows ultradeep."""
        manager = CognitiveSafetyManager(enabled=False)
        state = MagicMock()
        state.rapid_exchange_count = 100
        state.tangent_budget = 0
        state.energy_level = EnergyLevel.DEPLETED
        state.burnout_level = BurnoutLevel.RED

        result = manager.check(state, task_items=10)

        # When disabled, should allow ultradeep
        assert result.depth_limit == "ultradeep"

    def test_enabled_detects_memory_exceeded(self):
        """Enabled manager detects memory issues."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.rapid_exchange_count = 5
        state.tangent_budget = 5
        state.energy_level = EnergyLevel.MEDIUM
        state.burnout_level = BurnoutLevel.GREEN

        result = manager.check(state, task_items=5)  # Over limit of 3

        assert result.working_memory_exceeded is True

    def test_body_check_triggered(self):
        """Body check triggered at interval."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.rapid_exchange_count = 21  # Over 20
        state.tangent_budget = 5
        state.energy_level = EnergyLevel.MEDIUM
        state.burnout_level = BurnoutLevel.GREEN

        result = manager.check(state, task_items=1)

        assert result.body_check_needed is True
        assert result.body_check_message is not None

    def test_perfectionism_detection(self):
        """Detects perfectionism phrases."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.rapid_exchange_count = 5
        state.tangent_budget = 5
        state.energy_level = EnergyLevel.MEDIUM
        state.burnout_level = BurnoutLevel.GREEN

        result = manager.check(state, task_items=1, text="let me just add one more thing")

        assert result.perfectionism_detected is True

    def test_recovery_needed_at_red(self):
        """Recovery needed when RED burnout."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.rapid_exchange_count = 5
        state.tangent_budget = 5
        state.energy_level = EnergyLevel.LOW
        state.burnout_level = BurnoutLevel.RED

        result = manager.check(state, task_items=1)

        assert result.recovery_needed is True
        assert len(result.recovery_options) > 0


class TestDepthLimiting:
    """Test thinking depth limits."""

    def test_depleted_forces_minimal(self):
        """Depleted energy forces minimal depth."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.rapid_exchange_count = 5
        state.tangent_budget = 5
        state.energy_level = EnergyLevel.DEPLETED
        state.burnout_level = BurnoutLevel.GREEN

        result = manager.check(state)
        assert result.depth_limit == "minimal"

    def test_low_energy_caps_standard(self):
        """Low energy caps at standard."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.rapid_exchange_count = 5
        state.tangent_budget = 5
        state.energy_level = EnergyLevel.LOW
        state.burnout_level = BurnoutLevel.GREEN

        result = manager.check(state)
        assert result.depth_limit == "standard"

    def test_high_energy_allows_ultradeep(self):
        """High energy allows ultradeep thinking."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.rapid_exchange_count = 5
        state.tangent_budget = 5
        state.energy_level = EnergyLevel.HIGH
        state.burnout_level = BurnoutLevel.GREEN

        result = manager.check(state)
        assert result.depth_limit == "ultradeep"


class TestDeterminism:
    """Test determinism requirements [He2025]."""

    def test_same_input_same_output(self):
        """Same inputs produce same results."""
        manager = CognitiveSafetyManager(enabled=True)

        state = MagicMock()
        state.rapid_exchange_count = 25
        state.tangent_budget = 5
        state.energy_level = EnergyLevel.MEDIUM
        state.burnout_level = BurnoutLevel.GREEN

        results = [
            manager.check(state, task_items=4, text="one more thing")
            for _ in range(10)
        ]

        # All results should be identical
        first = results[0]
        for r in results[1:]:
            assert r.working_memory_exceeded == first.working_memory_exceeded
            assert r.body_check_needed == first.body_check_needed
            assert r.perfectionism_detected == first.perfectionism_detected

    def test_constraints_never_vary(self):
        """Constraint values never change."""
        # Multiple accesses should return same values
        for _ in range(100):
            assert CognitiveSafetyConstraints.WORKING_MEMORY_LIMIT == 3
            assert CognitiveSafetyConstraints.BODY_CHECK_INTERVAL == 20
            assert CognitiveSafetyConstraints.DEFAULT_TANGENT_BUDGET == 5


class TestAgentSpawning:
    """Test agent spawning restrictions."""

    def test_orange_burnout_blocks_agents(self):
        """ORANGE burnout blocks agent spawning."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.burnout_level = BurnoutLevel.ORANGE
        state.energy_level = EnergyLevel.MEDIUM
        state.momentum_phase = MagicMock()
        state.momentum_phase.value = "rolling"

        can_spawn, reason = manager.should_spawn_agents(state)
        assert can_spawn is False
        assert "burnout" in reason.lower()

    def test_depleted_energy_blocks_agents(self):
        """Depleted energy blocks agent spawning."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.burnout_level = BurnoutLevel.GREEN
        state.energy_level = EnergyLevel.DEPLETED
        state.momentum_phase = MagicMock()
        state.momentum_phase.value = "rolling"

        can_spawn, reason = manager.should_spawn_agents(state)
        assert can_spawn is False
        assert "depleted" in reason.lower()

    def test_crashed_momentum_blocks_agents(self):
        """Crashed momentum blocks agent spawning."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.burnout_level = BurnoutLevel.GREEN
        state.energy_level = EnergyLevel.MEDIUM
        state.momentum_phase = MagicMock()
        state.momentum_phase.value = "crashed"

        can_spawn, reason = manager.should_spawn_agents(state)
        assert can_spawn is False
        assert "crashed" in reason.lower()

    def test_healthy_state_allows_agents(self):
        """Healthy state allows agent spawning."""
        manager = CognitiveSafetyManager(enabled=True)
        state = MagicMock()
        state.burnout_level = BurnoutLevel.GREEN
        state.energy_level = EnergyLevel.MEDIUM
        state.momentum_phase = MagicMock()
        state.momentum_phase.value = "rolling"

        can_spawn, reason = manager.should_spawn_agents(state)
        assert can_spawn is True
        assert reason is None
