"""Acknowledger expert — celebrates wins, affirms progress.

Priority: 5
Safety floor: 0% (dynamic)
Voice: Celebrates, affirms, brief

The Acknowledger activates on positive signals — high energy,
decisions made, focused state. It reinforces momentum with
brief, genuine recognition. Never performative.
"""

from otto.core.experts.base import ExpertConfig
from otto.core.prism.signals import CognitiveSignal

CONFIG = ExpertConfig(
    name="acknowledger",
    safety_floor=0.0,
    trigger_signals=frozenset({
        CognitiveSignal.HIGH_ENERGY,
        CognitiveSignal.DECISION_MADE,
        CognitiveSignal.FOCUSED,
    }),
    signal_affinities={
        CognitiveSignal.HIGH_ENERGY: 0.70,
        CognitiveSignal.DECISION_MADE: 0.65,
        CognitiveSignal.FOCUSED: 0.40,
    },
)
