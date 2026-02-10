"""LIVRPS Compositor — deterministic layer resolution engine.

The compositor is the core of Patent Claim #1. It resolves cognitive
properties by checking layers from highest priority (Sovereign) down
to lowest (Learned). The first active layer that contains the requested
property wins.

Determinism:
    - All property name iteration uses sorted()
    - Resolution order is fixed by IntEnum value (descending)
    - resolve_all() output is sorted by property name
    - Same inputs always produce the same outputs
"""

from __future__ import annotations

from typing import Any, Optional

from otto_v3.core.livrps.layers import Layer, LayerName, LayerStack
from otto_v3.core.livrps.properties import CognitiveProperty


class LIVRPSCompositor:
    """Deterministic cognitive property compositor.

    Holds a LayerStack and resolves properties by highest-active-layer-
    wins semantics. Thread-safe reads (resolution is pure), but writes
    (set_property, clear_property) are not thread-safe — callers must
    synchronize externally if needed.
    """

    def __init__(self) -> None:
        self._stack = LayerStack()

    # ----- Layer access -----

    @property
    def stack(self) -> LayerStack:
        """Access the underlying layer stack."""
        return self._stack

    def get_layer(self, name: LayerName) -> Layer:
        """Get a specific layer by name."""
        return self._stack[name]

    # ----- Property mutation -----

    def set_property(
        self, layer: LayerName, name: str, value: Any
    ) -> None:
        """Set a property on a specific layer.

        Args:
            layer: Which LIVRPS layer to set the property on.
            name: Property name.
            value: Property value.
        """
        self._stack[layer].properties[name] = value

    def clear_property(self, layer: LayerName, name: str) -> None:
        """Remove a property from a specific layer.

        No-op if the property doesn't exist on that layer.

        Args:
            layer: Which LIVRPS layer to clear from.
            name: Property name to remove.
        """
        self._stack[layer].properties.pop(name, None)

    # ----- Layer activation -----

    def activate_layer(self, name: LayerName) -> None:
        """Activate a layer so it participates in resolution."""
        self._stack[name].active = True

    def deactivate_layer(self, name: LayerName) -> None:
        """Deactivate a layer so it is skipped during resolution."""
        self._stack[name].active = False

    def is_active(self, name: LayerName) -> bool:
        """Check whether a layer is currently active."""
        return self._stack[name].active

    # ----- Resolution (read-only, deterministic) -----

    def resolve(self, property_name: str) -> Optional[CognitiveProperty]:
        """Resolve a single property by checking layers highest-first.

        Iterates layers in descending priority order (Sovereign → Learned).
        The first active layer containing the property wins.

        Args:
            property_name: The cognitive property to resolve.

        Returns:
            CognitiveProperty from the winning layer, or None if no
            active layer contains this property.
        """
        for layer in self._stack.descending():
            if layer.active and property_name in layer.properties:
                return CognitiveProperty(
                    name=property_name,
                    value=layer.properties[property_name],
                    source_layer=layer.name,
                )
        return None

    def resolve_all(self) -> dict[str, CognitiveProperty]:
        """Resolve all properties across all active layers.

        Collects every property name from every active layer, then
        resolves each one. Output dict is sorted by property name
        for determinism.

        Returns:
            Dict of property_name → CognitiveProperty, sorted by key.
        """
        # Collect all property names from active layers
        all_names: set[str] = set()
        for layer in self._stack.ascending():
            if layer.active:
                all_names.update(layer.properties.keys())

        # Resolve each in sorted order for determinism
        resolved: dict[str, CognitiveProperty] = {}
        for name in sorted(all_names):
            prop = self.resolve(name)
            if prop is not None:
                resolved[name] = prop

        return resolved

    def resolve_with_audit(
        self, property_name: str
    ) -> list[tuple[LayerName, Any]]:
        """Resolve a property and return ALL layer values for auditing.

        Useful for debugging — shows what every layer thinks the value
        should be, not just the winner.

        Args:
            property_name: The property to audit.

        Returns:
            List of (layer_name, value) tuples for every active layer
            that contains this property, in descending priority order.
        """
        audit: list[tuple[LayerName, Any]] = []
        for layer in self._stack.descending():
            if layer.active and property_name in layer.properties:
                audit.append((layer.name, layer.properties[property_name]))
        return audit
