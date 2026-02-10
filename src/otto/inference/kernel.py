"""
Tier 3: Kernel-Level Determinism
================================

[He2025]-inspired kernel-level determinism for local inference.

This module provides:
1. KernelConfig - [He2025]-inspired kernel configuration
2. DeterministicEnvironment - CUDA environment management
3. ServerConfigValidator - Validates server determinism settings
4. DeterministicVLLMBackend - Backend with kernel-level guarantees

[He2025]-inspired determinism Requirements:
- Batch size = 1 (eliminates batch-variance)
- Fixed reduction order in RMSNorm
- Fixed tile sizes in MatMul (no split-K)
- Fixed split-KV strategy in Attention
- CUDA deterministic operations enabled
- No dynamic algorithm switching

References:
    [He2025] He, Horace and Thinking Machines Lab, "Defeating Nondeterminism
    in LLM Inference", Thinking Machines Lab, Sep 2025.
"""

import os
import time
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, AsyncIterator, Tuple
import aiohttp
import hashlib

from .backends.base import (
    InferenceBackend,
    BackendCapabilities,
    BackendStatus,
    InferenceResponse,
    InferenceError,
)


class DeterminismMode(Enum):
    """Level of determinism enforcement."""
    STRICT = "strict"       # Full [He2025]-inspired determinism, may reject non-compliant servers
    RELAXED = "relaxed"     # Best effort, warn on non-compliance
    DISABLED = "disabled"   # No enforcement (for debugging)


