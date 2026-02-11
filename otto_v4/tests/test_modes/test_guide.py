"""Tests for the Guide mode (Tier 4)."""

from __future__ import annotations

from otto.modes.guide import GuideMode
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _sig(st: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=st, confidence=confidence)


class TestGuideProtocol:
    def test_name(self):
        assert GuideMode().name == "guide"

    def test_safety_floor(self):
        assert GuideMode().safety_floor == 0.0

    def test_responds_to_exploring(self):
        assert GuideMode().responds_to([_sig(SignalType.EXPLORING)])

    def test_responds_to_focused(self):
        assert GuideMode().responds_to([_sig(SignalType.FOCUSED)])

    def test_does_not_respond_to_frustrated(self):
        assert not GuideMode().responds_to([_sig(SignalType.FRUSTRATED)])


class TestGuideWeight:
    def test_base_weight_exploring(self):
        mode = GuideMode()
        state = CognitiveState()
        w = mode.weight([_sig(SignalType.EXPLORING)], state)
        assert w >= 0.2

    def test_high_energy_boosts(self):
        mode = GuideMode()
        state = CognitiveState(energy="high")
        w = mode.weight([_sig(SignalType.EXPLORING)], state)
        assert w >= 0.5

    def test_zero_when_not_activated(self):
        mode = GuideMode()
        state = CognitiveState()
        w = mode.weight([_sig(SignalType.FRUSTRATED)], state)
        assert w == 0.0


class TestGuideExecute:
    def test_exploring_gives_socratic_prompt(self):
        mode = GuideMode()
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.EXPLORING)], state)
        assert response.text != ""
        assert response.metadata["action"] == "socratic_prompt"

    def test_focused_encourages_continuation(self):
        mode = GuideMode()
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.FOCUSED)], state)
        assert "groove" in response.text.lower() or "keep" in response.text.lower()
        assert response.metadata["action"] == "encourage_focus"

    def test_exploring_overrides_focused(self):
        mode = GuideMode()
        state = CognitiveState()
        signals = [_sig(SignalType.FOCUSED), _sig(SignalType.EXPLORING)]
        response = mode.execute(signals, state)
        assert response.metadata["action"] == "socratic_prompt"

    def test_deterministic_template(self):
        """Same confidence -> same prompt (He2025 compliance)."""
        results = set()
        for _ in range(10):
            mode = GuideMode()
            state = CognitiveState()
            response = mode.execute([_sig(SignalType.EXPLORING, 0.8)], state)
            results.add(response.text)
        assert len(results) == 1


class TestGuideAugment:
    def test_augment_adds_note_when_exploring(self):
        mode = GuideMode()
        from otto.modes.base import ModeResponse
        response = ModeResponse(text="Original", metadata={})
        state = CognitiveState()
        result = mode.augment(response, [_sig(SignalType.EXPLORING)], state)
        assert result.metadata.get("guide_note") == "curiosity_supported"
