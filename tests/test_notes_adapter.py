"""
Tests for Notes Adapter
=======================

Tests the notes integration adapters for metadata extraction.
"""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from otto.integration import (
    NotesContext,
    ContextSignal,
    IntegrationConfig,
    IntegrationType,
)
from otto.integration.notes import (
    NotesAdapter,
    MarkdownNotesAdapter,
    create_markdown_adapter,
    SPARSE_THRESHOLD,
    MODERATE_THRESHOLD,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_notes_dir():
    """Create a temporary notes directory with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        notes_path = Path(tmpdir)

        # Create some markdown files
        (notes_path / "note1.md").write_text("# Note 1\nContent here")
        (notes_path / "note2.md").write_text("# Note 2\nMore content")

        # Create subdirectory with notes
        (notes_path / "work").mkdir()
        (notes_path / "work" / "meeting.md").write_text("# Meeting notes")
        (notes_path / "work" / "project.md").write_text("# Project notes")

        # Create another subdirectory
        (notes_path / "personal").mkdir()
        (notes_path / "personal" / "ideas.md").write_text("# Ideas")

        yield notes_path


@pytest.fixture
def empty_notes_dir():
    """Create an empty notes directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def large_notes_dir():
    """Create a notes directory with many files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        notes_path = Path(tmpdir)

        # Create 60 notes (above MODERATE_THRESHOLD)
        for i in range(60):
            (notes_path / f"note_{i:03d}.md").write_text(f"# Note {i}")

        yield notes_path


# =============================================================================
# Test: NotesContext Model
# =============================================================================

class TestNotesContext:
    """Tests for NotesContext model."""

    def test_empty_context(self):
        """Empty context has default values."""
        ctx = NotesContext.empty()

        assert ctx.total_notes == 0
        assert ctx.notes_modified_today == 0
        assert ctx.richness_level == "sparse"
        assert ctx.has_searchable_notes is False

    def test_sparse_richness(self):
        """Sparse richness for low note count."""
        ctx = NotesContext(total_notes=5, richness_level="sparse")

        signals = ctx.get_signals()
        assert ContextSignal.NOTES_SPARSE in signals

    def test_rich_richness(self):
        """Rich richness for high note count."""
        ctx = NotesContext(total_notes=100, richness_level="rich")

        signals = ctx.get_signals()
        assert ContextSignal.NOTES_RICH in signals

    def test_recent_activity_signal(self):
        """Recent activity generates signal."""
        ctx = NotesContext(
            total_notes=10,
            notes_modified_today=3,
            richness_level="moderate",
        )

        signals = ctx.get_signals()
        assert ContextSignal.NOTES_RECENT_ACTIVITY in signals

    def test_to_dict_from_dict_roundtrip(self):
        """Serialization roundtrip preserves data."""
        original = NotesContext(
            total_notes=25,
            notes_modified_today=5,
            notes_modified_this_week=15,
            topic_counts={"work": 10, "personal": 15},
            has_searchable_notes=True,
            most_recent_activity_hours=2,
            richness_level="moderate",
        )

        data = original.to_dict()
        restored = NotesContext.from_dict(data)

        assert restored.total_notes == original.total_notes
        assert restored.notes_modified_today == original.notes_modified_today
        assert restored.topic_counts == original.topic_counts
        assert restored.richness_level == original.richness_level


# =============================================================================
# Test: MarkdownNotesAdapter Initialization
# =============================================================================

class TestMarkdownNotesAdapterInit:
    """Tests for MarkdownNotesAdapter initialization."""

    @pytest.mark.asyncio
    async def test_init_with_valid_path(self, temp_notes_dir):
        """Initialization succeeds with valid directory."""
        adapter = create_markdown_adapter(str(temp_notes_dir))

        result = await adapter.initialize()

        assert result is True

    @pytest.mark.asyncio
    async def test_init_with_missing_path(self):
        """Initialization fails with missing path."""
        adapter = create_markdown_adapter("/nonexistent/path")

        result = await adapter.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_init_with_file_path(self, temp_notes_dir):
        """Initialization fails when given a file instead of directory."""
        file_path = temp_notes_dir / "note1.md"
        adapter = create_markdown_adapter(str(file_path))

        result = await adapter.initialize()

        assert result is False

    @pytest.mark.asyncio
    async def test_init_without_path(self):
        """Initialization fails without notes_path in config."""
        config = IntegrationConfig(
            integration_type=IntegrationType.NOTES,
            service_name="markdown_notes",
            settings={},
        )
        adapter = MarkdownNotesAdapter(config)

        result = await adapter.initialize()

        assert result is False


# =============================================================================
# Test: MarkdownNotesAdapter Context Fetching
# =============================================================================

class TestMarkdownNotesAdapterContext:
    """Tests for MarkdownNotesAdapter context fetching."""

    @pytest.mark.asyncio
    async def test_fetch_context_counts_notes(self, temp_notes_dir):
        """Context includes correct note count."""
        adapter = create_markdown_adapter(str(temp_notes_dir))

        context = await adapter.get_context()

        # 5 notes: 2 in root, 2 in work/, 1 in personal/
        assert context.total_notes == 5
        assert context.has_searchable_notes is True

    @pytest.mark.asyncio
    async def test_fetch_context_extracts_topics(self, temp_notes_dir):
        """Context includes topic distribution from folder structure."""
        adapter = create_markdown_adapter(str(temp_notes_dir))

        context = await adapter.get_context()

        assert "work" in context.topic_counts
        assert "personal" in context.topic_counts
        assert "root" in context.topic_counts

        assert context.topic_counts["work"] == 2
        assert context.topic_counts["personal"] == 1
        assert context.topic_counts["root"] == 2

    @pytest.mark.asyncio
    async def test_fetch_context_empty_directory(self, empty_notes_dir):
        """Context handles empty directory."""
        adapter = create_markdown_adapter(str(empty_notes_dir))

        context = await adapter.get_context()

        assert context.total_notes == 0
        assert context.has_searchable_notes is False
        assert context.richness_level == "sparse"

    @pytest.mark.asyncio
    async def test_fetch_context_large_directory(self, large_notes_dir):
        """Context correctly calculates richness for large vault."""
        adapter = create_markdown_adapter(str(large_notes_dir))

        context = await adapter.get_context()

        assert context.total_notes == 60
        assert context.richness_level == "rich"

    @pytest.mark.asyncio
    async def test_ignores_hidden_directories(self, temp_notes_dir):
        """Adapter ignores hidden directories."""
        # Create hidden directory with notes
        hidden = temp_notes_dir / ".hidden"
        hidden.mkdir()
        (hidden / "secret.md").write_text("# Secret")

        adapter = create_markdown_adapter(str(temp_notes_dir))
        context = await adapter.get_context()

        # Should still be 5 (hidden dir ignored)
        assert context.total_notes == 5

    @pytest.mark.asyncio
    async def test_ignores_git_directory(self, temp_notes_dir):
        """Adapter ignores .git directory."""
        git_dir = temp_notes_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("# Git config")

        adapter = create_markdown_adapter(str(temp_notes_dir))
        context = await adapter.get_context()

        # Should still be 5 (.git ignored)
        assert context.total_notes == 5


# =============================================================================
# Test: Richness Levels
# =============================================================================

class TestRichnessLevels:
    """Tests for richness level calculation."""

    @pytest.mark.asyncio
    async def test_sparse_level(self):
        """Notes below SPARSE_THRESHOLD are sparse."""
        with tempfile.TemporaryDirectory() as tmpdir:
            notes_path = Path(tmpdir)
            for i in range(5):
                (notes_path / f"note_{i}.md").write_text(f"# Note {i}")

            adapter = create_markdown_adapter(str(notes_path))
            context = await adapter.get_context()

            assert context.richness_level == "sparse"
            assert context.total_notes < SPARSE_THRESHOLD

    @pytest.mark.asyncio
    async def test_moderate_level(self):
        """Notes between thresholds are moderate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            notes_path = Path(tmpdir)
            # Create 25 notes (between SPARSE_THRESHOLD and MODERATE_THRESHOLD)
            for i in range(25):
                (notes_path / f"note_{i}.md").write_text(f"# Note {i}")

            adapter = create_markdown_adapter(str(notes_path))
            context = await adapter.get_context()

            assert context.richness_level == "moderate"
            assert SPARSE_THRESHOLD <= context.total_notes < MODERATE_THRESHOLD

    @pytest.mark.asyncio
    async def test_rich_level(self):
        """Notes above MODERATE_THRESHOLD are rich."""
        with tempfile.TemporaryDirectory() as tmpdir:
            notes_path = Path(tmpdir)
            # Create 55 notes (above MODERATE_THRESHOLD)
            for i in range(55):
                (notes_path / f"note_{i}.md").write_text(f"# Note {i}")

            adapter = create_markdown_adapter(str(notes_path))
            context = await adapter.get_context()

            assert context.richness_level == "rich"
            assert context.total_notes >= MODERATE_THRESHOLD


# =============================================================================
# Test: File Extensions
# =============================================================================

class TestFileExtensions:
    """Tests for file extension handling."""

    @pytest.mark.asyncio
    async def test_includes_markdown_files(self, temp_notes_dir):
        """Adapter includes .md files."""
        adapter = create_markdown_adapter(str(temp_notes_dir))
        context = await adapter.get_context()

        assert context.total_notes == 5  # All .md files

    @pytest.mark.asyncio
    async def test_excludes_txt_by_default(self, temp_notes_dir):
        """Adapter excludes .txt files by default."""
        (temp_notes_dir / "plain.txt").write_text("Plain text")

        adapter = create_markdown_adapter(str(temp_notes_dir))
        context = await adapter.get_context()

        assert context.total_notes == 5  # txt excluded

    @pytest.mark.asyncio
    async def test_includes_txt_when_enabled(self, temp_notes_dir):
        """Adapter includes .txt files when enabled."""
        (temp_notes_dir / "plain.txt").write_text("Plain text")

        adapter = create_markdown_adapter(str(temp_notes_dir), include_txt=True)
        context = await adapter.get_context()

        assert context.total_notes == 6  # txt included

    @pytest.mark.asyncio
    async def test_ignores_other_extensions(self, temp_notes_dir):
        """Adapter ignores non-markdown files."""
        (temp_notes_dir / "image.png").write_bytes(b"fake image")
        (temp_notes_dir / "data.json").write_text('{"key": "value"}')
        (temp_notes_dir / "script.py").write_text("print('hello')")

        adapter = create_markdown_adapter(str(temp_notes_dir))
        context = await adapter.get_context()

        assert context.total_notes == 5  # Only .md files


# =============================================================================
# Test: Context Signals
# =============================================================================

class TestContextSignals:
    """Tests for context signal generation."""

    @pytest.mark.asyncio
    async def test_sparse_generates_sparse_signal(self):
        """Sparse notes generate NOTES_SPARSE signal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            notes_path = Path(tmpdir)
            (notes_path / "note.md").write_text("# Note")

            adapter = create_markdown_adapter(str(notes_path))
            context = await adapter.get_context()

            signals = context.get_signals()
            assert ContextSignal.NOTES_SPARSE in signals

    @pytest.mark.asyncio
    async def test_rich_generates_rich_signal(self, large_notes_dir):
        """Rich notes generate NOTES_RICH signal."""
        adapter = create_markdown_adapter(str(large_notes_dir))
        context = await adapter.get_context()

        signals = context.get_signals()
        assert ContextSignal.NOTES_RICH in signals


# =============================================================================
# Test: Privacy Compliance
# =============================================================================

class TestPrivacyCompliance:
    """Tests ensuring privacy-first design."""

    @pytest.mark.asyncio
    async def test_no_content_in_context(self, temp_notes_dir):
        """Context does not include note content."""
        adapter = create_markdown_adapter(str(temp_notes_dir))
        context = await adapter.get_context()

        # Convert to dict and verify no content fields
        data = context.to_dict()

        assert "content" not in data
        assert "title" not in data
        assert "text" not in data
        assert "body" not in data

    @pytest.mark.asyncio
    async def test_no_file_paths_in_context(self, temp_notes_dir):
        """Context does not include file paths."""
        adapter = create_markdown_adapter(str(temp_notes_dir))
        context = await adapter.get_context()

        data = context.to_dict()

        assert "path" not in data
        assert "file" not in data
        assert str(temp_notes_dir) not in str(data)


# =============================================================================
# Test: Health Status
# =============================================================================

class TestHealthStatus:
    """Tests for adapter health tracking."""

    @pytest.mark.asyncio
    async def test_healthy_after_successful_fetch(self, temp_notes_dir):
        """Adapter reports healthy after successful context fetch."""
        adapter = create_markdown_adapter(str(temp_notes_dir))
        await adapter.get_context()

        health = await adapter.get_health()

        assert health.is_available()
        assert health.last_sync is not None


# =============================================================================
# Test: Factory Function
# =============================================================================

class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_markdown_adapter(self, temp_notes_dir):
        """Factory creates configured adapter."""
        adapter = create_markdown_adapter(str(temp_notes_dir))

        assert isinstance(adapter, MarkdownNotesAdapter)
        assert adapter.config.settings["notes_path"] == str(temp_notes_dir)

    def test_create_with_include_txt(self, temp_notes_dir):
        """Factory passes include_txt setting."""
        adapter = create_markdown_adapter(str(temp_notes_dir), include_txt=True)

        assert adapter.config.settings["include_txt"] is True


# =============================================================================
# Test: ThinkingMachines Compliance
# =============================================================================

class TestDeterminism:
    """Tests for ThinkingMachines Determinism."""

    @pytest.mark.asyncio
    async def test_same_files_same_context(self, temp_notes_dir):
        """Same files produce same context (deterministic)."""
        adapter = create_markdown_adapter(str(temp_notes_dir))

        context1 = await adapter.get_context()
        context2 = await adapter.get_context()

        assert context1.total_notes == context2.total_notes
        assert context1.richness_level == context2.richness_level
        assert context1.topic_counts == context2.topic_counts
