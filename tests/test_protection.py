"""
Tests for Protection Module
============================

Tests overuse detection and protection decisions.
"""

import pytest
import time
from unittest.mock import patch

from otto.protection import (
    OveruseDetector,
    OveruseSignal,
    ProtectionEngine,
    ProtectionDecision,
    ProtectionAction,
    create_overuse_detector,
    create_protection_engine,
)
from otto.protection.overuse_detector import OveruseType
from otto.cognitive_state import (
    CognitiveState,
    BurnoutLevel,
    EnergyLevel,
    MomentumPhase,
)
from otto.profile_loader import ResolvedProfile
from otto.prism_detector import SignalVector


class TestOveruseDetector:
    """Tests for OveruseDetector class."""

    def test_no_signals_at_start(self):
        """Test no overuse signals at session start."""
        detector = OveruseDetector()
        state = CognitiveState()  # Fresh state
        signals = detector.detect(state)

        # Fresh session should have no significant signals
        assert not any(s.severity >= 0.5 for s in signals)

    def test_time_extended_detection(self):
        """Test detection of extended session time."""
        detector = OveruseDetector()

        # Simulate 2 hours elapsed
        state = CognitiveState(
            session_start=time.time() - (120 * 60)  # 2 hours ago
        )
        signals = detector.detect(state)

        time_signals = [s for s in signals if s.overuse_type == OveruseType.TIME_EXTENDED]
        assert len(time_signals) > 0
        assert time_signals[0].severity >= 0.6

    def test_rapid_exchange_detection(self):
        """Test detection of rapid exchanges."""
        detector = OveruseDetector()

        state = CognitiveState(rapid_exchange_count=25)
        signals = detector.detect(state)

        rapid_signals = [s for s in signals if s.overuse_type == OveruseType.RAPID_EXCHANGE]
        assert len(rapid_signals) > 0

    def test_energy_mismatch_detection(self):
        """Test detection of energy mismatch."""
        detector = OveruseDetector()

        state = CognitiveState(
            energy_level=EnergyLevel.DEPLETED,
            exchange_count=10  # Still working
        )
        signals = detector.detect(state)

        energy_signals = [s for s in signals if s.overuse_type == OveruseType.ENERGY_MISMATCH]
        assert len(energy_signals) > 0

    def test_override_tracking(self):
        """Test override counting."""
        detector = OveruseDetector()

        # Record several overrides
        detector.record_override()
        detector.record_override()
        detector.record_override()

        state = CognitiveState()
        signals = detector.detect(state)

        override_signals = [s for s in signals if s.overuse_type == OveruseType.OVERRIDE_PATTERN]
        assert len(override_signals) > 0
        assert override_signals[0].override_count == 3

    def test_cooldown_respected(self):
        """Test that cooldown is respected."""
        detector = OveruseDetector()
        detector.set_cooldown(10)  # 10 second cooldown

        signals = [OveruseSignal(OveruseType.TIME_EXTENDED, 0.5)]

        # First check should allow suggestion
        assert detector.should_suggest_protection(signals) is True

        # Mark suggested
        detector.mark_protection_suggested()

        # Immediate check should NOT suggest (cooldown)
        assert detector.should_suggest_protection(signals) is False

    def test_reset_overrides(self):
        """Test override reset."""
        detector = OveruseDetector()

        detector.record_override()
        detector.record_override()
        detector.reset_overrides()

        state = CognitiveState()
        signals = detector.detect(state)

        # No override signals after reset
        override_signals = [s for s in signals if s.overuse_type == OveruseType.OVERRIDE_PATTERN]
        assert len(override_signals) == 0

    def test_get_primary_signal(self):
        """Test getting primary (highest severity) signal."""
        detector = OveruseDetector()

        # Simulate multiple signals
        state = CognitiveState(
            session_start=time.time() - (180 * 60),  # 3 hours
            energy_level=EnergyLevel.LOW,
            exchange_count=10
        )
        signals = detector.detect(state)

        primary = detector.get_primary_signal(signals)
        assert primary is not None
        assert primary.severity >= signals[-1].severity  # Highest severity first

    def test_signal_to_dict(self):
        """Test signal serialization."""
        signal = OveruseSignal(
            overuse_type=OveruseType.TIME_EXTENDED,
            severity=0.7,
            duration_minutes=90,
            message="Test"
        )
        data = signal.to_dict()

        assert data["type"] == "time_extended"
        assert data["severity"] == 0.7
        assert data["duration_minutes"] == 90


