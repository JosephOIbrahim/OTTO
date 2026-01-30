"""
Deterministic Inference Layer
=============================

Tier 1 & 2 implementation of [He2025]-inspired deterministic inference.

This module provides:

**Tier 1 - API-Maximized Determinism:**
- DeterministicInferenceConfig: Configuration for maximizing inference determinism
- ResponseCache: Deterministic caching with integrity verification
- DeterministicAPIWrapper: Wraps LLM APIs with determinism-maximizing settings
- Backend abstraction for Claude, OpenAI, and local models

**Tier 2 - Verification:**
- DeterminismVerifier: Multi-trial verification for detecting non-determinism
- VerificationResult: Results with divergence analysis and confidence scores
- VerifiedInferenceWrapper: Auto-verification based on criticality

[He2025] Principles Applied:
- Fixed evaluation order for cache key computation (sorted keys)
- No dynamic algorithm switching based on load
- Deterministic serialization throughout
- Response caching for guaranteed reproducibility (after first call)
- Multi-trial verification for probabilistic non-determinism detection

Note: Tier 1 provides API-maximized determinism.
      Tier 2 adds verification (detection of non-determinism).
      Tier 3 (local deterministic inference) provides kernel-level compliance.
See docs/HE2025_KERNEL_COMPLIANCE_STRATEGY.md for full strategy.
"""

from .config import (
    DeterministicInferenceConfig,
    InferenceBackendType,
    DeterminismLevel,
)
from .cache import (
    ResponseCache,
    CacheEntry,
    CacheStats,
    compute_cache_key,
)
from .wrapper import (
    DeterministicAPIWrapper,
    InferenceResult,
    InferenceRequest,
)
from .metrics import (
    InferenceMetrics,
    DeterminismReport,
)
from .verification import (
    DeterminismVerifier,
    VerificationResult,
    VerifiedInferenceWrapper,
    DivergenceAnalysis,
    DivergenceType,
    ConsensusStrategy,
)

__all__ = [
    # Config
    'DeterministicInferenceConfig',
    'InferenceBackendType',
    'DeterminismLevel',
    # Cache
    'ResponseCache',
    'CacheEntry',
    'CacheStats',
    'compute_cache_key',
    # Wrapper
    'DeterministicAPIWrapper',
    'InferenceResult',
    'InferenceRequest',
    # Metrics
    'InferenceMetrics',
    'DeterminismReport',
    # Verification (Tier 2)
    'DeterminismVerifier',
    'VerificationResult',
    'VerifiedInferenceWrapper',
    'DivergenceAnalysis',
    'DivergenceType',
    'ConsensusStrategy',
]

__version__ = '2.0.0'
