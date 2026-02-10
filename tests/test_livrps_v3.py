"""Tests for the LIVRPS cognitive substrate — Day 2 of OTTO OS v3.0.

These tests verify:
1. Layer priority ordering (S > P > R > V > I > L)
2. Compositor resolution (highest active layer wins)
3. Inactive layers are skipped
4. resolve_all() is deterministic (100x consistency check)
5. Same inputs always produce same outputs
6. Property mutation and layer activation/deactivation
7. Audit trail for debugging
"""

from __future__ import annotations

import dataclasses

import pytest

from otto.core.livrps.layers import Layer, LayerName, LayerStack
from otto.core.livrps.properties import CognitiveProperty
from otto.core.livrps.compositor import LIVRPSCompositor


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def compositor() -> LIVRPSCompositor:
    """Fresh compositor with default empty layers."""
    return LIVRPSCompositor()


@pytest.fixture
def loaded_compositor() -> LIVRPSCompositor:
    """Compositor with properties set on multiple layers."""
    c = LIVRPSCompositor()
    c.set_property(LayerName.LEARNED, "energy", "medium")
    c.set_property(LayerName.LEARNED, "focus_mode", "broad")
    c.set_property(LayerName.INHERITED, "energy", "high")
    c.set_property(LayerName.INHERITED, "theme", "default")
    c.set_property(LayerName.VOLATILE, "session_goal", "implement LIVRPS")
    c.set_property(LayerName.REACTIVE, "energy", "low")
    c.set_property(LayerName.PROTECTIVE, "energy", "depleted")
    c.set_property(LayerName.SOVEREIGN, "theme", "dark")
    return c


# ===================================================================
# Test: LayerName enum
# ===================================================================

class TestLayerName:
    """LayerName must have exactly 6 values with correct priority ordering."""

    def test_has_six_layers(self) -> None:
        assert len(LayerName) == 6

    def test_priority_order(self) -> None:
        assert LayerName.LEARNED < LayerName.INHERITED
        assert LayerName.INHERITED < LayerName.VOLATILE
        assert LayerName.VOLATILE < LayerName.REACTIVE
        assert LayerName.REACTIVE < LayerName.PROTECTIVE
        assert LayerName.PROTECTIVE < LayerName.SOVEREIGN

    def test_learned_is_zero(self) -> None:
        assert LayerName.LEARNED == 0

    def test_sovereign_is_five(self) -> None:
        assert LayerName.SOVEREIGN == 5

    def test_is_int_enum(self) -> None:
        """IntEnum so we get free comparison operators."""
        assert isinstance(LayerName.LEARNED, int)

    def test_names_match_livrps(self) -> None:
        """Layer names spell out L-I-V-R-P-S."""
        names = [n.name[0] for n in sorted(LayerName)]
        assert names == ["L", "I", "V", "R", "P", "S"]


# ===================================================================
# Test: Layer dataclass
# ===================================================================

class TestLayer:
    """Layer must hold properties and an active flag."""

    def test_default_properties_empty(self) -> None:
        layer = Layer(name=LayerName.LEARNED)
        assert layer.properties == {}

    def test_default_active_true(self) -> None:
        layer = Layer(name=LayerName.LEARNED)
        assert layer.active is True

    def test_properties_are_independent(self) -> None:
        """Each Layer instance must have its own properties dict."""
        a = Layer(name=LayerName.LEARNED)
        b = Layer(name=LayerName.INHERITED)
        a.properties["x"] = 1
        assert "x" not in b.properties


# ===================================================================
# Test: LayerStack
# ===================================================================

