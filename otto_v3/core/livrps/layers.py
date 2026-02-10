"""Layer definitions for the LIVRPS cognitive substrate.

Each layer has a fixed priority (encoded in the IntEnum value). During
resolution, higher-numbered layers override lower ones. This ordering
is the core invariant of the compositor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class LayerName(IntEnum):
    """LIVRPS layer names with priority ordering.

    The integer value IS the priority: higher number = higher priority.
    Sovereign (5) always wins over everything. Learned (0) is lowest.
    """

    LEARNED = 0      # Accumulated from interactions (lowest priority)
    INHERITED = 1    # System defaults
    VOLATILE = 2     # Session-only, ephemeral
    REACTIVE = 3     # Real-time signal response
    PROTECTIVE = 4   # Safety overrides
    SOVEREIGN = 5    # User explicit choice (HIGHEST priority)


@dataclass
class Layer:
    """A single composition layer holding cognitive properties.

    Attributes:
        name: Which LIVRPS layer this is.
        properties: Key-value property store. Keys are property names,
            values are arbitrary cognitive data.
        active: Whether this layer participates in resolution. Inactive
            layers are skipped entirely.
    """

    name: LayerName
    properties: dict[str, Any] = field(default_factory=dict)
    active: bool = True


class LayerStack:
    """Ordered collection of all six LIVRPS layers.

    Provides indexed access by LayerName and iteration in priority
    order (ascending or descending). All iteration uses sorted order
    for Determinism.
    """

    def __init__(self) -> None:
        # Create one layer per LayerName, sorted by priority
        self._layers: dict[LayerName, Layer] = {
            name: Layer(name=name)
            for name in sorted(LayerName)
        }

    def __getitem__(self, name: LayerName) -> Layer:
        return self._layers[name]

    def ascending(self) -> list[Layer]:
        """Layers in ascending priority order (Learned → Sovereign)."""
        return [self._layers[name] for name in sorted(LayerName)]

    def descending(self) -> list[Layer]:
        """Layers in descending priority order (Sovereign → Learned)."""
        return [self._layers[name] for name in sorted(LayerName, reverse=True)]

    @property
    def all_layers(self) -> list[Layer]:
        """All layers in ascending priority order."""
        return self.ascending()
