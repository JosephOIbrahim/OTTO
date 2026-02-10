"""Base types for the expert routing system.

Defines ExpertConfig (static expert metadata), ExpertWeight (a scored
expert), and ExpertSelection (the routing decision). These are the
data types that flow through the 5-phase NEXUS pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from otto.core.prism.signals import CognitiveSignal


@dataclass(frozen=True)
class ExpertConfig:
    """Static configuration for a single expert.

    Frozen because expert definitions are fixed at build time.
    The router reads these; it never modifies them.

    Attributes:
        name: Unique expert identifier (lowercase, e.g. "protector").
        safety_floor: Minimum activation level (constitutional).
            0.0 for non-floored experts.
        trigger_signals: Which CognitiveSignals activate this expert.
        signal_affinities: How strongly this expert responds to each
            trigger signal. Values are 0.0–1.0 multipliers applied
            to signal confidence during Phase 2 (WEIGHT).
    """

    name: str
    safety_floor: float
    trigger_signals: frozenset[CognitiveSignal]
    signal_affinities: dict[CognitiveSignal, float]


@dataclass(frozen=True)
class ExpertWeight:
    """An expert with a computed activation weight.

    Produced by Phase 2 (WEIGHT) and Phase 3 (BOUND).
    """

    expert: str
    value: float


@dataclass(frozen=True)
class ExpertSelection:
    """The final routing decision from Phase 4 (SELECT).

    Frozen because once a routing decision is made for a request,
    it must not change. Downstream code reads the selection to
    determine which expert(s) generate the response.

    Attributes:
        primary: The highest-weighted expert (generates main response).
        supporting: Up to 2 additional experts with weight > 0.20
            (contribute to response via agent team).
        use_agent_team: True if there are supporting experts.
    """

    primary: ExpertWeight
    supporting: tuple[ExpertWeight, ...]
    use_agent_team: bool

    @classmethod
    def from_bounded_weights(cls, weights: list[ExpertWeight]) -> ExpertSelection:
        """Build a selection from bounded (post-Phase-3) weights.

        Sort is deterministic: (-value, expert_name) so ties break
        alphabetically by expert name. Supporting experts are those
        scoring above 0.20, limited to the top 2.

        Args:
            weights: List of ExpertWeights after safety floor bounding.

        Returns:
            ExpertSelection with primary, supporting, and team flag.
        """
        sorted_weights = sorted(
            weights, key=lambda w: (-w.value, w.expert)
        )
        primary = sorted_weights[0]
        supporting = tuple(
            w for w in sorted_weights[1:] if w.value > 0.20
        )[:2]
        return cls(
            primary=primary,
            supporting=supporting,
            use_agent_team=len(supporting) > 0,
        )
