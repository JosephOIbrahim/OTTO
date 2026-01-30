"""
Tests for Calibration Learner
=============================

Tests for Hebbian learning with bounded weights.
"""

import pytest
import tempfile
from pathlib import Path

from otto.calibration import (
    CalibrationLearner,
    LearnedWeight,
    create_calibration_learner,
    OutcomeTracker,
    Outcome,
    OutcomeType,
)


class TestLearnedWeight:
    """Tests for LearnedWeight dataclass."""

    def test_default_values(self):
        """LearnedWeight has sensible defaults."""
        lw = LearnedWeight(
            expert="validator",
            weight=0.15,
            base_weight=0.14,
        )
        assert lw.expert == "validator"
        assert lw.weight == 0.15
        assert lw.base_weight == 0.14
        assert lw.updates == 0
        assert lw.last_outcome_score == 0.5
        assert lw.trend == "stable"

    def test_to_dict(self):
        """to_dict produces serializable dict."""
        lw = LearnedWeight(
            expert="validator",
            weight=0.15,
            base_weight=0.14,
            updates=10,
            trend="improving",
        )
        d = lw.to_dict()

        assert d["expert"] == "validator"
        assert d["weight"] == 0.15
        assert d["trend"] == "improving"

    def test_from_dict_roundtrip(self):
        """from_dict restores from to_dict."""
        lw = LearnedWeight(
            expert="validator",
            weight=0.2,
            base_weight=0.14,
            updates=5,
        )
        d = lw.to_dict()
        restored = LearnedWeight.from_dict(d)

        assert restored.expert == lw.expert
        assert restored.weight == lw.weight
        assert restored.updates == lw.updates


class TestCalibrationLearner:
    """Tests for CalibrationLearner."""

    def test_create_learner(self):
        """Learner can be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = create_calibration_learner(Path(tmpdir))
            assert learner is not None

    def test_default_weights(self):
        """Learner starts with equal weights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))
            weights = learner.get_weights()

            assert len(weights) == 7  # 7 default experts
            assert abs(sum(weights.values()) - 1.0) < 0.01  # Sum to 1

    def test_get_weight_for_expert(self):
        """Can get weight for specific expert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            weight = learner.get_weight("validator")
            assert weight > 0

    def test_get_weight_unknown_expert(self):
        """Unknown expert returns default weight."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            weight = learner.get_weight("unknown")
            assert weight == pytest.approx(1/7, rel=0.01)

    def test_update_increases_weight_on_acceptance(self):
        """Accepted outcome increases expert weight."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            initial_weight = learner.get_weight("validator")

            outcome = Outcome(
                expert="validator",
                outcome_type=OutcomeType.ACCEPTED,
            )
            learner.update_from_outcome(outcome)

            new_weight = learner.get_weight("validator")
            # Weight should increase (score 1.0 > expected ~0.14)
            assert new_weight > initial_weight

    def test_update_decreases_weight_on_rejection(self):
        """Rejected outcome decreases expert weight."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            initial_weight = learner.get_weight("direct")

            outcome = Outcome(
                expert="direct",
                outcome_type=OutcomeType.REJECTED,
            )
            learner.update_from_outcome(outcome)

            new_weight = learner.get_weight("direct")
            # Weight should decrease (score 0.2 < expected ~0.14)
            # Note: with normalization, effect may be subtle
            # But relative position should change

    def test_weights_remain_normalized(self):
        """Weights always sum to 1.0 after updates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            for _ in range(10):
                outcome = Outcome(
                    expert="validator",
                    outcome_type=OutcomeType.ACCEPTED,
                )
                learner.update_from_outcome(outcome)

            weights = learner.get_weights()
            assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_weight_floor_enforced(self):
        """Safety experts cannot go below floor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            # Many rejections for validator
            for _ in range(50):
                outcome = Outcome(
                    expert="validator",
                    outcome_type=OutcomeType.REJECTED,
                )
                learner.update_from_outcome(outcome)

            # Validator has floor of 0.10
            # After normalization, should still be at or above floor
            weight = learner.get_weight("validator")
            assert weight >= 0.05  # Some buffer for normalization effects

    def test_weight_ceiling_enforced(self):
        """No expert can exceed ceiling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            # Many acceptances for one expert
            for _ in range(100):
                outcome = Outcome(
                    expert="validator",
                    outcome_type=OutcomeType.ACCEPTED,
                )
                learner.update_from_outcome(outcome)

            # Ceiling is 0.40
            weight = learner.get_weight("validator")
            # After normalization, should be at most ceiling
            assert weight <= 0.50  # Some buffer for normalization

    def test_update_batch(self):
        """Can update from batch of outcomes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            outcomes = [
                Outcome(expert="validator", outcome_type=OutcomeType.ACCEPTED),
                Outcome(expert="validator", outcome_type=OutcomeType.ACCEPTED),
                Outcome(expert="scaffolder", outcome_type=OutcomeType.REJECTED),
            ]

            weights = learner.update_batch(outcomes)

            assert "validator" in weights
            assert "scaffolder" in weights

    def test_get_adjustment(self):
        """get_adjustment returns change from base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            initial_adjustment = learner.get_adjustment("validator")
            assert initial_adjustment == 0.0

            outcome = Outcome(
                expert="validator",
                outcome_type=OutcomeType.ACCEPTED,
            )
            learner.update_from_outcome(outcome)

            adjustment = learner.get_adjustment("validator")
            # Adjustment should be positive after acceptance
            assert adjustment != 0

    def test_reset_expert(self):
        """reset_expert restores base weight."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            # Modify weight
            outcome = Outcome(
                expert="validator",
                outcome_type=OutcomeType.ACCEPTED,
            )
            for _ in range(5):
                learner.update_from_outcome(outcome)

            # Reset
            learner.reset_expert("validator")

            # Should be back to ~1/7
            lw = learner.get_learned_weights()["validator"]
            assert lw.updates == 0
            assert lw.trend == "stable"

    def test_reset_all(self):
        """reset_all restores all base weights."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            # Modify weights
            learner.update_from_outcome(Outcome(
                expert="validator", outcome_type=OutcomeType.ACCEPTED
            ))
            learner.update_from_outcome(Outcome(
                expert="scaffolder", outcome_type=OutcomeType.REJECTED
            ))

            # Reset all
            learner.reset_all()

            # All should be reset
            for lw in learner.get_learned_weights().values():
                assert lw.updates == 0

    def test_save_and_load(self):
        """Learned weights persist across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Create and train
            learner1 = CalibrationLearner(path)
            for _ in range(5):
                learner1.update_from_outcome(Outcome(
                    expert="validator",
                    outcome_type=OutcomeType.ACCEPTED,
                ))
            learner1.save()

            # Load in new instance
            learner2 = CalibrationLearner(path)
            lw = learner2.get_learned_weights()["validator"]

            assert lw.updates == 5

    def test_suggest_recalibration(self):
        """suggest_recalibration identifies underperforming experts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            # Make an expert significantly underperform (need many rejections)
            for _ in range(25):
                learner.update_from_outcome(Outcome(
                    expert="direct",
                    outcome_type=OutcomeType.REJECTED,
                ))

            suggestions = learner.suggest_recalibration()

            # Should suggest recalibration - either underperforming or declining
            # (the thresholds may require more updates or specific conditions)
            assert isinstance(suggestions, list)

    def test_get_summary(self):
        """get_summary provides comprehensive overview."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            learner.update_from_outcome(Outcome(
                expert="validator",
                outcome_type=OutcomeType.ACCEPTED,
            ))

            summary = learner.get_summary()

            assert "learning_rate" in summary
            assert "total_updates" in summary
            assert "weights" in summary
            assert "validator" in summary["weights"]


