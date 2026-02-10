"""
Profile Integration Tests
=========================

Tests for intake-to-profile mapping and ProfileManager integration.

Determinism Tests:
- Deterministic trait conversion
- Sorted key iteration
- Float precision
"""

import pytest
from unittest.mock import Mock

from otto.intake.profile_integration import (
    map_chronotype,
    map_work_style,
    map_stress_response,
    map_intervention_style,
    normalize_float,
    derive_focus_level,
    derive_tangent_tendency,
    derive_perfectionism_tendency,
    derive_interruption_tolerance,
    convert_intake_to_profile,
    load_intake_to_profile_manager,
    CHRONOTYPE_MAP,
    WORK_STYLE_MAP,
    STRESS_RESPONSE_MAP,
)
from otto.core.profile import ProfileManager, Profile


# =============================================================================
# Mapping Tests
# =============================================================================

class TestChronotypeMapping:
    """Tests for chronotype mapping."""

    def test_night_owl_to_late(self):
        """night_owl maps to late."""
        assert map_chronotype("night_owl") == "late"

    def test_early_bird_to_early(self):
        """early_bird maps to early."""
        assert map_chronotype("early_bird") == "early"

    def test_variable_to_flexible(self):
        """variable maps to flexible."""
        assert map_chronotype("variable") == "flexible"

    def test_unknown_defaults_to_flexible(self):
        """Unknown values default to flexible."""
        assert map_chronotype("unknown") == "flexible"
        assert map_chronotype("") == "flexible"


class TestWorkStyleMapping:
    """Tests for work style mapping."""

    def test_deep_work_to_deep(self):
        """deep_work maps to deep."""
        assert map_work_style("deep_work") == "deep"

    def test_task_switcher_to_flow(self):
        """task_switcher maps to flow."""
        assert map_work_style("task_switcher") == "flow"

    def test_burst_to_pomodoro(self):
        """burst maps to pomodoro."""
        assert map_work_style("burst") == "pomodoro"

    def test_unknown_defaults_to_flow(self):
        """Unknown values default to flow."""
        assert map_work_style("unknown") == "flow"


class TestStressResponseMapping:
    """Tests for stress response mapping."""

    def test_avoid_to_pause(self):
        """avoid maps to pause."""
        assert map_stress_response("avoid") == "pause"

    def test_confront_to_push(self):
        """confront maps to push."""
        assert map_stress_response("confront") == "push"

    def test_deflect_to_pivot(self):
        """deflect maps to pivot."""
        assert map_stress_response("deflect") == "pivot"

    def test_process_to_pause(self):
        """process maps to pause."""
        assert map_stress_response("process") == "pause"

    def test_unknown_defaults_to_pause(self):
        """Unknown values default to pause."""
        assert map_stress_response("unknown") == "pause"


class TestInterventionStyleMapping:
    """Tests for intervention style mapping."""

    def test_direct_mappings(self):
        """Direct style names map correctly."""
        assert map_intervention_style("gentle") == "gentle"
        assert map_intervention_style("moderate") == "moderate"
        assert map_intervention_style("firm") == "firm"

    def test_otto_role_mappings(self):
        """OTTO role maps to intervention style."""
        assert map_intervention_style("guardian") == "firm"
        assert map_intervention_style("companion") == "gentle"
        assert map_intervention_style("tool") == "moderate"

    def test_unknown_defaults_to_gentle(self):
        """Unknown values default to gentle."""
        assert map_intervention_style("unknown") == "gentle"


# =============================================================================
# Normalization Tests
# =============================================================================

class TestNormalizeFloat:
    """Tests for float normalization."""

    def test_in_range_unchanged(self):
        """Values in 0-1 range are preserved with precision."""
        assert normalize_float(0.5) == 0.5
        assert normalize_float(0.123456) == 0.123456

    def test_clamped_to_min(self):
        """Negative values are clamped to 0."""
        assert normalize_float(-0.5) == 0.0
        assert normalize_float(-100) == 0.0

    def test_clamped_to_max(self):
        """Values > 1 are clamped to 1."""
        assert normalize_float(1.5) == 1.0
        assert normalize_float(100) == 1.0

    def test_precision_round_6(self):
        """Values are rounded to 6 decimal places."""
        assert normalize_float(0.1234567890) == 0.123457


# =============================================================================
# Derived Trait Tests
# =============================================================================

