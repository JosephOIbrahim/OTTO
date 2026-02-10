"""Protector expert — emotional safety, empathy-first.

Priority: 1 (highest among experts)
Safety floor: 10% (constitutional)
Voice: Warm, validating, empathy-first

The Protector activates when the user is frustrated, overwhelmed,
or has crashed. It leads with empathy and validation before any
problem-solving. This is the first line of cognitive safety.
"""

from otto_v3.core.experts.base import ExpertConfig
from otto_v3.core.prism.signals import CognitiveSignal

CONFIG = ExpertConfig(
    name="protector",
    safety_floor=0.10,
    trigger_signals=frozenset({
        CognitiveSignal.FRUSTRATED,
        CognitiveSignal.OVERWHELMED,
        CognitiveSignal.CRASHED,
    }),
    signal_affinities={
        CognitiveSignal.FRUSTRATED: 0.90,
        CognitiveSignal.OVERWHELMED: 0.70,
        CognitiveSignal.CRASHED: 0.95,
    },
)
