"""
Cognitive State Module
======================

Implements the Cognitive State tracking layer for the hybrid Orchestra model.

Tracks:
- Burnout level (GREEN/YELLOW/ORANGE/RED)
- Momentum phase (cold_start/building/rolling/peak/crashed)
- Energy level (high/medium/low/depleted)
- Mode (focused/exploring/teaching/recovery)
- Focus calibration (scattered/moderate/locked_in)

Philosophy: Cognitive support is FOUNDATIONAL, not optional.
There is no toggle. The system always respects human cognitive limits.

ThinkingMachines [He2025] Compliance:
- Fixed evaluation order for state updates
- State snapshot before processing, batch update after
- Seeded RNG for any stochastic decisions

Persistence:
- State persisted to state/.cognitive-state.json
- Atomic writes prevent corruption
- Cross-session continuity
"""

import json
import time
import hashlib
import random
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from .file_ops import atomic_write_json, safe_read_json

logger = logging.getLogger(__name__)


# =============================================================================
# Enums - Fixed categorical states
# =============================================================================

class BurnoutLevel(Enum):
    """Burnout levels with escalating severity."""
    GREEN = "green"    # Normal pace, clear requests
    YELLOW = "yellow"  # Short responses, typos, "quick"
    ORANGE = "orange"  # Frustration, repetition
    RED = "red"        # Caps, negativity, "I'm done"


class MomentumPhase(Enum):
    """Momentum phases tracking cumulative progress energy."""
    COLD_START = "cold_start"  # First task, after break, post-switch
    BUILDING = "building"      # 2-3 tasks done, increasing pace
    ROLLING = "rolling"        # Sustained output, quick decisions
    PEAK = "peak"              # High output, resistance to stopping
    CRASHED = "crashed"        # Stopped, frustration, can't start


class EnergyLevel(Enum):
    """Energy levels for capacity tracking."""
    HIGH = "high"          # Full capacity
    MEDIUM = "medium"      # Normal capacity
    LOW = "low"            # Reduced capacity
    DEPLETED = "depleted"  # Minimal capacity


class CognitiveMode(Enum):
    """Active cognitive modes."""
    FOCUSED = "focused"      # Clear goal, direct execution
    EXPLORING = "exploring"  # Discovery, what-if, tangents allowed
    TEACHING = "teaching"    # Explanatory, educational
    RECOVERY = "recovery"    # Rest, easy wins only


class Altitude(Enum):
    """Cognitive altitude levels."""
    VISION = 30000      # WHY - Vision/Goals
    ARCHITECTURE = 15000  # HOW - Systems connect
    COMPONENTS = 5000   # Module interfaces
    GROUND = 0          # Code/Syntax details


# =============================================================================
# Attractor Basins (RC^+xi convergence)
# =============================================================================

ATTRACTOR_BASINS = {
    "focused": {
        "expert": "direct",
        "paradigm": "cortex",
        "burnout": BurnoutLevel.GREEN,
        "momentum": MomentumPhase.ROLLING
    },
    "exploring": {
        "expert": "socratic",
        "paradigm": "mycelium",
        "burnout": BurnoutLevel.GREEN,
        "momentum": MomentumPhase.BUILDING
    },
    "recovery": {
        "expert": "restorer",
        "paradigm": "cortex",
        "burnout": BurnoutLevel.ORANGE,
        "momentum": MomentumPhase.CRASHED
    },
    "teaching": {
        "expert": "socratic",
        "paradigm": "cortex",
        "burnout": BurnoutLevel.GREEN,
        "momentum": MomentumPhase.ROLLING
    }
}


# =============================================================================
# CognitiveState Dataclass
# =============================================================================

