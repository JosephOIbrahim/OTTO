"""Tests for memory management — Day 5 of OTTO OS v3.0.

These tests verify:
1. Store and retrieve episodic memories
2. Store and retrieve procedural memories
3. Read-before-write invariant enforced
4. Identity memory isolation (never in exports)
5. Contextual memory clearing
6. SQLite backend CRUD operations
7. JSON serialization roundtrip
8. Deterministic key listing
9. Session reset clears read tracking
"""

from __future__ import annotations

import dataclasses

import pytest

from otto_v3.core.memory.types import MemoryEntry, MemoryType
from otto_v3.core.memory.store import SQLiteStore
from otto_v3.core.memory.manager import MemoryManager, ReadBeforeWriteViolation


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def store() -> SQLiteStore:
    """In-memory SQLite store for testing."""
    s = SQLiteStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def manager() -> MemoryManager:
    """Memory manager with in-memory store."""
    m = MemoryManager(":memory:")
    yield m
    m.close()


# ===================================================================
# Test: MemoryType enum
# ===================================================================

class TestMemoryType:
    """MemoryType must have 4 types with correct properties."""

    def test_has_four_types(self) -> None:
        assert len(MemoryType) == 4

    def test_table_names(self) -> None:
        assert MemoryType.EPISODIC.table_name == "memory_episodic"
        assert MemoryType.PROCEDURAL.table_name == "memory_procedural"
        assert MemoryType.CONTEXTUAL.table_name == "memory_contextual"
        assert MemoryType.IDENTITY.table_name == "memory_identity"

    def test_identity_not_syncable(self) -> None:
        assert MemoryType.IDENTITY.syncable is False

    def test_others_syncable(self) -> None:
        assert MemoryType.EPISODIC.syncable is True
        assert MemoryType.PROCEDURAL.syncable is True
        assert MemoryType.CONTEXTUAL.syncable is True


# ===================================================================
# Test: MemoryEntry dataclass
# ===================================================================

