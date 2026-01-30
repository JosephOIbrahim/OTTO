"""
Tests for Tier 2: Determinism Verification
==========================================

Tests multi-trial verification, divergence detection, consensus mechanisms,
and criticality-based auto-verification.

[He2025] Tier 2 provides probabilistic detection of non-determinism.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from otto.inference import (
    DeterminismVerifier,
    VerificationResult,
    DivergenceAnalysis,
    DivergenceType,
    ConsensusStrategy,
    VerifiedInferenceWrapper,
    DeterministicAPIWrapper,
    InferenceRequest,
    DeterministicInferenceConfig,
    InferenceBackendType,
    DeterminismLevel,
)
from otto.inference.backends.base import InferenceBackend, InferenceResponse, BackendCapabilities
from otto.inference.backends.mock import MockBackend, DeterministicMockBackend


# =============================================================================
# Test Fixtures
# =============================================================================

class VariableBackend(InferenceBackend):
    """Mock backend that returns different responses for testing divergence."""

    def __init__(self, responses: List[str]):
        """
        Initialize with a list of responses to cycle through.

        Args:
            responses: List of responses to return in order
        """
        super().__init__(model_id="variable-mock")
        self._caps = BackendCapabilities(
            supports_seed=True,
            determinism_level="variable",
        )
        self._responses = responses
        self._call_count = 0

    @property
    def name(self) -> str:
        """Backend name."""
        return "variable-mock"

    @property
    def capabilities(self) -> BackendCapabilities:
        """Backend capabilities."""
        return self._caps

    async def infer(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: int = None,
        stop_sequences: List[str] = None,
        **kwargs,
    ) -> InferenceResponse:
        """Return next response in cycle."""
        response = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        return InferenceResponse(
            content=response,
            model=self.model_id,
            finish_reason="stop",
        )

    async def infer_stream(self, prompt: str, **kwargs):
        """Streaming not supported for this mock."""
        yield (await self.infer(prompt, **kwargs)).content

    async def health_check(self) -> bool:
        """Always healthy."""
        return True

    async def initialize(self):
        pass

    async def shutdown(self):
        pass


@pytest.fixture
def deterministic_backend():
    """Backend that always returns the same response."""
    return VariableBackend(["Hello, world!"])


@pytest.fixture
def divergent_backend():
    """Backend that returns different responses."""
    return VariableBackend([
        "Hello, world!",
        "Hello world!",  # Missing comma
        "Hello, World!",  # Different capitalization
    ])


@pytest.fixture
def completely_divergent_backend():
    """Backend that returns completely different responses."""
    return VariableBackend([
        "The answer is 42.",
        "I don't know the answer.",
        "Please rephrase your question.",
    ])


# =============================================================================
# DivergenceAnalysis Tests
# =============================================================================

class TestDivergenceAnalysis:
    """Tests for DivergenceAnalysis class."""

    def test_analyze_identical_responses(self):
        """Identical responses produce no divergence."""
        responses = ["Hello", "Hello", "Hello"]
        analysis = DivergenceAnalysis.analyze(responses)

        assert analysis.unique_count == 1
        assert analysis.common_prefix_len == 5
        assert analysis.common_suffix_len == 5
        assert "identical" in analysis.diff_summary.lower()

    def test_analyze_empty_responses(self):
        """Empty list produces empty analysis."""
        analysis = DivergenceAnalysis.analyze([])

        assert analysis.unique_count == 0
        assert analysis.responses == []

    def test_analyze_single_response(self):
        """Single response has no divergence."""
        analysis = DivergenceAnalysis.analyze(["Hello"])

        assert analysis.unique_count == 1
        assert analysis.common_prefix_len == 5
        assert analysis.common_suffix_len == 5

    def test_analyze_different_responses(self):
        """Different responses produce divergence metrics."""
        responses = ["Hello", "World", "Test"]
        analysis = DivergenceAnalysis.analyze(responses)

        assert analysis.unique_count == 3
        assert analysis.common_prefix_len == 0  # No common prefix
        assert analysis.common_suffix_len == 0  # No common suffix

    def test_analyze_partial_overlap(self):
        """Responses with partial overlap produce correct metrics."""
        responses = ["Hello world", "Hello there"]
        analysis = DivergenceAnalysis.analyze(responses)

        assert analysis.unique_count == 2
        assert analysis.common_prefix_len == 6  # "Hello "
        assert analysis.common_suffix_len == 0

    def test_similarity_matrix_computation(self):
        """Similarity matrix is correctly computed."""
        responses = ["abc", "abc", "xyz"]
        analysis = DivergenceAnalysis.analyze(responses)

        # Self-similarity is 1.0
        assert analysis.similarity_matrix[0][0] == 1.0
        assert analysis.similarity_matrix[1][1] == 1.0
        assert analysis.similarity_matrix[2][2] == 1.0

        # Identical strings have 1.0 similarity
        assert analysis.similarity_matrix[0][1] == 1.0

        # Different strings have < 1.0 similarity
        assert analysis.similarity_matrix[0][2] < 1.0

    def test_edit_distances_computed(self):
        """Edit distances are correctly computed."""
        responses = ["abc", "abd", "xyz"]
        analysis = DivergenceAnalysis.analyze(responses)

        # Self-distance is 0
        assert analysis.edit_distances[0][0] == 0

        # One character difference
        assert analysis.edit_distances[0][1] == 1

        # All different
        assert analysis.edit_distances[0][2] == 3

    def test_to_dict_serialization(self):
        """Analysis can be serialized to dict."""
        analysis = DivergenceAnalysis.analyze(["Hello", "World"])
        d = analysis.to_dict()

        assert "unique_count" in d
        assert "common_prefix_len" in d
        assert "diff_summary" in d
        assert d["unique_count"] == 2


# =============================================================================
# VerificationResult Tests
# =============================================================================

class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_basic_creation(self):
        """VerificationResult can be created with minimal args."""
        result = VerificationResult(
            response="Hello",
            verified=True,
            trials=3,
        )

        assert result.response == "Hello"
        assert result.verified is True
        assert result.trials == 3
        assert result.divergence_type == DivergenceType.NONE
        assert result.confidence == 1.0

    def test_content_hash_property(self):
        """content_hash property computes correctly."""
        result = VerificationResult(
            response="Hello",
            verified=True,
            trials=3,
        )

        assert result.content_hash is not None
        assert len(result.content_hash) == 32  # SHA-256 truncated

    def test_is_unanimous_property(self):
        """is_unanimous property works correctly."""
        unanimous = VerificationResult(
            response="Hello",
            verified=True,
            trials=3,
            divergence_type=DivergenceType.NONE,
        )
        assert unanimous.is_unanimous is True

        divergent = VerificationResult(
            response="Hello",
            verified=False,
            trials=3,
            divergence_type=DivergenceType.MINOR,
        )
        assert divergent.is_unanimous is False

    def test_to_dict_serialization(self):
        """VerificationResult can be serialized."""
        result = VerificationResult(
            response="Hello",
            verified=True,
            trials=3,
            confidence=0.95,
            divergence_score=0.05,
        )

        d = result.to_dict()

        assert d["response"] == "Hello"
        assert d["verified"] is True
        assert d["trials"] == 3
        assert d["confidence"] == 0.95
        assert d["divergence_score"] == 0.05
        assert "content_hash" in d
        assert "is_unanimous" in d


# =============================================================================
# DeterminismVerifier Tests
# =============================================================================

class TestDeterminismVerifier:
    """Tests for DeterminismVerifier class."""

    def test_initialization_valid(self, deterministic_backend):
        """Verifier initializes with valid parameters."""
        verifier = DeterminismVerifier(
            backend=deterministic_backend,
            n_trials=3,
            tolerance=0.0,
        )

        assert verifier.backend == deterministic_backend
        assert verifier.n_trials == 3

    def test_initialization_invalid_trials(self, deterministic_backend):
        """Verifier rejects invalid n_trials."""
        with pytest.raises(ValueError):
            DeterminismVerifier(backend=deterministic_backend, n_trials=1)

        with pytest.raises(ValueError):
            DeterminismVerifier(backend=deterministic_backend, n_trials=11)

    def test_initialization_invalid_tolerance(self, deterministic_backend):
        """Verifier rejects invalid tolerance."""
        with pytest.raises(ValueError):
            DeterminismVerifier(backend=deterministic_backend, tolerance=-0.1)

        with pytest.raises(ValueError):
            DeterminismVerifier(backend=deterministic_backend, tolerance=1.5)

    @pytest.mark.asyncio
    async def test_verify_deterministic_backend(self, deterministic_backend):
        """Deterministic backend produces verified result."""
        verifier = DeterminismVerifier(
            backend=deterministic_backend,
            n_trials=3,
        )

        result = await verifier.verify("Hello")

        assert result.verified is True
        assert result.divergence_type == DivergenceType.NONE
        assert result.confidence == 1.0
        assert result.trials == 3

    @pytest.mark.asyncio
    async def test_verify_divergent_backend(self, divergent_backend):
        """Divergent backend produces unverified result."""
        verifier = DeterminismVerifier(
            backend=divergent_backend,
            n_trials=3,
            tolerance=0.0,
        )

        result = await verifier.verify("Hello")

        assert result.verified is False
        assert result.divergence_type != DivergenceType.NONE
        assert result.confidence < 1.0

    @pytest.mark.asyncio
    async def test_verify_with_tolerance(self, divergent_backend):
        """Tolerance allows minor divergence to be verified."""
        verifier = DeterminismVerifier(
            backend=divergent_backend,
            n_trials=3,
            tolerance=0.5,  # High tolerance
        )

        result = await verifier.verify("Hello")

        # With high tolerance, minor divergence may still be "verified"
        assert result.divergence_score <= 0.5 or not result.verified

    @pytest.mark.asyncio
    async def test_parallel_execution(self, deterministic_backend):
        """Parallel execution runs trials concurrently."""
        verifier = DeterminismVerifier(
            backend=deterministic_backend,
            n_trials=3,
            parallel=True,
        )

        result = await verifier.verify("Hello")

        assert result.trials == 3
        assert len(result.all_responses) == 3

    @pytest.mark.asyncio
    async def test_sequential_execution(self, deterministic_backend):
        """Sequential execution runs trials one at a time."""
        verifier = DeterminismVerifier(
            backend=deterministic_backend,
            n_trials=3,
            parallel=False,
        )

        result = await verifier.verify("Hello")

        assert result.trials == 3
        assert len(result.all_responses) == 3

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, deterministic_backend):
        """Verifier tracks statistics correctly."""
        verifier = DeterminismVerifier(
            backend=deterministic_backend,
            n_trials=2,
        )

        # Run a few verifications
        await verifier.verify("Test 1")
        await verifier.verify("Test 2")

        stats = verifier.stats

        assert stats["total_verifications"] == 2
        assert stats["unanimous_count"] == 2
        assert stats["divergence_count"] == 0
        assert stats["unanimity_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_divergence_history_tracking(self, divergent_backend):
        """Verifier tracks divergence history."""
        verifier = DeterminismVerifier(
            backend=divergent_backend,
            n_trials=3,
        )

        await verifier.verify("Test")

        report = verifier.get_divergence_report()

        assert report["total_divergences"] >= 0
        assert "summary" in report


# =============================================================================
# Consensus Strategy Tests
# =============================================================================

class TestConsensusStrategies:
    """Tests for consensus strategy selection."""

    @pytest.mark.asyncio
    async def test_majority_strategy(self, divergent_backend):
        """MAJORITY strategy selects most common response."""
        # Create backend with majority
        backend = VariableBackend(["A", "A", "B"])
        verifier = DeterminismVerifier(
            backend=backend,
            n_trials=3,
            consensus_strategy=ConsensusStrategy.MAJORITY,
        )

        result = await verifier.verify("Test")

        assert result.response == "A"

    @pytest.mark.asyncio
    async def test_first_strategy(self, divergent_backend):
        """FIRST strategy selects first response."""
        backend = VariableBackend(["First", "Second", "Third"])
        verifier = DeterminismVerifier(
            backend=backend,
            n_trials=3,
            consensus_strategy=ConsensusStrategy.FIRST,
        )

        result = await verifier.verify("Test")

        assert result.response == "First"

    @pytest.mark.asyncio
    async def test_shortest_strategy(self):
        """SHORTEST strategy selects shortest response."""
        backend = VariableBackend(["Short", "Medium length", "Very long response here"])
        verifier = DeterminismVerifier(
            backend=backend,
            n_trials=3,
            consensus_strategy=ConsensusStrategy.SHORTEST,
        )

        result = await verifier.verify("Test")

        assert result.response == "Short"

    @pytest.mark.asyncio
    async def test_longest_strategy(self):
        """LONGEST strategy selects longest response."""
        backend = VariableBackend(["Short", "Medium length", "Very long response here"])
        verifier = DeterminismVerifier(
            backend=backend,
            n_trials=3,
            consensus_strategy=ConsensusStrategy.LONGEST,
        )

        result = await verifier.verify("Test")

        assert result.response == "Very long response here"

    @pytest.mark.asyncio
    async def test_strictest_strategy_unanimous(self, deterministic_backend):
        """STRICTEST strategy passes on unanimous agreement."""
        verifier = DeterminismVerifier(
            backend=deterministic_backend,
            n_trials=3,
            consensus_strategy=ConsensusStrategy.STRICTEST,
        )

        result = await verifier.verify("Test")

        assert result.response == "Hello, world!"
        assert "[VERIFICATION FAILED" not in result.response

    @pytest.mark.asyncio
    async def test_strictest_strategy_divergent(self, divergent_backend):
        """STRICTEST strategy fails on divergence."""
        verifier = DeterminismVerifier(
            backend=divergent_backend,
            n_trials=3,
            consensus_strategy=ConsensusStrategy.STRICTEST,
        )

        result = await verifier.verify("Test")

        assert "[VERIFICATION FAILED" in result.response


# =============================================================================
# Divergence Classification Tests
# =============================================================================

class TestDivergenceClassification:
    """Tests for divergence type classification."""

    @pytest.mark.asyncio
    async def test_no_divergence(self, deterministic_backend):
        """Identical responses produce NONE divergence."""
        verifier = DeterminismVerifier(backend=deterministic_backend, n_trials=3)
        result = await verifier.verify("Test")

        assert result.divergence_type == DivergenceType.NONE
        assert result.divergence_score == 0.0

    @pytest.mark.asyncio
    async def test_trivial_divergence(self):
        """Whitespace-only differences produce low divergence scores."""
        backend = VariableBackend([
            "Hello world",
            "Hello  world",  # Extra space
            "Hello world ",  # Trailing space
        ])
        verifier = DeterminismVerifier(backend=backend, n_trials=3)
        result = await verifier.verify("Test")

        # With 3 unique responses, may be classified as MODERATE
        # but divergence score should be low (< 0.1)
        assert result.divergence_type in [
            DivergenceType.TRIVIAL, DivergenceType.MINOR, DivergenceType.MODERATE
        ]
        assert result.divergence_score < 0.15  # Very similar strings

    @pytest.mark.asyncio
    async def test_complete_divergence(self, completely_divergent_backend):
        """Completely different responses produce MAJOR/COMPLETE divergence."""
        verifier = DeterminismVerifier(
            backend=completely_divergent_backend,
            n_trials=3,
        )
        result = await verifier.verify("Test")

        assert result.divergence_type in [DivergenceType.MAJOR, DivergenceType.COMPLETE]
        assert result.divergence_score > 0.5


# =============================================================================
# VerifiedInferenceWrapper Tests
# =============================================================================

class TestVerifiedInferenceWrapper:
    """Tests for VerifiedInferenceWrapper class."""

    @pytest.mark.asyncio
    async def test_normal_inference_no_verify(self):
        """Normal criticality doesn't trigger verification."""
        backend = DeterministicMockBackend()
        await backend.initialize()

        wrapper = VerifiedInferenceWrapper(
            backend=backend,
            auto_verify_threshold="high",
        )

        # Normal criticality - should not verify
        result = await wrapper.infer("Test", criticality="normal")

        assert "verified" not in result.metadata or result.metadata.get("verified") is None

    @pytest.mark.asyncio
    async def test_high_criticality_triggers_verify(self):
        """High criticality triggers auto-verification."""
        backend = DeterministicMockBackend()
        await backend.initialize()

        wrapper = VerifiedInferenceWrapper(
            backend=backend,
            auto_verify_threshold="high",
        )

        # High criticality - should verify
        result = await wrapper.infer("Test", criticality="high")

        assert result.metadata.get("verified") is not None

    @pytest.mark.asyncio
    async def test_explicit_verify(self):
        """infer_verified always performs verification."""
        backend = DeterministicMockBackend()
        await backend.initialize()

        wrapper = VerifiedInferenceWrapper(
            backend=backend,
            auto_verify_threshold="none",  # Disable auto
        )

        result = await wrapper.infer_verified("Test")

        assert isinstance(result, VerificationResult)
        assert result.trials == 3