@dataclass
class CognitiveState:
    """
    Tracks cognitive state for the hybrid Orchestra model.

    ThinkingMachines [He2025] compliance:
    - All state changes go through batch_update() after processing
    - Snapshot before processing with snapshot()
    - Seeded RNG instance for reproducibility
    """

    # Core state (mutable during session)
    burnout_level: BurnoutLevel = BurnoutLevel.GREEN
    momentum_phase: MomentumPhase = MomentumPhase.COLD_START
    energy_level: EnergyLevel = EnergyLevel.MEDIUM
    mode: CognitiveMode = CognitiveMode.FOCUSED
    altitude: Altitude = Altitude.VISION

    # Focus calibration (from non-invasive questions)
    # No toggle - cognitive support is always active
    focus_level: str = "moderate"  # scattered | moderate | locked_in
    urgency: str = "moderate"  # relaxed | moderate | deadline

    # Session tracking
    exchange_count: int = 0
    rapid_exchange_count: int = 0
    tasks_completed: int = 0
    tangent_budget: int = 5
    session_start: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    # Convergence tracking (RC^+xi)
    convergence_attractor: str = "focused"
    epistemic_tension: float = 0.0
    stable_exchanges: int = 0

    # MAX3 reflection tracking (moved from ParameterLocker for batch-invariance)
    reflection_count: int = 0

    # Determinism
    seed: int = 42

    # Internal RNG (not serialized)
    _rng: random.Random = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        """Initialize seeded RNG."""
        self._rng = random.Random(self.seed)

    def snapshot(self) -> 'CognitiveState':
        """
        Create an immutable snapshot of current state.

        Used BEFORE processing to ensure all agents see the same state.
        ThinkingMachines compliance: state snapshot prevents race conditions.
        """
        return CognitiveState(
            burnout_level=self.burnout_level,
            momentum_phase=self.momentum_phase,
            energy_level=self.energy_level,
            mode=self.mode,
            altitude=self.altitude,
            focus_level=self.focus_level,
            urgency=self.urgency,
            exchange_count=self.exchange_count,
            rapid_exchange_count=self.rapid_exchange_count,
            tasks_completed=self.tasks_completed,
            tangent_budget=self.tangent_budget,
            session_start=self.session_start,
            last_activity=self.last_activity,
            convergence_attractor=self.convergence_attractor,
            epistemic_tension=self.epistemic_tension,
            stable_exchanges=self.stable_exchanges,
            reflection_count=self.reflection_count,
            seed=self.seed
        )

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """
        Apply updates atomically AFTER all processing complete.

        ThinkingMachines compliance: batch updates prevent mid-processing changes.

        Args:
            updates: Dict of field names to new values
        """
        # FIXED evaluation order for updates
        UPDATE_ORDER = [
            'burnout_level', 'momentum_phase', 'energy_level', 'mode',
            'altitude', 'focus_level', 'urgency', 'exchange_count',
            'rapid_exchange_count', 'tasks_completed', 'tangent_budget',
            'convergence_attractor', 'epistemic_tension', 'stable_exchanges',
            'reflection_count'
        ]

        for field_name in UPDATE_ORDER:
            if field_name in updates:
                value = updates[field_name]

                # Convert string enums if needed
                if field_name == 'burnout_level' and isinstance(value, str):
                    value = BurnoutLevel(value)
                elif field_name == 'momentum_phase' and isinstance(value, str):
                    value = MomentumPhase(value)
                elif field_name == 'energy_level' and isinstance(value, str):
                    value = EnergyLevel(value)
                elif field_name == 'mode' and isinstance(value, str):
                    value = CognitiveMode(value)
                elif field_name == 'altitude' and isinstance(value, int):
                    value = Altitude(value)

                setattr(self, field_name, value)

        # Always update last_activity
        self.last_activity = time.time()

    def increment_exchange(self, rapid: bool = False) -> None:
        """Increment exchange counters."""
        self.exchange_count += 1
        if rapid:
            self.rapid_exchange_count += 1

    def complete_task(self) -> None:
        """Record task completion and update momentum."""
        self.tasks_completed += 1

        # Update momentum based on task completion
        if self.momentum_phase == MomentumPhase.COLD_START and self.tasks_completed >= 1:
            self.momentum_phase = MomentumPhase.BUILDING
        elif self.momentum_phase == MomentumPhase.BUILDING and self.tasks_completed >= 3:
            self.momentum_phase = MomentumPhase.ROLLING
        elif self.momentum_phase == MomentumPhase.ROLLING and self.tasks_completed >= 6:
            self.momentum_phase = MomentumPhase.PEAK

    def consume_tangent(self) -> bool:
        """
        Consume a tangent from the budget.

        Returns:
            True if tangent allowed, False if budget depleted
        """
        if self.tangent_budget > 0:
            self.tangent_budget -= 1
            return True
        return False

    def check_body_check_needed(self) -> bool:
        """
        Check if body check is needed.

        Always active - respects human cognitive limits.

        Returns:
            True if 20 rapid exchanges reached
        """
        return self.rapid_exchange_count >= 20

    def reset_rapid_exchanges(self) -> None:
        """Reset rapid exchange counter (after body check)."""
        self.rapid_exchange_count = 0

    def escalate_burnout(self) -> None:
        """Escalate burnout to next level."""
        escalation = {
            BurnoutLevel.GREEN: BurnoutLevel.YELLOW,
            BurnoutLevel.YELLOW: BurnoutLevel.ORANGE,
            BurnoutLevel.ORANGE: BurnoutLevel.RED,
            BurnoutLevel.RED: BurnoutLevel.RED  # Can't go higher
        }
        self.burnout_level = escalation[self.burnout_level]

    def recover_burnout(self) -> None:
        """Recover burnout by one level."""
        recovery = {
            BurnoutLevel.RED: BurnoutLevel.ORANGE,
            BurnoutLevel.ORANGE: BurnoutLevel.YELLOW,
            BurnoutLevel.YELLOW: BurnoutLevel.GREEN,
            BurnoutLevel.GREEN: BurnoutLevel.GREEN  # Already healthy
        }
        self.burnout_level = recovery[self.burnout_level]

    def should_intervene(self) -> bool:
        """
        Check if intervention is required based on state.

        Returns:
            True if burnout >= ORANGE or energy = depleted
        """
        return (
            self.burnout_level in (BurnoutLevel.ORANGE, BurnoutLevel.RED) or
            self.energy_level == EnergyLevel.DEPLETED
        )

    def get_max_thinking_depth(self) -> str:
        """
        Get maximum allowed thinking depth based on state.

        Cognitive Safety Gating: State ALWAYS overrides user depth request.
        """
        if self.energy_level == EnergyLevel.DEPLETED:
            return "minimal"
        if self.energy_level == EnergyLevel.LOW:
            return "standard"
        if self.burnout_level in (BurnoutLevel.ORANGE, BurnoutLevel.RED):
            return "standard"
        if self.burnout_level == BurnoutLevel.RED:
            return "minimal"
        # High energy allows ultradeep
        if self.energy_level == EnergyLevel.HIGH:
            return "ultradeep"
        return "deep"

    def update_convergence(self, new_attractor: str) -> float:
        """
        Update convergence tracking (RC^+xi).

        Formula: xi_n = ||A_{n+1} - A_n||_2

        Returns:
            Current epistemic tension
        """
        if new_attractor == self.convergence_attractor:
            self.stable_exchanges += 1
            # Tension decreases when stable
            self.epistemic_tension = max(0.0, self.epistemic_tension - 0.1)
        else:
            # Tension increases on attractor switch
            self.epistemic_tension = min(1.0, self.epistemic_tension + 0.3)
            self.stable_exchanges = 0
            self.convergence_attractor = new_attractor

        return self.epistemic_tension

    def is_converged(self, epsilon: float = 0.1) -> bool:
        """
        Check if state has converged (3 stable exchanges at xi < epsilon).
        """
        return self.stable_exchanges >= 3 and self.epistemic_tension < epsilon

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dict for persistence."""
        return {
            "burnout_level": self.burnout_level.value,
            "momentum_phase": self.momentum_phase.value,
            "energy_level": self.energy_level.value,
            "mode": self.mode.value,
            "altitude": self.altitude.value,
            "focus_level": self.focus_level,
            "urgency": self.urgency,
            "exchange_count": self.exchange_count,
            "rapid_exchange_count": self.rapid_exchange_count,
            "tasks_completed": self.tasks_completed,
            "tangent_budget": self.tangent_budget,
            "session_start": self.session_start,
            "last_activity": self.last_activity,
            "convergence_attractor": self.convergence_attractor,
            "epistemic_tension": self.epistemic_tension,
            "stable_exchanges": self.stable_exchanges,
            "reflection_count": self.reflection_count,
            "seed": self.seed
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CognitiveState':
        """Deserialize state from dict."""
        return cls(
            burnout_level=BurnoutLevel(data.get("burnout_level", "green")),
            momentum_phase=MomentumPhase(data.get("momentum_phase", "cold_start")),
            energy_level=EnergyLevel(data.get("energy_level", "medium")),
            mode=CognitiveMode(data.get("mode", "focused")),
            altitude=Altitude(data.get("altitude", 30000)),
            focus_level=data.get("focus_level", "moderate"),
            urgency=data.get("urgency", "moderate"),
            exchange_count=data.get("exchange_count", 0),
            rapid_exchange_count=data.get("rapid_exchange_count", 0),
            tasks_completed=data.get("tasks_completed", 0),
            tangent_budget=data.get("tangent_budget", 5),
            session_start=data.get("session_start", time.time()),
            last_activity=data.get("last_activity", time.time()),
            convergence_attractor=data.get("convergence_attractor", "focused"),
            epistemic_tension=data.get("epistemic_tension", 0.0),
            stable_exchanges=data.get("stable_exchanges", 0),
            reflection_count=data.get("reflection_count", 0),
            seed=data.get("seed", 42)
        )

    def checksum(self) -> str:
        """Generate deterministic checksum of current state."""
        state_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]


# =============================================================================
# CognitiveStateManager - Persistence Layer
# =============================================================================

class CognitiveStateManager:
    """
    Manages CognitiveState persistence and lifecycle.

    Persistence path: ~/.orchestra/state/cognitive_state.json
    Uses atomic writes for crash safety.

    Session reset: If last_activity > 2 hours ago, resets session-specific
    fields while preserving user preferences.
    """

    DEFAULT_STATE_DIR = Path.home() / ".orchestra" / "state"
    DEFAULT_STATE_FILE = "cognitive_state.json"

    # Session staleness threshold: 2 hours
    STALE_SESSION_SECONDS = 2 * 60 * 60

    def __init__(self, state_dir: Path = None):
        """
        Initialize state manager.

        Args:
            state_dir: Directory for state files (default: ~/.orchestra/state)
        """
        self.state_dir = state_dir or self.DEFAULT_STATE_DIR
        self.state_file = self.state_dir / self.DEFAULT_STATE_FILE
        self._state: Optional[CognitiveState] = None

        # Ensure state directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> CognitiveState:
        """
        Load state from disk or create new.

        Implements 2-hour session staleness detection: if last_activity
        was more than 2 hours ago, reset session-specific fields while
        preserving user preferences.

        Returns:
            Loaded or new CognitiveState
        """
        if self._state is not None:
            return self._state

        if self.state_file.exists():
            try:
                data = safe_read_json(self.state_file)
                if data:
                    self._state = CognitiveState.from_dict(data)

                    # Check for stale session
                    if self._is_session_stale():
                        logger.info("Session stale (>2h). Resetting session fields.")
                        self._reset_session_fields()

                    logger.info(f"Loaded cognitive state: {self._state.checksum()}")
                    return self._state
            except Exception as e:
                logger.error(f"Failed to load cognitive state: {e}")

        # Create fresh state
        self._state = CognitiveState()
        logger.info("Created new cognitive state")
        return self._state

    def _is_session_stale(self) -> bool:
        """Check if the session is stale (last activity > 2 hours ago)."""
        if self._state is None:
            return False
        elapsed = time.time() - self._state.last_activity
        return elapsed > self.STALE_SESSION_SECONDS

    def _reset_session_fields(self) -> None:
        """
        Reset session-specific fields while preserving preferences.

        Resets: exchange counts, session timing, momentum, tangent budget
        Preserves: focus_level, urgency, seed (user preferences)
        """
        if self._state is None:
            return

        # Reset session-specific fields
        self._state.exchange_count = 0
        self._state.rapid_exchange_count = 0
        self._state.tasks_completed = 0
        self._state.tangent_budget = 5
        self._state.session_start = time.time()
        self._state.last_activity = time.time()
        self._state.momentum_phase = MomentumPhase.COLD_START
        self._state.stable_exchanges = 0
        self._state.epistemic_tension = 0.0
        self._state.reflection_count = 0

        # Reset burnout to healthy (don't carry RED across sessions)
        if self._state.burnout_level in (BurnoutLevel.ORANGE, BurnoutLevel.RED):
            self._state.burnout_level = BurnoutLevel.GREEN

        # Preserve: focus_level, urgency, seed, energy_level, mode, altitude
        self.save()

    def save(self) -> None:
        """Save current state to disk atomically."""
        if self._state is None:
            return

        try:
            atomic_write_json(self.state_file, self._state.to_dict())
            logger.info(f"Saved cognitive state: {self._state.checksum()}")
        except Exception as e:
            logger.error(f"Failed to save cognitive state: {e}")

    def get_state(self) -> CognitiveState:
        """Get current state (loading if needed)."""
        if self._state is None:
            return self.load()
        return self._state

    def reset(self) -> CognitiveState:
        """Reset to fresh state."""
        self._state = CognitiveState()
        self.save()
        logger.info("Reset cognitive state to defaults")
        return self._state

    def snapshot(self) -> CognitiveState:
        """Get immutable snapshot of current state."""
        return self.get_state().snapshot()

    def get_resolved_value(self, key: str, default: Any = None) -> Any:
        """
        Get a resolved value from cognitive state with fallback default.

        This method provides the API contract expected by AgentCoordinator
        for extracting state values with graceful degradation.

        ThinkingMachines [He2025] Compliance:
        - Deterministic: Same key + same state → same value
        - Batch-invariant: No side effects on read

        Args:
            key: Attribute name on CognitiveState
            default: Fallback value if attribute missing or None

        Returns:
            Resolved value or default
        """
        state = self.get_state()

        # Handle enum fields - return their value
        value = getattr(state, key, None)
        if value is None:
            return default

        # Resolve enums to their string values for compatibility
        if hasattr(value, 'value'):
            return value.value

        return value

    def batch_update(self, updates: Dict[str, Any]) -> None:
        """Apply batch updates and save."""
        state = self.get_state()
        state.batch_update(updates)
        self.save()

    def calibrate(self, focus_level: str = None, urgency: str = None) -> None:
        """
        Calibrate cognitive state from non-invasive questions.

        Args:
            focus_level: 'scattered', 'moderate', or 'locked_in'
            urgency: 'relaxed', 'moderate', or 'deadline'
        """
        state = self.get_state()
        if focus_level:
            state.focus_level = focus_level
        if urgency:
            state.urgency = urgency
        self.save()
        logger.info(f"Calibrated: focus={state.focus_level}, urgency={state.urgency}")


__all__ = [
    'BurnoutLevel', 'MomentumPhase', 'EnergyLevel', 'CognitiveMode', 'Altitude',
    'CognitiveState', 'CognitiveStateManager', 'ATTRACTOR_BASINS'
]