class TestMemoryEntry:
    """MemoryEntry must be frozen with correct fields."""

    def test_is_frozen(self) -> None:
        entry = MemoryEntry(
            key="test",
            memory_type=MemoryType.EPISODIC,
            content={"message": "hello"},
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.content = "tampered"  # type: ignore[misc]

    def test_has_timestamps(self) -> None:
        entry = MemoryEntry(
            key="test",
            memory_type=MemoryType.EPISODIC,
            content="data",
        )
        assert entry.created_at is not None
        assert entry.updated_at is not None

    def test_default_metadata_empty(self) -> None:
        entry = MemoryEntry(
            key="test",
            memory_type=MemoryType.EPISODIC,
            content="data",
        )
        assert entry.metadata == {}


# ===================================================================
# Test: SQLiteStore — basic CRUD
# ===================================================================

class TestSQLiteStoreCRUD:
    """SQLiteStore must handle create, read, update, delete."""

    def test_put_and_get(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "conv_001", {"text": "hello"})
        entry = store.get(MemoryType.EPISODIC, "conv_001")
        assert entry is not None
        assert entry.key == "conv_001"
        assert entry.content == {"text": "hello"}
        assert entry.memory_type == MemoryType.EPISODIC

    def test_get_nonexistent_returns_none(self, store: SQLiteStore) -> None:
        assert store.get(MemoryType.EPISODIC, "nope") is None

    def test_update_preserves_created_at(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "k1", "original")
        original = store.get(MemoryType.EPISODIC, "k1")
        assert original is not None

        store.put(MemoryType.EPISODIC, "k1", "updated")
        updated = store.get(MemoryType.EPISODIC, "k1")
        assert updated is not None
        assert updated.content == "updated"
        assert updated.created_at == original.created_at
        assert updated.updated_at >= original.updated_at

    def test_delete_existing(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "k1", "data")
        assert store.delete(MemoryType.EPISODIC, "k1") is True
        assert store.get(MemoryType.EPISODIC, "k1") is None

    def test_delete_nonexistent(self, store: SQLiteStore) -> None:
        assert store.delete(MemoryType.EPISODIC, "nope") is False

    def test_count(self, store: SQLiteStore) -> None:
        assert store.count(MemoryType.EPISODIC) == 0
        store.put(MemoryType.EPISODIC, "k1", "a")
        store.put(MemoryType.EPISODIC, "k2", "b")
        assert store.count(MemoryType.EPISODIC) == 2

    def test_clear(self, store: SQLiteStore) -> None:
        store.put(MemoryType.CONTEXTUAL, "s1", "state")
        store.put(MemoryType.CONTEXTUAL, "s2", "state")
        cleared = store.clear(MemoryType.CONTEXTUAL)
        assert cleared == 2
        assert store.count(MemoryType.CONTEXTUAL) == 0

    def test_metadata_roundtrip(self, store: SQLiteStore) -> None:
        meta = {"source": "prism", "confidence": 0.85}
        store.put(MemoryType.PROCEDURAL, "pattern_1", "data", metadata=meta)
        entry = store.get(MemoryType.PROCEDURAL, "pattern_1")
        assert entry is not None
        assert entry.metadata == meta


# ===================================================================
# Test: SQLiteStore — JSON serialization
# ===================================================================

class TestSQLiteStoreJSON:
    """Content must survive JSON roundtrip faithfully."""

    def test_dict_content(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "k", {"nested": {"a": [1, 2, 3]}})
        entry = store.get(MemoryType.EPISODIC, "k")
        assert entry is not None
        assert entry.content == {"nested": {"a": [1, 2, 3]}}

    def test_string_content(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "k", "plain string")
        entry = store.get(MemoryType.EPISODIC, "k")
        assert entry is not None
        assert entry.content == "plain string"

    def test_numeric_content(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "k", 42.5)
        entry = store.get(MemoryType.EPISODIC, "k")
        assert entry is not None
        assert entry.content == 42.5

    def test_list_content(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "k", [1, "two", 3.0, None])
        entry = store.get(MemoryType.EPISODIC, "k")
        assert entry is not None
        assert entry.content == [1, "two", 3.0, None]

    def test_bool_content(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "k", True)
        entry = store.get(MemoryType.EPISODIC, "k")
        assert entry is not None
        assert entry.content is True

    def test_null_content(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "k", None)
        entry = store.get(MemoryType.EPISODIC, "k")
        assert entry is not None
        assert entry.content is None


# ===================================================================
# Test: SQLiteStore — table isolation
# ===================================================================

class TestSQLiteStoreIsolation:
    """Each memory type must be physically isolated."""

    def test_types_are_independent(self, store: SQLiteStore) -> None:
        store.put(MemoryType.EPISODIC, "shared_key", "episodic_data")
        store.put(MemoryType.IDENTITY, "shared_key", "identity_data")

        ep = store.get(MemoryType.EPISODIC, "shared_key")
        id_ = store.get(MemoryType.IDENTITY, "shared_key")
        assert ep is not None and ep.content == "episodic_data"
        assert id_ is not None and id_.content == "identity_data"

    def test_delete_in_one_type_doesnt_affect_other(
        self, store: SQLiteStore
    ) -> None:
        store.put(MemoryType.EPISODIC, "k1", "ep")
        store.put(MemoryType.PROCEDURAL, "k1", "proc")
        store.delete(MemoryType.EPISODIC, "k1")
        assert store.get(MemoryType.EPISODIC, "k1") is None
        assert store.get(MemoryType.PROCEDURAL, "k1") is not None

    def test_clear_one_type_doesnt_affect_others(
        self, store: SQLiteStore
    ) -> None:
        store.put(MemoryType.CONTEXTUAL, "s1", "session")
        store.put(MemoryType.EPISODIC, "e1", "episode")
        store.clear(MemoryType.CONTEXTUAL)
        assert store.count(MemoryType.CONTEXTUAL) == 0
        assert store.count(MemoryType.EPISODIC) == 1


# ===================================================================
# Test: SQLiteStore — determinism
# ===================================================================

class TestSQLiteStoreDeterminism:
    """Key listing must be sorted and deterministic."""

    def test_list_keys_sorted(self, store: SQLiteStore) -> None:
        # Insert in reverse order
        for key in ["z_key", "a_key", "m_key", "d_key"]:
            store.put(MemoryType.EPISODIC, key, "data")
        keys = store.list_keys(MemoryType.EPISODIC)
        assert keys == ["a_key", "d_key", "m_key", "z_key"]

    def test_list_keys_deterministic_100x(self, store: SQLiteStore) -> None:
        for key in ["c", "a", "b"]:
            store.put(MemoryType.EPISODIC, key, "data")
        first = store.list_keys(MemoryType.EPISODIC)
        for _ in range(99):
            assert store.list_keys(MemoryType.EPISODIC) == first

    def test_list_keys_empty(self, store: SQLiteStore) -> None:
        assert store.list_keys(MemoryType.EPISODIC) == []


# ===================================================================
# Test: MemoryManager — read-before-write invariant
# ===================================================================

class TestReadBeforeWrite:
    """write() and delete() must require prior read()."""

    def test_write_without_read_raises(self, manager: MemoryManager) -> None:
        with pytest.raises(ReadBeforeWriteViolation):
            manager.write(MemoryType.EPISODIC, "k1", "data")

    def test_write_after_read_succeeds(self, manager: MemoryManager) -> None:
        manager.read(MemoryType.EPISODIC, "k1")  # Returns None (new key)
        manager.write(MemoryType.EPISODIC, "k1", "data")  # Should not raise

    def test_delete_without_read_raises(self, manager: MemoryManager) -> None:
        # First, put data via the allowed path
        manager.read(MemoryType.EPISODIC, "k1")
        manager.write(MemoryType.EPISODIC, "k1", "data")
        # Reset tracking, then try to delete without re-reading
        manager.reset_read_tracking()
        with pytest.raises(ReadBeforeWriteViolation):
            manager.delete(MemoryType.EPISODIC, "k1")

    def test_delete_after_read_succeeds(self, manager: MemoryManager) -> None:
        manager.read(MemoryType.EPISODIC, "k1")
        manager.write(MemoryType.EPISODIC, "k1", "data")
        # Read again (key now exists), then delete
        manager.read(MemoryType.EPISODIC, "k1")
        result = manager.delete(MemoryType.EPISODIC, "k1")
        assert result is True

    def test_read_none_enables_create(self, manager: MemoryManager) -> None:
        """Reading a nonexistent key (returns None) enables writing it."""
        result = manager.read(MemoryType.EPISODIC, "new_key")
        assert result is None
        manager.write(MemoryType.EPISODIC, "new_key", "created")
        # Verify it was stored
        entry = manager.read(MemoryType.EPISODIC, "new_key")
        assert entry is not None
        assert entry.content == "created"

    def test_read_tracking_per_type(self, manager: MemoryManager) -> None:
        """Reading key in one type does NOT enable writing in another."""
        manager.read(MemoryType.EPISODIC, "k1")
        with pytest.raises(ReadBeforeWriteViolation):
            manager.write(MemoryType.PROCEDURAL, "k1", "data")

    def test_reset_read_tracking(self, manager: MemoryManager) -> None:
        """After reset, previously-read keys require re-reading."""
        manager.read(MemoryType.EPISODIC, "k1")
        manager.write(MemoryType.EPISODIC, "k1", "data")
        manager.reset_read_tracking()
        with pytest.raises(ReadBeforeWriteViolation):
            manager.write(MemoryType.EPISODIC, "k1", "updated")

    def test_error_message_is_helpful(self, manager: MemoryManager) -> None:
        with pytest.raises(ReadBeforeWriteViolation, match="must be read"):
            manager.write(MemoryType.EPISODIC, "k1", "data")


# ===================================================================
# Test: MemoryManager — episodic memory
# ===================================================================

class TestEpisodicMemory:
    """Episodic memory stores conversation history and events."""

    def test_store_and_retrieve_conversation(
        self, manager: MemoryManager
    ) -> None:
        conversation = {
            "messages": [
                {"role": "user", "text": "I feel stuck"},
                {"role": "otto", "text": "That sounds frustrating"},
            ],
            "signal": "STUCK",
        }
        manager.read(MemoryType.EPISODIC, "conv_001")
        manager.write(MemoryType.EPISODIC, "conv_001", conversation)

        entry = manager.read(MemoryType.EPISODIC, "conv_001")
        assert entry is not None
        assert entry.content["messages"][0]["text"] == "I feel stuck"
        assert entry.memory_type == MemoryType.EPISODIC

    def test_multiple_episodes(self, manager: MemoryManager) -> None:
        for i in range(5):
            key = f"conv_{i:03d}"
            manager.read(MemoryType.EPISODIC, key)
            manager.write(MemoryType.EPISODIC, key, {"index": i})
        assert manager.count(MemoryType.EPISODIC) == 5
        keys = manager.list_keys(MemoryType.EPISODIC)
        assert keys == ["conv_000", "conv_001", "conv_002", "conv_003", "conv_004"]


# ===================================================================
# Test: MemoryManager — procedural memory
# ===================================================================

class TestProceduralMemory:
    """Procedural memory stores learned patterns and trail data."""

    def test_store_and_retrieve_pattern(
        self, manager: MemoryManager
    ) -> None:
        pattern = {
            "action": "decompose_task",
            "context": "user_stuck",
            "success_rate": 0.85,
        }
        manager.read(MemoryType.PROCEDURAL, "pattern_decompose")
        manager.write(MemoryType.PROCEDURAL, "pattern_decompose", pattern)

        entry = manager.read(MemoryType.PROCEDURAL, "pattern_decompose")
        assert entry is not None
        assert entry.content["success_rate"] == 0.85

    def test_update_pattern(self, manager: MemoryManager) -> None:
        manager.read(MemoryType.PROCEDURAL, "p1")
        manager.write(MemoryType.PROCEDURAL, "p1", {"rate": 0.5})

        entry = manager.read(MemoryType.PROCEDURAL, "p1")
        assert entry is not None
        assert entry.content["rate"] == 0.5

        # Update with new data (already read above)
        manager.write(MemoryType.PROCEDURAL, "p1", {"rate": 0.9})
        entry = manager.read(MemoryType.PROCEDURAL, "p1")
        assert entry is not None
        assert entry.content["rate"] == 0.9


# ===================================================================
# Test: MemoryManager — identity isolation
# ===================================================================

class TestIdentityIsolation:
    """Identity memory must be isolated and never exported."""

    def test_identity_not_in_export(self, manager: MemoryManager) -> None:
        """export_syncable() must NEVER include identity data."""
        manager.read(MemoryType.IDENTITY, "user_name")
        manager.write(MemoryType.IDENTITY, "user_name", "Joe")
        manager.read(MemoryType.EPISODIC, "conv_1")
        manager.write(MemoryType.EPISODIC, "conv_1", "hello")

        exported = manager.export_syncable()
        assert "IDENTITY" not in exported
        assert "EPISODIC" in exported
        assert len(exported["EPISODIC"]) == 1

    def test_identity_accessible_directly(
        self, manager: MemoryManager
    ) -> None:
        """Identity CAN be read/written through explicit type calls."""
        manager.read(MemoryType.IDENTITY, "preference")
        manager.write(MemoryType.IDENTITY, "preference", {"theme": "dark"})
        entry = manager.read(MemoryType.IDENTITY, "preference")
        assert entry is not None
        assert entry.content == {"theme": "dark"}

    def test_identity_type_not_syncable(self) -> None:
        assert MemoryType.IDENTITY.syncable is False

    def test_export_includes_only_syncable(
        self, manager: MemoryManager
    ) -> None:
        for mt in MemoryType:
            manager.read(mt, "test_key")
            manager.write(mt, "test_key", f"data_{mt.name}")

        exported = manager.export_syncable()
        exported_types = set(exported.keys())
        assert "IDENTITY" not in exported_types
        assert "EPISODIC" in exported_types
        assert "PROCEDURAL" in exported_types
        assert "CONTEXTUAL" in exported_types


# ===================================================================
# Test: MemoryManager — contextual memory
# ===================================================================

class TestContextualMemory:
    """Contextual memory is session-scoped and clearable."""

    def test_clear_contextual(self, manager: MemoryManager) -> None:
        manager.read(MemoryType.CONTEXTUAL, "session_goal")
        manager.write(MemoryType.CONTEXTUAL, "session_goal", "implement LIVRPS")
        manager.read(MemoryType.CONTEXTUAL, "energy")
        manager.write(MemoryType.CONTEXTUAL, "energy", "high")

        cleared = manager.clear_contextual()
        assert cleared == 2
        assert manager.count(MemoryType.CONTEXTUAL) == 0

    def test_clear_contextual_doesnt_affect_others(
        self, manager: MemoryManager
    ) -> None:
        manager.read(MemoryType.EPISODIC, "e1")
        manager.write(MemoryType.EPISODIC, "e1", "episode")
        manager.read(MemoryType.CONTEXTUAL, "s1")
        manager.write(MemoryType.CONTEXTUAL, "s1", "session")

        manager.clear_contextual()
        assert manager.count(MemoryType.CONTEXTUAL) == 0
        assert manager.count(MemoryType.EPISODIC) == 1


# ===================================================================
# Test: MemoryManager — exists() helper
# ===================================================================

class TestExists:
    """exists() checks presence without enabling writes."""

    def test_exists_false_for_missing(self, manager: MemoryManager) -> None:
        assert manager.exists(MemoryType.EPISODIC, "nope") is False

    def test_exists_true_for_present(self, manager: MemoryManager) -> None:
        manager.read(MemoryType.EPISODIC, "k1")
        manager.write(MemoryType.EPISODIC, "k1", "data")
        assert manager.exists(MemoryType.EPISODIC, "k1") is True

    def test_exists_does_not_enable_write(
        self, manager: MemoryManager
    ) -> None:
        """exists() does NOT count as read for write invariant."""
        manager.read(MemoryType.EPISODIC, "k1")
        manager.write(MemoryType.EPISODIC, "k1", "data")
        manager.reset_read_tracking()

        # exists() returns True but should not enable write
        assert manager.exists(MemoryType.EPISODIC, "k1") is True
        with pytest.raises(ReadBeforeWriteViolation):
            manager.write(MemoryType.EPISODIC, "k1", "new_data")


# ===================================================================
# Test: Package imports
# ===================================================================

class TestPackageImports:
    """Verify __init__.py re-exports work correctly."""

    def test_import_from_package(self) -> None:
        from otto_v3.core.memory import (
            MemoryEntry,
            MemoryManager,
            MemoryType,
            ReadBeforeWriteViolation,
            SQLiteStore,
        )
        assert MemoryType.EPISODIC is not None
        assert MemoryManager is not None
