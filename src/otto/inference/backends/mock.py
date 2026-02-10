"""
Mock Inference Backend
======================

Deterministic mock backend for testing.

Determinism:
- Completely deterministic (same input → same output always)
- No network calls
- Configurable response patterns
"""

import hashlib
import time
from typing import Optional, List, Any, AsyncIterator, Dict, Callable

from .base import (
    InferenceBackend,
    BackendCapabilities,
    BackendStatus,
    InferenceResponse,
    InferenceError,
)

# Capabilities for mock backend
MOCK_CAPABILITIES = BackendCapabilities(
    supports_seed=True,
    supports_logprobs=True,
    supports_streaming=True,
    supports_system_prompt=True,
    supports_stop_sequences=True,
    supports_temperature_zero=True,
    max_context_window=1000000,  # Unlimited
    determinism_level="kernel",  # Perfectly deterministic
)


class MockBackend(InferenceBackend):
    """
    Mock inference backend for testing.

    Provides deterministic responses based on prompt hashing.
    Useful for testing cache behavior, error handling, and
    integration without making real API calls.

    Example:
        >>> backend = MockBackend()
        >>> await backend.initialize()
        >>> r1 = await backend.infer("Hello")
        >>> r2 = await backend.infer("Hello")
        >>> r1.content == r2.content  # Always true (deterministic)
        True

        >>> # Custom responses
        >>> backend = MockBackend(responses={"Hello": "Hi there!"})
        >>> r = await backend.infer("Hello")
        >>> r.content
        'Hi there!'
    """

    def __init__(
        self,
        model_id: str = "mock-model-v1",
        responses: Optional[Dict[str, str]] = None,
        response_generator: Optional[Callable[[str], str]] = None,
        latency_ms: float = 10.0,
        fail_rate: float = 0.0,
        fail_error: Optional[InferenceError] = None,
    ):
        """
        Initialize mock backend.

        Args:
            model_id: Mock model identifier
            responses: Dict mapping prompts to responses
            response_generator: Function to generate responses from prompts
            latency_ms: Simulated latency in milliseconds
            fail_rate: Probability of failure (0.0 to 1.0)
            fail_error: Error to raise on failure (if None, uses default)
        """
        super().__init__(model_id, None)
        self._responses = responses or {}
        self._response_generator = response_generator
        self._latency_ms = latency_ms
        self._fail_rate = fail_rate
        self._fail_error = fail_error or InferenceError(
            code="mock_error",
            message="Simulated failure",
            retryable=True,
            retry_after=1.0,
        )
        self._call_count = 0
        self._call_history: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> BackendCapabilities:
        return MOCK_CAPABILITIES

    @property
    def call_count(self) -> int:
        """Number of infer calls made."""
        return self._call_count

    @property
    def call_history(self) -> List[Dict[str, Any]]:
        """History of all infer calls."""
        return self._call_history.copy()

    def reset_history(self) -> None:
        """Reset call count and history."""
        self._call_count = 0
        self._call_history = []

    async def initialize(self) -> None:
        """Initialize the mock backend."""
        self._status = BackendStatus.HEALTHY

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
        Perform mock inference.

        Response generation (in order of precedence):
        1. Exact match in responses dict
        2. response_generator function
        3. Deterministic hash-based generation
        """
        import asyncio

        start_time = time.perf_counter()

        # Track call
        self._call_count += 1
        self._call_history.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "seed": seed,
            "kwargs": kwargs,
        })

        # Simulate latency
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000)

        # Check for simulated failure
        if self._fail_rate > 0:
            # Use deterministic "randomness" based on prompt hash
            hash_val = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
            if (hash_val % 100) < (self._fail_rate * 100):
                self._last_error = self._fail_error
                raise RuntimeError(self._fail_error.message)

        # Generate response
        content = self._generate_response(prompt, system_prompt, seed)

        # Apply stop sequences
        if stop_sequences:
            for seq in stop_sequences:
                if seq in content:
                    content = content[:content.index(seq)]

        # Truncate to max_tokens (approximate: 4 chars per token)
        max_chars = max_tokens * 4
        if len(content) > max_chars:
            content = content[:max_chars]

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Generate mock logprobs if requested
        logprobs = None
        if kwargs.get("logprobs"):
            # Deterministic mock logprobs
            logprobs = [-0.1 - (i * 0.01) for i in range(len(content.split()))]

        return InferenceResponse(
            content=content,
            model=self._model_id,
            finish_reason="stop",
            usage={
                "input_tokens": len(prompt.split()),
                "output_tokens": len(content.split()),
            },
            logprobs=logprobs,
            latency_ms=latency_ms,
            request_id=f"mock-{self._call_count}",
            metadata={
                "backend": "mock",
                "temperature": temperature,
                "seed": seed,
                "deterministic": True,
            },
        )

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
        Perform mock streaming inference.

        Yields response word by word with simulated delays.
        """
        import asyncio

        content = self._generate_response(prompt, system_prompt, seed)

        # Apply stop sequences
        if stop_sequences:
            for seq in stop_sequences:
                if seq in content:
                    content = content[:content.index(seq)]

        # Stream word by word
        words = content.split()
        for word in words:
            await asyncio.sleep(self._latency_ms / 1000 / len(words))
            yield word + " "

    async def health_check(self) -> bool:
        """Mock backends are always healthy."""
        self._status = BackendStatus.HEALTHY
        return True

    async def shutdown(self) -> None:
        """Shutdown mock backend."""
        self._status = BackendStatus.UNAVAILABLE

    def _generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str],
        seed: Optional[int],
    ) -> str:
        """
        Generate deterministic response.

        Determinism: Same inputs always produce same output.
        """
        # 1. Check for exact match in responses dict
        if prompt in self._responses:
            return self._responses[prompt]

        # 2. Use custom generator if provided
        if self._response_generator:
            return self._response_generator(prompt)

        # 3. Generate deterministic response from hash
        # Include seed in hash for reproducibility control
        hash_input = f"{prompt}:{system_prompt}:{seed}"
        hash_val = hashlib.sha256(hash_input.encode()).hexdigest()

        # Generate response based on hash
        # This is completely deterministic: same input → same output
        response_templates = [
            "I understand you're asking about {topic}. Here's my response based on the input.",
            "Thank you for your question about {topic}. Let me provide some information.",
            "Regarding {topic}, I can offer the following insights.",
            "Your query about {topic} is interesting. Here's what I think.",
        ]

        # Select template deterministically
        template_idx = int(hash_val[:2], 16) % len(response_templates)
        template = response_templates[template_idx]

        # Extract "topic" from prompt (first few words)
        topic = " ".join(prompt.split()[:5])
        if len(prompt.split()) > 5:
            topic += "..."

        response = template.format(topic=topic)

        # Add hash-based suffix for uniqueness
        response += f" [Response hash: {hash_val[:8]}]"

        return response


class DeterministicMockBackend(MockBackend):
    """
    Strictly deterministic mock backend.

    Guarantees bit-identical responses for identical inputs.
    Useful for testing Determinism.

    Example:
        >>> backend = DeterministicMockBackend()
        >>> r1 = await backend.infer("Test", seed=42)
        >>> r2 = await backend.infer("Test", seed=42)
        >>> r1.content == r2.content
        True
        >>> r1.content_hash == r2.content_hash
        True
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Disable any randomness
        self._fail_rate = 0.0

    def _generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str],
        seed: Optional[int],
    ) -> str:
        """
        Generate strictly deterministic response.

        The response is a pure function of the inputs with no randomness.
        """
        # Canonical input for hashing
        canonical = {
            "prompt": prompt,
            "system_prompt": system_prompt or "",
            "seed": seed if seed is not None else 0,
        }

        # Deterministic hash
        import json
        canonical_str = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        hash_val = hashlib.sha256(canonical_str.encode()).hexdigest()

        # Fixed response format
        return (
            f"Deterministic response for input hash {hash_val[:16]}. "
            f"Prompt length: {len(prompt)} chars. "
            f"System prompt: {'yes' if system_prompt else 'no'}. "
            f"Seed: {seed}."
        )
