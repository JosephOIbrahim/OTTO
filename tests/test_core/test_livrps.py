"""
LIVRPS Composition Engine Tests
===============================

Tests for USD-inspired composition semantics.

Determinism Tests:
- Deterministic evaluation order
- Sorted key iteration
- Float precision
- Safety floor enforcement
"""

import pytest
from otto.core.livrps import (
    LIVRPSResolver,
    Layer,
    LayerType,
    CompositionResult,
    SafetyFloor,
    LIVRPS_ORDER,
    COGNITIVE_VARIANTS,
    kahan_sum,
    round_for_comparison,
)


# =============================================================================
# LIVRPS Order Tests
# =============================================================================

class TestLIVRPSOrder:
    """Tests for LIVRPS priority ordering."""

    def test_livrps_order_is_fixed(self):
        """LIVRPS order must be L → I → V → R → P → S."""
        assert LIVRPS_ORDER == [
            LayerType.LOCAL,
            LayerType.INHERITS,
            LayerType.VARIANTS,
            LayerType.REFERENCES,
            LayerType.PAYLOADS,
            LayerType.SPECIALIZES,
        ]

    def test_layer_type_priorities(self):
        """Lower enum value = higher priority."""
        assert LayerType.LOCAL.value < LayerType.INHERITS.value
        assert LayerType.INHERITS.value < LayerType.VARIANTS.value
        assert LayerType.VARIANTS.value < LayerType.REFERENCES.value
        assert LayerType.REFERENCES.value < LayerType.PAYLOADS.value
        assert LayerType.PAYLOADS.value < LayerType.SPECIALIZES.value


# =============================================================================
# Layer Tests
# =============================================================================

class TestLayer:
    """Tests for Layer dataclass."""

    def test_layer_creation(self):
        """Create a layer with data."""
        layer = Layer(
            layer_type=LayerType.LOCAL,
            data={"key": "value"},
            name="test"
        )
        assert layer.layer_type == LayerType.LOCAL
        assert layer.get("key") == "value"
        assert layer.name == "test"
        assert layer.active is True

    def test_layer_get_default(self):
        """Get returns default for missing keys."""
        layer = Layer(LayerType.LOCAL, {})
        assert layer.get("missing") is None
        assert layer.get("missing", "default") == "default"

    def test_layer_has(self):
        """Has checks key existence."""
        layer = Layer(LayerType.LOCAL, {"exists": True})
        assert layer.has("exists") is True
        assert layer.has("missing") is False

    def test_layer_set(self):
        """Set updates layer data."""
        layer = Layer(LayerType.LOCAL, {})
        layer.set("key", "value")
        assert layer.get("key") == "value"

    def test_layer_keys(self):
        """Keys returns all keys."""
        layer = Layer(LayerType.LOCAL, {"a": 1, "b": 2, "c": 3})
        assert layer.keys() == {"a", "b", "c"}


# =============================================================================
# Resolver Tests
# =============================================================================

