"""Cognitive state tracking for OTTO v5.0.

Tracks energy level, burnout, and momentum so the constitutional layer
can gate outputs appropriately.  Persisted in the same SQLite database
as commitments (separate table).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from .log import get_logger

_log = get_logger(__name__)

# Valid values (used for validation + type hints)
EnergyLevel = Literal["high", "medium", "low", "depleted"]
BurnoutLevel = Literal["GREEN", "YELLOW", "ORANGE", "RED"]
MomentumPhase = Literal["cold_start", "building", "rolling", "peak", "crashed"]

_VALID_ENERGY: set[str] = {"high", "medium", "low", "depleted"}
_VALID_BURNOUT: set[str] = {"GREEN", "YELLOW", "ORANGE", "RED"}
_VALID_MOMENTUM: set[str] = {"cold_start", "building", "rolling", "peak", "crashed"}

_STATE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS cognitive_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_INTERACTION_LOG_SCHEMA = """\
CREATE TABLE IF NOT EXISTS interaction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message_length INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'cli'
);
"""


@dataclass
class CognitiveState:
    """Snapshot of the user's cognitive state.

    Defaults match a healthy baseline — the user shouldn't need to
    configure anything on first run.
    """

    energy: EnergyLevel = "medium"
    burnout: BurnoutLevel = "GREEN"
    momentum: MomentumPhase = "cold_start"
    nudges_sent_today: int = 0
    nudges_completed_today: int = 0
    suppressed_count: int = 0

    @property
    def nudge_effectiveness(self) -> float:
        """Ratio of completed to sent nudges. 1.0 if none sent."""
        if self.nudges_sent_today == 0:
            return 1.0
        return self.nudges_completed_today / self.nudges_sent_today

    @property
    def should_suppress_nudge(self) -> bool:
        """Constitutional check: should outbound nudges be suppressed?"""
        if self.burnout == "RED":
            return True
        if self.burnout == "ORANGE" and self.energy in ("low", "depleted"):
            return True
        if self.nudge_effectiveness < 0.1 and self.nudges_sent_today > 3:
            return True
        return False


class StateStore:
    """Read/write cognitive state from a SQLite database.

    Shares the same database file as CommitmentStore but uses a
    separate ``cognitive_state`` table.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            conn.execute(_STATE_SCHEMA)
            conn.execute(_INTERACTION_LOG_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _set_key(self, key: str, value: str) -> None:
        """Set a single key-value pair in the cognitive_state table."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO cognitive_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
                """,
                (key, value, now, value, now),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> CognitiveState:
        """Load the current cognitive state (or defaults).

        Automatically resets daily counters when the date changes.
        """
        conn = self._connect()
        try:
            cur = conn.execute("SELECT key, value FROM cognitive_state")
            rows = {k: v for k, v in cur.fetchall()}
        finally:
            conn.close()

        # Check for daily rollover
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        last_reset = rows.get("last_reset_date", "")

        state = CognitiveState(
            energy=rows.get("energy", "medium"),
            burnout=rows.get("burnout", "GREEN"),
            momentum=rows.get("momentum", "cold_start"),
            nudges_sent_today=int(rows.get("nudges_sent_today", "0")),
            nudges_completed_today=int(rows.get("nudges_completed_today", "0")),
            suppressed_count=int(rows.get("suppressed_count", "0")),
        )

        if last_reset and last_reset != today:
            state.nudges_sent_today = 0
            state.nudges_completed_today = 0
            state.suppressed_count = 0
            self._set_key("last_reset_date", today)
            self.save(state)
            _log.info("Daily rollover: counters reset for %s", today)
        elif not last_reset:
            # First load ever: record today as last reset date
            self._set_key("last_reset_date", today)

        return state

    def save(self, state: CognitiveState) -> None:
        """Persist the full cognitive state."""
        now = datetime.now(timezone.utc).isoformat()
        pairs = [
            ("energy", state.energy),
            ("burnout", state.burnout),
            ("momentum", state.momentum),
            ("nudges_sent_today", str(state.nudges_sent_today)),
            ("nudges_completed_today", str(state.nudges_completed_today)),
            ("suppressed_count", str(state.suppressed_count)),
        ]
        conn = self._connect()
        try:
            for key, value in pairs:
                conn.execute(
                    """
                    INSERT INTO cognitive_state (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
                    """,
                    (key, value, now, value, now),
                )
            conn.commit()
        finally:
            conn.close()
        _log.debug("Cognitive state saved: energy=%s burnout=%s", state.energy, state.burnout)

    def set_energy(self, level: str) -> CognitiveState:
        """Set energy level. Returns updated state.

        Raises ValueError if level is invalid.
        """
        if level not in _VALID_ENERGY:
            raise ValueError(
                f"Invalid energy level: {level!r}. "
                f"Valid: {sorted(_VALID_ENERGY)}"
            )
        state = self.load()
        state.energy = level  # type: ignore[assignment]
        self.save(state)
        _log.info("Energy set to %s", level)
        return state

    def set_burnout(self, level: str) -> CognitiveState:
        """Set burnout level. Returns updated state.

        Raises ValueError if level is invalid.
        """
        if level not in _VALID_BURNOUT:
            raise ValueError(
                f"Invalid burnout level: {level!r}. "
                f"Valid: {sorted(_VALID_BURNOUT)}"
            )
        state = self.load()
        state.burnout = level  # type: ignore[assignment]
        self.save(state)
        _log.info("Burnout set to %s", level)
        return state

    def set_momentum(self, phase: str) -> CognitiveState:
        """Set momentum phase. Returns updated state.

        Raises ValueError if phase is invalid.
        """
        if phase not in _VALID_MOMENTUM:
            raise ValueError(
                f"Invalid momentum phase: {phase!r}. "
                f"Valid: {sorted(_VALID_MOMENTUM)}"
            )
        state = self.load()
        state.momentum = phase  # type: ignore[assignment]
        self.save(state)
        _log.info("Momentum set to %s", phase)
        return state

    def increment_nudges_sent(self) -> None:
        """Bump nudges_sent_today by 1."""
        state = self.load()
        state.nudges_sent_today += 1
        self.save(state)

    def increment_nudges_completed(self) -> None:
        """Bump nudges_completed_today by 1."""
        state = self.load()
        state.nudges_completed_today += 1
        self.save(state)

    def increment_suppressed(self) -> None:
        """Bump suppressed_count by 1."""
        state = self.load()
        state.suppressed_count += 1
        self.save(state)

    def reset_daily_counters(self) -> None:
        """Reset nudges_sent_today and nudges_completed_today to 0."""
        state = self.load()
        state.nudges_sent_today = 0
        state.nudges_completed_today = 0
        self.save(state)

    # ------------------------------------------------------------------
    # Interaction log (Phase 2.2)
    # ------------------------------------------------------------------

    def log_interaction(
        self,
        message_length: int,
        source: str = "cli",
        timestamp: datetime | None = None,
    ) -> None:
        """Record an interaction for behavioral pattern analysis."""
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO interaction_log (timestamp, message_length, source) VALUES (?, ?, ?)",
                (ts, message_length, source),
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent_interactions(
        self,
        limit: int = 20,
    ) -> list[tuple[str, int, str]]:
        """Return recent interactions as (timestamp_iso, length, source) tuples.

        Sorted by timestamp ascending (oldest first).
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT timestamp, message_length, source FROM interaction_log "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        # Reverse so oldest is first (consistent with HistoryAnalyzer expectation)
        return list(reversed(rows))
