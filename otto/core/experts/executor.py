"""Executor expert — direct implementation, stays out of way.

Priority: 7 (lowest priority, highest efficiency)
Safety floor: 0% (dynamic)
Voice: Direct, efficient, implementation-focused

The Executor activates when the user is focused and productive.
It provides minimal friction — no unnecessary questions, no
over-explaining. When the user is in flow, get out of the way.
"""

from otto.core.experts.base import ExpertConfig
from otto.core.prism.signals import CognitiveSignal

CONFIG = ExpertConfig(
    name="executor",
    safety_floor=0.0,
    trigger_signals=frozenset({
        CognitiveSignal.FOCUSED,
        CognitiveSignal.TASK_IMPLIED,
        CognitiveSignal.HYPERFOCUS,
        CognitiveSignal.COMMITMENT_OUTBOUND,
        CognitiveSignal.COMMITMENT_INBOUND,
    }),
    signal_affinities={
        CognitiveSignal.FOCUSED: 0.85,
        CognitiveSignal.TASK_IMPLIED: 0.70,
        CognitiveSignal.HYPERFOCUS: 0.65,
        CognitiveSignal.COMMITMENT_OUTBOUND: 0.55,
        CognitiveSignal.COMMITMENT_INBOUND: 0.50,
    },
)
