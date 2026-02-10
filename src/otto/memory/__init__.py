"""
OTTO Unified Memory Interface
=============================

Single interface for all memory operations across OTTO.
Wraps existing memory systems:
- Pheromone Trails (episodic/procedural)
- Cognitive Substrate (identity/learned)
- LIVRPS Layers (contextual)
- EWM Manager (session state)

Determinism:
- Deterministic trail deposits
- Fixed LIVRPS priority resolution
- Sorted iteration for all queries
"""

from .interface import (
    # Core classes
    OTTOMemory,
    Episode,
    EpisodeQuery,
    Outcome,
    Context,
    ContextDelta,
    Identity,
    Relationship,
    TrailStrength,
    MemoryTier,
    # Knowledge Graph
    KnowledgePrim,
    KnowledgeGraph,
    # Trail Decay
    TrailDecayWorker,
    # Metrics
    MemoryMetrics,
    KnowledgeMetrics,
    DecayMetrics,
    # Module functions
    get_memory,
    # Constants
    AUTO_APPROVE_THRESHOLD,
    LEARNING_THRESHOLD,
    COGNITIVE_TILE_SIZE,
    MEMORY_SEED,
)

__all__ = [
    # Core classes
    "OTTOMemory",
    "Episode",
    "EpisodeQuery",
    "Outcome",
    "Context",
    "ContextDelta",
    "Identity",
    "Relationship",
    "TrailStrength",
    "MemoryTier",
    # Knowledge Graph
    "KnowledgePrim",
    "KnowledgeGraph",
    # Trail Decay
    "TrailDecayWorker",
    # Metrics
    "MemoryMetrics",
    "KnowledgeMetrics",
    "DecayMetrics",
    # Module functions
    "get_memory",
    # Constants
    "AUTO_APPROVE_THRESHOLD",
    "LEARNING_THRESHOLD",
    "COGNITIVE_TILE_SIZE",
    "MEMORY_SEED",
]
