"""Effort controller for Opus 4.6 API calls.

Maps cognitive routing decisions to API effort levels, controlling
how much computation the model spends on each request.

Effort levels (from CLAUDE.md §10)::

    LOW    → "low"     — Check-ins, energy queries (~$0.003)
    MEDIUM → "medium"  — Standard routing (~$0.015)
    HIGH   → "high"    — Complex multi-expert (~$0.045)
    MAX    → "max"     — Deep analysis (~$0.08+)

Cost gating::

    auto    → < $0.10    (proceed without confirmation)
    warn    → $0.10–0.50 (log warning)
    confirm → > $0.50    (require explicit approval)

Effort selection is deterministic — same routing decision
yields the same effort level, every time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EffortLevel(Enum):
    """Maps to the Opus 4.6 Messages API ``effort`` parameter.

    Values are the literal strings sent over the wire.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"


@dataclass(frozen=True)
class CostEstimate:
    """Estimated cost of an API call.

    Attributes:
        input_tokens: Estimated input token count.
        output_tokens: Estimated output token count.
        estimated_usd: Total estimated cost in USD.
        gate: Cost gate level: ``"auto"``, ``"warn"``, or ``"confirm"``.
    """

    input_tokens: int
    output_tokens: int
    estimated_usd: float
    gate: str  # "auto", "warn", "confirm"


# Cost gate thresholds (from CLAUDE.md §10)
_WARN_THRESHOLD_USD = 0.10
_CONFIRM_THRESHOLD_USD = 0.50


def _compute_gate(estimated_usd: float) -> str:
    """Determine cost gate level from estimated USD cost."""
    if estimated_usd >= _CONFIRM_THRESHOLD_USD:
        return "confirm"
    if estimated_usd >= _WARN_THRESHOLD_USD:
        return "warn"
    return "auto"


class EffortController:
    """Selects effort level and estimates cost for API calls.

    Effort selection logic (evaluated top-to-bottom, first match wins):

    1. Explicit ``override`` → use that level
    2. Primary expert is ``protector`` or ``restorer`` → HIGH
    3. Agent team is active (supporting experts) → HIGH
    4. 3+ signals detected → MEDIUM
    5. Default → LOW

    Args:
        input_cost_per_m: Cost per million input tokens (default $5.0).
        output_cost_per_m: Cost per million output tokens (default $25.0).
    """

    def __init__(
        self,
        input_cost_per_m: float = 5.0,
        output_cost_per_m: float = 25.0,
    ) -> None:
        self._input_cost_per_m = input_cost_per_m
        self._output_cost_per_m = output_cost_per_m

    def select_effort(
        self,
        primary_expert: str,
        use_agent_team: bool = False,
        signal_count: int = 0,
        override: EffortLevel | None = None,
    ) -> EffortLevel:
        """Select effort level based on routing decision.

        Args:
            primary_expert: Name of the primary expert (from routing).
            use_agent_team: Whether supporting experts are active.
            signal_count: Number of detected signals.
            override: Explicit effort level (highest priority).

        Returns:
            Selected EffortLevel.
        """
        if override is not None:
            return override

        # Safety-critical experts need deeper reasoning
        if primary_expert in ("protector", "restorer"):
            return EffortLevel.HIGH

        # Multi-expert merge needs more computation
        if use_agent_team:
            return EffortLevel.HIGH

        # Multiple signals suggest complexity
        if signal_count >= 3:
            return EffortLevel.MEDIUM

        return EffortLevel.LOW

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> CostEstimate:
        """Estimate the cost of an API call.

        Args:
            input_tokens: Estimated input token count.
            output_tokens: Estimated output token count.

        Returns:
            CostEstimate with USD amount and gate level.
        """
        input_cost = (input_tokens / 1_000_000) * self._input_cost_per_m
        output_cost = (output_tokens / 1_000_000) * self._output_cost_per_m
        total = input_cost + output_cost

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_usd=total,
            gate=_compute_gate(total),
        )
