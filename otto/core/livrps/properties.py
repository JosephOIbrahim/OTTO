"""Cognitive property — the resolved output of LIVRPS composition.

A CognitiveProperty records which layer a value was resolved from,
allowing downstream code to understand the authority level behind
any piece of cognitive state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from otto.core.livrps.layers import LayerName


@dataclass(frozen=True)
class CognitiveProperty:
    """A single resolved cognitive property.

    Frozen because once resolved, the result is immutable for that
    resolution cycle. Downstream code should never mutate a resolved
    property — request a new resolution instead.

    Attributes:
        name: Property name (e.g. "energy_level", "expert_override").
        value: The resolved value from the winning layer.
        source_layer: Which LIVRPS layer this value came from.
        timestamp: When this resolution occurred (UTC).
    """

    name: str
    value: Any
    source_layer: LayerName
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
