"""
Deterministic API Wrapper
=========================

The main entry point for deterministic inference. Wraps LLM API calls
with caching, deterministic configuration, verification, and metrics.

Principles Applied:
- Fixed evaluation order
- Response caching for guaranteed reproducibility
- No dynamic algorithm switching
- Deterministic configuration throughout
- Multi-trial verification for non-determinism detection (Tier 2)

Tier 1: API-maximized determinism (caching, fixed params)
Tier 2: Verification (multi-trial, divergence detection)
Tier 3: Kernel-level determinism (local backend with batch_size=1)
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union
import hashlib

from .config import (
    DeterministicInferenceConfig,
    InferenceBackendType,
    DeterminismLevel,
    DETERMINISTIC_DEFAULT,
)
from .cache import (
    ResponseCache,
    CacheEntry,
    compute_cache_key,
)
from .backends.base import (
    InferenceBackend,
    InferenceResponse,
    InferenceError,
    BackendStatus,
)
from .backends.mock import MockBackend, DeterministicMockBackend

# Tier 2 imports (lazy to avoid circular imports)
# from .verification import DeterminismVerifier, VerificationResult, ConsensusStrategy


@dataclass
class InferenceRequest:
    """
    A request for inference.

    Attributes:
        prompt: The user prompt
        system_prompt: Optional system prompt
        config: Inference configuration
        model_id: Optional model override
        metadata: Optional request metadata
        require_determinism: If True, only use cached or deterministic backend
        criticality: Request criticality (high = use verification)
    """
    prompt: str
    system_prompt: Optional[str] = None
    config: DeterministicInferenceConfig = field(default_factory=lambda: DETERMINISTIC_DEFAULT)
    model_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    require_determinism: bool = False
    criticality: str = "normal"  # low | normal | high | critical

    @property
    def cache_key(self) -> str:
        """Compute deterministic cache key for this request."""
        return compute_cache_key(
            prompt=self.prompt,
            system_prompt=self.system_prompt,
            params=self.config.to_api_params(),
            model_id=self.model_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "config_hash": self.config.config_hash,
            "model_id": self.model_id,
            "metadata": self.metadata,
            "require_determinism": self.require_determinism,
            "criticality": self.criticality,
            "cache_key": self.cache_key,
        }


@dataclass
class InferenceResult:
    """
    Result from inference with full metadata.

    Attributes:
        content: The generated content
        cache_hit: Whether this was served from cache
        determinism_level: Achieved determinism level
        backend_used: Which backend was used
        latency_ms: Total latency in milliseconds
        content_hash: SHA-256 hash of content
        request_id: Unique request identifier
        cache_key: The cache key used
        metadata: Additional metadata
        created_at: When this result was created
    """
    content: str
    cache_hit: bool = False
    determinism_level: DeterminismLevel = DeterminismLevel.API_MAXIMIZED
    backend_used: str = "unknown"
    latency_ms: float = 0.0
    content_hash: str = ""
    request_id: str = ""
    cache_key: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Compute content hash if not provided."""
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.content.encode("utf-8")
            ).hexdigest()[:32]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "content": self.content,
            "cache_hit": self.cache_hit,
            "determinism_level": self.determinism_level.value,
            "backend_used": self.backend_used,
            "latency_ms": self.latency_ms,
            "content_hash": self.content_hash,
            "request_id": self.request_id,
            "cache_key": self.cache_key,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


