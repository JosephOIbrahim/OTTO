"""
Cognitive State Manager Tests
=============================

Tests for state management with LIVRPS composition.

Determinism Tests:
- Deterministic state transitions
- Schema validation
- Float precision
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import json

from otto.core.state_manager import (
    CognitiveStateManager,
    CognitiveState,
    get_state_manager,
    reset_state_manager,
    BurnoutLevel,
    MomentumPhase,
    EnergyLevel,
    CognitiveMode,
    Paradigm,
    DetectedState,
    CONSTITUTIONAL_DEFAULTS,
)
from otto.core.livrps import LayerType, COGNITIVE_VARIANTS


# =============================================================================
# CognitiveState Tests
# =============================================================================

class TestCognitiveState:
    """Tests for CognitiveState dataclass."""

    def test_default_values(self):
        """State has sensible defaults."""
        state = CognitiveState()

        assert state.active_mode == "focused"
        assert state.active_paradigm == "cortex"
        assert state.burnout_level == "green"
        assert state.momentum_phase == "cold_start"
        assert state.energy_level == "medium"
        assert state.tangent_budget == 5
        assert state.exchange_count == 0
        assert state.cognitive_tile_size == 32  # fixed tile size

    def test_to_dict_sorted(self):
        """to_dict returns sorted keys for determinism."""
        state = CognitiveState()
        data = state.to_dict()

        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_from_dict_filters_unknown(self):
        """from_dict ignores unknown fields."""
        data = {
            "active_mode": "exploring",
            "unknown_field": "ignored",
        }
        state = CognitiveState.from_dict(data)

        assert state.active_mode == "exploring"
        assert not hasattr(state, "unknown_field")

    def test_compute_hash_deterministic(self):
        """compute_hash is deterministic for same field values."""
        # Use fixed values to avoid dynamic session_id/timestamp
        fixed_id = "fixed-session-id"
        fixed_time = "2026-02-01T00:00:00"

        state1 = CognitiveState(
            active_mode="focused",
            burnout_level="green",
            session_id=fixed_id,
            session_start_time=fixed_time,
        )
        state2 = CognitiveState(
            active_mode="focused",
            burnout_level="green",
            session_id=fixed_id,
            session_start_time=fixed_time,
        )

        assert state1.compute_hash() == state2.compute_hash()

    def test_compute_hash_changes(self):
        """compute_hash changes with state."""
        state1 = CognitiveState(burnout_level="green")
        state2 = CognitiveState(burnout_level="yellow")

        assert state1.compute_hash() != state2.compute_hash()

    def test_validation_valid_state(self):
        """Valid state passes validation."""
        state = CognitiveState()
        errors = state.validate()
        assert errors == []

    def test_validation_invalid_mode(self):
        """Invalid mode fails validation."""
        state = CognitiveState(active_mode="invalid")
        errors = state.validate()
        assert any("active_mode" in e for e in errors)

    def test_validation_invalid_burnout(self):
        """Invalid burnout fails validation."""
        state = CognitiveState(burnout_level="purple")
        errors = state.validate()
        assert any("burnout_level" in e for e in errors)

    def test_validation_range_errors(self):
        """Out of range values fail validation."""
        state = CognitiveState(
            epistemic_tension=1.5,  # Max is 1.0
            tangent_budget=-1,      # Min is 0
        )
        errors = state.validate()
        assert any("epistemic_tension" in e for e in errors)
        assert any("tangent_budget" in e for e in errors)

    def test_validation_fixed_tile_size(self):
        """cognitive_tile_size must be 32."""
        state = CognitiveState(cognitive_tile_size=64)
        errors = state.validate()
        assert any("cognitive_tile_size" in e for e in errors)


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Tests for state enums."""

    def test_burnout_levels(self):
        """All burnout levels exist."""
        assert BurnoutLevel.GREEN.value == "green"
        assert BurnoutLevel.YELLOW.value == "yellow"
        assert BurnoutLevel.ORANGE.value == "orange"
        assert BurnoutLevel.RED.value == "red"

    def test_momentum_phases(self):
        """All momentum phases exist."""
        assert MomentumPhase.COLD_START.value == "cold_start"
        assert MomentumPhase.BUILDING.value == "building"
        assert MomentumPhase.ROLLING.value == "rolling"
        assert MomentumPhase.PEAK.value == "peak"
        assert MomentumPhase.CRASHED.value == "crashed"

    def test_energy_levels(self):
        """All energy levels exist."""
        assert EnergyLevel.HIGH.value == "high"
        assert EnergyLevel.MEDIUM.value == "medium"
        assert EnergyLevel.LOW.value == "low"
        assert EnergyLevel.DEPLETED.value == "depleted"


