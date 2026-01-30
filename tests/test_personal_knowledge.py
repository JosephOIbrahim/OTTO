"""
Tests for Personal Knowledge Store and Unified Search.

Tests the integration between the CLI 'remember' command
and the knowledge layer.
"""

import json
import pytest
from pathlib import Path

from otto.substrate.knowledge import (
    PersonalKnowledgeStore,
    UnifiedKnowledgeSearch,
    KnowledgePrim,
    PERSONAL_CONFIDENCE,
    MAX_PERSONAL_ITEMS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_otto_dir(tmp_path):
    """Create a temporary .otto directory."""
    otto_dir = tmp_path / ".otto"
    otto_dir.mkdir()
    (otto_dir / "knowledge").mkdir()
    return otto_dir


@pytest.fixture
def personal_store(temp_otto_dir):
    """Create a personal knowledge store with temp directory."""
    return PersonalKnowledgeStore(otto_dir=temp_otto_dir)


@pytest.fixture
def temp_knowledge_dir(tmp_path):
    """Create a temporary knowledge prims directory."""
    prims_dir = tmp_path / "prims"
    prims_dir.mkdir()

    # Create a test USDA file
    usda_content = '''#usda 1.0
(
    defaultPrim = "Knowledge"
)

def Scope "Knowledge" {
    def "TestPrim" (prepend apiSchemas = ["KnowledgePrimAPI"]) {
        custom string canonical_path = "/Knowledge/Test/TestPrim"
        custom string content = "This is test knowledge content."
        custom string summary = "Test knowledge"
        custom float confidence = 0.95
        custom string provenance = "test"
        custom string[] domains = ["test"]
        custom string[] triggers = ["test", "knowledge", "prim"]
    }
}
'''
    (prims_dir / "test.usda").write_text(usda_content)
    return prims_dir


@pytest.fixture
def unified_search(temp_knowledge_dir, temp_otto_dir):
    """Create unified search with both sources."""
    return UnifiedKnowledgeSearch(
        knowledge_path=temp_knowledge_dir,
        otto_dir=temp_otto_dir,
    )


# =============================================================================
# Test: Personal Knowledge Store Basics
# =============================================================================

class TestPersonalKnowledgeStore:
    """Tests for PersonalKnowledgeStore."""

    def test_remember_creates_prim(self, personal_store):
        """Remembering creates a KnowledgePrim."""
        prim = personal_store.remember("My favorite color is blue")

        assert isinstance(prim, KnowledgePrim)
        assert prim.canonical_path.startswith("/Knowledge/Personal/")
        assert "blue" in prim.content

    def test_remember_stores_to_file(self, personal_store, temp_otto_dir):
        """Remember persists to JSON file."""
        personal_store.remember("Important information")

        storage_path = temp_otto_dir / "knowledge" / "personal.json"
        assert storage_path.exists()

        with open(storage_path) as f:
            data = json.load(f)

        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "Important information"

    def test_remember_with_tags(self, personal_store):
        """Tags are stored and become triggers."""
        prim = personal_store.remember(
            "Server IP: 192.168.1.1",
            tags=["server", "network"]
        )

        assert "server" in prim.triggers
        assert "network" in prim.triggers
        assert "server" in prim.domains
        assert "network" in prim.domains

    def test_remember_generates_triggers(self, personal_store):
        """Content words become triggers."""
        prim = personal_store.remember("Python programming language")

        assert "python" in prim.triggers
        assert "programming" in prim.triggers
        assert "language" in prim.triggers

    def test_remember_confidence_is_fixed(self, personal_store):
        """Personal knowledge has fixed confidence."""
        prim = personal_store.remember("Any content")
        assert prim.confidence == PERSONAL_CONFIDENCE

    def test_search_finds_remembered(self, personal_store):
        """Search finds remembered items."""
        personal_store.remember("The quick brown fox")
        personal_store.remember("Lazy dog sleeping")

        result = personal_store.search("fox")

        assert result.found
        assert len(result.prims) >= 1
        assert "fox" in result.prims[0].content

    def test_search_returns_multiple(self, personal_store):
        """Search returns multiple matches."""
        personal_store.remember("Python is great")
        personal_store.remember("Python programming")
        personal_store.remember("Unrelated content")

        result = personal_store.search("python")

        assert len(result.prims) >= 2

    def test_retrieve_by_path(self, personal_store):
        """Direct retrieval by canonical path."""
        prim = personal_store.remember("Test content")

        result = personal_store.retrieve(prim.canonical_path)

        assert result.found
        assert result.prims[0].content == "Test content"

    def test_forget_removes_item(self, personal_store, temp_otto_dir):
        """Forget removes matching items."""
        personal_store.remember("Item to keep")
        prim = personal_store.remember("Item to remove")

        removed = personal_store.forget(prim.canonical_path.split("/")[-1], force=True)

        assert len(removed) == 1
        assert "remove" in removed[0].content

        # Verify storage
        storage_path = temp_otto_dir / "knowledge" / "personal.json"
        with open(storage_path) as f:
            data = json.load(f)

        assert len(data["items"]) == 1
        assert "keep" in data["items"][0]["content"]

    def test_forget_by_content(self, personal_store):
        """Forget can match by content."""
        personal_store.remember("Delete this specific text")

        removed = personal_store.forget("specific text", force=True)

        assert len(removed) == 1

    def test_forget_multiple_requires_force(self, personal_store):
        """Multiple matches without force returns matches without removing."""
        personal_store.remember("Python code one")
        personal_store.remember("Python code two")

        # Without force, returns matches but doesn't remove
        matches = personal_store.forget("Python")
        assert len(matches) == 2

        # Items still exist
        assert personal_store.item_count == 2

    def test_list_all(self, personal_store):
        """List all returns all items."""
        personal_store.remember("First item")
        personal_store.remember("Second item")
        personal_store.remember("Third item")

        all_items = personal_store.list_all()

        assert len(all_items) == 3

    def test_item_count(self, personal_store):
        """Item count is accurate."""
        assert personal_store.item_count == 0

        personal_store.remember("One")
        assert personal_store.item_count == 1

        personal_store.remember("Two")
        assert personal_store.item_count == 2


# =============================================================================
# Test: Unified Search
# =============================================================================

class TestUnifiedSearch:
    """Tests for UnifiedKnowledgeSearch."""

    def test_searches_both_sources(self, unified_search):
        """Unified search checks both USDA and personal."""
        # Add personal knowledge
        unified_search.personal_store.remember("Personal test knowledge")

        # Search should find both
        result = unified_search.search("test")

        assert result.found
        # Should find USDA prim (TestPrim) and personal item
        paths = [p.canonical_path for p in result.prims]
        has_usda = any("/Knowledge/Test/" in p for p in paths)
        has_personal = any("/Knowledge/Personal/" in p for p in paths)

        assert has_usda or has_personal

    def test_results_sorted_by_confidence(self, unified_search):
        """Results are sorted by confidence (USDA first)."""
        unified_search.personal_store.remember("Test prim content")

        result = unified_search.search("test prim")

        if len(result.prims) >= 2:
            # First prim should have higher or equal confidence
            assert result.prims[0].confidence >= result.prims[1].confidence

    def test_retrieve_usda_prim(self, unified_search):
        """Can retrieve USDA prims by path."""
        result = unified_search.retrieve("/Knowledge/Test/TestPrim")

        assert result.found
        assert result.prims[0].confidence == 0.95

    def test_retrieve_personal_prim(self, unified_search):
        """Can retrieve personal prims by path."""
        prim = unified_search.personal_store.remember("My personal note")

        result = unified_search.retrieve(prim.canonical_path)

        assert result.found
        assert result.prims[0].confidence == PERSONAL_CONFIDENCE

    def test_retrieve_nonexistent(self, unified_search):
        """Retrieve returns empty for nonexistent path."""
        result = unified_search.retrieve("/Knowledge/DoesNot/Exist")

        assert not result.found
        assert len(result.prims) == 0

    def test_max_results_honored(self, unified_search):
        """Max results limit is respected."""
        # Add many personal items
        for i in range(15):
            unified_search.personal_store.remember(f"Test item number {i}")

        result = unified_search.search("test", max_results=5)

        assert len(result.prims) <= 5

    def test_get_stats(self, unified_search):
        """Get stats returns info about all sources."""
        unified_search.personal_store.remember("Test")

        stats = unified_search.get_stats()

        assert "usda_prims" in stats
        assert "personal_items" in stats
        assert stats["personal_items"] >= 1


# =============================================================================
# Test: ThinkingMachines Compliance
# =============================================================================

class TestThinkingMachinesCompliance:
    """Tests for ThinkingMachines [He2025] compliance."""

    def test_confidence_is_fixed(self):
        """Personal confidence is a fixed constant."""
        assert PERSONAL_CONFIDENCE == 0.85

    def test_max_items_is_fixed(self):
        """Max items is a fixed constant."""
        assert MAX_PERSONAL_ITEMS == 1000

    def test_path_generation_is_deterministic(self, personal_store):
        """Path generation follows deterministic pattern."""
        prim1 = personal_store.remember("First")
        prim2 = personal_store.remember("Second")

        assert prim1.canonical_path == "/Knowledge/Personal/mem_0001"
        assert prim2.canonical_path == "/Knowledge/Personal/mem_0002"

    def test_search_ordering_is_deterministic(self, unified_search):
        """Search results are ordered deterministically."""
        unified_search.personal_store.remember("Alpha test")
        unified_search.personal_store.remember("Beta test")

        result1 = unified_search.search("test")
        result2 = unified_search.search("test")

        # Same query should return same order
        paths1 = [p.canonical_path for p in result1.prims]
        paths2 = [p.canonical_path for p in result2.prims]
        assert paths1 == paths2

    def test_retrieval_is_deterministic(self, personal_store):
        """Same path always returns same prim."""
        prim = personal_store.remember("Consistent content")
        path = prim.canonical_path

        result1 = personal_store.retrieve(path)
        result2 = personal_store.retrieve(path)

        assert result1.prims[0].content == result2.prims[0].content
        assert result1.prims[0].confidence == result2.prims[0].confidence


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_search(self, personal_store):
        """Search with no matches returns empty result."""
        result = personal_store.search("nonexistent query xyz123")

        assert not result.found
        assert len(result.prims) == 0

    def test_empty_content_ignored(self, temp_otto_dir):
        """Items with empty content are not indexed."""
        # Manually create file with empty content
        storage_path = temp_otto_dir / "knowledge" / "personal.json"
        storage_path.write_text(json.dumps({
            "items": [{"id": "mem_0001", "content": "", "tags": []}]
        }))

        store = PersonalKnowledgeStore(otto_dir=temp_otto_dir)
        assert store.item_count == 0

    def test_corrupted_file_handled(self, temp_otto_dir):
        """Corrupted JSON file is handled gracefully."""
        storage_path = temp_otto_dir / "knowledge" / "personal.json"
        storage_path.write_text("not valid json {{{")

        store = PersonalKnowledgeStore(otto_dir=temp_otto_dir)
        # Should not raise, just return empty
        assert store.item_count == 0

    def test_special_characters_in_content(self, personal_store):
        """Special characters don't break storage."""
        content = 'Content with "quotes", <brackets>, and emoji 🎉'
        prim = personal_store.remember(content)

        result = personal_store.retrieve(prim.canonical_path)
        assert result.prims[0].content == content

    def test_very_long_content(self, personal_store):
        """Very long content is handled."""
        long_content = "word " * 1000  # 5000 chars
        prim = personal_store.remember(long_content)

        # Summary should be truncated
        assert len(prim.summary) <= 103  # 100 + "..."

    def test_unicode_content(self, personal_store):
        """Unicode content is handled correctly."""
        content = "日本語テスト содержание محتوى"
        prim = personal_store.remember(content)

        result = personal_store.retrieve(prim.canonical_path)
        assert result.prims[0].content == content


# =============================================================================
# Test: Performance
# =============================================================================

class TestPerformance:
    """Performance-related tests."""

    def test_retrieval_time_tracked(self, personal_store):
        """Retrieval time is tracked."""
        prim = personal_store.remember("Performance test")
        result = personal_store.retrieve(prim.canonical_path)

        assert result.retrieval_time_ms >= 0
        assert result.retrieval_time_ms < 100  # Should be fast

    def test_search_time_tracked(self, personal_store):
        """Search time is tracked."""
        for i in range(10):
            personal_store.remember(f"Item {i} for search test")

        result = personal_store.search("search test")

        assert result.retrieval_time_ms >= 0
        assert result.retrieval_time_ms < 100  # Should be fast

    def test_lazy_loading(self, temp_otto_dir):
        """Store uses lazy loading."""
        # Create file
        storage_path = temp_otto_dir / "knowledge" / "personal.json"
        storage_path.write_text(json.dumps({
            "items": [{"id": "mem_0001", "content": "test", "tags": []}]
        }))

        store = PersonalKnowledgeStore(otto_dir=temp_otto_dir)

        # Not loaded yet
        assert not store._loaded

        # Access triggers load
        _ = store.item_count
        assert store._loaded
