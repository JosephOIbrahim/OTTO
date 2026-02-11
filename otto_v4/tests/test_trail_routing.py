"""Tests for trail-router integration (Phase 5.2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from otto.modes.executor import ExecutorMode
from otto.modes.protector import ProtectorMode
from otto.modes.restorer import RestorerMode
from otto.router import compute_trail_adjustments, route
from otto.signals import Signal, SignalType
from otto.state import CognitiveState
from otto.trails import TrailStore


def _signal(stype: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=stype, confidence=confidence, source="pattern")


def _ts() -> datetime:
    return datetime(2026, 2, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def trail_store(tmp_path) -> TrailStore:
    return TrailStore(db_path=str(tmp_path / "trails.db"))


@pytest.fixture()
def all_modes():
    return [ExecutorMode(), ProtectorMode(), RestorerMode()]


class TestComputeTrailAdjustments:
    def test_no_trails_empty_adjustments(self, trail_store):
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        adj = compute_trail_adjustments(signals, trail_store)
        assert adj == {}

    def test_strong_trail_positive_adjustment(self, trail_store):
        # Deposit strong trail for executor on commitment context
        trail_store.deposit("executor:nudge", "commitment_detected", 3.0, now=_ts())
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        adj = compute_trail_adjustments(signals, trail_store)
        assert "executor" in adj
        assert adj["executor"] > 0

    def test_weak_trail_negative_adjustment(self, trail_store):
        # Deposit weak trail (below baseline of 1.0)
        trail_store.deposit("executor:nudge", "commitment_detected", 0.3, now=_ts())
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        adj = compute_trail_adjustments(signals, trail_store)
        assert "executor" in adj
        assert adj["executor"] < 0

    def test_baseline_trail_zero_adjustment(self, trail_store):
        # Trail at exactly baseline strength
        trail_store.deposit("executor:nudge", "commitment_detected", 1.0, now=_ts())
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        adj = compute_trail_adjustments(signals, trail_store)
        assert adj.get("executor", 0) == 0.0

    def test_adjustment_clamped_to_max(self, trail_store):
        # Very strong trail -> adjustment clamped to 0.2
        trail_store.deposit("executor:nudge", "commitment_detected", 100.0, now=_ts())
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        adj = compute_trail_adjustments(signals, trail_store)
        assert adj["executor"] <= 0.2

    def test_adjustments_sorted_by_mode_name(self, trail_store):
        trail_store.deposit("restorer:rest", "depleted", 3.0, now=_ts())
        trail_store.deposit("executor:nudge", "depleted", 3.0, now=_ts())
        signals = [_signal(SignalType.DEPLETED)]
        adj = compute_trail_adjustments(signals, trail_store)
        keys = list(adj.keys())
        assert keys == sorted(keys)


class TestTrailsInfluenceRouting:
    def test_strong_trail_boosts_mode_weight(self, trail_store, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.7)]
        state = CognitiveState()

        # Route without trails
        d_no_trail = route(signals, state, all_modes)

        # Deposit strong executor trail
        trail_store.deposit("executor:nudge", "commitment_detected", 3.0, now=_ts())
        adj = compute_trail_adjustments(signals, trail_store)
        d_with_trail = route(signals, state, all_modes, trail_adjustments=adj)

        assert d_with_trail.weights["executor"] >= d_no_trail.weights["executor"]

    def test_decayed_trail_has_minimal_influence(self, trail_store, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.7)]
        state = CognitiveState()

        # Deposit trail at baseline (strength=1.0) -> zero adjustment
        trail_store.deposit("executor:nudge", "commitment_detected", 1.0, now=_ts())
        adj = compute_trail_adjustments(signals, trail_store)

        d_no_trail = route(signals, state, all_modes)
        d_with_trail = route(signals, state, all_modes, trail_adjustments=adj)

        # Weights should be identical (adjustment is 0.0)
        assert d_with_trail.weights["executor"] == d_no_trail.weights["executor"]

    def test_no_trails_uses_default_weights(self, trail_store, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()

        adj = compute_trail_adjustments(signals, trail_store)
        d1 = route(signals, state, all_modes)
        d2 = route(signals, state, all_modes, trail_adjustments=adj)

        assert d1 == d2

    def test_trails_cannot_override_safety_floors(self, trail_store, all_modes):
        """Even with negative trail adjustment, safety floors hold."""
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.7)]
        state = CognitiveState()

        # Try to penalize protector
        trail_store.deposit("protector:validate", "commitment_detected", 0.01, now=_ts())
        adj = compute_trail_adjustments(signals, trail_store)
        decision = route(signals, state, all_modes, trail_adjustments=adj)

        # Protector should still be at least 10% (safety floor)
        assert decision.weights["protector"] >= 0.10
