"""
Profile Manager Tests
=====================

Tests for user profile management with LIVRPS layering.

Determinism Tests:
- Deterministic profile composition
- Schema validation
- Source tracking
"""

import pytest
from unittest.mock import Mock
import json

from otto.core.profile import (
    ProfileManager,
    Profile,
    ProfileSource,
    get_profile_manager,
    reset_profile_manager,
    Chronotype,
    WorkStyle,
    StressResponse,
    FocusLevel,
    Urgency,
    DEFAULT_PROFILE,
)
from otto.core.livrps import LayerType


# =============================================================================
# Profile Tests
# =============================================================================

class TestProfile:
    """Tests for Profile dataclass."""

    def test_default_values(self):
        """Profile has sensible defaults."""
        profile = Profile()

        assert profile.chronotype == "flexible"
        assert profile.work_style == "flow"
        assert profile.stress_response == "pause"
        assert profile.focus_level == "moderate"
        assert profile.intervention_style == "gentle"
        assert profile.current_energy == "medium"

    def test_to_dict_sorted(self):
        """to_dict returns sorted keys for determinism."""
        profile = Profile()
        data = profile.to_dict()

        keys = list(data.keys())
        assert keys == sorted(keys)

    def test_from_dict_filters_unknown(self):
        """from_dict ignores unknown fields."""
        data = {
            "chronotype": "early",
            "unknown_field": "ignored",
        }
        profile = Profile.from_dict(data)

        assert profile.chronotype == "early"
        assert not hasattr(profile, "unknown_field")

    def test_compute_hash_deterministic(self):
        """compute_hash is deterministic."""
        profile1 = Profile(chronotype="early", work_style="deep")
        profile2 = Profile(chronotype="early", work_style="deep")

        assert profile1.compute_hash() == profile2.compute_hash()

    def test_compute_hash_changes(self):
        """compute_hash changes with profile."""
        profile1 = Profile(chronotype="early")
        profile2 = Profile(chronotype="late")

        assert profile1.compute_hash() != profile2.compute_hash()

    def test_validation_valid_profile(self):
        """Valid profile passes validation."""
        profile = Profile()
        errors = profile.validate()
        assert errors == []

    def test_validation_invalid_chronotype(self):
        """Invalid chronotype fails validation."""
        profile = Profile(chronotype="invalid")
        errors = profile.validate()
        assert any("chronotype" in e for e in errors)

    def test_validation_invalid_work_style(self):
        """Invalid work_style fails validation."""
        profile = Profile(work_style="invalid")
        errors = profile.validate()
        assert any("work_style" in e for e in errors)

    def test_validation_range_errors(self):
        """Out of range values fail validation."""
        profile = Profile(
            perfectionism_tendency=1.5,  # Max is 1.0
            calibration_confidence=-0.1,  # Min is 0.0
        )
        errors = profile.validate()
        assert any("perfectionism_tendency" in e for e in errors)
        assert any("calibration_confidence" in e for e in errors)


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Tests for profile enums."""

    def test_profile_source(self):
        """All profile sources exist."""
        assert ProfileSource.DEFAULTS.value == "defaults"
        assert ProfileSource.INTAKE.value == "intake"
        assert ProfileSource.CALIBRATION.value == "calibration"
        assert ProfileSource.SESSION.value == "session"

    def test_chronotype(self):
        """All chronotypes exist."""
        assert Chronotype.EARLY.value == "early"
        assert Chronotype.FLEXIBLE.value == "flexible"
        assert Chronotype.LATE.value == "late"

    def test_work_style(self):
        """All work styles exist."""
        assert WorkStyle.DEEP.value == "deep"
        assert WorkStyle.POMODORO.value == "pomodoro"
        assert WorkStyle.FLOW.value == "flow"

    def test_stress_response(self):
        """All stress responses exist."""
        assert StressResponse.PUSH.value == "push"
        assert StressResponse.PIVOT.value == "pivot"
        assert StressResponse.PAUSE.value == "pause"


# =============================================================================
# ProfileManager Tests
# =============================================================================

class TestProfileManager:
    """Tests for ProfileManager."""

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

    def test_init_creates_layers(self, manager):
        """Manager initializes all LIVRPS layers."""
        layers = manager._resolver._layers

        assert len(layers[LayerType.SPECIALIZES]) > 0  # Defaults
        assert len(layers[LayerType.PAYLOADS]) > 0     # Intake
        assert len(layers[LayerType.REFERENCES]) > 0   # Calibration
        assert len(layers[LayerType.LOCAL]) > 0        # Session

    def test_get_profile_returns_profile(self, manager):
        """get_profile returns Profile instance."""
        profile = manager.get_profile()
        assert isinstance(profile, Profile)

    def test_update_session(self, manager):
        """update_session modifies LOCAL layer."""
        manager.update_session("current_energy", "low")
        profile = manager.get_profile()
        assert profile.current_energy == "low"

    def test_update_calibration(self, manager):
        """update_calibration stores values that persist."""
        # Calibration values should be stored in REFERENCES layer
        manager.update_calibration("custom_calibration", "test_value")

        # Verify the value is accessible through composition
        result = manager.get_composition_result()
        assert result.get("custom_calibration") == "test_value"

        # Verify it's in the REFERENCES layer directly
        ref_layers = manager._resolver.get_layers(LayerType.REFERENCES)
        assert len(ref_layers) > 0
        assert ref_layers[0].get("custom_calibration") == "test_value"

    def test_load_intake_profile(self, manager):
        """load_intake_profile updates PAYLOADS layer."""
        manager.load_intake_profile({
            "chronotype": "early",
            "work_style": "deep",
            "perfectionism_tendency": 0.8,
        })

        profile = manager.get_profile()
        assert profile.chronotype == "early"
        assert profile.work_style == "deep"
        assert profile.perfectionism_tendency == 0.8

    def test_has_intake_profile_false_initially(self, manager):
        """has_intake_profile is false when no intake loaded."""
        assert manager.has_intake_profile() is False

    def test_has_intake_profile_true_after_load(self, manager):
        """has_intake_profile is true after loading intake."""
        manager.load_intake_profile({"chronotype": "early"})
        assert manager.has_intake_profile() is True

    def test_get_profile_source(self, manager):
        """get_profile_source tracks where values come from."""
        # Default values come from SPECIALIZES (when nothing else has them)
        source = manager.get_profile_source("chronotype")
        assert source == ProfileSource.DEFAULTS

        # Load intake profile - should override defaults
        manager.load_intake_profile({"chronotype": "early"})
        source = manager.get_profile_source("chronotype")
        assert source == ProfileSource.INTAKE

        # Session override takes precedence over all
        manager.update_session("chronotype", "late")
        source = manager.get_profile_source("chronotype")
        assert source == ProfileSource.SESSION

        # Session values for standard session fields
        manager.update_session("current_energy", "depleted")
        source = manager.get_profile_source("current_energy")
        assert source == ProfileSource.SESSION

    def test_increment_stats(self, manager):
        """increment_stats updates calibration statistics."""
        profile = manager.get_profile()
        assert profile.total_sessions == 0
        assert profile.crash_count == 0
        assert profile.success_count == 0

        manager.increment_stats(crash=False, success=True)
        profile = manager.get_profile()
        assert profile.total_sessions == 1
        assert profile.crash_count == 0
        assert profile.success_count == 1

        manager.increment_stats(crash=True, success=False)
        profile = manager.get_profile()
        assert profile.total_sessions == 2
        assert profile.crash_count == 1
        assert profile.success_count == 1

    def test_increment_stats_confidence(self, manager):
        """increment_stats updates calibration confidence."""
        # Confidence grows with sessions
        for i in range(5):
            manager.increment_stats()

        profile = manager.get_profile()
        assert profile.calibration_confidence == 0.25  # 5/20

        for i in range(15):
            manager.increment_stats()

        profile = manager.get_profile()
        assert profile.calibration_confidence == 1.0  # 20/20, capped

    def test_reset_session(self, manager):
        """reset_session clears session state."""
        manager.update_session("current_energy", "depleted")
        manager.update_session("session_goal", "test goal")

        manager.reset_session()

        profile = manager.get_profile()
        assert profile.current_energy == "medium"
        assert profile.session_goal == ""

    def test_save_writes_to_storage(self, manager, mock_storage):
        """save writes profile to storage."""
        manager.load_intake_profile({"chronotype": "early"})
        manager.update_calibration("focus_level", "locked_in")

        result = manager.save()

        assert result is True
        assert mock_storage.write_json.called


# =============================================================================
# Default Profile Tests
# =============================================================================

class TestDefaultProfile:
    """Tests for DEFAULT_PROFILE values."""

    def test_default_profile_complete(self):
        """Default profile has all required fields."""
        required_fields = [
            "chronotype", "work_style", "stress_response",
            "focus_level", "urgency", "preferred_depth",
            "intervention_style", "current_energy",
        ]
        for field in required_fields:
            assert field in DEFAULT_PROFILE

    def test_default_profile_valid(self):
        """Default profile creates valid Profile."""
        profile = Profile.from_dict(DEFAULT_PROFILE)
        errors = profile.validate()
        assert errors == []


# =============================================================================
# Layer Priority Tests
# =============================================================================

class TestLayerPriority:
    """Tests for LIVRPS layer priority in profiles."""

    @pytest.fixture
    def mock_storage(self):
        storage = Mock()
        storage.read_json = Mock(return_value={})
        storage.write_json = Mock(return_value=True)
        return storage

    @pytest.fixture
    def manager(self, mock_storage):
        return ProfileManager(storage=mock_storage)

    def test_session_overrides_calibration(self, manager):
        """Session (LOCAL) overrides calibration (REFERENCES)."""
        manager.update_calibration("current_energy", "high")
        assert manager.get_profile().current_energy == "high"

        manager.update_session("current_energy", "low")
        assert manager.get_profile().current_energy == "low"

    def test_calibration_overrides_intake(self, manager):
        """Calibration (REFERENCES) overrides intake (PAYLOADS)."""
        manager.load_intake_profile({"focus_level": "scattered"})
        assert manager.get_profile().focus_level == "scattered"

        manager.update_calibration("focus_level", "locked_in")
        assert manager.get_profile().focus_level == "locked_in"

    def test_intake_overrides_defaults(self, manager):
        """Intake (PAYLOADS) overrides defaults (SPECIALIZES)."""
        # Default is "flexible"
        assert manager.get_profile().chronotype == "flexible"

        manager.load_intake_profile({"chronotype": "early"})
        assert manager.get_profile().chronotype == "early"


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingleton:
    """Tests for global singleton behavior."""

    def test_get_profile_manager_returns_same_instance(self):
        """get_profile_manager returns the same instance."""
        reset_profile_manager()

        manager1 = get_profile_manager()
        manager2 = get_profile_manager()

        assert manager1 is manager2

    def test_reset_profile_manager_clears_instance(self):
        """reset_profile_manager creates new instance on next call."""
        manager1 = get_profile_manager()
        reset_profile_manager()
        manager2 = get_profile_manager()

        assert manager1 is not manager2


# =============================================================================
# Determinism Tests
# =============================================================================

class TestProfileDeterminism:
    """Tests for Determinism."""

    @pytest.fixture
    def mock_storage(self):
        storage = Mock()
        storage.read_json = Mock(return_value={})
        storage.write_json = Mock(return_value=True)
        return storage

    def test_profile_hash_determinism(self, mock_storage):
        """Same profile produces same hash for same non-timestamp fields."""
        # Timestamps are set dynamically, so compare profiles excluding them
        dynamic_fields = {"created_at", "updated_at"}

        manager1 = ProfileManager(storage=mock_storage)
        manager1.load_intake_profile({"chronotype": "early", "work_style": "deep"})
        profile1 = manager1.get_profile()
        filtered1 = {k: v for k, v in profile1.to_dict().items() if k not in dynamic_fields}

        manager2 = ProfileManager(storage=mock_storage)
        manager2.load_intake_profile({"chronotype": "early", "work_style": "deep"})
        profile2 = manager2.get_profile()
        filtered2 = {k: v for k, v in profile2.to_dict().items() if k not in dynamic_fields}

        assert filtered1 == filtered2

    def test_serialization_determinism(self, mock_storage):
        """Serialization is deterministic."""
        manager = ProfileManager(storage=mock_storage)
        manager.load_intake_profile({"chronotype": "early"})

        dict1 = manager.to_dict()
        dict2 = manager.to_dict()

        assert json.dumps(dict1, sort_keys=True) == json.dumps(dict2, sort_keys=True)

    def test_layer_composition_determinism(self, mock_storage):
        """Layer composition is deterministic (excluding timestamps)."""
        # Timestamps are dynamic, so exclude them from comparison
        dynamic_fields = {"created_at", "updated_at"}
        fixed_time = "2026-02-01T00:00:00"

        results = []
        for _ in range(10):
            manager = ProfileManager(storage=mock_storage)
            manager.load_intake_profile({
                "chronotype": "early",
                "created_at": fixed_time,
                "updated_at": fixed_time,
            })
            manager.update_calibration("focus_level", "locked_in")
            manager.update_session("current_energy", "low")
            filtered = {k: v for k, v in manager.get_profile().to_dict().items() if k not in dynamic_fields}
            results.append(filtered)

        assert all(r == results[0] for r in results)
