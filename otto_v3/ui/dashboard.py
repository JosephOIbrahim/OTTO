"""Cognitive state dashboard — visualization data model.

Aggregates cognitive state from the chat session, services, and
pipeline into a display-ready snapshot.  The dashboard is a data
model — rendering is handled by the TUI or MCP layer.

All user-facing strings are constitutional:
    - No clinical language ("ADHD", "executive dysfunction")
    - No minimizing language ("just", "simply")
    - Dignity-first framing

Description dicts are sorted by key at module load.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from otto_v3.services.base import CategoricalSignal


# ── Expert descriptions for user display ──────────────────────
# Constitutional: No clinical language.  Dignity-first.
# Sorted by expert name.

EXPERT_DESCRIPTIONS: dict[str, str] = dict(sorted({
    "acknowledger": "Celebrating what you've accomplished",
    "decomposer": "Breaking things down into manageable pieces",
    "executor": "Getting things done efficiently",
    "guide": "Exploring possibilities together",
    "protector": "Looking out for your wellbeing",
    "redirector": "Helping you stay on track",
    "restorer": "Making space for rest and recovery",
}.items()))


# ── Effort level descriptions ─────────────────────────────────
# Sorted by level name.

EFFORT_DESCRIPTIONS: dict[str, str] = dict(sorted({
    "high": "Thinking carefully",
    "low": "Quick response",
    "max": "Deep analysis",
    "medium": "Standard thinking",
}.items()))


@dataclass(frozen=True)
class DashboardState:
    """Snapshot of current cognitive state for display.

    Frozen — each snapshot is immutable.  Build a new one
    for each dashboard refresh.

    Attributes:
        primary_expert: Name of the primary expert.
        supporting_experts: Names of supporting experts (0-2).
        effort_level: Current effort level string.
        active_signals: Current service signals (categorical).
        compaction_utilization: Context window usage (0.0-1.0).
        exchange_count: Number of exchanges in this session.
        session_duration_minutes: Minutes since session started.
    """

    primary_expert: str
    supporting_experts: tuple[str, ...]
    effort_level: str
    active_signals: tuple[CategoricalSignal, ...]
    compaction_utilization: float
    exchange_count: int
    session_duration_minutes: float


class CognitiveSummary:
    """Generates human-readable summaries of cognitive state.

    All outputs are constitutional:
        - No clinical language
        - No minimizing language
        - Dignity-first framing
    """

    @staticmethod
    def describe_expert(expert_name: str) -> str:
        """Human-readable description of the current expert mode.

        Args:
            expert_name: Expert name (e.g., ``"protector"``).

        Returns:
            Friendly description string.
        """
        return EXPERT_DESCRIPTIONS.get(expert_name, "Helping you out")

    @staticmethod
    def describe_effort(effort_level: str) -> str:
        """Human-readable description of the effort level.

        Args:
            effort_level: Effort string (e.g., ``"high"``).

        Returns:
            Friendly description string.
        """
        return EFFORT_DESCRIPTIONS.get(effort_level, "Thinking")

    @staticmethod
    def describe_state(state: DashboardState) -> str:
        """One-line summary of current cognitive state.

        Args:
            state: Current dashboard state.

        Returns:
            Human-readable summary line.
        """
        parts = [
            f"Mode: {CognitiveSummary.describe_expert(state.primary_expert)}",
            f"Effort: {CognitiveSummary.describe_effort(state.effort_level)}",
            f"{state.exchange_count} exchanges",
        ]
        return " | ".join(parts)

    @staticmethod
    def describe_compaction(utilization: float) -> str:
        """Describe context window utilization.

        Args:
            utilization: Fraction used (0.0–1.0).

        Returns:
            Friendly description string.
        """
        pct = int(utilization * 100)
        if utilization < 0.5:
            return f"Plenty of room ({pct}% used)"
        if utilization < 0.8:
            return f"Getting full ({pct}% used)"
        return f"Almost full ({pct}% used) — compaction soon"