class TestLIVRPSResolver:
    """Tests for LIVRPS composition resolution."""

    def test_empty_resolver(self):
        """Empty resolver returns empty result."""
        resolver = LIVRPSResolver()
        result = resolver.resolve()
        assert result.resolved == {}

    def test_single_layer(self):
        """Single layer values are resolved."""
        resolver = LIVRPSResolver()
        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"burnout": "green", "energy": "high"}
        ))

        result = resolver.resolve()
        assert result.get("burnout") == "green"
        assert result.get("energy") == "high"
        assert result.source_of("burnout") == LayerType.LOCAL

    def test_local_overrides_specializes(self):
        """LOCAL layer overrides SPECIALIZES layer."""
        resolver = LIVRPSResolver()

        # Lower priority
        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"burnout": "green", "extra": "value"}
        ))

        # Higher priority
        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"burnout": "yellow"}
        ))

        result = resolver.resolve()
        assert result.get("burnout") == "yellow"  # From LOCAL
        assert result.get("extra") == "value"      # From SPECIALIZES
        assert result.source_of("burnout") == LayerType.LOCAL
        assert result.source_of("extra") == LayerType.SPECIALIZES

    def test_full_livrps_cascade(self):
        """Full LIVRPS cascade with all layers."""
        resolver = LIVRPSResolver()

        # Add layers in reverse order (shouldn't matter)
        resolver.add_layer(Layer(LayerType.SPECIALIZES, {"a": "S", "b": "S", "c": "S", "d": "S", "e": "S", "f": "S"}))
        resolver.add_layer(Layer(LayerType.PAYLOADS, {"a": "P", "b": "P", "c": "P", "d": "P", "e": "P"}))
        resolver.add_layer(Layer(LayerType.REFERENCES, {"a": "R", "b": "R", "c": "R", "d": "R"}))
        resolver.add_layer(Layer(LayerType.VARIANTS, {"a": "V", "b": "V", "c": "V"}))
        resolver.add_layer(Layer(LayerType.INHERITS, {"a": "I", "b": "I"}))
        resolver.add_layer(Layer(LayerType.LOCAL, {"a": "L"}))

        result = resolver.resolve()

        # Each wins where it's the highest layer with a value
        assert result.get("a") == "L"  # LOCAL wins
        assert result.get("b") == "I"  # INHERITS wins
        assert result.get("c") == "V"  # VARIANTS wins
        assert result.get("d") == "R"  # REFERENCES wins
        assert result.get("e") == "P"  # PAYLOADS wins
        assert result.get("f") == "S"  # SPECIALIZES wins

    def test_inactive_layer_excluded(self):
        """Inactive layers don't participate in resolution."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"key": "local"},
            active=False  # Inactive!
        ))
        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"key": "specializes"}
        ))

        result = resolver.resolve()
        assert result.get("key") == "specializes"  # LOCAL skipped

    def test_overridden_values_tracked(self):
        """Overridden values are tracked in result."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(LayerType.LOCAL, {"key": "local"}))
        resolver.add_layer(Layer(LayerType.REFERENCES, {"key": "refs"}))
        resolver.add_layer(Layer(LayerType.SPECIALIZES, {"key": "spec"}))

        result = resolver.resolve()
        assert result.get("key") == "local"
        assert ("key" in result.overridden)
        assert (LayerType.REFERENCES, "refs") in result.overridden["key"]
        assert (LayerType.SPECIALIZES, "spec") in result.overridden["key"]

    def test_remove_layer(self):
        """Layers can be removed."""
        resolver = LIVRPSResolver()

        layer = Layer(LayerType.LOCAL, {"key": "value"})
        resolver.add_layer(layer)
        assert resolver.resolve().get("key") == "value"

        removed = resolver.remove_layer(layer)
        assert removed is True
        assert resolver.resolve().get("key") is None

    def test_clear_layer_type(self):
        """All layers of a type can be cleared."""
        resolver = LIVRPSResolver()

        resolver.add_layer(Layer(LayerType.LOCAL, {"a": 1}))
        resolver.add_layer(Layer(LayerType.LOCAL, {"b": 2}))
        assert len(resolver.get_layers(LayerType.LOCAL)) == 2

        resolver.clear_layer_type(LayerType.LOCAL)
        assert len(resolver.get_layers(LayerType.LOCAL)) == 0


# =============================================================================
# Safety Floor Tests
# =============================================================================

class TestSafetyFloors:
    """Tests for safety floor enforcement."""

    def test_safety_floor_applied(self):
        """Safety floors enforce minimums."""
        resolver = LIVRPSResolver(safety_floors=[
            SafetyFloor("weight", 0.10)
        ])

        resolver.add_layer(Layer(LayerType.LOCAL, {"weight": 0.05}))

        result = resolver.resolve()
        assert result.get("weight") == 0.10  # Floored
        assert result.was_floored("weight") is True

    def test_safety_floor_not_needed(self):
        """Safety floors don't change values above floor."""
        resolver = LIVRPSResolver(safety_floors=[
            SafetyFloor("weight", 0.10)
        ])

        resolver.add_layer(Layer(LayerType.LOCAL, {"weight": 0.50}))

        result = resolver.resolve()
        assert result.get("weight") == 0.50  # Not floored
        assert result.was_floored("weight") is False

    def test_default_safety_floors(self):
        """Default safety floors from constitutional.usda."""
        resolver = LIVRPSResolver()  # Uses defaults

        resolver.add_layer(Layer(LayerType.LOCAL, {
            "safety_floor_validator": 0.01,    # Below 0.10
            "safety_floor_restorer": 0.01,     # Below 0.05
            "safety_floor_scaffolder": 0.01,   # Below 0.05
        }))

        result = resolver.resolve()
        assert result.get("safety_floor_validator") == 0.10
        assert result.get("safety_floor_restorer") == 0.05
        assert result.get("safety_floor_scaffolder") == 0.05


# =============================================================================
# Variant Tests
# =============================================================================

class TestVariants:
    """Tests for cognitive mode variants."""

    def test_set_variant(self):
        """Setting a variant updates VARIANTS layer."""
        resolver = LIVRPSResolver()

        resolver.set_variant("focused", COGNITIVE_VARIANTS["focused"])

        result = resolver.resolve()
        assert result.get("interruption_threshold") == 0.7
        assert result.get("tangent_allowance") == 2
        assert result.get("paradigm") == "cortex"

    def test_variant_switch(self):
        """Switching variants replaces previous."""
        resolver = LIVRPSResolver()

        resolver.set_variant("focused", COGNITIVE_VARIANTS["focused"])
        assert resolver.resolve().get("tangent_allowance") == 2

        resolver.set_variant("exploring", COGNITIVE_VARIANTS["exploring"])
        assert resolver.resolve().get("tangent_allowance") == 5

    def test_predefined_variants(self):
        """All predefined variants exist."""
        assert "focused" in COGNITIVE_VARIANTS
        assert "exploring" in COGNITIVE_VARIANTS
        assert "teaching" in COGNITIVE_VARIANTS
        assert "recovery" in COGNITIVE_VARIANTS