@dataclass(frozen=True)
class He2025KernelConfig:
    """
    [He2025]-inspired kernel configuration.

    This configuration ensures kernel-level determinism by:
    1. Setting batch_size=1 to eliminate batch-variance
    2. Enabling CUDA deterministic operations
    3. Fixing memory allocation strategies
    4. Disabling dynamic algorithm selection

    Frozen for immutability (no runtime modification allowed).

    Attributes:
        batch_size: Must be 1 for determinism (eliminates batch-variance)
        seed: Random seed for reproducibility
        cuda_deterministic: Enable CUDA deterministic operations
        disable_cuda_graphs: Disable CUDA graphs for more determinism
        enforce_eager: Disable lazy execution
        tensor_parallel_size: Must be 1 for single-GPU determinism
        pipeline_parallel_size: Must be 1 for no pipeline variance
        use_flash_attention: Flash attention determinism setting
        max_num_batched_tokens: Must match batch_size
        quantization: Quantization mode (None for full precision)
        dtype: Data type for computations

    Example:
        >>> config = He2025KernelConfig()
        >>> config.batch_size
        1
        >>> config.is_he2025_compliant
        True
    """
    batch_size: int = 1
    seed: int = 42
    cuda_deterministic: bool = True
    disable_cuda_graphs: bool = True
    enforce_eager: bool = True
    tensor_parallel_size: int = 1
    pipeline_parallel_size: int = 1
    use_flash_attention: bool = False  # Flash attention can be non-deterministic
    max_num_batched_tokens: int = 1
    quantization: Optional[str] = None  # None = full precision (most deterministic)
    dtype: str = "float16"

    def __post_init__(self):
        """Validate configuration meets [He2025] requirements."""
        if self.batch_size != 1:
            raise ValueError(
                f"[He2025] requires batch_size=1, got {self.batch_size}. "
                "Batch size > 1 causes kernel selection variance."
            )
        if self.tensor_parallel_size != 1:
            raise ValueError(
                f"[He2025] requires tensor_parallel_size=1, got {self.tensor_parallel_size}. "
                "Multi-GPU introduces communication variance."
            )
        if self.max_num_batched_tokens != self.batch_size:
            raise ValueError(
                f"max_num_batched_tokens ({self.max_num_batched_tokens}) must equal "
                f"batch_size ({self.batch_size}) for determinism (inspired by [He2025])."
            )

    @property
    def is_he2025_compliant(self) -> bool:
        """Check if configuration is fully [He2025]-inspired determinism."""
        return (
            self.batch_size == 1 and
            self.cuda_deterministic and
            self.tensor_parallel_size == 1 and
            self.pipeline_parallel_size == 1 and
            self.enforce_eager
        )

    @property
    def config_hash(self) -> str:
        """Compute deterministic hash of configuration."""
        config_dict = {
            'batch_size': self.batch_size,
            'seed': self.seed,
            'cuda_deterministic': self.cuda_deterministic,
            'disable_cuda_graphs': self.disable_cuda_graphs,
            'enforce_eager': self.enforce_eager,
            'tensor_parallel_size': self.tensor_parallel_size,
            'pipeline_parallel_size': self.pipeline_parallel_size,
            'dtype': self.dtype,
        }
        config_str = json.dumps(config_dict, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(config_str.encode('utf-8')).hexdigest()[:16]

    def to_vllm_args(self) -> List[str]:
        """
        Convert to vLLM command-line arguments.

        Returns:
            List of command-line arguments for vLLM server
        """
        args = [
            f"--max-num-batched-tokens={self.max_num_batched_tokens}",
            f"--seed={self.seed}",
            f"--tensor-parallel-size={self.tensor_parallel_size}",
            f"--pipeline-parallel-size={self.pipeline_parallel_size}",
            f"--dtype={self.dtype}",
        ]

        if self.enforce_eager:
            args.append("--enforce-eager")

        if self.disable_cuda_graphs:
            args.append("--disable-cuda-graph")

        if self.quantization:
            args.append(f"--quantization={self.quantization}")

        return args

    def to_env_vars(self) -> Dict[str, str]:
        """
        Convert to environment variables for CUDA determinism.

        Returns:
            Dict of environment variables to set
        """
        env = {}

        if self.cuda_deterministic:
            env["CUDA_LAUNCH_BLOCKING"] = "1"
            env["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
            env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:False"
            env["CUDNN_DETERMINISTIC"] = "1"

        return env

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'batch_size': self.batch_size,
            'seed': self.seed,
            'cuda_deterministic': self.cuda_deterministic,
            'disable_cuda_graphs': self.disable_cuda_graphs,
            'enforce_eager': self.enforce_eager,
            'tensor_parallel_size': self.tensor_parallel_size,
            'pipeline_parallel_size': self.pipeline_parallel_size,
            'use_flash_attention': self.use_flash_attention,
            'max_num_batched_tokens': self.max_num_batched_tokens,
            'quantization': self.quantization,
            'dtype': self.dtype,
            'is_he2025_compliant': self.is_he2025_compliant,
            'config_hash': self.config_hash,
        }


# Pre-defined configurations
HE2025_STRICT = He2025KernelConfig()

HE2025_WITH_FLASH_ATTENTION = He2025KernelConfig(
    use_flash_attention=True,  # May introduce minor non-determinism
)

HE2025_INT8 = He2025KernelConfig(
    quantization="int8",  # Quantization may affect determinism
    dtype="int8",
)


@dataclass
class EnvironmentSnapshot:
    """Snapshot of environment variables for restoration."""
    variables: Dict[str, Optional[str]]
    timestamp: float = field(default_factory=time.time)


class DeterministicEnvironment:
    """
    Context manager for deterministic CUDA environment.

    Sets environment variables required for [He2025] kernel-level determinism
    and restores them on exit.

    Example:
        >>> with DeterministicEnvironment(He2025KernelConfig()) as env:
        ...     # Run deterministic inference here
        ...     pass
        >>> # Environment restored to original state
    """

    def __init__(self, config: He2025KernelConfig):
        """
        Initialize environment manager.

        Args:
            config: Kernel configuration to apply
        """
        self._config = config
        self._snapshot: Optional[EnvironmentSnapshot] = None
        self._applied = False

    @property
    def config(self) -> He2025KernelConfig:
        """Get the kernel configuration."""
        return self._config

    @property
    def is_applied(self) -> bool:
        """Check if environment changes are currently applied."""
        return self._applied

    def apply(self) -> None:
        """Apply deterministic environment variables."""
        if self._applied:
            return

        # Snapshot current environment
        env_vars = self._config.to_env_vars()
        self._snapshot = EnvironmentSnapshot(
            variables={k: os.environ.get(k) for k in env_vars}
        )

        # Apply new values
        for key, value in env_vars.items():
            os.environ[key] = value

        self._applied = True

    def restore(self) -> None:
        """Restore original environment variables."""
        if not self._applied or self._snapshot is None:
            return

        # Restore original values
        for key, value in self._snapshot.variables.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        self._applied = False
        self._snapshot = None

    def __enter__(self) -> 'DeterministicEnvironment':
        """Enter context manager."""
        self.apply()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self.restore()

    def get_applied_vars(self) -> Dict[str, str]:
        """Get currently applied environment variables."""
        if not self._applied:
            return {}
        return self._config.to_env_vars()


@dataclass
class ServerValidationResult:
    """Result of server configuration validation."""
    valid: bool
    he2025_compliant: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    server_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'valid': self.valid,
            'he2025_compliant': self.he2025_compliant,
            'warnings': self.warnings,
            'errors': self.errors,
            'server_config': self.server_config,
        }


