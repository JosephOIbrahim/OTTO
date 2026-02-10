"""Tests for the constitutional layer (Phase 0.3).

The constitutional layer can suppress any mode's output except the
Protector.  These tests verify suppression rules without wiring
the layer into the nudge pipeline (that's Phase 1.1).
"""

from __future__ import annotations

import pytest

from otto.constitutional import Suppression, should_suppress
from otto.state import CognitiveState


# ---------------------------------------------------------------------------
# RED burnout
# ---------------------------------------------------------------------------


class TestRedBurnout:
    """RED burnout suppresses everything except protector."""

    def test_red_suppresses_nudge(self):
        state = CognitiveState(burnout="RED")
        result = should_suppress(state, "nudge")
        assert result is not None
        assert isinstance(result, Suppression)
        assert "RED" in result.reason

    def test_red_suppresses_any_action(self):
        state = CognitiveState(burnout="RED")
        for action in ("nudge", "decompose", "redirect", "acknowledge"):
            result = should_suppress(state, action)
            assert result is not None, f"{action} should be suppressed in RED"

    def test_red_suppresses_regardless_of_energy(self):
        for energy in ("high", "medium", "low", "depleted"):
            state = CognitiveState(burnout="RED", energy=energy)
            result = should_suppress(state, "nudge")
            assert result is not None


# ---------------------------------------------------------------------------
# GREEN burnout
# ---------------------------------------------------------------------------


class TestGreenAllows:
    """GREEN burnout should not suppress nudges (healthy state)."""

    def test_green_allows_nudge(self):
        state = CognitiveState(burnout="GREEN", energy="high")
        result = should_suppress(state, "nudge")
        assert result is None

    def test_green_medium_allows_nudge(self):
        state = CognitiveState(burnout="GREEN", energy="medium")
        result = should_suppress(state, "nudge")
        assert result is None

    def test_green_low_allows_nudge(self):
        """GREEN + low energy is fine — low energy alone doesn't suppress."""
        state = CognitiveState(burnout="GREEN", energy="low")
        result = should_suppress(state, "nudge")
        assert result is None


# ---------------------------------------------------------------------------
# ORANGE + depleted
# ---------------------------------------------------------------------------


class TestOrangeDepleted:
    """ORANGE burnout + low/depleted energy suppresses."""

    def test_orange_depleted_suppresses(self):
        state = CognitiveState(burnout="ORANGE", energy="depleted")
        result = should_suppress(state, "nudge")
        assert result is not None
        assert "ORANGE" in result.reason

    def test_orange_low_suppresses(self):
        state = CognitiveState(burnout="ORANGE", energy="low")
        result = should_suppress(state, "nudge")
        assert result is not None

    def test_orange_medium_allows(self):
        state = CognitiveState(burnout="ORANGE", energy="medium")
        result = should_suppress(state, "nudge")
        assert result is None

    def test_orange_high_allows(self):
        state = CognitiveState(burnout="ORANGE", energy="high")
        result = should_suppress(state, "nudge")
        assert result is None


# ---------------------------------------------------------------------------
# Low effectiveness
# ---------------------------------------------------------------------------


class TestLowEffectiveness:
    """Low nudge effectiveness (< 10%) suppresses after threshold."""

    def test_low_effectiveness_suppresses_after_threshold(self):
        state = CognitiveState(
            nudges_sent_today=5,
            nudges_completed_today=0,  # 0% effectiveness
        )
        result = should_suppress(state, "nudge")
        assert result is not None
        assert "effectiveness" in result.reason

    def test_low_effectiveness_below_threshold_allows(self):
        """Need > 3 nudges sent before effectiveness check kicks in."""
        state = CognitiveState(
            nudges_sent_today=2,
            nudges_completed_today=0,
        )
        result = should_suppress(state, "nudge")
        assert result is None

    def test_high_effectiveness_allows(self):
        state = CognitiveState(
            nudges_sent_today=5,
            nudges_completed_today=4,  # 80% effectiveness
        )
        result = should_suppress(state, "nudge")
        assert result is None

    def test_effectiveness_only_applies_to_nudge(self):
        """Low effectiveness should only suppress nudge actions."""
        state = CognitiveState(
            nudges_sent_today=5,
            nudges_completed_today=0,
        )
        result = should_suppress(state, "decompose")
        assert result is None  # decompose is not affected by nudge effectiveness


# ---------------------------------------------------------------------------
# Protector is never suppressed
# ---------------------------------------------------------------------------


class TestProtectorNeverSuppressed:
    """The Protector mode is constitutionally unsuppressable."""

    def test_protector_not_suppressed_in_red(self):
        state = CognitiveState(burnout="RED")
        result = should_suppress(state, "nudge", mode="protector")
        assert result is None

    def test_protector_not_suppressed_in_orange_depleted(self):
        state = CognitiveState(burnout="ORANGE", energy="depleted")
        result = should_suppress(state, "nudge", mode="protector")
        assert result is None

    def test_protector_not_suppressed_with_low_effectiveness(self):
        state = CognitiveState(
            nudges_sent_today=10,
            nudges_completed_today=0,
        )
        result = should_suppress(state, "nudge", mode="protector")
        assert result is None


# ---------------------------------------------------------------------------
# YELLOW burnout (boundary)
# ---------------------------------------------------------------------------


class TestYellowBurnout:
    """YELLOW burnout should not suppress (it's a warning, not a gate)."""

    def test_yellow_allows_nudge(self):
        state = CognitiveState(burnout="YELLOW", energy="medium")
        result = should_suppress(state, "nudge")
        assert result is None

    def test_yellow_low_allows(self):
        state = CognitiveState(burnout="YELLOW", energy="low")
        result = should_suppress(state, "nudge")
        assert result is None
