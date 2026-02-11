"""Executor mode — commitment tracking and follow-up.

Wraps the existing v4.0 nudge.py + store.py logic without changing
any behavior. This is the mode that was implicitly running in v4.0.
"""

from __future__ import annotations

from otto.nudge import check_and_nudge
from otto.signals import Signal, SignalType
from otto.state import CognitiveState
from otto.store import CommitmentStore

from .base import ModeResponse

_ACTIVATION_SIGNALS = frozenset({
    SignalType.COMMITMENT_DETECTED,
    SignalType.ACTION_REQUIRED,
    SignalType.DEADLINE_MENTIONED,
})


class ExecutorMode:
    """Direct action mode: commitment tracking and follow-up nudges.

    Responds to commitment, action, and deadline signals. Delegates
    to the existing nudge.py and store.py for all behavior.
    """

    def __init__(self, store: CommitmentStore | None = None) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "executor"

    @property
    def safety_floor(self) -> float:
        return 0.0  # No safety floor — optional mode

    def responds_to(self, signals: list[Signal]) -> bool:
        return any(s.type in _ACTIVATION_SIGNALS for s in signals)

    def weight(self, signals: list[Signal], state: CognitiveState) -> float:
        if not self.responds_to(signals):
            return 0.0

        # Base weight from signal confidence
        relevant = [s for s in signals if s.type in _ACTIVATION_SIGNALS]
        if not relevant:
            return 0.0

        base = max(s.confidence for s in relevant)

        # Reduce weight if user is depleted or overwhelmed
        if state.energy == "depleted":
            base *= 0.3
        elif state.energy == "low":
            base *= 0.6

        return min(1.0, base)

    def execute(
        self, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        if self._store is None:
            return ModeResponse(
                text="No commitment store available.",
                metadata={"action": "none"},
            )

        nudges = check_and_nudge(self._store)
        if not nudges:
            return ModeResponse(
                text="All commitments are on track.",
                metadata={"action": "check", "nudge_count": 0},
            )

        return ModeResponse(
            text="\n\n".join(nudges),
            metadata={"action": "nudge", "nudge_count": len(nudges)},
        )

    def augment(
        self, response: ModeResponse, signals: list[Signal], state: CognitiveState
    ) -> ModeResponse:
        # Executor doesn't modify other modes' output
        return response
