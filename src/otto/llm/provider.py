"""
LLM Provider Protocol
=====================

Abstract interface for LLM backends.

Determinism:
- Fixed interface contract
- Deterministic configuration
- Provider-agnostic design
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Final, List, Optional, Protocol, runtime_checkable


# Fixed constants
DEFAULT_MAX_TOKENS: Final[int] = 1024
DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_TOP_P: Final[float] = 0.9


@dataclass
class Message:
    """
    A single message in a conversation.

    Fixed role values for deterministic serialization.
    """
    role: str  # "user" or "assistant"
    content: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to API format."""
        return {"role": self.role, "content": self.content}


@dataclass
class LLMConfig:
    """
    Configuration for LLM provider.

    All fields have fixed defaults.
    """
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P  # Nucleus sampling parameter
    model: Optional[str] = None  # Provider-specific model name

    # Effort control (Opus 4.6 GA): "low", "medium", "high", "max"
    effort: Optional[str] = None

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

    Fixed method signatures for deterministic behavior.
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
        messages: Optional[List["Message"]] = None,
    ) -> LLMResponse:
        """
        Generate a response.

        Args:
            prompt: User message/prompt (used if messages not provided)
            system: System prompt (optional)
            config: Generation config (uses defaults if None)
            messages: Conversation history (optional, for multi-turn)

        Returns:
            LLMResponse with generated text

        Note:
            If messages is provided, prompt is appended as the final user message.
            If messages is None, a single-turn conversation is created from prompt.
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
        messages: Optional[List["Message"]] = None,
    ) -> LLMResponse:
        """Generate response with optional conversation history."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check availability."""
        ...

    def _get_config(self, config: Optional[LLMConfig]) -> LLMConfig:
        """Get config with defaults."""
        return config or LLMConfig()
