"""Restorer mode -- energy management, permission to rest, and exploration support.

The Restorer has a constitutional 5% safety floor. When the user is
depleted or in ORANGE burnout, the Restorer grants permission to stop,
suggests easy wins, and suppresses demanding tasks.

Also absorbs the Guide mode's Socratic exploration support: when the user
is exploring with available energy, the Restorer encourages discovery
through questions rather than answers.

"Rest is productive" is a constitutional principle.
"""

from __future__ import annotations

from otto.signals import Signal, SignalType
from otto.state import CognitiveState

from .base import ModeResponse

_ACTIVATION_SIGNALS = frozenset({
    SignalType.DEPLETED,
    SignalType.EXPLORING,
})

# Templates -- warm, non-judgmental, permission-granting
_DEPLETED_RESPONSE = (
    "Permission granted: rest is productive. "
    "Your commitments are safe and will be here tomorrow."
)

_LOW_ENERGY_RESPONSE = (
    "Energy is low. Want to tackle something small and achievable, "
    "or call it for today? Both are good options."
)

_ORANGE_RESPONSE = (
    "You've been pushing hard. OTTO will only surface urgent items. "
    "Everything else can wait."
)

# Exploration templates (absorbed from Guide)
_EXPLORE_PROMPTS = [
    "What's drawing you to this? Sometimes the thread is worth following.",
    "Interesting direction. What would it look like if you pursued it?",
    "What's the smallest experiment that would test this idea?",
]


class RestorerMode:
    """Energy management and exploration mode. 5% constitutional floor.

    Grants permission to rest. Suppresses demanding nudges when
    the user is depleted. Supports exploration with Socratic prompts
    when energy allows. "Rest is productive."
    """

    @property
    def name(self) -> str:
        return "restorer"

    @property
    def safety_floor(self) -> float:
        return 0.05  # Constitutional: always at least 5%

    def responds_to(self, signals: list[Signal]) -> bool:
        return any(s.type in _ACTIVATION_SIGNALS for s in signals)

    def weight(self, signals: list[Signal], state: CognitiveState) -> float:
        base = self.safety_floor

        # Depleted energy: restorer takes priority
        if state.energy == "depleted":
            return 0.9

        # Low energy: significant weight
        if state.energy == "low":
            base = max(base, 0.5)

        # ORANGE burnout: boost restorer
        if state.burnout == "ORANGE":
            base = max(base, 0.6)

        # Depleted signal in input
        depleted = [s for s in signals if s.type == SignalType.DEPLETED]
        if depleted:
            signal_weight = max(s.confidence for s in depleted)
            base = max(base, signal_weight)

        # Exploring: support exploration (absorbed from Guide)
        exploring = [s for s in signals if s.type == SignalType.EXPLORING]
        if exploring:
            explore_weight = max(s.confidence for s in exploring) * 0.6
            # High energy + exploring = Socratic mode
            if state.energy == "high":
                explore_weight = max(explore_weight, 0.5)
            base = max(base, explore_weight)

        return min(1.0, base)

    def execute(
        self, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        signal_types = {s.type for s in signals}

        # Depleted energy: full rest permission
        if state.energy == "depleted":
            return ModeResponse(
                text=_DEPLETED_RESPONSE,
                suppress_others=True,
                metadata={
                    "action": "grant_rest",
                    "suppress_nudges_hours": 12,
                },
            )

        # ORANGE burnout: reduce scope
        if state.burnout == "ORANGE":
            return ModeResponse(
                text=_ORANGE_RESPONSE,
                metadata={
                    "action": "reduce_scope",
                    "urgent_only": True,
                },
            )

        # Exploring: Socratic prompt (absorbed from Guide)
        if SignalType.EXPLORING in signal_types:
            exploring = [s for s in signals if s.type == SignalType.EXPLORING]
            confidence_bucket = int(exploring[0].confidence * 10) % len(_EXPLORE_PROMPTS)
            return ModeResponse(
                text=_EXPLORE_PROMPTS[confidence_bucket],
                metadata={"action": "socratic_prompt"},
            )

        # Low energy: offer choice
        if state.energy == "low":
            return ModeResponse(
                text=_LOW_ENERGY_RESPONSE,
                metadata={
                    "action": "offer_easy_win",
                },
            )

        # Depleted signal detected but state not yet updated
        if SignalType.DEPLETED in signal_types:
            return ModeResponse(
                text=_LOW_ENERGY_RESPONSE,
                metadata={"action": "offer_easy_win"},
            )

        # Safety floor activated but no strong signal
        return ModeResponse(
            text="",
            metadata={"action": "monitoring"},
        )

    def augment(
        self, response: ModeResponse, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        """As a supporting mode, can soften other modes' demands."""
        if state.energy in ("low", "depleted") and not response.suppress_others:
            response.metadata["restorer_note"] = "low_energy_context"
        if any(s.type == SignalType.EXPLORING for s in signals):
            response.metadata["restorer_note"] = "curiosity_supported"
        return response
