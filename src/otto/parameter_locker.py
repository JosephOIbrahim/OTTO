"""
Parameter Locker
================

Locks cognitive parameters before generation for deterministic behavior.

Features:
- MAX3 bounded reflection (max 3 iterations)
- Cognitive safety gating (state overrides user requests)
- Deterministic checksum computation
- Parameter freezing for batch-invariance

ThinkingMachines [He2025] Compliance:
- Parameters LOCKED before generation
- Same inputs = same locked params = same checksum
- No mid-generation parameter changes

Cognitive Safety Gating (from CLAUDE.md):
- depleted → minimal thinking
- low energy → standard thinking
- RED/ORANGE burnout → standard thinking
- high energy → ultradeep allowed (if requested)
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
import logging

from .expert_router import Expert, RoutingResult
from .cognitive_state import BurnoutLevel, EnergyLevel, Altitude

logger = logging.getLogger(__name__)


# =============================================================================
# Thinking Depths
# =============================================================================

class ThinkDepth(Enum):
    """Thinking depth levels with token budgets."""
    MINIMAL = "minimal"      # 1K tokens
    STANDARD = "standard"    # 8K tokens
    DEEP = "deep"            # 32K tokens
    ULTRADEEP = "ultradeep"  # 128K tokens (Opus only)


# Depth budgets
DEPTH_BUDGETS = {
    ThinkDepth.MINIMAL: 1_000,
    ThinkDepth.STANDARD: 8_000,
    ThinkDepth.DEEP: 32_000,
    ThinkDepth.ULTRADEEP: 128_000
}


# =============================================================================
# Paradigms
# =============================================================================

class Paradigm(Enum):
    """Cognitive paradigms."""
    CORTEX = "Cortex"      # Hierarchical, explicit, controlled
    MYCELIUM = "Mycelium"  # Distributed, associative, emergent


# =============================================================================
# Lock Status
# =============================================================================

class LockStatus(Enum):
    """Lock status states."""
    UNLOCKED = "unlocked"
    LOCKING = "locking"
    LOCKED = "locked"


# =============================================================================
# Locked Parameters
# =============================================================================

@dataclass
class LockedParams:
    """
    Immutable locked parameters for generation.

    Once locked, these CANNOT change during generation.

    ThinkingMachines [He2025] Batch-Invariance:
    - `checksum`: Routing-only checksum (excludes reflection_iteration)
    - `session_checksum`: Full checksum including iteration (for debugging)
    - Same routing params → same checksum regardless of reflection count
    """
    expert: str
    paradigm: str
    altitude: str
    think_depth: str
    checksum: str = ""
    session_checksum: str = ""  # Includes reflection_iteration for debugging
    reflection_iteration: int = 0
    max_reflections: int = 3  # MAX3

    def __post_init__(self):
        """Compute deterministic checksums."""
        if not self.checksum:
            self.checksum = self._compute_checksum()
        if not self.session_checksum:
            self.session_checksum = self._compute_session_checksum()

    def _compute_checksum(self) -> str:
        """
        Compute deterministic checksum of ROUTING params only.

        Excludes reflection_iteration to ensure batch-invariance:
        Same routing decision → same checksum regardless of iteration.

        ThinkingMachines [He2025]: Same inputs → same outputs → same checksums
        """
        data = json.dumps({
            "expert": self.expert,
            "paradigm": self.paradigm,
            "altitude": self.altitude,
            "think_depth": self.think_depth,
            # NOTE: reflection_iteration intentionally excluded for batch-invariance
        }, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()[:6]

    def _compute_session_checksum(self) -> str:
        """
        Compute session-aware checksum including iteration.

        Used for debugging/tracing, not for batch-invariance verification.
        """
        data = json.dumps({
            "expert": self.expert,
            "paradigm": self.paradigm,
            "altitude": self.altitude,
            "think_depth": self.think_depth,
            "reflection_iteration": self.reflection_iteration
        }, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()[:6]

    def to_anchor(self) -> str:
        """
        Format as anchor string for embedding in responses.

        Format: [EXEC:{checksum}|{expert}|{paradigm}|{altitude}|{think_depth}]
        """
        return f"[EXEC:{self.checksum}|{self.expert}|{self.paradigm}|{self.altitude}|{self.think_depth}]"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for WebSocket."""
        return {
            "expert": self.expert,
            "paradigm": self.paradigm,
            "altitude": self.altitude,
            "think_depth": self.think_depth,
            "checksum": self.checksum,
            "session_checksum": self.session_checksum,
            "reflection_iteration": self.reflection_iteration,
            "max_reflections": self.max_reflections
        }

    def can_reflect(self) -> bool:
        """Check if another reflection iteration is allowed (MAX3)."""
        return self.reflection_iteration < self.max_reflections


