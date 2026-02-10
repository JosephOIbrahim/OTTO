"""Pheromone trail system — deposit, follow, decay (Patent Claim #4).

Pheromone trails implement distributed learning through persistent
signal deposit/follow/decay.  When OTTO's routing produces a good
outcome, it deposits pheromone on that trail.  Future routing follows
stronger trails.  Unused trails decay over time.

Trail keys are ``(action, context)`` tuples.  ``action`` is what was
done (e.g., ``"route:protector"``), ``context`` is when it applied
(e.g., ``"frustrated_user"``).

Lifecycle::

    deposit("route:protector", 0.5, "frustrated")  # strengthen
    follow("frustrated")  # → sorted by strength desc
    decay()               # half-life reduction + pruning
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from otto.core.determinism.kahan import KahanAccumulator


@dataclass(frozen=True)
class Trail:
    """A single pheromone trail.

    Frozen because trails are snapshots — to update, create a new
    instance.  The TrailManager handles all mutation of the internal
    store.

    Attributes:
        action: What was done (e.g., "route:protector").
        context: When it applies (e.g., "frustrated_user").
        strength: Current trail strength (>= 0.0).
        deposit_count: How many times this trail was reinforced.
        last_deposited: When the trail was last deposited/reinforced.
    """

    action: str
    context: str
    strength: float
    deposit_count: int = 1
    last_deposited: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# Type alias for the trail store key
TrailKey = tuple[str, str]  # (action, context)


class TrailManager:
    """Manages pheromone trails: deposit, follow, query, decay.

    Stores trails in memory keyed by ``(action, context)``.  The
    DecayEngine (in ``decay.py``) operates on this manager's store.

    Args:
        half_life_hours: Decay half-life in hours (default 168 = 7 days).
        prune_threshold: Minimum strength; below this trails are pruned.
    """

    def __init__(
        self,
        half_life_hours: float = 168.0,
        prune_threshold: float = 0.001,
    ) -> None:
        self._half_life_hours = half_life_hours
        self._prune_threshold = prune_threshold
        # [He2025]: dict keyed by tuple, iterated in sorted order
        self._trails: dict[TrailKey, Trail] = {}

    # ---- Deposit (strengthen) ----

    def deposit(
        self,
        action: str,
        strength: float,
        context: str,
        now: Optional[datetime] = None,
    ) -> Trail:
        """Deposit pheromone on a trail, strengthening it.

        If the trail already exists, strength is added and deposit
        count is incremented.  If new, a fresh trail is created.

        Args:
            action: What was done.
            strength: How much to add (> 0).
            context: When it applies.
            now: Override timestamp (for testing).

        Returns:
            The trail after deposit.

        Raises:
            ValueError: If strength is not positive.
        """
        if strength <= 0:
            raise ValueError(
                f"Deposit strength must be positive, got {strength}."
            )

        timestamp = now or datetime.now(timezone.utc)
        key: TrailKey = (action, context)
        existing = self._trails.get(key)

        if existing is not None:
            trail = Trail(
                action=action,
                context=context,
                strength=existing.strength + strength,
                deposit_count=existing.deposit_count + 1,
                last_deposited=timestamp,
            )
        else:
            trail = Trail(
                action=action,
                context=context,
                strength=strength,
                deposit_count=1,
                last_deposited=timestamp,
            )

        self._trails[key] = trail
        return trail

    # ---- Follow (query) ----

    def follow(self, context: str) -> list[Trail]:
        """Follow trails in a context, strongest first.

        Returns trails matching the given context, sorted by strength
        descending.  Tiebreaker: action name ascending [He2025].

        Args:
            context: The context to follow trails in.

        Returns:
            List of Trail objects sorted by (-strength, action).
        """
        matching = [
            trail
            for key, trail in sorted(self._trails.items())
            if trail.context == context
        ]
        return sorted(
            matching,
            key=lambda t: (-t.strength, t.action),
        )

    def get_strength(
        self,
        action: str,
        context: Optional[str] = None,
    ) -> float:
        """Get current strength of a trail.

        If context is provided, returns strength for that specific
        (action, context) pair.  If context is None, returns the
        maximum strength across all contexts for that action.

        Args:
            action: The trail action to query.
            context: Optional specific context.

        Returns:
            Trail strength, or 0.0 if not found.
        """
        if context is not None:
            trail = self._trails.get((action, context))
            return trail.strength if trail is not None else 0.0

        # Max across all contexts for this action [He2025]: sorted iteration
        strengths = [
            trail.strength
            for key, trail in sorted(self._trails.items())
            if trail.action == action
        ]
        return max(strengths) if strengths else 0.0

    def total_strength(self, context: Optional[str] = None) -> float:
        """Sum of all trail strengths, optionally filtered by context.

        Uses Kahan summation for numerical stability per [He2025].

        Args:
            context: If provided, only sum trails in this context.

        Returns:
            Compensated sum of trail strengths.
        """
        acc = KahanAccumulator()
        for key in sorted(self._trails.keys()):
            trail = self._trails[key]
            if context is None or trail.context == context:
                acc.add(trail.strength)
        return acc.total()

    # ---- Introspection ----

    def all_trails(self) -> list[Trail]:
        """Return all trails, sorted by key [He2025].

        Returns:
            List of Trail objects sorted by (action, context).
        """
        return [
            self._trails[key]
            for key in sorted(self._trails.keys())
        ]

    def count(self) -> int:
        """Number of active trails."""
        return len(self._trails)

    # ---- Internal access for DecayEngine ----

    @property
    def _store(self) -> dict[TrailKey, Trail]:
        """Direct access to the trail store (for DecayEngine only)."""
        return self._trails