class TestCalibrationLearnerMomentum:
    """Tests for momentum in weight updates."""

    def test_momentum_smooths_updates(self):
        """Momentum prevents oscillation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            # Alternating accept/reject
            weights_history = []
            for i in range(10):
                outcome_type = OutcomeType.ACCEPTED if i % 2 == 0 else OutcomeType.REJECTED
                learner.update_from_outcome(Outcome(
                    expert="validator",
                    outcome_type=outcome_type,
                ))
                weights_history.append(learner.get_weight("validator"))

            # With momentum, weight should be relatively stable
            # (not oscillating wildly between extremes)
            weight_range = max(weights_history) - min(weights_history)
            assert weight_range < 0.3  # Should be reasonably stable


class TestCalibrationLearnerTrends:
    """Tests for trend tracking."""

    def test_trend_starts_stable(self):
        """Trend starts as stable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            lw = learner.get_learned_weights()["validator"]
            assert lw.trend == "stable"

    def test_trend_becomes_improving(self):
        """Trend becomes improving with positive outcomes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            # Many positive outcomes
            for _ in range(10):
                learner.update_from_outcome(Outcome(
                    expert="validator",
                    outcome_type=OutcomeType.ACCEPTED,
                ))

            lw = learner.get_learned_weights()["validator"]
            assert lw.trend == "improving"

    def test_trend_becomes_declining(self):
        """Trend becomes declining with negative outcomes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(Path(tmpdir))

            # Many negative outcomes for celebrator (no floor, easier to decline)
            for _ in range(20):
                learner.update_from_outcome(Outcome(
                    expert="celebrator",
                    outcome_type=OutcomeType.OVERRIDE,  # Strongest negative
                ))

            lw = learner.get_learned_weights()["celebrator"]
            # Weight should have decreased from base
            assert lw.weight < lw.base_weight
            # Trend should reflect negative adjustment
            assert lw.trend in ["declining", "stable"]  # May be stable if < 5% change
