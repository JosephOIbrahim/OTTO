"""
Notes Integration Module
========================

Notes adapters for context gathering.

Privacy First:
- Only metadata extraction (counts, topics, activity)
- Never raw content (note titles, text)
- Auth tokens in OS keychain (via encryption module)

Available Adapters:
- MarkdownNotesAdapter: For Obsidian vaults, markdown directories

Usage:
    from otto.integration.notes import (
        NotesAdapter,
        MarkdownNotesAdapter,
        create_markdown_adapter,
    )

    # Create adapter
    adapter = create_markdown_adapter("~/Documents/Notes")

    # Get context
    context = await adapter.get_context()
    print(f"Total notes: {context.total_notes}")
    print(f"Richness: {context.richness_level}")
"""

from .base import NotesAdapter, SPARSE_THRESHOLD, MODERATE_THRESHOLD
from .markdown_adapter import MarkdownNotesAdapter, create_markdown_adapter


__all__ = [
    # Base
    "NotesAdapter",
    "SPARSE_THRESHOLD",
    "MODERATE_THRESHOLD",
    # Markdown
    "MarkdownNotesAdapter",
    "create_markdown_adapter",
]
