"""
Dashboard Bridge
================

Connects the CognitiveOrchestrator to the WebSocket dashboard.

Maps NexusResult → WebSocket CognitiveState fields for real-time visualization
of the 5-Phase NEXUS Pipeline.

Usage:
    from dashboard_bridge import DashboardBridge

    bridge = DashboardBridge(orchestrator, websocket_server)
    result = bridge.process_and_broadcast("help me implement this")
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from .cognitive_orchestrator import CognitiveOrchestrator, NexusResult, create_orchestrator
from .cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel, MomentumPhase
from .expert_router import Expert

logger = logging.getLogger(__name__)


# =============================================================================
# Decision Mode Derivation
# =============================================================================

def _derive_decision_mode(result: NexusResult) -> str:
    """
    Derive decision mode from routing result.

    Decision modes (work/delegate/protect):
    - protect: Safety gate fired, protecting user from overload
    - delegate: Guidance/breakdown mode (Scaffolder, Socratic)
    - work: Direct execution mode

    Args:
        result: NexusResult from pipeline

    Returns:
        "work", "delegate", or "protect"
    """
    # Safety redirect = protect mode
    if result.routing.safety_redirect:
        return "protect"

    # Scaffolder/Socratic = delegate (guiding/breaking down)
    if result.routing.expert in (Expert.SCAFFOLDER, Expert.SOCRATIC):
        return "delegate"

    # Restorer with crashed momentum = protect
    if result.routing.expert == Expert.RESTORER:
        return "protect"

    # Default = work
    return "work"


def _estimate_working_memory(result: NexusResult, state: CognitiveState) -> int:
    """
    Estimate working memory load from active signals and state.

    Based on cognitive science (Miller's Law): humans can hold 7±2 items.
    We track active concerns as working memory load.

    Args:
        result: NexusResult from pipeline
        state: Current CognitiveState

    Returns:
        Estimated working memory items (0-5+)
    """
    items = 0

    # Active emotional concerns add cognitive load
    if result.signals.emotional:
        items += min(len(result.signals.emotional), 2)

    # Active task adds 1 item
    if result.signals.primary_task:
        items += 1

    # Domain context adds 1 item
    if result.signals.primary_domain:
        items += 1

    # Mode tracking adds 1 item if not default
    if result.signals.mode_detected and result.signals.mode_detected != "focused":
        items += 1

    # Tasks in progress add to load
    if state.tasks_completed > 0:
        items += min(state.tasks_completed, 2)

    return min(items, 5)  # Cap at 5 (cognitive limit)


# =============================================================================
# Dashboard State Mapper
# =============================================================================

def map_nexus_to_dashboard(result: NexusResult, state: CognitiveState) -> Dict[str, Any]:
    """
    Map NexusResult + CognitiveState to dashboard WebSocket state.

    This maps the full 5-phase pipeline output to the fields expected
    by the React dashboard.

    Args:
        result: Output from CognitiveOrchestrator.process_message()
        state: Current CognitiveState

    Returns:
        Dict matching WebSocket CognitiveState schema
    """
    # Get priority signal for display
    priority_cat, priority_sig, priority_score = result.signals.get_priority_signal()

    # Derive decision mode from routing (work/delegate/protect)
    decision_mode = _derive_decision_mode(result)

    # Estimate working memory load from active signals
    working_memory_used = _estimate_working_memory(result, state)

    return {
        # === EXISTING FIELDS (backward compatible) ===
        "burnout_level": state.burnout_level.value.upper(),
        "decision_mode": decision_mode,
        "momentum_phase": state.momentum_phase.value,
        "energy_level": state.energy_level.value,
        "working_memory_used": working_memory_used,
        "tangent_budget": state.tangent_budget,
        "altitude": _format_altitude(state.altitude.value),
        "paradigm": result.lock.params.paradigm,
        "body_check_needed": state.check_body_check_needed(),
        "current_task": None,
        "tasks_completed": state.tasks_completed,
        "session_minutes": int((state.last_activity - state.session_start) / 60),

        # === PHASE 1: DETECT - PRISM Signals ===
        "signals_emotional": _get_top_emotional(result.signals.emotional),
        "signals_mode": result.signals.mode_detected,
        "signals_domain": list(result.signals.domain.keys()) if result.signals.domain else None,
        "signals_task": result.signals.primary_task,
        "current_phase": "detect",  # Will transition through phases

        # === PHASE 2: CASCADE - Expert Routing ===
        "constitutional_pass": result.routing.constitutional_pass,
        "safety_gate_pass": result.routing.safety_gate_pass,
        "safety_redirect": result.routing.safety_redirect,
        "selected_expert": result.routing.expert.value,
        "expert_trigger": result.routing.trigger,

        # === PHASE 3: LOCK - Parameter Locking ===
        "lock_status": result.lock.status.value,
        "reflection_iteration": result.lock.params.reflection_iteration,
        "locked_expert": result.lock.params.expert,
        "locked_paradigm": result.lock.params.paradigm,
        "locked_altitude": result.lock.params.altitude,
        "locked_think_depth": result.lock.params.think_depth,
        "lock_checksum": result.lock.params.checksum,

        # === PHASE 5: UPDATE - RC^+xi Convergence ===
        "epistemic_tension": result.convergence.epistemic_tension,
        "epsilon": 0.1,
        "attractor_basin": result.convergence.attractor_basin.value,
        "stable_exchanges": result.convergence.stable_exchanges,
        "converged": result.convergence.converged,
        "feedback_active": True
    }


def _format_altitude(altitude_value: int) -> str:
    """Format altitude for display."""
    altitude_map = {
        30000: "30000ft",
        15000: "15000ft",
        5000: "5000ft",
        0: "Ground"
    }
    return altitude_map.get(altitude_value, "30000ft")


def _get_top_emotional(emotional_signals: Dict[str, float]) -> Optional[str]:
    """Get top emotional signal."""
    if not emotional_signals:
        return None
    return max(emotional_signals.items(), key=lambda x: x[1])[0]


# =============================================================================
# Dashboard Bridge
# =============================================================================

class DashboardBridge:
    """
    Bridge between CognitiveOrchestrator and WebSocket dashboard.

    Handles:
    - Processing messages through the NEXUS pipeline
    - Mapping results to dashboard state
    - Writing state to file for WebSocket server to broadcast
    - Phase transition animations

    State file: ~/.orchestra/state/cognitive_state.json (shared with CognitiveStateManager)
    """

    # State file path (read by WebSocket server)
    # Must match CognitiveStateManager.DEFAULT_STATE_DIR / DEFAULT_STATE_FILE
    STATE_DIR = Path.home() / ".orchestra" / "state"
    STATE_FILE = STATE_DIR / "cognitive_state.json"

    def __init__(
        self,
        orchestrator: Optional[CognitiveOrchestrator] = None
    ):
        """
        Initialize bridge.

        Args:
            orchestrator: CognitiveOrchestrator instance (creates default if None)
        """
        self.orchestrator = orchestrator or create_orchestrator()
        self._ensure_state_dir()

    def _ensure_state_dir(self) -> None:
        """Ensure state directory exists."""
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def process_and_broadcast(
        self,
        message: str,
        context: Dict[str, Any] = None
    ) -> NexusResult:
        """
        Process message and broadcast state to dashboard.

        This is the main entry point for integration with Claude Code.

        Args:
            message: User message to process
            context: Optional context dict

        Returns:
            NexusResult from pipeline
        """
        # Run through NEXUS pipeline
        result = self.orchestrator.process_message(message, context)

        # Map to dashboard state
        state = self.orchestrator.get_state()
        dashboard_state = map_nexus_to_dashboard(result, state)

        # Write to state file (WebSocket server will broadcast)
        self._write_state(dashboard_state)

        logger.info(f"Dashboard updated: {result.to_anchor()}")

        return result

    def _write_state(self, state: Dict[str, Any]) -> None:
        """Write state to file for WebSocket broadcast."""
        try:
            # Atomic write
            temp_file = self.STATE_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            temp_file.replace(self.STATE_FILE)
        except Exception as e:
            logger.error(f"Failed to write dashboard state: {e}")

    def update_phase(self, phase: str) -> None:
        """
        Update current phase (for animations).

        Called during pipeline execution to show phase transitions.

        Args:
            phase: One of 'detect', 'cascade', 'lock', 'execute', 'update'
        """
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE) as f:
                    state = json.load(f)
                state["current_phase"] = phase
                self._write_state(state)
        except Exception as e:
            logger.error(f"Failed to update phase: {e}")

    def get_current_state(self) -> Dict[str, Any]:
        """Get current dashboard state."""
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE) as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read state: {e}")
        return {}

    def set_burnout(self, level: str) -> None:
        """Set burnout level and update dashboard."""
        level_map = {
            "GREEN": BurnoutLevel.GREEN,
            "YELLOW": BurnoutLevel.YELLOW,
            "ORANGE": BurnoutLevel.ORANGE,
            "RED": BurnoutLevel.RED
        }
        if level.upper() in level_map:
            self.orchestrator.update_burnout(level_map[level.upper()])
            self._refresh_dashboard()

    def set_energy(self, level: str) -> None:
        """Set energy level and update dashboard."""
        level_map = {
            "high": EnergyLevel.HIGH,
            "medium": EnergyLevel.MEDIUM,
            "low": EnergyLevel.LOW,
            "depleted": EnergyLevel.DEPLETED
        }
        if level.lower() in level_map:
            self.orchestrator.update_energy(level_map[level.lower()])
            self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        """Refresh dashboard with current state."""
        state = self.orchestrator.get_state()
        last_result = self.orchestrator.get_last_result()

        if last_result:
            dashboard_state = map_nexus_to_dashboard(last_result, state)
            self._write_state(dashboard_state)
        else:
            # No result yet - write basic state
            basic_state = {
                "burnout_level": state.burnout_level.value.upper(),
                "momentum_phase": state.momentum_phase.value,
                "energy_level": state.energy_level.value,
                "current_phase": "detect"
            }
            self._write_state(basic_state)


# =============================================================================
# Factory Function
# =============================================================================

def create_bridge(orchestrator: Optional[CognitiveOrchestrator] = None) -> DashboardBridge:
    """Create a DashboardBridge instance."""
    return DashboardBridge(orchestrator=orchestrator)


__all__ = [
    'DashboardBridge', 'map_nexus_to_dashboard', 'create_bridge'
]
