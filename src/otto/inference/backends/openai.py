"""
OpenAI Inference Backend
========================

Backend implementation for OpenAI models via the OpenAI API.

[He2025] Compliance:
- Uses temperature=0 for deterministic sampling
- Provides seed parameter for reproducibility
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

# Capabilities for OpenAI backends
OPENAI_CAPABILITIES = BackendCapabilities(
    supports_seed=True,
    supports_logprobs=True,
    supports_streaming=True,
    supports_system_prompt=True,
    supports_stop_sequences=True,
    supports_temperature_zero=True,
    max_context_window=128000,
    determinism_level="api",
)


class OpenAIBackend(InferenceBackend):
    """
    OpenAI inference backend using OpenAI API.

    Example:
        >>> backend = OpenAIBackend("gpt-4-turbo-preview")
        >>> await backend.initialize()
        >>> response = await backend.infer("Hello, GPT!")
        >>> print(response.content)
    """

    def __init__(
        self,
        model_id: str = "gpt-4-turbo-preview",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """
        Initialize OpenAI backend.

        Args:
            model_id: OpenAI model to use
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            base_url: Optional custom API base URL
            organization: Optional organization ID
            timeout: Request timeout in seconds
        """
        super().__init__(model_id, api_key)
        self._base_url = base_url
        self._organization = organization
        self._timeout = timeout
        self._client = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def capabilities(self) -> BackendCapabilities:
        return OPENAI_CAPABILITIES

    async def initialize(self) -> None:
        """Initialize the OpenAI client."""
        try:
            # Lazy import to avoid hard dependency
            import openai

            api_key = self._api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "API key required: pass api_key or set OPENAI_API_KEY"
                )

            self._client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=self._base_url,
                organization=self._organization,
                timeout=self._timeout,
            )
            self._status = BackendStatus.HEALTHY

        except ImportError:
            self._status = BackendStatus.UNAVAILABLE
            self._last_error = InferenceError(
                code="missing_dependency",
                message="openai package not installed: pip install openai",
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
        Perform inference using OpenAI.

        [He2025] Compliance:
        - temperature=0 by default for deterministic output
        - seed parameter for reproducibility
        """
        if self._client is None:
            await self.initialize()

        start_time = time.perf_counter()

        try:
            # Build messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Build request parameters
            request_params = {
                "model": self._model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            # OpenAI supports seed parameter for determinism
            if seed is not None:
                request_params["seed"] = seed

            if stop_sequences:
                request_params["stop"] = stop_sequences

            # Handle logprobs if requested
            if kwargs.get("logprobs"):
                request_params["logprobs"] = True
                if kwargs.get("top_logprobs"):
                    request_params["top_logprobs"] = kwargs["top_logprobs"]

            # Add any additional kwargs
            for key, value in kwargs.items():
                if key not in ("logprobs", "top_logprobs") and value is not None:
                    request_params[key] = value

            # Make API call
            response = await self._client.chat.completions.create(**request_params)

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Extract content
            choice = response.choices[0]
            content = choice.message.content or ""

            # Extract logprobs if available
            logprobs = None
            if choice.logprobs and choice.logprobs.content:
                logprobs = [lp.logprob for lp in choice.logprobs.content]

            # Build response
            return InferenceResponse(
                content=content,
                model=response.model,
                finish_reason=choice.finish_reason or "stop",
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                logprobs=logprobs,
                latency_ms=latency_ms,
                request_id=response.id,
                metadata={
                    "backend": "openai",
                    "temperature": temperature,
                    "seed": seed,
                    "system_fingerprint": getattr(response, 'system_fingerprint', None),
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
        Perform streaming inference using OpenAI.
        """
        if self._client is None:
            await self.initialize()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            request_params = {
                "model": self._model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }

            if seed is not None:
                request_params["seed"] = seed

            if stop_sequences:
                request_params["stop"] = stop_sequences

            stream = await self._client.chat.completions.create(**request_params)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            self._last_error = self._classify_error(e)
            self._status = BackendStatus.DEGRADED
            raise

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            if self._client is None:
                await self.initialize()

            # List models as a health check
            await self._client.models.list()
            self._status = BackendStatus.HEALTHY
            return True

        except Exception:
            self._status = BackendStatus.UNAVAILABLE
            return False

    async def shutdown(self) -> None:
        """Shutdown the client."""
        if self._client:
            await self._client.close()
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

        if "context" in error_str or "token" in error_str or "length" in error_str:
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
