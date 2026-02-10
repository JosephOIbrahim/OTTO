"""Restorer expert — permission-giving, recovery-focused.

Priority: 3
Safety floor: 5% (constitutional)
Voice: Permission-giving, gentle, recovery-focused

The Restorer activates when energy is depleted or a crash zone
is approaching. It gives explicit permission to rest and frames
recovery as productive, not lazy. Constitutional principle:
"Recovery is not laziness."
"""

from otto_v3.core.experts.base import ExpertConfig
from otto_v3.core.prism.signals import CognitiveSignal

CONFIG = ExpertConfig(
    name="restorer",
    safety_floor=0.05,
    trigger_signals=frozenset({
        CognitiveSignal.DEPLETED,
        CognitiveSignal.LOW_ENERGY,
        CognitiveSignal.CRASH_ZONE_APPROACHING,
        CognitiveSignal.CRASHED,
    }),
    signal_affinities={
        CognitiveSignal.DEPLETED: 0.90,
        CognitiveSignal.LOW_ENERGY: 0.80,
        CognitiveSignal.CRASH_ZONE_APPROACHING: 0.75,
        CognitiveSignal.CRASHED: 0.60,
    },
)
