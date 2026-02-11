"""Tests for Protector mode (Phase 3.3).

The Protector has a 10% constitutional safety floor and can suppress
all other modes. It validates first, problem-solves second.
"""

from __future__ import annotations

import pytest

from otto.modes.base import ModeResponse
from otto.modes.protector import ProtectorMode
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _signal(stype: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=stype, confidence=confidence, source="pattern")


class TestRespondsTo:
    def test_responds_to_frustrated(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.FRUSTRATED)]
        assert mode.responds_to(signals) is True

    def test_responds_to_crash_zone(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.CRASH_ZONE)]
        assert mode.responds_to(signals) is True

    def test_responds_to_spiral(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.SPIRAL)]
        assert mode.responds_to(signals) is True

    def test_responds_to_overwhelmed(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.OVERWHELMED)]
        assert mode.responds_to(signals) is True

    def test_does_not_respond_to_commitment(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        assert mode.responds_to(signals) is False

    def test_does_not_respond_to_focused(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.FOCUSED)]
        assert mode.responds_to(signals) is False


class TestWeight:
    def test_floor_always_10_percent(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.FOCUSED)]  # Non-activating
        state = CognitiveState()
        w = mode.weight(signals, state)
        assert w >= 0.10

    def test_red_burnout_full_weight(self):
        mode = ProtectorMode()
        signals = []
        state = CognitiveState(burnout="RED")
        assert mode.weight(signals, state) == 1.0

    def test_frustrated_signal_boosts_weight(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState()
        w = mode.weight(signals, state)
        assert w >= 0.9

    def test_orange_burnout_boosts_weight(self):
        mode = ProtectorMode()
        signals = []
        state = CognitiveState(burnout="ORANGE")
        w = mode.weight(signals, state)
        assert w >= 0.6


class TestExecute:
    def test_red_burnout_suppresses_others(self):
        mode = ProtectorMode()
        signals = []
        state = CognitiveState(burnout="RED")
        response = mode.execute(signals, state)
        assert response.suppress_others is True
        assert "stepping back" in response.text.lower()

    def test_crash_zone_suppresses_others(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.CRASH_ZONE)]
        state = CognitiveState()
        response = mode.execute(signals, state)
        assert response.suppress_others is True
        assert "permission" in response.text.lower()

    def test_overwhelmed_reduces_to_one_choice(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.OVERWHELMED)]
        state = CognitiveState()
        response = mode.execute(signals, state)
        assert response.suppress_others is True
        assert response.metadata.get("max_options") == 1
        assert "one thing" in response.text.lower()

    def test_frustrated_validates_first(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState()
        response = mode.execute(signals, state)
        assert response.suppress_others is True
        assert response.metadata.get("max_options") == 3

    def test_frustrated_offers_max_three_options(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.FRUSTRATED, 0.9)]
        state = CognitiveState()
        response = mode.execute(signals, state)
        # Count options by looking for commas/or in text
        assert response.metadata["max_options"] <= 3

    def test_spiral_offers_exit(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.SPIRAL)]
        state = CognitiveState()
        response = mode.execute(signals, state)
        assert response.suppress_others is True
        assert "pause" in response.text.lower() or "reset" in response.text.lower()

    def test_monitoring_when_no_strong_signal(self):
        mode = ProtectorMode()
        signals = [_signal(SignalType.FOCUSED)]  # Non-activating
        state = CognitiveState()
        response = mode.execute(signals, state)
        assert response.metadata.get("action") == "monitoring"
        assert response.text == ""


class TestAugment:
    def test_augment_adds_warning_in_orange(self):
        mode = ProtectorMode()
        original = ModeResponse(text="Here are your commitments.")
        signals = []
        state = CognitiveState(burnout="ORANGE")
        result = mode.augment(original, signals, state)
        assert result.metadata.get("protector_note") == "energy_warning"

    def test_augment_no_warning_in_green(self):
        mode = ProtectorMode()
        original = ModeResponse(text="Here are your commitments.")
        signals = []
        state = CognitiveState(burnout="GREEN")
        result = mode.augment(original, signals, state)
        assert "protector_note" not in result.metadata
