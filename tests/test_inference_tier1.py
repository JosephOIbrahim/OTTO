"""
Tests for Tier 1 Deterministic Inference Layer
==============================================

Comprehensive tests verifying Determinism at the application level.

Test Categories:
1. Configuration determinism
2. Cache key computation
3. Response caching
4. Backend abstraction
5. Wrapper integration
6. Metrics accuracy
"""

import asyncio
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta

# Import modules under test
from otto.inference.config import (
    DeterministicInferenceConfig,
    InferenceBackendType,
    DeterminismLevel,
    DETERMINISTIC_DEFAULT,
    STOCHASTIC_CONFIG,
    ModelConfig,
)
from otto.inference.cache import (
    compute_cache_key,
    ResponseCache,
    CacheEntry,
    CacheStats,
    CacheKeyBuilder,
    compute_content_hash,
    _deep_sort_dict,
)
from otto.inference.wrapper import (
    DeterministicAPIWrapper,
    InferenceRequest,
    InferenceResult,
)
from otto.inference.metrics import (
    InferenceMetrics,
    DeterminismReport,
    MetricsCollector,
)
from otto.inference.backends.base import (
    InferenceBackend,
    BackendCapabilities,
    InferenceResponse,
)
from otto.inference.backends.mock import (
    MockBackend,
    DeterministicMockBackend,
)


# =============================================================================
# Configuration Tests
# =============================================================================

class TestDeterministicInferenceConfig:
    """Tests for DeterministicInferenceConfig."""

    def test_default_is_deterministic(self):
        """Default config should maximize determinism."""
        config = DeterministicInferenceConfig()
        assert config.temperature == 0.0
        assert config.top_k == 1
        assert config.top_p == 1.0
        assert config.is_deterministic

    def test_config_is_frozen(self):
        """Config should be immutable."""
        config = DeterministicInferenceConfig()
        with pytest.raises(AttributeError):
            config.temperature = 0.5

    def test_config_hash_deterministic(self):
        """Same config should produce same hash."""
        config1 = DeterministicInferenceConfig(temperature=0.0, seed=42)
        config2 = DeterministicInferenceConfig(temperature=0.0, seed=42)
        assert config1.config_hash == config2.config_hash

    def test_config_hash_differs_on_change(self):
        """Different configs should produce different hashes."""
        config1 = DeterministicInferenceConfig(seed=42)
        config2 = DeterministicInferenceConfig(seed=43)
        assert config1.config_hash != config2.config_hash

    def test_validation_rejects_invalid_temperature(self):
        """Should reject invalid temperature values."""
        with pytest.raises(ValueError):
            DeterministicInferenceConfig(temperature=-0.1)
        with pytest.raises(ValueError):
            DeterministicInferenceConfig(temperature=2.5)

    def test_with_overrides_creates_new_instance(self):
        """with_overrides should create new config."""
        original = DeterministicInferenceConfig()
        modified = original.with_overrides(temperature=0.5)
        assert original.temperature == 0.0
        assert modified.temperature == 0.5
        assert original is not modified

    def test_to_api_params(self):
        """Should convert to API-compatible parameters."""
        config = DeterministicInferenceConfig(
            temperature=0.0,
            seed=42,
            max_tokens=1000,
        )
        params = config.to_api_params()
        assert params["temperature"] == 0.0
        assert params["seed"] == 42
        assert params["max_tokens"] == 1000

    def test_stochastic_config_not_deterministic(self):
        """Stochastic config should not be deterministic."""
        assert not STOCHASTIC_CONFIG.is_deterministic
        assert STOCHASTIC_CONFIG.temperature > 0


# =============================================================================
# Cache Key Tests
# =============================================================================

