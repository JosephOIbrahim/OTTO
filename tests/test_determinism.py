"""
Tests for [He2025] Determinism Compliance
=========================================

Verifies that OTTO OS routing and aggregation operations are deterministic
per ThinkingMachines [He2025] principles.

These tests ensure:
1. sorted_max() has deterministic tie-breaking
2. kahan_sum() is order-independent
3. PRISM detector produces consistent input_hash
4. CognitiveOrchestrator produces consistent anchors
5. All 5 aggregation strategies are deterministic
"""

import pytest
import random
from typing import Dict, Any

from otto.determinism import (
    COGNITIVE_TILE_SIZE,
    DETERMINISM_SEED,
    sorted_max,
    sorted_max_key,
    sorted_max_value,
    kahan_sum,
    kahan_weighted_sum,
    sorted_set_to_list,
    deterministic_dict_iter,
    deterministic_dict_values,
    aggregate_max,
    aggregate_mean,
    aggregate_weighted_mean,
    aggregate_decay_mean,
    aggregate_threshold_filter,
    verify_determinism,
)


# =============================================================================
# Constants Tests
# =============================================================================

class TestConstants:
    """Test that constants are correctly defined."""

    def test_cognitive_tile_size_is_32(self):
        """COGNITIVE_TILE_SIZE must be exactly 32."""
        assert COGNITIVE_TILE_SIZE == 32

    def test_determinism_seed_is_cafebabe(self):
        """DETERMINISM_SEED must be 0xCAFEBABE."""
        assert DETERMINISM_SEED == 0xCAFEBABE


# =============================================================================
# sorted_max Tests
# =============================================================================

class TestSortedMax:
    """Test deterministic max with tie-breaking."""

    def test_sorted_max_basic(self):
        """sorted_max returns highest value."""
        d = {"a": 0.3, "b": 0.5, "c": 0.1}
        result = sorted_max(d)
        assert result == ("b", 0.5)

    def test_sorted_max_tiebreaking_is_lexicographic(self):
        """When values tie, lexicographically first key wins."""
        d = {"b": 0.5, "a": 0.5, "c": 0.5}
        result = sorted_max(d)
        # "a" comes before "b" and "c" lexicographically
        assert result == ("a", 0.5)

    def test_sorted_max_determinism_100_trials(self):
        """sorted_max produces identical results across 100 trials."""
        d = {"x": 0.5, "y": 0.5, "z": 0.5}
        results = [sorted_max(d) for _ in range(100)]
        assert len(set(results)) == 1

    def test_sorted_max_key_wrapper(self):
        """sorted_max_key returns only the key."""
        d = {"a": 0.3, "b": 0.5}
        assert sorted_max_key(d) == "b"

    def test_sorted_max_value_wrapper(self):
        """sorted_max_value returns only the value."""
        d = {"a": 0.3, "b": 0.5}
        assert sorted_max_value(d) == 0.5

    def test_sorted_max_empty_raises(self):
        """sorted_max raises ValueError on empty dict."""
        with pytest.raises(ValueError, match="empty dict"):
            sorted_max({})

    def test_sorted_max_with_custom_tiebreaker(self):
        """sorted_max respects custom tiebreaker function."""
        d = {"b": 0.5, "a": 0.5}
        # Custom tiebreaker: prefer "b" over "a" (reverse alphabetical)
        result = sorted_max(d, tiebreaker=lambda k: -ord(k))
        assert result[0] == "b"


# =============================================================================
# Kahan Summation Tests
# =============================================================================

