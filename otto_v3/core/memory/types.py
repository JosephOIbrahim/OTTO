"""Memory types and entry structure.

MemoryType is an enum of the four cognitive memory categories.
MemoryEntry is the frozen dataclass that represents a single
stored memory with metadata and timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any


class MemoryType(Enum):
    """The four categories of cognitive memory.

    Each type maps to a separate SQLite table, providing physical
    isolation at the storage level. Identity is flagged as never-sync
    to enforce the constitutional privacy requirement.
    """

    EPISODIC = auto()      # What happened (conversations, events)
    PROCEDURAL = auto()    # What works (pheromone trails, learned patterns)
    CONTEXTUAL = auto()    # Current state (session-scoped, cleared on restart)
    IDENTITY = auto()      # Who you are (NEVER synced, device-only)

    @property
    def table_name(self) -> str:
        """SQLite table name for this memory type."""
        return f"memory_{self.name.lower()}"

    @property
    def syncable(self) -> bool:
        """Whether this memory type can be synced to other devices.

        Identity memory is NEVER syncable — this is constitutional.
        """
        return self != MemoryType.IDENTITY


@dataclass(frozen=True)
class MemoryEntry:
    """A single memory record.

    Frozen because retrieved memories are snapshots — they should
    not be mutated after retrieval. To update, write a new version
    through the manager (which enforces read-before-write).

    Attributes:
        key: Unique identifier within its memory type.
        memory_type: Which category this memory belongs to.
        content: The actual memory data (JSON-serializable).
        created_at: When first stored (UTC).
        updated_at: When last modified (UTC).
        metadata: Optional tags, source info, etc.
    """

    key: str
    memory_type: MemoryType
    content: Any
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)
