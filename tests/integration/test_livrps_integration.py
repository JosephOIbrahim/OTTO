"""
LIVRPS Integration Tests
========================

Integration tests for LIVRPS (Local > Inherits > Variants > References > Payloads > Specializes)
composition engine with memory backbone integration.

Determinism Testing:
- Fixed evaluation order (L → I → V → R → P → S)
- Deterministic resolution (100 runs produce identical output)
- Safety floor enforcement
- Kahan summation for batch invariance
- Sorted key iteration

Test Categories:
1. Priority Resolution - Higher layers win
2. Safety Floors - Constitutional minimums enforced
3. Determinism - Same inputs → same outputs
4. Variant Switching - Mode-specific overrides
5. Memory Integration - Oracle results as Local layer
"""

import hashlib
import json
import pytest
from typing import Any, Dict, List

from otto.core.livrps import (
    LIVRPSResolver,
    Layer,
    LayerType,
    SafetyFloor,
    CompositionResult,
    LIVRPS_ORDER,
    COGNITIVE_VARIANTS,
    kahan_sum,
    round_for_comparison,
)


class TestLIVRPSPriorityResolution:
    """Test that higher priority layers win conflicts."""

    def test_local_overrides_all_lower_layers(self):
        """LOCAL (highest) should override all other layers."""
        resolver = LIVRPSResolver()

        # Add layers in reverse priority order (shouldn't matter)
        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"key": "specializes_value"},
            name="constitutional"
        ))
        resolver.add_layer(Layer(
            LayerType.PAYLOADS,
            {"key": "payloads_value"},
            name="domain"
        ))
        resolver.add_layer(Layer(
            LayerType.REFERENCES,
            {"key": "references_value"},
            name="calibration"
        ))
        resolver.add_layer(Layer(
            LayerType.VARIANTS,
            {"key": "variants_value"},
            name="focused"
        ))
        resolver.add_layer(Layer(
            LayerType.INHERITS,
            {"key": "inherits_value"},
            name="parent"
        ))
        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"key": "local_value"},
            name="session"
        ))

        result = resolver.resolve()

        assert result.get("key") == "local_value"
        assert result.source_of("key") == LayerType.LOCAL

    def test_inherits_overrides_variants_and_below(self):
        """INHERITS should override VARIANTS and lower layers."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"key": "specializes_value"},
        ))
        resolver.add_layer(Layer(
            LayerType.VARIANTS,
            {"key": "variants_value"},
        ))
        resolver.add_layer(Layer(
            LayerType.INHERITS,
            {"key": "inherits_value"},
        ))

        result = resolver.resolve()

        assert result.get("key") == "inherits_value"
        assert result.source_of("key") == LayerType.INHERITS

    def test_variants_override_references_and_below(self):
        """VARIANTS should override REFERENCES and lower layers."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"key": "specializes_value"},
        ))
        resolver.add_layer(Layer(
            LayerType.REFERENCES,
            {"key": "references_value"},
        ))
        resolver.add_layer(Layer(
            LayerType.VARIANTS,
            {"key": "variants_value"},
        ))

        result = resolver.resolve()

        assert result.get("key") == "variants_value"
        assert result.source_of("key") == LayerType.VARIANTS

    def test_fallback_to_specializes_when_no_higher_layers(self):
        """Without higher layers, SPECIALIZES should provide defaults."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"energy": "medium", "burnout": "GREEN"},
            name="constitutional"
        ))

        result = resolver.resolve()

        assert result.get("energy") == "medium"
        assert result.get("burnout") == "GREEN"
        assert result.source_of("energy") == LayerType.SPECIALIZES

    def test_partial_overrides_preserve_unrelated_values(self):
        """Higher layers only override their specific keys."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"energy": "medium", "burnout": "GREEN", "mode": "focused"},
        ))
        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"burnout": "YELLOW"},  # Only override burnout
        ))

        result = resolver.resolve()

        assert result.get("burnout") == "YELLOW"  # Overridden
        assert result.get("energy") == "medium"   # From SPECIALIZES
        assert result.get("mode") == "focused"    # From SPECIALIZES


