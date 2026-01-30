"""
Deterministic Inference Layer
=============================

Tier 1, 2 & 3 implementation of [He2025]-inspired deterministic inference.

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

**Tier 3 - Kernel-Level Determinism:**
- He2025KernelConfig: [He2025]-compliant kernel configuration
- DeterministicEnvironment: CUDA environment management for determinism
- ServerConfigValidator: Validates server determinism settings
- DeterministicVLLMBackend: Local inference with kernel-level guarantees

[He2025] Principles Applied:
- Fixed evaluation order for cache key computation (sorted keys)
- No dynamic algorithm switching based on load
- Deterministic serialization throughout
- Response caching for guaranteed reproducibility (after first call)
- Multi-trial verification for probabilistic non-determinism detection
- Batch size = 1 for kernel-level determinism (Tier 3)
- CUDA deterministic operations enabled (Tier 3)

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
from .kernel import (
    He2025KernelConfig,
    DeterminismMode,
    DeterministicEnvironment,
    ServerConfigValidator,
    ServerValidationResult,
    DeterministicVLLMBackend,
    DeterministicLocalBackend,
    HE2025_STRICT,
    HE2025_WITH_FLASH_ATTENTION,
    HE2025_INT8,
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
    # Kernel-Level (Tier 3)
    'He2025KernelConfig',
    'DeterminismMode',
    'DeterministicEnvironment',
    'ServerConfigValidator',
    'ServerValidationResult',
    'DeterministicVLLMBackend',
    'DeterministicLocalBackend',
    'HE2025_STRICT',
    'HE2025_WITH_FLASH_ATTENTION',
    'HE2025_INT8',
]

__version__ = '3.0.0'
