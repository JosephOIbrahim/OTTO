"""Tests for Restorer mode (Phase 3.4).

The Restorer has a 5% constitutional safety floor. It grants
permission to rest and suppresses demanding nudges when depleted.
"Rest is productive" is constitutional.
"""

from __future__ import annotations

import pytest

from otto.modes.base import ModeResponse
from otto.modes.restorer import RestorerMode
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _signal(stype: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=stype, confidence=confidence, source="pattern")


class TestRespondsTo:
    def test_responds_to_depleted(self):
        mode = RestorerMode()
        signals = [_signal(SignalType.DEPLETED)]
        assert mode.responds_to(signals) is True

    def test_does_not_respond_to_focused(self):
        mode = RestorerMode()
        signals = [_signal(SignalType.FOCUSED)]
        assert mode.responds_to(signals) is False

    def test_does_not_respond_to_frustrated(self):
        mode = RestorerMode()
        signals = [_signal(SignalType.FRUSTRATED)]
        assert mode.responds_to(signals) is False


class TestWeight:
    def test_floor_always_5_percent(self):
        mode = RestorerMode()
        signals = [_signal(SignalType.FOCUSED)]
        state = CognitiveState()
        w = mode.weight(signals, state)
        assert w >= 0.05

    def test_depleted_energy_high_weight(self):
        mode = RestorerMode()
        signals = []
        state = CognitiveState(energy="depleted")
        w = mode.weight(signals, state)
        assert w >= 0.9

    def test_low_energy_moderate_weight(self):
        mode = RestorerMode()
        signals = []
        state = CognitiveState(energy="low")
        w = mode.weight(signals, state)
        assert w >= 0.5

    def test_orange_burnout_boosts_weight(self):
        mode = RestorerMode()
        signals = []
        state = CognitiveState(burnout="ORANGE")
        w = mode.weight(signals, state)
        assert w >= 0.6

    def test_green_healthy_low_weight(self):
        mode = RestorerMode()
        signals = []
        state = CognitiveState(energy="high", burnout="GREEN")
        w = mode.weight(signals, state)
        assert w == 0.05  # Just the safety floor


class TestExecute:
    def test_depleted_grants_rest_permission(self):
        mode = RestorerMode()
        signals = [_signal(SignalType.DEPLETED)]
        state = CognitiveState(energy="depleted")
        response = mode.execute(signals, state)
        assert response.suppress_others is True
        assert "permission" in response.text.lower()
        assert "rest" in response.text.lower()
        assert response.metadata.get("suppress_nudges_hours") == 12

    def test_orange_burnout_reduces_scope(self):
        mode = RestorerMode()
        signals = []
        state = CognitiveState(burnout="ORANGE", energy="medium")
        response = mode.execute(signals, state)
        assert "urgent" in response.text.lower()
        assert response.metadata.get("urgent_only") is True

    def test_low_energy_offers_choice(self):
        mode = RestorerMode()
        signals = []
        state = CognitiveState(energy="low")
        response = mode.execute(signals, state)
        assert "small" in response.text.lower() or "achievable" in response.text.lower()

    def test_depleted_signal_without_state_still_offers(self):
        """Even if state hasn't been updated, depleted signal triggers restorer."""
        mode = RestorerMode()
        signals = [_signal(SignalType.DEPLETED)]
        state = CognitiveState(energy="medium")  # State not yet updated
        response = mode.execute(signals, state)
        assert response.text != ""

    def test_monitoring_when_no_activation(self):
        mode = RestorerMode()
        signals = [_signal(SignalType.FOCUSED)]
        state = CognitiveState(energy="high")
        response = mode.execute(signals, state)
        assert response.metadata.get("action") == "monitoring"
        assert response.text == ""


class TestAugment:
    def test_augment_adds_note_in_low_energy(self):
        mode = RestorerMode()
        original = ModeResponse(text="Here's your next task.")
        signals = []
        state = CognitiveState(energy="low")
        result = mode.augment(original, signals, state)
        assert result.metadata.get("restorer_note") == "low_energy_context"

    def test_augment_no_note_in_high_energy(self):
        mode = RestorerMode()
        original = ModeResponse(text="Here's your next task.")
        signals = []
        state = CognitiveState(energy="high")
        result = mode.augment(original, signals, state)
        assert "restorer_note" not in result.metadata
