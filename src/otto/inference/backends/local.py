"""
Local Inference Backends
========================

Backend implementations for local model inference.

These backends enable Tier 3 Determinism through:
- Batch size = 1 (eliminates batch-variance)
- Deterministic CUDA configuration
- Full control over kernel execution

Supported:
- vLLM: High-performance local inference
- Ollama: Easy-to-use local inference
"""

import os
import time
from typing import Optional, List, Any, AsyncIterator
import aiohttp

from .base import (
    InferenceBackend,
    BackendCapabilities,
    BackendStatus,
    InferenceResponse,
    InferenceError,
)

# Capabilities for local vLLM backend
VLLM_CAPABILITIES = BackendCapabilities(
    supports_seed=True,
    supports_logprobs=True,
    supports_streaming=True,
    supports_system_prompt=True,
    supports_stop_sequences=True,
    supports_temperature_zero=True,
    max_context_window=128000,
    determinism_level="kernel",  # True Determinism!
)

# Capabilities for Ollama backend
OLLAMA_CAPABILITIES = BackendCapabilities(
    supports_seed=True,
    supports_logprobs=False,
    supports_streaming=True,
    supports_system_prompt=True,
    supports_stop_sequences=True,
    supports_temperature_zero=True,
    max_context_window=128000,
    determinism_level="api",  # Ollama doesn't guarantee kernel-level determinism
)


