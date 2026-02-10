"""Redirector expert — acknowledges tangent, refocuses.

Priority: 4
Safety floor: 0% (dynamic)
Voice: Acknowledges, parks ideas, gently refocuses

The Redirector activates on context switches. It validates the
tangent ("good thought"), parks it for later, and brings focus
back to the current task without judgment.
"""

from otto.core.experts.base import ExpertConfig
from otto.core.prism.signals import CognitiveSignal

CONFIG = ExpertConfig(
    name="redirector",
    safety_floor=0.0,
    trigger_signals=frozenset({
        CognitiveSignal.CONTEXT_SWITCH,
    }),
    signal_affinities={
        CognitiveSignal.CONTEXT_SWITCH: 0.80,
    },
)
