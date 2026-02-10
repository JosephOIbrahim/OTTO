"""
Personal Knowledge Store
========================

Bridges the CLI 'remember' command with the Knowledge Retriever.

Stores personal knowledge in JSON format and converts to KnowledgePrims
for unified search across all knowledge sources.

Determinism:
- FIXED confidence for personal knowledge: 0.85
- DETERMINISTIC path generation: /Knowledge/Personal/{id}
- BOUNDED: Max 1000 personal items (configurable)
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List

from .schemas import KnowledgePrim, RetrievalResult

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED - determinism compliant)
# =============================================================================

PERSONAL_CONFIDENCE = 0.85  # Personal knowledge confidence
MAX_PERSONAL_ITEMS = 1000   # Maximum stored items
PERSONAL_FILENAME = "personal.json"
PERSONAL_DOMAIN = "personal"


# =============================================================================
# Personal Knowledge Store
# =============================================================================

class PersonalKnowledgeStore:
    """
    Manages personal knowledge storage and retrieval.

    Integrates with the KnowledgeRetriever to provide unified search
    across both curated USDA prims and personal memories.

    Determinism:
    - All confidence values are FIXED
    - Path generation is DETERMINISTIC
    - Storage is BOUNDED by MAX_PERSONAL_ITEMS
    """

    def __init__(self, otto_dir: Optional[Path] = None):
        """
        Initialize personal knowledge store.

        Args:
            otto_dir: OTTO data directory (default: ~/.otto)
        """
        self.otto_dir = otto_dir or Path.home() / ".otto"
        self._cache: dict[str, KnowledgePrim] = {}
        self._trigger_index: dict[str, list[str]] = {}
        self._loaded = False

    def _get_storage_path(self) -> Path:
        """Get path to personal knowledge file."""
        return self.otto_dir / "knowledge" / PERSONAL_FILENAME

    def _ensure_loaded(self) -> None:
        """Load personal knowledge from disk."""
        if self._loaded:
            return

        self._cache.clear()
        self._trigger_index.clear()

        path = self._get_storage_path()
        if not path.exists():
            self._loaded = True
            return

        try:
            with open(path) as f:
                data = json.load(f)

            for item in data.get("items", []):
                prim = self._item_to_prim(item)
                if prim:
                    self._cache[prim.canonical_path] = prim
                    self._index_triggers(prim)

            logger.debug(f"Loaded {len(self._cache)} personal knowledge items")
        except Exception as e:
            logger.warning(f"Failed to load personal knowledge: {e}")

        self._loaded = True

    def _item_to_prim(self, item: dict[str, Any]) -> Optional[KnowledgePrim]:
        """Convert personal item to KnowledgePrim."""
        item_id = item.get("id", "")
        content = item.get("content", "")
        if not item_id or not content:
            return None

        # Generate triggers from content
        triggers = self._extract_triggers(content)

        # Add explicit tags as triggers
        tags = item.get("tags", [])
        triggers.extend(tags)

        # Generate summary (first 100 chars)
        summary = content[:100] + ("..." if len(content) > 100 else "")

        return KnowledgePrim(
            canonical_path=f"/Knowledge/Personal/{item_id}",
            content=content,
            summary=summary,
            confidence=PERSONAL_CONFIDENCE,
            provenance="personal",
            domains=[PERSONAL_DOMAIN] + tags,
            triggers=triggers,
            requires=[],
            enables=[],
            related_to=[],
            teaching_altitude="Ground",
            key_concepts=tags,
        )

    def _extract_triggers(self, content: str) -> list[str]:
        """Extract search triggers from content.

        Uses word extraction to create searchable terms.
        """
        # Extract words (3+ chars)
        words = re.findall(r'\b\w{3,}\b', content.lower())

        # Remove common stop words
        stop_words = {
            "the", "and", "for", "that", "this", "with", "from",
            "have", "been", "were", "being", "their", "which",
            "will", "would", "could", "should", "about", "into",
        }

        triggers = [w for w in words if w not in stop_words]

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in triggers:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        return unique[:20]  # Limit triggers per item

    def _index_triggers(self, prim: KnowledgePrim) -> None:
        """Add prim triggers to search index."""
        for trigger in prim.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower not in self._trigger_index:
                self._trigger_index[trigger_lower] = []
            self._trigger_index[trigger_lower].append(prim.canonical_path)

    def remember(
        self,
        content: str,
        tags: Optional[List[str]] = None,
    ) -> KnowledgePrim:
        """
        Store new personal knowledge.

        Args:
            content: The knowledge content to store
            tags: Optional tags for categorization

        Returns:
            Created KnowledgePrim

        Raises:
            ValueError: If max items exceeded
        """
        self._ensure_loaded()

        # Check bounds
        if len(self._cache) >= MAX_PERSONAL_ITEMS:
            raise ValueError(f"Maximum personal items ({MAX_PERSONAL_ITEMS}) exceeded")

        # Load existing data
        path = self._get_storage_path()
        data = {"items": []}
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Generate ID
        item_id = f"mem_{len(data['items']) + 1:04d}"

        # Create item
        item = {
            "id": item_id,
            "content": content,
            "created": datetime.now().isoformat(),
            "tags": tags or [],
        }

        data["items"].append(item)

        # Save
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        # Update cache
        prim = self._item_to_prim(item)
        if prim:
            self._cache[prim.canonical_path] = prim
            self._index_triggers(prim)

        logger.info(f"Remembered: {item_id}")
        return prim

    def forget(self, query: str, force: bool = False) -> List[KnowledgePrim]:
        """
        Remove personal knowledge.

        Args:
            query: Content search or exact ID
            force: Remove all matches if True

        Returns:
            List of removed prims
        """
        self._ensure_loaded()

        path = self._get_storage_path()
        if not path.exists():
            return []

        with open(path) as f:
            data = json.load(f)

        query_lower = query.lower()

        # Find matches
        matches = []
        remaining = []
        for item in data.get("items", []):
            is_match = (
                query_lower in item.get("content", "").lower() or
                query == item.get("id", "")
            )
            if is_match:
                matches.append(item)
            else:
                remaining.append(item)

        if not matches:
            return []

        if len(matches) > 1 and not force:
            # Return matches without removing (caller should confirm)
            return [self._item_to_prim(m) for m in matches if self._item_to_prim(m)]

        # Remove matches
        data["items"] = remaining
        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        # Update cache
        removed = []
        for item in matches:
            prim = self._item_to_prim(item)
            if prim:
                removed.append(prim)
                if prim.canonical_path in self._cache:
                    del self._cache[prim.canonical_path]

        logger.info(f"Forgot {len(removed)} items")
        return removed

    def search(self, query: str, max_results: int = 5) -> RetrievalResult:
        """
        Search personal knowledge by triggers.

        Args:
            query: Natural language query
            max_results: Maximum results to return

        Returns:
            RetrievalResult with matching prims
        """
        import time
        start = time.perf_counter()

        self._ensure_loaded()

        query_lower = query.lower()
        words = re.findall(r'\w+', query_lower)

        # Score prims by trigger matches
        scores: dict[str, int] = {}
        for word in words:
            if word in self._trigger_index:
                for path in self._trigger_index[word]:
                    scores[path] = scores.get(path, 0) + 1

            # Partial matches
            for trigger, paths in self._trigger_index.items():
                if word in trigger or trigger in word:
                    for path in paths:
                        scores[path] = scores.get(path, 0) + 1

        # Sort by score
        sorted_paths = sorted(scores.keys(), key=lambda p: scores[p], reverse=True)
        prims = [self._cache[p] for p in sorted_paths[:max_results] if p in self._cache]

        elapsed = (time.perf_counter() - start) * 1000

        return RetrievalResult(
            prims=prims,
            query=query,
            retrieval_method="personal_trigger",
            retrieval_time_ms=elapsed,
        )

    def retrieve(self, path: str) -> RetrievalResult:
        """
        Direct retrieval by canonical path.

        Args:
            path: Path like /Knowledge/Personal/mem_0001

        Returns:
            RetrievalResult with the prim if found
        """
        import time
        start = time.perf_counter()

        self._ensure_loaded()

        prim = self._cache.get(path)
        elapsed = (time.perf_counter() - start) * 1000

        return RetrievalResult(
            prims=[prim] if prim else [],
            query=path,
            retrieval_method="personal_direct",
            retrieval_time_ms=elapsed,
        )

    def list_all(self) -> List[KnowledgePrim]:
        """List all personal knowledge items."""
        self._ensure_loaded()
        return list(self._cache.values())

    @property
    def item_count(self) -> int:
        """Number of stored items."""
        self._ensure_loaded()
        return len(self._cache)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        self._ensure_loaded()
        return {
            "item_count": len(self._cache),
            "trigger_count": len(self._trigger_index),
            "max_items": MAX_PERSONAL_ITEMS,
            "storage_path": str(self._get_storage_path()),
        }


# =============================================================================
# Module-level singleton
# =============================================================================

_store: Optional[PersonalKnowledgeStore] = None


def get_personal_store(otto_dir: Optional[Path] = None) -> PersonalKnowledgeStore:
    """Get or create the singleton personal knowledge store."""
    global _store
    if _store is None:
        _store = PersonalKnowledgeStore(otto_dir)
    return _store


def remember(content: str, tags: Optional[List[str]] = None) -> KnowledgePrim:
    """Store personal knowledge."""
    return get_personal_store().remember(content, tags)


def forget(query: str, force: bool = False) -> List[KnowledgePrim]:
    """Remove personal knowledge."""
    return get_personal_store().forget(query, force)


def search_personal(query: str, max_results: int = 5) -> RetrievalResult:
    """Search personal knowledge."""
    return get_personal_store().search(query, max_results)


__all__ = [
    "PersonalKnowledgeStore",
    "get_personal_store",
    "remember",
    "forget",
    "search_personal",
    "PERSONAL_CONFIDENCE",
    "MAX_PERSONAL_ITEMS",
]