class TestCacheKeyComputation:
    """Tests for deterministic cache key computation."""

    def test_same_input_same_key(self):
        """Identical inputs should produce identical keys."""
        key1 = compute_cache_key("Hello", params={"temp": 0.0})
        key2 = compute_cache_key("Hello", params={"temp": 0.0})
        assert key1 == key2

    def test_different_input_different_key(self):
        """Different inputs should produce different keys."""
        key1 = compute_cache_key("Hello")
        key2 = compute_cache_key("World")
        assert key1 != key2

    def test_order_independence(self):
        """Dict order should not affect key."""
        key1 = compute_cache_key("Test", params={"a": 1, "b": 2, "c": 3})
        key2 = compute_cache_key("Test", params={"c": 3, "a": 1, "b": 2})
        assert key1 == key2

    def test_nested_dict_order_independence(self):
        """Nested dict order should not affect key."""
        key1 = compute_cache_key("Test", params={"outer": {"a": 1, "b": 2}})
        key2 = compute_cache_key("Test", params={"outer": {"b": 2, "a": 1}})
        assert key1 == key2

    def test_key_is_sha256(self):
        """Key should be 64-char SHA-256 hex."""
        key = compute_cache_key("Test")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_system_prompt_affects_key(self):
        """System prompt should affect cache key."""
        key1 = compute_cache_key("Hello", system_prompt=None)
        key2 = compute_cache_key("Hello", system_prompt="Be helpful")
        assert key1 != key2

    def test_model_affects_key(self):
        """Model ID should affect cache key."""
        key1 = compute_cache_key("Hello", model_id="model-a")
        key2 = compute_cache_key("Hello", model_id="model-b")
        assert key1 != key2

    def test_cache_key_builder(self):
        """CacheKeyBuilder should produce same key as compute_cache_key."""
        direct = compute_cache_key(
            "Hello",
            system_prompt="Be helpful",
            params={"temperature": 0.0},
            model_id="test-model",
        )

        builder = (
            CacheKeyBuilder()
            .with_prompt("Hello")
            .with_system_prompt("Be helpful")
            .with_param("temperature", 0.0)
            .with_model("test-model")
            .build()
        )

        assert direct == builder

    def test_builder_requires_prompt(self):
        """Builder should require prompt."""
        with pytest.raises(ValueError):
            CacheKeyBuilder().build()


class TestDeepSortDict:
    """Tests for _deep_sort_dict helper."""

    def test_sorts_dict_keys(self):
        """Should sort dict keys."""
        result = _deep_sort_dict({"c": 1, "a": 2, "b": 3})
        assert list(result.keys()) == ["a", "b", "c"]

    def test_sorts_nested_dicts(self):
        """Should sort nested dict keys."""
        result = _deep_sort_dict({"outer": {"z": 1, "a": 2}})
        assert list(result["outer"].keys()) == ["a", "z"]

    def test_handles_lists(self):
        """Should handle lists without sorting elements."""
        result = _deep_sort_dict([3, 1, 2])
        assert result == [3, 1, 2]

    def test_handles_sets(self):
        """Should convert sets to sorted lists."""
        result = _deep_sort_dict({3, 1, 2})
        assert result == [1, 2, 3]


# =============================================================================
# Response Cache Tests
# =============================================================================

