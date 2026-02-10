"""
LIVRPS Composition Engine
=========================

USD-inspired composition semantics for cognitive state resolution.

LIVRPS Priority Order (highest to lowest):
- L (Local): Session state, oracle results - mutable, highest priority
- I (Inherits): Inherited context from parent agents
- V (VariantSets): Mode switching (focused/exploring/recovery)
- R (References): Calibration data, cross-session preferences
- P (Payloads): Domain knowledge loaded on demand
- S (Specializes): Base profile, constitutional defaults - lowest priority

Resolution Rule:
    First layer with a value wins.
    Safety floors from Specializes are ADDITIVE (never overridden below floor).

[He2025]-inspired determinism:
- Fixed evaluation order (L → I → V → R → P → S)
- Deterministic key iteration (sorted keys)
- Float comparisons use round(value, 6)
- Safety floor enforcement is deterministic

Reference:
    [He2025] He, Horace and Thinking Machines Lab,
    "Defeating Nondeterminism in LLM Inference", Sep 2025.
    See also: docs/HE2025_DETERMINISM_ADDENDUM.md
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
import copy


class LayerType(Enum):
    """
    LIVRPS layer types in priority order.

    Lower value = higher priority.
    """
    LOCAL = 1       # Session state, oracle results (mutable)
    INHERITS = 2    # Inherited context from parent
    VARIANTS = 3    # Mode variants (focused/exploring/recovery)
    REFERENCES = 4  # Calibration data, cross-session preferences
    PAYLOADS = 5    # Domain knowledge (loaded on demand)
    SPECIALIZES = 6 # Base profile, constitutional defaults


# Fixed evaluation order - Deterministic ordering (inspired by [He2025])
LIVRPS_ORDER: List[LayerType] = [
    LayerType.LOCAL,
    LayerType.INHERITS,
    LayerType.VARIANTS,
    LayerType.REFERENCES,
    LayerType.PAYLOADS,
    LayerType.SPECIALIZES,
]


@dataclass
class Layer:
    """
    A single composition layer.

    Attributes:
        layer_type: Which LIVRPS level this layer belongs to
        data: The attribute values in this layer
        name: Optional human-readable name for debugging
        active: Whether this layer participates in composition
    """
    layer_type: LayerType
    data: Dict[str, Any]
    name: str = ""
    active: bool = True

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from this layer."""
        return self.data.get(key, default)

    def has(self, key: str) -> bool:
        """Check if this layer has a value for the given key."""
        return key in self.data

    def set(self, key: str, value: Any) -> None:
        """Set a value in this layer."""
        self.data[key] = value

    def keys(self) -> Set[str]:
        """Get all keys in this layer (for merge discovery)."""
        return set(self.data.keys())


@dataclass
class CompositionResult:
    """
    Result of LIVRPS composition.

    Attributes:
        resolved: The final resolved values
        sources: Which layer each value came from
        overridden: Values that were overridden by higher layers
        safety_floors_applied: Safety floors that were enforced
    """
    resolved: Dict[str, Any]
    sources: Dict[str, LayerType]
    overridden: Dict[str, List[Tuple[LayerType, Any]]]
    safety_floors_applied: Dict[str, Tuple[Any, Any]]  # key -> (original, floor)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a resolved value."""
        return self.resolved.get(key, default)

    def source_of(self, key: str) -> Optional[LayerType]:
        """Get which layer a value came from."""
        return self.sources.get(key)

    def was_floored(self, key: str) -> bool:
        """Check if a value had a safety floor applied."""
        return key in self.safety_floors_applied


@dataclass
class SafetyFloor:
    """
    A safety floor constraint.

    Safety floors from constitutional layer are ADDITIVE - they establish
    minimums that cannot be violated regardless of other layer values.

    Attributes:
        key: The attribute this floor applies to
        minimum: The minimum allowed value
        comparator: How to compare values (default: >=)
    """
    key: str
    minimum: Any
    comparator: Callable[[Any, Any], bool] = field(
        default_factory=lambda: lambda value, floor: value >= floor
    )

    def check(self, value: Any) -> bool:
        """Check if value meets the floor requirement."""
        return self.comparator(value, self.minimum)

    def apply(self, value: Any) -> Any:
        """Apply the floor, returning floor if value doesn't meet it."""
        if self.check(value):
            return value
        return self.minimum


