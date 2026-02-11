"""Tests for Executor mode (Phase 3.2).

The Executor wraps v4.0's nudge.py + store.py. No new behavior —
just a Mode protocol wrapper.
"""

from __future__ import annotations

import pytest

from otto.modes.executor import ExecutorMode
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _signal(stype: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=stype, confidence=confidence, source="pattern")


class TestRespondsTo:
    def test_responds_to_commitment(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        assert mode.responds_to(signals) is True

    def test_responds_to_action_required(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.ACTION_REQUIRED)]
        assert mode.responds_to(signals) is True

    def test_responds_to_deadline(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.DEADLINE_MENTIONED)]
        assert mode.responds_to(signals) is True

    def test_does_not_respond_to_frustrated(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.FRUSTRATED)]
        assert mode.responds_to(signals) is False

    def test_does_not_respond_to_depleted(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.DEPLETED)]
        assert mode.responds_to(signals) is False


class TestWeight:
    def test_base_weight_from_signal_confidence(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.9)]
        state = CognitiveState()
        assert mode.weight(signals, state) == pytest.approx(0.9)

    def test_depleted_reduces_weight(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.9)]
        state = CognitiveState(energy="depleted")
        w = mode.weight(signals, state)
        assert w < 0.5  # Significantly reduced

    def test_low_energy_reduces_weight(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.COMMITMENT_DETECTED, 0.9)]
        state = CognitiveState(energy="low")
        w = mode.weight(signals, state)
        assert w < 0.9  # Reduced but not as much as depleted

    def test_zero_weight_no_relevant_signals(self):
        mode = ExecutorMode()
        signals = [_signal(SignalType.FRUSTRATED)]
        state = CognitiveState()
        assert mode.weight(signals, state) == 0.0


class TestExecute:
    def test_no_store_returns_message(self):
        mode = ExecutorMode(store=None)
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()
        response = mode.execute(signals, state)
        assert "No commitment store" in response.text

    def test_empty_store_all_on_track(self, tmp_path):
        from otto.store import CommitmentStore
        store = CommitmentStore(db_path=str(tmp_path / "test.db"))
        mode = ExecutorMode(store=store)
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()
        response = mode.execute(signals, state)
        assert "on track" in response.text
        assert response.metadata["nudge_count"] == 0


class TestAugment:
    def test_augment_passes_through(self):
        from otto.modes.base import ModeResponse
        mode = ExecutorMode()
        original = ModeResponse(text="hello")
        signals = [_signal(SignalType.COMMITMENT_DETECTED)]
        state = CognitiveState()
        result = mode.augment(original, signals, state)
        assert result.text == "hello"
