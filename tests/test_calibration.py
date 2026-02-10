"""
Tests for Protection Calibration Learning.

Tests the calibration engine that learns from user overrides
to adjust protection firmness.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from otto.protection.calibration import (
    CalibrationEngine,
    CalibrationState,
    create_calibration_engine,
    OVERRIDE_THRESHOLD,
    ACCEPT_THRESHOLD,
    FIRMNESS_DECREASE,
    FIRMNESS_INCREASE,
    FIRMNESS_MIN,
    FIRMNESS_MAX,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_otto_dir(tmp_path):
    """Create a temporary .otto directory."""
    otto_dir = tmp_path / ".otto"
    otto_dir.mkdir()
    (otto_dir / "state").mkdir()
    return otto_dir


@pytest.fixture
def calibration_engine(temp_otto_dir):
    """Create a calibration engine with temp directory."""
    return CalibrationEngine(otto_dir=temp_otto_dir)


# =============================================================================
# Test: CalibrationState
# =============================================================================

class TestCalibrationState:
    """Tests for CalibrationState dataclass."""

    def test_default_values(self):
        """State has correct defaults."""
        state = CalibrationState()
        assert state.session_overrides == 0
        assert state.session_accepts == 0
        assert state.learned_firmness_adjustment == 0.0
        assert state.adjustment_history == []
        assert state.last_updated is None

    def test_to_dict(self):
        """State serializes correctly."""
        state = CalibrationState(
            session_overrides=2,
            session_accepts=1,
            learned_firmness_adjustment=-0.05,
        )
        data = state.to_dict()

        assert data["session_overrides"] == 2
        assert data["session_accepts"] == 1
        assert data["learned_firmness_adjustment"] == -0.05

    def test_from_dict(self):
        """State deserializes correctly."""
        data = {
            "session_overrides": 3,
            "session_accepts": 2,
            "learned_firmness_adjustment": 0.1,
            "adjustment_history": [{"event": "test"}],
        }
        state = CalibrationState.from_dict(data)

        assert state.session_overrides == 3
        assert state.session_accepts == 2
        assert state.learned_firmness_adjustment == 0.1
        assert len(state.adjustment_history) == 1

    def test_from_dict_handles_missing_fields(self):
        """State handles missing fields gracefully."""
        state = CalibrationState.from_dict({})

        assert state.session_overrides == 0
        assert state.session_accepts == 0
        assert state.learned_firmness_adjustment == 0.0


# =============================================================================
# Test: CalibrationEngine Initialization
# =============================================================================

class TestCalibrationEngineInit:
    """Tests for calibration engine initialization."""

    def test_init_creates_fresh_state(self, temp_otto_dir):
        """Engine creates fresh state when no file exists."""
        engine = CalibrationEngine(otto_dir=temp_otto_dir)

        assert engine.state.session_overrides == 0
        assert engine.state.learned_firmness_adjustment == 0.0

    def test_init_loads_existing_state(self, temp_otto_dir):
        """Engine loads existing state from disk."""
        # Write existing state
        state_file = temp_otto_dir / "state" / "calibration.json"
        state_file.parent.mkdir(exist_ok=True)
        state_file.write_text(json.dumps({
            "session_overrides": 1,
            "learned_firmness_adjustment": -0.1,
        }))

        engine = CalibrationEngine(otto_dir=temp_otto_dir)

        assert engine.state.session_overrides == 1
        assert engine.state.learned_firmness_adjustment == -0.1

    def test_init_handles_corrupted_file(self, temp_otto_dir):
        """Engine handles corrupted state file gracefully."""
        state_file = temp_otto_dir / "state" / "calibration.json"
        state_file.parent.mkdir(exist_ok=True)
        state_file.write_text("not valid json")

        engine = CalibrationEngine(otto_dir=temp_otto_dir)

        # Should use defaults
        assert engine.state.session_overrides == 0


# =============================================================================
# Test: Override Recording
# =============================================================================

class TestOverrideRecording:
    """Tests for recording user overrides."""

    def test_record_override_increments_count(self, calibration_engine):
        """Recording override increments session count."""
        calibration_engine.record_override("burnout_yellow", 0.5)

        assert calibration_engine.state.session_overrides == 1

    def test_record_override_no_adjustment_below_threshold(self, calibration_engine):
        """No adjustment until threshold reached."""
        for i in range(OVERRIDE_THRESHOLD - 1):
            result = calibration_engine.record_override("test", 0.5)
            assert result is None

        assert calibration_engine.state.learned_firmness_adjustment == 0.0

    def test_record_override_adjusts_at_threshold(self, calibration_engine):
        """Adjustment occurs when threshold reached."""
        for i in range(OVERRIDE_THRESHOLD - 1):
            calibration_engine.record_override("test", 0.5)

        result = calibration_engine.record_override("test", 0.5)

        assert result is not None
        assert result < 0.5  # Firmness decreased
        assert calibration_engine.state.learned_firmness_adjustment == -FIRMNESS_DECREASE

    def test_record_override_resets_count_after_adjustment(self, calibration_engine):
        """Session count resets after adjustment."""
        for i in range(OVERRIDE_THRESHOLD):
            calibration_engine.record_override("test", 0.5)

        assert calibration_engine.state.session_overrides == 0

    def test_record_override_respects_minimum(self, calibration_engine):
        """Firmness cannot go below minimum."""
        # Set very low adjustment
        calibration_engine.state.learned_firmness_adjustment = -0.5

        for i in range(OVERRIDE_THRESHOLD):
            result = calibration_engine.record_override("test", 0.1)

        # Should be bounded to minimum
        assert result is not None
        assert result >= FIRMNESS_MIN

    def test_record_override_saves_state(self, calibration_engine, temp_otto_dir):
        """Adjustment saves state to disk."""
        for i in range(OVERRIDE_THRESHOLD):
            calibration_engine.record_override("test", 0.5)

        state_file = temp_otto_dir / "state" / "calibration.json"
        assert state_file.exists()

        with open(state_file) as f:
            data = json.load(f)
        assert data["learned_firmness_adjustment"] == -FIRMNESS_DECREASE

    def test_record_override_adds_to_history(self, calibration_engine):
        """Adjustment adds event to history."""
        for i in range(OVERRIDE_THRESHOLD):
            calibration_engine.record_override("burnout_orange", 0.5)

        assert len(calibration_engine.state.adjustment_history) == 1
        assert calibration_engine.state.adjustment_history[0]["event_type"] == "override"
        assert calibration_engine.state.adjustment_history[0]["trigger"] == "burnout_orange"


# =============================================================================
# Test: Accept Recording
# =============================================================================

class TestAcceptRecording:
    """Tests for recording user acceptances."""

    def test_record_accept_increments_count(self, calibration_engine):
        """Recording accept increments session count."""
        calibration_engine.record_accept("time_check", 0.5)

        assert calibration_engine.state.session_accepts == 1

    def test_record_accept_no_adjustment_below_threshold(self, calibration_engine):
        """No adjustment until threshold reached."""
        for i in range(ACCEPT_THRESHOLD - 1):
            result = calibration_engine.record_accept("test", 0.5)
            assert result is None

    def test_record_accept_adjusts_at_threshold(self, calibration_engine):
        """Adjustment occurs when threshold reached."""
        for i in range(ACCEPT_THRESHOLD - 1):
            calibration_engine.record_accept("test", 0.5)

        result = calibration_engine.record_accept("test", 0.5)

        assert result is not None
        assert result > 0.5  # Firmness increased
        assert calibration_engine.state.learned_firmness_adjustment == FIRMNESS_INCREASE

    def test_record_accept_respects_maximum(self, calibration_engine):
        """Firmness cannot go above maximum."""
        calibration_engine.state.learned_firmness_adjustment = 0.5

        for i in range(ACCEPT_THRESHOLD):
            result = calibration_engine.record_accept("test", 0.9)

        assert result is not None
        assert result <= FIRMNESS_MAX


# =============================================================================
# Test: Recommended Firmness
# =============================================================================

class TestRecommendedFirmness:
    """Tests for firmness recommendation."""

    def test_get_recommended_no_adjustment(self, calibration_engine):
        """Returns base firmness when no adjustment."""
        result = calibration_engine.get_recommended_firmness(0.5)
        assert result == 0.5

    def test_get_recommended_with_negative_adjustment(self, calibration_engine):
        """Returns decreased firmness with negative adjustment."""
        calibration_engine.state.learned_firmness_adjustment = -0.1
        result = calibration_engine.get_recommended_firmness(0.5)
        assert result == 0.4

    def test_get_recommended_with_positive_adjustment(self, calibration_engine):
        """Returns increased firmness with positive adjustment."""
        calibration_engine.state.learned_firmness_adjustment = 0.1
        result = calibration_engine.get_recommended_firmness(0.5)
        assert result == 0.6

    def test_get_recommended_respects_bounds(self, calibration_engine):
        """Recommended firmness stays within bounds."""
        calibration_engine.state.learned_firmness_adjustment = -1.0
        result = calibration_engine.get_recommended_firmness(0.5)
        assert result >= FIRMNESS_MIN

        calibration_engine.state.learned_firmness_adjustment = 1.0
        result = calibration_engine.get_recommended_firmness(0.5)
        assert result <= FIRMNESS_MAX


# =============================================================================
# Test: Session Management
# =============================================================================

class TestSessionManagement:
    """Tests for session management."""

    def test_reset_session_clears_counts(self, calibration_engine):
        """Reset clears session counts."""
        calibration_engine.state.session_overrides = 5
        calibration_engine.state.session_accepts = 3

        calibration_engine.reset_session()

        assert calibration_engine.state.session_overrides == 0
        assert calibration_engine.state.session_accepts == 0

    def test_reset_session_preserves_learned_adjustment(self, calibration_engine):
        """Reset preserves learned adjustment."""
        calibration_engine.state.learned_firmness_adjustment = -0.1

        calibration_engine.reset_session()

        assert calibration_engine.state.learned_firmness_adjustment == -0.1

    def test_get_summary(self, calibration_engine):
        """Get summary returns correct data."""
        calibration_engine.state.session_overrides = 2
        calibration_engine.state.session_accepts = 1
        calibration_engine.state.learned_firmness_adjustment = -0.05

        summary = calibration_engine.get_summary()

        assert summary["session_overrides"] == 2
        assert summary["session_accepts"] == 1
        assert summary["learned_adjustment"] == -0.05


# =============================================================================
# Test: Factory Function
# =============================================================================

class TestFactory:
    """Tests for factory function."""

    def test_create_calibration_engine(self, temp_otto_dir):
        """Factory creates engine."""
        engine = create_calibration_engine(otto_dir=temp_otto_dir)

        assert isinstance(engine, CalibrationEngine)
        assert engine.otto_dir == temp_otto_dir

    def test_create_calibration_engine_default_dir(self):
        """Factory uses default directory."""
        with patch.object(Path, "home", return_value=Path("/tmp/test_home")):
            engine = create_calibration_engine()

        assert str(engine.otto_dir).endswith(".otto")


# =============================================================================
# Test: Determinism Compliance
# =============================================================================

class TestDeterminismCompliance:
    """Tests for determinism ([He2025])."""

    def test_constants_are_fixed(self):
        """All constants are fixed values."""
        assert OVERRIDE_THRESHOLD == 3
        assert ACCEPT_THRESHOLD == 3
        assert FIRMNESS_DECREASE == 0.05
        assert FIRMNESS_INCREASE == 0.02
        assert FIRMNESS_MIN == 0.1
        assert FIRMNESS_MAX == 0.9

    def test_adjustment_is_deterministic(self, calibration_engine):
        """Same inputs produce same outputs."""
        # First run
        engine1 = CalibrationEngine(otto_dir=calibration_engine.otto_dir)
        for i in range(OVERRIDE_THRESHOLD):
            engine1.record_override("test", 0.5)
        adj1 = engine1.state.learned_firmness_adjustment

        # Reset and second run
        engine1.state = CalibrationState()
        for i in range(OVERRIDE_THRESHOLD):
            engine1.record_override("test", 0.5)
        adj2 = engine1.state.learned_firmness_adjustment

        assert adj1 == adj2  # Deterministic

    def test_bounds_prevent_extreme_values(self, calibration_engine):
        """Bounds prevent firmness from going to extremes."""
        # Try to go too low
        calibration_engine.state.learned_firmness_adjustment = -10.0
        result = calibration_engine.get_recommended_firmness(0.5)
        assert result >= FIRMNESS_MIN

        # Try to go too high
        calibration_engine.state.learned_firmness_adjustment = 10.0
        result = calibration_engine.get_recommended_firmness(0.5)
        assert result <= FIRMNESS_MAX
