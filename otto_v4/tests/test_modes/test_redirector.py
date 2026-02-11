"""Tests for the Redirector mode (Tier 4)."""

from __future__ import annotations

from otto.modes.redirector import RedirectorMode
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _sig(st: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=st, confidence=confidence)


class TestRedirectorProtocol:
    def test_name(self):
        assert RedirectorMode().name == "redirector"

    def test_safety_floor(self):
        assert RedirectorMode().safety_floor == 0.0

    def test_responds_to_exploring(self):
        assert RedirectorMode().responds_to([_sig(SignalType.EXPLORING)])

    def test_does_not_respond_to_frustrated(self):
        assert not RedirectorMode().responds_to([_sig(SignalType.FRUSTRATED)])


class TestRedirectorWeight:
    def test_base_weight(self):
        mode = RedirectorMode()
        state = CognitiveState()
        w = mode.weight([_sig(SignalType.EXPLORING)], state)
        assert w >= 0.2

    def test_commitments_boost_weight(self):
        mode = RedirectorMode()
        state = CognitiveState()
        signals = [_sig(SignalType.EXPLORING), _sig(SignalType.COMMITMENT_DETECTED)]
        w = mode.weight(signals, state)
        assert w >= 0.4

    def test_rolling_momentum_boosts(self):
        mode = RedirectorMode()
        state = CognitiveState(momentum="rolling")
        w = mode.weight([_sig(SignalType.EXPLORING)], state)
        assert w >= 0.3

    def test_zero_when_not_activated(self):
        mode = RedirectorMode()
        state = CognitiveState()
        w = mode.weight([_sig(SignalType.FRUSTRATED)], state)
        assert w == 0.0


class TestRedirectorExecute:
    def test_exploring_with_commitments(self):
        mode = RedirectorMode()
        state = CognitiveState()
        signals = [_sig(SignalType.EXPLORING), _sig(SignalType.COMMITMENT_DETECTED)]
        response = mode.execute(signals, state)
        assert "commitments" in response.text.lower() or "pending" in response.text.lower()
        assert response.metadata["has_pending"] is True

    def test_exploring_in_rolling_momentum(self):
        mode = RedirectorMode()
        state = CognitiveState(momentum="rolling")
        response = mode.execute([_sig(SignalType.EXPLORING)], state)
        assert "compass" in response.text.lower() or "goal" in response.text.lower()

    def test_general_exploration(self):
        mode = RedirectorMode()
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.EXPLORING)], state)
        assert "capture" in response.text.lower() or "commitment" in response.text.lower()


class TestRedirectorAugment:
    def test_augment_adds_note_when_exploring(self):
        mode = RedirectorMode()
        from otto.modes.base import ModeResponse
        response = ModeResponse(text="Original", metadata={})
        state = CognitiveState()
        result = mode.augment(response, [_sig(SignalType.EXPLORING)], state)
        assert result.metadata.get("redirector_note") == "exploring_detected"
