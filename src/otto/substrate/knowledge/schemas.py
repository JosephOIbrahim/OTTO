"""
Knowledge Prims Schemas

Pydantic models for knowledge prim storage and retrieval.
Part of USD Cognitive Substrate production hardening.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgePrim:
    """Single knowledge prim containing factual information.

    Attributes:
        canonical_path: Unique USD-style path (e.g., /Knowledge/USD/LIVRPS)
        content: Full knowledge content
        summary: Brief summary for quick display
        confidence: Trust level (0.0 to 1.0, typically 0.95 for curated)
        provenance: Source of knowledge (e.g., 'pixar_usd_docs', 'substrate_v5')
        domains: Categories this knowledge belongs to
        triggers: Keywords that should match this prim
        requires: Paths to prerequisite prims
        enables: Paths to prims this enables
        related_to: Paths to related prims
        teaching_altitude: Recommended abstraction level for teaching
        key_concepts: Main concepts covered
    """
    canonical_path: str
    content: str
    summary: str
    confidence: float = 0.95
    provenance: str = "unknown"
    domains: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    enables: list[str] = field(default_factory=list)
    related_to: list[str] = field(default_factory=list)
    teaching_altitude: str = "Ground"
    key_concepts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'canonical_path': self.canonical_path,
            'content': self.content,
            'summary': self.summary,
            'confidence': self.confidence,
            'provenance': self.provenance,
            'domains': self.domains,
            'triggers': self.triggers,
            'requires': self.requires,
            'enables': self.enables,
            'related_to': self.related_to,
            'teaching_altitude': self.teaching_altitude,
            'key_concepts': self.key_concepts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgePrim:
        """Create from dictionary."""
        return cls(
            canonical_path=data.get('canonical_path', ''),
            content=data.get('content', ''),
            summary=data.get('summary', ''),
            confidence=data.get('confidence', 0.95),
            provenance=data.get('provenance', 'unknown'),
            domains=data.get('domains', []),
            triggers=data.get('triggers', []),
            requires=data.get('requires', []),
            enables=data.get('enables', []),
            related_to=data.get('related_to', []),
            teaching_altitude=data.get('teaching_altitude', 'Ground'),
            key_concepts=data.get('key_concepts', []),
        )


@dataclass
class RetrievalResult:
    """Result of a knowledge retrieval operation.

    Attributes:
        prims: List of matching prims
        query: Original query string
        retrieval_method: How prims were found ('direct', 'trigger', 'relationship')
        cache_hit: Whether result came from cache
        retrieval_time_ms: Time taken for retrieval
    """
    prims: list[KnowledgePrim] = field(default_factory=list)
    query: str = ""
    retrieval_method: str = "direct"
    cache_hit: bool = False
    retrieval_time_ms: float = 0.0

    @property
    def found(self) -> bool:
        """Whether any prims were found."""
        return len(self.prims) > 0

    @property
    def top_confidence(self) -> float:
        """Highest confidence among found prims."""
        if not self.prims:
            return 0.0
        return max(p.confidence for p in self.prims)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'prims': [p.to_dict() for p in self.prims],
            'query': self.query,
            'retrieval_method': self.retrieval_method,
            'cache_hit': self.cache_hit,
            'retrieval_time_ms': self.retrieval_time_ms,
            'found': self.found,
            'top_confidence': self.top_confidence,
        }
