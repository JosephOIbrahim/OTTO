"""Memory manager — public API with read-before-write invariant.

The MemoryManager wraps SQLiteStore and enforces two critical
invariants:

1. **Read-before-write:** Every write() call requires that the key
   was previously read() in the current session. This prevents blind
   overwrites of cognitive data. You must acknowledge the current
   state before modifying it.

2. **Identity isolation:** Identity memories are never included in
   bulk exports or sync operations. They can only be accessed through
   explicit, type-specific calls.

The manager tracks read keys per-session (in memory). A new manager
instance starts with no keys marked as read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from otto.core.memory.store import SQLiteStore
from otto.core.memory.types import MemoryEntry, MemoryType


class ReadBeforeWriteViolation(Exception):
    """Raised when write() is called on a key that hasn't been read().

    This is a programming error — the caller must read the current
    state before modifying it. This prevents blind overwrites of
    cognitive data.
    """


class MemoryManager:
    """High-level cognitive memory manager.

    Wraps SQLiteStore with safety invariants. All memory operations
    go through this class — never access the store directly.

    Args:
        db_path: Path to the SQLite database file. Use ":memory:" for
            in-memory databases (testing).
        store: Optional pre-configured SQLiteStore (for dependency
            injection in tests).
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        store: SQLiteStore | None = None,
    ) -> None:
        self._store = store or SQLiteStore(db_path)
        # Session-level read tracking: memory_type → set of read keys
        # [He2025]: dict keyed by enum, sets used only for membership
        self._read_keys: dict[MemoryType, set[str]] = {
            t: set() for t in sorted(MemoryType, key=lambda t: t.name)
        }

    # ---- Read operations (always safe) ----

    def read(
        self, memory_type: MemoryType, key: str
    ) -> Optional[MemoryEntry]:
        """Read a memory entry and mark it as read for write access.

        This is the primary read path. It marks the key as "read" in
        the current session, which is required before any write or
        delete to that key.

        Args:
            memory_type: Which memory category.
            key: The entry's unique key.

        Returns:
            MemoryEntry if found, None if the key doesn't exist.
        """
        self._read_keys[memory_type].add(key)
        return self._store.get(memory_type, key)

    def list_keys(self, memory_type: MemoryType) -> list[str]:
        """List all keys for a memory type.

        Returns sorted list for [He2025] determinism. Does NOT mark
        keys as read — you must still call read() on individual keys
        before writing them.

        Args:
            memory_type: Which memory category.

        Returns:
            Sorted list of key strings.
        """
        return self._store.list_keys(memory_type)

    def count(self, memory_type: MemoryType) -> int:
        """Count entries in a memory type."""
        return self._store.count(memory_type)

    def exists(self, memory_type: MemoryType, key: str) -> bool:
        """Check if a key exists. Does NOT count as a read.

        To write, you must still call read() first.
        """
        return self._store.get(memory_type, key) is not None

    # ---- Write operations (require prior read) ----

    def write(
        self,
        memory_type: MemoryType,
        key: str,
        content: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Write a memory entry. Key MUST have been read() first.

        The read-before-write invariant ensures you acknowledge the
        current state before modifying it. To create a new entry:
        call read(key) first (returns None), then write(key, content).

        Args:
            memory_type: Which memory category.
            key: The entry's unique key.
            content: JSON-serializable data to store.
            metadata: Optional metadata dict.

        Raises:
            ReadBeforeWriteViolation: If key was not previously read().
        """
        if key not in self._read_keys[memory_type]:
            raise ReadBeforeWriteViolation(
                f"Key '{key}' in {memory_type.name} must be read() "
                f"before write(). This prevents blind overwrites of "
                f"cognitive data."
            )
        self._store.put(memory_type, key, content, metadata)

    def delete(
        self, memory_type: MemoryType, key: str
    ) -> bool:
        """Delete a memory entry. Key MUST have been read() first.

        Args:
            memory_type: Which memory category.
            key: The entry to delete.

        Returns:
            True if entry was deleted, False if it didn't exist.

        Raises:
            ReadBeforeWriteViolation: If key was not previously read().
        """
        if key not in self._read_keys[memory_type]:
            raise ReadBeforeWriteViolation(
                f"Key '{key}' in {memory_type.name} must be read() "
                f"before delete()."
            )
        return self._store.delete(memory_type, key)

    # ---- Session management ----

    def clear_contextual(self) -> int:
        """Clear all contextual (session-scoped) memory.

        Called on session restart. Contextual memory is ephemeral —
        it exists only for the current session.

        Returns:
            Number of entries cleared.
        """
        count = self._store.clear(MemoryType.CONTEXTUAL)
        self._read_keys[MemoryType.CONTEXTUAL].clear()
        return count

    def reset_read_tracking(self) -> None:
        """Reset the read-before-write tracking for a new session.

        After calling this, all keys must be re-read before writing.
        Call this at the start of each session.
        """
        for memory_type in sorted(
            self._read_keys.keys(), key=lambda t: t.name
        ):
            self._read_keys[memory_type].clear()

    # ---- Identity isolation ----

    def export_syncable(self) -> dict[str, list[MemoryEntry]]:
        """Export all syncable memories (EXCLUDES identity).

        Identity memory is NEVER included in exports — this is
        constitutional (privacy_is_law principle).

        Returns:
            Dict of memory_type.name → list of MemoryEntry, sorted
            by type name then key for [He2025].
        """
        result: dict[str, list[MemoryEntry]] = {}
        for memory_type in sorted(MemoryType, key=lambda t: t.name):
            if not memory_type.syncable:
                continue
            keys = self._store.list_keys(memory_type)
            entries = []
            for key in keys:  # Already sorted by store
                entry = self._store.get(memory_type, key)
                if entry is not None:
                    entries.append(entry)
            result[memory_type.name] = entries
        return result

    # ---- Lifecycle ----

    def close(self) -> None:
        """Close the underlying store."""
        self._store.close()
