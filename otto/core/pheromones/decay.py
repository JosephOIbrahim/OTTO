"""Decay engine for pheromone trails.

Applies exponential half-life decay to trail strengths and prunes
trails that fall below threshold.  Uses Kahan summation when
computing aggregate decay amounts.

Formula::

    new_strength = old_strength * 0.5 ^ (elapsed_hours / half_life_hours)

At ``half_life_hours`` elapsed, strength is halved.  At 2x half-life,
it's quartered.  When strength drops below ``prune_threshold``, the
trail is pruned (removed from the store).

[He2025]: All iterations are in sorted key order.  Decay is
deterministic given the same timestamps and half-life.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from otto.core.determinism.kahan import KahanAccumulator
from otto.core.pheromones.trails import Trail, TrailKey


class DecayEngine:
    """Stateless decay engine for pheromone trails.

    Operates on a trail dict (borrowed from TrailManager).
    Replaces decayed Trail values with new frozen instances
    and deletes pruned entries.

    Args:
        half_life_hours: Time for strength to halve (default 168 = 7 days).
        prune_threshold: Minimum surviving strength (default 0.001).
    """

    def __init__(
        self,
        half_life_hours: float = 168.0,
        prune_threshold: float = 0.001,
    ) -> None:
        if half_life_hours <= 0:
            raise ValueError(
                f"half_life_hours must be positive, got {half_life_hours}."
            )
        if prune_threshold < 0:
            raise ValueError(
                f"prune_threshold must be non-negative, got {prune_threshold}."
            )
        self._half_life_hours = half_life_hours
        self._prune_threshold = prune_threshold

    @property
    def half_life_hours(self) -> float:
        """The configured half-life in hours."""
        return self._half_life_hours

    @property
    def prune_threshold(self) -> float:
        """The minimum strength before a trail is pruned."""
        return self._prune_threshold

    def compute_decay_factor(self, elapsed_hours: float) -> float:
        """Compute the multiplicative decay factor.

        Args:
            elapsed_hours: Hours since last deposit.

        Returns:
            Factor in [0.0, 1.0] to multiply strength by.
            Returns 1.0 if elapsed_hours <= 0 (no decay).
        """
        if elapsed_hours <= 0:
            return 1.0
        return 0.5 ** (elapsed_hours / self._half_life_hours)

    def decay_all(
        self,
        trails: dict[TrailKey, Trail],
        now: Optional[datetime] = None,
    ) -> int:
        """Apply decay to all trails.  Prune below threshold.

        Modifies the dict in place: replaces Trail values with
        decayed versions, deletes pruned entries.  Trail objects
        themselves are frozen — new instances are created.

        [He2025]: Keys are processed in sorted order.

        Args:
            trails: Mutable dict of (action, context) → Trail.
            now: Reference time (default: UTC now).

        Returns:
            Number of trails pruned (removed).
        """
        now = now or datetime.now(timezone.utc)
        to_prune: list[TrailKey] = []

        # [He2025]: Process in deterministic sorted order
        for key in sorted(trails.keys()):
            trail = trails[key]
            elapsed_hours = (
                (now - trail.last_deposited).total_seconds() / 3600.0
            )

            if elapsed_hours <= 0:
                continue

            decay_factor = self.compute_decay_factor(elapsed_hours)
            new_strength = trail.strength * decay_factor

            if new_strength < self._prune_threshold:
                to_prune.append(key)
            else:
                # Replace with decayed version (frozen → new instance).
                # Update last_deposited to `now` so that subsequent
                # decay calls compute incremental elapsed time, not
                # cumulative from the original deposit.  This is the
                # standard approach in physics simulations.
                trails[key] = Trail(
                    action=trail.action,
                    context=trail.context,
                    strength=new_strength,
                    deposit_count=trail.deposit_count,
                    last_deposited=now,
                )

        # Prune dead trails
        for key in to_prune:
            del trails[key]

        return len(to_prune)

    def total_decayed_amount(
        self,
        trails: dict[TrailKey, Trail],
        now: Optional[datetime] = None,
    ) -> float:
        """Compute total strength that WOULD be lost to decay.

        Uses Kahan summation for numerical stability across
        potentially many trails.

        Does NOT modify the trails — this is a read-only query.

        Args:
            trails: Trail dict to analyze.
            now: Reference time (default: UTC now).

        Returns:
            Total strength that would be lost.
        """
        now = now or datetime.now(timezone.utc)
        acc = KahanAccumulator()

        for key in sorted(trails.keys()):
            trail = trails[key]
            elapsed_hours = (
                (now - trail.last_deposited).total_seconds() / 3600.0
            )
            if elapsed_hours <= 0:
                continue

            decay_factor = self.compute_decay_factor(elapsed_hours)
            loss = trail.strength * (1.0 - decay_factor)
            acc.add(loss)

        return acc.total()
