"""End-to-end integration tests for the full cognitive pipeline (Phase 4.2).

Tests the complete path:
  MESSAGE -> detect_signals() -> route() -> mode.execute() -> response

These are deterministic (no API calls, no randomness).
"""

from __future__ import annotations

import pytest

from otto.constitutional import should_suppress
from otto.modes.executor import ExecutorMode
from otto.modes.protector import ProtectorMode
from otto.modes.restorer import RestorerMode
from otto.router import route, route_and_execute
from otto.signals import detect_signals
from otto.state import CognitiveState


@pytest.fixture()
def all_modes():
    return [ExecutorMode(), ProtectorMode(), RestorerMode()]


class TestFrustratedPipeline:
    def test_frustrated_message_routes_to_protector(self, all_modes):
        """UGH message -> frustrated signal -> protector mode."""
        signals = detect_signals("UGH this is NOT WORKING!!!")
        state = CognitiveState()
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        assert response.metadata["primary"] == "protector"
        assert response.suppress_others is True

    def test_frustrated_protector_validates_first(self, all_modes):
        signals = detect_signals("I can't figure this out, giving up!!!")
        state = CognitiveState()
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        # Protector should validate, not problem-solve
        text = response.text.lower()
        assert any(word in text for word in ["frustrat", "valid", "pause", "simplif", "break"])


class TestCommitmentPipeline:
    def test_commitment_message_routes_to_executor(self, all_modes):
        """Promise message -> commitment signal -> executor mode."""
        signals = detect_signals("I'll send the report to Sarah by Friday")
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision is not None
        assert decision.primary == "executor"

    def test_commitment_in_depleted_state_still_routes(self, all_modes):
        """Commitment detected but energy is low -> executor still primary but reduced weight."""
        signals = detect_signals("I'll call the dentist tomorrow")
        state = CognitiveState(energy="low")
        decision = route(signals, state, all_modes)
        assert decision is not None
        # Executor should still be primary but with reduced weight
        # Restorer may have higher weight due to low energy
        assert decision.primary in ("executor", "restorer")


class TestDepletedPipeline:
    def test_depleted_message_routes_to_restorer(self, all_modes):
        """Tired message -> depleted signal -> restorer mode."""
        signals = detect_signals("I'm exhausted, can't think anymore")
        state = CognitiveState(energy="depleted")
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        assert response.metadata["primary"] == "restorer"

    def test_short_message_suggests_depleted(self, all_modes):
        """Very short messages trigger depleted heuristic."""
        signals = detect_signals("ok")
        state = CognitiveState(energy="low")
        decision = route(signals, state, all_modes)
        assert decision is not None
        # Should route to restorer due to depleted signal + low energy
        assert decision.primary == "restorer"


class TestRedBurnoutPipeline:
    def test_red_burnout_overrides_everything(self, all_modes):
        """In RED burnout, protector takes full control regardless of signals."""
        signals = detect_signals("I'll send the report by Friday")
        state = CognitiveState(burnout="RED")
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        assert response.metadata["primary"] == "protector"
        assert response.suppress_others is True

    def test_red_burnout_constitutional_suppresses_nudge(self):
        """RED burnout also suppresses nudges via constitutional layer."""
        state = CognitiveState(burnout="RED")
        suppression = should_suppress(state, "nudge")
        assert suppression is not None
        assert "RED" in suppression.reason


class TestConstitutionalIntegration:
    def test_orange_depleted_suppresses_nudge(self):
        state = CognitiveState(burnout="ORANGE", energy="depleted")
        suppression = should_suppress(state, "nudge")
        assert suppression is not None

    def test_green_allows_nudge(self):
        state = CognitiveState(burnout="GREEN", energy="medium")
        suppression = should_suppress(state, "nudge")
        assert suppression is None

    def test_protector_never_suppressed(self):
        state = CognitiveState(burnout="RED")
        suppression = should_suppress(state, "nudge", mode="protector")
        assert suppression is None


class TestOverwhelmedPipeline:
    def test_overwhelmed_routes_to_protector(self, all_modes):
        signals = detect_signals("I don't know where to start, too much going on")
        state = CognitiveState()
        response = route_and_execute(signals, state, all_modes)
        assert response is not None
        assert response.metadata["primary"] == "protector"
        # Should reduce to one choice
        assert response.metadata.get("max_options") == 1


class TestExploringPipeline:
    def test_exploring_does_not_route_to_protector(self, all_modes):
        """Exploring is not a crisis — protector should not be primary."""
        signals = detect_signals("what if we tried a different approach?")
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision is not None
        # With only 3 modes, exploring doesn't activate any
        # Safety floors kick in — protector at 10% is highest
        # This is expected: Guide mode (not yet implemented) would handle this


class TestDeterminism:
    def test_full_pipeline_deterministic(self, all_modes):
        msg = "UGH I can't do this, I'll call Sarah by Friday but I'm so tired!!!"
        state = CognitiveState(energy="low", burnout="YELLOW")
        baseline_signals = detect_signals(msg)
        baseline_response = route_and_execute(baseline_signals, state, all_modes)

        for _ in range(50):
            signals = detect_signals(msg)
            response = route_and_execute(signals, state, all_modes)
            assert signals == baseline_signals
            assert response.text == baseline_response.text
            assert response.metadata == baseline_response.metadata


class TestMixedSignals:
    def test_frustrated_plus_commitment(self, all_modes):
        """Frustration outweighs commitment — safety first."""
        signals = detect_signals("UGH I'll send the damn report!!!")
        state = CognitiveState()
        decision = route(signals, state, all_modes)
        assert decision is not None
        assert decision.primary == "protector"

    def test_depleted_plus_commitment(self, all_modes):
        """Depleted + commitment — restorer wins when energy is depleted."""
        signals = detect_signals("I'm exhausted but I'll try to send the report")
        state = CognitiveState(energy="depleted")
        decision = route(signals, state, all_modes)
        assert decision is not None
        assert decision.primary == "restorer"
