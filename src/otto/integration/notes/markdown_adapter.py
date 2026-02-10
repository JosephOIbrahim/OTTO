"""
Markdown Notes Adapter
======================

File-based notes adapter that reads markdown files from directories.

This provides notes context without requiring Obsidian/Notion API setup:
- Point OTTO to a directory containing .md files
- OTTO scans for markdown files
- Extracts metadata (not content) for context

Use Cases:
1. Obsidian vaults (without plugin requirements)
2. Any markdown-based notes (Foam, Dendron, etc.)
3. Documentation directories
4. Personal wikis

Privacy First:
- Only extracts file metadata (size, modified time)
- Uses folder structure for topic categorization
- NEVER reads note content or titles

Determinism:
- DETERMINISTIC: Same files -> Same context
- FIXED: Parsing rules are immutable
- BOUNDED: Max notes limit prevents memory issues
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..adapter import IntegrationError
from ..models import IntegrationConfig, IntegrationType
from .base import NotesAdapter

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED - determinism compliant)
# =============================================================================

MAX_NOTES = 5000         # Prevent memory issues with huge vaults
MAX_DEPTH = 10           # Max directory traversal depth
EXTENSIONS = {".md", ".markdown", ".txt"}  # Supported extensions
ENCODING = "utf-8"       # Standard encoding
IGNORE_DIRS = {".git", ".obsidian", "node_modules", "__pycache__", ".trash"}


# =============================================================================
# Markdown Adapter
# =============================================================================

class MarkdownNotesAdapter(NotesAdapter):
    """
    Markdown file-based notes adapter.

    Scans directories for markdown files and provides
    notes context without reading file contents.

    Config Settings:
        notes_path: Path to notes directory (e.g., Obsidian vault)
        include_txt: Whether to include .txt files (default: False)

    Example:
        config = IntegrationConfig(
            integration_type=IntegrationType.NOTES,
            service_name="markdown_notes",
            settings={"notes_path": "~/Documents/Notes"}
        )
        adapter = MarkdownNotesAdapter(config)
        context = await adapter.get_context()
    """

    SERVICE_NAME = "markdown_notes"
    INTEGRATION_TYPE = IntegrationType.NOTES
    SUPPORTS_WRITE = False  # Read-only

    def __init__(self, config: IntegrationConfig):
        """
        Initialize markdown notes adapter.

        Args:
            config: Configuration with 'notes_path' in settings
        """
        super().__init__(config)
        self._notes_path: Optional[Path] = None
        self._include_txt = config.settings.get("include_txt", False)

    # =========================================================================
    # IntegrationAdapter Implementation
    # =========================================================================

    async def initialize(self) -> bool:
        """
        Initialize adapter by validating the notes path.

        Returns:
            True if path exists and is a directory
        """
        notes_path_str = self.config.settings.get("notes_path")
        if not notes_path_str:
            logger.error("MarkdownNotesAdapter: No 'notes_path' in config settings")
            return False

        # Expand user path
        self._notes_path = Path(notes_path_str).expanduser()

        if not self._notes_path.exists():
            logger.error(f"MarkdownNotesAdapter: Path does not exist: {self._notes_path}")
            return False

        if not self._notes_path.is_dir():
            logger.error(f"MarkdownNotesAdapter: Path is not a directory: {self._notes_path}")
            return False

        logger.info(f"MarkdownNotesAdapter: Initialized with {self._notes_path}")
        return True

    async def _fetch_raw_notes(self) -> List[dict]:
        """
        Discover and extract metadata from markdown files.

        Returns:
            List of note metadata dictionaries
        """
        if not self._notes_path:
            return []

        notes = []
        extensions = EXTENSIONS.copy()
        if not self._include_txt:
            extensions.discard(".txt")

        try:
            notes = self._scan_directory(
                self._notes_path,
                root_path=self._notes_path,  # Pass original root for topic calculation
                extensions=extensions,
                depth=0,
                max_depth=MAX_DEPTH,
            )
        except Exception as e:
            logger.error(f"MarkdownNotesAdapter: Scan failed: {e}")
            raise IntegrationError(f"Failed to scan notes directory: {e}")

        logger.debug(f"MarkdownNotesAdapter: Found {len(notes)} notes")
        return notes

    def _scan_directory(
        self,
        path: Path,
        root_path: Path,
        extensions: set,
        depth: int,
        max_depth: int,
    ) -> List[dict]:
        """
        Recursively scan directory for notes.

        Args:
            path: Directory to scan
            root_path: Original notes directory (for topic calculation)
            extensions: File extensions to include
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            List of note metadata dictionaries
        """
        if depth > max_depth:
            return []

        notes = []

        try:
            for item in path.iterdir():
                if len(notes) >= MAX_NOTES:
                    logger.warning(f"Reached max notes limit ({MAX_NOTES})")
                    break

                # Skip hidden and ignored directories
                if item.name.startswith(".") or item.name in IGNORE_DIRS:
                    continue

                if item.is_file():
                    if item.suffix.lower() in extensions:
                        note_meta = self._extract_metadata(item, root_path)
                        if note_meta:
                            notes.append(note_meta)

                elif item.is_dir():
                    # Recurse into subdirectories
                    sub_notes = self._scan_directory(
                        item,
                        root_path=root_path,  # Preserve original root
                        extensions=extensions,
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                    notes.extend(sub_notes)

                    if len(notes) >= MAX_NOTES:
                        break

        except PermissionError:
            logger.warning(f"Permission denied: {path}")

        return notes

    def _extract_metadata(self, file_path: Path, root_path: Path) -> Optional[dict]:
        """
        Extract metadata from a single note file.

        Args:
            file_path: Path to the note file
            root_path: Root notes directory (for topic calculation)

        Returns:
            Metadata dictionary or None if extraction fails

        NOTE: We only extract metadata, NEVER read content.
        """
        try:
            stat = file_path.stat()

            # Derive topic from relative path (folder structure)
            try:
                relative = file_path.parent.relative_to(root_path)
                if relative == Path("."):
                    topic = "root"
                else:
                    # Use first folder level as topic
                    parts = relative.parts
                    topic = parts[0] if parts else "root"
            except ValueError:
                topic = "root"

            return {
                "modified_time": datetime.fromtimestamp(stat.st_mtime),
                "topic": topic,
                "size_bytes": stat.st_size,
            }

        except (OSError, IOError) as e:
            logger.warning(f"Failed to get metadata for {file_path}: {e}")
            return None


def create_markdown_adapter(notes_path: str, include_txt: bool = False) -> MarkdownNotesAdapter:
    """
    Factory function to create a MarkdownNotesAdapter.

    Args:
        notes_path: Path to notes directory
        include_txt: Whether to include .txt files

    Returns:
        Configured MarkdownNotesAdapter
    """
    config = IntegrationConfig(
        integration_type=IntegrationType.NOTES,
        service_name="markdown_notes",
        settings={
            "notes_path": notes_path,
            "include_txt": include_txt,
        },
    )
    return MarkdownNotesAdapter(config)


__all__ = [
    "MarkdownNotesAdapter",
    "create_markdown_adapter",
]