# =============================================================================
# CognitiveStateManager Tests
# =============================================================================

class TestCognitiveStateManager:
    """Tests for CognitiveStateManager."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage provider."""
        storage = Mock()
        storage.read_json = Mock(return_value={})
        storage.write_json = Mock(return_value=True)
        return storage

    @pytest.fixture
    def manager(self, mock_storage):
        """Create a manager with mock storage."""
        return CognitiveStateManager(storage=mock_storage)

    def test_init_creates_layers(self, manager):
        """Manager initializes all LIVRPS layers."""
        layers = manager._resolver._layers

        assert len(layers[LayerType.SPECIALIZES]) > 0  # Constitutional
        assert len(layers[LayerType.PAYLOADS]) > 0     # Domain
        assert len(layers[LayerType.REFERENCES]) > 0   # Calibration
        assert len(layers[LayerType.VARIANTS]) > 0     # Mode variant
        assert len(layers[LayerType.INHERITS]) > 0     # Inherited
        assert len(layers[LayerType.LOCAL]) > 0        # Session

    def test_get_state_returns_cognitive_state(self, manager):
        """get_state returns CognitiveState instance."""
        state = manager.get_state()
        assert isinstance(state, CognitiveState)

    def test_update_session(self, manager):
        """update_session modifies LOCAL layer."""
        manager.update_session("burnout_level", "yellow")
        state = manager.get_state()
        assert state.burnout_level == "yellow"

    def test_update_calibration(self, manager):
        """update_calibration stores values that persist across sessions."""
        # Calibration values should be stored in REFERENCES layer
        manager.update_calibration("custom_calibration", "deep")

        # Verify the value is accessible through composition
        result = manager.get_composition_result()
        assert result.get("custom_calibration") == "deep"

        # Verify it's in the REFERENCES layer directly
        ref_layers = manager._resolver.get_layers(LayerType.REFERENCES)
        assert len(ref_layers) > 0
        assert ref_layers[0].get("custom_calibration") == "deep"

    def test_set_mode_updates_variant(self, manager):
        """set_mode changes the active variant."""
        manager.set_mode("exploring")
        state = manager.get_state()
        assert state.active_mode == "exploring"

        # Variant values should be applied
        result = manager.get_composition_result()
        assert result.get("paradigm") == "mycelium"
        assert result.get("tangent_allowance") == 5

    def test_set_mode_invalid_raises(self, manager):
        """set_mode raises for invalid mode."""
        with pytest.raises(ValueError):
            manager.set_mode("invalid_mode")

    def test_set_inherited(self, manager):
        """set_inherited sets INHERITS layer."""
        manager.set_inherited({"burnout_level": "orange", "from_parent": True})

        result = manager.get_composition_result()
        # Inherited won't override LOCAL if LOCAL has a value
        # But from_parent should be visible
        assert result.get("from_parent") is True

    def test_load_payload(self, manager):
        """load_payload updates PAYLOADS layer."""
        manager.load_payload("vfx", {"domain": "vfx", "render_engine": "karma"})

        result = manager.get_composition_result()
        assert result.get("domain") == "vfx"
        assert result.get("render_engine") == "karma"

    def test_reset_session(self, manager):
        """reset_session clears LOCAL and starts fresh."""
        manager.update_session("exchange_count", 50)
        manager.update_session("burnout_level", "orange")

        manager.reset_session()

        state = manager.get_state()
        assert state.exchange_count == 0
        assert state.momentum_phase == "cold_start"
        # Burnout should reset too (from session)

    def test_increment_exchange(self, manager):
        """increment_exchange updates count."""
        assert manager.get_state().exchange_count == 0

        count = manager.increment_exchange()
        assert count == 1
        assert manager.get_state().exchange_count == 1

        count = manager.increment_exchange()
        assert count == 2

    def test_save_writes_to_storage(self, manager, mock_storage):
        """save writes state to storage."""
        manager.update_session("burnout_level", "yellow")
        result = manager.save()

        assert result is True
        assert mock_storage.write_json.called

    def test_constitutional_defaults_applied(self, manager):
        """Constitutional defaults from constitutional.usda are available."""
        result = manager.get_composition_result()

        # These come from CONSTITUTIONAL_DEFAULTS
        assert result.get("working_memory_limit") == 3
        assert result.get("body_check_interval") == 20
        assert result.get("max_agent_depth") == 3
        assert result.get("convergence_epsilon") == 0.1


# =============================================================================
# Constitutional Defaults Tests
# =============================================================================

