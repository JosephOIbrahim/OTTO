"""Tests for otto_hooks.py -- constitutional gating."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_otto_src = str(Path(__file__).resolve().parent.parent.parent / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

_agent_src = str(Path(__file__).resolve().parent.parent.parent)
if _agent_src not in sys.path:
    sys.path.insert(0, _agent_src)

from otto.state import CognitiveState
from otto_agent.otto_hooks import (
    constitutional_gate,
    format_suppression_result,
)


# ---------------------------------------------------------------------------
# RED burnout blocks nudges
# ---------------------------------------------------------------------------


class TestRedBurnout:
    def test_red_blocks_nudge(self):
        state = CognitiveState(burnout="RED")
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is not None
        assert result["suppressed"] is True
        assert "RED" in result["reason"]

    def test_red_blocks_regardless_of_energy(self):
        for energy in ("high", "medium", "low", "depleted"):
            state = CognitiveState(burnout="RED", energy=energy)
            result = constitutional_gate("otto_run_nudge", {}, state)
            assert result is not None


# ---------------------------------------------------------------------------
# ORANGE + low/depleted blocks nudges
# ---------------------------------------------------------------------------


class TestOrangeDepleted:
    def test_orange_depleted_blocks(self):
        state = CognitiveState(burnout="ORANGE", energy="depleted")
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is not None

    def test_orange_low_blocks(self):
        state = CognitiveState(burnout="ORANGE", energy="low")
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is not None

    def test_orange_medium_allows(self):
        state = CognitiveState(burnout="ORANGE", energy="medium")
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is None

    def test_orange_high_allows(self):
        state = CognitiveState(burnout="ORANGE", energy="high")
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is None


# ---------------------------------------------------------------------------
# GREEN allows nudges
# ---------------------------------------------------------------------------


class TestGreenAllows:
    def test_green_allows_nudge(self):
        state = CognitiveState(burnout="GREEN", energy="high")
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is None

    def test_green_medium_allows(self):
        state = CognitiveState(burnout="GREEN", energy="medium")
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is None


# ---------------------------------------------------------------------------
# Low effectiveness blocks nudges
# ---------------------------------------------------------------------------


class TestLowEffectiveness:
    def test_low_effectiveness_blocks(self):
        state = CognitiveState(
            nudges_sent_today=5,
            nudges_completed_today=0,
        )
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is not None
        assert "effectiveness" in result["reason"]

    def test_few_nudges_allows(self):
        """Effectiveness check only kicks in after >3 nudges sent."""
        state = CognitiveState(
            nudges_sent_today=2,
            nudges_completed_today=0,
        )
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is None

    def test_high_effectiveness_allows(self):
        state = CognitiveState(
            nudges_sent_today=5,
            nudges_completed_today=4,
        )
        result = constitutional_gate("otto_run_nudge", {}, state)
        assert result is None


# ---------------------------------------------------------------------------
# Non-gated tools pass through
# ---------------------------------------------------------------------------


class TestNonGatedTools:
    def test_list_always_allowed(self):
        state = CognitiveState(burnout="RED")
        result = constitutional_gate("otto_list_commitments", {}, state)
        assert result is None

    def test_add_always_allowed(self):
        state = CognitiveState(burnout="RED")
        result = constitutional_gate("otto_add_commitment", {}, state)
        assert result is None

    def test_done_always_allowed(self):
        state = CognitiveState(burnout="RED")
        result = constitutional_gate("otto_mark_done", {}, state)
        assert result is None

    def test_energy_always_allowed(self):
        state = CognitiveState(burnout="RED")
        result = constitutional_gate("otto_get_energy", {}, state)
        assert result is None

    def test_stats_always_allowed(self):
        state = CognitiveState(burnout="RED")
        result = constitutional_gate("otto_get_stats", {}, state)
        assert result is None


# ---------------------------------------------------------------------------
# Suppression formatting
# ---------------------------------------------------------------------------


class TestFormatSuppression:
    def test_red_message(self):
        suppression = {
            "suppressed": True,
            "tool": "otto_run_nudge",
            "reason": "burnout is RED -- OTTO is giving you space",
            "action": "nudge",
        }
        result = json.loads(format_suppression_result(suppression))
        assert result["suppressed"] is True
        assert "space" in result["message"]

    def test_orange_message(self):
        suppression = {
            "suppressed": True,
            "tool": "otto_run_nudge",
            "reason": "burnout ORANGE + energy depleted -- backing off",
            "action": "nudge",
        }
        result = json.loads(format_suppression_result(suppression))
        assert "backing off" in result["message"]

    def test_effectiveness_message(self):
        suppression = {
            "suppressed": True,
            "tool": "otto_run_nudge",
            "reason": "nudge effectiveness 0% after 5 sent -- backing off",
            "action": "nudge",
        }
        result = json.loads(format_suppression_result(suppression))
        assert "pausing" in result["message"]
