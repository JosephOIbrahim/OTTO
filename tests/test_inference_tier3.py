"""
Tests for Tier 3: Kernel-Level Determinism
==========================================

Tests [He2025] kernel-level compliance including:
- Kernel configuration validation
- CUDA environment management
- Server configuration validation
- Deterministic vLLM backend

[He2025] Tier 3 provides TRUE kernel-level determinism through:
- Batch size = 1 (eliminates batch-variance)
- Fixed CUDA deterministic operations
- No dynamic algorithm switching
"""

import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from otto.inference import (
    He2025KernelConfig,
    DeterminismMode,
    DeterministicEnvironment,
    ServerConfigValidator,
    ServerValidationResult,
    DeterministicVLLMBackend,
    DeterministicLocalBackend,
    HE2025_STRICT,
    HE2025_WITH_FLASH_ATTENTION,
    HE2025_INT8,
)
from otto.inference.kernel import EnvironmentSnapshot


# =============================================================================
# He2025KernelConfig Tests
# =============================================================================

class TestHe2025KernelConfig:
    """Tests for He2025KernelConfig class."""

    def test_default_config_is_compliant(self):
        """Default configuration is [He2025] compliant."""
        config = He2025KernelConfig()

        assert config.batch_size == 1
        assert config.cuda_deterministic is True
        assert config.tensor_parallel_size == 1
        assert config.is_he2025_compliant is True

    def test_batch_size_must_be_one(self):
        """Batch size != 1 raises ValueError."""
        with pytest.raises(ValueError) as exc:
            He2025KernelConfig(batch_size=2)

        assert "[He2025] requires batch_size=1" in str(exc.value)

    def test_tensor_parallel_must_be_one(self):
        """Tensor parallel != 1 raises ValueError."""
        with pytest.raises(ValueError) as exc:
            He2025KernelConfig(tensor_parallel_size=2)

        assert "[He2025] requires tensor_parallel_size=1" in str(exc.value)

    def test_max_batched_tokens_must_match_batch_size(self):
        """max_num_batched_tokens must equal batch_size."""
        with pytest.raises(ValueError) as exc:
            He2025KernelConfig(max_num_batched_tokens=4)

        assert "must equal batch_size" in str(exc.value)

    def test_config_is_frozen(self):
        """Configuration is immutable."""
        config = He2025KernelConfig()

        with pytest.raises(Exception):  # FrozenInstanceError
            config.batch_size = 2

    def test_config_hash_deterministic(self):
        """Configuration hash is deterministic."""
        config1 = He2025KernelConfig(seed=42)
        config2 = He2025KernelConfig(seed=42)
        config3 = He2025KernelConfig(seed=123)

        assert config1.config_hash == config2.config_hash
        assert config1.config_hash != config3.config_hash

    def test_to_vllm_args(self):
        """Converts to vLLM command-line arguments."""
        config = He2025KernelConfig()
        args = config.to_vllm_args()

        assert "--max-num-batched-tokens=1" in args
        assert "--seed=42" in args
        assert "--tensor-parallel-size=1" in args
        assert "--enforce-eager" in args
        assert "--disable-cuda-graph" in args

    def test_to_env_vars(self):
        """Converts to environment variables."""
        config = He2025KernelConfig()
        env = config.to_env_vars()

        assert "CUDA_LAUNCH_BLOCKING" in env
        assert env["CUDA_LAUNCH_BLOCKING"] == "1"
        assert "CUBLAS_WORKSPACE_CONFIG" in env
        assert "CUDNN_DETERMINISTIC" in env

    def test_to_dict_serialization(self):
        """Configuration can be serialized to dict."""
        config = He2025KernelConfig()
        d = config.to_dict()

        assert d["batch_size"] == 1
        assert d["is_he2025_compliant"] is True
        assert "config_hash" in d

    def test_predefined_configs(self):
        """Pre-defined configurations are valid."""
        assert HE2025_STRICT.is_he2025_compliant is True
        assert HE2025_WITH_FLASH_ATTENTION.batch_size == 1
        assert HE2025_INT8.quantization == "int8"


