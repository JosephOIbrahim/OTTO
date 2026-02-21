"""Tests for 4-mode consolidated architecture."""

from __future__ import annotations

import pytest

from otto.modes.decomposer import DecomposerMode
from otto.modes.executor import ExecutorMode
from otto.modes.protector import ProtectorMode
from otto.modes.restorer import RestorerMode
from otto.router import _SIGNAL_TO_MODE
from otto.signals import Signal, SignalType
from otto.state import CognitiveState


def _signal(stype: SignalType, confidence: float = 0.8) -> Signal:
    return Signal(type=stype, confidence=confidence, source="pattern")


class TestAllSignalsCovered:
    def test_all_signal_types_have_handler(self):
        """Every SignalType in _SIGNAL_TO_MODE maps to a mode that exists."""
        mode_names = {"executor", "protector", "restorer", "decomposer"}
        for st, mode_name in _SIGNAL_TO_MODE.items():
            assert mode_name in mode_names, f"{st} maps to unknown mode {mode_name}"

    def test_four_modes_cover_all_signals(self):
        """Every mapped signal type is handled by exactly one of the 4 modes."""
        expected_signals = {
            SignalType.COMMITMENT_DETECTED, SignalType.ACTION_REQUIRED,
            SignalType.DEADLINE_MENTIONED, SignalType.FRUSTRATED,
            SignalType.OVERWHELMED, SignalType.CRASH_ZONE, SignalType.SPIRAL,
            SignalType.DEPLETED, SignalType.EXPLORING, SignalType.STUCK,
            SignalType.BURST_DETECTED, SignalType.FOCUSED,
        }
        assert set(_SIGNAL_TO_MODE.keys()) == expected_signals


class TestRestorerHandlesExploring:
    def test_responds_to_exploring(self):
        mode = RestorerMode()
        signals = [_signal(SignalType.EXPLORING)]
        assert mode.responds_to(signals)

    def test_exploring_returns_socratic_prompt(self):
        mode = RestorerMode()
        signals = [_signal(SignalType.EXPLORING)]
        state = CognitiveState(energy="high")
        response = mode.execute(signals, state)
        assert response.text  # Should produce output
        assert response.metadata.get("action") == "socratic_prompt"

    def test_depleted_still_works(self):
        """Restorer still handles depleted after Guide merge."""
        mode = RestorerMode()
        signals = [_signal(SignalType.DEPLETED)]
        state = CognitiveState(energy="depleted")
        response = mode.execute(signals, state)
        assert response.suppress_others is True
        assert "rest" in response.text.lower() or "permission" in response.text.lower()


class TestDecomposerHandlesFocused:
    def test_responds_to_focused(self):
        mode = DecomposerMode()
        signals = [_signal(SignalType.FOCUSED)]
        assert mode.responds_to(signals)

    def test_focused_returns_acknowledgment(self):
        mode = DecomposerMode()
        signals = [_signal(SignalType.FOCUSED)]
        state = CognitiveState(momentum="building")
        response = mode.execute(signals, state)
        assert response.text
        assert response.metadata.get("action") == "acknowledge"


class TestDecomposerHandlesBurst:
    def test_responds_to_burst(self):
        mode = DecomposerMode()
        signals = [_signal(SignalType.BURST_DETECTED)]
        assert mode.responds_to(signals)

    def test_burst_returns_redirect(self):
        mode = DecomposerMode()
        signals = [_signal(SignalType.BURST_DETECTED)]
        state = CognitiveState(momentum="peak")
        response = mode.execute(signals, state)
        assert response.text
        assert response.metadata.get("action") in ("redirect", "compass_check")

    def test_stuck_still_works(self):
        """Decomposer still handles stuck after merges."""
        mode = DecomposerMode()
        signals = [_signal(SignalType.STUCK)]
        state = CognitiveState()
        response = mode.execute(signals, state)
        assert "stuck" in response.text.lower() or "step" in response.text.lower()