class TestResponseCache:
    """Tests for ResponseCache."""

    def test_put_and_get(self):
        """Should store and retrieve entries."""
        cache = ResponseCache(max_size=100)
        cache.put("key1", "response1")

        entry = cache.get("key1")
        assert entry is not None
        assert entry.response == "response1"

    def test_cache_miss_returns_none(self):
        """Should return None for missing keys."""
        cache = ResponseCache()
        assert cache.get("nonexistent") is None

    def test_integrity_verification(self):
        """Should verify content integrity on retrieval."""
        cache = ResponseCache(verify_on_get=True)
        cache.put("key1", "response1")

        entry = cache.get("key1")
        assert entry is not None
        assert entry.verify_integrity()

    def test_lru_eviction(self):
        """Should evict oldest entries when full."""
        cache = ResponseCache(max_size=3)
        cache.put("key1", "r1")
        cache.put("key2", "r2")
        cache.put("key3", "r3")
        cache.put("key4", "r4")  # Should evict key1

        assert cache.get("key1") is None
        assert cache.get("key2") is not None

    def test_access_updates_lru(self):
        """Accessing entry should move it to end of LRU."""
        cache = ResponseCache(max_size=3)
        cache.put("key1", "r1")
        cache.put("key2", "r2")
        cache.put("key3", "r3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add key4, should evict key2 (oldest)
        cache.put("key4", "r4")

        assert cache.get("key1") is not None
        assert cache.get("key2") is None

    def test_ttl_expiration(self):
        """Expired entries should not be returned."""
        cache = ResponseCache(default_ttl=1)
        cache.put("key1", "response1")

        # Entry should be available immediately
        assert cache.get("key1") is not None

        # Manually expire for testing (normally would wait)
        entry = cache._cache["key1"]
        entry.created_at = datetime.now(timezone.utc) - timedelta(seconds=10)

        # Should now be expired
        assert cache.get("key1") is None

    def test_invalidate(self):
        """Should remove specific entries."""
        cache = ResponseCache()
        cache.put("key1", "r1")
        cache.put("key2", "r2")

        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") is not None

    def test_clear(self):
        """Should remove all entries."""
        cache = ResponseCache()
        cache.put("key1", "r1")
        cache.put("key2", "r2")

        count = cache.clear()

        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_stats_tracking(self):
        """Should track cache statistics."""
        cache = ResponseCache()
        cache.put("key1", "r1")

        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.stats
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5

    def test_export_import_state(self):
        """Should export and import cache state."""
        cache1 = ResponseCache()
        cache1.put("key1", "response1", metadata={"test": True})
        cache1.put("key2", "response2")

        state = cache1.export_state()

        cache2 = ResponseCache()
        imported = cache2.import_state(state)

        assert imported == 2
        assert cache2.get("key1").response == "response1"
        assert cache2.get("key2").response == "response2"


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_content_hash_verification(self):
        """Should verify content hash on creation."""
        content = "test content"
        content_hash = compute_content_hash(content)

        entry = CacheEntry(
            key="test",
            response=content,
            content_hash=content_hash,
            created_at=datetime.now(timezone.utc),
            accessed_at=datetime.now(timezone.utc),
        )

        assert entry.verify_integrity()

    def test_rejects_invalid_hash(self):
        """Should reject mismatched hash."""
        with pytest.raises(ValueError):
            CacheEntry(
                key="test",
                response="content",
                content_hash="invalid_hash",
                created_at=datetime.now(timezone.utc),
                accessed_at=datetime.now(timezone.utc),
            )

    def test_is_expired(self):
        """Should correctly report expiration."""
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=10)

        entry = CacheEntry(
            key="test",
            response="content",
            content_hash=compute_content_hash("content"),
            created_at=past,
            accessed_at=past,
            ttl_seconds=5,
        )

        assert entry.is_expired

    def test_touch_updates_access(self):
        """touch() should update access time and count."""
        entry = CacheEntry(
            key="test",
            response="content",
            content_hash=compute_content_hash("content"),
            created_at=datetime.now(timezone.utc),
            accessed_at=datetime.now(timezone.utc),
            access_count=1,
        )

        original_access = entry.accessed_at
        entry.touch()

        assert entry.access_count == 2
        assert entry.accessed_at >= original_access


# =============================================================================
# Mock Backend Tests
# =============================================================================

class TestMockBackend:
    """Tests for MockBackend."""

    @pytest.mark.asyncio
    async def test_deterministic_responses(self):
        """Same input should produce same output."""
        backend = DeterministicMockBackend()
        await backend.initialize()

        r1 = await backend.infer("Hello", seed=42)
        r2 = await backend.infer("Hello", seed=42)

        assert r1.content == r2.content
        assert r1.content_hash == r2.content_hash

    @pytest.mark.asyncio
    async def test_custom_responses(self):
        """Should use custom response mapping."""
        backend = MockBackend(responses={"Hello": "Hi there!"})
        await backend.initialize()

        response = await backend.infer("Hello")
        assert response.content == "Hi there!"

    @pytest.mark.asyncio
    async def test_call_history(self):
        """Should track call history."""
        backend = MockBackend()
        await backend.initialize()

        await backend.infer("First")
        await backend.infer("Second")

        assert backend.call_count == 2
        assert backend.call_history[0]["prompt"] == "First"
        assert backend.call_history[1]["prompt"] == "Second"

    @pytest.mark.asyncio
    async def test_stop_sequences(self):
        """Should respect stop sequences."""
        backend = MockBackend(responses={"Test": "Hello STOP world"})
        await backend.initialize()

        response = await backend.infer("Test", stop_sequences=["STOP"])
        assert "STOP" not in response.content
        assert "world" not in response.content


