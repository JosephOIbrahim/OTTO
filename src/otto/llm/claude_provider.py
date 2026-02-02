"""
Claude (Anthropic) LLM Provider
===============================

Primary provider for OTTO cognitive support.

[He2025] Compliance:
- Fixed model defaults
- Deterministic system prompts
- Structured error handling

Requirements:
    pip install anthropic

Environment:
    ANTHROPIC_API_KEY: Your Anthropic API key
"""

import logging
import os
from typing import Final, Optional

from .provider import BaseLLMProvider, LLMConfig, LLMResponse

logger = logging.getLogger(__name__)

# Check for anthropic library
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None
    logger.warning(
        "anthropic not installed. "
        "Install with: pip install anthropic"
    )


# [He2025] Fixed constants
DEFAULT_MODEL: Final[str] = "claude-sonnet-4-20250514"
FALLBACK_MODEL: Final[str] = "claude-3-haiku-20240307"


class ClaudeProvider(BaseLLMProvider):
    """
    Claude (Anthropic) LLM provider.

    [He2025] Compliance:
    - Fixed model selection
    - Deterministic configuration
    - Graceful degradation

    Usage:
        provider = ClaudeProvider()  # Uses ANTHROPIC_API_KEY env var
        response = await provider.generate("Hello!", system="Be helpful.")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use (defaults to claude-sonnet-4)
        """
        super().__init__(api_key)

        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model or DEFAULT_MODEL
        self._client: Optional["anthropic.AsyncAnthropic"] = None

        if ANTHROPIC_AVAILABLE and self._api_key:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    @property
    def name(self) -> str:
        """Provider name."""
        return "claude"

    @property
    def default_model(self) -> str:
        """Default model."""
        return DEFAULT_MODEL

    def is_available(self) -> bool:
        """Check if Claude is available."""
        return ANTHROPIC_AVAILABLE and self._client is not None

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """
        Generate response using Claude.

        Args:
            prompt: User message
            system: System prompt
            config: Generation config

        Returns:
            LLMResponse with Claude's response

        Raises:
            ImportError: If anthropic not installed
            ValueError: If no API key configured
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic is required. "
                "Install with: pip install anthropic"
            )

        if not self._client:
            raise ValueError(
                "No Anthropic API key configured. "
                "Set ANTHROPIC_API_KEY environment variable."
            )

        cfg = self._get_config(config)
        model = cfg.model or self._model

        try:
            # Build messages
            messages = [{"role": "user", "content": prompt}]

            # Call Claude API with voice-aware parameters
            response = await self._client.messages.create(
                model=model,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                top_p=cfg.top_p,  # Nucleus sampling
                system=system or "",
                messages=messages,
                stop_sequences=cfg.stop_sequences if cfg.stop_sequences else anthropic.NOT_GIVEN,
            )

            # Extract text from response
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            return LLMResponse(
                text=text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                finish_reason=response.stop_reason or "stop",
                provider=self.name,
                raw={"id": response.id, "type": response.type},
            )

        except anthropic.APIConnectionError as e:
            logger.error(f"Claude connection error: {e}")
            raise
        except anthropic.RateLimitError as e:
            logger.error(f"Claude rate limit: {e}")
            raise
        except anthropic.APIStatusError as e:
            logger.error(f"Claude API error: {e}")
            raise


def create_claude_provider(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> ClaudeProvider:
    """
    Create and validate a Claude provider.

    Args:
        api_key: API key (defaults to env var)
        model: Model name

    Returns:
        Configured ClaudeProvider

    Raises:
        ImportError: If anthropic not installed
        ValueError: If no API key available
    """
    if not ANTHROPIC_AVAILABLE:
        raise ImportError(
            "anthropic is required. "
            "Install with: pip install anthropic"
        )

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "No Anthropic API key. "
            "Set ANTHROPIC_API_KEY environment variable."
        )

    return ClaudeProvider(api_key=key, model=model)


__all__ = [
    "ClaudeProvider",
    "create_claude_provider",
    "ANTHROPIC_AVAILABLE",
    "DEFAULT_MODEL",
]
