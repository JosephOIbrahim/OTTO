"""Redirector mode -- gentle refocus from tangents.

No safety floor (optional mode). When the user drifts from their
current focus, the Redirector offers a gentle redirect without
judgment. Template-based (no LLM, no cost).

Primarily useful in conversational contexts (agent/chat) rather than
CLI commands. In CLI mode, detects tangent signals from PRISM.
"""

from __future__ import annotations

from otto.signals import Signal, SignalType
from otto.state import CognitiveState

from .base import ModeResponse

# The Redirector doesn't have a dedicated signal type yet,
# but it can activate when EXPLORING + COMMITMENT_DETECTED overlap
# (exploring tangent while commitments are pending).
_ACTIVATION_SIGNALS = frozenset({
    SignalType.EXPLORING,
})

# Redirect templates — gentle, non-judgmental
_GENTLE_REDIRECT = (
    "Interesting thread. Just a heads up: you have active commitments. "
    "Want to explore this, or circle back to what's pending?"
)

_FOCUS_REMINDER = (
    "Quick compass check: is this moving toward your current goal, "
    "or is it a tangent worth parking for later?"
)

_TANGENT_ACKNOWLEDGE = (
    "Good thought. Want to capture that as a new commitment and "
    "come back to what you were doing?"
)


class RedirectorMode:
    """Tangent management mode. No safety floor (optional).

    Offers gentle redirects when the user drifts from focus.
    Never forces — always offers a choice.
    """

    @property
    def name(self) -> str:
        return "redirector"

    @property
    def safety_floor(self) -> float:
        return 0.0  # Optional mode

    def responds_to(self, signals: list[Signal]) -> bool:
        return any(s.type in _ACTIVATION_SIGNALS for s in signals)

    def weight(self, signals: list[Signal], state: CognitiveState) -> float:
        if not self.responds_to(signals):
            return 0.0

        base = 0.2  # Low base: don't interrupt exploration lightly

        # If there are also commitment signals, redirect is more relevant
        has_commitments = any(
            s.type in (SignalType.COMMITMENT_DETECTED, SignalType.ACTION_REQUIRED)
            for s in signals
        )
        if has_commitments:
            base = max(base, 0.4)

        # If momentum is peak/rolling, redirecting is valuable
        if state.momentum in ("rolling", "peak"):
            base = max(base, 0.3)

        return min(1.0, base)

    def execute(
        self, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        has_commitments = any(
            s.type in (SignalType.COMMITMENT_DETECTED, SignalType.ACTION_REQUIRED)
            for s in signals
        )

        # Exploring while commitments are pending -> gentle redirect
        if has_commitments:
            return ModeResponse(
                text=_GENTLE_REDIRECT,
                metadata={"action": "redirect", "has_pending": True},
            )

        # Rolling momentum + exploring -> compass check
        if state.momentum in ("rolling", "peak"):
            return ModeResponse(
                text=_FOCUS_REMINDER,
                metadata={"action": "compass_check"},
            )

        # General exploration -> offer to capture
        return ModeResponse(
            text=_TANGENT_ACKNOWLEDGE,
            metadata={"action": "capture_tangent"},
        )

    def augment(
        self, response: ModeResponse, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        """As supporting mode, can add a gentle focus hint."""
        if any(s.type == SignalType.EXPLORING for s in signals):
            response.metadata["redirector_note"] = "exploring_detected"
        return response
