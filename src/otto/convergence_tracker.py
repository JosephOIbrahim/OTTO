"""
Convergence Tracker (RC^+xi)
============================

Tracks epistemic tension and convergence to attractor basins.

Formula: xi_n = ||A_{n+1} - A_n||_2 (epistemic tension)
Epsilon: 0.1 (convergence threshold)
Stable: 3 exchanges at xi < epsilon = CONVERGED

Attractor Basins (from CLAUDE.md):
- focused   → Direct + Cortex + GREEN + rolling
- exploring → Socratic + Mycelium + GREEN + building
- recovery  → Restorer + Cortex + ORANGE + crashed
- teaching  → Socratic + Cortex + GREEN + 15000ft

ThinkingMachines [He2025] Compliance:
- Fixed attractor definitions
- Deterministic tension calculation
- Reproducible convergence detection
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

from .expert_router import Expert
from .parameter_locker import Paradigm
from .cognitive_state import BurnoutLevel, MomentumPhase, Altitude

logger = logging.getLogger(__name__)


# =============================================================================
# Attractor Basins
# =============================================================================

class AttractorBasin(Enum):
    """Attractor basin states."""
    FOCUSED = "focused"
    EXPLORING = "exploring"
    RECOVERY = "recovery"
    TEACHING = "teaching"


# Attractor basin definitions (target states)
ATTRACTOR_DEFINITIONS = {
    AttractorBasin.FOCUSED: {
        "expert": Expert.DIRECT,
        "paradigm": Paradigm.CORTEX,
        "burnout": BurnoutLevel.GREEN,
        "momentum": MomentumPhase.ROLLING,
        "description": "Optimal flow state - direct execution, minimal friction"
    },
    AttractorBasin.EXPLORING: {
        "expert": Expert.SOCRATIC,
        "paradigm": Paradigm.MYCELIUM,
        "burnout": BurnoutLevel.GREEN,
        "momentum": MomentumPhase.BUILDING,
        "description": "Discovery mode - following threads, building understanding"
    },
    AttractorBasin.RECOVERY: {
        "expert": Expert.RESTORER,
        "paradigm": Paradigm.CORTEX,
        "burnout": BurnoutLevel.ORANGE,
        "momentum": MomentumPhase.CRASHED,
        "description": "Recovery mode - easy wins, rest, rebuilding"
    },
    AttractorBasin.TEACHING: {
        "expert": Expert.SOCRATIC,
        "paradigm": Paradigm.CORTEX,
        "burnout": BurnoutLevel.GREEN,
        "momentum": MomentumPhase.ROLLING,
        "altitude": Altitude.ARCHITECTURE,  # 15000ft
        "description": "Teaching mode - explanatory, educational focus"
    }
}


# =============================================================================
# Tension Color Coding
# =============================================================================

def get_tension_color(tension: float) -> str:
    """
    Get color code for tension level.

    - 0.0-0.1: GREEN (converged)
    - 0.1-0.3: BLUE (stable)
    - 0.3-0.6: YELLOW (tension)
    - 0.6-1.0: RED (high tension)
    """
    if tension <= 0.1:
        return "green"
    elif tension <= 0.3:
        return "blue"
    elif tension <= 0.6:
        return "yellow"
    else:
        return "red"


# =============================================================================
# Convergence Result
# =============================================================================

@dataclass
class ConvergenceResult:
    """Result of convergence tracking."""
    epistemic_tension: float  # xi_n (0.0 - 1.0)
    attractor_basin: AttractorBasin
    stable_exchanges: int  # 0-3
    converged: bool
    tension_color: str
    attractor_distance: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for WebSocket."""
        return {
            "epistemic_tension": self.epistemic_tension,
            "attractor_basin": self.attractor_basin.value,
            "stable_exchanges": self.stable_exchanges,
            "converged": self.converged,
            "tension_color": self.tension_color,
            "attractor_distance": self.attractor_distance
        }


# =============================================================================
# State Vector
# =============================================================================

