"""
Cognitive State Manager
=======================

Extended state management with LIVRPS composition and schema validation.

Determinism:
- All state transitions are deterministic
- Float comparisons use round(value, 6)
- State serialization uses sorted keys
- No runtime variation in state operations

Reference:
    He, Horace and Thinking Machines Lab,
    "Defeating Nondeterminism in LLM Inference", Sep 2025.
    See also: docs/HE2025_DETERMINISM_ADDENDUM.md
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json
import uuid

from otto.core.livrps import (
    LIVRPSResolver,
    Layer,
    LayerType,
    CompositionResult,
    COGNITIVE_VARIANTS,
    kahan_sum,
    round_for_comparison,
)


# =============================================================================
# Enums for State Values
# =============================================================================

class BurnoutLevel(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


class MomentumPhase(Enum):
    COLD_START = "cold_start"
    BUILDING = "building"
    ROLLING = "rolling"
    PEAK = "peak"
    CRASHED = "crashed"


class EnergyLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEPLETED = "depleted"


class CognitiveMode(Enum):
    FOCUSED = "focused"
    EXPLORING = "exploring"
    TEACHING = "teaching"
    RECOVERY = "recovery"


class Paradigm(Enum):
    CORTEX = "cortex"
    MYCELIUM = "mycelium"


class DetectedState(Enum):
    FOCUSED = "focused"
    EXPLORING = "exploring"
    STUCK = "stuck"
    OVERWHELMED = "overwhelmed"
    FRUSTRATED = "frustrated"
    HYPERFOCUSED = "hyperfocused"
    DEPLETED = "depleted"


class SourceMode(Enum):
    """Grounding source mode (v6.0)."""
    LEARN = "learn"
    ACCESS = "access"
    HYBRID = "hybrid"


# =============================================================================
# Cognitive State Dataclass
# =============================================================================

@dataclass
class CognitiveState:
    """
    Complete cognitive state schema (v7.1.0).

    62 fields tracking session, grounding, BCM, and batch invariance state.

    Determinism:
    - All enum fields use fixed vocabularies
    - Float fields use round(6) for comparison
    - Serialization uses sorted keys
    """

    # -------------------------------------------------------------------------
    # Core State (from v5.0)
    # -------------------------------------------------------------------------
    active_mode: str = "focused"
    active_paradigm: str = "cortex"
    detected_state: str = "focused"
    current_altitude: int = 30000
    energy_level: str = "medium"
    burnout_level: str = "green"
    momentum_phase: str = "cold_start"
    tangent_budget: int = 5
    convergence_attractor: str = "focused"
    epistemic_tension: float = 0.0
    decision_mode: str = "work"

    # -------------------------------------------------------------------------
    # Session Tracking
    # -------------------------------------------------------------------------
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_start_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    session_duration: int = 0
    exchange_count: int = 0
    rapid_exchange_count: int = 0
    tasks_completed: int = 0
    stable_exchanges: int = 0

    # -------------------------------------------------------------------------
    # Grounding State (v6.0.0)
    # -------------------------------------------------------------------------
    grounding_mode: str = "learn"
    oracle_cache_age: int = 0
    evidence_chain_length: int = 0
    hallucination_score: float = 0.0
    last_oracle_latency: int = 0
    grounding_budget: int = 5
    active_oracles: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------------
    # BCM State (v7.0.0)
    # -------------------------------------------------------------------------
    bcm_trail_version: str = "7.0.0"
    bcm_expert_confidence: Dict[str, float] = field(default_factory=dict)
    bcm_plasticity_active: bool = False
    bcm_plasticity_sigma: float = 0.0
    bcm_last_update: str = ""
    bcm_plasticity_trigger: Optional[str] = None
    bcm_trail_checksum: str = ""

    # -------------------------------------------------------------------------
    # Batch Invariance State (v7.1.0)
    # -------------------------------------------------------------------------
    cognitive_tile_size: int = 32  # FIXED, never changes
    determinism_mode: str = "strict"
    aggregation_strategy: str = "max"
    aggregation_order: str = "id_ascending"
    template_match_order: str = "lexicographic"
    deterministic_hash: str = ""
    hash_seed: int = 0xCAFEBABE
    conflict_resolution: str = "newest_wins"

    # -------------------------------------------------------------------------
    # Temporal Coherence (v7.1.0)
    # -------------------------------------------------------------------------
    temporal_epoch: int = 0
    schema_version: str = "7.1.0"
    template_version: str = ""
    migration_path: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------------
    # Session Lifecycle (v7.1.0)
    # -------------------------------------------------------------------------
    session_state: str = "initializing"
    parent_session_id: str = ""
    last_checkpoint_hash: str = ""
    session_goal: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary.

        Determinism: Keys sorted for deterministic serialization.
        """
        data = asdict(self)
        # Sort nested dicts too
        if "bcm_expert_confidence" in data:
            data["bcm_expert_confidence"] = {
                k: data["bcm_expert_confidence"][k]
                for k in sorted(data["bcm_expert_confidence"].keys())
            }
        return {k: data[k] for k in sorted(data.keys())}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CognitiveState":
        """Deserialize from dictionary."""
        # Filter to known fields only
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def compute_hash(self) -> str:
        """
        Compute deterministic hash of state.

        Determinism: Uses sorted serialization.
        """
        serialized = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:12]

    def validate(self) -> List[str]:
        """
        Validate state against schema constraints.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate enums
        valid_modes = {"focused", "exploring", "teaching", "recovery"}
        if self.active_mode not in valid_modes:
            errors.append(f"Invalid active_mode: {self.active_mode}")

        valid_paradigms = {"cortex", "mycelium"}
        if self.active_paradigm not in valid_paradigms:
            errors.append(f"Invalid active_paradigm: {self.active_paradigm}")

        valid_burnout = {"green", "yellow", "orange", "red"}
        if self.burnout_level not in valid_burnout:
            errors.append(f"Invalid burnout_level: {self.burnout_level}")

        valid_momentum = {"cold_start", "building", "rolling", "peak", "crashed"}
        if self.momentum_phase not in valid_momentum:
            errors.append(f"Invalid momentum_phase: {self.momentum_phase}")

        valid_energy = {"high", "medium", "low", "depleted"}
        if self.energy_level not in valid_energy:
            errors.append(f"Invalid energy_level: {self.energy_level}")

        # Validate ranges
        if not (0.0 <= self.epistemic_tension <= 1.0):
            errors.append(f"epistemic_tension out of range: {self.epistemic_tension}")

        if self.tangent_budget < 0:
            errors.append(f"tangent_budget cannot be negative: {self.tangent_budget}")

        if self.cognitive_tile_size != 32:
            errors.append(f"cognitive_tile_size must be 32: {self.cognitive_tile_size}")

        return errors


# =============================================================================
# Constitutional Defaults (from constitutional.usda)
# =============================================================================

CONSTITUTIONAL_DEFAULTS = {
    # Cognitive limits
    "working_memory_limit": 3,
    "body_check_interval": 20,
    "tangent_budget_default": 5,
    "max_visible_subtasks": 5,

    # Agent orchestration
    "max_agent_depth": 3,
    "max_parallel_agents": 3,

    # Thinking depth gates
    "max_depth_depleted": "minimal",
    "max_depth_low_energy": "standard",
    "max_depth_red_burnout": "minimal",
    "max_depth_orange_burnout": "standard",

    # Safety floors
    "safety_floor_validator": 0.10,
    "safety_floor_restorer": 0.05,
    "safety_floor_scaffolder": 0.05,

    # Intervention thresholds
    "emotional_intervention_threshold": 0.5,
    "burnout_escalation_threshold": 0.7,
    "tension_surfacing_threshold": 0.3,

    # Convergence
    "convergence_epsilon": 0.1,
    "convergence_stable_exchanges": 3,
    "tension_increase_on_switch": 0.3,
    "tension_decrease_when_stable": 0.1,

    # Time estimates
    "minutes_per_exchange": 4.5,
    "break_reminder_minutes": 90,
}


# =============================================================================
# Cognitive State Manager
# =============================================================================

class CognitiveStateManager:
    """
    Manages cognitive state with LIVRPS composition.

    Integrates:
    - LIVRPS layer resolution
    - Storage persistence
    - Schema validation
    - Deterministic state transitions

    Example:
        manager = get_state_manager()

        # Update session state (LOCAL layer)
        manager.update_session("burnout_level", "yellow")

        # Get resolved state
        state = manager.get_state()
        print(state.burnout_level)  # "yellow"

        # Save to disk
        manager.save()
    """

    STATE_FILE = "state/cognitive_state.json"
    CALIBRATION_FILE = "calibration/overrides.json"

    def __init__(self, storage=None):
        """
        Initialize the state manager.

        Args:
            storage: Optional storage provider (uses default if None)
        """
        self._storage = storage
        self._resolver = LIVRPSResolver()
        self._state: Optional[CognitiveState] = None
        self._dirty = False

        # Initialize layers
        self._init_layers()

    def _get_storage(self):
        """Lazy-load storage to avoid circular imports."""
        if self._storage is None:
            try:
                from otto.storage import get_storage
                self._storage = get_storage()
            except ImportError:
                # Fallback for testing without storage
                self._storage = None
        return self._storage

    def _init_layers(self):
        """Initialize LIVRPS layers with defaults."""
        # S (Specializes) - Constitutional defaults
        self._resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            CONSTITUTIONAL_DEFAULTS.copy(),
            name="constitutional"
        ))

        # P (Payloads) - Empty, populated when domain loaded
        self._resolver.add_layer(Layer(
            LayerType.PAYLOADS,
            {},
            name="domain"
        ))

        # R (References) - Calibration, loaded from storage
        calibration = self._load_calibration()
        self._resolver.add_layer(Layer(
            LayerType.REFERENCES,
            calibration,
            name="calibration"
        ))

        # V (Variants) - Default to focused mode
        self._resolver.set_variant("focused", COGNITIVE_VARIANTS["focused"])

        # I (Inherits) - Empty, populated by parent agent
        self._resolver.add_layer(Layer(
            LayerType.INHERITS,
            {},
            name="inherited"
        ))

        # L (Local) - Session state, loaded from storage
        session = self._load_session()
        self._resolver.add_layer(Layer(
            LayerType.LOCAL,
            session,
            name="session"
        ))

    def _load_calibration(self) -> Dict[str, Any]:
        """Load calibration data from storage."""
        storage = self._get_storage()
        if storage:
            return storage.read_json(self.CALIBRATION_FILE, root_type="otto", default={})
        return {}

    def _load_session(self) -> Dict[str, Any]:
        """Load session state from storage."""
        storage = self._get_storage()
        if storage:
            return storage.read_json(self.STATE_FILE, root_type="otto", default={})
        return {}

    def get_state(self) -> CognitiveState:
        """
        Get the current resolved cognitive state.

        Returns:
            CognitiveState with all LIVRPS layers resolved
        """
        if self._state is None or self._dirty:
            result = self._resolver.resolve()
            self._state = CognitiveState.from_dict(result.resolved)
            self._dirty = False
        return self._state

    def get_composition_result(self) -> CompositionResult:
        """
        Get the full composition result with provenance.

        Returns:
            CompositionResult with sources and override information
        """
        return self._resolver.resolve()

    def update_session(self, key: str, value: Any) -> None:
        """
        Update a value in the session (LOCAL) layer.

        Args:
            key: Attribute to update
            value: New value
        """
        self._resolver.update_local(key, value)
        self._dirty = True

    def update_calibration(self, key: str, value: Any) -> None:
        """
        Update a value in the calibration (REFERENCES) layer.

        Args:
            key: Attribute to update
            value: New value
        """
        self._resolver.update_references(key, value)
        self._dirty = True

    def set_mode(self, mode: str) -> None:
        """
        Set the cognitive mode variant.

        Args:
            mode: One of "focused", "exploring", "teaching", "recovery"
        """
        if mode not in COGNITIVE_VARIANTS:
            raise ValueError(f"Unknown mode: {mode}")
        self._resolver.set_variant(mode, COGNITIVE_VARIANTS[mode])
        self.update_session("active_mode", mode)

    def set_inherited(self, context: Dict[str, Any]) -> None:
        """
        Set inherited context from parent agent.

        Args:
            context: Context from parent (burnout_level, goal, etc.)
        """
        self._resolver.clear_layer_type(LayerType.INHERITS)
        self._resolver.add_layer(Layer(
            LayerType.INHERITS,
            context,
            name="inherited"
        ))
        self._dirty = True

    def load_payload(self, payload_name: str, payload_data: Dict[str, Any]) -> None:
        """
        Load a domain payload.

        Args:
            payload_name: Name of the payload (e.g., "vfx", "webdev")
            payload_data: Domain-specific settings
        """
        self._resolver.clear_layer_type(LayerType.PAYLOADS)
        self._resolver.add_layer(Layer(
            LayerType.PAYLOADS,
            payload_data,
            name=payload_name
        ))
        self._dirty = True

    def save(self) -> bool:
        """
        Save state to storage.

        Saves:
        - Session state to STATE_FILE
        - Calibration to CALIBRATION_FILE (if changed)

        Returns:
            True if successful
        """
        storage = self._get_storage()
        if not storage:
            return False

        # Save session state (LOCAL layer)
        local_layers = self._resolver.get_layers(LayerType.LOCAL)
        if local_layers:
            session_data = local_layers[0].data.copy()
            session_data["_saved_at"] = datetime.utcnow().isoformat()
            storage.write_json(self.STATE_FILE, session_data, root_type="otto", backup=True)

        # Save calibration (REFERENCES layer)
        ref_layers = self._resolver.get_layers(LayerType.REFERENCES)
        if ref_layers:
            cal_data = ref_layers[0].data.copy()
            if cal_data:  # Only save if there's calibration data
                storage.write_json(self.CALIBRATION_FILE, cal_data, root_type="otto", backup=True)

        return True

    def reset_session(self) -> None:
        """
        Reset session state while preserving calibration.

        Called when starting a new session or after staleness timeout.
        """
        # Clear LOCAL layer
        self._resolver.clear_layer_type(LayerType.LOCAL)
        self._resolver.add_layer(Layer(
            LayerType.LOCAL,
            {
                "session_id": str(uuid.uuid4()),
                "session_start_time": datetime.utcnow().isoformat(),
                "session_state": "active",
                "exchange_count": 0,
                "momentum_phase": "cold_start",
                "tangent_budget": CONSTITUTIONAL_DEFAULTS["tangent_budget_default"],
            },
            name="session"
        ))

        # Reset variant to focused
        self._resolver.set_variant("focused", COGNITIVE_VARIANTS["focused"])
        self._dirty = True

    def increment_exchange(self) -> int:
        """
        Increment the exchange count.

        Returns:
            New exchange count
        """
        state = self.get_state()
        new_count = state.exchange_count + 1
        self.update_session("exchange_count", new_count)
        return new_count

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize manager state.

        Determinism: Deterministic serialization.
        """
        return {
            "resolver": self._resolver.to_dict(),
            "state": self.get_state().to_dict(),
        }


# =============================================================================
# Global Singleton
# =============================================================================

_manager: Optional[CognitiveStateManager] = None


def get_state_manager() -> CognitiveStateManager:
    """
    Get the global state manager instance.

    Creates the manager on first call.

    Returns:
        CognitiveStateManager instance
    """
    global _manager
    if _manager is None:
        _manager = CognitiveStateManager()
    return _manager


def reset_state_manager() -> None:
    """
    Reset the global state manager.

    Used for testing to ensure clean state.
    """
    global _manager
    _manager = None
