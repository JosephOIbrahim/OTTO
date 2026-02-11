"""Guide mode -- Socratic exploration and curiosity support.

No safety floor (optional mode). When the user is exploring or asking
"what if" questions, the Guide encourages discovery through questions
rather than answers. Template-based (no LLM, no cost).

This mode supports the user's natural curiosity without taking over.
"""

from __future__ import annotations

from otto.signals import Signal, SignalType
from otto.state import CognitiveState

from .base import ModeResponse

_ACTIVATION_SIGNALS = frozenset({
    SignalType.EXPLORING,
    SignalType.FOCUSED,
})

# Guide templates — Socratic, question-based
_EXPLORE_PROMPTS = [
    "What's drawing you to this? Sometimes the thread is worth following.",
    "Interesting direction. What would it look like if you pursued it?",
    "What's the smallest experiment that would test this idea?",
]

_FOCUS_PROMPTS = [
    "You're in a good groove. What's the next step you see?",
    "Clear focus. Keep going — what comes after this?",
]


class GuideMode:
    """Socratic exploration mode. No safety floor (optional).

    Encourages discovery through questions. Follows the user's
    curiosity without directing it.
    """

    @property
    def name(self) -> str:
        return "guide"

    @property
    def safety_floor(self) -> float:
        return 0.0  # Optional mode

    def responds_to(self, signals: list[Signal]) -> bool:
        return any(s.type in _ACTIVATION_SIGNALS for s in signals)

    def weight(self, signals: list[Signal], state: CognitiveState) -> float:
        if not self.responds_to(signals):
            return 0.0

        base = 0.2  # Low base: guide supports, doesn't lead

        # Exploring signals boost guide weight
        exploring = [s for s in signals if s.type == SignalType.EXPLORING]
        if exploring:
            base = max(base, max(s.confidence for s in exploring) * 0.6)

        # High energy + exploring = Socratic mode shines
        if state.energy == "high" and exploring:
            base = max(base, 0.5)

        return min(1.0, base)

    def execute(
        self, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        signal_types = {s.type for s in signals}

        # Focused: encourage continuation
        if SignalType.FOCUSED in signal_types and SignalType.EXPLORING not in signal_types:
            return ModeResponse(
                text=_FOCUS_PROMPTS[0],
                metadata={"action": "encourage_focus"},
            )

        # Exploring: Socratic prompt
        exploring = [s for s in signals if s.type == SignalType.EXPLORING]
        if exploring:
            # Deterministic template selection
            confidence_bucket = int(exploring[0].confidence * 10) % len(_EXPLORE_PROMPTS)
            return ModeResponse(
                text=_EXPLORE_PROMPTS[confidence_bucket],
                metadata={"action": "socratic_prompt"},
            )

        # Default
        return ModeResponse(
            text="",
            metadata={"action": "monitoring"},
        )

    def augment(
        self, response: ModeResponse, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        """As supporting mode, add a curious note."""
        if any(s.type == SignalType.EXPLORING for s in signals):
            response.metadata["guide_note"] = "curiosity_supported"
        return response