class LocalVLLMBackend(InferenceBackend):
    """
    Local vLLM inference backend.

    This backend provides TRUE kernel-level determinism when
    configured with batch_size=1 and deterministic CUDA settings.

    Configuration for determinism:
    ```bash
    export CUDA_LAUNCH_BLOCKING=1
    export CUBLAS_WORKSPACE_CONFIG=":4096:8"
    vllm serve meta-llama/Llama-3.1-70B-Instruct \\
        --max-num-batched-tokens 1 \\
        --seed 42 \\
        --enforce-eager
    ```

    Example:
        >>> backend = LocalVLLMBackend("meta-llama/Llama-3.1-70B-Instruct")
        >>> await backend.initialize()
        >>> response = await backend.infer("Hello!")
        >>> print(response.content)
    """

    def __init__(
        self,
        model_id: str = "meta-llama/Llama-3.1-70B-Instruct",
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 300.0,
    ):
        """
        Initialize vLLM backend.

        Args:
            model_id: Model being served by vLLM
            base_url: vLLM server URL
            api_key: Optional API key (if vLLM configured with auth)
            timeout: Request timeout in seconds
        """
        super().__init__(model_id, api_key)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def name(self) -> str:
        return "vllm"

    @property
    def capabilities(self) -> BackendCapabilities:
        return VLLM_CAPABILITIES

    async def initialize(self) -> None:
        """Initialize the HTTP session."""
        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

            # Verify server is accessible
            async with self._session.get(f"{self._base_url}/health") as resp:
                if resp.status != 200:
                    raise ConnectionError(f"vLLM server not healthy: {resp.status}")

            self._status = BackendStatus.HEALTHY

        except Exception as e:
            self._status = BackendStatus.UNAVAILABLE
            self._last_error = InferenceError(
                code="initialization_failed",
                message=f"Failed to connect to vLLM: {e}",
                retryable=True,
                retry_after=5.0,
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
        Perform inference using local vLLM.

        Determinism: With proper server configuration, this provides
        TRUE kernel-level determinism.
        """
        if self._session is None:
            await self.initialize()

        start_time = time.perf_counter()

        try:
            # vLLM uses OpenAI-compatible API
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            request_body = {
                "model": self._model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if seed is not None:
                request_body["seed"] = seed

            if stop_sequences:
                request_body["stop"] = stop_sequences

            # Request logprobs if available
            if kwargs.get("logprobs"):
                request_body["logprobs"] = True

            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            async with self._session.post(
                f"{self._base_url}/v1/chat/completions",
                json=request_body,
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"vLLM error {resp.status}: {error_text}")

                response = await resp.json()

            latency_ms = (time.perf_counter() - start_time) * 1000

            choice = response["choices"][0]
            content = choice["message"]["content"]

            # Extract logprobs if present
            logprobs = None
            if "logprobs" in choice and choice["logprobs"]:
                logprobs = [lp["logprob"] for lp in choice["logprobs"]["content"]]

            usage = response.get("usage", {})

            return InferenceResponse(
                content=content,
                model=response.get("model", self._model_id),
                finish_reason=choice.get("finish_reason", "stop"),
                usage={
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                },
                logprobs=logprobs,
                latency_ms=latency_ms,
                request_id=response.get("id", ""),
                metadata={
                    "backend": "vllm",
                    "temperature": temperature,
                    "seed": seed,
                    "determinism_level": "kernel",
                },
            )

        except Exception as e:
            self._last_error = InferenceError(
                code="inference_failed",
                message=str(e),
                retryable=True,
                retry_after=5.0,
            )
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
        """Perform streaming inference using local vLLM."""
        if self._session is None:
            await self.initialize()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            request_body = {
                "model": self._model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }

            if seed is not None:
                request_body["seed"] = seed

            if stop_sequences:
                request_body["stop"] = stop_sequences

            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            async with self._session.post(
                f"{self._base_url}/v1/chat/completions",
                json=request_body,
                headers=headers,
            ) as resp:
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        import json
                        chunk = json.loads(data)
                        if chunk["choices"][0]["delta"].get("content"):
                            yield chunk["choices"][0]["delta"]["content"]

        except Exception as e:
            self._last_error = InferenceError(
                code="streaming_failed",
                message=str(e),
                retryable=True,
            )
            raise

    async def health_check(self) -> bool:
        """Check if vLLM server is healthy."""
        try:
            if self._session is None:
                await self.initialize()

            async with self._session.get(f"{self._base_url}/health") as resp:
                if resp.status == 200:
                    self._status = BackendStatus.HEALTHY
                    return True

            self._status = BackendStatus.UNAVAILABLE
            return False

        except Exception:
            self._status = BackendStatus.UNAVAILABLE
            return False

    async def shutdown(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._status = BackendStatus.UNAVAILABLE


class LocalOllamaBackend(InferenceBackend):
    """
    Local Ollama inference backend.

    Ollama provides easy local model serving. Note that Ollama does NOT
    guarantee kernel-level determinism (API-level only).

    Example:
        >>> backend = LocalOllamaBackend("llama3.1:70b")
        >>> await backend.initialize()
        >>> response = await backend.infer("Hello!")
    """

    def __init__(
        self,
        model_id: str = "llama3.1:70b",
        base_url: str = "http://localhost:11434",
        timeout: float = 300.0,
    ):
        """
        Initialize Ollama backend.

        Args:
            model_id: Ollama model name
            base_url: Ollama server URL
            timeout: Request timeout in seconds
        """
        super().__init__(model_id, None)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def capabilities(self) -> BackendCapabilities:
        return OLLAMA_CAPABILITIES

    async def initialize(self) -> None:
        """Initialize the HTTP session."""
        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

            # Verify Ollama is running
            async with self._session.get(f"{self._base_url}/api/tags") as resp:
                if resp.status != 200:
                    raise ConnectionError(f"Ollama not accessible: {resp.status}")

            self._status = BackendStatus.HEALTHY

        except Exception as e:
            self._status = BackendStatus.UNAVAILABLE
            self._last_error = InferenceError(
                code="initialization_failed",
                message=f"Failed to connect to Ollama: {e}",
                retryable=True,
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
        """Perform inference using Ollama."""
        if self._session is None:
            await self.initialize()

        start_time = time.perf_counter()

        try:
            request_body = {
                "model": self._model_id,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            if system_prompt:
                request_body["system"] = system_prompt

            if seed is not None:
                request_body["options"]["seed"] = seed

            if stop_sequences:
                request_body["options"]["stop"] = stop_sequences

            async with self._session.post(
                f"{self._base_url}/api/generate",
                json=request_body,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"Ollama error {resp.status}: {error_text}")

                response = await resp.json()

            latency_ms = (time.perf_counter() - start_time) * 1000

            return InferenceResponse(
                content=response.get("response", ""),
                model=response.get("model", self._model_id),
                finish_reason="stop" if response.get("done") else "length",
                usage={
                    "input_tokens": response.get("prompt_eval_count", 0),
                    "output_tokens": response.get("eval_count", 0),
                },
                latency_ms=latency_ms,
                metadata={
                    "backend": "ollama",
                    "temperature": temperature,
                    "seed": seed,
                    "total_duration_ns": response.get("total_duration"),
                },
            )

        except Exception as e:
            self._last_error = InferenceError(
                code="inference_failed",
                message=str(e),
                retryable=True,
            )
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
        """Perform streaming inference using Ollama."""
        if self._session is None:
            await self.initialize()

        try:
            request_body = {
                "model": self._model_id,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            if system_prompt:
                request_body["system"] = system_prompt

            if seed is not None:
                request_body["options"]["seed"] = seed

            async with self._session.post(
                f"{self._base_url}/api/generate",
                json=request_body,
            ) as resp:
                async for line in resp.content:
                    if line:
                        import json
                        chunk = json.loads(line)
                        if chunk.get("response"):
                            yield chunk["response"]
                        if chunk.get("done"):
                            break

        except Exception as e:
            self._last_error = InferenceError(
                code="streaming_failed",
                message=str(e),
                retryable=True,
            )
            raise

    async def health_check(self) -> bool:
        """Check if Ollama is healthy."""
        try:
            if self._session is None:
                await self.initialize()

            async with self._session.get(f"{self._base_url}/api/tags") as resp:
                if resp.status == 200:
                    self._status = BackendStatus.HEALTHY
                    return True

            self._status = BackendStatus.UNAVAILABLE
            return False

        except Exception:
            self._status = BackendStatus.UNAVAILABLE
            return False

    async def shutdown(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._status = BackendStatus.UNAVAILABLE