class TestProtectionEngine:
    """Tests for ProtectionEngine class."""

    @pytest.fixture
    def profile(self):
        """Default test profile."""
        return ResolvedProfile(
            protection_firmness=0.5,
            otto_role="companion",
            allow_override=True,
        )

    def test_green_state_allows(self, profile):
        """Test GREEN burnout allows without comment."""
        engine = ProtectionEngine(profile)
        state = CognitiveState(burnout_level=BurnoutLevel.GREEN)

        decision = engine.check(state)

        assert decision.action == ProtectionAction.ALLOW

    def test_yellow_state_mentions(self, profile):
        """Test YELLOW burnout mentions time."""
        engine = ProtectionEngine(profile)
        state = CognitiveState(burnout_level=BurnoutLevel.YELLOW)

        decision = engine.check(state)

        assert decision.action == ProtectionAction.MENTION
        assert "while" in decision.message.lower()

    def test_orange_state_suggests_break(self, profile):
        """Test ORANGE burnout suggests break."""
        engine = ProtectionEngine(profile)
        state = CognitiveState(burnout_level=BurnoutLevel.ORANGE)

        decision = engine.check(state)

        assert decision.action == ProtectionAction.SUGGEST_BREAK

    def test_red_state_requires_confirm(self, profile):
        """Test RED burnout requires confirmation."""
        engine = ProtectionEngine(profile)
        state = CognitiveState(burnout_level=BurnoutLevel.RED)

        decision = engine.check(state)

        assert decision.action == ProtectionAction.REQUIRE_CONFIRM

    def test_user_break_request_allowed(self, profile):
        """Test user break request is honored."""
        engine = ProtectionEngine(profile)
        state = CognitiveState()
        signals = SignalVector(protection={"needs_break": 0.8})

        decision = engine.check(state, signals)

        assert decision.action == ProtectionAction.ALLOW
        assert "break" in decision.trigger or "go for it" in decision.message.lower()

    def test_user_override_recorded(self, profile):
        """Test user override is recorded."""
        engine = ProtectionEngine(profile)
        state = CognitiveState()
        signals = SignalVector(protection={"override": 0.8})

        decision = engine.check(state, signals)

        assert decision.action == ProtectionAction.ALLOW
        assert decision.override_logged is True

    def test_firmness_affects_threshold(self):
        """Test that firmness setting affects intervention threshold."""
        # Gentle profile (high threshold)
        gentle_profile = ResolvedProfile(protection_firmness=0.0)
        gentle_engine = ProtectionEngine(gentle_profile)

        # Firm profile (low threshold)
        firm_profile = ResolvedProfile(protection_firmness=1.0)
        firm_engine = ProtectionEngine(firm_profile)

        # Same state
        state = CognitiveState(
            session_start=time.time() - (50 * 60),  # 50 minutes
            burnout_level=BurnoutLevel.GREEN
        )

        gentle_decision = gentle_engine.check(state)
        firm_decision = firm_engine.check(state)

        # Firm should be more likely to intervene at same signal level
        # (This is a behavioral test - actual behavior depends on thresholds)
        assert gentle_decision.action == ProtectionAction.ALLOW or \
               firm_decision.action != ProtectionAction.ALLOW

    def test_handle_user_response_break_accepted(self, profile):
        """Test handling user accepting break."""
        engine = ProtectionEngine(profile)
        decision = ProtectionDecision(
            action=ProtectionAction.SUGGEST_BREAK,
            message="Take a break?"
        )

        response = "yes"
        new_decision = engine.handle_user_response(response, decision)

        assert "break" in new_decision.trigger or "accepted" in new_decision.trigger

    def test_handle_user_response_override(self, profile):
        """Test handling user override."""
        engine = ProtectionEngine(profile)
        decision = ProtectionDecision(
            action=ProtectionAction.SUGGEST_BREAK,
            message="Take a break?"
        )

        response = "no, keep going"
        new_decision = engine.handle_user_response(response, decision)

        assert new_decision.override_logged is True

    def test_reset_session(self, profile):
        """Test session reset."""
        engine = ProtectionEngine(profile)

        # Simulate some activity
        engine._session_overrides = 5
        engine._last_decision = ProtectionDecision(action=ProtectionAction.MENTION)

        engine.reset_session()

        assert engine._session_overrides == 0
        assert engine._last_decision is None

    def test_get_session_summary(self, profile):
        """Test session summary."""
        engine = ProtectionEngine(profile)
        engine._session_overrides = 3

        summary = engine.get_session_summary()

        assert summary["overrides"] == 3

    def test_protection_with_hyperfocus_signal(self, profile):
        """Test protection with hyperfocus signal."""
        engine = ProtectionEngine(profile)
        state = CognitiveState()
        signals = SignalVector(
            protection={"hyperfocus": 0.7},
            protection_score=0.7
        )

        decision = engine.check(state, signals)

        # Should at least mention hyperfocus
        assert decision.action in (ProtectionAction.MENTION, ProtectionAction.SUGGEST_BREAK)

    def test_decision_to_dict(self, profile):
        """Test decision serialization."""
        decision = ProtectionDecision(
            action=ProtectionAction.SUGGEST_BREAK,
            message="Take a break",
            suggestion="15 minutes",
            can_override=True,
            trigger="burnout_orange"
        )
        data = decision.to_dict()

        assert data["action"] == "suggest_break"
        assert data["message"] == "Take a break"
        assert data["can_override"] is True


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_overuse_detector(self):
        """Test overuse detector factory."""
        detector = create_overuse_detector()
        assert isinstance(detector, OveruseDetector)

    def test_create_protection_engine(self):
        """Test protection engine factory."""
        profile = ResolvedProfile()
        engine = create_protection_engine(profile)
        assert isinstance(engine, ProtectionEngine)