class TestSafetyFloors:
    """Test constitutional safety floor enforcement."""

    def test_safety_floor_prevents_below_minimum(self):
        """Safety floors should prevent values below minimum."""
        floor = SafetyFloor("validator_confidence", 0.10)

        # Check values
        assert floor.check(0.15) is True  # Above floor
        assert floor.check(0.10) is True  # At floor
        assert floor.check(0.05) is False  # Below floor

        # Apply floor
        assert floor.apply(0.15) == 0.15  # Above - no change
        assert floor.apply(0.05) == 0.10  # Below - raised to floor

    def test_resolver_applies_safety_floors(self):
        """Resolver should apply safety floors from constitutional layer."""
        resolver = LIVRPSResolver(safety_floors=[
            SafetyFloor("safety_floor_validator", 0.10),
        ])

        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"safety_floor_validator": 0.05},  # Below floor
        ))

        result = resolver.resolve()

        # Value should be raised to floor
        assert result.get("safety_floor_validator") == 0.10
        assert result.was_floored("safety_floor_validator") is True

    def test_safety_floor_records_original_value(self):
        """Safety floor application should record original value."""
        resolver = LIVRPSResolver(safety_floors=[
            SafetyFloor("confidence", 0.10),
        ])

        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"confidence": 0.03},
        ))

        result = resolver.resolve()

        original, floor = result.safety_floors_applied["confidence"]
        assert original == 0.03
        assert floor == 0.10

    def test_values_above_floor_not_affected(self):
        """Values at or above floor should not be modified."""
        resolver = LIVRPSResolver(safety_floors=[
            SafetyFloor("confidence", 0.10),
        ])

        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"confidence": 0.50},  # Above floor
        ))

        result = resolver.resolve()

        assert result.get("confidence") == 0.50
        assert result.was_floored("confidence") is False