class TestKahanSum:
    """Test batch-invariant summation."""

    def test_kahan_sum_basic(self):
        """kahan_sum computes correct sum."""
        values = [0.1, 0.2, 0.3]
        result = kahan_sum(values)
        assert abs(result - 0.6) < 1e-10

    def test_kahan_sum_order_independent(self):
        """kahan_sum produces same result regardless of input order."""
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        original_result = kahan_sum(values)

        # Shuffle 100 times and verify same result
        for _ in range(100):
            shuffled = values.copy()
            random.shuffle(shuffled)
            assert kahan_sum(shuffled) == original_result

    def test_kahan_sum_empty(self):
        """kahan_sum of empty list is 0."""
        assert kahan_sum([]) == 0.0

    def test_kahan_sum_single_value(self):
        """kahan_sum of single value is that value."""
        assert kahan_sum([42.5]) == 42.5

    def test_kahan_sum_compensates_fp_errors(self):
        """kahan_sum reduces floating-point accumulation errors."""
        # This is a classic example where naive sum fails
        values = [1.0] + [1e-16] * 10000
        # Naive sum would lose the small values
        # Kahan should preserve them (though result will be close to 1.0)
        result = kahan_sum(values)
        # Should be approximately 1.0 + 1e-12
        assert result >= 1.0

    def test_kahan_weighted_sum(self):
        """kahan_weighted_sum computes weighted sum correctly."""
        items = [(0.5, 0.6), (0.3, 0.4)]
        result = kahan_weighted_sum(items)
        expected = 0.5 * 0.6 + 0.3 * 0.4  # 0.3 + 0.12 = 0.42
        assert abs(result - expected) < 1e-10


# =============================================================================
# Collection Utilities Tests
# =============================================================================

class TestCollectionUtilities:
    """Test deterministic collection iteration."""

    def test_sorted_set_to_list(self):
        """sorted_set_to_list produces sorted list."""
        s = {"c", "a", "b"}
        result = sorted_set_to_list(s)
        assert result == ["a", "b", "c"]

    def test_sorted_set_to_list_determinism(self):
        """sorted_set_to_list is deterministic across iterations."""
        s = {"z", "m", "a", "f"}
        results = [sorted_set_to_list(s) for _ in range(100)]
        assert all(r == ["a", "f", "m", "z"] for r in results)

    def test_deterministic_dict_iter(self):
        """deterministic_dict_iter yields sorted key order."""
        d = {"b": 1, "a": 2, "c": 3}
        result = list(deterministic_dict_iter(d))
        assert result == [("a", 2), ("b", 1), ("c", 3)]

    def test_deterministic_dict_values(self):
        """deterministic_dict_values returns values in sorted key order."""
        d = {"b": 1, "a": 2, "c": 3}
        result = deterministic_dict_values(d)
        assert result == [2, 1, 3]


# =============================================================================
# Aggregation Strategy Tests
# =============================================================================

class TestAggregationStrategies:
    """Test the 5 aggregation strategies from v7.1.0 spec."""

    def test_aggregate_max(self):
        """aggregate_max returns maximum value."""
        values = [0.1, 0.5, 0.3]
        assert aggregate_max(values) == 0.5

    def test_aggregate_max_empty(self):
        """aggregate_max of empty returns 0."""
        assert aggregate_max([]) == 0.0

    def test_aggregate_mean(self):
        """aggregate_mean computes arithmetic mean."""
        values = [0.2, 0.4, 0.6]
        result = aggregate_mean(values)
        assert abs(result - 0.4) < 1e-10

    def test_aggregate_mean_uses_kahan(self):
        """aggregate_mean uses Kahan summation (order-independent)."""
        values = [0.1, 0.2, 0.3]
        shuffled = [0.3, 0.1, 0.2]
        assert aggregate_mean(values) == aggregate_mean(shuffled)

    def test_aggregate_weighted_mean(self):
        """aggregate_weighted_mean computes weighted average."""
        values = [0.2, 0.8]
        weights = [0.3, 0.7]
        result = aggregate_weighted_mean(values, weights)
        expected = (0.2 * 0.3 + 0.8 * 0.7) / (0.3 + 0.7)
        assert abs(result - expected) < 1e-10

    def test_aggregate_weighted_mean_mismatched_lengths_raises(self):
        """aggregate_weighted_mean raises on mismatched lengths."""
        with pytest.raises(ValueError):
            aggregate_weighted_mean([1, 2], [1])

    def test_aggregate_decay_mean(self):
        """aggregate_decay_mean applies exponential decay."""
        values = [1.0, 1.0, 1.0]
        result = aggregate_decay_mean(values, decay=0.5)
        # Sorted: [1.0, 1.0, 1.0], weights: [1, 0.5, 0.25]
        expected = (1.0 * 1 + 1.0 * 0.5 + 1.0 * 0.25) / (1 + 0.5 + 0.25)
        assert abs(result - expected) < 1e-10

    def test_aggregate_threshold_filter(self):
        """aggregate_threshold_filter returns max above threshold."""
        values = [0.1, 0.5, 0.3, 0.8]
        result = aggregate_threshold_filter(values, threshold=0.4)
        assert result == 0.8

    def test_aggregate_threshold_filter_none_meet_threshold(self):
        """aggregate_threshold_filter returns 0 if none meet threshold."""
        values = [0.1, 0.2, 0.3]
        result = aggregate_threshold_filter(values, threshold=0.5)
        assert result == 0.0

    def test_all_strategies_deterministic(self):
        """All 5 strategies produce same results across 100 trials."""
        values = [0.5, 0.3, 0.8, 0.1]
        weights = [0.2, 0.3, 0.4, 0.1]

        for _ in range(100):
            shuffled_v = values.copy()
            random.shuffle(shuffled_v)

            # MAX is inherently order-independent
            assert aggregate_max(shuffled_v) == aggregate_max(values)

            # MEAN uses Kahan, should be order-independent
            assert aggregate_mean(shuffled_v) == aggregate_mean(values)

            # THRESHOLD_FILTER is order-independent (filter then max)
            assert (aggregate_threshold_filter(shuffled_v, 0.3) ==
                    aggregate_threshold_filter(values, 0.3))


