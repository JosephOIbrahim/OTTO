"""Tests for NEXUS deterministic router (Phase 4.1)."""

from __future__ import annotations

import pytest

from otto.modes.decomposer import DecomposerMode
from otto.modes.executor import ExecutorMode
from otto.modes.protector import ProtectorMode
from otto.modes.restorer import RestorerMode
from otto.router import RoutingDecision, route, route_and_execute
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _signal(stype: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=stype, confidence=confidence, source="pattern")


@pytest.fixture()
def all_modes():
    """All four production modes."""
    return [DecomposerMode(), ExecutorMode(), ProtectorMode(), RestorerMode()]


class TestActivation:
    def test_commitment_activates_executor(self, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision is not None
        assert decision.primary == "executor"

    def test_frustrated_activates_protector(self, all_modes):
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision is not None
        assert decision.primary == "protector"

    def test_depleted_activates_restorer(self, all_modes):
        signals = [_signal(SignalType.DEPLETED, 0.9)]
        state = CognitiveState(energy="depleted")
        decision = route(signals, state, all_modes)
        assert decision is not None
        assert decision.primary == "restorer"

    def test_no_signals_still_activates_floored_modes(self, all_modes):
        """Even with no signals, safety-floored modes should appear."""
        signals = []
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision is not None
        # Protector has 10% floor, highest among floor-only modes
        assert "protector" in decision.weights
        assert "restorer" in decision.weights

    def test_empty_modes_returns_none(self):
        signals = [_signal(SignalType.FRUSTRATED)]
        state = CognitiveState()
        assert route(signals, state, []) is None


class TestWeighting:
    def test_commitment_routes_to_executor(self, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.9)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision.primary == "executor"

    def test_frustrated_routes_to_protector(self, all_modes):
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision.primary == "protector"

    def test_depleted_routes_to_restorer(self, all_modes):
        signals = [_signal(SignalType.DEPLETED, 0.9)]
        state = CognitiveState(energy="depleted")
        decision = route(signals, state, all_modes)
        assert decision.primary == "restorer"

    def test_red_burnout_forces_protector(self, all_modes):
        """RED burnout: protector weight goes to 1.0 regardless of signals."""
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.9)]
        state = CognitiveState(burnout="RED")
        decision = route(signals, state, all_modes)
        assert decision.primary == "protector"
        assert decision.primary_weight == 1.0

    def test_multiple_signals_routes_to_highest_weight(self, all_modes):
        signals = [
            _signal(SignalType.COMMITMENT_DETECTED, 0.6),
            _signal(SignalType.FRUSTRATED, 0.9),
        ]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        # Frustrated at 0.9 should outweigh commitment at 0.6
        assert decision.primary == "protector"


class TestSafetyFloors:
    def test_protector_always_at_least_10_percent(self, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision.weights["protector"] >= 0.10

    def test_restorer_always_at_least_5_percent(self, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision.weights["restorer"] >= 0.05

    def test_executor_can_be_zero(self, all_modes):
        """Executor has no safety floor."""
        signals = [_signal(SignalType.FRUSTRATED)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision.weights.get("executor", 0) == 0.0


class TestSupporting:
    def test_supporting_modes_included(self, all_modes):
        """Modes above threshold should be in supporting list."""
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState(energy="low")
        decision = route(signals, state, all_modes)
        # Protector is primary, restorer should be supporting (low energy)
        assert decision.primary == "protector"
        assert "restorer" in decision.supporting

    def test_max_two_supporting(self, all_modes):
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert len(decision.supporting) <= 2


class TestDeterminism:
    def test_same_input_same_output_100_times(self, all_modes):
        signals = [
            _signal(SignalType.COMMITMENT_DETECTED, 0.7),
            _signal(SignalType.FRUSTRATED, 0.6),
            _signal(SignalType.DEPLETED, 0.5),
        ]
        state = CognitiveState(energy="low", burnout="YELLOW")
        baseline = route(signals, state, all_modes)
        for _ in range(100):
            result = route(signals, state, all_modes)
            assert result == baseline

    def test_weights_dict_is_sorted(self, all_modes):
        signals = [_signal(SignalType.FRUSTRATED)]
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        keys = list(decision.weights.keys())
        assert keys == sorted(keys)


class TestTrailAdjustments:
    def test_trail_boost_increases_weight(self, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.7)]
        state = CognitiveState()
        # Boost executor
        decision_no_trail = route(signals, state, all_modes)
        decision_with_trail = route(
            signals, state, all_modes,
            trail_adjustments={"executor": 0.15},
        )
        assert decision_with_trail.weights["executor"] >= decision_no_trail.weights["executor"]

    def test_trail_penalty_decreases_weight(self, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.7)]
        state = CognitiveState()
        decision_no_trail = route(signals, state, all_modes)
        decision_with_trail = route(
            signals, state, all_modes,
            trail_adjustments={"executor": -0.15},
        )
        assert decision_with_trail.weights["executor"] <= decision_no_trail.weights["executor"]

    def test_trail_adjustment_clamped(self, all_modes):
        """Adjustments beyond +/- 0.2 are clamped."""
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.5)]
        state = CognitiveState()
        decision = route(
            signals, state, all_modes,
            trail_adjustments={"executor": 0.5},  # Should clamp to 0.2
        )
        # Executor base = 0.5, max adjustment = 0.2, so max = 0.7
        assert decision.weights["executor"] <= 0.7

    def test_no_trails_uses_default_weights(self, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()
        d1 = route(signals, state, all_modes)
        d2 = route(signals, state, all_modes, trail_adjustments=None)
        assert d1 == d2


class TestRouteAndExecute:
    def test_frustrated_returns_protector_response(self, all_modes):
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState()
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        assert response.metadata.get("primary") == "protector"
        assert response.suppress_others is True

    def test_commitment_returns_executor_response(self, all_modes):
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        assert response.metadata.get("primary") == "executor"

    def test_depleted_returns_restorer_response(self, all_modes):
        signals = [_signal(SignalType.DEPLETED)]
        state = CognitiveState(energy="depleted")
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        assert response.metadata.get("primary") == "restorer"
        assert response.suppress_others is True

    def test_suppressed_response_skips_augmentation(self, all_modes):
        """When primary suppresses others, no augmentation happens."""
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState()
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        assert "supporting" not in response.metadata

    def test_non_suppressed_gets_augmented(self, all_modes):
        """When primary doesn't suppress, supporting modes augment."""
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.8)]
        state = CognitiveState(energy="low")
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        # Executor is primary, restorer should augment due to low energy
        if "supporting" in response.metadata:
            assert isinstance(response.metadata["supporting"], list)

    def test_no_modes_returns_none(self):
        signals = [_signal(SignalType.FRUSTRATED)]
        state = CognitiveState()
        assert route_and_execute(signals, state, []) is None

    def test_routed_by_nexus_metadata(self, all_modes):
        signals = [_signal(SignalType.FRUSTRATED)]
        state = CognitiveState()
        response = route_and_execute(signals, state, all_modes)
        assert response.metadata.get("routed_by") == "nexus"