@dataclass
class LockResult:
    """Result of parameter locking."""
    status: LockStatus
    params: LockedParams
    safety_capped: bool = False  # True if safety gating reduced depth
    original_depth: Optional[str] = None  # Depth before safety cap
    converged: bool = False  # True if early convergence detected (xi < epsilon)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "status": self.status.value,
            "params": self.params.to_dict(),
            "safety_capped": self.safety_capped,
            "original_depth": self.original_depth,
            "converged": self.converged
        }


# =============================================================================
# Parameter Locker
# =============================================================================

class ParameterLocker:
    """
    Locks cognitive parameters for deterministic generation.

    Implements:
    - MAX3 bounded reflection
    - Cognitive safety gating
    - Deterministic checksums
    - Paradigm selection based on mode
    """

    def __init__(self, max_reflections: int = 3, epsilon: float = 0.1):
        """
        Initialize locker.

        Args:
            max_reflections: Maximum reflection iterations (MAX3)
            epsilon: Convergence threshold for stopping early

        Note: reflection_count is now tracked in CognitiveState for batch-invariance.
        """
        self.max_reflections = max_reflections
        self.epsilon = epsilon
        self._current_lock: Optional[LockResult] = None

    def lock(
        self,
        routing: RoutingResult,
        burnout: BurnoutLevel,
        energy: EnergyLevel,
        altitude: Altitude,
        requested_depth: ThinkDepth = ThinkDepth.STANDARD,
        mode: str = "focused",
        epistemic_tension: float = 0.0,
        reflection_count: int = 0
    ) -> LockResult:
        """
        Lock parameters for generation.

        ThinkingMachines [He2025]: Parameters locked BEFORE generation.
        Batch-invariance: reflection_count passed from state snapshot,
        not stored as instance state.

        Args:
            routing: Result from expert router
            burnout: Current burnout level
            energy: Current energy level
            altitude: Current altitude
            requested_depth: User-requested thinking depth
            mode: Current cognitive mode (for paradigm selection)
            epistemic_tension: Current epistemic tension (for early stop)
            reflection_count: Current reflection count (from CognitiveState snapshot)

        Returns:
            LockResult with locked parameters
        """
        # =================================================================
        # STEP 1: Determine paradigm based on mode
        # =================================================================
        paradigm = self._select_paradigm(routing.expert, mode)

        # =================================================================
        # STEP 2: Apply cognitive safety gating to thinking depth
        # =================================================================
        actual_depth, safety_capped = self._apply_safety_gating(
            requested_depth, burnout, energy
        )

        # =================================================================
        # STEP 3: Check MAX3 and epsilon stopping
        # =================================================================
        converged = False
        if epistemic_tension < self.epsilon and reflection_count > 0:
            # Early convergence - signal to caller
            logger.info(f"Early convergence at xi={epistemic_tension:.2f} < epsilon={self.epsilon}")
            converged = True

        if reflection_count >= self.max_reflections:
            # MAX3 reached - force minimal depth
            actual_depth = ThinkDepth.MINIMAL
            safety_capped = True
            logger.info(f"MAX3 reached ({reflection_count}/{self.max_reflections})")

        # =================================================================
        # STEP 4: Create locked params
        # =================================================================
        params = LockedParams(
            expert=routing.expert.value,
            paradigm=paradigm.value,
            altitude=self._format_altitude(altitude),
            think_depth=actual_depth.value,
            reflection_iteration=reflection_count
        )

        result = LockResult(
            status=LockStatus.LOCKED,
            params=params,
            safety_capped=safety_capped,
            original_depth=requested_depth.value if safety_capped else None,
            converged=converged
        )

        self._current_lock = result
        # NOTE: Counter increment now handled by caller (CognitiveOrchestrator)
        # after batch_update() for batch-invariance

        logger.info(f"Locked params: {params.to_anchor()}")
        return result

    def _select_paradigm(self, expert: Expert, mode: str) -> Paradigm:
        """
        Select paradigm based on expert and mode.

        Per CLAUDE.md:
        - Default: Cortex (hierarchical, explicit)
        - Switch to Mycelium on "what if", exploring signals
        """
        # Socratic expert + exploring mode → Mycelium
        if expert == Expert.SOCRATIC and mode in ("exploring", "teaching"):
            return Paradigm.MYCELIUM

        # Explicit mode signals
        if mode == "exploring":
            return Paradigm.MYCELIUM

        # Default to Cortex
        return Paradigm.CORTEX

    def _apply_safety_gating(
        self,
        requested: ThinkDepth,
        burnout: BurnoutLevel,
        energy: EnergyLevel
    ) -> tuple[ThinkDepth, bool]:
        """
        Apply cognitive safety gating to thinking depth.

        Per CLAUDE.md:
        - depleted → minimal
        - low energy → standard
        - RED/ORANGE burnout → standard
        - high energy → ultradeep OK (if requested)

        Safety state ALWAYS overrides user request. Can REDUCE, never increase.

        Returns:
            (actual_depth, was_capped)
        """
        max_allowed = self._get_max_depth(burnout, energy)

        # Get depth order for comparison
        depth_order = [ThinkDepth.MINIMAL, ThinkDepth.STANDARD, ThinkDepth.DEEP, ThinkDepth.ULTRADEEP]

        requested_idx = depth_order.index(requested)
        max_idx = depth_order.index(max_allowed)

        if requested_idx > max_idx:
            # Safety cap - reduce to max allowed
            logger.info(f"Safety gating: {requested.value} → {max_allowed.value}")
            return (max_allowed, True)

        return (requested, False)

    def _get_max_depth(self, burnout: BurnoutLevel, energy: EnergyLevel) -> ThinkDepth:
        """
        Get maximum allowed thinking depth based on state.

        Cognitive Safety Gating (from CLAUDE.md):
        - depleted → minimal
        - low energy → standard
        - RED burnout → minimal
        - ORANGE burnout → standard
        - high energy → ultradeep OK
        """
        # Energy depleted → minimal
        if energy == EnergyLevel.DEPLETED:
            return ThinkDepth.MINIMAL

        # RED burnout → minimal
        if burnout == BurnoutLevel.RED:
            return ThinkDepth.MINIMAL

        # Low energy OR ORANGE burnout → standard
        if energy == EnergyLevel.LOW or burnout == BurnoutLevel.ORANGE:
            return ThinkDepth.STANDARD

        # High energy → ultradeep allowed
        if energy == EnergyLevel.HIGH:
            return ThinkDepth.ULTRADEEP

        # Default → deep
        return ThinkDepth.DEEP

    def _format_altitude(self, altitude: Altitude) -> str:
        """Format altitude for display."""
        altitude_map = {
            Altitude.VISION: "30000ft",
            Altitude.ARCHITECTURE: "15000ft",
            Altitude.COMPONENTS: "5000ft",
            Altitude.GROUND: "Ground"
        }
        return altitude_map.get(altitude, "30000ft")

    def reset(self) -> None:
        """Reset locker state (for new task).

        Note: reflection_count is now reset in CognitiveState for batch-invariance.
        """
        self._current_lock = None

    def get_current_lock(self) -> Optional[LockResult]:
        """Get current lock result."""
        return self._current_lock


# =============================================================================
# Factory Function
# =============================================================================

def create_locker(max_reflections: int = 3, epsilon: float = 0.1) -> ParameterLocker:
    """Create a ParameterLocker instance."""
    return ParameterLocker(max_reflections=max_reflections, epsilon=epsilon)


__all__ = [
    'ThinkDepth', 'Paradigm', 'LockStatus',
    'LockedParams', 'LockResult', 'ParameterLocker',
    'DEPTH_BUDGETS', 'create_locker'
]