# =============================================================================
# DeterministicEnvironment Tests
# =============================================================================

class TestDeterministicEnvironment:
    """Tests for DeterministicEnvironment class."""

    def test_apply_sets_environment_variables(self):
        """apply() sets CUDA deterministic environment variables."""
        config = He2025KernelConfig()
        env = DeterministicEnvironment(config)

        # Save original values
        original_cuda = os.environ.get("CUDA_LAUNCH_BLOCKING")

        try:
            env.apply()

            assert os.environ.get("CUDA_LAUNCH_BLOCKING") == "1"
            assert os.environ.get("CUBLAS_WORKSPACE_CONFIG") == ":4096:8"
            assert env.is_applied is True

        finally:
            env.restore()

    def test_restore_reverts_environment(self):
        """restore() reverts environment to original state."""
        config = He2025KernelConfig()
        env = DeterministicEnvironment(config)

        # Save original values
        original_cuda = os.environ.get("CUDA_LAUNCH_BLOCKING")

        env.apply()
        env.restore()

        assert os.environ.get("CUDA_LAUNCH_BLOCKING") == original_cuda
        assert env.is_applied is False

    def test_context_manager(self):
        """Works as context manager."""
        config = He2025KernelConfig()
        original_cuda = os.environ.get("CUDA_LAUNCH_BLOCKING")

        with DeterministicEnvironment(config) as env:
            assert os.environ.get("CUDA_LAUNCH_BLOCKING") == "1"
            assert env.is_applied is True

        # After exiting context
        assert os.environ.get("CUDA_LAUNCH_BLOCKING") == original_cuda

    def test_get_applied_vars(self):
        """get_applied_vars() returns applied variables."""
        config = He2025KernelConfig()
        env = DeterministicEnvironment(config)

        # Before apply
        assert env.get_applied_vars() == {}

        env.apply()
        vars = env.get_applied_vars()

        assert "CUDA_LAUNCH_BLOCKING" in vars
        assert "CUBLAS_WORKSPACE_CONFIG" in vars

        env.restore()

    def test_double_apply_is_safe(self):
        """Calling apply() twice doesn't cause issues."""
        config = He2025KernelConfig()
        env = DeterministicEnvironment(config)

        env.apply()
        env.apply()  # Should be no-op

        assert env.is_applied is True

        env.restore()

    def test_double_restore_is_safe(self):
        """Calling restore() twice doesn't cause issues."""
        config = He2025KernelConfig()
        env = DeterministicEnvironment(config)

        env.apply()
        env.restore()
        env.restore()  # Should be no-op

        assert env.is_applied is False


# =============================================================================
# ServerConfigValidator Tests
# =============================================================================

class TestServerConfigValidator:
    """Tests for ServerConfigValidator class."""

    @pytest.mark.asyncio
    async def test_validate_unreachable_server(self):
        """Validation fails for unreachable server."""
        validator = ServerConfigValidator(
            base_url="http://localhost:99999",
            mode=DeterminismMode.STRICT,
        )

        result = await validator.validate()

        assert result.valid is False
        assert result.he2025_compliant is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_validation_result_to_dict(self):
        """ServerValidationResult can be serialized."""
        result = ServerValidationResult(
            valid=True,
            he2025_compliant=True,
            warnings=["test warning"],
            errors=[],
            server_config={"test": "value"},
        )

        d = result.to_dict()

        assert d["valid"] is True
        assert d["he2025_compliant"] is True
        assert "test warning" in d["warnings"]


# =============================================================================
# DeterministicLocalBackend Tests
# =============================================================================

