"""Tests for the Acknowledger mode (Tier 2)."""

from __future__ import annotations

from otto.modes.acknowledger import AcknowledgerMode
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _sig(st: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=st, confidence=confidence)


class TestAcknowledgerProtocol:
    def test_name(self):
        assert AcknowledgerMode().name == "acknowledger"

    def test_safety_floor(self):
        assert AcknowledgerMode().safety_floor == 0.0

    def test_responds_to_focused(self):
        assert AcknowledgerMode().responds_to([_sig(SignalType.FOCUSED)])

    def test_responds_to_exploring(self):
        assert AcknowledgerMode().responds_to([_sig(SignalType.EXPLORING)])

    def test_does_not_respond_to_frustrated(self):
        assert not AcknowledgerMode().responds_to([_sig(SignalType.FRUSTRATED)])


class TestAcknowledgerWeight:
    def test_base_weight_when_activated(self):
        mode = AcknowledgerMode()
        state = CognitiveState()
        w = mode.weight([_sig(SignalType.FOCUSED)], state)
        assert w >= 0.3

    def test_momentum_boosts_weight(self):
        mode = AcknowledgerMode()
        state = CognitiveState(momentum="rolling")
        w = mode.weight([_sig(SignalType.FOCUSED)], state)
        assert w >= 0.4

    def test_zero_when_not_activated(self):
        mode = AcknowledgerMode()
        state = CognitiveState()
        w = mode.weight([_sig(SignalType.FRUSTRATED)], state)
        assert w == 0.0


class TestAcknowledgerExecute:
    def test_standard_completion(self):
        mode = AcknowledgerMode(completed_count=1)
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.FOCUSED)], state)
        assert response.text != ""
        assert response.metadata["action"] == "acknowledge"

    def test_milestone_at_5(self):
        mode = AcknowledgerMode(completed_count=5)
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.FOCUSED)], state)
        assert "5" in response.text
        assert response.metadata["action"] == "milestone"

    def test_milestone_at_10(self):
        mode = AcknowledgerMode(completed_count=10)
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.FOCUSED)], state)
        assert "10" in response.text
        assert response.metadata["action"] == "milestone"

    def test_streak_in_rolling_momentum(self):
        mode = AcknowledgerMode(completed_count=3)
        state = CognitiveState(momentum="rolling")
        response = mode.execute([_sig(SignalType.FOCUSED)], state)
        assert response.metadata["action"] == "streak"

    def test_deterministic_template_selection(self):
        """Same completed_count -> same template (deterministic by design)."""
        results = set()
        for _ in range(10):
            mode = AcknowledgerMode(completed_count=7)
            state = CognitiveState()
            response = mode.execute([_sig(SignalType.FOCUSED)], state)
            results.add(response.text)
        assert len(results) == 1  # Same input -> same output


class TestAcknowledgerAugment:
    def test_augment_adds_note_in_momentum(self):
        mode = AcknowledgerMode()
        from otto.modes.base import ModeResponse
        response = ModeResponse(text="Original", metadata={})
        state = CognitiveState(momentum="rolling")
        result = mode.augment(response, [_sig(SignalType.FOCUSED)], state)
        assert result.metadata.get("acknowledger_note") == "momentum_positive"

    def test_augment_no_note_at_cold_start(self):
        mode = AcknowledgerMode()
        from otto.modes.base import ModeResponse
        response = ModeResponse(text="Original", metadata={})
        state = CognitiveState(momentum="cold_start")
        result = mode.augment(response, [_sig(SignalType.FOCUSED)], state)
        assert "acknowledger_note" not in result.metadata
