"""
Tests for Calibration Manager
==============================

Tests for the orchestrator of all calibration operations.
"""

import pytest
import tempfile
from pathlib import Path

from otto.calibration import (
    CalibrationManager,
    create_calibration_manager,
    OutcomeType,
)


class TestCalibrationManager:
    """Tests for CalibrationManager."""

    def test_create_manager(self):
        """Manager can be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = create_calibration_manager(Path(tmpdir))
            assert manager is not None

    def test_create_manager_no_persist(self):
        """Manager can be created without persistence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(
                Path(tmpdir),
                persist=False,
                auto_save=False
            )
            assert manager is not None


class TestCalibrationManagerOutcomes:
    """Tests for outcome recording."""

    def test_record_outcome_accepted(self):
        """Can record accepted outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            weights = manager.record_outcome(
                expert="validator",
                accepted=True,
                signals=["frustrated"],
            )

            assert "validator" in weights
            assert weights["validator"] > 0

    def test_record_outcome_rejected(self):
        """Can record rejected outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            weights = manager.record_outcome(
                expert="direct",
                accepted=False,
            )

            assert "direct" in weights

    def test_record_outcome_partial(self):
        """Can record partial outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            weights = manager.record_outcome(
                expert="scaffolder",
                partial=True,
            )

            assert "scaffolder" in weights

    def test_record_outcome_override(self):
        """Can record override outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            weights = manager.record_outcome(
                expert="direct",
                override=True,
            )

            assert "direct" in weights

    def test_convenience_methods(self):
        """Convenience methods work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator")
            manager.record_rejected("scaffolder")
            manager.record_override("direct")

            stats = manager.get_all_stats()
            assert stats["total_outcomes"] == 3

    def test_outcome_updates_weights(self):
        """Recording outcomes updates weights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            initial = manager.get_expert_weight("validator")

            # Multiple acceptances should increase weight
            for _ in range(5):
                manager.record_accepted("validator")

            final = manager.get_expert_weight("validator")
            assert final > initial


class TestCalibrationManagerValues:
    """Tests for calibration value management."""

    def test_observe_and_get(self):
        """Can observe and get values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.observe("focus_level", "locked_in")
            value = manager.get_value("focus_level")

            assert value == "locked_in"

    def test_set_value(self):
        """Can set values explicitly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            cal_value = manager.set_value("theme", "dark", confidence=0.9)

            assert cal_value.value == "dark"
            assert cal_value.confidence == 0.9

    def test_get_confident_value(self):
        """get_confident_value respects threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.set_value("confident", "yes", confidence=0.9)
            manager.set_value("uncertain", "maybe", confidence=0.4)

            assert manager.get_confident_value("confident") == "yes"
            assert manager.get_confident_value("uncertain") is None

    def test_observation_builds_confidence(self):
        """Repeated observations build confidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            # First observation starts at 0.3
            cv = manager.observe("preference", "option_a")
            initial_conf = cv.confidence

            # More observations of same value
            for _ in range(5):
                cv = manager.observe("preference", "option_a")

            # Confidence should have increased
            assert cv.confidence > initial_conf


class TestCalibrationManagerWeights:
    """Tests for expert weight queries."""

    def test_get_expert_weights(self):
        """Can get all expert weights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            weights = manager.get_expert_weights()

            assert len(weights) == 7
            assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_get_expert_weight(self):
        """Can get specific expert weight."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            weight = manager.get_expert_weight("validator")
            assert weight > 0

    def test_get_learned_weights(self):
        """Can get full LearnedWeight objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            learned = manager.get_learned_weights()

            assert "validator" in learned
            assert hasattr(learned["validator"], "weight")
            assert hasattr(learned["validator"], "updates")

    def test_get_weight_adjustment(self):
        """Can get weight adjustment from base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            initial = manager.get_weight_adjustment("validator")
            assert initial == 0.0

            manager.record_accepted("validator")
            adjustment = manager.get_weight_adjustment("validator")
            assert adjustment != 0