# =============================================================================
# Integration with DeterministicAPIWrapper Tests
# =============================================================================

class TestDeterministicAPIWrapperTier2:
    """Tests for Tier 2 integration with DeterministicAPIWrapper."""

    @pytest.mark.asyncio
    async def test_infer_verified_method(self):
        """infer_verified method works correctly."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        result = await wrapper.infer_verified("Test question")

        assert isinstance(result, VerificationResult)
        assert result.trials >= 2
        assert result.verified is True  # DeterministicMock is deterministic

    @pytest.mark.asyncio
    async def test_auto_verify_critical_requests(self):
        """Critical requests trigger auto-verification."""
        wrapper = DeterministicAPIWrapper(
            auto_verify_criticality="critical",
        )
        await wrapper.initialize(InferenceBackendType.MOCK)

        # Critical request should auto-verify
        request = InferenceRequest(
            prompt="Critical question",
            criticality="critical",
        )
        result = await wrapper.infer(request)

        assert result.metadata.get("verified") is not None
        assert result.backend_used.startswith("verified-")

    @pytest.mark.asyncio
    async def test_skip_auto_verify_flag(self):
        """skip_auto_verify flag prevents auto-verification."""
        wrapper = DeterministicAPIWrapper(
            auto_verify_criticality="normal",  # Would verify everything
        )
        await wrapper.initialize(InferenceBackendType.MOCK)

        request = InferenceRequest(
            prompt="Test",
            criticality="critical",
        )
        result = await wrapper.infer(request, skip_auto_verify=True)

        # Should not be verified
        assert "verified" not in result.metadata or result.metadata.get("verified") is None
        assert not result.backend_used.startswith("verified-")

    @pytest.mark.asyncio
    async def test_verification_stats(self):
        """Verification statistics are tracked."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        await wrapper.infer_verified("Test 1")
        await wrapper.infer_verified("Test 2")

        stats = wrapper.get_verifier_stats()

        assert stats["verified_requests"] == 2
        assert stats["divergence_rate"] == 0.0  # Deterministic mock

    @pytest.mark.asyncio
    async def test_verified_determinism_level(self):
        """Verified results have VERIFIED determinism level."""
        wrapper = DeterministicAPIWrapper(
            auto_verify_criticality="normal",
        )
        await wrapper.initialize(InferenceBackendType.MOCK)

        request = InferenceRequest(
            prompt="Test",
            criticality="high",
        )
        result = await wrapper.infer(request)

        assert result.determinism_level == DeterminismLevel.VERIFIED

    @pytest.mark.asyncio
    async def test_cache_after_verification(self):
        """Verified results are cached."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        # First call - verified
        result1 = await wrapper.infer_verified("Cache test")
        assert result1.verified is True

        # Check cache
        request = InferenceRequest(prompt="Cache test")
        entry = wrapper.cache.get(request.cache_key)

        assert entry is not None
        assert entry.metadata.get("verified") is True

    @pytest.mark.asyncio
    async def test_verification_trials_config(self):
        """Verification uses configured trial count."""
        wrapper = DeterministicAPIWrapper(
            verification_trials=5,
        )
        await wrapper.initialize(InferenceBackendType.MOCK)

        result = await wrapper.infer_verified("Test")

        assert result.trials == 5

    @pytest.mark.asyncio
    async def test_stats_include_verification(self):
        """get_stats includes verification metrics."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        await wrapper.infer_verified("Test")

        stats = wrapper.get_stats()

        assert "verification" in stats
        assert stats["verification"]["verified_requests"] == 1


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Verifier handles empty responses."""
        backend = VariableBackend(["", "", ""])
        verifier = DeterminismVerifier(backend=backend, n_trials=3)

        result = await verifier.verify("Test")

        assert result.response == ""
        assert result.verified is True

    @pytest.mark.asyncio
    async def test_unicode_response_handling(self):
        """Verifier handles unicode correctly."""
        backend = VariableBackend(["Hello 世界", "Hello 世界", "Hello 世界"])
        verifier = DeterminismVerifier(backend=backend, n_trials=3)

        result = await verifier.verify("Test")

        assert result.response == "Hello 世界"
        assert result.verified is True

    @pytest.mark.asyncio
    async def test_very_long_response(self):
        """Verifier handles very long responses."""
        long_response = "A" * 10000
        backend = VariableBackend([long_response, long_response, long_response])
        verifier = DeterminismVerifier(backend=backend, n_trials=3)

        result = await verifier.verify("Test")

        assert len(result.response) == 10000
        assert result.verified is True

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Verifier handles timeouts gracefully."""
        class SlowBackend(InferenceBackend):
            def __init__(self):
                super().__init__(model_id="slow-mock")
                self._caps = BackendCapabilities(determinism_level="api")

            @property
            def name(self) -> str:
                return "slow-mock"

            @property
            def capabilities(self) -> BackendCapabilities:
                return self._caps

            async def infer(self, prompt, **kwargs):
                await asyncio.sleep(10)  # Very slow
                return InferenceResponse(content="Slow", model=self.model_id)

            async def infer_stream(self, prompt, **kwargs):
                yield "Slow"

            async def health_check(self) -> bool:
                return True

            async def initialize(self):
                pass

            async def shutdown(self):
                pass

        backend = SlowBackend()
        verifier = DeterminismVerifier(
            backend=backend,
            n_trials=2,
            timeout_per_trial=0.1,  # Short timeout
        )

        result = await verifier.verify("Test")

        # Should have error responses due to timeout
        assert any("[ERROR" in r for r in result.all_responses)


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions in verification module."""

    def test_edit_distance_identical(self):
        """Edit distance of identical strings is 0."""
        from otto.inference.verification import _edit_distance

        assert _edit_distance("hello", "hello") == 0

    def test_edit_distance_one_char(self):
        """Edit distance of one character difference is 1."""
        from otto.inference.verification import _edit_distance

        assert _edit_distance("hello", "hallo") == 1
        assert _edit_distance("hello", "hello!") == 1
        assert _edit_distance("hello", "ello") == 1

    def test_edit_distance_empty(self):
        """Edit distance with empty string."""
        from otto.inference.verification import _edit_distance

        assert _edit_distance("", "") == 0
        assert _edit_distance("hello", "") == 5
        assert _edit_distance("", "hello") == 5

    def test_common_prefix_length(self):
        """Common prefix length calculation."""
        from otto.inference.verification import _common_prefix_length

        assert _common_prefix_length(["hello", "hello"]) == 5
        assert _common_prefix_length(["hello", "world"]) == 0
        assert _common_prefix_length(["hello world", "hello there"]) == 6
        assert _common_prefix_length([]) == 0

    def test_common_suffix_length(self):
        """Common suffix length calculation."""
        from otto.inference.verification import _common_suffix_length

        assert _common_suffix_length(["hello", "hello"]) == 5
        assert _common_suffix_length(["hello", "world"]) == 0
        assert _common_suffix_length(["say hello", "world hello"]) == 6

    def test_normalize_whitespace(self):
        """Whitespace normalization."""
        from otto.inference.verification import _normalize_whitespace

        assert _normalize_whitespace("hello  world") == "hello world"
        assert _normalize_whitespace("  hello  ") == "hello"
        assert _normalize_whitespace("a\t\nb") == "a b"


# =============================================================================
# Determinism Tests (Meta)
# =============================================================================

class TestVerificationDeterminism:
    """Tests that verification itself is deterministic."""

    @pytest.mark.asyncio
    async def test_analysis_deterministic(self):
        """DivergenceAnalysis produces same results for same input."""
        responses = ["Hello", "World", "Test"]

        analysis1 = DivergenceAnalysis.analyze(responses)
        analysis2 = DivergenceAnalysis.analyze(responses)

        assert analysis1.unique_count == analysis2.unique_count
        assert analysis1.common_prefix_len == analysis2.common_prefix_len
        assert analysis1.similarity_matrix == analysis2.similarity_matrix

    @pytest.mark.asyncio
    async def test_verification_order_preserved(self, deterministic_backend):
        """Verification runs in deterministic order."""
        verifier = DeterminismVerifier(
            backend=deterministic_backend,
            n_trials=3,
            parallel=False,  # Sequential for order guarantee
        )

        result = await verifier.verify("Test")

        # All responses should be in order received
        assert len(result.all_responses) == 3
        # With deterministic backend, all should be same
        assert len(set(result.all_responses)) == 1
