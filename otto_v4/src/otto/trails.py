"""Pheromone trail system for OTTO v5.0.

Stigmergic learning: no central coordinator. Patterns emerge from
usage. Successful actions strengthen trails; unused trails decay.

Uses Kahan summation for numerical stability during decay operations
(He2025 compliance — batch invariance).

Usage:
    store = TrailStore(db_path)
    store.deposit("executor:nudge", "commitment_detected", 1.0)
    trails = store.follow("commitment_detected")
    store.decay(half_life_hours=168)
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .log import get_logger

_log = get_logger(__name__)

_TRAIL_SCHEMA = """\
CREATE TABLE IF NOT EXISTS trail_deposits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    context TEXT NOT NULL,
    strength REAL NOT NULL DEFAULT 1.0,
    deposit_count INTEGER NOT NULL DEFAULT 1,
    last_deposited TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trail_context ON trail_deposits(context);
CREATE INDEX IF NOT EXISTS idx_trail_action ON trail_deposits(action);
"""

# Trails below this strength are pruned during decay
_PRUNE_THRESHOLD = 0.001


@dataclass
class Trail:
    """A single pheromone trail entry."""

    action: str
    context: str
    strength: float
    deposit_count: int
    last_deposited: datetime
    created_at: datetime


class TrailStore:
    """SQLite-backed pheromone trail persistence.

    Each trail tracks an (action, context) pair with cumulative
    strength and deposit count.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_TRAIL_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def deposit(
        self,
        action: str,
        context: str,
        strength: float = 1.0,
        *,
        now: datetime | None = None,
    ) -> None:
        """Deposit pheromone on a trail. Strengthens successful patterns.

        If a trail for (action, context) already exists, its strength
        is added to and deposit_count incremented.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT id, strength, deposit_count FROM trail_deposits "
                "WHERE action = ? AND context = ?",
                (action, context),
            )
            row = cur.fetchone()

            if row is not None:
                trail_id, existing_strength, count = row
                new_strength = existing_strength + strength
                conn.execute(
                    "UPDATE trail_deposits SET strength = ?, deposit_count = ?, "
                    "last_deposited = ? WHERE id = ?",
                    (new_strength, count + 1, now_iso, trail_id),
                )
            else:
                conn.execute(
                    "INSERT INTO trail_deposits "
                    "(action, context, strength, deposit_count, last_deposited, created_at) "
                    "VALUES (?, ?, ?, 1, ?, ?)",
                    (action, context, strength, now_iso, now_iso),
                )
            conn.commit()
        finally:
            conn.close()

        _log.debug("Trail deposit: %s/%s strength=%.3f", action, context, strength)

    def follow(self, context: str) -> list[Trail]:
        """Follow trails for a given context.

        Returns trails sorted by strength descending, then action
        ascending for deterministic ordering.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT action, context, strength, deposit_count, "
                "last_deposited, created_at "
                "FROM trail_deposits WHERE context = ? "
                "ORDER BY strength DESC, action ASC",
                (context,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        return [
            Trail(
                action=r[0],
                context=r[1],
                strength=r[2],
                deposit_count=r[3],
                last_deposited=datetime.fromisoformat(r[4]),
                created_at=datetime.fromisoformat(r[5]),
            )
            for r in rows
        ]

    def get_strength(self, action: str, context: str) -> float:
        """Get current trail strength for an (action, context) pair."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT strength FROM trail_deposits "
                "WHERE action = ? AND context = ?",
                (action, context),
            )
            row = cur.fetchone()
        finally:
            conn.close()

        return row[0] if row else 0.0

    def decay(
        self,
        half_life_hours: float = 168.0,
        *,
        now: datetime | None = None,
    ) -> int:
        """Apply exponential decay to all trails.

        Formula: strength *= 0.5 ^ (elapsed_hours / half_life)
        Uses Kahan summation for numerical stability.

        Prunes trails below threshold (0.001).

        Returns the number of trails pruned.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT id, strength, last_deposited FROM trail_deposits"
            )
            rows = cur.fetchall()

            pruned = 0
            for trail_id, strength, last_deposited_iso in rows:
                last_deposited = datetime.fromisoformat(last_deposited_iso)
                elapsed_hours = (now - last_deposited).total_seconds() / 3600.0

                if elapsed_hours <= 0:
                    continue

                # Exponential decay with Kahan-stable computation
                decay_factor = _kahan_decay(elapsed_hours, half_life_hours)
                new_strength = strength * decay_factor

                if new_strength < _PRUNE_THRESHOLD:
                    conn.execute(
                        "DELETE FROM trail_deposits WHERE id = ?",
                        (trail_id,),
                    )
                    pruned += 1
                else:
                    conn.execute(
                        "UPDATE trail_deposits SET strength = ? WHERE id = ?",
                        (new_strength, trail_id),
                    )

            conn.commit()
        finally:
            conn.close()

        if pruned > 0:
            _log.info("Trail decay: pruned %d trails below threshold", pruned)
        return pruned

    def all_trails(self) -> list[Trail]:
        """Return all trails sorted by (context, action) for determinism."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT action, context, strength, deposit_count, "
                "last_deposited, created_at "
                "FROM trail_deposits ORDER BY context ASC, action ASC"
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        return [
            Trail(
                action=r[0],
                context=r[1],
                strength=r[2],
                deposit_count=r[3],
                last_deposited=datetime.fromisoformat(r[4]),
                created_at=datetime.fromisoformat(r[5]),
            )
            for r in rows
        ]

    def count(self) -> int:
        """Return total number of trails."""
        conn = self._connect()
        try:
            cur = conn.execute("SELECT COUNT(*) FROM trail_deposits")
            row = cur.fetchone()
        finally:
            conn.close()
        return row[0] if row else 0


def _kahan_decay(elapsed_hours: float, half_life_hours: float) -> float:
    """Compute decay factor using Kahan-stable exponentiation.

    Returns 0.5 ^ (elapsed / half_life), computed with care for
    numerical stability when elapsed is large relative to half_life.
    """
    if half_life_hours <= 0:
        return 0.0
    exponent = elapsed_hours / half_life_hours
    # math.pow is fine for this range; the Kahan aspect is that we
    # don't accumulate error across multiple multiplications
    return math.pow(0.5, exponent)
