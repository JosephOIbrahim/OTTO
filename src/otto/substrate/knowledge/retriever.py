"""
Knowledge Prim Retriever

O(1) factual knowledge retrieval from USD-style knowledge prims.
Provides fast path for factual queries before LLM inference.

Part of USD Cognitive Substrate production hardening.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

from .schemas import KnowledgePrim, RetrievalResult

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """O(1) knowledge prim retrieval engine.

    Provides:
    - Direct path lookup (O(1))
    - Trigger-based search
    - Relationship traversal
    - Caching for performance

    Example:
        >>> retriever = KnowledgeRetriever()
        >>> retriever.load_from_directory("~/.claude/substrate/knowledge/prims")
        >>> result = retriever.search("what is LIVRPS")
        >>> if result.found:
        ...     print(result.prims[0].summary)
    """

    def __init__(self, knowledge_path: Path | str | None = None):
        """Initialize retriever.

        Args:
            knowledge_path: Path to knowledge prims directory.
                           Defaults to package's prims directory.
        """
        if knowledge_path is None:
            knowledge_path = Path(__file__).parent / "prims"
        self.knowledge_path = Path(knowledge_path)

        self._cache: dict[str, KnowledgePrim] = {}
        self._trigger_index: dict[str, list[str]] = {}
        self._loaded = False
        self._load_time_ms = 0.0

    def _ensure_loaded(self) -> None:
        """Lazy load knowledge prims on first access."""
        if self._loaded:
            return

        start = time.perf_counter()

        # Load all .usda files in prims directory
        if self.knowledge_path.exists():
            for filepath in self.knowledge_path.glob("*.usda"):
                self._load_file(filepath)

        self._loaded = True
        self._load_time_ms = (time.perf_counter() - start) * 1000
        logger.info(f"Knowledge loaded: {len(self._cache)} prims in {self._load_time_ms:.2f}ms")

    def _load_file(self, filepath: Path) -> None:
        """Load knowledge prims from a USDA file."""
        try:
            content = filepath.read_text(encoding='utf-8')
            self._parse_content(content)
        except Exception as e:
            logger.warning(f"Failed to load knowledge file {filepath}: {e}")

    def _parse_content(self, content: str) -> None:
        """Parse USDA content and extract knowledge prims."""
        # Pattern for prim blocks with KnowledgePrimAPI
        prim_pattern = re.compile(
            r'def\s+"(\w+)"\s*\(\s*prepend\s+apiSchemas\s*=\s*\["KnowledgePrimAPI"\]\s*\)\s*\{(.*?)\n\s*\}',
            re.DOTALL
        )

        for match in prim_pattern.finditer(content):
            prim_name = match.group(1)
            prim_body = match.group(2)

            try:
                prim = self._parse_prim_body(prim_name, prim_body)
                if prim:
                    self._cache[prim.canonical_path] = prim
                    self._index_triggers(prim)
            except Exception as e:
                logger.warning(f"Failed to parse prim {prim_name}: {e}")

    def _parse_prim_body(self, name: str, body: str) -> KnowledgePrim | None:
        """Parse prim body into KnowledgePrim."""
        def extract_string(key: str) -> str:
            pattern = rf'custom\s+string\s+{key}\s*=\s*"""(.*?)"""'
            match = re.search(pattern, body, re.DOTALL)
            if match:
                return match.group(1).strip()
            # Try single-line string
            pattern = rf'custom\s+string\s+{key}\s*=\s*"([^"]*)"'
            match = re.search(pattern, body)
            return match.group(1) if match else ""

        def extract_float(key: str) -> float:
            pattern = rf'custom\s+float\s+{key}\s*=\s*([\d.]+)'
            match = re.search(pattern, body)
            return float(match.group(1)) if match else 0.95

        def extract_string_array(key: str) -> list[str]:
            pattern = rf'custom\s+string\[\]\s+{key}\s*=\s*\[(.*?)\]'
            match = re.search(pattern, body, re.DOTALL)
            if not match:
                return []
            array_content = match.group(1)
            items = re.findall(r'"([^"]*)"', array_content)
            return items

        canonical_path = extract_string("canonical_path")
        if not canonical_path:
            return None

        return KnowledgePrim(
            canonical_path=canonical_path,
            content=extract_string("content"),
            summary=extract_string("summary"),
            confidence=extract_float("confidence"),
            provenance=extract_string("provenance"),
            domains=extract_string_array("domains"),
            triggers=extract_string_array("triggers"),
            requires=extract_string_array("requires"),
            enables=extract_string_array("enables"),
            related_to=extract_string_array("related_to"),
            teaching_altitude=extract_string("teaching_altitude"),
            key_concepts=extract_string_array("key_concepts"),
        )

    def _index_triggers(self, prim: KnowledgePrim) -> None:
        """Add prim triggers to search index."""
        for trigger in prim.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower not in self._trigger_index:
                self._trigger_index[trigger_lower] = []
            self._trigger_index[trigger_lower].append(prim.canonical_path)

    def retrieve(self, path: str) -> RetrievalResult:
        """Direct O(1) retrieval by canonical path.

        Args:
            path: Canonical path like "/Knowledge/USD/LIVRPS"

        Returns:
            RetrievalResult with the prim if found
        """
        self._ensure_loaded()
        start = time.perf_counter()

        prim = self._cache.get(path)
        elapsed = (time.perf_counter() - start) * 1000

        return RetrievalResult(
            prims=[prim] if prim else [],
            query=path,
            retrieval_method="direct",
            retrieval_time_ms=elapsed,
        )

    def search_by_triggers(self, query: str, max_results: int = 5) -> RetrievalResult:
        """Search prims by trigger keywords.

        Args:
            query: Natural language query
            max_results: Maximum number of results

        Returns:
            RetrievalResult with matching prims
        """
        self._ensure_loaded()
        start = time.perf_counter()

        # Normalize query
        query_lower = query.lower()
        words = re.findall(r'\w+', query_lower)

        # Score prims by trigger matches
        scores: dict[str, int] = {}
        for word in words:
            if word in self._trigger_index:
                for path in self._trigger_index[word]:
                    scores[path] = scores.get(path, 0) + 1

            # Also check partial matches
            for trigger, paths in self._trigger_index.items():
                if word in trigger or trigger in word:
                    for path in paths:
                        scores[path] = scores.get(path, 0) + 1

        # Sort by score and return top results
        sorted_paths = sorted(scores.keys(), key=lambda p: scores[p], reverse=True)
        prims = [self._cache[p] for p in sorted_paths[:max_results] if p in self._cache]

        elapsed = (time.perf_counter() - start) * 1000

        return RetrievalResult(
            prims=prims,
            query=query,
            retrieval_method="trigger",
            retrieval_time_ms=elapsed,
        )

    def get_related(self, path: str, max_depth: int = 2) -> RetrievalResult:
        """Get related prims via relationship traversal.

        Args:
            path: Starting prim path
            max_depth: Maximum traversal depth

        Returns:
            RetrievalResult with related prims
        """
        self._ensure_loaded()
        start = time.perf_counter()

        visited: set[str] = set()
        related: list[KnowledgePrim] = []

        def traverse(current_path: str, depth: int) -> None:
            if depth > max_depth or current_path in visited:
                return
            visited.add(current_path)

            prim = self._cache.get(current_path)
            if not prim:
                return

            if current_path != path:
                related.append(prim)

            # Traverse relationships
            for related_path in prim.related_to + prim.enables + prim.requires:
                traverse(related_path, depth + 1)

        traverse(path, 0)
        elapsed = (time.perf_counter() - start) * 1000

        return RetrievalResult(
            prims=related,
            query=path,
            retrieval_method="relationship",
            retrieval_time_ms=elapsed,
        )

    @property
    def prim_count(self) -> int:
        """Number of loaded prims."""
        self._ensure_loaded()
        return len(self._cache)

    @property
    def trigger_count(self) -> int:
        """Number of indexed triggers."""
        self._ensure_loaded()
        return len(self._trigger_index)


# Module-level singleton
_retriever: KnowledgeRetriever | None = None


def get_retriever() -> KnowledgeRetriever:
    """Get or create the singleton retriever."""
    global _retriever
    if _retriever is None:
        _retriever = KnowledgeRetriever()
    return _retriever


def retrieve(path: str) -> RetrievalResult:
    """Direct O(1) retrieval by path."""
    return get_retriever().retrieve(path)


def search(query: str, max_results: int = 5) -> RetrievalResult:
    """Search by trigger keywords."""
    return get_retriever().search_by_triggers(query, max_results)
