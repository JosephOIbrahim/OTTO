"""UCB1-based mode weight learning for OTTO v5.0.

Replaces heuristic trail adjustments with Upper Confidence Bound
(Auer et al. 2002). Deterministic: same outcome data -> same scores.

UCB score = success_rate + c * sqrt(ln(total_outcomes) / mode_outcomes)

Constitutional safety floors are NEVER overridden -- UCB adjustments
are additive and clamped to +/-0.2, applied BEFORE floor bounding.
"""

from __future__ import annotations

import math

from .signals import Signal, SignalType
from .trails import TrailStore

_EXPLORATION_CONSTANT = 1.0
_MAX_ADJUSTMENT = 0.2
_NEUTRAL_RATE = 0.5  # Baseline: adjustments relative to 50% success
_MIN_SAMPLES = 3  # Don't adjust with fewer than 3 observations

# Signal type -> typical mode mapping (mirrors router._SIGNAL_TO_MODE)
_SIGNAL_TO_MODE: dict[SignalType, str] = {
    SignalType.COMMITMENT_DETECTED: "executor",
    SignalType.ACTION_REQUIRED: "executor",
    SignalType.DEADLINE_MENTIONED: "executor",
    SignalType.FRUSTRATED: "protector",
    SignalType.OVERWHELMED: "protector",
    SignalType.CRASH_ZONE: "protector",
    SignalType.SPIRAL: "protector",
    SignalType.DEPLETED: "restorer",
    SignalType.STUCK: "decomposer",
    SignalType.EXPLORING: "guide",
    SignalType.FOCUSED: "acknowledger",
}


def compute_ucb_adjustments(
    signals: list[Signal],
    trail_store: TrailStore,
) -> dict[str, float]:
    """Compute per-mode weight adjustments using UCB1.

    For each signal, looks up the corresponding mode's outcome history.
    Modes with high success rates get positive adjustments; modes with
    low success rates get negative adjustments. The exploration bonus
    rewards under-tested modes.

    Parameters
    ----------
    signals:
        Current detected signals.
    trail_store:
        The trail store to query for outcome data.

    Returns
    -------
    dict[str, float]
        Mode name -> weight adjustment. Empty if insufficient data.
    """
    adjustments: dict[str, float] = {}

    all_total = trail_store.get_total_outcomes()
    if all_total <= 0:
        return {}

    for signal in signals:
        mode_name = _SIGNAL_TO_MODE.get(signal.type)
        if not mode_name:
            continue

        stats = trail_store.get_mode_stats(mode_name)
        total = stats.get("total", 0)
        if total < _MIN_SAMPLES:
            continue

        rate = trail_store.get_success_rate(mode_name)
        if rate is None:
            continue

        # UCB1: success_rate + c * sqrt(ln(N) / n)
        exploration = _EXPLORATION_CONSTANT * math.sqrt(
            math.log(all_total) / total
        )
        ucb_score = rate + exploration

        # Convert to adjustment: (ucb_score - neutral) scaled to [-0.2, 0.2]
        raw = (ucb_score - _NEUTRAL_RATE) * 0.4  # Scale so 1.0 -> +0.2
        clamped = max(-_MAX_ADJUSTMENT, min(_MAX_ADJUSTMENT, raw))

        # Take strongest adjustment per mode across signals
        if mode_name in adjustments:
            if abs(clamped) > abs(adjustments[mode_name]):
                adjustments[mode_name] = clamped
        else:
            adjustments[mode_name] = clamped

    return dict(sorted(adjustments.items()))