class TestDeterminism:
    """Test determinism requirements."""

    def test_same_inputs_produce_same_outputs(self):
        """Verify determinism: same inputs → same outputs over 100 runs."""
        hashes = set()

        for _ in range(100):
            resolver = LIVRPSResolver()

            resolver.add_layer(Layer(
                LayerType.SPECIALIZES,
                {"a": 1, "b": 2, "c": 3},
            ))
            resolver.add_layer(Layer(
                LayerType.LOCAL,
                {"b": 20},
            ))

            result = resolver.resolve()

            # Hash the result
            result_str = json.dumps(result.resolved, sort_keys=True)
            result_hash = hashlib.sha256(result_str.encode()).hexdigest()
            hashes.add(result_hash)

        # All 100 runs should produce identical hash
        assert len(hashes) == 1, f"Non-deterministic! Got {len(hashes)} unique hashes"

    def test_key_iteration_order_is_sorted(self):
        """Verify keys are processed in sorted order."""
        resolver = LIVRPSResolver()

        # Add keys in random order
        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"zebra": 1, "apple": 2, "mango": 3},
        ))

        result = resolver.resolve()

        # Keys should be in sorted order
        resolved_keys = list(result.resolved.keys())
        assert resolved_keys == sorted(resolved_keys)

    def test_layer_addition_order_does_not_affect_result(self):
        """Layer addition order should not affect resolution."""
        # First order: SPECIALIZES, then LOCAL
        resolver1 = LIVRPSResolver()
        resolver1.add_layer(Layer(LayerType.SPECIALIZES, {"key": "spec"}))
        resolver1.add_layer(Layer(LayerType.LOCAL, {"key": "local"}))

        # Second order: LOCAL, then SPECIALIZES
        resolver2 = LIVRPSResolver()
        resolver2.add_layer(Layer(LayerType.LOCAL, {"key": "local"}))
        resolver2.add_layer(Layer(LayerType.SPECIALIZES, {"key": "spec"}))

        result1 = resolver1.resolve()
        result2 = resolver2.resolve()

        assert result1.resolved == result2.resolved
        assert result1.sources == result2.sources

    def test_serialization_roundtrip_is_deterministic(self):
        """Serialization and deserialization should be deterministic."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"z": 1, "a": 2},
            name="base"
        ))
        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"m": 3},
            name="session"
        ))

        # Serialize
        data = resolver.to_dict()

        # Deserialize
        restored = LIVRPSResolver.from_dict(data)

        # Results should be identical
        original_result = resolver.resolve()
        restored_result = restored.resolve()

        assert original_result.resolved == restored_result.resolved


class TestKahanSummation:
    """Test batch-invariant summation."""

    def test_kahan_sum_basic(self):
        """Kahan sum should work for basic cases."""
        values = [1.0, 2.0, 3.0]
        assert kahan_sum(values) == 6.0

    def test_kahan_sum_sorted_for_determinism(self):
        """Kahan sum should sort values for determinism."""
        values1 = [0.1, 0.2, 0.3]
        values2 = [0.3, 0.1, 0.2]

        # Both should produce same result due to sorting
        assert kahan_sum(values1) == kahan_sum(values2)

    def test_kahan_sum_numerical_stability(self):
        """Kahan sum should handle numerical edge cases."""
        # Small values that could cause floating-point issues
        values = [1e-10, 1e-10, 1e-10, 1e10]
        result = kahan_sum(values)

        # Should be close to 1e10
        assert abs(result - 1e10) < 1e-5

    def test_round_for_comparison(self):
        """round_for_comparison should round to specified precision."""
        assert round_for_comparison(0.123456789) == 0.123457
        assert round_for_comparison(0.123456789, 2) == 0.12


class TestVariantSwitching:
    """Test cognitive mode variant switching."""

    def test_set_variant_clears_previous_variant(self):
        """Setting a variant should clear previous variants."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"paradigm": "default"},
        ))

        # Set focused variant
        resolver.set_variant("focused", COGNITIVE_VARIANTS["focused"])
        result1 = resolver.resolve()
        assert result1.get("paradigm") == "cortex"

        # Switch to exploring variant
        resolver.set_variant("exploring", COGNITIVE_VARIANTS["exploring"])
        result2 = resolver.resolve()
        assert result2.get("paradigm") == "mycelium"

    def test_variant_values_override_lower_layers(self):
        """Variant values should override REFERENCES and below."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"tangent_allowance": 10},
        ))
        resolver.add_layer(Layer(
            LayerType.REFERENCES,
            {"tangent_allowance": 8},
        ))
        resolver.set_variant("focused", COGNITIVE_VARIANTS["focused"])

        result = resolver.resolve()

        # Variant (tangent_allowance=2) should override References
        assert result.get("tangent_allowance") == 2

    def test_local_overrides_variant(self):
        """LOCAL should still override variant values."""
        resolver = LIVRPSResolver()

        resolver.set_variant("focused", COGNITIVE_VARIANTS["focused"])
        resolver.update_local("paradigm", "mycelium")

        result = resolver.resolve()

        # LOCAL should win
        assert result.get("paradigm") == "mycelium"

    def test_all_predefined_variants_exist(self):
        """All standard variants should be defined."""
        expected_variants = ["focused", "exploring", "teaching", "recovery"]
        for variant in expected_variants:
            assert variant in COGNITIVE_VARIANTS


class TestMemoryIntegration:
    """Test LIVRPS integration with memory backbone."""

    def test_oracle_results_as_local_layer(self):
        """Oracle results should be stored in LOCAL layer (highest priority)."""
        resolver = LIVRPSResolver()

        # Specializes has base values
        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"position": "(0, 0, 0)", "velocity": "(0, 0, 0)"},
        ))

        # Oracle results go to LOCAL (simulating grounding layer integration)
        resolver.update_local("position", "(10, 5, 0)")

        result = resolver.resolve()

        # Oracle result should win
        assert result.get("position") == "(10, 5, 0)"
        assert result.source_of("position") == LayerType.LOCAL
        # Non-oracle value from SPECIALIZES
        assert result.get("velocity") == "(0, 0, 0)"

    def test_update_local_creates_layer_if_needed(self):
        """update_local should create LOCAL layer if it doesn't exist."""
        resolver = LIVRPSResolver()

        # No layers yet
        assert len(resolver.get_layers(LayerType.LOCAL)) == 0

        resolver.update_local("key", "value")

        # LOCAL layer should now exist
        assert len(resolver.get_layers(LayerType.LOCAL)) == 1
        result = resolver.resolve()
        assert result.get("key") == "value"

    def test_update_references_for_calibration(self):
        """update_references should update calibration data."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"think_depth": "standard"},
        ))

        # Calibration updates go to REFERENCES
        resolver.update_references("think_depth", "deep")

        result = resolver.resolve()
        assert result.get("think_depth") == "deep"
        assert result.source_of("think_depth") == LayerType.REFERENCES


class TestLIVRPSOrder:
    """Test LIVRPS_ORDER constant is correct."""

    def test_livrps_order_is_correct(self):
        """LIVRPS_ORDER should be L → I → V → R → P → S."""
        expected_order = [
            LayerType.LOCAL,
            LayerType.INHERITS,
            LayerType.VARIANTS,
            LayerType.REFERENCES,
            LayerType.PAYLOADS,
            LayerType.SPECIALIZES,
        ]
        assert LIVRPS_ORDER == expected_order

    def test_layer_type_values_match_priority(self):
        """LayerType enum values should reflect priority (lower = higher)."""
        assert LayerType.LOCAL.value < LayerType.INHERITS.value
        assert LayerType.INHERITS.value < LayerType.VARIANTS.value
        assert LayerType.VARIANTS.value < LayerType.REFERENCES.value
        assert LayerType.REFERENCES.value < LayerType.PAYLOADS.value
        assert LayerType.PAYLOADS.value < LayerType.SPECIALIZES.value


class TestOverriddenTracking:
    """Test that overridden values are tracked for debugging."""

    def test_overridden_values_tracked(self):
        """Values overridden by higher layers should be recorded."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(LayerType.SPECIALIZES, {"key": "spec_value"}))
        resolver.add_layer(Layer(LayerType.REFERENCES, {"key": "ref_value"}))
        resolver.add_layer(Layer(LayerType.LOCAL, {"key": "local_value"}))

        result = resolver.resolve()

        # Should have overridden entries
        assert "key" in result.overridden

        # Check overridden values (REFERENCES and SPECIALIZES were overridden)
        overridden_layers = [lt for lt, val in result.overridden["key"]]
        assert LayerType.REFERENCES in overridden_layers
        assert LayerType.SPECIALIZES in overridden_layers

    def test_no_overridden_when_single_layer(self):
        """Single layer should have no overridden entries."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(LayerType.SPECIALIZES, {"key": "value"}))

        result = resolver.resolve()

        assert "key" not in result.overridden
