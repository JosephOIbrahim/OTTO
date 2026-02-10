"""Memory subsystem — episodic, procedural, contextual, identity.

Four memory types with SQLite persistence and read-before-write
invariant enforcement. Identity memory is isolated and NEVER synced.

Memory types:
    EPISODIC    — What happened (conversations, events)
    PROCEDURAL  — What works (pheromone trails, patterns)
    CONTEXTUAL  — Current state (session-scoped)
    IDENTITY    — Who you are (NEVER synced, device-only)
"""

from otto.core.memory.types import MemoryEntry, MemoryType
from otto.core.memory.store import SQLiteStore
from otto.core.memory.manager import MemoryManager, ReadBeforeWriteViolation

__all__ = [
    "MemoryEntry",
    "MemoryManager",
    "MemoryType",
    "ReadBeforeWriteViolation",
    "SQLiteStore",
]