class TestLayerStack:
    """LayerStack must provide ordered access to all 6 layers."""

    def test_has_six_layers(self) -> None:
        stack = LayerStack()
        assert len(stack.ascending()) == 6

    def test_ascending_order(self) -> None:
        stack = LayerStack()
        layers = stack.ascending()
        priorities = [l.name.value for l in layers]
        assert priorities == [0, 1, 2, 3, 4, 5]

    def test_descending_order(self) -> None:
        stack = LayerStack()
        layers = stack.descending()
        priorities = [l.name.value for l in layers]
        assert priorities == [5, 4, 3, 2, 1, 0]

    def test_getitem_by_layer_name(self) -> None:
        stack = LayerStack()
        layer = stack[LayerName.SOVEREIGN]
        assert layer.name == LayerName.SOVEREIGN

    def test_all_layers_are_active_by_default(self) -> None:
        stack = LayerStack()
        for layer in stack.ascending():
            assert layer.active is True


# ===================================================================
# Test: CognitiveProperty
# ===================================================================

class TestCognitiveProperty:
    """CognitiveProperty must be frozen and carry resolution metadata."""

    def test_is_frozen(self) -> None:
        prop = CognitiveProperty(
            name="energy",
            value="high",
            source_layer=LayerName.INHERITED,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            prop.value = "low"  # type: ignore[misc]

    def test_records_source_layer(self) -> None:
        prop = CognitiveProperty(
            name="energy",
            value="high",
            source_layer=LayerName.REACTIVE,
        )
        assert prop.source_layer == LayerName.REACTIVE

    def test_has_timestamp(self) -> None:
        prop = CognitiveProperty(
            name="energy",
            value="high",
            source_layer=LayerName.LEARNED,
        )
        assert prop.timestamp is not None


# ===================================================================
# Test: Compositor — basic resolution
# ===================================================================

class TestCompositorResolve:
    """resolve() must return the value from the highest active layer."""

    def test_empty_compositor_returns_none(self, compositor: LIVRPSCompositor) -> None:
        assert compositor.resolve("nonexistent") is None

    def test_single_layer_resolves(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.LEARNED, "energy", "medium")
        result = compositor.resolve("energy")
        assert result is not None
        assert result.value == "medium"
        assert result.source_layer == LayerName.LEARNED

    def test_higher_layer_overrides_lower(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.LEARNED, "energy", "medium")
        compositor.set_property(LayerName.INHERITED, "energy", "high")
        result = compositor.resolve("energy")
        assert result is not None
        assert result.value == "high"
        assert result.source_layer == LayerName.INHERITED

    def test_sovereign_overrides_all(self, loaded_compositor: LIVRPSCompositor) -> None:
        """S overrides L, I, V, R, P — the core LIVRPS invariant."""
        loaded_compositor.set_property(LayerName.SOVEREIGN, "energy", "user_says_fine")
        result = loaded_compositor.resolve("energy")
        assert result is not None
        assert result.value == "user_says_fine"
        assert result.source_layer == LayerName.SOVEREIGN

    def test_protective_overrides_livrps_but_not_sovereign(
        self, compositor: LIVRPSCompositor
    ) -> None:
        """P overrides L, I, V, R but NOT S."""
        compositor.set_property(LayerName.LEARNED, "energy", "medium")
        compositor.set_property(LayerName.INHERITED, "energy", "high")
        compositor.set_property(LayerName.VOLATILE, "energy", "session_high")
        compositor.set_property(LayerName.REACTIVE, "energy", "rising")
        compositor.set_property(LayerName.PROTECTIVE, "energy", "depleted_override")

        result = compositor.resolve("energy")
        assert result is not None
        assert result.value == "depleted_override"
        assert result.source_layer == LayerName.PROTECTIVE

        # Now add Sovereign — it should win
        compositor.set_property(LayerName.SOVEREIGN, "energy", "user_override")
        result = compositor.resolve("energy")
        assert result is not None
        assert result.value == "user_override"
        assert result.source_layer == LayerName.SOVEREIGN

    def test_reactive_overrides_volatile(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.VOLATILE, "mood", "calm")
        compositor.set_property(LayerName.REACTIVE, "mood", "alert")
        result = compositor.resolve("mood")
        assert result is not None
        assert result.value == "alert"
        assert result.source_layer == LayerName.REACTIVE

    def test_each_layer_beats_all_lower(self, compositor: LIVRPSCompositor) -> None:
        """Every layer must override every layer below it."""
        layers_ascending = sorted(LayerName)
        for i, higher in enumerate(layers_ascending[1:], start=1):
            # Fresh compositor for each pair
            c = LIVRPSCompositor()
            for lower in layers_ascending[:i]:
                c.set_property(lower, "test_prop", f"from_{lower.name}")
            c.set_property(higher, "test_prop", f"from_{higher.name}")

            result = c.resolve("test_prop")
            assert result is not None, f"{higher.name} failed to resolve"
            assert result.value == f"from_{higher.name}", (
                f"Expected {higher.name} to win, got {result.source_layer.name}"
            )
            assert result.source_layer == higher


# ===================================================================
# Test: Compositor — inactive layers
# ===================================================================

class TestCompositorInactiveLayers:
    """Inactive layers must be completely skipped during resolution."""

    def test_inactive_layer_skipped(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.SOVEREIGN, "energy", "user_says")
        compositor.set_property(LayerName.LEARNED, "energy", "learned")
        compositor.deactivate_layer(LayerName.SOVEREIGN)

        result = compositor.resolve("energy")
        assert result is not None
        assert result.value == "learned"
        assert result.source_layer == LayerName.LEARNED

    def test_reactivated_layer_participates(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.SOVEREIGN, "energy", "user_says")
        compositor.set_property(LayerName.LEARNED, "energy", "learned")
        compositor.deactivate_layer(LayerName.SOVEREIGN)
        compositor.activate_layer(LayerName.SOVEREIGN)

        result = compositor.resolve("energy")
        assert result is not None
        assert result.value == "user_says"

    def test_all_inactive_returns_none(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.LEARNED, "energy", "medium")
        for name in LayerName:
            compositor.deactivate_layer(name)

        assert compositor.resolve("energy") is None

    def test_is_active_reflects_state(self, compositor: LIVRPSCompositor) -> None:
        assert compositor.is_active(LayerName.VOLATILE) is True
        compositor.deactivate_layer(LayerName.VOLATILE)
        assert compositor.is_active(LayerName.VOLATILE) is False
        compositor.activate_layer(LayerName.VOLATILE)
        assert compositor.is_active(LayerName.VOLATILE) is True


# ===================================================================
# Test: Compositor — property mutation
# ===================================================================

class TestCompositorMutation:
    """set_property and clear_property must work correctly."""

    def test_set_property(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.VOLATILE, "goal", "ship it")
        layer = compositor.get_layer(LayerName.VOLATILE)
        assert layer.properties["goal"] == "ship it"

    def test_overwrite_property(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.VOLATILE, "goal", "first")
        compositor.set_property(LayerName.VOLATILE, "goal", "updated")
        layer = compositor.get_layer(LayerName.VOLATILE)
        assert layer.properties["goal"] == "updated"

    def test_clear_property(self, compositor: LIVRPSCompositor) -> None:
        compositor.set_property(LayerName.VOLATILE, "goal", "temp")
        compositor.clear_property(LayerName.VOLATILE, "goal")
        assert "goal" not in compositor.get_layer(LayerName.VOLATILE).properties

    def test_clear_nonexistent_is_noop(self, compositor: LIVRPSCompositor) -> None:
        """Clearing a property that doesn't exist should not raise."""
        compositor.clear_property(LayerName.VOLATILE, "nope")  # Should not raise


# ===================================================================
# Test: resolve_all — determinism
# ===================================================================

class TestResolveAll:
    """resolve_all() must be deterministic and collect from all layers."""

    def test_empty_compositor(self, compositor: LIVRPSCompositor) -> None:
        assert compositor.resolve_all() == {}

    def test_collects_from_multiple_layers(
        self, loaded_compositor: LIVRPSCompositor
    ) -> None:
        resolved = loaded_compositor.resolve_all()
        # Should have: energy, focus_mode, theme, session_goal
        assert "energy" in resolved
        assert "focus_mode" in resolved
        assert "theme" in resolved
        assert "session_goal" in resolved

    def test_highest_layer_wins_in_resolve_all(
        self, loaded_compositor: LIVRPSCompositor
    ) -> None:
        resolved = loaded_compositor.resolve_all()
        # energy: set on L(medium), I(high), R(low), P(depleted)
        # P is highest → depleted
        assert resolved["energy"].value == "depleted"
        assert resolved["energy"].source_layer == LayerName.PROTECTIVE

        # theme: set on I(default), S(dark)
        # S is highest → dark
        assert resolved["theme"].value == "dark"
        assert resolved["theme"].source_layer == LayerName.SOVEREIGN

    def test_output_sorted_by_property_name(
        self, loaded_compositor: LIVRPSCompositor
    ) -> None:
        """Keys must be in sorted order for [He2025] compliance."""
        resolved = loaded_compositor.resolve_all()
        keys = list(resolved.keys())
        assert keys == sorted(keys)

    def test_deterministic_100x(self, loaded_compositor: LIVRPSCompositor) -> None:
        """Run resolve_all 100 times — result must be identical every time."""
        first = {
            k: (v.value, v.source_layer)
            for k, v in loaded_compositor.resolve_all().items()
        }
        for i in range(99):
            current = {
                k: (v.value, v.source_layer)
                for k, v in loaded_compositor.resolve_all().items()
            }
            assert current == first, f"Divergence on iteration {i + 2}"

    def test_same_input_same_output(self) -> None:
        """Two compositors with identical state must resolve identically."""
        def build() -> LIVRPSCompositor:
            c = LIVRPSCompositor()
            c.set_property(LayerName.LEARNED, "a", 1)
            c.set_property(LayerName.INHERITED, "b", 2)
            c.set_property(LayerName.VOLATILE, "a", 10)
            c.set_property(LayerName.REACTIVE, "c", 3)
            c.set_property(LayerName.PROTECTIVE, "b", 20)
            c.set_property(LayerName.SOVEREIGN, "d", 4)
            return c

        r1 = {k: (v.value, v.source_layer) for k, v in build().resolve_all().items()}
        r2 = {k: (v.value, v.source_layer) for k, v in build().resolve_all().items()}
        assert r1 == r2


# ===================================================================
# Test: resolve_with_audit
# ===================================================================

class TestResolveWithAudit:
    """Audit trail must show all competing values in priority order."""

    def test_audit_shows_all_layers(self, loaded_compositor: LIVRPSCompositor) -> None:
        # energy exists on L, I, R, P
        audit = loaded_compositor.resolve_with_audit("energy")
        assert len(audit) == 4
        # First entry should be highest priority (PROTECTIVE)
        assert audit[0][0] == LayerName.PROTECTIVE
        assert audit[0][1] == "depleted"
        # Last entry should be lowest (LEARNED)
        assert audit[-1][0] == LayerName.LEARNED
        assert audit[-1][1] == "medium"

    def test_audit_empty_for_unknown(self, compositor: LIVRPSCompositor) -> None:
        assert compositor.resolve_with_audit("nonexistent") == []

    def test_audit_skips_inactive(self, loaded_compositor: LIVRPSCompositor) -> None:
        loaded_compositor.deactivate_layer(LayerName.PROTECTIVE)
        audit = loaded_compositor.resolve_with_audit("energy")
        layer_names = [name for name, _ in audit]
        assert LayerName.PROTECTIVE not in layer_names


# ===================================================================
# Test: Package imports
# ===================================================================

class TestPackageImports:
    """Verify the __init__.py re-exports work correctly."""

    def test_import_from_package(self) -> None:
        from otto.core.livrps import (
            CognitiveProperty,
            Layer,
            LayerName,
            LayerStack,
            LIVRPSCompositor,
        )
        # Just verifying imports work
        assert LayerName.SOVEREIGN.value == 5
        assert LIVRPSCompositor is not None
