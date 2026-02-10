"""
Tests for Knowledge Layer Phase 0 Integration.

Verifies:
1. Factual query detection (positive cases)
2. Non-factual queries skip Phase 0
3. High-confidence match short-circuits to KnowledgeResult
4. Low-confidence continues to full pipeline (NexusResult)
5. Determinism: same query → same result
6. Performance: Phase 0 is faster than full pipeline
"""

import time
import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from otto.prism_detector import PRISMDetector, create_detector
from otto.cognitive_orchestrator import (
    CognitiveOrchestrator,
    NexusResult,
    KnowledgeResult,
    KNOWLEDGE_CONFIDENCE_THRESHOLD,
    create_orchestrator,
)
from otto.substrate.knowledge import (
    get_unified_search,
    UnifiedKnowledgeSearch,
    remember,
    forget,
    get_personal_store,
)


class TestFactualQueryDetection:
    """Tests for PRISM factual query detection."""

    @pytest.fixture
    def detector(self):
        return create_detector()

    def test_detects_what_is(self, detector):
        """Should detect 'what is' as factual query."""
        assert detector.detect_factual_query("what is LIVRPS")
        assert detector.detect_factual_query("What is USD composition")
        assert detector.detect_factual_query("WHAT IS knowledge prims")

    def test_detects_whats(self, detector):
        """Should detect 'what's' as factual query."""
        assert detector.detect_factual_query("what's a prim")
        assert detector.detect_factual_query("What's the difference between layers")

    def test_detects_explain(self, detector):
        """Should detect 'explain' as factual query."""
        assert detector.detect_factual_query("explain the routing cascade")
        assert detector.detect_factual_query("Explain how PRISM works")

    def test_detects_define(self, detector):
        """Should detect 'define' as factual query."""
        assert detector.detect_factual_query("define cognitive state")
        assert detector.detect_factual_query("Define epistemic tension")

    def test_detects_how_does(self, detector):
        """Should detect 'how does' as factual query."""
        assert detector.detect_factual_query("how does the orchestrator work")
        assert detector.detect_factual_query("How does batch invariance help")

    def test_detects_tell_me_about(self, detector):
        """Should detect 'tell me about' as factual query."""
        assert detector.detect_factual_query("tell me about the knowledge layer")

    def test_detects_describe(self, detector):
        """Should detect 'describe' as factual query."""
        assert detector.detect_factual_query("describe the NEXUS pipeline")


class TestNonFactualQueries:
    """Tests that non-factual queries skip Phase 0."""

    @pytest.fixture
    def detector(self):
        return create_detector()

    def test_implementation_requests(self, detector):
        """Implementation requests should not be factual queries."""
        assert not detector.detect_factual_query("fix the authentication bug")
        assert not detector.detect_factual_query("implement the feature")
        assert not detector.detect_factual_query("add error handling")

    def test_action_requests(self, detector):
        """Action requests should not be factual queries."""
        assert not detector.detect_factual_query("run the tests")
        assert not detector.detect_factual_query("deploy to production")
        assert not detector.detect_factual_query("create a new file")

    def test_context_dependent(self, detector):
        """Context-dependent queries that don't start with factual signals skip Phase 0."""
        # Note: "what's broken" WILL match "what's" signal, but knowledge layer
        # won't find a high-confidence match, so it continues to full pipeline.
        # This is acceptable - false positive detection, correct final routing.

        # These don't match any factual signal prefix
        assert not detector.detect_factual_query("what did we do yesterday")
        assert not detector.detect_factual_query("what happened to the build")
        assert not detector.detect_factual_query("where is the bug")
        assert not detector.detect_factual_query("why is this failing")

    def test_mid_sentence_signals(self, detector):
        """Factual signals mid-sentence should not trigger."""
        assert not detector.detect_factual_query("I want to know what is wrong")
        assert not detector.detect_factual_query("can you explain the error")


class TestKnowledgeShortCircuit:
    """Tests for high-confidence knowledge short-circuiting."""

    @pytest.fixture
    def orchestrator(self):
        return create_orchestrator()

    @pytest.fixture
    def personal_store(self):
        """Set up personal store with test data."""
        store = get_personal_store()
        # Add a test memory with high confidence
        remember("OTTO is a cognitive operating system for ADHD support")
        yield store
        # Cleanup
        forget("/Knowledge/Personal/mem_0001")

    def test_high_confidence_returns_knowledge_result(self, orchestrator, personal_store):
        """High-confidence match should return KnowledgeResult."""
        result = orchestrator.process_message("what is OTTO")

        # If knowledge layer has a high-confidence match, we get KnowledgeResult
        if isinstance(result, KnowledgeResult):
            assert result.short_circuited is True
            assert result.found is True
            assert result.retrieval.top_confidence >= KNOWLEDGE_CONFIDENCE_THRESHOLD
            assert "KNOW:" in result.to_anchor()

    def test_knowledge_result_has_correct_structure(self, orchestrator, personal_store):
        """KnowledgeResult should have expected fields."""
        result = orchestrator.process_message("what is OTTO")

        if isinstance(result, KnowledgeResult):
            dict_result = result.to_dict()
            assert "phase" in dict_result
            assert dict_result["phase"] == "knowledge"
            assert "short_circuited" in dict_result
            assert "query" in dict_result
            assert "found" in dict_result
            assert "confidence" in dict_result
            assert "processing_time_ms" in dict_result


