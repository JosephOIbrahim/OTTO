"""SQLite commitment store for OTTO v4.0.

Uses stdlib sqlite3 only. No ORM. Datetimes stored as ISO strings.
Connection management delegated to the centralized Database class.
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
    notes TEXT NOT NULL DEFAULT '',
    sender_phone TEXT
);
"""


class CommitmentStore:
    """Persistent store for commitments backed by SQLite."""

    def __init__(
        self,
        db_path: str = "~/.otto/commitments.db",
        *,
        db: "Database | None" = None,
        encryption_key: bytes | None = None,
    ) -> None:
        if db is not None:
            self._db = db
        else:
            from .db import Database
            self._db = Database(db_path)
        self._encryption_key = encryption_key
        self._ensure_table()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_table(self) -> None:
        with self._db.connect() as conn:
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
            # Migration: add sender_phone column
            if "sender_phone" not in columns:
                conn.execute(
                    "ALTER TABLE commitments ADD COLUMN sender_phone TEXT"
                )
            # Migration: add is_encrypted flag for at-rest encryption
            if "is_encrypted" not in columns:
                conn.execute(
                    "ALTER TABLE commitments "
                    "ADD COLUMN is_encrypted INTEGER NOT NULL DEFAULT 0"
                )
            # Performance indices for common query patterns
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_commitments_status "
                "ON commitments(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_commitments_deadline "
                "ON commitments(deadline)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_commitments_created_at "
                "ON commitments(created_at)"
            )

    def _row_to_commitment(self, row: tuple) -> Commitment:
        """Map a SELECT * row to a Commitment instance.

        Column order matches _SCHEMA + migrations:
            0  id, 1 raw_message, 2 commitment_text, 3 who_to, 4 who_from,
            5  direction, 6 deadline, 7 deadline_source, 8 status,
            9  created_at, 10 updated_at, 11 follow_up_count, 12 source_chat,
            13 snoozed_until, 14 notes, 15 sender_phone, 16 is_encrypted
        """
        id_ = row[0]
        raw_message = row[1]
        commitment_text = row[2]
        who_to = row[3]
        who_from = row[4]
        direction = row[5]
        deadline_str = row[6]
        deadline_source = row[7]
        status = row[8]
        created_at_str = row[9]
        updated_at_str = row[10]
        follow_up_count = row[11]
        source_chat = row[12]
        snoozed_until_str = row[13]
        notes = row[14]
        sender_phone = row[15]
        # is_encrypted may be absent for very old DBs (pre-migration)
        is_encrypted = row[16] if len(row) > 16 else 0

        # Decrypt sensitive fields when the row is encrypted and we have a key
        if is_encrypted and self._encryption_key:
            from otto.crypto import decrypt_field

            raw_message = decrypt_field(raw_message, self._encryption_key)
            commitment_text = decrypt_field(
                commitment_text, self._encryption_key
            )
            who_to = decrypt_field(who_to, self._encryption_key)
            source_chat = decrypt_field(source_chat, self._encryption_key)
            sender_phone = decrypt_field(
                sender_phone or "", self._encryption_key
            ) or None

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
            sender_phone=sender_phone,
            snoozed_until=snoozed_until,
            notes=notes or "",
        )

    @staticmethod
    def _utcnow_iso() -> str:
        """Wall-clock timestamp for write operations (boundary call).

        Not injected because updated_at should always reflect real time,
        not test time.
        """
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(self, commitment: Commitment) -> bool:
        """Check if a near-identical commitment already exists (active)."""
        with self._db.connect() as conn:
            # Check by normalized commitment text + who_to + source_chat
            cur = conn.execute(
                """
                SELECT COUNT(*) FROM commitments
                WHERE status = 'active'
                  AND LOWER(TRIM(commitment_text)) = LOWER(TRIM(?))
                  AND LOWER(TRIM(who_to)) = LOWER(TRIM(?))
                  AND LOWER(TRIM(source_chat)) = LOWER(TRIM(?))
                """,
                (commitment.commitment_text, commitment.who_to, commitment.source_chat),
            )
            count = cur.fetchone()[0]
        return count > 0

    def add(self, commitment: Commitment, *, dedup: bool = True) -> str:
        """Insert a commitment. Returns its ID.

        If dedup=True (default), skips insertion if a near-identical
        active commitment already exists. Returns empty string on skip.
        """
        if dedup and self.is_duplicate(commitment):
            return ""

        # Prepare field values -- encrypt sensitive fields if key is set
        if self._encryption_key:
            from otto.crypto import encrypt_field

            raw_message = encrypt_field(commitment.raw_message, self._encryption_key)
            commitment_text = encrypt_field(
                commitment.commitment_text, self._encryption_key
            )
            who_to = encrypt_field(commitment.who_to, self._encryption_key)
            source_chat = encrypt_field(commitment.source_chat, self._encryption_key)
            sender_phone = encrypt_field(
                commitment.sender_phone or "", self._encryption_key
            )
            is_encrypted = 1
        else:
            raw_message = commitment.raw_message
            commitment_text = commitment.commitment_text
            who_to = commitment.who_to
            source_chat = commitment.source_chat
            sender_phone = commitment.sender_phone
            is_encrypted = 0

        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO commitments (
                    id, raw_message, commitment_text, who_to, who_from,
                    direction, deadline, deadline_source, status,
                    created_at, updated_at, follow_up_count, source_chat,
                    snoozed_until, notes, sender_phone, is_encrypted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commitment.id,
                    raw_message,
                    commitment_text,
                    who_to,
                    commitment.who_from,
                    commitment.direction,
                    commitment.deadline.isoformat() if commitment.deadline else None,
                    commitment.deadline_source,
                    commitment.status,
                    commitment.created_at.isoformat(),
                    commitment.updated_at.isoformat(),
                    commitment.follow_up_count,
                    source_chat,
                    commitment.snoozed_until.isoformat() if commitment.snoozed_until else None,
                    commitment.notes,
                    sender_phone,
                    is_encrypted,
                ),
            )
        return commitment.id

    def get(self, commitment_id: str) -> Commitment | None:
        """Retrieve a commitment by ID. Returns None if not found."""
        with self._db.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM commitments WHERE id = ?",
                (commitment_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_commitment(row)

    def get_active(self) -> list[Commitment]:
        """Return active commitments ordered by deadline (NULLs last)."""
        with self._db.connect() as conn:
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
        return [self._row_to_commitment(r) for r in rows]

    def get_due(self, as_of: datetime | None = None) -> list[Commitment]:
        """Return active commitments whose deadline has passed."""
        if as_of is None:
            as_of = datetime.now(timezone.utc)
        cutoff = as_of.isoformat()
        now_iso = as_of.isoformat()  # determinism: use as_of, not a second wall-clock call
        with self._db.connect() as conn:
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
        return [self._row_to_commitment(r) for r in rows]

    def get_stale(self, days: int = 3, *, now: datetime | None = None) -> list[Commitment]:
        """Return active commitments with no deadline older than *days*."""
        from datetime import timedelta

        if now is None:
            now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=days)).isoformat()
        now_iso = now.isoformat()
        with self._db.connect() as conn:
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
        return [self._row_to_commitment(r) for r in rows]

    def mark_done(self, commitment_id: str) -> None:
        """Set status to 'done' and update updated_at."""
        with self._db.connect() as conn:
            conn.execute(
                """
                UPDATE commitments
                SET status = 'done', updated_at = ?
                WHERE id = ?
                """,
                (self._utcnow_iso(), commitment_id),
            )

    def mark_parked(self, commitment_id: str) -> None:
        """Set status to 'parked' and update updated_at."""
        with self._db.connect() as conn:
            conn.execute(
                """
                UPDATE commitments
                SET status = 'parked', updated_at = ?
                WHERE id = ?
                """,
                (self._utcnow_iso(), commitment_id),
            )

    def increment_follow_up(self, commitment_id: str) -> None:
        """Bump follow_up_count by 1 and update updated_at."""
        with self._db.connect() as conn:
            conn.execute(
                """
                UPDATE commitments
                SET follow_up_count = follow_up_count + 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (self._utcnow_iso(), commitment_id),
            )

    def snooze(self, commitment_id: str, until: datetime) -> None:
        """Snooze a commitment until a given time."""
        with self._db.connect() as conn:
            conn.execute(
                """
                UPDATE commitments
                SET snoozed_until = ?, updated_at = ?
                WHERE id = ?
                """,
                (until.isoformat(), self._utcnow_iso(), commitment_id),
            )

    def unsnooze(self, commitment_id: str) -> None:
        """Clear the snooze on a commitment."""
        with self._db.connect() as conn:
            conn.execute(
                """
                UPDATE commitments
                SET snoozed_until = NULL, updated_at = ?
                WHERE id = ?
                """,
                (self._utcnow_iso(), commitment_id),
            )

    def add_note(self, commitment_id: str, text: str) -> None:
        """Append a note to a commitment. Notes are newline-separated."""
        with self._db.connect() as conn:
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

    def delete(self, commitment_id: str) -> None:
        """Hard-delete a commitment."""
        with self._db.connect() as conn:
            conn.execute(
                "DELETE FROM commitments WHERE id = ?",
                (commitment_id,),
            )

    def count(self) -> dict[str, int]:
        """Return commitment counts grouped by status."""
        with self._db.connect() as conn:
            cur = conn.execute(
                "SELECT status, COUNT(*) FROM commitments GROUP BY status"
            )
            rows = cur.fetchall()
        return {status: cnt for status, cnt in rows}

    def get_all(self) -> list[Commitment]:
        """Return all commitments regardless of status, newest first."""
        with self._db.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM commitments ORDER BY created_at DESC, id DESC"
            )
            rows = cur.fetchall()
        return [self._row_to_commitment(r) for r in rows]

    def avg_follow_ups_done(self) -> float | None:
        """Return average follow_up_count across done commitments, or None."""
        with self._db.connect() as conn:
            cur = conn.execute(
                "SELECT AVG(follow_up_count) FROM commitments WHERE status = 'done'"
            )
            row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return row[0]

    def nuke(self) -> None:
        """Drop and recreate the commitments table."""
        with self._db.connect() as conn:
            conn.execute("DROP TABLE IF EXISTS commitments")
            conn.execute(_SCHEMA)
        # Re-run migrations so is_encrypted column etc. exist immediately
        self._ensure_table()
