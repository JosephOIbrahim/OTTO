"""Acknowledger mode -- validate emotions and celebrate progress.

No safety floor (optional mode). When the user completes a task or reaches
a milestone, the Acknowledger provides warm, brief validation. Momentum
sustainer: recognized progress keeps energy up.

Template-based (no LLM, no cost).
"""

from __future__ import annotations

import hashlib

from otto.signals import Signal, SignalType
from otto.state import CognitiveState

from .base import ModeResponse

# The Acknowledger responds to focused/exploring signals as supporting mode,
# and is primarily triggered programmatically on task completion.
_ACTIVATION_SIGNALS = frozenset({
    SignalType.FOCUSED,
    SignalType.EXPLORING,
})

# Celebration templates — warm, brief, not over the top
_COMPLETION_TEMPLATES = [
    "Done. That's one less thing taking up space in your head.",
    "Handled. Momentum is building.",
    "Crossed off. What's next?",
    "That's done. Nice.",
]

_MILESTONE_TEMPLATES = [
    "Look at that -- you've cleared {count} commitments. Solid work.",
    "That's {count} commitments handled. You're rolling.",
]

_STREAK_TEMPLATES = [
    "Three in a row. You're in a groove.",
    "Consistent follow-through. That's the pattern building.",
]


class AcknowledgerMode:
    """Progress validation mode. No safety floor (optional).

    Celebrates completion and milestones. Keeps momentum alive.
    """

    def __init__(self, *, completed_count: int = 0) -> None:
        self._completed_count = completed_count

    @property
    def name(self) -> str:
        return "acknowledger"

    @property
    def safety_floor(self) -> float:
        return 0.0  # Optional mode

    def responds_to(self, signals: list[Signal]) -> bool:
        return any(s.type in _ACTIVATION_SIGNALS for s in signals)

    def weight(self, signals: list[Signal], state: CognitiveState) -> float:
        if not self.responds_to(signals):
            return 0.0

        base = 0.3  # Moderate base when activated

        # Boost if momentum is building/rolling/peak
        if state.momentum in ("building", "rolling", "peak"):
            base = max(base, 0.4)

        return min(1.0, base)

    def execute(
        self, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        # Milestone check (every 5 completions)
        if self._completed_count > 0 and self._completed_count % 5 == 0:
            idx = self._completed_count % len(_MILESTONE_TEMPLATES)
            text = _MILESTONE_TEMPLATES[idx].format(count=self._completed_count)
            return ModeResponse(
                text=text,
                metadata={"action": "milestone", "count": self._completed_count},
            )

        # Streak check (3+ in momentum)
        if state.momentum in ("rolling", "peak") and self._completed_count >= 3:
            idx = self._completed_count % len(_STREAK_TEMPLATES)
            return ModeResponse(
                text=_STREAK_TEMPLATES[idx],
                metadata={"action": "streak"},
            )

        # Standard completion acknowledgment
        # Deterministic template selection via hash
        key = str(self._completed_count).encode()
        idx = int(hashlib.sha256(key).hexdigest()[:8], 16) % len(_COMPLETION_TEMPLATES)
        return ModeResponse(
            text=_COMPLETION_TEMPLATES[idx],
            metadata={"action": "acknowledge"},
        )

    def augment(
        self, response: ModeResponse, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        """As supporting mode, can add a brief positive note."""
        if state.momentum in ("building", "rolling", "peak"):
            response.metadata["acknowledger_note"] = "momentum_positive"
        return response