@dataclass
class StateVector:
    """
    Normalized state vector for distance calculation.

    Used to compute ||A_{n+1} - A_n||_2
    """
    expert: float  # 0-1 normalized expert index
    paradigm: float  # 0 = Cortex, 1 = Mycelium
    burnout: float  # 0-1 normalized burnout
    momentum: float  # 0-1 normalized momentum
    altitude: float  # 0-1 normalized altitude

    def to_array(self) -> List[float]:
        """Convert to array for distance calculation."""
        return [self.expert, self.paradigm, self.burnout, self.momentum, self.altitude]

    @staticmethod
    def distance(a: 'StateVector', b: 'StateVector') -> float:
        """
        Calculate L2 distance between two state vectors.

        Formula: ||A - B||_2 = sqrt(sum((a_i - b_i)^2))
        """
        arr_a = a.to_array()
        arr_b = b.to_array()
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(arr_a, arr_b)))


# =============================================================================
# Convergence Tracker
# =============================================================================

class ConvergenceTracker:
    """
    Tracks epistemic tension and convergence to attractor basins.

    Implements RC^+xi from CLAUDE.md:
    - Calculates epistemic tension after each exchange
    - Detects current attractor basin
    - Tracks stable exchange count
    - Declares convergence at 3 stable exchanges
    """

    # Convergence threshold (epsilon)
    EPSILON = 0.1

    # Stable exchanges required for convergence
    STABLE_REQUIRED = 3

    def __init__(self, epsilon: float = 0.1):
        """
        Initialize tracker.

        Args:
            epsilon: Convergence threshold (default 0.1)
        """
        self.epsilon = epsilon
        self._previous_state: Optional[StateVector] = None
        self._current_attractor: AttractorBasin = AttractorBasin.FOCUSED
        self._stable_count = 0
        self._tension_history: List[float] = []

    def update(
        self,
        expert: Expert,
        paradigm: Paradigm,
        burnout: BurnoutLevel,
        momentum: MomentumPhase,
        altitude: Altitude
    ) -> ConvergenceResult:
        """
        Update convergence tracking with new state.

        Args:
            expert: Current expert
            paradigm: Current paradigm
            burnout: Current burnout level
            momentum: Current momentum phase
            altitude: Current altitude

        Returns:
            ConvergenceResult with tension and convergence status
        """
        # =================================================================
        # STEP 1: Normalize current state to vector
        # =================================================================
        current_state = self._normalize_state(expert, paradigm, burnout, momentum, altitude)

        # =================================================================
        # STEP 2: Calculate epistemic tension (xi_n)
        # =================================================================
        if self._previous_state is None:
            # First exchange - no tension
            tension = 0.0
        else:
            # xi_n = ||A_{n+1} - A_n||_2
            tension = StateVector.distance(current_state, self._previous_state)
            # Normalize to 0-1 range (max theoretical distance is sqrt(5) ≈ 2.24)
            tension = min(tension / 2.24, 1.0)

        # =================================================================
        # STEP 3: Detect current attractor basin
        # =================================================================
        new_attractor, attractor_distances = self._detect_attractor(
            expert, paradigm, burnout, momentum, altitude
        )

        # =================================================================
        # STEP 4: Update stable exchange count
        # =================================================================
        if new_attractor == self._current_attractor and tension < self.epsilon:
            self._stable_count += 1
        else:
            self._stable_count = 0 if new_attractor != self._current_attractor else 1
            self._current_attractor = new_attractor

        # =================================================================
        # STEP 5: Check convergence
        # =================================================================
        converged = self._stable_count >= self.STABLE_REQUIRED and tension < self.epsilon

        # Update history
        self._previous_state = current_state
        self._tension_history.append(tension)
        if len(self._tension_history) > 100:
            self._tension_history = self._tension_history[-100:]

        result = ConvergenceResult(
            epistemic_tension=tension,
            attractor_basin=self._current_attractor,
            stable_exchanges=min(self._stable_count, self.STABLE_REQUIRED),
            converged=converged,
            tension_color=get_tension_color(tension),
            attractor_distance=attractor_distances
        )

        logger.debug(
            f"Convergence: xi={tension:.3f}, attractor={self._current_attractor.value}, "
            f"stable={self._stable_count}, converged={converged}"
        )

        return result

    def _normalize_state(
        self,
        expert: Expert,
        paradigm: Paradigm,
        burnout: BurnoutLevel,
        momentum: MomentumPhase,
        altitude: Altitude
    ) -> StateVector:
        """Normalize state to vector for distance calculation."""
        # Expert: normalize by priority (1-7 → 0-1)
        expert_order = [Expert.VALIDATOR, Expert.SCAFFOLDER, Expert.RESTORER,
                        Expert.REFOCUSER, Expert.CELEBRATOR, Expert.SOCRATIC, Expert.DIRECT]
        expert_idx = expert_order.index(expert) if expert in expert_order else 6
        expert_norm = expert_idx / 6.0

        # Paradigm: binary
        paradigm_norm = 0.0 if paradigm == Paradigm.CORTEX else 1.0

        # Burnout: GREEN=0, YELLOW=0.33, ORANGE=0.67, RED=1.0
        burnout_map = {
            BurnoutLevel.GREEN: 0.0,
            BurnoutLevel.YELLOW: 0.33,
            BurnoutLevel.ORANGE: 0.67,
            BurnoutLevel.RED: 1.0
        }
        burnout_norm = burnout_map.get(burnout, 0.0)

        # Momentum: cold_start=0.1, building=0.35, rolling=0.65, peak=1.0, crashed=0.05
        momentum_map = {
            MomentumPhase.COLD_START: 0.1,
            MomentumPhase.BUILDING: 0.35,
            MomentumPhase.ROLLING: 0.65,
            MomentumPhase.PEAK: 1.0,
            MomentumPhase.CRASHED: 0.05
        }
        momentum_norm = momentum_map.get(momentum, 0.5)

        # Altitude: Ground=0, 5000ft=0.33, 15000ft=0.67, 30000ft=1.0
        altitude_map = {
            Altitude.GROUND: 0.0,
            Altitude.COMPONENTS: 0.33,
            Altitude.ARCHITECTURE: 0.67,
            Altitude.VISION: 1.0
        }
        altitude_norm = altitude_map.get(altitude, 1.0)

        return StateVector(
            expert=expert_norm,
            paradigm=paradigm_norm,
            burnout=burnout_norm,
            momentum=momentum_norm,
            altitude=altitude_norm
        )

    def _detect_attractor(
        self,
        expert: Expert,
        paradigm: Paradigm,
        burnout: BurnoutLevel,
        momentum: MomentumPhase,
        altitude: Altitude
    ) -> tuple[AttractorBasin, Dict[str, float]]:
        """
        Detect which attractor basin the current state is closest to.

        Returns:
            (closest_attractor, distances_to_all_attractors)
        """
        current = self._normalize_state(expert, paradigm, burnout, momentum, altitude)
        distances = {}
        min_distance = float('inf')
        closest = AttractorBasin.FOCUSED

        for attractor, definition in ATTRACTOR_DEFINITIONS.items():
            # Create target state vector
            target = self._normalize_state(
                definition["expert"],
                definition["paradigm"],
                definition["burnout"],
                definition["momentum"],
                definition.get("altitude", Altitude.VISION)
            )

            distance = StateVector.distance(current, target)
            distances[attractor.value] = round(distance, 3)

            if distance < min_distance:
                min_distance = distance
                closest = attractor

        return (closest, distances)

    def get_tension_trend(self) -> str:
        """
        Get tension trend (increasing/decreasing/stable).
        """
        if len(self._tension_history) < 3:
            return "insufficient_data"

        recent = self._tension_history[-3:]
        if recent[-1] < recent[0] - 0.05:
            return "decreasing"
        elif recent[-1] > recent[0] + 0.05:
            return "increasing"
        else:
            return "stable"

    def reset(self) -> None:
        """Reset tracker state."""
        self._previous_state = None
        self._current_attractor = AttractorBasin.FOCUSED
        self._stable_count = 0
        self._tension_history = []

    def get_attractor_info(self, attractor: AttractorBasin) -> Dict[str, Any]:
        """Get information about an attractor basin."""
        definition = ATTRACTOR_DEFINITIONS.get(attractor, {})
        return {
            "name": attractor.value,
            "expert": definition.get("expert", Expert.DIRECT).value,
            "paradigm": definition.get("paradigm", Paradigm.CORTEX).value,
            "burnout": definition.get("burnout", BurnoutLevel.GREEN).value,
            "momentum": definition.get("momentum", MomentumPhase.ROLLING).value,
            "description": definition.get("description", "")
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_tracker(epsilon: float = 0.1) -> ConvergenceTracker:
    """Create a ConvergenceTracker instance."""
    return ConvergenceTracker(epsilon=epsilon)


__all__ = [
    'AttractorBasin', 'ConvergenceResult', 'StateVector', 'ConvergenceTracker',
    'ATTRACTOR_DEFINITIONS', 'get_tension_color', 'create_tracker'
]
