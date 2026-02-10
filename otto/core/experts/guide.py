"""Guide expert — Socratic discovery, strategic thinking.

Priority: 6
Safety floor: 0% (dynamic)
Voice: Curious, strategic, Socratic

The Guide activates when the user is exploring ideas or has
follow-ups to process. It asks questions rather than giving
answers, helping the user discover their own solutions.
"""

from otto.core.experts.base import ExpertConfig
from otto.core.prism.signals import CognitiveSignal

CONFIG = ExpertConfig(
    name="guide",
    safety_floor=0.0,
    trigger_signals=frozenset({
        CognitiveSignal.EXPLORING,
        CognitiveSignal.DECISION_MADE,
        CognitiveSignal.FOLLOW_UP_NEEDED,
    }),
    signal_affinities={
        CognitiveSignal.EXPLORING: 0.85,
        CognitiveSignal.DECISION_MADE: 0.60,
        CognitiveSignal.FOLLOW_UP_NEEDED: 0.55,
    },
)
