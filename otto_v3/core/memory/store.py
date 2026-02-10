"""SQLite persistence backend for cognitive memory.

Uses one table per MemoryType for physical isolation. Content and
metadata are JSON-serialized. All list operations return sorted
results for determinism.

This store will be wrapped with encryption in Day 6 (AES-256-GCM).
For now it stores plaintext SQLite — no cognitive data should be
committed to version control.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from otto_v3.core.memory.types import MemoryEntry, MemoryType


class SQLiteStore:
    """Low-level SQLite storage for cognitive memories.

    Each MemoryType gets its own table. The store handles serialization
    (JSON for content/metadata) and provides deterministic query results
    (ORDER BY key for).

    Args:
        db_path: Path to the SQLite database file. Use ":memory:" for
            in-memory databases (useful for testing).
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(
            self._db_path,
            # Detect types so we get proper Python types back
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()

    def _init_tables(self) -> None:
        """Create tables for all memory types if they don't exist."""
        for memory_type in sorted(MemoryType, key=lambda t: t.name):
            table = memory_type.table_name
            self._conn.execute(f"""
                CREATE TABLE IF NOT EXISTS [{table}] (
                    key TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)
        self._conn.commit()

    # ---- CRUD operations ----

    def get(
        self, memory_type: MemoryType, key: str
    ) -> Optional[MemoryEntry]:
        """Retrieve a single memory entry.

        Args:
            memory_type: Which memory table to query.
            key: The entry's unique key.

        Returns:
            MemoryEntry if found, None otherwise.
        """
        table = memory_type.table_name
        cursor = self._conn.execute(
            f"SELECT key, content, created_at, updated_at, metadata "
            f"FROM [{table}] WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entry(memory_type, row)

    def put(
        self,
        memory_type: MemoryType,
        key: str,
        content: Any,
        metadata: Optional[dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        """Store or update a memory entry (upsert).

        If the key exists, updates content/metadata/updated_at.
        If new, creates with current timestamp.

        Args:
            memory_type: Which memory table to write to.
            key: The entry's unique key.
            content: JSON-serializable data to store.
            metadata: Optional metadata dict.
            created_at: Override creation timestamp (for migrations).
        """
        table = memory_type.table_name
        now = datetime.now(timezone.utc).isoformat()
        created = created_at.isoformat() if created_at else now
        content_json = json.dumps(content, sort_keys=True)
        metadata_json = json.dumps(
            metadata, sort_keys=True
        ) if metadata else None

        # Check if key exists to preserve created_at on update
        existing = self.get(memory_type, key)
        if existing is not None:
            # Update: preserve original created_at
            self._conn.execute(
                f"UPDATE [{table}] SET content = ?, updated_at = ?, "
                f"metadata = ? WHERE key = ?",
                (content_json, now, metadata_json, key),
            )
        else:
            # Insert: new entry
            self._conn.execute(
                f"INSERT INTO [{table}] (key, content, created_at, "
                f"updated_at, metadata) VALUES (?, ?, ?, ?, ?)",
                (key, content_json, created, now, metadata_json),
            )
        self._conn.commit()

    def delete(self, memory_type: MemoryType, key: str) -> bool:
        """Delete a memory entry.

        Args:
            memory_type: Which memory table.
            key: The entry to delete.

        Returns:
            True if an entry was deleted, False if key didn't exist.
        """
        table = memory_type.table_name
        cursor = self._conn.execute(
            f"DELETE FROM [{table}] WHERE key = ?", (key,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def list_keys(self, memory_type: MemoryType) -> list[str]:
        """List all keys for a memory type.

        Returns sorted list for determinism.

        Args:
            memory_type: Which memory table to list.

        Returns:
            Sorted list of key strings.
        """
        table = memory_type.table_name
        cursor = self._conn.execute(
            f"SELECT key FROM [{table}] ORDER BY key ASC"
        )
        return [row[0] for row in cursor.fetchall()]

    def count(self, memory_type: MemoryType) -> int:
        """Count entries in a memory type.

        Args:
            memory_type: Which memory table to count.

        Returns:
            Number of entries.
        """
        table = memory_type.table_name
        cursor = self._conn.execute(
            f"SELECT COUNT(*) FROM [{table}]"
        )
        return cursor.fetchone()[0]

    def clear(self, memory_type: MemoryType) -> int:
        """Delete all entries from a memory type.

        Useful for clearing contextual (session) memory on restart.

        Args:
            memory_type: Which memory table to clear.

        Returns:
            Number of entries deleted.
        """
        table = memory_type.table_name
        cursor = self._conn.execute(f"DELETE FROM [{table}]")
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ---- Internal helpers ----

    @staticmethod
    def _row_to_entry(
        memory_type: MemoryType,
        row: tuple,
    ) -> MemoryEntry:
        """Convert a database row to a MemoryEntry."""
        key, content_json, created_str, updated_str, metadata_json = row
        return MemoryEntry(
            key=key,
            memory_type=memory_type,
            content=json.loads(content_json),
            created_at=datetime.fromisoformat(created_str),
            updated_at=datetime.fromisoformat(updated_str),
            metadata=json.loads(metadata_json) if metadata_json else {},
        )
