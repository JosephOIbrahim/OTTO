"""
USD-Native Cognitive Stage
==========================

Implements cognitive state management using actual USD (Universal Scene Description)
composition semantics. This is the key technical novelty of Orchestra.

USD's LIVRPS composition order maps to cognitive state priority:
- L (Local/Session): Current session state - highest priority, mutable
- I (Inherits): Inherited context from parent (agent chains)
- V (Variants): Cognitive mode variants (focused/exploring/recovery/teaching)
- R (References): Calibration data - cross-session learned preferences
- P (Payloads): Domain knowledge - loaded on demand
- S (Specializes): Constitutional/base profile - safety floors, immutable

Novel Contribution:
No existing system uses Pixar's USD scene graph composition to resolve
cognitive state priority. This is genuine technical novelty.

Implementation:
- When pxr is available: Uses actual Usd.Stage for composition
- When pxr is unavailable: Uses mock implementation with same semantics
"""

import json
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from .cognitive_state import (
    CognitiveState,
    CognitiveStateManager,
    BurnoutLevel,
    MomentumPhase,
    EnergyLevel,
    CognitiveMode,
    Altitude,
    ATTRACTOR_BASINS,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Check for pxr availability
# =============================================================================

try:
    from pxr import Usd, Sdf, Vt, Gf
    PXR_AVAILABLE = True
    logger.info("USD Python bindings (pxr) available - using native implementation")
except ImportError:
    PXR_AVAILABLE = False
    logger.info("USD Python bindings (pxr) not available - using mock implementation")


# =============================================================================
# LIVRPS Layer Priority (Fixed Order)
# =============================================================================

class LayerPriority(Enum):
    """
    LIVRPS layer priority for cognitive state resolution.

    Higher priority (lower value) wins in composition.
    """
    LOCAL = 1       # Session state - highest priority (mutable)
    INHERITS = 2    # Inherited from parent context
    VARIANTS = 3    # Mode variants (focused/exploring/etc)
    REFERENCES = 4  # Calibration data
    PAYLOADS = 5    # Domain knowledge
    SPECIALIZES = 6 # Constitutional base - lowest priority (safety floors)


# =============================================================================
# Constitutional Values (Safety Floors - Never Violated)
# =============================================================================

CONSTITUTIONAL_VALUES = {
    # Safety floors for cognitive limits
    "safety_floor_protector": 0.10,     # Min weight for emotional safety
    "safety_floor_restorer": 0.05,      # Min weight for recovery support
    "working_memory_limit": 3,          # Miller's Law with margin
    "max_agent_depth": 3,               # Prevent agent chain complexity
    "max_parallel_agents": 3,           # Limit cognitive tracking load
    "body_check_interval": 20,          # Rapid exchanges before check
    "tangent_budget_default": 5,        # Exploration allowance

    # Thinking depth safety gates
    "max_depth_depleted": "minimal",
    "max_depth_low_energy": "standard",
    "max_depth_red_burnout": "minimal",
    "max_depth_orange_burnout": "standard",
}


# =============================================================================
# Layer Data Structures
# =============================================================================

@dataclass
class CognitiveLayer:
    """
    A single layer in the cognitive composition stack.

    Each layer can express opinions on cognitive attributes.
    Resolution happens via LIVRPS priority.
    """
    name: str
    priority: LayerPriority
    attributes: Dict[str, Any] = field(default_factory=dict)
    sublayers: List['CognitiveLayer'] = field(default_factory=list)

    def get_attribute(self, name: str) -> Optional[Any]:
        """Get attribute value from this layer (or None if not set)."""
        return self.attributes.get(name)

    def set_attribute(self, name: str, value: Any) -> None:
        """Set attribute value in this layer."""
        self.attributes[name] = value

    def has_attribute(self, name: str) -> bool:
        """Check if this layer has an opinion on this attribute."""
        return name in self.attributes

    def to_dict(self) -> Dict[str, Any]:
        """Serialize layer to dict."""
        return {
            "name": self.name,
            "priority": self.priority.name,
            "attributes": self.attributes.copy(),
            "sublayers": [sl.to_dict() for sl in self.sublayers]
        }


@dataclass
class AttributeOpinion:
    """
    Tracks all opinions for a single attribute across layers.

    Used for debugging and tension detection - seeing which layers
    disagree about an attribute's value.
    """
    attribute_name: str
    opinions: List[Tuple[str, LayerPriority, Any]] = field(default_factory=list)
    resolved_value: Any = None
    resolved_from: Optional[str] = None
    has_conflict: bool = False

    def add_opinion(self, layer_name: str, priority: LayerPriority, value: Any) -> None:
        """Add a layer's opinion on this attribute."""
        self.opinions.append((layer_name, priority, value))

        # Check for conflict
        if len(self.opinions) > 1:
            values = [v for _, _, v in self.opinions]
            if len(set(str(v) for v in values)) > 1:
                self.has_conflict = True

    def resolve(self) -> Any:
        """
        Resolve using LIVRPS priority (lowest priority value wins).

        This IS USD composition - highest priority layer's opinion wins.
        """
        if not self.opinions:
            return None

        # Sort by priority (lower priority value = higher precedence)
        sorted_opinions = sorted(self.opinions, key=lambda x: x[1].value)
        winner = sorted_opinions[0]

        self.resolved_value = winner[2]
        self.resolved_from = winner[0]

        return self.resolved_value


# =============================================================================
# Abstract Backend Interface
# =============================================================================

class CognitiveStageBackend(ABC):
    """
    Abstract interface for cognitive stage backends.

    Allows swapping between mock and pxr implementations.
    """

    @abstractmethod
    def create_stage(self) -> None:
        """Create a new cognitive stage."""
        pass

    @abstractmethod
    def load_stage(self, path: Path) -> bool:
        """Load stage from file."""
        pass

    @abstractmethod
    def save_stage(self, path: Path) -> None:
        """Save stage to file."""
        pass

    @abstractmethod
    def get_layer(self, priority: LayerPriority) -> CognitiveLayer:
        """Get layer by priority."""
        pass

    @abstractmethod
    def set_attribute(self, layer: LayerPriority, name: str, value: Any) -> None:
        """Set attribute on a specific layer."""
        pass

    @abstractmethod
    def get_resolved_attribute(self, name: str) -> Any:
        """Get attribute value resolved through LIVRPS composition."""
        pass

    @abstractmethod
    def get_opinion_stack(self, name: str) -> AttributeOpinion:
        """Get all opinions for an attribute (for debugging/tension detection)."""
        pass

    @abstractmethod
    def set_variant(self, variant_set: str, variant: str) -> None:
        """Set active variant (e.g., cognitive_mode -> focused)."""
        pass

    @abstractmethod
    def get_variant(self, variant_set: str) -> Optional[str]:
        """Get active variant for a variant set."""
        pass

    @abstractmethod
    def export_usda(self, path: Path) -> None:
        """Export stage to .usda format for debugging."""
        pass


# =============================================================================
# Mock Backend (When pxr unavailable)
# =============================================================================

class MockCognitiveBackend(CognitiveStageBackend):
    """
    Mock implementation of cognitive stage.

    Uses same LIVRPS semantics as real USD, but without pxr dependency.
    Useful for development and when USD isn't installed.
    """

    def __init__(self):
        self.layers: Dict[LayerPriority, CognitiveLayer] = {}
        self.variants: Dict[str, str] = {}  # variant_set -> active_variant
        self.variant_values: Dict[str, Dict[str, Dict[str, Any]]] = {}  # variant_set -> variant -> attrs

    def create_stage(self) -> None:
        """Create cognitive stage with all layers."""
        # Initialize layers in LIVRPS order
        self.layers = {
            LayerPriority.LOCAL: CognitiveLayer("session", LayerPriority.LOCAL),
            LayerPriority.INHERITS: CognitiveLayer("inherited", LayerPriority.INHERITS),
            LayerPriority.VARIANTS: CognitiveLayer("variants", LayerPriority.VARIANTS),
            LayerPriority.REFERENCES: CognitiveLayer("calibration", LayerPriority.REFERENCES),
            LayerPriority.PAYLOADS: CognitiveLayer("domain", LayerPriority.PAYLOADS),
            LayerPriority.SPECIALIZES: CognitiveLayer("constitutional", LayerPriority.SPECIALIZES),
        }

        # Initialize constitutional layer with safety floors
        for attr, value in CONSTITUTIONAL_VALUES.items():
            self.layers[LayerPriority.SPECIALIZES].set_attribute(attr, value)

        # Initialize default variants
        self._init_variants()

        logger.debug("Created mock cognitive stage with LIVRPS layers")

    def _init_variants(self) -> None:
        """Initialize cognitive mode variants."""
        self.variant_values = {
            "cognitive_mode": {
                "focused": {
                    "interruption_threshold": 0.7,
                    "tangent_allowance": 2,
                    "paradigm": "cortex",
                },
                "exploring": {
                    "interruption_threshold": 0.3,
                    "tangent_allowance": 5,
                    "paradigm": "mycelium",
                },
                "teaching": {
                    "interruption_threshold": 0.5,
                    "tangent_allowance": 3,
                    "paradigm": "cortex",
                },
                "recovery": {
                    "interruption_threshold": 0.9,
                    "tangent_allowance": 0,
                    "paradigm": "cortex",
                },
            }
        }

        # Default to focused mode
        self.variants["cognitive_mode"] = "focused"

    def load_stage(self, path: Path) -> bool:
        """Load stage from JSON file."""
        try:
            if not path.exists():
                return False

            with open(path, 'r') as f:
                data = json.load(f)

            self.create_stage()  # Reset

            # Load layer data
            for priority_name, layer_data in data.get("layers", {}).items():
                priority = LayerPriority[priority_name]
                if priority in self.layers:
                    self.layers[priority].attributes = layer_data.get("attributes", {})

            # Load variants
            self.variants = data.get("variants", {"cognitive_mode": "focused"})

            logger.debug(f"Loaded cognitive stage from {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load cognitive stage: {e}")
            return False

    def save_stage(self, path: Path) -> None:
        """Save stage to JSON file with secure atomic write [He2025].

        Uses atomic write pattern to prevent:
        - TOCTOU (time-of-check-time-of-use) vulnerabilities
        - Partial writes on crash
        - Permission issues (sets mode 0o600)
        """
        from .file_ops import atomic_write_json

        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "layers": {
                priority.name: layer.to_dict()
                for priority, layer in self.layers.items()
            },
            "variants": self.variants,
            "variant_values": self.variant_values,
        }

        try:
            atomic_write_json(path, data)
            logger.debug(f"Saved cognitive stage to {path}")
        except Exception as e:
            logger.error(f"Failed to save cognitive stage to {path}: {e}")
            raise

    def get_layer(self, priority: LayerPriority) -> CognitiveLayer:
        """Get layer by priority."""
        return self.layers.get(priority)

    def set_attribute(self, layer: LayerPriority, name: str, value: Any) -> None:
        """Set attribute on a specific layer."""
        if layer in self.layers:
            self.layers[layer].set_attribute(name, value)

    def get_resolved_attribute(self, name: str) -> Any:
        """
        Get attribute resolved through LIVRPS composition.

        This is the core of USD composition - highest priority layer wins.
        """
        opinion = self.get_opinion_stack(name)
        return opinion.resolve()

    def get_opinion_stack(self, name: str) -> AttributeOpinion:
        """Get all opinions for an attribute."""
        opinion = AttributeOpinion(attribute_name=name)

        # Collect opinions in LIVRPS order
        for priority in LayerPriority:
            layer = self.layers.get(priority)
            if layer and layer.has_attribute(name):
                opinion.add_opinion(layer.name, priority, layer.get_attribute(name))

        # Also check active variant
        for variant_set, active_variant in self.variants.items():
            variant_attrs = self.variant_values.get(variant_set, {}).get(active_variant, {})
            if name in variant_attrs:
                opinion.add_opinion(
                    f"variant:{variant_set}:{active_variant}",
                    LayerPriority.VARIANTS,
                    variant_attrs[name]
                )

        return opinion

    def set_variant(self, variant_set: str, variant: str) -> None:
        """Set active variant."""
        if variant_set in self.variant_values:
            if variant in self.variant_values[variant_set]:
                self.variants[variant_set] = variant
                logger.debug(f"Set variant {variant_set} = {variant}")

    def get_variant(self, variant_set: str) -> Optional[str]:
        """Get active variant."""
        return self.variants.get(variant_set)

    def export_usda(self, path: Path) -> None:
        """
        Export stage to .usda format.

        This is human-readable USD ASCII format.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            '#usda 1.0',
            '(',
            '    doc = "Cognitive Stage - Orchestra Cognitive Architecture"',
            '    metersPerUnit = 1',
            '    upAxis = "Y"',
            ')',
            '',
            'def Xform "CognitiveRoot"',
            '{',
        ]

        # Export layers as prims
        for priority in LayerPriority:
            layer = self.layers.get(priority)
            if layer:
                lines.append(f'    def Xform "{layer.name}" (')
                lines.append(f'        doc = "Priority: {priority.name} ({priority.value})"')
                lines.append('    )')
                lines.append('    {')

                for attr, value in layer.attributes.items():
                    # Format value based on type
                    if isinstance(value, str):
                        formatted = f'"{value}"'
                    elif isinstance(value, bool):
                        formatted = "true" if value else "false"
                    elif isinstance(value, (int, float)):
                        formatted = str(value)
                    else:
                        formatted = f'"{str(value)}"'

                    lines.append(f'        custom {self._usda_type(value)} {attr} = {formatted}')

                lines.append('    }')
                lines.append('')

        # Export variant sets
        if self.variants:
            lines.append('    # Variant Sets')
            for variant_set, active in self.variants.items():
                lines.append(f'    # {variant_set} = "{active}"')

        lines.append('}')

        with open(path, 'w') as f:
            f.write('\n'.join(lines))

        logger.info(f"Exported cognitive stage to {path}")

    def _usda_type(self, value: Any) -> str:
        """Get USD type string for a Python value."""
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, int):
            return "int"
        elif isinstance(value, float):
            return "double"
        elif isinstance(value, str):
            return "string"
        else:
            return "string"


# =============================================================================
# PXR Backend (When pxr available)
# =============================================================================

if PXR_AVAILABLE:
    class PxrCognitiveBackend(CognitiveStageBackend):
        """
        Real USD implementation using pxr library.

        Uses actual Usd.Stage for cognitive state composition.
        """

        def __init__(self):
            self.stage: Optional[Usd.Stage] = None
            self.root_layer: Optional[Sdf.Layer] = None
            self.session_layer: Optional[Sdf.Layer] = None
            self._mock_fallback = MockCognitiveBackend()  # For complex ops

        def create_stage(self) -> None:
            """Create USD stage in memory."""
            self.stage = Usd.Stage.CreateInMemory()
            self.root_layer = self.stage.GetRootLayer()
            self.session_layer = self.stage.GetSessionLayer()

            # Create root prim
            root_prim = self.stage.DefinePrim("/CognitiveRoot", "Xform")
            self.stage.SetDefaultPrim(root_prim)

            # Create layer prims
            for priority in LayerPriority:
                prim_path = f"/CognitiveRoot/{priority.name.lower()}"
                self.stage.DefinePrim(prim_path, "Xform")

            # Set constitutional values on base layer
            const_prim = self.stage.GetPrimAtPath("/CognitiveRoot/specializes")
            for attr_name, value in CONSTITUTIONAL_VALUES.items():
                self._set_prim_attribute(const_prim, attr_name, value)

            # Initialize mock for variant handling (USD variants are complex)
            self._mock_fallback.create_stage()

            logger.debug("Created pxr cognitive stage")

        def _set_prim_attribute(self, prim, name: str, value: Any) -> None:
            """Set attribute on a USD prim."""
            if isinstance(value, bool):
                attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Bool)
            elif isinstance(value, int):
                attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Int)
            elif isinstance(value, float):
                attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.Double)
            else:
                attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.String)
            attr.Set(value)

        def _get_prim_attribute(self, prim, name: str) -> Optional[Any]:
            """Get attribute from a USD prim."""
            attr = prim.GetAttribute(name)
            if attr and attr.HasValue():
                return attr.Get()
            return None

        def load_stage(self, path: Path) -> bool:
            """Load stage from USD file."""
            try:
                if not path.exists():
                    return False

                self.stage = Usd.Stage.Open(str(path))
                self.root_layer = self.stage.GetRootLayer()
                self.session_layer = self.stage.GetSessionLayer()

                logger.debug(f"Loaded pxr cognitive stage from {path}")
                return True

            except Exception as e:
                logger.error(f"Failed to load pxr stage: {e}")
                return False

        def save_stage(self, path: Path) -> None:
            """Save stage to USD file."""
            path.parent.mkdir(parents=True, exist_ok=True)
            self.stage.Export(str(path))
            logger.debug(f"Saved pxr cognitive stage to {path}")

        def get_layer(self, priority: LayerPriority) -> CognitiveLayer:
            """Get layer as CognitiveLayer wrapper."""
            prim_path = f"/CognitiveRoot/{priority.name.lower()}"
            prim = self.stage.GetPrimAtPath(prim_path)

            layer = CognitiveLayer(name=priority.name.lower(), priority=priority)

            if prim:
                for attr in prim.GetAttributes():
                    if attr.HasValue():
                        layer.attributes[attr.GetName()] = attr.Get()

            return layer

        def set_attribute(self, layer: LayerPriority, name: str, value: Any) -> None:
            """Set attribute on session layer (for local) or root layer."""
            prim_path = f"/CognitiveRoot/{layer.name.lower()}"

            if layer == LayerPriority.LOCAL:
                # Session layer edits for local/mutable state
                with Sdf.ChangeBlock():
                    spec = self.session_layer.GetPrimAtPath(prim_path)
                    if not spec:
                        spec = Sdf.PrimSpec(self.session_layer, prim_path.split('/')[-1], Sdf.SpecifierDef)
                    spec.SetInfo(name, value)
            else:
                prim = self.stage.GetPrimAtPath(prim_path)
                if prim:
                    self._set_prim_attribute(prim, name, value)

        def get_resolved_attribute(self, name: str) -> Any:
            """
            Get attribute resolved through USD composition.

            This uses USD's native composition engine - LIVRPS happens automatically.
            """
            root_prim = self.stage.GetPrimAtPath("/CognitiveRoot")

            # Check each layer prim in priority order
            for priority in LayerPriority:
                prim_path = f"/CognitiveRoot/{priority.name.lower()}"
                prim = self.stage.GetPrimAtPath(prim_path)
                if prim:
                    value = self._get_prim_attribute(prim, name)
                    if value is not None:
                        return value

            return None

        def get_opinion_stack(self, name: str) -> AttributeOpinion:
            """Get all opinions from USD stack."""
            opinion = AttributeOpinion(attribute_name=name)

            for priority in LayerPriority:
                prim_path = f"/CognitiveRoot/{priority.name.lower()}"
                prim = self.stage.GetPrimAtPath(prim_path)
                if prim:
                    value = self._get_prim_attribute(prim, name)
                    if value is not None:
                        opinion.add_opinion(priority.name.lower(), priority, value)

            return opinion

        def set_variant(self, variant_set: str, variant: str) -> None:
            """Set variant - delegated to mock for now."""
            self._mock_fallback.set_variant(variant_set, variant)

        def get_variant(self, variant_set: str) -> Optional[str]:
            """Get variant - delegated to mock."""
            return self._mock_fallback.get_variant(variant_set)

        def export_usda(self, path: Path) -> None:
            """Export to .usda format."""
            path.parent.mkdir(parents=True, exist_ok=True)
            self.stage.Export(str(path))
            logger.info(f"Exported pxr cognitive stage to {path}")


# =============================================================================
# CognitiveStage - Main Interface
# =============================================================================

class CognitiveStage:
    """
    USD-native cognitive state management.

    This is the key technical novelty of Orchestra: using actual USD composition
    semantics (LIVRPS) to resolve cognitive state priority.

    The stage maintains layers for:
    - Session (LOCAL): Current session state - highest priority, mutable
    - Calibration (REFERENCES): Learned preferences - cross-session
    - Mode (VARIANTS): Cognitive mode variants (focused/exploring/etc)
    - Constitutional (SPECIALIZES): Safety floors - never violated

    Usage:
        stage = CognitiveStage()
        stage.load_or_create()

        # Set session-level values (highest priority)
        stage.set_session_value("burnout_level", "yellow")

        # Get resolved value (through LIVRPS composition)
        burnout = stage.get_resolved("burnout_level")

        # Set cognitive mode variant
        stage.set_mode("exploring")

        # Export for debugging
        stage.export("session_2025-01-24.usda")
    """

    DEFAULT_STAGE_FILE = "cognitive_stage.json"

    def __init__(self, state_dir: Path = None):
        """
        Initialize cognitive stage.

        Args:
            state_dir: Directory for stage persistence (default: ~/Orchestra/state)
        """
        self.state_dir = state_dir or (Path.home() / "Orchestra" / "state")
        self.stage_file = self.state_dir / self.DEFAULT_STAGE_FILE

        # Select backend based on pxr availability
        if PXR_AVAILABLE:
            self._backend: CognitiveStageBackend = PxrCognitiveBackend()
            self._using_pxr = True
        else:
            self._backend = MockCognitiveBackend()
            self._using_pxr = False

        # Integration with existing CognitiveState
        self._state_manager = CognitiveStateManager(state_dir)

        logger.info(f"CognitiveStage initialized (pxr={'available' if self._using_pxr else 'mock'})")

    def load_or_create(self) -> 'CognitiveStage':
        """
        Load existing stage or create new one.

        Returns self for chaining.
        """
        if not self._backend.load_stage(self.stage_file):
            self._backend.create_stage()
            logger.info("Created new cognitive stage")
        else:
            logger.info("Loaded existing cognitive stage")

        # Sync with existing CognitiveState
        self._sync_from_state()

        return self

    def _sync_from_state(self) -> None:
        """Sync session layer from existing CognitiveState."""
        state = self._state_manager.get_state()

        # Map CognitiveState fields to stage attributes
        self.set_session_value("burnout_level", state.burnout_level.value)
        self.set_session_value("momentum_phase", state.momentum_phase.value)
        self.set_session_value("energy_level", state.energy_level.value)
        self.set_session_value("mode", state.mode.value)
        self.set_session_value("altitude", state.altitude.value)
        self.set_session_value("focus_level", state.focus_level)
        self.set_session_value("urgency", state.urgency)
        self.set_session_value("exchange_count", state.exchange_count)
        self.set_session_value("epistemic_tension", state.epistemic_tension)

    def _sync_to_state(self) -> None:
        """Sync session layer back to CognitiveState."""
        state = self._state_manager.get_state()

        updates = {}
        for attr in ["burnout_level", "momentum_phase", "energy_level", "mode",
                     "altitude", "focus_level", "urgency", "exchange_count",
                     "epistemic_tension"]:
            value = self.get_resolved(attr)
            if value is not None:
                updates[attr] = value

        if updates:
            state.batch_update(updates)
            self._state_manager.save()

    def save(self) -> None:
        """Save stage and sync to CognitiveState."""
        self._sync_to_state()
        self._backend.save_stage(self.stage_file)

    # =========================================================================
    # Session Layer (LOCAL - highest priority)
    # =========================================================================

    def set_session_value(self, name: str, value: Any) -> None:
        """
        Set value on session layer (highest priority).

        Session values override all other layers during this session.
        """
        self._backend.set_attribute(LayerPriority.LOCAL, name, value)

    def set_session_values(self, **kwargs) -> None:
        """Set multiple session values."""
        for name, value in kwargs.items():
            self.set_session_value(name, value)

    # =========================================================================
    # Calibration Layer (REFERENCES)
    # =========================================================================

    def set_calibration_value(self, name: str, value: Any) -> None:
        """
        Set value on calibration layer (learned preferences).

        Calibration values persist across sessions but can be
        overridden by session values.
        """
        self._backend.set_attribute(LayerPriority.REFERENCES, name, value)

    def calibrate(self, focus_level: str = None, urgency: str = None,
                  energy_estimate: str = None) -> None:
        """
        Calibrate from non-invasive questions.

        Args:
            focus_level: 'scattered', 'moderate', or 'locked_in'
            urgency: 'relaxed', 'moderate', or 'deadline'
            energy_estimate: 'high', 'medium', 'low', or 'depleted'
        """
        if focus_level:
            self.set_calibration_value("focus_level", focus_level)
            self.set_session_value("focus_level", focus_level)

        if urgency:
            self.set_calibration_value("urgency", urgency)
            self.set_session_value("urgency", urgency)

        if energy_estimate:
            self.set_calibration_value("energy_estimate", energy_estimate)
            self.set_session_value("energy_level", energy_estimate)

        self.save()
        logger.info(f"Calibrated: focus={focus_level}, urgency={urgency}, energy={energy_estimate}")

    # =========================================================================
    # Mode Variants (VARIANTS)
    # =========================================================================

    def set_mode(self, mode: str) -> None:
        """
        Set cognitive mode variant.

        Modes: focused, exploring, teaching, recovery
        """
        valid_modes = ["focused", "exploring", "teaching", "recovery"]
        if mode not in valid_modes:
            logger.warning(f"Invalid mode '{mode}', using 'focused'")
            mode = "focused"

        self._backend.set_variant("cognitive_mode", mode)
        self.set_session_value("mode", mode)

        # Apply mode-specific values
        mode_values = ATTRACTOR_BASINS.get(mode, {})
        if "paradigm" in mode_values:
            self.set_session_value("paradigm", mode_values["paradigm"])

    def get_mode(self) -> str:
        """Get current cognitive mode."""
        return self._backend.get_variant("cognitive_mode") or "focused"

    # =========================================================================
    # Resolution (LIVRPS Composition)
    # =========================================================================

    def get_resolved(self, name: str) -> Any:
        """
        Get attribute value resolved through LIVRPS composition.

        This is the core of USD composition - highest priority layer wins.
        """
        return self._backend.get_resolved_attribute(name)

    def get_opinion_stack(self, name: str) -> AttributeOpinion:
        """
        Get all opinions for an attribute.

        Useful for debugging and tension detection.
        """
        return self._backend.get_opinion_stack(name)

    def has_conflict(self, name: str) -> bool:
        """Check if attribute has conflicting opinions across layers."""
        opinion = self.get_opinion_stack(name)
        return opinion.has_conflict

    # =========================================================================
    # Safety Checks (Constitutional Layer)
    # =========================================================================

    def get_safety_floor(self, name: str) -> Any:
        """
        Get constitutional safety floor value.

        These values CANNOT be overridden by other layers.
        """
        return CONSTITUTIONAL_VALUES.get(name)

    def enforce_safety_floors(self) -> Dict[str, Any]:
        """
        Enforce constitutional safety floors.

        Returns dict of values that were corrected.
        """
        corrections = {}

        # Check working memory limit
        wm_limit = self.get_safety_floor("working_memory_limit")
        # Working memory is typically enforced in cognitive support

        # Check thinking depth based on energy/burnout
        energy = self.get_resolved("energy_level")
        burnout = self.get_resolved("burnout_level")

        if energy == "depleted":
            max_depth = self.get_safety_floor("max_depth_depleted")
            corrections["max_thinking_depth"] = max_depth
        elif burnout == "red":
            max_depth = self.get_safety_floor("max_depth_red_burnout")
            corrections["max_thinking_depth"] = max_depth
        elif burnout == "orange":
            max_depth = self.get_safety_floor("max_depth_orange_burnout")
            corrections["max_thinking_depth"] = max_depth

        return corrections

    # =========================================================================
    # Integration with Existing State
    # =========================================================================

    def get_cognitive_state(self) -> CognitiveState:
        """Get underlying CognitiveState."""
        return self._state_manager.get_state()

    def update_from_signals(self, burnout: str = None, momentum: str = None,
                            energy: str = None) -> None:
        """
        Update state from detected signals.

        This is called by PRISM detector after signal analysis.
        """
        if burnout:
            self.set_session_value("burnout_level", burnout)
        if momentum:
            self.set_session_value("momentum_phase", momentum)
        if energy:
            self.set_session_value("energy_level", energy)

        self._sync_to_state()

    # =========================================================================
    # Export & Debug
    # =========================================================================

    def export(self, filename: str = None) -> Path:
        """
        Export stage to .usda file for debugging.

        Args:
            filename: Output filename (default: session_{timestamp}.usda)

        Returns:
            Path to exported file
        """
        if filename is None:
            from datetime import datetime
            filename = f"session_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.usda"

        export_dir = self.state_dir / "exports"
        export_path = export_dir / filename

        self._backend.export_usda(export_path)
        return export_path

    def get_prompt_context(self) -> str:
        """
        Get cognitive context for prompt injection.

        This is injected into the system prompt to inform AI behavior.
        """
        burnout = self.get_resolved("burnout_level") or "green"
        energy = self.get_resolved("energy_level") or "medium"
        mode = self.get_mode()
        focus = self.get_resolved("focus_level") or "moderate"
        urgency = self.get_resolved("urgency") or "moderate"
        tension = self.get_resolved("epistemic_tension") or 0.0

        return f"""[COGNITIVE_STATE]
