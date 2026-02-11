"""Protector mode — emotional safety and crisis intervention.

The Protector has a constitutional 10% safety floor: it always runs
and can suppress any other mode's output. When frustrated or in crisis,
the Protector intervenes first, validates feelings, and offers
simplified options (max 3 when overwhelmed, max 1 when in RED).
"""

from __future__ import annotations

from otto.signals import Signal, SignalType
from otto.state import CognitiveState

from .base import ModeResponse

_ACTIVATION_SIGNALS = frozenset({
    SignalType.FRUSTRATED,
    SignalType.CRASH_ZONE,
    SignalType.SPIRAL,
    SignalType.OVERWHELMED,
})

# Response templates — no LLM, no cost, deterministic
_FRUSTRATED_RESPONSES = [
    "I can see this is frustrating. That's valid. Want to step back for a moment, or should I simplify what we're working on?",
    "Frustration makes sense here. Want to take a break, try a different approach, or park this for now?",
]

_CRASH_RESPONSE = (
    "You've been going hard. Permission granted to stop. "
    "Your commitments are safe — they'll be here when you're ready."
)

_OVERWHELMED_RESPONSE = (
    "There's a lot going on. Let's pick just one thing. "
    "What matters most right now?"
)

_RED_RESPONSE = (
    "OTTO is stepping back. You don't need more input right now. "
    "Everything is saved. Take the space you need."
)


class ProtectorMode:
    """Emotional safety mode. 10% constitutional floor.

    The Protector validates first, problem-solves second.
    It can suppress all other modes via suppress_others=True.
    """

    @property
    def name(self) -> str:
        return "protector"

    @property
    def safety_floor(self) -> float:
        return 0.10  # Constitutional: always at least 10%

    def responds_to(self, signals: list[Signal]) -> bool:
        return any(s.type in _ACTIVATION_SIGNALS for s in signals)

    def weight(self, signals: list[Signal], state: CognitiveState) -> float:
        base = self.safety_floor

        # RED burnout: protector takes full control
        if state.burnout == "RED":
            return 1.0

        # Crisis signals escalate weight
        relevant = [s for s in signals if s.type in _ACTIVATION_SIGNALS]
        if relevant:
            signal_weight = max(s.confidence for s in relevant)
            base = max(base, signal_weight)

        # ORANGE burnout boosts protector
        if state.burnout == "ORANGE":
            base = max(base, 0.6)

        return min(1.0, base)

    def execute(
        self, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        signal_types = {s.type for s in signals}

        # RED burnout: maximum protection
        if state.burnout == "RED":
            return ModeResponse(
                text=_RED_RESPONSE,
                suppress_others=True,
                metadata={"action": "full_protection", "burnout": "RED"},
            )

        # Crash zone: permission to stop
        if SignalType.CRASH_ZONE in signal_types:
            return ModeResponse(
                text=_CRASH_RESPONSE,
                suppress_others=True,
                metadata={"action": "crash_intervention"},
            )

        # Overwhelmed: reduce to one choice
        if SignalType.OVERWHELMED in signal_types:
            return ModeResponse(
                text=_OVERWHELMED_RESPONSE,
                suppress_others=True,
                metadata={"action": "simplify", "max_options": 1},
            )

        # Frustrated: validate + offer options (max 3)
        if SignalType.FRUSTRATED in signal_types:
            # Deterministic: pick template based on confidence
            frustrated = [s for s in signals if s.type == SignalType.FRUSTRATED]
            idx = 0 if frustrated[0].confidence >= 0.8 else 1
            idx = idx % len(_FRUSTRATED_RESPONSES)
            return ModeResponse(
                text=_FRUSTRATED_RESPONSES[idx],
                suppress_others=True,
                metadata={"action": "validate", "max_options": 3},
            )

        # Spiral: gentle exit ramp
        if SignalType.SPIRAL in signal_types:
            return ModeResponse(
                text="I notice a pattern forming. Want to pause and reset, or keep going?",
                suppress_others=True,
                metadata={"action": "spiral_break"},
            )

        # Fallback (safety floor activated but no strong signal)
        return ModeResponse(
            text="",
            metadata={"action": "monitoring"},
        )

    def augment(
        self, response: ModeResponse, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        """As a supporting mode, the Protector can add safety notes."""
        # If burnout is elevated, add a gentle note
        if state.burnout in ("ORANGE", "RED"):
            if response.text and not response.suppress_others:
                response.metadata["protector_note"] = "energy_warning"
        return response
