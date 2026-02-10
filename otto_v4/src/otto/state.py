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
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> CognitiveState:
        """Load the current cognitive state (or defaults)."""
        conn = self._connect()
        try:
            cur = conn.execute("SELECT key, value FROM cognitive_state")
            rows = {k: v for k, v in cur.fetchall()}
        finally:
            conn.close()

        return CognitiveState(
            energy=rows.get("energy", "medium"),
            burnout=rows.get("burnout", "GREEN"),
            momentum=rows.get("momentum", "cold_start"),
            nudges_sent_today=int(rows.get("nudges_sent_today", "0")),
            nudges_completed_today=int(rows.get("nudges_completed_today", "0")),
            suppressed_count=int(rows.get("suppressed_count", "0")),
        )

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
