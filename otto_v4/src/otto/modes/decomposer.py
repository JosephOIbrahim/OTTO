"""Decomposer mode -- break overwhelming tasks into steps.

The Decomposer has a constitutional 5% safety floor. When the user is
overwhelmed or stuck, it breaks the current task into smaller, achievable
steps. Template-based (no LLM, no cost).

"One at a time" is a constitutional principle.
"""

from __future__ import annotations

from otto.signals import Signal, SignalType
from otto.state import CognitiveState

from .base import ModeResponse

_ACTIVATION_SIGNALS = frozenset({
    SignalType.OVERWHELMED,
    SignalType.STUCK,
})

# Templates — concrete, action-oriented, achievable
_OVERWHELMED_RESPONSE = (
    "That's a lot. Let's pick just one piece.\n"
    "What's the smallest first step you can see?"
)

_STUCK_RESPONSE = (
    "Stuck happens. Try this: what's the ONE thing that would unblock you?\n"
    "Not the whole task -- just the next move."
)

_STUCK_WITH_COMMITMENT_RESPONSE = (
    "This commitment feels stuck. Here's a breakdown approach:\n"
    "1. What's blocking it right now?\n"
    "2. What's the smallest action that moves it forward?\n"
    "3. Can you do that action in the next 15 minutes?"
)


class DecomposerMode:
    """Task breakdown mode. 5% constitutional floor.

    When overwhelmed or stuck, breaks things into achievable steps.
    "One at a time" is the principle.
    """

    @property
    def name(self) -> str:
        return "decomposer"

    @property
    def safety_floor(self) -> float:
        return 0.05  # Constitutional: always at least 5%

    def responds_to(self, signals: list[Signal]) -> bool:
        return any(s.type in _ACTIVATION_SIGNALS for s in signals)

    def weight(self, signals: list[Signal], state: CognitiveState) -> float:
        base = self.safety_floor

        # Overwhelmed signals escalate weight
        relevant = [s for s in signals if s.type in _ACTIVATION_SIGNALS]
        if relevant:
            signal_weight = max(s.confidence for s in relevant)
            base = max(base, signal_weight)

        # If also depleted, boost decomposer (small steps help)
        if state.energy in ("low", "depleted"):
            base = max(base, 0.5)

        # ORANGE burnout + overwhelmed = strong decomposition
        if state.burnout == "ORANGE":
            base = max(base, 0.6)

        return min(1.0, base)

    def execute(
        self, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        signal_types = {s.type for s in signals}
        has_commitment = any(
            s.type in (SignalType.COMMITMENT_DETECTED, SignalType.ACTION_REQUIRED)
            for s in signals
        )

        # Overwhelmed: reduce to one choice
        if SignalType.OVERWHELMED in signal_types:
            return ModeResponse(
                text=_OVERWHELMED_RESPONSE,
                metadata={"action": "decompose", "trigger": "overwhelmed"},
            )

        # Stuck with a commitment: structured breakdown
        if SignalType.STUCK in signal_types and has_commitment:
            return ModeResponse(
                text=_STUCK_WITH_COMMITMENT_RESPONSE,
                metadata={"action": "decompose", "trigger": "stuck_commitment"},
            )

        # Stuck general
        if SignalType.STUCK in signal_types:
            return ModeResponse(
                text=_STUCK_RESPONSE,
                metadata={"action": "decompose", "trigger": "stuck"},
            )

        # Safety floor activated but no strong signal
        return ModeResponse(
            text="",
            metadata={"action": "monitoring"},
        )

    def augment(
        self, response: ModeResponse, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        """As supporting mode, add a decomposition hint to other modes' output."""
        signal_types = {s.type for s in signals}
        if SignalType.OVERWHELMED in signal_types or SignalType.STUCK in signal_types:
            response.metadata["decomposer_note"] = "consider_breakdown"
        return response