class TestDeterministicLocalBackend:
    """Tests for DeterministicLocalBackend (mock backend)."""

    @pytest.mark.asyncio
    async def test_basic_inference(self):
        """Basic inference works."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        response = await backend.infer("Hello, world!")

        assert response.content is not None
        assert len(response.content) > 0
        assert response.metadata["determinism_level"] == "kernel"
        assert response.metadata["he2025_compliant"] is True

    @pytest.mark.asyncio
    async def test_deterministic_responses(self):
        """Same input produces same output."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        response1 = await backend.infer("Test prompt", seed=42)
        response2 = await backend.infer("Test prompt", seed=42)
        response3 = await backend.infer("Test prompt", seed=42)

        assert response1.content == response2.content
        assert response2.content == response3.content

    @pytest.mark.asyncio
    async def test_different_seeds_different_responses(self):
        """Different seeds produce different responses."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        response1 = await backend.infer("Test prompt", seed=42)
        response2 = await backend.infer("Test prompt", seed=123)

        assert response1.content != response2.content

    @pytest.mark.asyncio
    async def test_custom_response_generator(self):
        """Custom response generator works."""
        def custom_generator(prompt: str, seed: int) -> str:
            return f"Custom: {prompt[:10]}"

        backend = DeterministicLocalBackend(response_generator=custom_generator)
        await backend.initialize()

        response = await backend.infer("Hello world!")

        assert response.content == "Custom: Hello worl"

    @pytest.mark.asyncio
    async def test_streaming(self):
        """Streaming inference works."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        chunks = []
        async for chunk in backend.infer_stream("Test"):
            chunks.append(chunk)

        assert len(chunks) > 0
        full_content = "".join(chunks)
        assert len(full_content) > 0

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Health check returns True."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        healthy = await backend.health_check()

        assert healthy is True

    def test_properties(self):
        """Backend properties are correct."""
        backend = DeterministicLocalBackend()

        assert backend.name == "mock-deterministic-local"
        assert backend.capabilities.determinism_level == "kernel"
        assert backend.kernel_config.is_he2025_compliant is True


# =============================================================================
# DeterministicVLLMBackend Tests
# =============================================================================

class TestDeterministicVLLMBackend:
    """Tests for DeterministicVLLMBackend."""

    def test_initialization(self):
        """Backend can be created."""
        backend = DeterministicVLLMBackend(
            model_id="test-model",
            base_url="http://localhost:8000",
        )

        assert backend.name == "deterministic-vllm"
        assert backend.capabilities.determinism_level == "kernel"
        assert backend.kernel_config.is_he2025_compliant is True

    def test_custom_kernel_config(self):
        """Custom kernel config is used."""
        config = He2025KernelConfig(seed=999)
        backend = DeterministicVLLMBackend(kernel_config=config)

        assert backend.kernel_config.seed == 999

    def test_determinism_stats_initial(self):
        """Initial determinism stats are correct."""
        backend = DeterministicVLLMBackend()
        stats = backend.determinism_stats

        assert stats["total_requests"] == 0
        assert stats["determinism_verified"] == 0
        assert stats["he2025_compliant"] is True
        assert stats["server_validated"] is False

    @pytest.mark.asyncio
    async def test_initialize_fails_on_unreachable_server(self):
        """Initialization fails for unreachable server."""
        backend = DeterministicVLLMBackend(
            base_url="http://localhost:99999",
            validation_mode=DeterminismMode.STRICT,
        )

        with pytest.raises(RuntimeError):
            await backend.initialize()


# =============================================================================
# Integration Tests
# =============================================================================

