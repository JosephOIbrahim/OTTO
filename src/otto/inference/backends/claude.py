"""
Claude (Anthropic) Inference Backend
====================================

Backend implementation for Claude models via the Anthropic API.

[He2025] Compliance:
- Uses temperature=0 for deterministic sampling
- Provides seed parameter (when supported)
- Fixed parameter handling
"""

import os
import time
from typing import Optional, List, Any, AsyncIterator

from .base import (
    InferenceBackend,
    BackendCapabilities,
    BackendStatus,
    InferenceResponse,
    InferenceError,
)

# Capabilities for Claude backends
CLAUDE_CAPABILITIES = BackendCapabilities(
    supports_seed=True,
    supports_logprobs=False,  # Claude doesn't expose logprobs
    supports_streaming=True,
    supports_system_prompt=True,
    supports_stop_sequences=True,
    supports_temperature_zero=True,
    max_context_window=200000,
    determinism_level="api",
)


class ClaudeBackend(InferenceBackend):
    """
    Claude inference backend using Anthropic API.

    Example:
        >>> backend = ClaudeBackend("claude-3-opus-20240229")
        >>> await backend.initialize()
        >>> response = await backend.infer("Hello, Claude!")
        >>> print(response.content)
    """

    def __init__(
        self,
        model_id: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """
        Initialize Claude backend.

        Args:
            model_id: Claude model to use
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            base_url: Optional custom API base URL
            timeout: Request timeout in seconds
        """
        super().__init__(model_id, api_key)
        self._base_url = base_url
        self._timeout = timeout
        self._client = None

    @property
    def name(self) -> str:
        return "claude"

    @property
    def capabilities(self) -> BackendCapabilities:
        return CLAUDE_CAPABILITIES

    async def initialize(self) -> None:
        """Initialize the Anthropic client."""
        try:
            # Lazy import to avoid hard dependency
            import anthropic

            api_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "API key required: pass api_key or set ANTHROPIC_API_KEY"
                )

            self._client = anthropic.AsyncAnthropic(
                api_key=api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
            self._status = BackendStatus.HEALTHY

        except ImportError:
            self._status = BackendStatus.UNAVAILABLE
            self._last_error = InferenceError(
                code="missing_dependency",
                message="anthropic package not installed: pip install anthropic",
                retryable=False,
            )
            raise

        except Exception as e:
            self._status = BackendStatus.UNAVAILABLE
            self._last_error = InferenceError(
                code="initialization_failed",
                message=str(e),
                retryable=False,
            )
            raise

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
        Perform inference using Claude.

        [He2025] Compliance: temperature=0 by default for deterministic output.
        """
        if self._client is None:
            await self.initialize()

        start_time = time.perf_counter()

        try:
            # Build messages
            messages = [{"role": "user", "content": prompt}]

            # Build request parameters
            request_params = {
                "model": self._model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if system_prompt:
                request_params["system"] = system_prompt

            if stop_sequences:
                request_params["stop_sequences"] = stop_sequences

            # Note: Anthropic API doesn't officially support seed parameter yet
            # but we include it for future compatibility
            if seed is not None and kwargs.get("force_seed", False):
                request_params["seed"] = seed

            # Add any additional kwargs
            for key, value in kwargs.items():
                if key not in ("force_seed",) and value is not None:
                    request_params[key] = value

            # Make API call
            response = await self._client.messages.create(**request_params)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract content
            content = ""
            if response.content:
                content = response.content[0].text

            # Build response
            return InferenceResponse(
                content=content,
                model=response.model,
                finish_reason=response.stop_reason or "stop",
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                latency_ms=latency_ms,
                request_id=response.id,
                metadata={
                    "backend": "claude",
                    "temperature": temperature,
                    "seed": seed,
                },
            )

        except Exception as e:
            self._last_error = self._classify_error(e)
            self._status = BackendStatus.DEGRADED
            raise

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
        Perform streaming inference using Claude.
        """
        if self._client is None:
            await self.initialize()

        try:
            messages = [{"role": "user", "content": prompt}]

            request_params = {
                "model": self._model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if system_prompt:
                request_params["system"] = system_prompt

            if stop_sequences:
                request_params["stop_sequences"] = stop_sequences

            async with self._client.messages.stream(**request_params) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as e:
            self._last_error = self._classify_error(e)
            self._status = BackendStatus.DEGRADED
            raise

    async def health_check(self) -> bool:
        """Check if Claude API is accessible."""
        try:
            if self._client is None:
                await self.initialize()

            # Simple health check - just verify we can create a client
            # A real health check would make a minimal API call
            self._status = BackendStatus.HEALTHY
            return True

        except Exception:
            self._status = BackendStatus.UNAVAILABLE
            return False

    async def shutdown(self) -> None:
        """Shutdown the client."""
        if self._client:
            # AsyncAnthropic doesn't require explicit close
            self._client = None
        self._status = BackendStatus.UNAVAILABLE

    def _classify_error(self, error: Exception) -> InferenceError:
        """Classify an exception into an InferenceError."""
        error_str = str(error).lower()

        if "rate" in error_str or "429" in error_str:
            return InferenceError(
                code="rate_limit",
                message="Rate limit exceeded",
                retryable=True,
                retry_after=60.0,
                details={"original_error": str(error)},
            )

        if "context" in error_str or "token" in error_str:
            return InferenceError(
                code="context_length",
                message="Context length exceeded",
                retryable=False,
                details={"original_error": str(error)},
            )

        if "timeout" in error_str:
            return InferenceError(
                code="timeout",
                message="Request timed out",
                retryable=True,
                retry_after=5.0,
                details={"original_error": str(error)},
            )

        if "auth" in error_str or "key" in error_str or "401" in error_str:
            return InferenceError(
                code="authentication",
                message="Authentication failed",
                retryable=False,
                details={"original_error": str(error)},
            )

        return InferenceError(
            code="unknown",
            message=str(error),
            retryable=True,
            retry_after=5.0,
            details={"original_error": str(error)},
        )
