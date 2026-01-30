"""
Cognitive Safety Module
=======================

Implements cognitive safety gating for the Orchestra cognitive model.

Core Cognitive Safety Constraints (from CLAUDE.md):
- Working memory limit: Max 3 items without structure
- Time blindness: Use exchange count as proxy (20 exchanges = 90min)
- Tangent budget: 5 per session, explicit tracking
- Body check: Every 20 rapid exchanges
- Task chunking: Max 5 subtasks visible at once

Toggle Mode:
- Cognitive safety mode is a binary toggle (ON/OFF)
- When ON: All constraints enforced
- When OFF: Constraints disabled

ThinkingMachines [He2025] Compliance:
- Binary toggle, no soft modes
- Fixed constraint values
- Deterministic behavior
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import time
import logging

from .cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel

logger = logging.getLogger(__name__)


# =============================================================================
# Cognitive Safety Constraints - FIXED Values
# =============================================================================

class CognitiveSafetyConstraints:
    """Fixed cognitive safety constraint values - never vary based on input."""

    # Working memory
    WORKING_MEMORY_LIMIT = 3  # Max items without structure

    # Time tracking
    BODY_CHECK_INTERVAL = 20  # Rapid exchanges before body check
    EXCHANGE_TIME_ESTIMATE = 4.5  # Minutes per exchange (approximate)

    # Tangent management
    DEFAULT_TANGENT_BUDGET = 5  # Tangents allowed per session

    # Task chunking
    MAX_VISIBLE_SUBTASKS = 5  # Max subtasks shown at once
    CHUNK_OVERFLOW_THRESHOLD = 5  # When to group into phases

    # Thinking depth limits
    MAX_DEPTH_DEPLETED = "minimal"
    MAX_DEPTH_LOW_ENERGY = "standard"
    MAX_DEPTH_BURNOUT = "standard"

    # Perfectionism interrupt triggers
    PERFECTIONISM_PHRASES = [
        "one more thing",
        "let me just",
        "almost ready",
        "just need to",
        "quick fix",
        "small tweak"
    ]


# =============================================================================
# Recovery Options
# =============================================================================

class RecoveryOption(Enum):
    """Recovery options when RED burnout detected."""
    DONE_TODAY = "done_for_today"          # Save state and stop
    EASY_WINS = "switch_to_easy_wins"      # Low-effort tasks only
    TALK_OUT = "talk_it_out"               # No code, just discussion
    SHORT_BREAK = "15_min_break"           # Pause and reassess
    SCOPE_CUT = "scope_cut"                # Reduce requirements


RECOVERY_OPTIONS = {
    RecoveryOption.DONE_TODAY: {
        "label": "Done for today",
        "description": "Save state and stop. Tomorrow is fine.",
        "action": "save_and_exit"
    },
    RecoveryOption.EASY_WINS: {
        "label": "Switch to easy wins",
        "description": "Only low-effort, high-dopamine tasks.",
        "action": "filter_easy_tasks"
    },
    RecoveryOption.TALK_OUT: {
        "label": "Talk it out",
        "description": "No code - just discussion and clarification.",
        "action": "disable_code_gen"
    },
    RecoveryOption.SHORT_BREAK: {
        "label": "15-minute break",
        "description": "Step away, then reassess energy.",
        "action": "schedule_break"
    },
    RecoveryOption.SCOPE_CUT: {
        "label": "Scope cut",
        "description": "Reduce requirements to minimum viable.",
        "action": "reduce_scope"
    }
}


# =============================================================================
# Cognitive Safety Check Result
# =============================================================================

@dataclass
class CognitiveSafetyCheckResult:
    """Result from cognitive safety constraint checking."""

    # Constraint status
    working_memory_exceeded: bool = False
    body_check_needed: bool = False
    tangent_budget_depleted: bool = False
    perfectionism_detected: bool = False

    # Current limits
    working_memory_items: int = 0
    rapid_exchanges: int = 0
    tangents_remaining: int = 5

    # Recommendations
    should_chunk: bool = False
    chunk_size: int = 5
    depth_limit: str = "deep"

    # Messages
    intervention_message: Optional[str] = None
    body_check_message: Optional[str] = None

    # Recovery (if RED)
    recovery_needed: bool = False
    recovery_options: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "working_memory_exceeded": self.working_memory_exceeded,
            "body_check_needed": self.body_check_needed,
            "tangent_budget_depleted": self.tangent_budget_depleted,
            "perfectionism_detected": self.perfectionism_detected,
            "working_memory_items": self.working_memory_items,
            "rapid_exchanges": self.rapid_exchanges,
            "tangents_remaining": self.tangents_remaining,
            "should_chunk": self.should_chunk,
            "chunk_size": self.chunk_size,
            "depth_limit": self.depth_limit,
            "intervention_message": self.intervention_message,
            "body_check_message": self.body_check_message,
            "recovery_needed": self.recovery_needed,
            "recovery_options": self.recovery_options
        }


# =============================================================================
# Cognitive Safety Manager
# =============================================================================

class CognitiveSafetyManager:
    """
    Manages cognitive safety constraints when enabled.

    Toggle mode: Binary ON/OFF, no soft modes per [He2025].
    """

    def __init__(self, enabled: bool = False):
        """
        Initialize cognitive safety support.

        Args:
            enabled: Whether cognitive safety mode is enabled
        """
        self.enabled = enabled
        self.constraints = CognitiveSafetyConstraints()

    def set_enabled(self, enabled: bool) -> None:
        """Toggle cognitive safety mode (binary)."""
        self.enabled = enabled
        logger.info(f"Cognitive safety {'enabled' if enabled else 'disabled'}")

    def check(self, state: CognitiveState, task_items: int = 0,
              text: str = "") -> CognitiveSafetyCheckResult:
        """
        Check cognitive safety constraints against current state.

        Args:
            state: Current cognitive state
            task_items: Number of items in current task/list
            text: User input text (for perfectionism detection)

        Returns:
            CognitiveSafetyCheckResult with constraint status and recommendations
        """
        result = CognitiveSafetyCheckResult()

        if not self.enabled:
            # Cognitive safety mode disabled - return minimal result
            result.depth_limit = "ultradeep"  # No limits
            return result

        # Check working memory
        result.working_memory_items = task_items
        if task_items > self.constraints.WORKING_MEMORY_LIMIT:
            result.working_memory_exceeded = True
            result.should_chunk = True
            result.chunk_size = self.constraints.MAX_VISIBLE_SUBTASKS
            result.intervention_message = (
                f"Working memory limit ({self.constraints.WORKING_MEMORY_LIMIT}) exceeded. "
                f"Chunking {task_items} items into groups of {result.chunk_size}."
            )

        # Check body check interval
        result.rapid_exchanges = state.rapid_exchange_count
        if state.rapid_exchange_count >= self.constraints.BODY_CHECK_INTERVAL:
            result.body_check_needed = True
            estimated_time = state.rapid_exchange_count * self.constraints.EXCHANGE_TIME_ESTIMATE
            result.body_check_message = (
                f"Body check: {state.rapid_exchange_count} rapid exchanges "
                f"(~{estimated_time:.0f} min). How are you feeling physically? "
                "Water? Stretch? Bio break?"
            )

        # Check tangent budget
        result.tangents_remaining = state.tangent_budget
        if state.tangent_budget <= 0:
            result.tangent_budget_depleted = True

        # Check for perfectionism language
        text_lower = text.lower()
        for phrase in self.constraints.PERFECTIONISM_PHRASES:
            if phrase in text_lower:
                result.perfectionism_detected = True
                result.intervention_message = (
                    "Perfectionism detected. Is this blocking ship? "
                    "Ship it. Polish later."
                )
                break

        # Determine depth limit based on state
        result.depth_limit = self._get_depth_limit(state)

        # Check if recovery needed (RED burnout)
        if state.burnout_level == BurnoutLevel.RED:
            result.recovery_needed = True
            result.recovery_options = [
                {"value": opt.value, **info}
                for opt, info in RECOVERY_OPTIONS.items()
            ]

        return result

    def _get_depth_limit(self, state: CognitiveState) -> str:
        """
        Get thinking depth limit based on state.

        Cognitive Safety Gating: State ALWAYS overrides user depth request.
        Can REDUCE depth, never increase.
        """
        # Depleted = minimal only
        if state.energy_level == EnergyLevel.DEPLETED:
            return self.constraints.MAX_DEPTH_DEPLETED

        # Low energy = standard max
        if state.energy_level == EnergyLevel.LOW:
            return self.constraints.MAX_DEPTH_LOW_ENERGY

        # RED burnout = minimal
        if state.burnout_level == BurnoutLevel.RED:
            return self.constraints.MAX_DEPTH_DEPLETED

        # ORANGE burnout = standard
        if state.burnout_level == BurnoutLevel.ORANGE:
            return self.constraints.MAX_DEPTH_BURNOUT

        # High energy = allow ultradeep
        if state.energy_level == EnergyLevel.HIGH:
            return "ultradeep"

        # Default = deep
        return "deep"

    def chunk_tasks(self, tasks: List[str]) -> List[Dict[str, Any]]:
        """
        Chunk tasks into manageable groups.

        Per CLAUDE.md: "Max 5 subtasks visible at once"

        Args:
            tasks: List of task descriptions

        Returns:
            List of phase dicts with chunked tasks
        """
        if not self.enabled:
            # No chunking when disabled
            return [{"phase": 1, "name": "All Tasks", "tasks": tasks}]

        chunk_size = self.constraints.MAX_VISIBLE_SUBTASKS
        phases = []

        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i + chunk_size]
            phase_num = (i // chunk_size) + 1
            phases.append({
                "phase": phase_num,
                "name": f"Phase {phase_num}",
                "tasks": chunk,
                "count": len(chunk)
            })

        return phases

    def format_progress(self, completed: int, total: int,
                        current_phase: int = 1, total_phases: int = 1) -> str:
        """
        Format progress for cognitive safety-friendly display.

        Per CLAUDE.md: "Progress ALWAYS visible"

        Args:
            completed: Tasks completed
            total: Total tasks
            current_phase: Current phase number
            total_phases: Total phases

        Returns:
            Formatted progress string
        """
        if total == 0:
            return "No tasks"

        percent = (completed / total) * 100
        bar_filled = int(percent / 10)
        bar_empty = 10 - bar_filled

        bar = f"[{'#' * bar_filled}{'-' * bar_empty}]"

        if total_phases > 1:
            return f"{bar} {percent:.0f}% ({completed}/{total}) | Phase {current_phase}/{total_phases}"
        else:
            return f"{bar} {percent:.0f}% ({completed}/{total})"

    def get_recovery_menu(self) -> Dict[str, Any]:
        """
        Get recovery menu for RED burnout state.

        Returns:
            Dict with recovery options and formatting
        """
        return {
            "title": "Recovery Options",
            "message": "You're in RED burnout. No judgment. Let's figure out what helps.",
            "options": [
                {
                    "key": str(i + 1),
                    "value": opt.value,
                    "label": info["label"],
                    "description": info["description"]
                }
                for i, (opt, info) in enumerate(RECOVERY_OPTIONS.items())
            ]
        }

    def should_spawn_agents(self, state: CognitiveState) -> Tuple[bool, Optional[str]]:
        """
        Check if agent spawning is allowed given current state.

        Per CLAUDE.md Anti-Orchestration Signals:
        - burnout >= ORANGE: NO agents
        - energy = depleted: NO agents
        - momentum = crashed: NO agents

        Returns:
            (allowed, reason_if_not)
        """
        if not self.enabled:
            return (True, None)

        if state.burnout_level in (BurnoutLevel.ORANGE, BurnoutLevel.RED):
            return (False, f"Burnout level {state.burnout_level.value} - simplify, don't spawn agents")

        if state.energy_level == EnergyLevel.DEPLETED:
            return (False, "Energy depleted - no bandwidth for tracking agents")

        if state.momentum_phase.value == "crashed":
            return (False, "Momentum crashed - recovery mode, minimize moving parts")

        return (True, None)

    def suggest_break(self, state: CognitiveState) -> Optional[str]:
        """
        Suggest a break based on state.

        Returns:
            Break suggestion message or None
        """
        if not self.enabled:
            return None

        if state.burnout_level == BurnoutLevel.YELLOW:
            return "Quick break soon? You've been at this a while."

        if state.burnout_level == BurnoutLevel.ORANGE:
            return "What's the blocker? Maybe time to step back."

        return None


# =============================================================================
# Task Tracker for Working Memory
# =============================================================================

@dataclass
class WorkingMemoryTracker:
    """
    Tracks items in working memory for cognitive safety.

    Enforces the 3-item limit per CLAUDE.md.
    """
    items: List[str] = field(default_factory=list)
    max_items: int = CognitiveSafetyConstraints.WORKING_MEMORY_LIMIT

    def add(self, item: str) -> Tuple[bool, Optional[str]]:
        """
        Add item to working memory.

        Returns:
            (success, overflow_item) - if overflow, returns the dropped item
        """
        if len(self.items) >= self.max_items:
            # FIFO overflow
            dropped = self.items.pop(0)
            self.items.append(item)
            return (True, dropped)

        self.items.append(item)
        return (True, None)

    def remove(self, item: str) -> bool:
        """Remove item from working memory."""
        if item in self.items:
            self.items.remove(item)
            return True
        return False

    def clear(self) -> None:
        """Clear all items."""
        self.items.clear()

    def get_count(self) -> int:
        """Get current item count."""
        return len(self.items)

    def is_at_capacity(self) -> bool:
        """Check if at capacity."""
        return len(self.items) >= self.max_items

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "items": self.items.copy(),
            "count": len(self.items),
            "max": self.max_items,
            "at_capacity": self.is_at_capacity()
        }


# =============================================================================
# Factory Functions
# =============================================================================

def create_cognitive_safety_manager(state: CognitiveState) -> CognitiveSafetyManager:
    """
    Create cognitive safety manager from cognitive state.

    Args:
        state: Current cognitive state (reads cognitive_safety_enabled flag)

    Returns:
        Configured CognitiveSafetyManager
    """
    return CognitiveSafetyManager(enabled=getattr(state, 'cognitive_safety_enabled', getattr(state, 'adhd_enabled', False)))


# =============================================================================
# Backward Compatibility Aliases (deprecated, will be removed in v2.0)
# =============================================================================

ADHDConstraints = CognitiveSafetyConstraints
ADHDCheckResult = CognitiveSafetyCheckResult
ADHDSupportManager = CognitiveSafetyManager


def create_adhd_manager(state: CognitiveState) -> CognitiveSafetyManager:
    """
    Backward compatibility: Create cognitive safety manager.

    DEPRECATED: Use create_cognitive_safety_manager() instead.
    """
    return create_cognitive_safety_manager(state)


__all__ = [
    # New names (preferred)
    'CognitiveSafetyConstraints', 'CognitiveSafetyCheckResult',
    'CognitiveSafetyManager', 'create_cognitive_safety_manager',
    # Backward compatibility aliases (deprecated)
    'ADHDConstraints', 'ADHDCheckResult', 'ADHDSupportManager', 'create_adhd_manager',
    # Shared (no name change)
    'RecoveryOption', 'RECOVERY_OPTIONS', 'WorkingMemoryTracker'
]