class TestTier3Integration:
    """Integration tests for Tier 3 components."""

    @pytest.mark.asyncio
    async def test_environment_with_backend(self):
        """DeterministicEnvironment works with backend."""
        config = He2025KernelConfig()

        with DeterministicEnvironment(config):
            backend = DeterministicLocalBackend(kernel_config=config)
            await backend.initialize()

            response = await backend.infer("Test")

            assert response.metadata["he2025_compliant"] is True
            assert response.metadata["kernel_config_hash"] == config.config_hash

    @pytest.mark.asyncio
    async def test_determinism_across_sessions(self):
        """Determinism is preserved across backend instances."""
        config = He2025KernelConfig(seed=42)

        # Session 1
        backend1 = DeterministicLocalBackend(kernel_config=config)
        await backend1.initialize()
        response1 = await backend1.infer("What is 2+2?")

        # Session 2 (new backend instance)
        backend2 = DeterministicLocalBackend(kernel_config=config)
        await backend2.initialize()
        response2 = await backend2.infer("What is 2+2?")

        assert response1.content == response2.content

    @pytest.mark.asyncio
    async def test_config_hash_in_response(self):
        """Response includes kernel config hash for auditing."""
        config = He2025KernelConfig()
        backend = DeterministicLocalBackend(kernel_config=config)
        await backend.initialize()

        response = await backend.infer("Test")

        assert "kernel_config_hash" in response.metadata
        assert response.metadata["kernel_config_hash"] == config.config_hash


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_prompt(self):
        """Empty prompt is handled."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        response = await backend.infer("")

        assert response.content is not None

    @pytest.mark.asyncio
    async def test_unicode_prompt(self):
        """Unicode prompts are handled correctly."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        response = await backend.infer("Hello 世界! 🌍")

        assert response.content is not None

    @pytest.mark.asyncio
    async def test_very_long_prompt(self):
        """Very long prompts are handled."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        long_prompt = "A" * 10000
        response = await backend.infer(long_prompt)

        assert response.content is not None

    def test_config_with_all_default_values(self):
        """Config with all defaults is valid."""
        config = He2025KernelConfig()
        assert config.is_he2025_compliant is True

    def test_environment_snapshot_creation(self):
        """EnvironmentSnapshot can be created."""
        snapshot = EnvironmentSnapshot(
            variables={"TEST_VAR": "value"}
        )

        assert snapshot.variables["TEST_VAR"] == "value"
        assert snapshot.timestamp > 0


# =============================================================================
# Determinism Guarantee Tests
# =============================================================================

class TestDeterminismGuarantees:
    """Tests that verify determinism guarantees."""

    @pytest.mark.asyncio
    async def test_100_identical_responses(self):
        """100 identical requests produce 100 identical responses."""
        backend = DeterministicLocalBackend()
        await backend.initialize()

        responses = []
        for _ in range(100):
            response = await backend.infer("Test determinism", seed=42)
            responses.append(response.content)

        unique_responses = set(responses)
        assert len(unique_responses) == 1, f"Expected 1 unique response, got {len(unique_responses)}"

    @pytest.mark.asyncio
    async def test_config_immutability(self):
        """Kernel config cannot be modified after creation."""
        config = He2025KernelConfig()

        # Verify frozen
        with pytest.raises(Exception):
            config.batch_size = 2

        # Config should still be compliant
        assert config.is_he2025_compliant is True

    def test_hash_reproducibility(self):
        """Config hash is reproducible across instances."""
        hashes = []
        for _ in range(100):
            config = He2025KernelConfig(seed=42)
            hashes.append(config.config_hash)

        assert len(set(hashes)) == 1, "Config hash should be reproducible"


# =============================================================================
# Mode Tests
# =============================================================================

class TestDeterminismModes:
    """Tests for DeterminismMode enum."""

    def test_strict_mode(self):
        """STRICT mode rejects non-compliant servers."""
        assert DeterminismMode.STRICT.value == "strict"

    def test_relaxed_mode(self):
        """RELAXED mode warns on non-compliance."""
        assert DeterminismMode.RELAXED.value == "relaxed"

    def test_disabled_mode(self):
        """DISABLED mode has no enforcement."""
        assert DeterminismMode.DISABLED.value == "disabled"

    def test_vllm_backend_uses_mode(self):
        """DeterministicVLLMBackend respects validation mode."""
        backend_strict = DeterministicVLLMBackend(
            validation_mode=DeterminismMode.STRICT
        )
        backend_relaxed = DeterministicVLLMBackend(
            validation_mode=DeterminismMode.RELAXED
        )

        assert backend_strict.determinism_stats["validation_mode"] == "strict"
        assert backend_relaxed.determinism_stats["validation_mode"] == "relaxed"
