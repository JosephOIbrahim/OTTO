"""
USD Cognitive Substrate Runtime v7.1.0
======================================

Production runtime for the USD Cognitive Substrate specification.
Extracted from cognitive-orchestrator for Orchestra integration.

Version: 7.1.0 (Batch Invariance + Encryption)
Spec: ~/.claude/substrate/cognitive_substrate_v7.usda

Modules:
- knowledge: O(1) factual retrieval from USDA knowledge prims
- ewm: External Working Memory (session anchor, time beacon, project friction)
- hardening: Graceful degradation, backup, recovery, handoff detection
- protection: Encryption and signing for substrate assets (NEW)
- integrity: Merkle tree verification and tamper detection (NEW)

v7.1.0 Batch Invariance Features:
- COGNITIVE_TILE_SIZE = 32 (fixed, never changes)
- Kahan summation for batch-invariant accumulation
- 5 aggregation strategies (max, mean, weighted_mean, decay_mean, threshold_filter)
- Deterministic tie-breaking (sorted_max)
- Sorted collection iteration (deterministic_dict_iter, sorted_set_to_list)

v7.1.0 Encryption Features (NEW):
- AES-256-GCM encryption for sensitive assets
- HMAC-SHA256 signatures for configuration integrity
- Argon2id key derivation from passphrase
- Recovery key support
- Merkle tree for efficient partial verification
- Safety constraint enforcement (floors cannot be lowered)

ThinkingMachines [He2025] Compliance:
- Fixed tile sizes for memory operations
- Deterministic checksums (SHA256, sorted keys)
- Fixed evaluation order (9-phase NEXUS pipeline)
- Kahan summation for FP accumulation
- Consistent degradation behavior
- Reproducible state persistence
- Fixed encryption parameters (AES-256-GCM, 12-byte nonce)

Reference: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

# Substrate version for explicit tracking
SUBSTRATE_VERSION = "7.1.0"

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

from .protection import (
    SubstrateProtection,
    SubstrateProtectionError,
    IntegrityError,
    PermissionDeniedError,
    AssetNotFoundError,
    ProtectionLevel,
    ProtectionStatus,
    Signature,
    SUBSTRATE_ASSETS,
    create_substrate_protection,
    get_protection,
    reset_protection,
)

from .integrity import (
    SubstrateIntegrity,
    IntegrityReport,
    VerificationIssue,
    MerkleNode,
    IntegrityVerificationError,
    SchemaValidationError,
    SafetyConstraintViolation,
    CONFIG_SCHEMAS,
    SAFETY_CONSTRAINTS,
    create_integrity_verifier,
)

__all__ = [
    # Version
    "SUBSTRATE_VERSION",
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
    # Protection (NEW)
    "SubstrateProtection",
    "SubstrateProtectionError",
    "IntegrityError",
    "PermissionDeniedError",
    "AssetNotFoundError",
    "ProtectionLevel",
    "ProtectionStatus",
    "Signature",
    "SUBSTRATE_ASSETS",
    "create_substrate_protection",
    "get_protection",
    "reset_protection",
    # Integrity (NEW)
    "SubstrateIntegrity",
    "IntegrityReport",
    "VerificationIssue",
    "MerkleNode",
    "IntegrityVerificationError",
    "SchemaValidationError",
    "SafetyConstraintViolation",
    "CONFIG_SCHEMAS",
    "SAFETY_CONSTRAINTS",
    "create_integrity_verifier",
]