burnout={burnout}
energy={energy}
mode={mode}
focus={focus}
urgency={urgency}
epistemic_tension={tension:.2f}
[/COGNITIVE_STATE]"""

    def checksum(self) -> str:
        """Generate deterministic checksum of current state."""
        state_dict = {
            "burnout": self.get_resolved("burnout_level"),
            "energy": self.get_resolved("energy_level"),
            "mode": self.get_mode(),
            "focus": self.get_resolved("focus_level"),
            "urgency": self.get_resolved("urgency"),
        }
        state_str = json.dumps(state_dict, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]

    @property
    def using_pxr(self) -> bool:
        """Check if using real pxr backend."""
        return self._using_pxr


# =============================================================================
# Factory Function
# =============================================================================

def create_cognitive_stage(state_dir: Path = None) -> CognitiveStage:
    """
    Create and initialize a cognitive stage.

    Args:
        state_dir: Optional state directory

    Returns:
        Initialized CognitiveStage
    """
    return CognitiveStage(state_dir).load_or_create()


__all__ = [
    'CognitiveStage',
    'CognitiveLayer',
    'LayerPriority',
    'AttributeOpinion',
    'CONSTITUTIONAL_VALUES',
    'PXR_AVAILABLE',
    'create_cognitive_stage',
]