# =============================================================================
# Convenience Method Tests
# =============================================================================

class TestConvenienceMethods:
    """Tests for update convenience methods."""

    def test_update_local(self):
        """update_local modifies LOCAL layer."""
        resolver = LIVRPSResolver()

        resolver.update_local("key", "value")
        assert resolver.resolve().get("key") == "value"
        assert resolver.resolve().source_of("key") == LayerType.LOCAL

    def test_update_references(self):
        """update_references modifies REFERENCES layer."""
        resolver = LIVRPSResolver()

        resolver.update_references("key", "value")
        assert resolver.resolve().get("key") == "value"
        assert resolver.resolve().source_of("key") == LayerType.REFERENCES

    def test_resolve_attribute(self):
        """resolve_attribute returns single value efficiently."""
        resolver = LIVRPSResolver()
        resolver.add_layer(Layer(LayerType.LOCAL, {"key": "value"}))

        value, source = resolver.resolve_attribute("key")
        assert value == "value"
        assert source == LayerType.LOCAL

        value, source = resolver.resolve_attribute("missing", "default")
        assert value == "default"
        assert source is None


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests for Determinism."""

    def test_deterministic_key_order(self):
        """Keys are processed in sorted order."""
        resolver = LIVRPSResolver()
        resolver.add_layer(Layer(LayerType.LOCAL, {"z": 1, "a": 2, "m": 3}))

        result = resolver.resolve()
        keys = list(result.resolved.keys())
        assert keys == sorted(keys)  # Always sorted

    def test_deterministic_resolution(self):
        """Same inputs → same outputs (100 trials)."""
        def create_resolver():
            resolver = LIVRPSResolver()
            resolver.add_layer(Layer(LayerType.LOCAL, {"a": 1, "b": 2}))
            resolver.add_layer(Layer(LayerType.SPECIALIZES, {"b": 99, "c": 3}))
            return resolver.resolve().resolved

        results = [create_resolver() for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_serialization_determinism(self):
        """Serialization is deterministic."""
        resolver = LIVRPSResolver()
        resolver.add_layer(Layer(LayerType.LOCAL, {"z": 1, "a": 2}))
        resolver.add_layer(Layer(LayerType.SPECIALIZES, {"b": 3}))

        serialized1 = resolver.to_dict()
        serialized2 = resolver.to_dict()

        import json
        assert json.dumps(serialized1, sort_keys=True) == json.dumps(serialized2, sort_keys=True)

    def test_kahan_sum_accuracy(self):
        """Kahan summation maintains precision."""
        values = [0.1] * 10  # Would accumulate error with naive sum
        result = kahan_sum(values)
        assert abs(result - 1.0) < 1e-10

    def test_kahan_sum_order_invariant(self):
        """Kahan sum is order-invariant (because we sort)."""
        values1 = [0.3, 0.1, 0.2]
        values2 = [0.2, 0.3, 0.1]  # Different order

        assert kahan_sum(values1) == kahan_sum(values2)

    def test_round_for_comparison(self):
        """Float rounding for comparison."""
        assert round_for_comparison(0.1234567) == 0.123457
        assert round_for_comparison(0.1234564) == 0.123456


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerialization:
    """Tests for resolver serialization."""

    def test_to_dict_from_dict_roundtrip(self):
        """Serialize → deserialize preserves state."""
        resolver = LIVRPSResolver()
        resolver.add_layer(Layer(LayerType.LOCAL, {"a": 1}, name="session"))
        resolver.add_layer(Layer(LayerType.SPECIALIZES, {"b": 2}, name="defaults"))

        data = resolver.to_dict()
        restored = LIVRPSResolver.from_dict(data)

        assert restored.resolve().resolved == resolver.resolve().resolved

    def test_serialization_with_inactive_layers(self):
        """Inactive layers are preserved in serialization."""
        resolver = LIVRPSResolver()
        resolver.add_layer(Layer(LayerType.LOCAL, {"key": "value"}, active=False))

        data = resolver.to_dict()
        restored = LIVRPSResolver.from_dict(data)

        # Layer should still be inactive
        layers = restored.get_layers(LayerType.LOCAL)
        assert len(layers) == 1
        assert layers[0].active is False
