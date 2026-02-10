"""
Unified Knowledge Search
========================

Combines USDA prims and personal knowledge into a single search interface.

Provides a unified O(1) retrieval and trigger-based search across:
- Curated USDA knowledge prims (confidence: 0.95)
- Personal memories from 'remember' command (confidence: 0.85)

Determinism:
- DETERMINISTIC result ordering (by confidence, then path)
- FIXED confidence values from sources
- BOUNDED result sets
"""

import time
import logging
from pathlib import Path
from typing import Optional

from .schemas import KnowledgePrim, RetrievalResult
from .retriever import KnowledgeRetriever
from .personal_store import PersonalKnowledgeStore

logger = logging.getLogger(__name__)


class UnifiedKnowledgeSearch:
    """
    Unified search across all knowledge sources.

    Combines:
    - KnowledgeRetriever: USDA prims (high confidence, curated)
    - PersonalKnowledgeStore: User memories (personal, contextual)

    Results are sorted by confidence (descending), then by path (alphabetical).
    """

    def __init__(
        self,
        knowledge_path: Optional[Path] = None,
        otto_dir: Optional[Path] = None,
    ):
        """
        Initialize unified search.

        Args:
            knowledge_path: Path to USDA prims directory
            otto_dir: Path to OTTO data directory (for personal knowledge)
        """
        self.retriever = KnowledgeRetriever(knowledge_path)
        self.personal_store = PersonalKnowledgeStore(otto_dir)

    def search(self, query: str, max_results: int = 10) -> RetrievalResult:
        """
        Search all knowledge sources.

        Args:
            query: Natural language query
            max_results: Maximum results to return

        Returns:
            Combined RetrievalResult sorted by confidence
        """
        start = time.perf_counter()

        # Search both sources
        usda_result = self.retriever.search_by_triggers(query, max_results)
        personal_result = self.personal_store.search(query, max_results)

        # Combine prims
        all_prims = usda_result.prims + personal_result.prims

        # Sort by confidence (desc), then path (asc) for determinism
        sorted_prims = sorted(
            all_prims,
            key=lambda p: (-p.confidence, p.canonical_path)
        )

        # Limit results
        limited = sorted_prims[:max_results]

        elapsed = (time.perf_counter() - start) * 1000

        return RetrievalResult(
            prims=limited,
            query=query,
            retrieval_method="unified",
            retrieval_time_ms=elapsed,
        )

    def retrieve(self, path: str) -> RetrievalResult:
        """
        Direct retrieval by canonical path.

        Checks both USDA prims and personal knowledge.

        Args:
            path: Canonical path (e.g., /Knowledge/USD/LIVRPS or /Knowledge/Personal/mem_0001)

        Returns:
            RetrievalResult with the prim if found
        """
        start = time.perf_counter()

        # Check personal first (common case for direct path)
        if path.startswith("/Knowledge/Personal/"):
            result = self.personal_store.retrieve(path)
            if result.found:
                return result

        # Check USDA prims
        result = self.retriever.retrieve(path)
        if result.found:
            return result

        # Not found in either
        elapsed = (time.perf_counter() - start) * 1000
        return RetrievalResult(
            prims=[],
            query=path,
            retrieval_method="unified_direct",
            retrieval_time_ms=elapsed,
        )

    def get_stats(self) -> dict:
        """Get statistics about all knowledge sources."""
        return {
            "usda_prims": self.retriever.prim_count,
            "usda_triggers": self.retriever.trigger_count,
            "personal_items": self.personal_store.item_count,
            "personal_summary": self.personal_store.get_summary(),
        }


# =============================================================================
# Module-level singleton
# =============================================================================

_unified_search: Optional[UnifiedKnowledgeSearch] = None


def get_unified_search() -> UnifiedKnowledgeSearch:
    """Get or create the singleton unified search."""
    global _unified_search
    if _unified_search is None:
        _unified_search = UnifiedKnowledgeSearch()
    return _unified_search


def search_all(query: str, max_results: int = 10) -> RetrievalResult:
    """Search all knowledge sources."""
    return get_unified_search().search(query, max_results)


def retrieve_any(path: str) -> RetrievalResult:
    """Direct retrieval from any knowledge source."""
    return get_unified_search().retrieve(path)


__all__ = [
    "UnifiedKnowledgeSearch",
    "get_unified_search",
    "search_all",
    "retrieve_any",
]