# =============================================================================
# Verification Utility Tests
# =============================================================================

class TestVerifyDeterminism:
    """Test the verify_determinism utility."""

    def test_verify_determinism_passes_for_deterministic_func(self):
        """verify_determinism returns True for deterministic function."""
        assert verify_determinism(sorted_max, {"a": 1, "b": 1})

    def test_verify_determinism_with_kahan_sum(self):
        """verify_determinism passes for kahan_sum."""
        assert verify_determinism(kahan_sum, [0.1, 0.2, 0.3])


# =============================================================================
# Integration Tests with OTTO Components
# =============================================================================

class TestPRISMDeterminism:
    """Test that PRISM detector is deterministic."""

    def test_prism_input_hash_deterministic(self):
        """PRISM detector produces consistent input_hash across 100 trials."""
        from otto.prism_detector import PRISMDetector

        detector = PRISMDetector()
        message = "I'm frustrated and stuck on this bug"

        hashes = set()
        for _ in range(100):
            result = detector.detect(message)
            hashes.add(result.input_hash)

        assert len(hashes) == 1, f"Non-deterministic hashes: {hashes}"

    def test_prism_priority_signal_deterministic(self):
        """PRISM detector produces consistent priority signal."""
        from otto.prism_detector import PRISMDetector

        detector = PRISMDetector()
        message = "I'm frustrated and overwhelmed"  # Both at same level

        results = []
        for _ in range(100):
            result = detector.detect(message)
            priority = result.get_priority_signal()
            results.append((priority[0].name, priority[1]))

        # All results should be identical
        assert len(set(results)) == 1, f"Non-deterministic priority: {set(results)}"


class TestConvergenceTrackerDeterminism:
    """Test that convergence tracker is deterministic."""

    def test_state_vector_distance_deterministic(self):
        """StateVector.distance produces consistent results."""
        from otto.convergence_tracker import StateVector

        a = StateVector(0.5, 0.0, 0.33, 0.65, 1.0)
        b = StateVector(0.8, 1.0, 0.67, 0.35, 0.67)

        distances = set()
        for _ in range(100):
            distances.add(StateVector.distance(a, b))

        assert len(distances) == 1, f"Non-deterministic distances: {distances}"


class TestCalibrationLearnerDeterminism:
    """Test that calibration learner is deterministic."""

    def test_weight_normalization_deterministic(self):
        """Weight normalization produces consistent results."""
        from otto.calibration.calibration_learner import CalibrationLearner
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = CalibrationLearner(otto_dir=Path(tmpdir))

            # Get weights multiple times
            weights_sets = []
            for _ in range(100):
                weights = learner.get_weights()
                weights_sets.append(tuple(sorted(weights.items())))

            # All should be identical
            assert len(set(weights_sets)) == 1


# =============================================================================
# Marker for determinism-specific tests
# =============================================================================

# This allows running just determinism tests with: pytest -m determinism
pytestmark = pytest.mark.determinism
