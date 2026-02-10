"""
Deterministic Inference Configuration
=====================================

Configuration classes for maximizing inference determinism within API constraints.

[He2025] Principles Applied:
- Fixed parameter values (no dynamic adjustment based on load)
- Deterministic defaults (temperature=0, greedy decoding)
- Explicit seed control where supported
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, FrozenSet
import hashlib
import json


class InferenceBackendType(Enum):
    """Supported inference backends."""
    CLAUDE = "claude"
    OPENAI = "openai"
    LOCAL_VLLM = "local_vllm"
    LOCAL_OLLAMA = "local_ollama"
    MOCK = "mock"  # For testing


class DeterminismLevel(Enum):
    """
    Determinism guarantee levels.

    Maps to the tiered strategy in HE2025_KERNEL_COMPLIANCE_STRATEGY.md.
    """
    NONE = "none"              # No determinism guarantees
    API_MAXIMIZED = "api"      # Tier 1: Best effort with API params
    VERIFIED = "verified"      # Tier 2: Multi-trial verification
    KERNEL_LEVEL = "kernel"    # Tier 3: Local deterministic inference
    CRYPTOGRAPHIC = "crypto"   # Tier 4: TEE + proofs (future)


@dataclass(frozen=True)
class DeterministicInferenceConfig:
    """
    Configuration for deterministic inference.

    This config maximizes determinism within API constraints by:
    1. Setting temperature=0 (no sampling randomness)
    2. Using greedy decoding (top_k=1, top_p=1.0)
    3. Providing fixed seed where supported
    4. Enabling response caching

    The frozen=True ensures the config itself is immutable and hashable,
    supporting [He2025] principle of fixed parameters.

    Attributes:
        temperature: Sampling temperature (0.0 = deterministic)
        seed: Random seed for backends that support it
        top_p: Nucleus sampling parameter (1.0 = disabled)
        top_k: Top-k sampling parameter (1 = greedy)
        max_tokens: Maximum tokens to generate
        stop_sequences: Sequences that stop generation
        backend: Which inference backend to use
        determinism_level: Target determinism level
        cache_enabled: Whether to cache responses
        cache_ttl_seconds: Cache entry TTL (None = forever)
        request_timeout: Timeout for inference requests (seconds)
        retry_count: Number of retries on failure
        retry_delay: Delay between retries (seconds)

    Example:
        >>> config = DeterministicInferenceConfig()
        >>> config.temperature
        0.0
        >>> config.is_deterministic
        True
    """
    # Core sampling parameters (deterministic defaults)
    temperature: float = 0.0
    seed: Optional[int] = 42
    top_p: float = 1.0
    top_k: int = 1

    # Generation limits
    max_tokens: int = 4096
    stop_sequences: FrozenSet[str] = field(default_factory=frozenset)

    # Backend selection
    backend: InferenceBackendType = InferenceBackendType.CLAUDE
    determinism_level: DeterminismLevel = DeterminismLevel.API_MAXIMIZED

    # Caching
    cache_enabled: bool = True
    cache_ttl_seconds: Optional[int] = None  # None = no expiration

    # Reliability
    request_timeout: float = 120.0
    retry_count: int = 3
    retry_delay: float = 1.0

    def __post_init__(self):
        """Validate configuration."""
        if self.temperature < 0.0 or self.temperature > 2.0:
            raise ValueError(f"temperature must be in [0.0, 2.0], got {self.temperature}")
        if self.top_p < 0.0 or self.top_p > 1.0:
            raise ValueError(f"top_p must be in [0.0, 1.0], got {self.top_p}")
        if self.top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {self.top_k}")
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {self.max_tokens}")

    @property
    def is_deterministic(self) -> bool:
        """
        Check if this configuration maximizes determinism.

        Returns True if temperature=0 and greedy decoding is enabled.
        """
        return (
            self.temperature == 0.0 and
            self.top_k == 1 and
            self.top_p == 1.0
        )

    @property
    def config_hash(self) -> str:
        """
        Compute deterministic hash of this configuration.

        Used for cache key computation and verification.

        [He2025]-inspired determinism: Uses sorted keys for deterministic serialization.
        """
        # Convert to dict with sorted keys for deterministic serialization
        config_dict = {
            'temperature': self.temperature,
            'seed': self.seed,
            'top_p': self.top_p,
            'top_k': self.top_k,
            'max_tokens': self.max_tokens,
            'stop_sequences': sorted(self.stop_sequences),
            'backend': self.backend.value,
        }
        config_str = json.dumps(config_dict, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(config_str.encode('utf-8')).hexdigest()[:16]

    def to_api_params(self) -> Dict[str, Any]:
        """
        Convert to API-specific parameters.

        Returns a dict suitable for passing to LLM APIs.
        Different backends may use different parameter names.
        """
        params = {
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
        }

        if self.seed is not None:
            params['seed'] = self.seed

        if self.top_p != 1.0:
            params['top_p'] = self.top_p

        if self.top_k != 1:
            params['top_k'] = self.top_k

        if self.stop_sequences:
            params['stop'] = list(self.stop_sequences)

        return params

    def with_overrides(self, **kwargs) -> 'DeterministicInferenceConfig':
        """
        Create a new config with specified overrides.

        Since the config is frozen, this creates a new instance.

        Example:
            >>> config = DeterministicInferenceConfig()
            >>> high_temp = config.with_overrides(temperature=0.7)
            >>> high_temp.temperature
            0.7
        """
        current = {
            'temperature': self.temperature,
            'seed': self.seed,
            'top_p': self.top_p,
            'top_k': self.top_k,
            'max_tokens': self.max_tokens,
            'stop_sequences': self.stop_sequences,
            'backend': self.backend,
            'determinism_level': self.determinism_level,
            'cache_enabled': self.cache_enabled,
            'cache_ttl_seconds': self.cache_ttl_seconds,
            'request_timeout': self.request_timeout,
            'retry_count': self.retry_count,
            'retry_delay': self.retry_delay,
        }
        current.update(kwargs)
        return DeterministicInferenceConfig(**current)


# Pre-defined configurations for common use cases
DETERMINISTIC_DEFAULT = DeterministicInferenceConfig()

DETERMINISTIC_FAST = DeterministicInferenceConfig(
    max_tokens=1024,
    request_timeout=30.0,
)

DETERMINISTIC_LONG = DeterministicInferenceConfig(
    max_tokens=8192,
    request_timeout=300.0,
)

# Non-deterministic config (for comparison/fallback)
STOCHASTIC_CONFIG = DeterministicInferenceConfig(
    temperature=0.7,
    seed=None,
    top_p=0.9,
    top_k=40,
    cache_enabled=False,
    determinism_level=DeterminismLevel.NONE,
)


@dataclass(frozen=True)
class ModelConfig:
    """
    Model-specific configuration.

    Attributes:
        model_id: Model identifier (e.g., "claude-3-opus-20240229")
        context_window: Maximum context window size
        supports_seed: Whether the model/API supports seed parameter
        supports_logprobs: Whether logprobs are available
        default_config: Default inference config for this model
    """
    model_id: str
    context_window: int = 128000
    supports_seed: bool = True
    supports_logprobs: bool = False
    default_config: DeterministicInferenceConfig = DETERMINISTIC_DEFAULT

    @property
    def model_hash(self) -> str:
        """Deterministic hash of model configuration."""
        model_dict = {
            'model_id': self.model_id,
            'context_window': self.context_window,
        }
        model_str = json.dumps(model_dict, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(model_str.encode('utf-8')).hexdigest()[:16]


# Common model configurations
CLAUDE_OPUS = ModelConfig(
    model_id="claude-3-opus-20240229",
    context_window=200000,
    supports_seed=True,
    supports_logprobs=False,
)

CLAUDE_SONNET = ModelConfig(
    model_id="claude-3-5-sonnet-20241022",
    context_window=200000,
    supports_seed=True,
    supports_logprobs=False,
)

GPT4_TURBO = ModelConfig(
    model_id="gpt-4-turbo-preview",
    context_window=128000,
    supports_seed=True,
    supports_logprobs=True,
)

LLAMA_70B_LOCAL = ModelConfig(
    model_id="meta-llama/Llama-3.1-70B-Instruct",
    context_window=128000,
    supports_seed=True,
    supports_logprobs=True,
    default_config=DeterministicInferenceConfig(
        backend=InferenceBackendType.LOCAL_VLLM,
        determinism_level=DeterminismLevel.KERNEL_LEVEL,
    ),
)