class TestConstitutionalDefaults:
    """Tests for constitutional defaults from constitutional.usda."""

    def test_cognitive_limits(self):
        """Cognitive limits are defined."""
        assert CONSTITUTIONAL_DEFAULTS["working_memory_limit"] == 3
        assert CONSTITUTIONAL_DEFAULTS["body_check_interval"] == 20
        assert CONSTITUTIONAL_DEFAULTS["tangent_budget_default"] == 5
        assert CONSTITUTIONAL_DEFAULTS["max_visible_subtasks"] == 5

    def test_agent_limits(self):
        """Agent orchestration limits are defined."""
        assert CONSTITUTIONAL_DEFAULTS["max_agent_depth"] == 3
        assert CONSTITUTIONAL_DEFAULTS["max_parallel_agents"] == 3

    def test_safety_floors(self):
        """Safety floors are defined."""
        assert CONSTITUTIONAL_DEFAULTS["safety_floor_validator"] == 0.10
        assert CONSTITUTIONAL_DEFAULTS["safety_floor_restorer"] == 0.05
        assert CONSTITUTIONAL_DEFAULTS["safety_floor_scaffolder"] == 0.05

    def test_intervention_thresholds(self):
        """Intervention thresholds are defined."""
        assert CONSTITUTIONAL_DEFAULTS["emotional_intervention_threshold"] == 0.5
        assert CONSTITUTIONAL_DEFAULTS["burnout_escalation_threshold"] == 0.7
        assert CONSTITUTIONAL_DEFAULTS["tension_surfacing_threshold"] == 0.3

    def test_convergence_params(self):
        """Convergence parameters are defined."""
        assert CONSTITUTIONAL_DEFAULTS["convergence_epsilon"] == 0.1
        assert CONSTITUTIONAL_DEFAULTS["convergence_stable_exchanges"] == 3
        assert CONSTITUTIONAL_DEFAULTS["tension_increase_on_switch"] == 0.3
        assert CONSTITUTIONAL_DEFAULTS["tension_decrease_when_stable"] == 0.1


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Tests for global singleton behavior."""

    def test_get_state_manager_returns_same_instance(self):
        """get_state_manager returns the same instance."""
        reset_state_manager()

        manager1 = get_state_manager()
        manager2 = get_state_manager()

        assert manager1 is manager2

    def test_reset_state_manager_clears_instance(self):
        """reset_state_manager creates new instance on next call."""
        manager1 = get_state_manager()
        reset_state_manager()
        manager2 = get_state_manager()

        assert manager1 is not manager2


# =============================================================================
# Determinism Tests
# =============================================================================

class TestStateDeterminism:
    """Tests for Determinism."""

    @pytest.fixture
    def mock_storage(self):
        storage = Mock()
        storage.read_json = Mock(return_value={})
        storage.write_json = Mock(return_value=True)
        return storage

    def test_state_hash_determinism(self, mock_storage):
        """Same state produces same hash when dynamic fields match."""
        # Fix the dynamic fields for comparison
        fixed_id = "test-session-id"
        fixed_time = "2026-02-01T00:00:00"

        manager1 = CognitiveStateManager(storage=mock_storage)
        manager1.update_session("session_id", fixed_id)
        manager1.update_session("session_start_time", fixed_time)
        manager1.update_session("burnout_level", "yellow")
        manager1.update_session("exchange_count", 10)

        manager2 = CognitiveStateManager(storage=mock_storage)
        manager2.update_session("session_id", fixed_id)
        manager2.update_session("session_start_time", fixed_time)
        manager2.update_session("burnout_level", "yellow")
        manager2.update_session("exchange_count", 10)

        assert manager1.get_state().compute_hash() == manager2.get_state().compute_hash()

    def test_serialization_determinism(self, mock_storage):
        """Serialization is deterministic."""
        manager = CognitiveStateManager(storage=mock_storage)
        manager.update_session("key", "value")

        dict1 = manager.to_dict()
        dict2 = manager.to_dict()

        assert json.dumps(dict1, sort_keys=True) == json.dumps(dict2, sort_keys=True)

    def test_mode_switch_determinism(self, mock_storage):
        """Mode switching is deterministic (excluding dynamic fields)."""
        # Dynamic fields to exclude from comparison
        dynamic_fields = {"session_id", "session_start_time"}

        results = []
        for _ in range(10):
            manager = CognitiveStateManager(storage=mock_storage)
            manager.set_mode("exploring")
            state = manager.get_state()
            # Filter out dynamic fields for comparison
            filtered = {k: v for k, v in state.to_dict().items() if k not in dynamic_fields}
            results.append(filtered)

        assert all(r == results[0] for r in results)
