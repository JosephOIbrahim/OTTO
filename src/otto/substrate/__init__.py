"""
USD Cognitive Substrate Runtime
===============================

Production runtime for the USD Cognitive Substrate specification.
Extracted from cognitive-orchestrator for Orchestra integration.

Modules:
- knowledge: O(1) factual retrieval from USDA knowledge prims
- ewm: External Working Memory (session anchor, time beacon, project friction)
- hardening: Graceful degradation, backup, recovery, handoff detection

ThinkingMachines [He2025] Compliance:
- Deterministic checksums (SHA256, sorted keys)
- Fixed evaluation order
- Consistent degradation behavior
- Reproducible state persistence

Reference: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

from .knowledge import (
    KnowledgePrim,
    KnowledgeRetriever,
    RetrievalResult,
    get_retriever,
    retrieve,
    search,
)

from .ewm import (
    EWMManager,
    EWMState,
    Project,
    ProjectFriction,
    SessionAnchor,
    TimeBeacon,
    get_manager as get_ewm_manager,
)

from .hardening import (
    HandoffDocument,
    HandoffManager,
    StateManager,
    StateResult,
    get_handoff_manager,
    get_state_manager,
)

__all__ = [
    # Knowledge
    "KnowledgePrim",
    "KnowledgeRetriever",
    "RetrievalResult",
    "get_retriever",
    "retrieve",
    "search",
    # EWM
    "EWMManager",
    "EWMState",
    "Project",
    "ProjectFriction",
    "SessionAnchor",
    "TimeBeacon",
    "get_ewm_manager",
    # Hardening
    "HandoffDocument",
    "HandoffManager",
    "StateManager",
    "StateResult",
    "get_handoff_manager",
    "get_state_manager",
]