class TestDeriveFocusLevel:
    """Tests for focus level derivation."""

    def test_locked_in(self):
        """High duration + high switch cost = locked_in."""
        traits = {"focus_duration_minutes": 120, "context_switch_cost": 0.8}
        assert derive_focus_level(traits) == "locked_in"

    def test_scattered(self):
        """Low duration = scattered."""
        traits = {"focus_duration_minutes": 20, "context_switch_cost": 0.5}
        assert derive_focus_level(traits) == "scattered"

    def test_scattered_low_switch_cost(self):
        """Low switch cost = scattered."""
        traits = {"focus_duration_minutes": 60, "context_switch_cost": 0.2}
        assert derive_focus_level(traits) == "scattered"

    def test_moderate_default(self):
        """Middle values = moderate."""
        traits = {"focus_duration_minutes": 60, "context_switch_cost": 0.5}
        assert derive_focus_level(traits) == "moderate"

    def test_empty_traits_defaults_moderate(self):
        """Empty traits defaults to moderate."""
        assert derive_focus_level({}) == "moderate"


class TestDeriveTangentTendency:
    """Tests for tangent tendency derivation."""

    def test_task_switcher_high_tendency(self):
        """Task switchers have higher base tendency."""
        traits = {"work_style": "task_switcher", "context_switch_cost": 0.5}
        result = derive_tangent_tendency(traits)
        assert result > 0.5

    def test_deep_work_low_tendency(self):
        """Deep workers have lower base tendency."""
        traits = {"work_style": "deep_work", "context_switch_cost": 0.5}
        result = derive_tangent_tendency(traits)
        assert result < 0.5

    def test_high_switch_cost_reduces_tendency(self):
        """High switch cost reduces tendency."""
        traits_low = {"work_style": "flow", "context_switch_cost": 0.1}
        traits_high = {"work_style": "flow", "context_switch_cost": 0.9}
        assert derive_tangent_tendency(traits_low) > derive_tangent_tendency(traits_high)

    def test_result_normalized(self):
        """Result is in 0-1 range."""
        for work_style in ["deep_work", "task_switcher", "burst"]:
            for switch_cost in [0.0, 0.5, 1.0]:
                traits = {"work_style": work_style, "context_switch_cost": switch_cost}
                result = derive_tangent_tendency(traits)
                assert 0.0 <= result <= 1.0


class TestDerivePerfectionismTendency:
    """Tests for perfectionism tendency derivation."""

    def test_high_fatigue_low_overwhelm(self):
        """High fatigue + low overwhelm = high perfectionism."""
        traits = {"decision_fatigue_sensitivity": 0.9, "overwhelm_threshold": 0.1}
        result = derive_perfectionism_tendency(traits)
        assert result > 0.7

    def test_result_normalized(self):
        """Result is in 0-1 range."""
        for fatigue in [0.0, 0.5, 1.0]:
            for overwhelm in [0.0, 0.5, 1.0]:
                traits = {"decision_fatigue_sensitivity": fatigue, "overwhelm_threshold": overwhelm}
                result = derive_perfectionism_tendency(traits)
                assert 0.0 <= result <= 1.0


class TestDeriveInterruptionTolerance:
    """Tests for interruption tolerance derivation."""

    def test_low_sensitivity_fast_recovery(self):
        """Low sensitivity + fast recovery = high tolerance."""
        traits = {"notification_sensitivity": 0.1, "interruption_recovery_minutes": 1}
        result = derive_interruption_tolerance(traits)
        assert result > 0.7

    def test_high_sensitivity_low_tolerance(self):
        """High sensitivity = low tolerance."""
        traits = {"notification_sensitivity": 0.9, "interruption_recovery_minutes": 5}
        result = derive_interruption_tolerance(traits)
        assert result < 0.3

    def test_result_normalized(self):
        """Result is in 0-1 range."""
        for sensitivity in [0.0, 0.5, 1.0]:
            for recovery in [1, 5, 30]:
                traits = {"notification_sensitivity": sensitivity, "interruption_recovery_minutes": recovery}
                result = derive_interruption_tolerance(traits)
                assert 0.0 <= result <= 1.0


# =============================================================================
# Full Conversion Tests
# =============================================================================

