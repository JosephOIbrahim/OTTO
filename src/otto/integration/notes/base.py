"""
Notes Adapter Base
==================

Base class for notes integrations.

Provides notes context for cognitive state without
exposing note content (privacy-first).

What we extract:
- Note counts and distribution
- Topic categories (from folder structure)
- Activity recency
- Search availability

What we NEVER extract:
- Note titles or content
- Personal information
- Specific file paths
"""

import logging
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional

from ..adapter import IntegrationAdapter
from ..models import IntegrationConfig, IntegrationType, NotesContext

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED - ThinkingMachines compliant)
# =============================================================================

# Richness thresholds
SPARSE_THRESHOLD = 10       # < 10 notes = sparse
MODERATE_THRESHOLD = 50     # 10-50 notes = moderate
# > 50 notes = rich


# =============================================================================
# Notes Adapter Base
# =============================================================================

class NotesAdapter(IntegrationAdapter[NotesContext]):
    """
    Base class for notes integrations.

    Subclasses implement service-specific note discovery and
    metadata extraction.

    Example:
        class ObsidianAdapter(NotesAdapter):
            async def _fetch_raw_notes(self) -> List[dict]:
                # Discover notes in vault
                ...
    """

    SERVICE_NAME = "notes_base"
    INTEGRATION_TYPE = IntegrationType.NOTES
    SUPPORTS_WRITE = False  # Notes are read-only in Phase 5

    def __init__(self, config: IntegrationConfig):
        """
        Initialize notes adapter.

        Args:
            config: Integration configuration
        """
        super().__init__(config)

    # =========================================================================
    # Abstract Methods (Subclasses Implement)
    # =========================================================================

    @abstractmethod
    async def _fetch_raw_notes(self) -> List[dict]:
        """
        Fetch raw note metadata.

        Returns:
            List of note dictionaries with:
            - modified_time: datetime
            - topic: str (folder/category)
            - size_bytes: int (optional)

        NOTE: Do NOT include note content or titles.
        """
        pass

    # =========================================================================
    # IntegrationAdapter Implementation
    # =========================================================================

    async def _fetch_context(self) -> NotesContext:
        """
        Fetch notes context from adapter.

        Returns:
            NotesContext with aggregated metadata
        """
        raw_notes = await self._fetch_raw_notes()
        return self._build_context(raw_notes)

    def _create_empty_context(self) -> NotesContext:
        """Create empty context when service unavailable."""
        return NotesContext.empty()

    # =========================================================================
    # Context Building
    # =========================================================================

    def _build_context(self, raw_notes: List[dict]) -> NotesContext:
        """
        Build NotesContext from raw note metadata.

        Args:
            raw_notes: List of note metadata dicts

        Returns:
            Aggregated NotesContext
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        total = len(raw_notes)
        modified_today = 0
        modified_week = 0
        topic_counts = {}
        most_recent = None

        for note in raw_notes:
            # Count modifications
            mod_time = note.get("modified_time")
            if mod_time:
                if isinstance(mod_time, str):
                    try:
                        mod_time = datetime.fromisoformat(mod_time)
                    except ValueError:
                        mod_time = None

                if mod_time:
                    if mod_time >= today_start:
                        modified_today += 1
                    if mod_time >= week_start:
                        modified_week += 1

                    if most_recent is None or mod_time > most_recent:
                        most_recent = mod_time

            # Count topics (from folder structure)
            topic = note.get("topic", "uncategorized")
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Calculate richness level
        if total < SPARSE_THRESHOLD:
            richness = "sparse"
        elif total < MODERATE_THRESHOLD:
            richness = "moderate"
        else:
            richness = "rich"

        # Calculate hours since most recent activity
        most_recent_hours = None
        if most_recent:
            delta = now - most_recent
            most_recent_hours = int(delta.total_seconds() / 3600)

        return NotesContext(
            total_notes=total,
            notes_modified_today=modified_today,
            notes_modified_this_week=modified_week,
            topic_counts=topic_counts,
            has_searchable_notes=total > 0,
            most_recent_activity_hours=most_recent_hours,
            richness_level=richness,
        )


__all__ = [
    "NotesAdapter",
    "SPARSE_THRESHOLD",
    "MODERATE_THRESHOLD",
]