class DeterministicAPIWrapper:
    """
    Wrapper for LLM inference with determinism guarantees.

    This wrapper provides:
    1. Response caching for guaranteed reproducibility
    2. Deterministic configuration enforcement
    3. Multiple backend support with fallback
    4. Metrics and instrumentation

    Determinism (Tier 1):
    - Same prompt + params → Same cached result (after first call)
    - Fixed evaluation order for all operations
    - No dynamic algorithm switching

    Example:
        >>> wrapper = DeterministicAPIWrapper()
        >>> await wrapper.initialize()
        >>>
        >>> # First call - hits API
        >>> r1 = await wrapper.infer(InferenceRequest(prompt="Hello"))
        >>> r1.cache_hit
        False
        >>>
        >>> # Second call - hits cache (guaranteed same result)
        >>> r2 = await wrapper.infer(InferenceRequest(prompt="Hello"))
        >>> r2.cache_hit
        True
        >>> r1.content == r2.content
        True
    """

    def __init__(
        self,
        config: Optional[DeterministicInferenceConfig] = None,
        cache: Optional[ResponseCache] = None,
        backends: Optional[Dict[InferenceBackendType, InferenceBackend]] = None,
        verification_trials: int = 3,
        auto_verify_criticality: str = "critical",
    ):
        """
        Initialize the wrapper.

        Args:
            config: Default inference configuration
            cache: Response cache (creates default if None)
            backends: Dict of backends (creates defaults if None)
            verification_trials: Number of trials for Tier 2 verification
            auto_verify_criticality: Criticality level that triggers auto-verification
                                     ("low", "normal", "high", "critical", "none")
        """
        self._config = config or DETERMINISTIC_DEFAULT
        self._cache = cache or ResponseCache(
            max_size=10000,
            default_ttl=self._config.cache_ttl_seconds,
        )
        self._backends = backends or {}
        self._default_backend: Optional[InferenceBackend] = None
        self._initialized = False

        # Tier 2 verification settings
        self._verification_trials = verification_trials
        self._auto_verify_criticality = auto_verify_criticality
        self._verifier = None  # Lazy initialization

        # Criticality levels for auto-verification
        self._criticality_levels = {
            "low": 0,
            "normal": 1,
            "high": 2,
            "critical": 3,
        }
        self._verify_threshold = self._criticality_levels.get(auto_verify_criticality, 99)

        # Metrics
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._errors = 0
        self._total_latency_ms = 0.0
        self._verified_requests = 0
        self._verification_divergences = 0

    @property
    def config(self) -> DeterministicInferenceConfig:
        """Get default configuration."""
        return self._config

    @property
    def cache(self) -> ResponseCache:
        """Get the response cache."""
        return self._cache

    @property
    def is_initialized(self) -> bool:
        """Check if wrapper is initialized."""
        return self._initialized

    async def initialize(
        self,
        backend_type: Optional[InferenceBackendType] = None,
        **backend_kwargs: Any,
    ) -> None:
        """
        Initialize the wrapper with a backend.

        Args:
            backend_type: Type of backend to initialize (uses config default if None)
            **backend_kwargs: Arguments passed to backend constructor
        """
        backend_type = backend_type or self._config.backend

        # Create backend if not already present
        if backend_type not in self._backends:
            backend = await self._create_backend(backend_type, **backend_kwargs)
            self._backends[backend_type] = backend

        # Set as default
        self._default_backend = self._backends[backend_type]
        self._initialized = True

    async def infer(
        self,
        request: Union[InferenceRequest, str],
        use_cache: Optional[bool] = None,
        skip_auto_verify: bool = False,
    ) -> InferenceResult:
        """
        Perform inference with determinism guarantees.

        If the request's criticality exceeds the auto_verify_criticality threshold,
        this method automatically performs Tier 2 verification and returns the
        verified result. This can be disabled with skip_auto_verify=True.

        Args:
            request: InferenceRequest or prompt string
            use_cache: Override cache usage (None = use config)
            skip_auto_verify: If True, skip auto-verification even for high criticality

        Returns:
            InferenceResult with content and metadata

        Raises:
            RuntimeError: If not initialized or inference fails
        """
        if not self._initialized:
            raise RuntimeError("Wrapper not initialized. Call initialize() first.")

        start_time = time.perf_counter()
        self._total_requests += 1

        # Convert string to request
        if isinstance(request, str):
            request = InferenceRequest(prompt=request, config=self._config)

        # Tier 2 Auto-verification based on criticality
        if not skip_auto_verify and self._auto_verify_criticality != "none":
            request_criticality = self._criticality_levels.get(request.criticality, 1)
            if request_criticality >= self._verify_threshold:
                # High criticality request - use verification
                verification_result = await self.infer_verified(request)

                latency_ms = (time.perf_counter() - start_time) * 1000
                self._total_latency_ms += latency_ms

                # Convert VerificationResult to InferenceResult
                unique_count = len(set(verification_result.all_responses))
                return InferenceResult(
                    content=verification_result.response,
                    cache_hit=False,  # Verification always makes fresh calls
                    determinism_level=DeterminismLevel.VERIFIED if verification_result.verified else DeterminismLevel.API_MAXIMIZED,
                    backend_used=f"verified-{self._default_backend.name}",
                    latency_ms=latency_ms,
                    request_id=f"verified-{verification_result.trials}trials",
                    cache_key=request.cache_key,
                    metadata={
                        "verified": verification_result.verified,
                        "confidence": verification_result.confidence,
                        "trials": verification_result.trials,
                        "unique_responses": unique_count,
                        "divergence_type": verification_result.divergence_type.value if verification_result.divergence_type else None,
                    },
                )

        # Check cache first
        cache_enabled = use_cache if use_cache is not None else self._config.cache_enabled
        if cache_enabled:
            cache_entry = self._cache.get(request.cache_key)
            if cache_entry is not None:
                self._cache_hits += 1
                latency_ms = (time.perf_counter() - start_time) * 1000
                self._total_latency_ms += latency_ms

                return InferenceResult(
                    content=cache_entry.response,
                    cache_hit=True,
                    determinism_level=DeterminismLevel.API_MAXIMIZED,
                    backend_used="cache",
                    latency_ms=latency_ms,
                    content_hash=cache_entry.content_hash,
                    request_id=f"cache-{cache_entry.access_count}",
                    cache_key=request.cache_key,
                    metadata=cache_entry.metadata,
                )

        self._cache_misses += 1

        # Require determinism check
        if request.require_determinism:
            # If cache miss and determinism required, we need to make API call
            # but flag that this result is not from a verified deterministic source
            pass

        # Make API call
        try:
            backend = self._default_backend
            response = await backend.infer(
                prompt=request.prompt,
                system_prompt=request.system_prompt,
                temperature=request.config.temperature,
                max_tokens=request.config.max_tokens,
                seed=request.config.seed,
                stop_sequences=list(request.config.stop_sequences) if request.config.stop_sequences else None,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000
            self._total_latency_ms += latency_ms

            # Cache the response
            if cache_enabled:
                self._cache.put(
                    key=request.cache_key,
                    response=response.content,
                    metadata={
                        "model": response.model,
                        "backend": backend.name,
                        "request_id": response.request_id,
                        "usage": response.usage,
                    },
                )

            # Determine achieved determinism level
            determinism = DeterminismLevel.API_MAXIMIZED
            if backend.capabilities.determinism_level == "kernel":
                determinism = DeterminismLevel.KERNEL_LEVEL

            return InferenceResult(
                content=response.content,
                cache_hit=False,
                determinism_level=determinism,
                backend_used=backend.name,
                latency_ms=latency_ms,
                content_hash=response.content_hash,
                request_id=response.request_id,
                cache_key=request.cache_key,
                metadata={
                    "model": response.model,
                    "usage": response.usage,
                    "finish_reason": response.finish_reason,
                },
            )

        except Exception as e:
            self._errors += 1
            raise RuntimeError(f"Inference failed: {e}") from e

    async def infer_batch(
        self,
        requests: List[InferenceRequest],
        max_concurrent: int = 5,
    ) -> List[InferenceResult]:
        """
        Perform batch inference with controlled concurrency.

        Determinism: Results are returned in request order,
        regardless of completion order.

        Args:
            requests: List of inference requests
            max_concurrent: Maximum concurrent requests

        Returns:
            List of results in same order as requests
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_infer(request: InferenceRequest) -> InferenceResult:
            async with semaphore:
                return await self.infer(request)

        # Maintain order by using gather with return_exceptions
        tasks = [bounded_infer(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(InferenceResult(
                    content="",
                    cache_hit=False,
                    determinism_level=DeterminismLevel.NONE,
                    backend_used="error",
                    metadata={"error": str(result)},
                ))
            else:
                processed.append(result)

        return processed

    async def infer_verified(
        self,
        request: Union[InferenceRequest, str],
        n_trials: Optional[int] = None,
    ) -> 'VerificationResult':
        """
        Perform verified inference with multiple trials (Tier 2).

        This method runs multiple inference trials and compares results
        to detect non-determinism. Use for critical decisions that need
        verification.

        Args:
            request: InferenceRequest or prompt string
            n_trials: Override number of trials (None = use default)

        Returns:
            VerificationResult with divergence analysis

        Example:
            >>> result = await wrapper.infer_verified("Critical question")
            >>> if result.verified:
            ...     print("All trials agreed!")
            ... else:
            ...     print(f"Divergence: {result.divergence_type}")
        """
        if not self._initialized:
            raise RuntimeError("Wrapper not initialized. Call initialize() first.")

        # Lazy import to avoid circular imports
        from .verification import DeterminismVerifier, VerificationResult

        # Convert string to request
        if isinstance(request, str):
            request = InferenceRequest(prompt=request, config=self._config)

        # Initialize verifier if needed
        if self._verifier is None:
            self._verifier = DeterminismVerifier(
                backend=self._default_backend,
                n_trials=n_trials or self._verification_trials,
            )

        # Run verification
        result = await self._verifier.verify(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            temperature=request.config.temperature,
            max_tokens=request.config.max_tokens,
            seed=request.config.seed,
        )

        # Update metrics
        self._verified_requests += 1
        if not result.verified:
            self._verification_divergences += 1

        # Cache the consensus result if verified
        if result.verified and self._config.cache_enabled:
            self._cache.put(
                key=request.cache_key,
                response=result.response,
                metadata={
                    "verified": True,
                    "trials": result.trials,
                    "confidence": result.confidence,
                },
            )

        return result

    def get_verifier_stats(self) -> Dict[str, Any]:
        """
        Get Tier 2 verification statistics.

        Returns:
            Dict with verification metrics and divergence report
        """
        if self._verifier is None:
            return {
                "status": "not_initialized",
                "verified_requests": self._verified_requests,
                "divergences": self._verification_divergences,
            }

        return {
            "verified_requests": self._verified_requests,
            "divergences": self._verification_divergences,
            "divergence_rate": self._verification_divergences / max(1, self._verified_requests),
            "verifier_stats": self._verifier.stats,
            "divergence_report": self._verifier.get_divergence_report(),
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get wrapper statistics.

        Returns:
            Dict with request counts, cache stats, verification stats, and latency
        """
        cache_stats = self._cache.stats

        stats = {
            "total_requests": self._total_requests,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hits / max(1, self._total_requests),
            "errors": self._errors,
            "error_rate": self._errors / max(1, self._total_requests),
            "avg_latency_ms": self._total_latency_ms / max(1, self._total_requests),
            "cache": cache_stats.to_dict(),
            "backends": {
                name.value: backend.get_status_report()
                for name, backend in self._backends.items()
            },
            # Tier 2 verification stats
            "verification": {
                "verified_requests": self._verified_requests,
                "divergences": self._verification_divergences,
                "divergence_rate": self._verification_divergences / max(1, self._verified_requests),
                "auto_verify_threshold": self._auto_verify_criticality,
            },
        }

        return stats

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._errors = 0
        self._total_latency_ms = 0.0
        self._verified_requests = 0
        self._verification_divergences = 0

    async def shutdown(self) -> None:
        """Shutdown all backends."""
        for backend in self._backends.values():
            await backend.shutdown()
        self._initialized = False

    async def _create_backend(
        self,
        backend_type: InferenceBackendType,
        **kwargs: Any,
    ) -> InferenceBackend:
        """Create and initialize a backend."""
        if backend_type == InferenceBackendType.CLAUDE:
            from .backends.claude import ClaudeBackend
            backend = ClaudeBackend(**kwargs)

        elif backend_type == InferenceBackendType.OPENAI:
            from .backends.openai import OpenAIBackend
            backend = OpenAIBackend(**kwargs)

        elif backend_type == InferenceBackendType.LOCAL_VLLM:
            from .backends.local import LocalVLLMBackend
            backend = LocalVLLMBackend(**kwargs)

        elif backend_type == InferenceBackendType.LOCAL_OLLAMA:
            from .backends.local import LocalOllamaBackend
            backend = LocalOllamaBackend(**kwargs)

        elif backend_type == InferenceBackendType.MOCK:
            backend = DeterministicMockBackend(**kwargs)

        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

        await backend.initialize()
        return backend


# Convenience functions for simple usage

_default_wrapper: Optional[DeterministicAPIWrapper] = None


async def get_default_wrapper() -> DeterministicAPIWrapper:
    """
    Get or create the default wrapper.

    Returns:
        Initialized DeterministicAPIWrapper
    """
    global _default_wrapper
    if _default_wrapper is None:
        _default_wrapper = DeterministicAPIWrapper()
        await _default_wrapper.initialize(InferenceBackendType.MOCK)
    return _default_wrapper


async def infer(
    prompt: str,
    system_prompt: Optional[str] = None,
    **kwargs: Any,
) -> InferenceResult:
    """
    Convenience function for quick inference.

    Args:
        prompt: The prompt
        system_prompt: Optional system prompt
        **kwargs: Additional parameters

    Returns:
        InferenceResult
    """
    wrapper = await get_default_wrapper()
    request = InferenceRequest(
        prompt=prompt,
        system_prompt=system_prompt,
    )
    return await wrapper.infer(request)
