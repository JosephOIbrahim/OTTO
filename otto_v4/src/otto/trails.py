"""Trail-based preference learning for OTTO v5.0.

Successful actions strengthen trails; unused trails decay.
Uses exponential decay for trail strength reduction over time.

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
CREATE TABLE IF NOT EXISTS mode_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    context TEXT NOT NULL,
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcomes_mode ON mode_outcomes(mode);
"""

# Trails below this strength are pruned during decay
_PRUNE_THRESHOLD = 0.001


@dataclass
class Trail:
    """A single outcome trail entry."""

    action: str
    context: str
    strength: float
    deposit_count: int
    last_deposited: datetime
    created_at: datetime


class TrailStore:
    """SQLite-backed outcome trail persistence.

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
            conn.execute("PRAGMA journal_mode=WAL")
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
        """Record an outcome on a trail. Strengthens successful patterns.

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
        Uses exponential half-life decay.

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

                # Exponential half-life decay
                decay_factor = _exponential_decay(elapsed_hours, half_life_hours)
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

    # ------------------------------------------------------------------
    # Mode outcome tracking
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        mode: str,
        context: str,
        outcome: str,
        *,
        now: datetime | None = None,
    ) -> None:
        """Record a mode outcome (success, ignored, mixed, activated)."""
        if now is None:
            now = datetime.now(timezone.utc)
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO mode_outcomes (mode, context, outcome, created_at) "
                "VALUES (?, ?, ?, ?)",
                (mode, context, outcome, now.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
        _log.debug("Outcome recorded: %s/%s -> %s", mode, context, outcome)

    def get_mode_stats(self, mode: str) -> dict[str, int]:
        """Return {outcome: count, ..., 'total': N} for a mode."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT outcome, COUNT(*) FROM mode_outcomes "
                "WHERE mode = ? GROUP BY outcome ORDER BY outcome",
                (mode,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        stats: dict[str, int] = {}
        total = 0
        for outcome, count in rows:
            stats[outcome] = count
            total += count
        stats["total"] = total
        return stats

    def get_success_rate(self, mode: str) -> float | None:
        """Return success / total for a mode. None if no data."""
        stats = self.get_mode_stats(mode)
        total = stats.get("total", 0)
        if total == 0:
            return None
        return stats.get("success", 0) / total

    def get_total_outcomes(self) -> int:
        """Return total outcome count across all modes."""
        conn = self._connect()
        try:
            cur = conn.execute("SELECT COUNT(*) FROM mode_outcomes")
            row = cur.fetchone()
        finally:
            conn.close()
        return row[0] if row else 0

    def get_all_modes(self) -> list[str]:
        """Return all mode names that have recorded outcomes, sorted."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT DISTINCT mode FROM mode_outcomes ORDER BY mode"
            )
            result = [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
        return result

    def prune_outcomes(
        self,
        max_age_days: int = 30,
        *,
        now: datetime | None = None,
    ) -> int:
        """Delete outcomes older than max_age_days.

        Returns the number of rows deleted.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff = (now - timedelta(days=max_age_days)).isoformat()

        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM mode_outcomes WHERE created_at < ?",
                (cutoff,),
            )
            deleted = cur.rowcount
            conn.commit()
        finally:
            conn.close()

        if deleted > 0:
            _log.info("Outcome pruning: removed %d outcomes older than %d days", deleted, max_age_days)
        return deleted

    def nuke(self) -> None:
        """Drop and recreate trail_deposits and mode_outcomes tables."""
        conn = self._connect()
        try:
            conn.execute("DELETE FROM trail_deposits")
            conn.execute("DELETE FROM mode_outcomes")
            conn.commit()
        finally:
            conn.close()
        _log.info("All trail and outcome data deleted")


def _exponential_decay(elapsed_hours: float, half_life_hours: float) -> float:
    """Compute exponential decay factor for trail strength.

    Returns 0.5 ^ (elapsed / half_life), computed with care for
    numerical stability when elapsed is large relative to half_life.
    """
    if half_life_hours <= 0:
        return 0.0
    exponent = elapsed_hours / half_life_hours
    # Single exponential: no accumulation, so no compensation needed
    return math.pow(0.5, exponent)