class TestConvertIntakeToProfile:
    """Tests for full intake-to-profile conversion."""

    def test_empty_traits(self):
        """Empty traits produces derived defaults."""
        result = convert_intake_to_profile({})
        assert "focus_level" in result
        assert "tangent_tendency" in result
        assert "perfectionism_tendency" in result
        assert "interruption_tolerance" in result

    def test_chronotype_conversion(self):
        """Chronotype is converted correctly."""
        result = convert_intake_to_profile({"chronotype": "night_owl"})
        assert result["chronotype"] == "late"

    def test_work_style_conversion(self):
        """Work style is converted correctly."""
        result = convert_intake_to_profile({"work_style": "deep_work"})
        assert result["work_style"] == "deep"

    def test_stress_response_conversion(self):
        """Stress response is converted correctly."""
        result = convert_intake_to_profile({"stress_response": "confront"})
        assert result["stress_response"] == "push"

    def test_intervention_style_from_role(self):
        """Intervention style derived from OTTO role."""
        result = convert_intake_to_profile({"otto_role": "guardian"})
        assert result["intervention_style"] == "firm"

    def test_protection_firmness_overrides_style(self):
        """High protection firmness sets intervention to firm."""
        result = convert_intake_to_profile({"protection_firmness": 0.8})
        assert result["intervention_style"] == "firm"

    def test_low_firmness_gentle(self):
        """Low protection firmness sets intervention to gentle."""
        result = convert_intake_to_profile({"protection_firmness": 0.2})
        assert result["intervention_style"] == "gentle"

    def test_keys_are_sorted(self):
        """Result keys are sorted for determinism."""
        result = convert_intake_to_profile({
            "chronotype": "night_owl",
            "work_style": "deep_work",
            "stress_response": "avoid",
        })
        keys = list(result.keys())
        assert keys == sorted(keys)


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests for Determinism."""

    def test_conversion_deterministic(self):
        """Same inputs produce same outputs (100 trials)."""
        traits = {
            "chronotype": "night_owl",
            "work_style": "deep_work",
            "stress_response": "avoid",
            "protection_firmness": 0.6,
            "focus_duration_minutes": 90,
            "context_switch_cost": 0.7,
            "decision_fatigue_sensitivity": 0.5,
            "overwhelm_threshold": 0.4,
            "notification_sensitivity": 0.3,
            "interruption_recovery_minutes": 5,
        }

        results = [convert_intake_to_profile(traits) for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_sorted_keys_deterministic(self):
        """Keys are always in sorted order regardless of input order."""
        # Create traits in different orders
        traits1 = {"chronotype": "early_bird", "work_style": "burst", "stress_response": "confront"}
        traits2 = {"stress_response": "confront", "chronotype": "early_bird", "work_style": "burst"}
        traits3 = {"work_style": "burst", "stress_response": "confront", "chronotype": "early_bird"}

        result1 = convert_intake_to_profile(traits1)
        result2 = convert_intake_to_profile(traits2)
        result3 = convert_intake_to_profile(traits3)

        assert list(result1.keys()) == list(result2.keys()) == list(result3.keys())
        assert result1 == result2 == result3


# =============================================================================
# ProfileManager Integration Tests
# =============================================================================

class TestLoadIntakeToProfileManager:
    """Tests for ProfileManager integration."""

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
        return ProfileManager(storage=mock_storage)

    def test_loads_traits_into_manager(self, manager):
        """Intake traits are loaded into ProfileManager."""
        traits = {
            "chronotype": "night_owl",
            "work_style": "deep_work",
        }

        profile = load_intake_to_profile_manager(traits, manager)

        assert isinstance(profile, Profile)
        assert profile.chronotype == "late"
        assert profile.work_style == "deep"

    def test_manager_has_intake_profile(self, manager):
        """Manager reports having intake profile after load."""
        assert manager.has_intake_profile() is False

        load_intake_to_profile_manager({"chronotype": "early_bird"}, manager)

        assert manager.has_intake_profile() is True

    def test_source_is_intake(self, manager):
        """Loaded values have INTAKE source."""
        from otto.core.profile import ProfileSource

        load_intake_to_profile_manager({"chronotype": "night_owl"}, manager)

        source = manager.get_profile_source("chronotype")
        assert source == ProfileSource.INTAKE

    def test_session_overrides_intake(self, manager):
        """Session values override intake values."""
        load_intake_to_profile_manager({"chronotype": "night_owl"}, manager)
        assert manager.get_profile().chronotype == "late"

        manager.update_session("chronotype", "early")
        assert manager.get_profile().chronotype == "early"

    def test_derived_fields_populated(self, manager):
        """Derived fields are calculated and populated."""
        traits = {
            "focus_duration_minutes": 120,
            "context_switch_cost": 0.8,
        }

        profile = load_intake_to_profile_manager(traits, manager)

        assert profile.focus_level == "locked_in"
        assert profile.tangent_tendency > 0.0


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_extreme_float_values(self):
        """Extreme float values are normalized."""
        traits = {
            "protection_firmness": 1000.0,
            "context_switch_cost": -500.0,
        }
        result = convert_intake_to_profile(traits)
        # Protection firmness > 0.7 should trigger firm
        assert result["intervention_style"] == "firm"

    def test_missing_optional_fields(self):
        """Missing optional fields use defaults."""
        result = convert_intake_to_profile({})
        # Should have all derived fields
        assert "focus_level" in result
        assert "body_check_enabled" in result
        assert result["body_check_enabled"] is True

    def test_all_mapping_tables_sorted(self):
        """Verify mapping tables have sorted keys for determinism."""
        # This is a meta-test to ensure tables themselves are deterministic
        assert list(CHRONOTYPE_MAP.keys()) == sorted(CHRONOTYPE_MAP.keys())
        assert list(WORK_STYLE_MAP.keys()) == sorted(WORK_STYLE_MAP.keys())
        assert list(STRESS_RESPONSE_MAP.keys()) == sorted(STRESS_RESPONSE_MAP.keys())