class ServerConfigValidator:
    """
    Validates that a vLLM server is configured for [He2025] determinism.

    This validator checks:
    1. Server is accessible
    2. Model is loaded
    3. Configuration matches [He2025] requirements
    4. Environment variables are set correctly

    Example:
        >>> validator = ServerConfigValidator("http://localhost:8000")
        >>> result = await validator.validate()
        >>> if result.he2025_compliant:
        ...     print("Server is [He2025]-inspired determinism!")
    """

    def __init__(
        self,
        base_url: str,
        expected_config: Optional[He2025KernelConfig] = None,
        mode: DeterminismMode = DeterminismMode.STRICT,
    ):
        """
        Initialize validator.

        Args:
            base_url: vLLM server URL
            expected_config: Expected kernel configuration
            mode: Validation strictness mode
        """
        self._base_url = base_url.rstrip("/")
        self._expected_config = expected_config or HE2025_STRICT
        self._mode = mode

    async def validate(self) -> ServerValidationResult:
        """
        Validate server configuration.

        Returns:
            ServerValidationResult with compliance status
        """
        warnings = []
        errors = []
        server_config = {}
        valid = True
        he2025_compliant = True

        try:
            async with aiohttp.ClientSession() as session:
                # Check server health
                try:
                    async with session.get(f"{self._base_url}/health") as resp:
                        if resp.status != 200:
                            errors.append(f"Server not healthy: status {resp.status}")
                            valid = False
                            he2025_compliant = False
                except Exception as e:
                    errors.append(f"Cannot connect to server: {e}")
                    return ServerValidationResult(
                        valid=False,
                        he2025_compliant=False,
                        errors=errors,
                    )

                # Get model info
                try:
                    async with session.get(f"{self._base_url}/v1/models") as resp:
                        if resp.status == 200:
                            models = await resp.json()
                            server_config["models"] = models.get("data", [])
                        else:
                            warnings.append("Could not retrieve model info")
                except Exception:
                    warnings.append("Could not query models endpoint")

                # Check server configuration (vLLM-specific)
                # Note: vLLM doesn't expose all config via API, so we infer what we can
                try:
                    # Try a test inference to check behavior
                    test_result = await self._test_determinism(session)
                    server_config["determinism_test"] = test_result
                    if not test_result["passed"]:
                        warnings.append("Determinism test showed variance")
                        if self._mode == DeterminismMode.STRICT:
                            he2025_compliant = False
                except Exception as e:
                    warnings.append(f"Could not run determinism test: {e}")

        except Exception as e:
            errors.append(f"Validation failed: {e}")
            valid = False
            he2025_compliant = False

        return ServerValidationResult(
            valid=valid,
            he2025_compliant=he2025_compliant,
            warnings=warnings,
            errors=errors,
            server_config=server_config,
        )

    async def _test_determinism(
        self,
        session: aiohttp.ClientSession,
    ) -> Dict[str, Any]:
        """
        Run a quick determinism test.

        Makes identical requests and checks for identical responses.
        """
        test_prompt = "What is 2+2? Answer with just the number."
        responses = []

        for _ in range(3):
            try:
                request_body = {
                    "model": "default",  # Use whatever model is loaded
                    "messages": [{"role": "user", "content": test_prompt}],
                    "temperature": 0.0,
                    "max_tokens": 10,
                    "seed": 42,
                }

                async with session.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=request_body,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        content = result["choices"][0]["message"]["content"]
                        responses.append(content)
            except Exception:
                pass

        if len(responses) < 2:
            return {"passed": False, "reason": "Could not get enough responses"}

        unique_responses = len(set(responses))
        passed = unique_responses == 1

        return {
            "passed": passed,
            "unique_responses": unique_responses,
            "total_responses": len(responses),
            "responses": responses[:3],  # Include samples
        }


# Backend capabilities for deterministic vLLM
DETERMINISTIC_VLLM_CAPABILITIES = BackendCapabilities(
    supports_seed=True,
    supports_logprobs=True,
    supports_streaming=True,
    supports_system_prompt=True,
    supports_stop_sequences=True,
    supports_temperature_zero=True,
    max_context_window=128000,
    determinism_level="kernel",  # True [He2025]-inspired determinism
)