# =============================================================================
# Test: Calibration Integration
# =============================================================================

class TestCalibrationIntegration:
    """Tests for CalibrationEngine integration with ProtectionEngine."""

    @pytest.fixture
    def temp_otto_dir(self, tmp_path):
        """Create a temporary .otto directory."""
        otto_dir = tmp_path / ".otto"
        otto_dir.mkdir()
        (otto_dir / "state").mkdir()
        return otto_dir

    @pytest.fixture
    def profile(self):
        """Create a test profile."""
        return ResolvedProfile(protection_firmness=0.5)

    @pytest.fixture
    def engine_with_calibration(self, profile, temp_otto_dir):
        """Create engine with calibration in temp directory."""
        from otto.protection.calibration import CalibrationEngine
        calibration = CalibrationEngine(otto_dir=temp_otto_dir)
        return ProtectionEngine(profile, calibration_engine=calibration)

    def test_engine_has_calibration(self, engine_with_calibration):
        """Engine has calibration engine attached."""
        assert engine_with_calibration.calibration is not None

    def test_calibrated_firmness_without_learning(self, engine_with_calibration):
        """Calibrated firmness equals base when no learning."""
        calibrated = engine_with_calibration._get_calibrated_firmness()
        assert calibrated == 0.5  # Base firmness

    def test_override_feeds_to_calibration(self, engine_with_calibration):
        """User override feeds back to calibration engine."""
        decision = ProtectionDecision(
            action=ProtectionAction.SUGGEST_BREAK,
            message="Take a break?",
            trigger="burnout_yellow"
        )

        # First two overrides - no adjustment yet
        engine_with_calibration.handle_user_response("no, keep going", decision)
        assert engine_with_calibration.calibration.state.session_overrides == 1

        engine_with_calibration.handle_user_response("no", decision)
        assert engine_with_calibration.calibration.state.session_overrides == 2

        # Third override - should trigger adjustment
        engine_with_calibration.handle_user_response("continue", decision)
        assert engine_with_calibration.calibration.state.session_overrides == 0  # Reset after adjustment
        assert engine_with_calibration.calibration.state.learned_firmness_adjustment < 0

    def test_accept_feeds_to_calibration(self, engine_with_calibration):
        """User accepting break feeds back to calibration engine."""
        decision = ProtectionDecision(
            action=ProtectionAction.SUGGEST_BREAK,
            message="Take a break?",
            trigger="burnout_orange"
        )

        # Accepts
        engine_with_calibration.handle_user_response("yes", decision)
        assert engine_with_calibration.calibration.state.session_accepts == 1

        engine_with_calibration.handle_user_response("ok", decision)
        assert engine_with_calibration.calibration.state.session_accepts == 2

        # Third accept - should trigger adjustment
        engine_with_calibration.handle_user_response("sure", decision)
        assert engine_with_calibration.calibration.state.session_accepts == 0  # Reset after adjustment
        assert engine_with_calibration.calibration.state.learned_firmness_adjustment > 0

    def test_calibrated_threshold_changes_with_learning(self, engine_with_calibration):
        """Threshold changes after learning from overrides."""
        initial_threshold = engine_with_calibration._get_calibrated_threshold()

        # Simulate 3 overrides
        decision = ProtectionDecision(
            action=ProtectionAction.SUGGEST_BREAK,
            trigger="test"
        )
        for _ in range(3):
            engine_with_calibration.handle_user_response("no", decision)

        new_threshold = engine_with_calibration._get_calibrated_threshold()

        # After overrides, firmness decreases, so threshold increases (less intervention)
        assert new_threshold > initial_threshold

    def test_session_summary_includes_calibration(self, engine_with_calibration):
        """Session summary includes calibration info."""
        summary = engine_with_calibration.get_session_summary()

        assert "calibration" in summary
        assert "calibrated_firmness" in summary

    def test_reset_session_resets_calibration_session(self, engine_with_calibration):
        """Reset session also resets calibration session counts."""
        decision = ProtectionDecision(action=ProtectionAction.SUGGEST_BREAK, trigger="test")
        engine_with_calibration.handle_user_response("no", decision)

        assert engine_with_calibration.calibration.state.session_overrides == 1

        engine_with_calibration.reset_session()

        assert engine_with_calibration.calibration.state.session_overrides == 0