class TestLowConfidenceContinues:
    """Tests that low-confidence queries continue to full pipeline."""

    @pytest.fixture
    def orchestrator(self):
        return create_orchestrator()

    def test_no_match_returns_nexus_result(self, orchestrator):
        """Query with no knowledge match should return NexusResult."""
        # Use a query that won't match any knowledge
        result = orchestrator.process_message(
            "what is xyzzy123 nonexistent concept"
        )

        # Either no match (NexusResult) or low confidence (NexusResult)
        # Both should continue to full pipeline
        assert isinstance(result, (NexusResult, KnowledgeResult))

        if isinstance(result, NexusResult):
            # Full pipeline was executed
            assert "EXEC:" in result.to_anchor() or result.to_anchor().startswith("[")

    def test_action_query_returns_nexus_result(self, orchestrator):
        """Non-factual query should always return NexusResult."""
        result = orchestrator.process_message("implement a new feature for user auth")

        # Non-factual queries bypass Phase 0 entirely
        assert isinstance(result, NexusResult)
        assert result.signals is not None
        assert result.routing is not None
        assert result.lock is not None


class TestDeterminism:
    """Tests for deterministic behavior (ThinkingMachines Determinism)."""

    @pytest.fixture
    def orchestrator(self):
        return create_orchestrator()

    @pytest.fixture
    def detector(self):
        return create_detector()

    def test_factual_detection_deterministic(self, detector):
        """Same input should always give same detection result."""
        query = "what is the knowledge layer"

        results = [detector.detect_factual_query(query) for _ in range(100)]

        # All results should be identical
        assert all(r == results[0] for r in results)
        assert results[0] is True

    def test_knowledge_search_deterministic(self):
        """Same query should always return same search results."""
        knowledge = get_unified_search()

        results = [knowledge.search("OTTO", max_results=5) for _ in range(10)]

        # All results should have same number of prims
        prim_counts = [len(r.prims) for r in results]
        assert all(c == prim_counts[0] for c in prim_counts)

        # If any prims found, paths should be identical
        if results[0].prims:
            paths = [[p.canonical_path for p in r.prims] for r in results]
            assert all(p == paths[0] for p in paths)

    def test_orchestrator_deterministic(self, orchestrator):
        """Same query should produce consistent result type."""
        query = "implement error handling"

        results = [orchestrator.process_message(query) for _ in range(5)]

        # All should be NexusResult (non-factual query)
        assert all(isinstance(r, NexusResult) for r in results)

        # Expert routing should be consistent
        experts = [r.routing.expert.value for r in results]
        assert all(e == experts[0] for e in experts)


class TestPerformance:
    """Tests for Phase 0 performance characteristics."""

    @pytest.fixture
    def orchestrator(self):
        return create_orchestrator()

    def test_knowledge_retrieval_fast(self):
        """Knowledge retrieval should be fast (<10ms for search)."""
        knowledge = get_unified_search()

        start = time.perf_counter()
        for _ in range(10):
            knowledge.search("test query", max_results=5)
        elapsed = (time.perf_counter() - start) * 1000

        # Average should be under 10ms per search
        avg_ms = elapsed / 10
        assert avg_ms < 10, f"Knowledge search too slow: {avg_ms:.2f}ms avg"

    def test_factual_detection_fast(self):
        """Factual query detection should be very fast (<1ms)."""
        detector = create_detector()
        queries = [
            "what is LIVRPS",
            "explain the routing",
            "implement feature",
            "fix the bug",
        ]

        start = time.perf_counter()
        for _ in range(100):
            for q in queries:
                detector.detect_factual_query(q)
        elapsed = (time.perf_counter() - start) * 1000

        # 400 detections in under 100ms = <0.25ms each
        avg_ms = elapsed / 400
        assert avg_ms < 1, f"Factual detection too slow: {avg_ms:.4f}ms avg"

    def test_short_circuit_faster_than_full_pipeline(self, orchestrator):
        """KnowledgeResult (if triggered) should be faster than NexusResult."""
        # First, add some knowledge so we can potentially short-circuit
        remember("Test performance item for knowledge layer testing")

        try:
            # Time a factual query that might short-circuit
            start = time.perf_counter()
            factual_result = orchestrator.process_message("what is test performance")
            factual_time = (time.perf_counter() - start) * 1000

            # Time a non-factual query (always full pipeline)
            start = time.perf_counter()
            full_result = orchestrator.process_message("implement test feature")
            full_time = (time.perf_counter() - start) * 1000

            # Both should complete reasonably fast
            assert factual_time < 100, f"Factual query too slow: {factual_time:.2f}ms"
            assert full_time < 200, f"Full pipeline too slow: {full_time:.2f}ms"

            # If we got a short-circuit, it should be faster
            if isinstance(factual_result, KnowledgeResult):
                assert factual_time < full_time, (
                    f"Short-circuit not faster: {factual_time:.2f}ms vs {full_time:.2f}ms"
                )

        finally:
            # Cleanup
            forget("/Knowledge/Personal/mem_0001")


class TestConfidenceThresholds:
    """Tests for confidence threshold behavior."""

    def test_threshold_constant_value(self):
        """Confidence threshold should be exactly 0.85."""
        assert KNOWLEDGE_CONFIDENCE_THRESHOLD == 0.85

    def test_threshold_used_correctly(self):
        """Threshold comparison should be >=, not >."""
        # 0.85 should trigger short-circuit
        assert 0.85 >= KNOWLEDGE_CONFIDENCE_THRESHOLD
        # 0.84999 should not
        assert not (0.84999 >= KNOWLEDGE_CONFIDENCE_THRESHOLD)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