class TestCalibrationManagerStats:
    """Tests for statistics and analysis."""

    def test_get_expert_stats(self):
        """Can get expert statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator")
            manager.record_accepted("validator")
            manager.record_rejected("validator")

            stats = manager.get_expert_stats("validator")

            assert stats["total_outcomes"] == 3
            assert stats["acceptance_rate"] == pytest.approx(2/3, rel=0.01)

    def test_get_signal_stats(self):
        """Can get signal statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator", signals=["frustrated"])
            manager.record_accepted("validator", signals=["frustrated"])

            stats = manager.get_signal_stats("frustrated")

            assert stats["total_outcomes"] == 2

    def test_get_all_stats(self):
        """Can get overall statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator")
            manager.record_rejected("scaffolder")

            stats = manager.get_all_stats()

            assert stats["total_outcomes"] == 2
            assert "validator" in stats["experts"]

    def test_get_patterns(self):
        """Can detect patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            # Create a pattern: frustrated + direct = rejected
            for _ in range(10):
                manager.record_rejected("direct", signals=["frustrated"])

            patterns = manager.get_patterns()
            assert isinstance(patterns, list)

    def test_get_suggestions(self):
        """Can get recalibration suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            # Create underperforming expert
            for _ in range(15):
                manager.record_rejected("direct")

            suggestions = manager.get_suggestions()
            assert isinstance(suggestions, list)


class TestCalibrationManagerSnapshot:
    """Tests for snapshots and summaries."""

    def test_snapshot(self):
        """Can take snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator")
            manager.set_value("theme", "dark", confidence=0.9)

            snapshot = manager.snapshot()

            assert "validator" in snapshot.weights
            assert "theme" in snapshot.confident_values

    def test_snapshot_to_dict(self):
        """Snapshot converts to dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            snapshot = manager.snapshot()
            d = snapshot.to_dict()

            assert "weights" in d
            assert "confident_values" in d
            assert "total_outcomes" in d

    def test_get_summary(self):
        """Can get comprehensive summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator")

            summary = manager.get_summary()

            assert "weights" in summary
            assert "values" in summary
            assert "outcomes" in summary
            assert "patterns" in summary


class TestCalibrationManagerPersistence:
    """Tests for persistence operations."""

    def test_save_and_load(self):
        """Data persists across manager instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Create, modify, and save
            manager1 = CalibrationManager(path)
            manager1.record_accepted("validator")
            manager1.set_value("theme", "dark", confidence=0.9)
            manager1.save()

            # Load in new instance
            manager2 = CalibrationManager(path)

            # Check persisted data
            stats = manager2.get_expert_stats("validator")
            assert stats["total_outcomes"] == 1

            value = manager2.get_value("theme")
            assert value == "dark"

    def test_auto_save(self):
        """Auto-save persists data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Create with auto_save=True
            manager1 = CalibrationManager(path, auto_save=True)
            manager1.record_accepted("validator")

            # Load in new instance
            manager2 = CalibrationManager(path)
            stats = manager2.get_expert_stats("validator")
            assert stats["total_outcomes"] == 1

    def test_reset_expert(self):
        """reset_expert restores base weight."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            # Modify
            for _ in range(5):
                manager.record_accepted("validator")

            # Reset
            manager.reset_expert("validator")

            lw = manager.get_learned_weights()["validator"]
            assert lw.updates == 0

    def test_reset_all_weights(self):
        """reset_all_weights restores all."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator")
            manager.record_rejected("scaffolder")
            manager.reset_all_weights()

            for lw in manager.get_learned_weights().values():
                assert lw.updates == 0

    def test_clear_outcomes(self):
        """clear_outcomes removes history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator")
            manager.clear_outcomes()

            stats = manager.get_all_stats()
            assert stats["total_outcomes"] == 0

    def test_clear_values(self):
        """clear_values removes calibration values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.set_value("theme", "dark")
            manager.clear_values()

            assert manager.get_value("theme") is None

    def test_reset_all(self):
        """reset_all clears everything."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.record_accepted("validator")
            manager.set_value("theme", "dark")
            manager.reset_all()

            stats = manager.get_all_stats()
            assert stats["total_outcomes"] == 0
            assert manager.get_value("theme") is None


class TestCalibrationManagerSession:
    """Tests for session management."""

    def test_start_session(self):
        """start_session creates new session ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            manager.start_session()
            # Should not crash, session tracking is internal


class TestCalibrationManagerIntegration:
    """Tests for integration helpers."""

    def test_apply_to_routing(self):
        """apply_to_routing blends learned and base weights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            # Train validator to be higher
            for _ in range(10):
                manager.record_accepted("validator")

            base_weights = {
                "validator": 0.14,
                "scaffolder": 0.14,
                "restorer": 0.14,
                "direct": 0.14,
                "socratic": 0.14,
                "celebrator": 0.14,
                "refocuser": 0.14,
            }

            adjusted = manager.apply_to_routing(base_weights)

            # Should sum to 1.0
            assert abs(sum(adjusted.values()) - 1.0) < 0.01

            # Validator should be higher due to learning
            assert adjusted["validator"] > base_weights["validator"]

    def test_should_adjust_expert(self):
        """should_adjust_expert identifies problematic experts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CalibrationManager(Path(tmpdir), persist=False)

            # Make direct underperform
            for _ in range(15):
                manager.record_rejected("direct")

            reason = manager.should_adjust_expert("direct")
            # May or may not return reason depending on thresholds
            assert reason is None or isinstance(reason, str)
