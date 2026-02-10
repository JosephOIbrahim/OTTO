"""Decomposer expert — breaks things down, reduces scope.

Priority: 2
Safety floor: 5% (constitutional)
Voice: Clear, structured, breaks things down

The Decomposer activates when the user is stuck or overwhelmed.
It structures chaos into manageable pieces and provides clear
next steps. Never adds complexity — only reduces it.
"""

from otto.core.experts.base import ExpertConfig
from otto.core.prism.signals import CognitiveSignal

CONFIG = ExpertConfig(
    name="decomposer",
    safety_floor=0.05,
    trigger_signals=frozenset({
        CognitiveSignal.STUCK,
        CognitiveSignal.OVERWHELMED,
        CognitiveSignal.TASK_IMPLIED,
    }),
    signal_affinities={
        CognitiveSignal.STUCK: 0.85,
        CognitiveSignal.OVERWHELMED: 0.75,
        CognitiveSignal.TASK_IMPLIED: 0.50,
    },
)
