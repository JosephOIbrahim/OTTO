"""SQLite commitment store for OTTO v4.0.

Uses stdlib sqlite3 only. No ORM. Datetimes stored as ISO strings.
Opens and closes connection per operation (no pooling).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from otto.models import Commitment

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS commitments (
    id TEXT PRIMARY KEY,
    raw_message TEXT NOT NULL,
    commitment_text TEXT NOT NULL,
    who_to TEXT NOT NULL,
    who_from TEXT NOT NULL DEFAULT 'me',
    direction TEXT NOT NULL DEFAULT 'outbound',
    deadline TEXT,
    deadline_source TEXT NOT NULL DEFAULT 'none',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    follow_up_count INTEGER NOT NULL DEFAULT 0,
    source_chat TEXT NOT NULL DEFAULT 'unknown',
    snoozed_until TEXT,
    notes TEXT NOT NULL DEFAULT ''
);
"""


class CommitmentStore:
    """Persistent store for commitments backed by SQLite."""

    def __init__(self, db_path: str = "~/.otto/commitments.db") -> None:
        expanded = os.path.expanduser(db_path)
        self._db_path = Path(expanded)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a new connection. Caller must close it."""
        return sqlite3.connect(str(self._db_path))

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            conn.execute(_SCHEMA)
            # Migrate existing DBs: add new columns if missing
            cursor = conn.execute("PRAGMA table_info(commitments)")
            columns = {row[1] for row in cursor.fetchall()}
            if "snoozed_until" not in columns:
                conn.execute(
                    "ALTER TABLE commitments ADD COLUMN snoozed_until TEXT"
                )
            if "notes" not in columns:
                conn.execute(
                    "ALTER TABLE commitments ADD COLUMN notes TEXT NOT NULL DEFAULT ''"
                )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _row_to_commitment(row: tuple) -> Commitment:
        """Map a SELECT * row to a Commitment instance.

        Column order matches _SCHEMA:
            id, raw_message, commitment_text, who_to, who_from,
            direction, deadline, deadline_source, status,
            created_at, updated_at, follow_up_count, source_chat,
            snoozed_until, notes
        """
        (
            id_,
            raw_message,
            commitment_text,
            who_to,
            who_from,
            direction,
            deadline_str,
            deadline_source,
            status,
            created_at_str,
            updated_at_str,
            follow_up_count,
            source_chat,
            snoozed_until_str,
            notes,
        ) = row

        deadline = (
            datetime.fromisoformat(deadline_str) if deadline_str else None
        )
        snoozed_until = (
            datetime.fromisoformat(snoozed_until_str)
            if snoozed_until_str
            else None
        )

        return Commitment(
            id=id_,
            raw_message=raw_message,
            commitment_text=commitment_text,
            who_to=who_to,
            who_from=who_from,
            direction=direction,
            deadline=deadline,
            deadline_source=deadline_source,
            status=status,
            created_at=datetime.fromisoformat(created_at_str),
            updated_at=datetime.fromisoformat(updated_at_str),
            follow_up_count=follow_up_count,
            source_chat=source_chat,
            snoozed_until=snoozed_until,
            notes=notes or "",
        )

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, commitment: Commitment) -> str:
        """Insert a commitment. Returns its ID."""
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO commitments (
                    id, raw_message, commitment_text, who_to, who_from,
                    direction, deadline, deadline_source, status,
                    created_at, updated_at, follow_up_count, source_chat,
                    snoozed_until, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commitment.id,
                    commitment.raw_message,
                    commitment.commitment_text,
                    commitment.who_to,
                    commitment.who_from,
                    commitment.direction,
                    commitment.deadline.isoformat() if commitment.deadline else None,
                    commitment.deadline_source,
                    commitment.status,
                    commitment.created_at.isoformat(),
                    commitment.updated_at.isoformat(),
                    commitment.follow_up_count,
                    commitment.source_chat,
                    commitment.snoozed_until.isoformat() if commitment.snoozed_until else None,
                    commitment.notes,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return commitment.id

    def get(self, commitment_id: str) -> Commitment | None:
        """Retrieve a commitment by ID. Returns None if not found."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT * FROM commitments WHERE id = ?",
                (commitment_id,),
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_commitment(row)

    def get_active(self) -> list[Commitment]:
        """Return active commitments ordered by deadline (NULLs last)."""
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                SELECT * FROM commitments
                WHERE status = 'active'
                ORDER BY
                    CASE WHEN deadline IS NULL THEN 1 ELSE 0 END,
                    deadline ASC,
                    id ASC
                """
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [self._row_to_commitment(r) for r in rows]

    def get_due(self, as_of: datetime | None = None) -> list[Commitment]:
        """Return active commitments whose deadline has passed."""
        if as_of is None:
            as_of = datetime.now(timezone.utc)
        cutoff = as_of.isoformat()
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                SELECT * FROM commitments
                WHERE status = 'active'
                  AND deadline IS NOT NULL
                  AND deadline <= ?
                  AND (snoozed_until IS NULL OR snoozed_until <= ?)
                ORDER BY deadline ASC, id ASC
                """,
                (cutoff, now_iso),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [self._row_to_commitment(r) for r in rows]

    def get_stale(self, days: int = 3) -> list[Commitment]:
        """Return active commitments with no deadline older than *days*."""
        from datetime import timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                SELECT * FROM commitments
                WHERE status = 'active'
                  AND deadline IS NULL
                  AND created_at <= ?
                  AND (snoozed_until IS NULL OR snoozed_until <= ?)
                ORDER BY created_at ASC, id ASC
                """,
                (cutoff, now_iso),
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [self._row_to_commitment(r) for r in rows]

    def mark_done(self, commitment_id: str) -> None:
        """Set status to 'done' and update updated_at."""
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE commitments
                SET status = 'done', updated_at = ?
                WHERE id = ?
                """,
                (self._utcnow_iso(), commitment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_parked(self, commitment_id: str) -> None:
        """Set status to 'parked' and update updated_at."""
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE commitments
                SET status = 'parked', updated_at = ?
                WHERE id = ?
                """,
                (self._utcnow_iso(), commitment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def increment_follow_up(self, commitment_id: str) -> None:
        """Bump follow_up_count by 1 and update updated_at."""
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE commitments
                SET follow_up_count = follow_up_count + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (self._utcnow_iso(), commitment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def snooze(self, commitment_id: str, until: datetime) -> None:
        """Snooze a commitment until a given time."""
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE commitments
                SET snoozed_until = ?, updated_at = ?
                WHERE id = ?
                """,
                (until.isoformat(), self._utcnow_iso(), commitment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def unsnooze(self, commitment_id: str) -> None:
        """Clear the snooze on a commitment."""
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE commitments
                SET snoozed_until = NULL, updated_at = ?
                WHERE id = ?
                """,
                (self._utcnow_iso(), commitment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def add_note(self, commitment_id: str, text: str) -> None:
        """Append a note to a commitment. Notes are newline-separated."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT notes FROM commitments WHERE id = ?",
                (commitment_id,),
            )
            row = cur.fetchone()
            if row is None:
                return
            existing = row[0] or ""
            new_notes = f"{existing}\n{text}".strip() if existing else text
            conn.execute(
                """
                UPDATE commitments
                SET notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_notes, self._utcnow_iso(), commitment_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, commitment_id: str) -> None:
        """Hard-delete a commitment."""
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM commitments WHERE id = ?",
                (commitment_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def count(self) -> dict[str, int]:
        """Return commitment counts grouped by status."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT status, COUNT(*) FROM commitments GROUP BY status"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return {status: cnt for status, cnt in rows}

    def get_all(self) -> list[Commitment]:
        """Return all commitments regardless of status, newest first."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT * FROM commitments ORDER BY created_at DESC, id DESC"
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        return [self._row_to_commitment(r) for r in rows]

    def avg_follow_ups_done(self) -> float | None:
        """Return average follow_up_count across done commitments, or None."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT AVG(follow_up_count) FROM commitments WHERE status = 'done'"
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if row is None or row[0] is None:
            return None
        return row[0]

    def nuke(self) -> None:
        """Drop and recreate the commitments table."""
        conn = self._connect()
        try:
            conn.execute("DROP TABLE IF EXISTS commitments")
            conn.execute(_SCHEMA)
            conn.commit()
        finally:
            conn.close()
