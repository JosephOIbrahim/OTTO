"""
LLM Provider Protocol
=====================

Abstract interface for LLM backends.

[He2025] Compliance:
- Fixed interface contract
- Deterministic configuration
- Provider-agnostic design
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Final, List, Optional, Protocol, runtime_checkable


# [He2025] Fixed constants
DEFAULT_MAX_TOKENS: Final[int] = 1024
DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_TOP_P: Final[float] = 0.9


@dataclass
class LLMConfig:
    """
    Configuration for LLM provider.

    [He2025] All fields have fixed defaults.
    """
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P  # Nucleus sampling parameter
    model: Optional[str] = None  # Provider-specific model name

    # Safety settings
    stop_sequences: List[str] = field(default_factory=list)

    # Provider-specific options
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """
    Response from LLM provider.

    Normalized across all providers.
    """
    text: str
    model: str

    # Usage tracking
    input_tokens: int = 0
    output_tokens: int = 0

    # Metadata
    finish_reason: str = "stop"
    provider: str = "unknown"

    # Raw response for debugging
    raw: Optional[Dict[str, Any]] = None

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


@runtime_checkable
class LLMProvider(Protocol):
    """
    Protocol for LLM providers.

    Implement this to add a new LLM backend.

    [He2025] Fixed method signatures for deterministic behavior.
    """

    @property
    def name(self) -> str:
        """Provider name (e.g., 'claude', 'openai')."""
        ...

    @property
    def default_model(self) -> str:
        """Default model for this provider."""
        ...

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """
        Generate a response.

        Args:
            prompt: User message/prompt
            system: System prompt (optional)
            config: Generation config (uses defaults if None)

        Returns:
            LLMResponse with generated text
        """
        ...

    def is_available(self) -> bool:
        """Check if provider is configured and available."""
        ...


class BaseLLMProvider(ABC):
    """
    Base class for LLM providers.

    Provides common functionality.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize provider.

        Args:
            api_key: API key (can also come from env var)
        """
        self._api_key = api_key

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Generate response."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check availability."""
        ...

    def _get_config(self, config: Optional[LLMConfig]) -> LLMConfig:
        """Get config with defaults."""
        return config or LLMConfig()
