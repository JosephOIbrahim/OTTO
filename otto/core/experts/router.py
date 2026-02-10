"""NEXUS 5-phase expert routing pipeline.

The router takes PRISM signals and LIVRPS-resolved state, then
produces an ExpertSelection through 5 deterministic phases:

    Phase 1: ACTIVATE — identify which experts respond to these signals
    Phase 2: WEIGHT   — compute activation scores (signal * affinity + state boosts)
    Phase 3: BOUND    — enforce constitutional safety floors
    Phase 4: SELECT   — pick primary + supporting experts
    Phase 5: UPDATE   — record routing decision (pheromone trail stub)

Determinism guarantees ([He2025]):
    - Expert iteration: sorted by expert name
    - Signal iteration: sorted by signal type name
    - Weight comparison: explicit tiebreaker (expert name)
    - Same signals + same state = same selection, always
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from otto.core.constitution import SafetyFloors
from otto.core.prism.signals import CognitiveSignal, Signal
from otto.core.experts.base import ExpertConfig, ExpertSelection, ExpertWeight

# --- Import all 7 expert configs ---
from otto.core.experts.protector import CONFIG as PROTECTOR
from otto.core.experts.decomposer import CONFIG as DECOMPOSER
from otto.core.experts.restorer import CONFIG as RESTORER
from otto.core.experts.redirector import CONFIG as REDIRECTOR
from otto.core.experts.acknowledger import CONFIG as ACKNOWLEDGER
from otto.core.experts.guide import CONFIG as GUIDE
from otto.core.experts.executor import CONFIG as EXECUTOR

# [He2025]: Registry is a tuple sorted by expert name at module load.
# This fixes evaluation order for all phases.
ALL_EXPERTS: tuple[ExpertConfig, ...] = tuple(
    sorted(
        [PROTECTOR, DECOMPOSER, RESTORER, REDIRECTOR,
         ACKNOWLEDGER, GUIDE, EXECUTOR],
        key=lambda e: e.name,
    )
)

# --- State-to-expert boost mappings ---
# Each entry: (property_name, property_value, expert_name, boost_amount)
# Applied during Phase 2 when LIVRPS-resolved state matches.
# Tuple of tuples for [He2025] fixed order.
STATE_BOOSTS: tuple[tuple[str, str, str, float], ...] = (
    ("burnout", "orange", "protector", 0.20),
    ("burnout", "orange", "restorer", 0.15),
    ("burnout", "red", "protector", 0.30),
    ("energy", "depleted", "restorer", 0.30),
    ("energy", "high", "executor", 0.10),
    ("energy", "low", "restorer", 0.15),
    ("momentum", "crashed", "protector", 0.15),
    ("momentum", "crashed", "restorer", 0.25),
)

# Type alias for the optional Phase 5 callback
RouteCallback = Callable[[ExpertSelection, list[Signal]], None]


class NEXUSRouter:
    """5-phase expert routing pipeline with safety floor enforcement.

    The router is stateless between calls — all state comes from the
    input signals and LIVRPS-resolved state dict. This makes routing
    deterministic and testable.

    Args:
        safety_floors: Constitutional safety floors (from Day 1).
            Defaults to the standard SafetyFloors.
        experts: Expert configurations. Defaults to ALL_EXPERTS.
        on_route: Optional callback invoked in Phase 5 (UPDATE).
            Receives the ExpertSelection and input signals.
    """

    def __init__(
        self,
        safety_floors: SafetyFloors | None = None,
        experts: tuple[ExpertConfig, ...] | None = None,
        on_route: RouteCallback | None = None,
    ) -> None:
        self._floors = safety_floors or SafetyFloors()
        # [He2025]: Ensure experts are sorted by name
        self._experts = tuple(
            sorted(experts or ALL_EXPERTS, key=lambda e: e.name)
        )
        self._on_route = on_route

        # Build floor lookup: expert_name → floor value
        self._floor_map: dict[str, float] = {
            e.name: e.safety_floor for e in self._experts
        }

    @property
    def experts(self) -> tuple[ExpertConfig, ...]:
        """All registered experts, sorted by name."""
        return self._experts

    # =================================================================
    # Public API
    # =================================================================

    def route(
        self,
        signals: list[Signal],
        state: dict[str, Any] | None = None,
    ) -> ExpertSelection:
        """Run the full 5-phase routing pipeline.

        Args:
            signals: Detected PRISM signals for this request.
            state: LIVRPS-resolved state dict. Keys are property
                names, values are resolved values.

        Returns:
            ExpertSelection with primary, supporting, and team flag.
        """
        if state is None:
            state = {}

        # Phase 1: ACTIVATE
        activated = self._activate(signals)

        # Phase 2: WEIGHT
        weighted = self._weight(activated, signals, state)

        # Phase 3: BOUND (constitutional safety floors)
        bounded = self._bound(weighted)

        # Phase 4: SELECT
        selection = ExpertSelection.from_bounded_weights(bounded)

        # Phase 5: UPDATE (pheromone trail deposit — stub/callback)
        self._update(selection, signals)

        return selection

    # =================================================================
    # Phase 1: ACTIVATE
    # =================================================================

    def _activate(self, signals: list[Signal]) -> list[ExpertConfig]:
        """Identify which experts respond to the detected signals.

        An expert is activated if ANY of its trigger signals appear
        in the detected signal list. Iteration is sorted by expert
        name for [He2025].

        Returns:
            List of activated ExpertConfigs (may be empty if no
            signals match — safety floors still apply in Phase 3).
        """
        signal_types = {s.type for s in signals}
        activated: list[ExpertConfig] = []
        for expert in self._experts:  # Already sorted by name
            if expert.trigger_signals & signal_types:
                activated.append(expert)
        return activated

    # =================================================================
    # Phase 2: WEIGHT
    # =================================================================

    def _weight(
        self,
        activated: list[ExpertConfig],
        signals: list[Signal],
        state: dict[str, Any],
    ) -> list[ExpertWeight]:
        """Compute activation weights for all experts.

        For activated experts:
            weight = sum(signal.confidence * affinity) + state_boosts
            clamped to [0.0, 1.0]

        For non-activated experts:
            weight = 0.0 (safety floors applied in Phase 3)

        Signal iteration uses sorted order by signal type name for
        [He2025] determinism.

        Returns:
            List of ExpertWeights for ALL experts (not just activated).
        """
        # Build signal confidence lookup
        signal_conf: dict[CognitiveSignal, float] = {}
        for sig in signals:
            # Keep highest confidence if same signal type appears twice
            existing = signal_conf.get(sig.type, -1.0)
            if sig.confidence > existing:
                signal_conf[sig.type] = sig.confidence

        # Compute state boosts per expert
        expert_boosts: dict[str, float] = {}
        for prop_name, prop_value, expert_name, boost in STATE_BOOSTS:
            if state.get(prop_name) == prop_value:
                current = expert_boosts.get(expert_name, 0.0)
                expert_boosts[expert_name] = current + boost

        # Set of activated expert names for O(1) lookup
        activated_names = {e.name for e in activated}

        # Compute weights for ALL experts
        weights: list[ExpertWeight] = []
        for expert in self._experts:  # Sorted by name
            if expert.name in activated_names:
                # Sum of (confidence * affinity) for matching signals
                signal_weight = 0.0
                for sig_type in sorted(
                    expert.signal_affinities.keys(),
                    key=lambda s: s.name,
                ):
                    if sig_type in signal_conf:
                        signal_weight += (
                            signal_conf[sig_type]
                            * expert.signal_affinities[sig_type]
                        )

                # Add state boosts
                boost = expert_boosts.get(expert.name, 0.0)
                total = min(signal_weight + boost, 1.0)
            else:
                # Non-activated: only state boosts (if any)
                total = min(expert_boosts.get(expert.name, 0.0), 1.0)

            weights.append(ExpertWeight(expert=expert.name, value=total))

        return weights

    # =================================================================
    # Phase 3: BOUND (CONSTITUTIONAL — SAFETY FLOORS)
    # =================================================================

    def _bound(self, weights: list[ExpertWeight]) -> list[ExpertWeight]:
        """Apply constitutional safety floors to expert weights.

        Every expert's weight is raised to at least its safety floor.
        No expert can score BELOW its floor after this phase.

        This is the enforcement of Patent Claim #2. The floors come
        from SafetyFloors (frozen dataclass, Day 1). They cannot be
        lowered at runtime.

        Returns:
            New list of ExpertWeights with floors applied. Sorted by
            expert name for [He2025].
        """
        return [
            ExpertWeight(
                expert=w.expert,
                value=max(w.value, self._floor_map.get(w.expert, 0.0)),
            )
            for w in sorted(weights, key=lambda w: w.expert)
        ]

    # =================================================================
    # Phase 5: UPDATE (pheromone trail deposit — stub)
    # =================================================================

    def _update(
        self, selection: ExpertSelection, signals: list[Signal]
    ) -> None:
        """Record the routing decision for future learning.

        Currently a stub that invokes the optional on_route callback.
        Will integrate with the pheromone trail system (Day 7).
        """
        if self._on_route is not None:
            self._on_route(selection, signals)
