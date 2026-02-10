"""Anthropic SDK wrapper for OTTO OS.

Provides a thin wrapper around the Anthropic Messages API with:

- Lazy SDK import for testability
- Dependency injection of the raw client
- Frozen response dataclasses
- deterministic configuration

The client does NOT handle routing — that's NEXUSPipeline's job.
This module is purely about API communication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelConfig:
    """Static model configuration.

    Attributes:
        model: Model identifier for the API.
        max_output_tokens: Maximum output tokens per request.
        max_context_tokens: Maximum context window size.
        input_cost_per_m: Cost per million input tokens (USD).
        output_cost_per_m: Cost per million output tokens (USD).
    """

    model: str = "claude-opus-4-6"
    max_output_tokens: int = 128_000
    max_context_tokens: int = 1_000_000
    input_cost_per_m: float = 5.0
    output_cost_per_m: float = 25.0


# Default config matching CLAUDE.md §10 specification
OPUS_46_CONFIG = ModelConfig()


@dataclass(frozen=True)
class APIResponse:
    """Normalized API response.

    Frozen because responses are immutable facts — once received,
    they never change.

    Attributes:
        content: The text content of the response.
        model: Model that generated the response.
        input_tokens: Tokens used for input.
        output_tokens: Tokens used for output.
        stop_reason: Why the model stopped generating.
    """

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: str


class OTTOClient:
    """OTTO's Anthropic API client.

    Wraps the Anthropic SDK with OTTO-specific defaults and
    response normalization.  Supports dependency injection of
    the raw messages client for testing.

    Args:
        config: Model configuration (defaults to OPUS_46_CONFIG).
        raw_client: Optional pre-configured messages client with
            a ``.create(**kwargs)`` method.  If ``None``, creates
            one via the Anthropic SDK (requires ``ANTHROPIC_API_KEY``).
    """

    def __init__(
        self,
        config: ModelConfig | None = None,
        raw_client: Any | None = None,
    ) -> None:
        self._config = config or OPUS_46_CONFIG
        self._raw_client = raw_client

    @property
    def config(self) -> ModelConfig:
        """The active model configuration."""
        return self._config

    def _get_messages_client(self) -> Any:
        """Lazy-initialize and return the messages interface.

        Uses dependency injection if a raw_client was provided.
        Otherwise, imports anthropic SDK and creates a client.

        Returns:
            Object with a ``.create(**kwargs)`` method.

        Raises:
            ImportError: If anthropic SDK is not installed.
        """
        if self._raw_client is not None:
            return self._raw_client

        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for API calls. "
                "Install it with: pip install anthropic"
            ) from exc

        client = anthropic.Anthropic()
        self._raw_client = client.messages
        return self._raw_client

    def send(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        effort: str | None = None,
        max_tokens: int | None = None,
    ) -> APIResponse:
        """Send a message to the API and return a normalized response.

        Args:
            messages: Conversation messages in API format
                (list of ``{"role": "...", "content": "..."}``).
            system: Optional system prompt.
            effort: Optional effort level
                (``"low"``, ``"medium"``, ``"high"``, ``"max"``).
            max_tokens: Maximum output tokens (defaults to config).

        Returns:
            Normalized APIResponse.

        Raises:
            ImportError: If anthropic SDK is not installed.
        """
        client = self._get_messages_client()

        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "max_tokens": max_tokens or self._config.max_output_tokens,
            "messages": messages,
        }

        if system is not None:
            kwargs["system"] = system

        if effort is not None:
            kwargs["effort"] = effort

        raw_response = client.create(**kwargs)

        return self._normalize_response(raw_response)

    def _normalize_response(self, raw: Any) -> APIResponse:
        """Convert raw SDK response to frozen APIResponse.

        Handles the anthropic SDK ``Message`` structure:

        - ``raw.content[0].text`` → content (concatenated if multiple)
        - ``raw.model`` → model
        - ``raw.usage.input_tokens`` → input_tokens
        - ``raw.usage.output_tokens`` → output_tokens
        - ``raw.stop_reason`` → stop_reason
        """
        # Extract text from content blocks
        content_text = ""
        if hasattr(raw, "content") and raw.content:
            for block in raw.content:
                if hasattr(block, "text"):
                    content_text += block.text

        # Extract usage safely
        input_tokens = 0
        output_tokens = 0
        if hasattr(raw, "usage") and raw.usage is not None:
            input_tokens = getattr(raw.usage, "input_tokens", 0)
            output_tokens = getattr(raw.usage, "output_tokens", 0)

        return APIResponse(
            content=content_text,
            model=getattr(raw, "model", self._config.model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=getattr(raw, "stop_reason", "unknown"),
        )
