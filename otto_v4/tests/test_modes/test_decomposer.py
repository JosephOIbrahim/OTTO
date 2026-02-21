"""Tests for the Decomposer mode (Tier 2)."""

from __future__ import annotations

from otto.modes.decomposer import DecomposerMode
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _sig(st: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=st, confidence=confidence)


class TestDecomposerProtocol:
    def test_name(self):
        assert DecomposerMode().name == "decomposer"

    def test_safety_floor(self):
        assert DecomposerMode().safety_floor == 0.05

    def test_responds_to_overwhelmed(self):
        mode = DecomposerMode()
        assert mode.responds_to([_sig(SignalType.OVERWHELMED)])

    def test_responds_to_stuck(self):
        mode = DecomposerMode()
        assert mode.responds_to([_sig(SignalType.STUCK)])

    def test_responds_to_focused(self):
        """Decomposer now handles FOCUSED (absorbed from Acknowledger)."""
        mode = DecomposerMode()
        assert mode.responds_to([_sig(SignalType.FOCUSED)])

    def test_does_not_respond_to_commitment(self):
        mode = DecomposerMode()
        assert not mode.responds_to([_sig(SignalType.COMMITMENT_DETECTED)])


class TestDecomposerWeight:
    def test_base_weight_from_signal(self):
        mode = DecomposerMode()
        state = CognitiveState()
        w = mode.weight([_sig(SignalType.OVERWHELMED, 0.9)], state)
        assert w >= 0.9

    def test_depleted_boosts_weight(self):
        mode = DecomposerMode()
        state = CognitiveState(energy="depleted")
        w = mode.weight([_sig(SignalType.STUCK, 0.3)], state)
        assert w >= 0.5

    def test_orange_burnout_boosts(self):
        mode = DecomposerMode()
        state = CognitiveState(burnout="ORANGE")
        w = mode.weight([_sig(SignalType.STUCK, 0.3)], state)
        assert w >= 0.6

    def test_focused_returns_moderate_weight(self):
        """FOCUSED signal now activates Decomposer (absorbed from Acknowledger)."""
        mode = DecomposerMode()
        state = CognitiveState()
        w = mode.weight([_sig(SignalType.FOCUSED)], state)
        assert w >= 0.3


class TestDecomposerExecute:
    def test_overwhelmed_response(self):
        mode = DecomposerMode()
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.OVERWHELMED)], state)
        assert "one piece" in response.text.lower() or "one thing" in response.text.lower()
        assert response.metadata["action"] == "decompose"
        assert response.metadata["trigger"] == "overwhelmed"

    def test_stuck_response(self):
        mode = DecomposerMode()
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.STUCK)], state)
        assert "stuck" in response.text.lower() or "unblock" in response.text.lower()
        assert response.metadata["action"] == "decompose"

    def test_stuck_with_commitment_gives_structured_breakdown(self):
        mode = DecomposerMode()
        state = CognitiveState()
        signals = [
            _sig(SignalType.STUCK),
            _sig(SignalType.COMMITMENT_DETECTED),
        ]
        response = mode.execute(signals, state)
        assert "1." in response.text  # numbered steps
        assert response.metadata["trigger"] == "stuck_commitment"

    def test_focused_returns_acknowledgment(self):
        """FOCUSED now triggers acknowledgment (absorbed from Acknowledger)."""
        mode = DecomposerMode()
        state = CognitiveState()
        response = mode.execute([_sig(SignalType.FOCUSED)], state)
        assert response.text != ""
        assert response.metadata["action"] == "acknowledge"


class TestDecomposerAugment:
    def test_augment_adds_note_when_overwhelmed(self):
        mode = DecomposerMode()
        from otto.modes.base import ModeResponse
        response = ModeResponse(text="Original", metadata={})
        state = CognitiveState()
        result = mode.augment(response, [_sig(SignalType.OVERWHELMED)], state)
        assert result.metadata.get("decomposer_note") == "consider_breakdown"

    def test_augment_no_note_when_irrelevant(self):
        mode = DecomposerMode()
        from otto.modes.base import ModeResponse
        response = ModeResponse(text="Original", metadata={})
        state = CognitiveState()
        result = mode.augment(response, [_sig(SignalType.FOCUSED)], state)
        assert "decomposer_note" not in result.metadata
