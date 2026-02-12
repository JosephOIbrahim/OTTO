"""Tests for UCB1-based mode weight learning."""

from __future__ import annotations

import pytest

from otto.learner import compute_ucb_adjustments, _MAX_ADJUSTMENT
from otto.signals import Signal, SignalType
from otto.trails import TrailStore


@pytest.fixture()
def store(tmp_path) -> TrailStore:
    return TrailStore(str(tmp_path / "learner.db"))


class TestUCBFormula:
    def test_no_data_returns_empty(self, store):
        signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]
        result = compute_ucb_adjustments(signals, store)
        assert result == {}

    def test_insufficient_samples_returns_empty(self, store):
        """Fewer than MIN_SAMPLES -> no adjustment."""
        store.record_outcome("executor", "commitment_detected", "success")
        store.record_outcome("executor", "commitment_detected", "success")
        signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]
        result = compute_ucb_adjustments(signals, store)
        assert result == {}

    def test_high_success_positive_adjustment(self, store):
        for _ in range(9):
            store.record_outcome("executor", "commitment_detected", "success")
        store.record_outcome("executor", "commitment_detected", "ignored")
        signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]
        result = compute_ucb_adjustments(signals, store)
        assert result.get("executor", 0) > 0  # 90% success -> positive

    def test_low_success_negative_adjustment(self, store):
        # Need enough samples so exploration bonus doesn't overwhelm low rate
        for _ in range(5):
            store.record_outcome("executor", "commitment_detected", "success")
        for _ in range(95):
            store.record_outcome("executor", "commitment_detected", "ignored")
        signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]
        result = compute_ucb_adjustments(signals, store)
        assert result.get("executor", 0) < 0  # 5% success with many samples -> negative

    def test_clamped_to_max_adjustment(self, store):
        for _ in range(100):
            store.record_outcome("executor", "commitment_detected", "success")
        signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]
        result = compute_ucb_adjustments(signals, store)
        assert abs(result.get("executor", 0)) <= 0.2

    def test_determinism_100_iterations(self, store):
        for _ in range(5):
            store.record_outcome("executor", "commitment_detected", "success")
        for _ in range(3):
            store.record_outcome("executor", "commitment_detected", "ignored")
        signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]
        baseline = compute_ucb_adjustments(signals, store)
        for _ in range(100):
            assert compute_ucb_adjustments(signals, store) == baseline

    def test_unknown_signal_type_skipped(self, store):
        """Signals not in _SIGNAL_TO_MODE produce no adjustments."""
        store.record_outcome("executor", "nudge_fatigue", "success")
        signals = [Signal(type=SignalType.NUDGE_FATIGUE, confidence=0.8)]
        result = compute_ucb_adjustments(signals, store)
        assert result == {}

    def test_multiple_signals_multiple_modes(self, store):
        """Multiple signals can produce adjustments for different modes."""
        for _ in range(5):
            store.record_outcome("executor", "commitment_detected", "success")
        for _ in range(5):
            store.record_outcome("protector", "frustrated", "success")
        signals = [
            Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8),
            Signal(type=SignalType.FRUSTRATED, confidence=0.7),
        ]
        result = compute_ucb_adjustments(signals, store)
        assert "executor" in result
        assert "protector" in result

    def test_sorted_output_keys(self, store):
        """Output dict keys are sorted for determinism."""
        for _ in range(5):
            store.record_outcome("protector", "frustrated", "success")
        for _ in range(5):
            store.record_outcome("executor", "commitment_detected", "success")
        signals = [
            Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8),
            Signal(type=SignalType.FRUSTRATED, confidence=0.7),
        ]
        result = compute_ucb_adjustments(signals, store)
        keys = list(result.keys())
        assert keys == sorted(keys)

    def test_exploration_bonus_for_undertested_mode(self, store):
        """Modes with fewer samples get a larger exploration bonus."""
        # executor: 100 samples at 50% success
        for _ in range(50):
            store.record_outcome("executor", "commitment_detected", "success")
        for _ in range(50):
            store.record_outcome("executor", "commitment_detected", "ignored")
        # protector: 3 samples at 50% success (but with exploration bonus)
        store.record_outcome("protector", "frustrated", "success")
        store.record_outcome("protector", "frustrated", "ignored")
        store.record_outcome("protector", "frustrated", "success")

        signals_exec = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]
        signals_prot = [Signal(type=SignalType.FRUSTRATED, confidence=0.8)]

        adj_exec = compute_ucb_adjustments(signals_exec, store)
        adj_prot = compute_ucb_adjustments(signals_prot, store)

        # Protector has fewer samples -> higher exploration bonus -> higher UCB
        # Both have ~50% success rate, but protector's exploration term is larger
        assert adj_prot.get("protector", 0) > adj_exec.get("executor", 0)

    def test_exploration_bounded_at_small_n(self, store):
        """With c=0.5, exploration bonus should not overwhelm at small N."""
        # 1 success out of 5 (20% rate)
        store.record_outcome("executor", "commitment_detected", "success")
        for _ in range(4):
            store.record_outcome("executor", "commitment_detected", "ignored")
        # Pad total so all_total > 5
        for _ in range(5):
            store.record_outcome("protector", "frustrated", "success")
        signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]
        result = compute_ucb_adjustments(signals, store)
        adj = result.get("executor", 0)
        # With conservative c=0.5, adjustment should not hit the max clamp
        assert abs(adj) < _MAX_ADJUSTMENT
