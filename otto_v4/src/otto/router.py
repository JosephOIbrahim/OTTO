"""NEXUS deterministic router for OTTO v5.0.

Routes PRISM signals to specialist modes via a 5-phase pipeline:
  1. ACTIVATE — which modes respond to these signals?
  2. WEIGHT — score each mode's relevance (0.0-1.0)
  3. BOUND — apply constitutional safety floors
  4. SELECT — pick primary mode + supporting team
  5. EXECUTE — run selected modes and return response

Deterministic: same signals + same state = same routing. Always.
No randomness, no floating-point order ambiguity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .modes.base import Mode, ModeResponse
from .signals import Signal, SignalType
from .state import CognitiveState
from .trails import TrailStore


@dataclass(frozen=True)
class RoutingDecision:
    """The outcome of NEXUS routing.

    Attributes
    ----------
    primary:
        The mode that will execute the main response.
    primary_weight:
        The bounded weight of the primary mode.
    supporting:
        Modes that will augment the primary response (max 2).
    weights:
        All bounded weights, sorted by mode name for determinism.
    """

    primary: str
    primary_weight: float
    supporting: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)


# Minimum weight for a mode to be included as supporting
_SUPPORT_THRESHOLD = 0.20
_MAX_SUPPORTING = 2


def route(
    signals: list[Signal],
    state: CognitiveState,
    modes: list[Mode],
    *,
    trail_adjustments: dict[str, float] | None = None,
) -> RoutingDecision | None:
    """Route signals to the appropriate specialist mode(s).

    Parameters
    ----------
    signals:
        Detected signals from PRISM.
    state:
        Current cognitive state.
    modes:
        Available specialist modes.
    trail_adjustments:
        Optional weight adjustments from outcome trails.
        Keys are mode names, values are additive adjustments
        (clamped to +/- 0.2).

    Returns
    -------
    RoutingDecision | None
        The routing decision, or None if no modes activate.
    """
    if not modes:
        return None

    # Phase 1: ACTIVATE — which modes respond?
    activated = [m for m in modes if m.responds_to(signals)]

    # Even non-activated modes with safety floors stay in play
    floored = [m for m in modes if m.safety_floor > 0 and m not in activated]
    candidates = activated + floored

    if not candidates:
        return None

    # Phase 2: WEIGHT — score each mode
    weights: dict[str, float] = {}
    for mode in candidates:
        w = mode.weight(signals, state)
        weights[mode.name] = w

    # Apply trail adjustments (Phase 5.2)
    if trail_adjustments:
        for mode_name, adjustment in sorted(trail_adjustments.items()):
            if mode_name in weights:
                clamped = max(-0.2, min(0.2, adjustment))
                weights[mode_name] = max(0.0, min(1.0, weights[mode_name] + clamped))

    # Phase 3: BOUND — apply safety floors
    for mode in candidates:
        if mode.safety_floor > 0:
            weights[mode.name] = max(weights.get(mode.name, 0), mode.safety_floor)

    # Phase 4: SELECT — pick primary + supporting
    # Deterministic: sort by (-weight, name) so ties break alphabetically
    ranked = sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))

    if not ranked:
        return None

    primary_name, primary_weight = ranked[0]

    # Supporting: modes above threshold, excluding primary, max 2
    supporting = [
        name
        for name, w in ranked[1:]
        if w >= _SUPPORT_THRESHOLD
    ][:_MAX_SUPPORTING]

    # Build deterministic weights dict
    sorted_weights = dict(sorted(weights.items()))

    return RoutingDecision(
        primary=primary_name,
        primary_weight=primary_weight,
        supporting=supporting,
        weights=sorted_weights,
    )


def route_and_execute(
    signals: list[Signal],
    state: CognitiveState,
    modes: list[Mode],
    *,
    trail_adjustments: dict[str, float] | None = None,
) -> ModeResponse | None:
    """Route signals and execute the selected mode(s).

    Convenience function that combines route() with mode execution.

    Returns
    -------
    ModeResponse | None
        The final response after primary execution and augmentation,
        or None if no modes activate.
    """
    decision = route(signals, state, modes, trail_adjustments=trail_adjustments)
    if decision is None:
        return None

    # Build name->mode lookup
    mode_map = {m.name: m for m in modes}

    primary_mode = mode_map.get(decision.primary)
    if primary_mode is None:
        return None

    # Phase 5: EXECUTE
    response = primary_mode.execute(signals, state)

    # If primary suppresses others, skip augmentation
    if response.suppress_others:
        response.metadata["routed_by"] = "nexus"
        response.metadata["primary"] = decision.primary
        return response

    # Augment with supporting modes
    for support_name in decision.supporting:
        support_mode = mode_map.get(support_name)
        if support_mode is not None:
            response = support_mode.augment(response, signals, state)

    response.metadata["routed_by"] = "nexus"
    response.metadata["primary"] = decision.primary
    response.metadata["supporting"] = decision.supporting

    return response


# ---------------------------------------------------------------------------
# Trail -> adjustment computation (Phase 5.2)
# ---------------------------------------------------------------------------

# Map signal types to the mode that typically handles them
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
    SignalType.BURST_DETECTED: "redirector",
    SignalType.EXPLORING: "guide",
    SignalType.FOCUSED: "acknowledger",
}

# Baseline strength: if a trail is stronger than this, it boosts;
# if weaker, it penalizes. Neutral zone avoids noise.
_BASELINE_STRENGTH = 1.0
_MAX_ADJUSTMENT = 0.2


def compute_trail_adjustments(
    signals: list[Signal],
    trail_store: TrailStore,
) -> dict[str, float]:
    """Compute per-mode weight adjustments from outcome trails.

    For each signal, looks up trails for that signal's context.
    If a mode has strong trails (above baseline), it gets a positive
    adjustment. If trails are weak (below baseline), negative.

    Adjustments are clamped to +/- 0.2 per mode.

    Parameters
    ----------
    signals:
        Current detected signals.
    trail_store:
        The trail store to query.

    Returns
    -------
    dict[str, float]
        Mode name -> weight adjustment. Empty if no relevant trails.
    """
    adjustments: dict[str, float] = {}

    for signal in signals:
        context = signal.type.value
        trails = trail_store.follow(context)

        if not trails:
            continue

        for trail in trails:
            # Extract mode name from action (e.g. "executor:nudge" -> "executor")
            mode_name = trail.action.split(":")[0] if ":" in trail.action else trail.action

            # Compute adjustment based on trail strength relative to baseline
            raw = (trail.strength - _BASELINE_STRENGTH) * 0.1
            clamped = max(-_MAX_ADJUSTMENT, min(_MAX_ADJUSTMENT, raw))

            # Accumulate (take strongest adjustment per mode)
            if mode_name in adjustments:
                # Use the adjustment with larger absolute value
                if abs(clamped) > abs(adjustments[mode_name]):
                    adjustments[mode_name] = clamped
            else:
                adjustments[mode_name] = clamped

    return dict(sorted(adjustments.items()))