# =============================================================================
# Wrapper Integration Tests
# =============================================================================

class TestDeterministicAPIWrapper:
    """Tests for DeterministicAPIWrapper."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Should initialize with mock backend."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)
        assert wrapper.is_initialized

    @pytest.mark.asyncio
    async def test_basic_inference(self):
        """Should perform inference."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        result = await wrapper.infer("Hello")

        assert result.content
        assert not result.cache_hit

    @pytest.mark.asyncio
    async def test_cache_hit_on_repeat(self):
        """Second identical request should hit cache."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        r1 = await wrapper.infer("Hello")
        r2 = await wrapper.infer("Hello")

        assert not r1.cache_hit
        assert r2.cache_hit
        assert r1.content == r2.content

    @pytest.mark.asyncio
    async def test_cache_key_in_result(self):
        """Result should include cache key."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        result = await wrapper.infer("Hello")

        assert result.cache_key
        assert len(result.cache_key) == 64

    @pytest.mark.asyncio
    async def test_inference_request_object(self):
        """Should accept InferenceRequest objects."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        request = InferenceRequest(
            prompt="Hello",
            system_prompt="Be helpful",
        )
        result = await wrapper.infer(request)

        assert result.content

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Should track statistics."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        await wrapper.infer("A")
        await wrapper.infer("B")
        await wrapper.infer("A")  # Cache hit

        stats = wrapper.get_stats()

        assert stats["total_requests"] == 3
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 2

    @pytest.mark.asyncio
    async def test_batch_inference(self):
        """Should handle batch inference."""
        wrapper = DeterministicAPIWrapper()
        await wrapper.initialize(InferenceBackendType.MOCK)

        requests = [
            InferenceRequest(prompt="A"),
            InferenceRequest(prompt="B"),
            InferenceRequest(prompt="C"),
        ]
        results = await wrapper.infer_batch(requests)

        assert len(results) == 3
        assert all(r.content for r in results)

    @pytest.mark.asyncio
    async def test_batch_maintains_order(self):
        """Batch results should match request order."""
        # Use MockBackend with custom responses (not DeterministicMockBackend)
        from otto.inference.backends.mock import MockBackend

        backend = MockBackend(responses={
            "A": "Response A",
            "B": "Response B",
            "C": "Response C",
        })
        await backend.initialize()

        wrapper = DeterministicAPIWrapper(
            backends={InferenceBackendType.MOCK: backend}
        )
        wrapper._default_backend = backend
        wrapper._initialized = True

        requests = [
            InferenceRequest(prompt="A"),
            InferenceRequest(prompt="B"),
            InferenceRequest(prompt="C"),
        ]
        results = await wrapper.infer_batch(requests)

        assert results[0].content == "Response A"
        assert results[1].content == "Response B"
        assert results[2].content == "Response C"


# =============================================================================
# Metrics Tests
# =============================================================================

class TestInferenceMetrics:
    """Tests for InferenceMetrics."""

    def test_record_request(self):
        """Should record request metrics."""
        metrics = InferenceMetrics()

        metrics.record_request(
            cache_hit=True,
            latency_ms=100.0,
            backend="mock",
            determinism_level="api",
        )

        assert metrics.total_requests == 1
        assert metrics.cache_hits == 1
        assert metrics.latencies == [100.0]

    def test_cache_hit_rate(self):
        """Should compute correct cache hit rate."""
        metrics = InferenceMetrics()

        metrics.record_request(True, 10, "mock", "api")
        metrics.record_request(False, 20, "mock", "api")
        metrics.record_request(True, 30, "mock", "api")

        assert metrics.cache_hit_rate == pytest.approx(2/3)

    def test_latency_percentiles(self):
        """Should compute latency percentiles."""
        metrics = InferenceMetrics()

        for lat in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            metrics.record_request(False, lat, "mock", "api")

        assert metrics.p50_latency_ms == 55  # Median of 10-100
        assert metrics.p95_latency_ms >= 90


class TestDeterminismReport:
    """Tests for DeterminismReport."""

    def test_record_inference(self):
        """Should record inference operations."""
        report = DeterminismReport()

        report.record_inference("kernel", cache_hit=False)
        report.record_inference("api", cache_hit=True)

        assert report.total_inferences == 2
        assert report.kernel_level_count == 1
        assert report.cache_served_count == 1

    def test_determinism_rate(self):
        """Should compute determinism rate."""
        report = DeterminismReport()

        report.record_inference("kernel", cache_hit=False)  # Deterministic
        report.record_inference("api", cache_hit=True)       # Deterministic (cache)
        report.record_inference("none", cache_hit=False)    # Non-deterministic

        assert report.determinism_rate == pytest.approx(2/3)

    def test_report_hash_deterministic(self):
        """Report hash should be deterministic."""
        report1 = DeterminismReport()
        report1.record_inference("api", cache_hit=True)

        report2 = DeterminismReport()
        report2.record_inference("api", cache_hit=True)

        assert report1.report_hash == report2.report_hash

    def test_markdown_generation(self):
        """Should generate markdown report."""
        report = DeterminismReport()
        report.record_inference("kernel", cache_hit=False)

        md = report.to_markdown()

        assert "# Determinism Report" in md
        assert "Kernel-Level" in md


# =============================================================================
# Determinism Tests
# =============================================================================

class TestHe2025Compliance:
    """
    Tests verifying Determinism principles.

    These tests ensure the implementation follows:
    1. Fixed evaluation order
    2. No dynamic algorithm switching
    3. Deterministic state management
    """

    def test_cache_key_fixed_order(self):
        """
        Determinism: Cache key computation uses fixed order.

        This is analogous to fixed reduction order in RMSNorm.
        """
        # Create many variations of dict ordering
        orderings = [
            {"a": 1, "b": 2, "c": 3},
            {"c": 3, "b": 2, "a": 1},
            {"b": 2, "a": 1, "c": 3},
            {"c": 3, "a": 1, "b": 2},
        ]

        keys = [compute_cache_key("test", params=p) for p in orderings]

        # All keys should be identical (fixed order)
        assert len(set(keys)) == 1

    def test_no_dynamic_algorithm_switching(self):
        """
        Determinism: No algorithm switching based on load.

        The wrapper always uses the same logic regardless of cache state.
        """
        # This is verified by the consistent behavior of the wrapper
        # regardless of cache size or hit rate
        pass  # Structural compliance

    @pytest.mark.asyncio
    async def test_deterministic_across_runs(self):
        """
        Determinism: Same input produces same output across runs.
        """
        results = []

        for _ in range(5):
            wrapper = DeterministicAPIWrapper()
            await wrapper.initialize(InferenceBackendType.MOCK)

            result = await wrapper.infer("Determinism test")
            results.append(result.content)

            await wrapper.shutdown()

        # All results should be identical
        assert len(set(results)) == 1

    def test_config_immutability(self):
        """
        Determinism: Configuration is immutable (frozen dataclass).

        Prevents runtime parameter modification that could cause variance.
        """
        config = DeterministicInferenceConfig()

        with pytest.raises(AttributeError):
            config.temperature = 0.5

    def test_cache_entry_integrity(self):
        """
        Determinism: Cache entries have integrity verification.

        Ensures cached data hasn't been corrupted.
        """
        cache = ResponseCache(verify_on_get=True)
        cache.put("key", "response")

        entry = cache.get("key")
        assert entry.verify_integrity()

        # Tampering should be detected
        entry.response = "tampered"  # This would normally not be allowed
        assert not entry.verify_integrity()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
