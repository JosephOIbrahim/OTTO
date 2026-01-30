"""
Deterministic Inference Layer
=============================

Tier 1 implementation of [He2025]-inspired deterministic inference.

This module provides:
- DeterministicInferenceConfig: Configuration for maximizing inference determinism
- ResponseCache: Deterministic caching with integrity verification
- DeterministicAPIWrapper: Wraps LLM APIs with determinism-maximizing settings
- Backend abstraction for Claude, OpenAI, and local models

[He2025] Principles Applied:
- Fixed evaluation order for cache key computation (sorted keys)
- No dynamic algorithm switching based on load
- Deterministic serialization throughout
- Response caching for guaranteed reproducibility (after first call)

Note: This is Tier 1 compliance (API-maximized determinism).
True kernel-level compliance requires Tier 3 (local deterministic inference).
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
]

__version__ = '1.0.0'
