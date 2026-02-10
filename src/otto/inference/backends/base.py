"""
Abstract Inference Backend
==========================

Base class defining the interface that all inference backends must implement.

Principles:
- Fixed interface (no dynamic method addition)
- Explicit capabilities declaration
- Deterministic status reporting
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, AsyncIterator
import hashlib
import json


class BackendStatus(Enum):
    """Backend operational status."""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"


@dataclass(frozen=True)
class BackendCapabilities:
    """
    Declares what features a backend supports.

    Frozen for determinism (no runtime modification).

    Attributes:
        supports_seed: Can accept seed parameter for reproducibility
        supports_logprobs: Can return token log probabilities
        supports_streaming: Can stream responses
        supports_system_prompt: Can accept system prompt separately
        supports_stop_sequences: Can stop on specific sequences
        supports_temperature_zero: Handles temperature=0 correctly
        max_context_window: Maximum context length in tokens
        determinism_level: Maximum determinism level this backend can provide
    """
    supports_seed: bool = True
    supports_logprobs: bool = False
    supports_streaming: bool = True
    supports_system_prompt: bool = True
    supports_stop_sequences: bool = True
    supports_temperature_zero: bool = True
    max_context_window: int = 128000
    determinism_level: str = "api"  # api | verified | kernel

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'supports_seed': self.supports_seed,
            'supports_logprobs': self.supports_logprobs,
            'supports_streaming': self.supports_streaming,
            'supports_system_prompt': self.supports_system_prompt,
            'supports_stop_sequences': self.supports_stop_sequences,
            'supports_temperature_zero': self.supports_temperature_zero,
            'max_context_window': self.max_context_window,
            'determinism_level': self.determinism_level,
        }


@dataclass
class InferenceResponse:
    """
    Response from an inference backend.

    Attributes:
        content: The generated text
        model: Model that generated the response
        finish_reason: Why generation stopped (stop, length, etc.)
        usage: Token usage statistics
        logprobs: Optional log probabilities
        latency_ms: Request latency in milliseconds
        request_id: Unique request identifier
        content_hash: SHA-256 hash of content for integrity
        metadata: Additional backend-specific metadata
    """
    content: str
    model: str
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)
    logprobs: Optional[List[float]] = None
    latency_ms: float = 0.0
    request_id: str = ""
    content_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Compute content hash if not provided."""
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.content.encode('utf-8')
            ).hexdigest()[:32]

        if not self.request_id:
            # Generate deterministic request ID from content + timestamp
            timestamp = datetime.now(timezone.utc).isoformat()
            id_data = f"{self.content_hash}:{timestamp}"
            self.request_id = hashlib.sha256(
                id_data.encode('utf-8')
            ).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'content': self.content,
            'model': self.model,
            'finish_reason': self.finish_reason,
            'usage': self.usage,
            'logprobs': self.logprobs,
            'latency_ms': self.latency_ms,
            'request_id': self.request_id,
            'content_hash': self.content_hash,
            'metadata': self.metadata,
        }


@dataclass
class InferenceError:
    """
    Error from an inference backend.

    Attributes:
        code: Error code (e.g., "rate_limit", "context_length", "timeout")
        message: Human-readable error message
        retryable: Whether this error can be retried
        retry_after: Suggested retry delay in seconds
        details: Additional error details
    """
    code: str
    message: str
    retryable: bool = False
    retry_after: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'code': self.code,
            'message': self.message,
            'retryable': self.retryable,
            'retry_after': self.retry_after,
            'details': self.details,
        }


class InferenceBackend(ABC):
    """
    Abstract base class for inference backends.

    All backends must implement this interface to ensure consistent
    behavior and enable backend swapping.

    Determinism:
    - Fixed method signatures
    - Explicit capability declaration
    - Deterministic configuration
    """

    def __init__(self, model_id: str, api_key: Optional[str] = None):
        """
        Initialize the backend.

        Args:
            model_id: The model to use for inference
            api_key: Optional API key (may be read from environment)
        """
        self._model_id = model_id
        self._api_key = api_key
        self._status = BackendStatus.INITIALIZING
        self._last_error: Optional[InferenceError] = None

    @property
    def model_id(self) -> str:
        """Get the model ID."""
        return self._model_id

    @property
    def status(self) -> BackendStatus:
        """Get current backend status."""
        return self._status

    @property
    def last_error(self) -> Optional[InferenceError]:
        """Get the last error encountered."""
        return self._last_error

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the backend name (e.g., 'claude', 'openai')."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        """Get backend capabilities."""
        pass

    @abstractmethod
    async def infer(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> InferenceResponse:
        """
        Perform inference.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
            seed: Random seed for reproducibility
            stop_sequences: Sequences that stop generation
            **kwargs: Additional backend-specific parameters

        Returns:
            InferenceResponse with the generated content

        Raises:
            InferenceError: If inference fails
        """
        pass

    @abstractmethod
    async def infer_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Perform streaming inference.

        Args:
            Same as infer()

        Yields:
            String chunks as they are generated

        Raises:
            InferenceError: If inference fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the backend is healthy.

        Returns:
            True if backend is operational
        """
        pass

    async def initialize(self) -> None:
        """
        Initialize the backend (connect, validate API key, etc.).

        Override in subclasses for custom initialization.
        """
        self._status = BackendStatus.HEALTHY

    async def shutdown(self) -> None:
        """
        Shutdown the backend (close connections, cleanup, etc.).

        Override in subclasses for custom cleanup.
        """
        self._status = BackendStatus.UNAVAILABLE

    def get_status_report(self) -> Dict[str, Any]:
        """
        Get detailed status report.

        Returns:
            Dict with status, capabilities, and error info
        """
        return {
            'name': self.name,
            'model_id': self._model_id,
            'status': self._status.value,
            'capabilities': self.capabilities.to_dict(),
            'last_error': self._last_error.to_dict() if self._last_error else None,
        }