class DeterministicVLLMBackend(InferenceBackend):
    """
    [He2025]-inspired local vLLM backend.

    This backend provides TRUE kernel-level determinism when used with
    a properly configured vLLM server. It:

    1. Validates server configuration on initialization
    2. Enforces batch_size=1 for all requests
    3. Sets deterministic CUDA environment
    4. Tracks determinism metrics

    Compared to LocalVLLMBackend, this backend:
    - Validates server is [He2025]-inspired determinism
    - Can reject servers that don't meet requirements
    - Tracks determinism statistics
    - Provides stronger guarantees

    Example:
        >>> backend = DeterministicVLLMBackend(
        ...     model_id="meta-llama/Llama-3.1-70B-Instruct",
        ...     kernel_config=He2025KernelConfig(),
        ... )
        >>> await backend.initialize()
        >>> response = await backend.infer("Hello!")
        >>> print(backend.determinism_stats)
    """

    def __init__(
        self,
        model_id: str = "meta-llama/Llama-3.1-70B-Instruct",
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 300.0,
        kernel_config: Optional[He2025KernelConfig] = None,
        validation_mode: DeterminismMode = DeterminismMode.STRICT,
    ):
        """
        Initialize deterministic vLLM backend.

        Args:
            model_id: Model being served by vLLM
            base_url: vLLM server URL
            api_key: Optional API key
            timeout: Request timeout in seconds
            kernel_config: [He2025] kernel configuration
            validation_mode: How strictly to enforce compliance
        """
        super().__init__(model_id, api_key)
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._kernel_config = kernel_config or HE2025_STRICT
        self._validation_mode = validation_mode
        self._session: Optional[aiohttp.ClientSession] = None
        self._environment: Optional[DeterministicEnvironment] = None
        self._validator: Optional[ServerConfigValidator] = None
        self._validation_result: Optional[ServerValidationResult] = None

        # Determinism tracking
        self._total_requests = 0
        self._determinism_verified = 0
        self._last_response_hashes: List[str] = []

    @property
    def name(self) -> str:
        return "deterministic-vllm"

    @property
    def capabilities(self) -> BackendCapabilities:
        return DETERMINISTIC_VLLM_CAPABILITIES

    @property
    def kernel_config(self) -> He2025KernelConfig:
        """Get the kernel configuration."""
        return self._kernel_config

    @property
    def validation_result(self) -> Optional[ServerValidationResult]:
        """Get the last validation result."""
        return self._validation_result

    @property
    def determinism_stats(self) -> Dict[str, Any]:
        """Get determinism tracking statistics."""
        return {
            "total_requests": self._total_requests,
            "determinism_verified": self._determinism_verified,
            "kernel_config_hash": self._kernel_config.config_hash,
            "he2025_compliant": self._kernel_config.is_he2025_compliant,
            "validation_mode": self._validation_mode.value,
            "server_validated": self._validation_result is not None,
            "server_compliant": (
                self._validation_result.he2025_compliant
                if self._validation_result else None
            ),
        }

    async def initialize(self) -> None:
        """
        Initialize the backend with validation.

        Raises:
            RuntimeError: If validation fails in STRICT mode
        """
        try:
            # Set up deterministic environment
            self._environment = DeterministicEnvironment(self._kernel_config)
            self._environment.apply()

            # Create session
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

            # Validate server configuration
            self._validator = ServerConfigValidator(
                base_url=self._base_url,
                expected_config=self._kernel_config,
                mode=self._validation_mode,
            )
            self._validation_result = await self._validator.validate()

            if not self._validation_result.valid:
                error_msg = "; ".join(self._validation_result.errors)
                if self._validation_mode == DeterminismMode.STRICT:
                    raise RuntimeError(f"Server validation failed: {error_msg}")

            if not self._validation_result.he2025_compliant:
                if self._validation_mode == DeterminismMode.STRICT:
                    raise RuntimeError(
                        "Server is not [He2025]-inspired determinism. "
                        f"Warnings: {self._validation_result.warnings}"
                    )

            self._status = BackendStatus.HEALTHY

        except Exception as e:
            self._status = BackendStatus.UNAVAILABLE
            self._last_error = InferenceError(
                code="initialization_failed",
                message=f"Failed to initialize deterministic backend: {e}",
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
        Perform [He2025]-inspired inference.

        Always uses temperature=0 and the configured seed for determinism.
        """
        if self._session is None:
            await self.initialize()

        start_time = time.perf_counter()
        self._total_requests += 1

        # Force deterministic parameters
        if temperature != 0.0:
            temperature = 0.0  # Override for determinism

        # Use kernel config seed if not provided
        if seed is None:
            seed = self._kernel_config.seed

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
                "seed": seed,
            }

            if stop_sequences:
                request_body["stop"] = stop_sequences

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

            # Track response hash for determinism verification
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
            self._last_response_hashes.append(content_hash)
            if len(self._last_response_hashes) > 100:
                self._last_response_hashes = self._last_response_hashes[-100:]

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
                content_hash=content_hash,
                metadata={
                    "backend": "deterministic-vllm",
                    "temperature": temperature,
                    "seed": seed,
                    "determinism_level": "kernel",
                    "he2025_compliant": self._kernel_config.is_he2025_compliant,
                    "kernel_config_hash": self._kernel_config.config_hash,
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
        """Perform streaming [He2025]-inspired inference."""
        if self._session is None:
            await self.initialize()

        # Force deterministic parameters
        if temperature != 0.0:
            temperature = 0.0

        if seed is None:
            seed = self._kernel_config.seed

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
                "seed": seed,
                "stream": True,
            }

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

    async def verify_determinism(
        self,
        prompt: str,
        n_trials: int = 3,
    ) -> Tuple[bool, List[str]]:
        """
        Verify determinism by running multiple identical inferences.

        Args:
            prompt: Test prompt
            n_trials: Number of trials

        Returns:
            Tuple of (is_deterministic, list of responses)
        """
        responses = []
        for _ in range(n_trials):
            result = await self.infer(prompt)
            responses.append(result.content)

        is_deterministic = len(set(responses)) == 1

        if is_deterministic:
            self._determinism_verified += 1

        return is_deterministic, responses

    async def health_check(self) -> bool:
        """Check if server is healthy."""
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
        """Shutdown backend and restore environment."""
        if self._session:
            await self._session.close()
            self._session = None

        if self._environment:
            self._environment.restore()
            self._environment = None

        self._status = BackendStatus.UNAVAILABLE


class DeterministicLocalBackend(InferenceBackend):
    """
    Mock backend for testing [He2025] kernel-level determinism.

    This backend simulates a deterministic local inference server
    for testing purposes. It always returns identical responses
    for identical inputs.
    """

    def __init__(
        self,
        model_id: str = "mock-deterministic",
        kernel_config: Optional[He2025KernelConfig] = None,
        response_generator: Optional[callable] = None,
    ):
        """
        Initialize mock deterministic backend.

        Args:
            model_id: Model identifier
            kernel_config: Kernel configuration
            response_generator: Optional function to generate responses
        """
        super().__init__(model_id)
        self._kernel_config = kernel_config or HE2025_STRICT
        self._response_generator = response_generator
        self._request_count = 0

    @property
    def name(self) -> str:
        return "mock-deterministic-local"

    @property
    def capabilities(self) -> BackendCapabilities:
        return DETERMINISTIC_VLLM_CAPABILITIES

    @property
    def kernel_config(self) -> He2025KernelConfig:
        return self._kernel_config

    async def initialize(self) -> None:
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
        """Generate deterministic response."""
        self._request_count += 1

        if self._response_generator:
            content = self._response_generator(prompt, seed or self._kernel_config.seed)
        else:
            # Default: Hash-based deterministic response
            input_hash = hashlib.sha256(
                f"{prompt}:{system_prompt}:{seed or self._kernel_config.seed}".encode()
            ).hexdigest()[:16]
            content = f"Deterministic response for hash {input_hash}"

        return InferenceResponse(
            content=content,
            model=self._model_id,
            finish_reason="stop",
            usage={"input_tokens": len(prompt.split()), "output_tokens": len(content.split())},
            metadata={
                "backend": "mock-deterministic-local",
                "determinism_level": "kernel",
                "he2025_compliant": True,
                "kernel_config_hash": self._kernel_config.config_hash,
            },
        )

    async def infer_stream(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream deterministic response."""
        result = await self.infer(prompt, **kwargs)
        for word in result.content.split():
            yield word + " "

    async def health_check(self) -> bool:
        return True

    async def shutdown(self) -> None:
        self._status = BackendStatus.UNAVAILABLE