class LIVRPSResolver:
    """
    LIVRPS composition engine.

    Resolves conflicting attribute values from multiple layers using
    USD-inspired composition semantics.

    Example:
        resolver = LIVRPSResolver()

        # Add layers (order doesn't matter - priority is by LayerType)
        resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            {"burnout_level": "GREEN", "energy": "medium"},
            name="constitutional"
        ))
        resolver.add_layer(Layer(
            LayerType.LOCAL,
            {"burnout_level": "YELLOW"},
            name="session"
        ))

        # Resolve - LOCAL wins where it has values
        result = resolver.resolve()
        assert result.get("burnout_level") == "YELLOW"  # From LOCAL
        assert result.get("energy") == "medium"         # From SPECIALIZES

    [He2025]-inspired determinism:
        - Layers evaluated in FIXED LIVRPS order
        - Keys within layers iterated in sorted order
        - Float comparisons rounded to 6 decimal places
    """

    # Default safety floors from constitutional.usda
    DEFAULT_SAFETY_FLOORS: List[SafetyFloor] = [
        SafetyFloor("safety_floor_validator", 0.10),
        SafetyFloor("safety_floor_restorer", 0.05),
        SafetyFloor("safety_floor_scaffolder", 0.05),
    ]

    def __init__(self, safety_floors: Optional[List[SafetyFloor]] = None):
        """
        Initialize the resolver.

        Args:
            safety_floors: Custom safety floors (or use defaults)
        """
        self._layers: Dict[LayerType, List[Layer]] = {lt: [] for lt in LayerType}
        self._safety_floors = safety_floors or self.DEFAULT_SAFETY_FLOORS.copy()

    def add_layer(self, layer: Layer) -> None:
        """
        Add a layer to the composition.

        Multiple layers of the same type are allowed (first wins within type).

        Args:
            layer: The layer to add
        """
        self._layers[layer.layer_type].append(layer)

    def remove_layer(self, layer: Layer) -> bool:
        """
        Remove a layer from the composition.

        Args:
            layer: The layer to remove

        Returns:
            True if the layer was found and removed
        """
        try:
            self._layers[layer.layer_type].remove(layer)
            return True
        except ValueError:
            return False

    def get_layers(self, layer_type: LayerType) -> List[Layer]:
        """Get all layers of a given type."""
        return self._layers[layer_type].copy()

    def clear_layer_type(self, layer_type: LayerType) -> None:
        """Remove all layers of a given type."""
        self._layers[layer_type] = []

    def add_safety_floor(self, floor: SafetyFloor) -> None:
        """Add a safety floor constraint."""
        self._safety_floors.append(floor)

    def resolve(self) -> CompositionResult:
        """
        Resolve all layers using LIVRPS composition.

        Returns:
            CompositionResult with resolved values and provenance

        [He2025]-inspired determinism:
            - FIXED evaluation order (L → I → V → R → P → S)
            - Keys processed in sorted order
            - Safety floors applied deterministically
        """
        resolved: Dict[str, Any] = {}
        sources: Dict[str, LayerType] = {}
        overridden: Dict[str, List[Tuple[LayerType, Any]]] = {}

        # Collect all keys across all layers (sorted for determinism)
        all_keys: Set[str] = set()
        for layer_type in LIVRPS_ORDER:
            for layer in self._layers[layer_type]:
                if layer.active:
                    all_keys.update(layer.keys())

        # [He2025] CRITICAL: Process keys in sorted order
        for key in sorted(all_keys):
            # Find first layer with this value (LIVRPS order)
            for layer_type in LIVRPS_ORDER:
                for layer in self._layers[layer_type]:
                    if layer.active and layer.has(key):
                        value = layer.get(key)

                        if key not in resolved:
                            # First value wins
                            resolved[key] = value
                            sources[key] = layer_type
                        else:
                            # Track overridden values
                            if key not in overridden:
                                overridden[key] = []
                            overridden[key].append((layer_type, value))

        # Apply safety floors (from Specializes layer, ADDITIVE)
        safety_floors_applied: Dict[str, Tuple[Any, Any]] = {}
        for floor in self._safety_floors:
            if floor.key in resolved:
                original = resolved[floor.key]
                floored = floor.apply(original)
                if floored != original:
                    safety_floors_applied[floor.key] = (original, floor.minimum)
                    resolved[floor.key] = floored

        return CompositionResult(
            resolved=resolved,
            sources=sources,
            overridden=overridden,
            safety_floors_applied=safety_floors_applied,
        )

    def resolve_attribute(self, key: str, default: Any = None) -> Tuple[Any, Optional[LayerType]]:
        """
        Resolve a single attribute.

        More efficient than full resolve() when you need one value.

        Args:
            key: The attribute to resolve
            default: Value if not found in any layer

        Returns:
            Tuple of (value, source_layer_type) or (default, None)
        """
        for layer_type in LIVRPS_ORDER:
            for layer in self._layers[layer_type]:
                if layer.active and layer.has(key):
                    return (layer.get(key), layer_type)
        return (default, None)

    def update_local(self, key: str, value: Any) -> None:
        """
        Update a value in the LOCAL layer.

        Creates the LOCAL layer if it doesn't exist.

        Args:
            key: Attribute to update
            value: New value
        """
        if not self._layers[LayerType.LOCAL]:
            self._layers[LayerType.LOCAL].append(
                Layer(LayerType.LOCAL, {}, name="session")
            )
        self._layers[LayerType.LOCAL][0].set(key, value)

    def update_references(self, key: str, value: Any) -> None:
        """
        Update a value in the REFERENCES layer (calibration).

        Creates the REFERENCES layer if it doesn't exist.

        Args:
            key: Attribute to update
            value: New value
        """
        if not self._layers[LayerType.REFERENCES]:
            self._layers[LayerType.REFERENCES].append(
                Layer(LayerType.REFERENCES, {}, name="calibration")
            )
        self._layers[LayerType.REFERENCES][0].set(key, value)

    def set_variant(self, variant_name: str, variant_data: Dict[str, Any]) -> None:
        """
        Set the active variant.

        Variants are mode-specific overrides (focused, exploring, recovery).
        Only one variant can be active at a time.

        Args:
            variant_name: Name of the variant (for debugging)
            variant_data: The variant's attribute values
        """
        # Clear existing variants and add new one
        self._layers[LayerType.VARIANTS] = [
            Layer(LayerType.VARIANTS, variant_data, name=variant_name)
        ]

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the resolver state to a dictionary.

        [He2025]-inspired determinism: Keys sorted for deterministic serialization.
        """
        return {
            "layers": {
                layer_type.name: [
                    {
                        "name": layer.name,
                        "active": layer.active,
                        "data": {k: layer.data[k] for k in sorted(layer.data.keys())},
                    }
                    for layer in layers
                ]
                for layer_type, layers in self._layers.items()
            },
            "safety_floors": [
                {"key": f.key, "minimum": f.minimum}
                for f in sorted(self._safety_floors, key=lambda x: x.key)
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LIVRPSResolver":
        """
        Deserialize a resolver from a dictionary.

        Args:
            data: Serialized resolver state

        Returns:
            New LIVRPSResolver instance
        """
        floors = [
            SafetyFloor(key=f["key"], minimum=f["minimum"])
            for f in data.get("safety_floors", [])
        ]
        resolver = cls(safety_floors=floors)

        for layer_type_name, layers in data.get("layers", {}).items():
            layer_type = LayerType[layer_type_name]
            for layer_data in layers:
                resolver.add_layer(Layer(
                    layer_type=layer_type,
                    data=layer_data.get("data", {}),
                    name=layer_data.get("name", ""),
                    active=layer_data.get("active", True),
                ))

        return resolver


def kahan_sum(values: List[float]) -> float:
    """
    [He2025] Batch-invariant summation.

    Uses Kahan summation algorithm for numerical stability,
    with sorted input for deterministic order.

    Args:
        values: List of floats to sum

    Returns:
        Sum with minimized floating-point error
    """
    total = 0.0
    compensation = 0.0
    for v in sorted(values):  # CRITICAL: sort first
        y = v - compensation
        t = total + y
        compensation = (t - total) - y
        total = t
    return total


def round_for_comparison(value: float, precision: int = 6) -> float:
    """
    [He2025] Round a float for comparison.

    All float comparisons should use this for determinism.

    Args:
        value: The float to round
        precision: Decimal places (default 6)

    Returns:
        Rounded value
    """
    return round(value, precision)


# =============================================================================
# Predefined Variants (from cognitive.usda)
# =============================================================================

VARIANT_FOCUSED = {
    "interruption_threshold": 0.7,
    "tangent_allowance": 2,
    "paradigm": "cortex",
}

VARIANT_EXPLORING = {
    "interruption_threshold": 0.3,
    "tangent_allowance": 5,
    "paradigm": "mycelium",
}

VARIANT_TEACHING = {
    "interruption_threshold": 0.5,
    "tangent_allowance": 3,
    "paradigm": "cortex",
}

VARIANT_RECOVERY = {
    "interruption_threshold": 0.9,
    "tangent_allowance": 0,
    "paradigm": "cortex",
}

COGNITIVE_VARIANTS = {
    "focused": VARIANT_FOCUSED,
    "exploring": VARIANT_EXPLORING,
    "teaching": VARIANT_TEACHING,
    "recovery": VARIANT_RECOVERY,
}
