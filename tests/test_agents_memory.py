"""
Tests for Memory Agent
======================

Tests for profile storage and recall.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from otto.agents import AgentConfig
from otto.agents.memory import (
    MemoryAgent,
    MemoryCategory,
    MemoryEntry,
    MemoryResult,
)


class TestMemoryEntry:
    """Tests for MemoryEntry."""

    def test_create_entry(self):
        """Create memory entry."""
        now = datetime.now()
        entry = MemoryEntry(
            key="preference:theme",
            category="preference",
            value="dark",
            confidence=0.9,
            created_at=now,
            updated_at=now,
        )
        assert entry.key == "preference:theme"
        assert entry.value == "dark"

    def test_entry_not_expired(self):
        """Entry without expiration is not expired."""
        now = datetime.now()
        entry = MemoryEntry(
            key="test",
            category="test",
            value="value",
            confidence=0.5,
            created_at=now,
            updated_at=now,
        )
        assert not entry.is_expired()

    def test_entry_expired(self):
        """Entry with past expiration is expired."""
        now = datetime.now()
        past = now - timedelta(hours=1)
        entry = MemoryEntry(
            key="test",
            category="test",
            value="value",
            confidence=0.5,
            created_at=past,
            updated_at=past,
            expires_at=past,
        )
        assert entry.is_expired()

    def test_entry_to_dict_from_dict(self):
        """Entry serialization roundtrip."""
        now = datetime.now()
        original = MemoryEntry(
            key="test:key",
            category="test",
            value={"nested": "value"},
            confidence=0.8,
            created_at=now,
            updated_at=now,
            source="explicit",
        )
        data = original.to_dict()
        restored = MemoryEntry.from_dict(data)

        assert restored.key == original.key
        assert restored.value == original.value
        assert restored.confidence == original.confidence


class TestMemoryAgent:
    """Tests for MemoryAgent."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_store_memory(self, temp_storage):
        """Store a memory."""
        agent = MemoryAgent(storage_path=temp_storage)
        result = await agent.run(
            "store preference:theme=dark",
            {"confidence": 0.9}
        )

        assert result.success
        memory_result = result.result
        # Result is now a dict via to_dict()
        assert isinstance(memory_result, dict)
        assert memory_result["operation"] == "store"
        assert memory_result["affected_count"] == 1

    @pytest.mark.asyncio
    async def test_recall_memory(self, temp_storage):
        """Recall a stored memory."""
        agent = MemoryAgent(storage_path=temp_storage)

        # Store first
        await agent.run("store preference:theme=dark", {})

        # Recall
        result = await agent.run("recall preference:theme", {})

        assert result.success
        memory_result = result.result
        assert memory_result["operation"] == "recall"
        assert len(memory_result["entries"]) == 1
        assert memory_result["entries"][0]["value"] == "dark"

    @pytest.mark.asyncio
    async def test_update_memory(self, temp_storage):
        """Update an existing memory."""
        agent = MemoryAgent(storage_path=temp_storage)

        # Store first
        await agent.run("store preference:theme=dark", {})

        # Update
        result = await agent.run("update preference:theme=light", {})

        assert result.success

        # Recall to verify
        recall_result = await agent.run("recall preference:theme", {})
        assert recall_result.result["entries"][0]["value"] == "light"

    @pytest.mark.asyncio
    async def test_forget_memory(self, temp_storage):
        """Forget a memory."""
        agent = MemoryAgent(storage_path=temp_storage)

        # Store first
        await agent.run("store preference:theme=dark", {})

        # Forget
        result = await agent.run("forget preference:theme", {})

        assert result.success
        assert result.result["affected_count"] == 1

        # Recall should find nothing
        recall_result = await agent.run("recall preference:theme", {})
        assert len(recall_result.result["entries"]) == 0

    @pytest.mark.asyncio
    async def test_list_category(self, temp_storage):
        """List all memories in a category."""
        agent = MemoryAgent(storage_path=temp_storage)

        # Store multiple
        await agent.run("store preference:theme=dark", {})
        await agent.run("store preference:font=mono", {})
        await agent.run("store calibration:speed=fast", {})

        # List preferences
        result = await agent.run("list preference", {})

        assert result.success
        assert result.result["affected_count"] == 2

    @pytest.mark.asyncio
    async def test_store_json_value(self, temp_storage):
        """Store JSON value."""
        agent = MemoryAgent(storage_path=temp_storage)

        result = await agent.run(
            'store preference:settings={"theme": "dark", "size": 14}',
            {}
        )

        assert result.success

        # Recall and verify JSON was parsed
        recall = await agent.run("recall preference:settings", {})
        value = recall.result["entries"][0]["value"]
        assert isinstance(value, dict)
        assert value["theme"] == "dark"

    @pytest.mark.asyncio
    async def test_recall_with_pattern(self, temp_storage):
        """Recall with pattern matching."""
        agent = MemoryAgent(storage_path=temp_storage)

        # Store multiple
        await agent.run("store preference:theme=dark", {})
        await agent.run("store preference:theme_alt=light", {})
        await agent.run("store preference:other=value", {})

        # Recall with pattern
        result = await agent.run("recall preference:theme", {})

        assert result.success
        # Should match both theme and theme_alt
        assert len(result.result["entries"]) >= 1

    @pytest.mark.asyncio
    async def test_persistence(self, temp_storage):
        """Memory persists across agent instances."""
        # First agent stores
        agent1 = MemoryAgent(storage_path=temp_storage)
        await agent1.run("store preference:test=persisted", {})

        # Second agent recalls
        agent2 = MemoryAgent(storage_path=temp_storage)
        result = await agent2.run("recall preference:test", {})

        assert result.success
        assert len(result.result["entries"]) == 1
        assert result.result["entries"][0]["value"] == "persisted"

    @pytest.mark.asyncio
    async def test_direct_get_set(self, temp_storage):
        """Direct synchronous get/set."""
        agent = MemoryAgent(storage_path=temp_storage)

        # Direct set
        agent.set("test", "key", {"value": 42}, confidence=0.9)

        # Direct get
        value = agent.get("test", "key")
        assert value == {"value": 42}

    @pytest.mark.asyncio
    async def test_direct_get_default(self, temp_storage):
        """Direct get returns default for missing."""
        agent = MemoryAgent(storage_path=temp_storage)
        value = agent.get("missing", "key", default="default_value")
        assert value == "default_value"

    @pytest.mark.asyncio
    async def test_invalid_store_format(self, temp_storage):
        """Invalid store format returns error."""
        agent = MemoryAgent(storage_path=temp_storage)
        result = await agent.run("store invalid_format", {})

        assert not result.result["success"]

    @pytest.mark.asyncio
    async def test_unknown_operation(self, temp_storage):
        """Unknown operation returns error."""
        agent = MemoryAgent(storage_path=temp_storage)
        result = await agent.run("unknown test:key=value", {})

        assert not result.result["success"]
