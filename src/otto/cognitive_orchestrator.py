"""
Cognitive Orchestrator
======================

Ties together all cognitive modules in the 5-Phase NEXUS Pipeline.

Pipeline:
1. DETECT  - PRISM signal extraction
2. CASCADE - Constitutional/safety gates + Cognitive Safety MoE expert routing
3. LOCK    - Parameter locking with MAX3 bounds
4. EXECUTE - Decision engine routing (work/delegate/protect)
5. UPDATE  - RC^+xi convergence tracking

ThinkingMachines [He2025] Compliance:
- State snapshot BEFORE processing (batch-invariance)
- FIXED evaluation order (5 phases, no reordering)
- FIXED signal priority (emotional > mode > domain > task)
- FIXED expert priority (Validator > ... > Direct)
- LOCKED parameters during generation
- Deterministic checksums

Usage:
    orchestrator = CognitiveOrchestrator()
    result = orchestrator.process_message("help me implement this feature")
    print(result.to_anchor())  # [EXEC:a3f2b8|direct|Cortex|30000ft|standard]
"""

import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import logging

# Cognitive modules
from .prism_detector import PRISMDetector, SignalVector, create_detector
from .expert_router import ExpertRouter, Expert, RoutingResult, create_router
from .parameter_locker import (
    ParameterLocker, LockedParams, LockResult, ThinkDepth, Paradigm, create_locker
)
from .convergence_tracker import (
    ConvergenceTracker, ConvergenceResult, AttractorBasin, create_tracker
)
from .cognitive_state import (
    CognitiveState, CognitiveStateManager, BurnoutLevel, EnergyLevel,
    MomentumPhase, CognitiveMode, Altitude
)

logger = logging.getLogger(__name__)


# =============================================================================
# NEXUS Result
# =============================================================================

@dataclass
class NexusResult:
    """
    Complete result from the 5-Phase NEXUS Pipeline.

    Contains all phase outputs for dashboard visualization and logging.
    """
    # Phase 1: DETECT
    signals: SignalVector

    # Phase 2: CASCADE
    routing: RoutingResult

    # Phase 3: LOCK
    lock: LockResult

    # Phase 5: UPDATE
    convergence: ConvergenceResult

    # Metadata
    timestamp: float = field(default_factory=time.time)
    processing_time_ms: float = 0.0
    state_checksum: str = ""

    def to_anchor(self) -> str:
        """Get anchor string for embedding in responses."""
        return self.lock.params.to_anchor()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for WebSocket/dashboard."""
        return {
            # Phase 1: DETECT - PRISM signals
            "signals_emotional": self._get_top_signal(self.signals.emotional),
            "signals_mode": self.signals.mode_detected,
            "signals_domain": list(self.signals.domain.keys()) if self.signals.domain else None,
            "signals_task": self.signals.primary_task,
            "current_phase": "execute",  # After processing, we're at execute

            # Phase 2: CASCADE - Expert routing
            "constitutional_pass": self.routing.constitutional_pass,
            "safety_gate_pass": self.routing.safety_gate_pass,
            "safety_redirect": self.routing.safety_redirect,
            "selected_expert": self.routing.expert.value,
            "expert_trigger": self.routing.trigger,

            # Phase 3: LOCK - Parameter locking
            "lock_status": self.lock.status.value,
            "reflection_iteration": self.lock.params.reflection_iteration,
            "locked_expert": self.lock.params.expert,
            "locked_paradigm": self.lock.params.paradigm,
            "locked_altitude": self.lock.params.altitude,
            "locked_think_depth": self.lock.params.think_depth,
            "lock_checksum": self.lock.params.checksum,

            # Phase 5: UPDATE - Convergence
            "epistemic_tension": self.convergence.epistemic_tension,
            "epsilon": 0.1,
            "attractor_basin": self.convergence.attractor_basin.value,
            "stable_exchanges": self.convergence.stable_exchanges,
            "converged": self.convergence.converged,
            "feedback_active": True,

            # Metadata
            "timestamp": self.timestamp,
            "processing_time_ms": self.processing_time_ms,
            "state_checksum": self.state_checksum
        }

    def _get_top_signal(self, signals: Dict[str, float]) -> Optional[str]:
        """Get top signal from dict."""
        if not signals:
            return None
        return max(signals.items(), key=lambda x: x[1])[0]


# =============================================================================
# Cognitive Orchestrator
# =============================================================================

class CognitiveOrchestrator:
    """
    Orchestrates the 5-Phase NEXUS Pipeline.

    This is the main entry point for cognitive processing. It:
    1. Takes a state snapshot (batch-invariance)
    2. Runs PRISM detection (DETECT)
    3. Routes to expert (CASCADE)
    4. Locks parameters (LOCK)
    5. Updates convergence (UPDATE)
    6. Commits state changes atomically
    """

    def __init__(
        self,
        state_manager: Optional[CognitiveStateManager] = None,
        detector: Optional[PRISMDetector] = None,
        router: Optional[ExpertRouter] = None,
        locker: Optional[ParameterLocker] = None,
        tracker: Optional[ConvergenceTracker] = None
    ):
        """
        Initialize orchestrator with cognitive modules.

        Args:
            state_manager: State persistence manager (creates default if None)
            detector: PRISM signal detector (creates default if None)
            router: Expert router (creates default if None)
            locker: Parameter locker (creates default if None)
            tracker: Convergence tracker (creates default if None)
        """
        self.state_manager = state_manager or CognitiveStateManager()
        self.detector = detector or create_detector()
        self.router = router or create_router()
        self.locker = locker or create_locker()
        self.tracker = tracker or create_tracker()

        self._last_result: Optional[NexusResult] = None

    def process_message(
        self,
        message: str,
        context: Dict[str, Any] = None,
        requested_depth: ThinkDepth = ThinkDepth.STANDARD
    ) -> NexusResult:
        """
        Process a message through the 5-Phase NEXUS Pipeline.

        ThinkingMachines [He2025]: Fixed evaluation order, deterministic routing.

        Args:
            message: The user message to process
            context: Optional context (active domain, etc.)
            requested_depth: User-requested thinking depth

        Returns:
            NexusResult with all phase outputs
        """
        start_time = time.time()
        context = context or {}

        # =================================================================
        # STEP 0: STATE SNAPSHOT (ThinkingMachines [He2025])
        # =================================================================
        state = self.state_manager.get_state()
        snapshot = state.snapshot()
        state_checksum = snapshot.checksum()

        logger.info(f"NEXUS Pipeline starting: state={state_checksum}")

        # =================================================================
        # PHASE 1: DETECT (PRISM Signal Extraction)
        # =================================================================
        logger.debug("Phase 1: DETECT")

        # Check for ALL CAPS
        caps_detected = self.detector.detect_caps_anger(message)

        # Detect signals with FIXED priority order
        signals = self.detector.detect(message, context)

        logger.debug(f"  Signals: emotional={signals.emotional_score:.2f}, "
                     f"mode={signals.mode_detected}, task={signals.primary_task}")

        # =================================================================
        # PHASE 2: CASCADE (Expert Routing)
        # =================================================================
        logger.debug("Phase 2: CASCADE")

        # Detect task completion from signals (enables Celebrator expert)
        task_completed = signals.task_completed()

        routing = self.router.route(
            signals=signals,
            burnout=snapshot.burnout_level,
            energy=snapshot.energy_level,
            momentum=snapshot.momentum_phase,
            mode=snapshot.mode.value,
            tangent_budget=snapshot.tangent_budget,
            task_completed=task_completed,
            caps_detected=caps_detected
        )

        logger.debug(f"  Routing: expert={routing.expert.value}, "
                     f"trigger={routing.trigger}, "
                     f"safety_redirect={routing.safety_redirect}")

        # =================================================================
        # PHASE 3: LOCK (Parameter Locking)
        # =================================================================
        logger.debug("Phase 3: LOCK")

        lock = self.locker.lock(
            routing=routing,
            burnout=snapshot.burnout_level,
            energy=snapshot.energy_level,
            altitude=snapshot.altitude,
            requested_depth=requested_depth,
            mode=snapshot.mode.value,
            epistemic_tension=snapshot.epistemic_tension,
            reflection_count=snapshot.reflection_count  # Batch-invariance: from snapshot
        )

        logger.debug(f"  Lock: {lock.params.to_anchor()}, "
                     f"safety_capped={lock.safety_capped}")

        # =================================================================
        # PHASE 4: EXECUTE (handled externally by decision engine)
        # =================================================================
        # The orchestrator prepares params; execution happens in Claude's response

        # =================================================================
        # PHASE 5: UPDATE (Convergence Tracking)
        # =================================================================
        logger.debug("Phase 5: UPDATE")

        # Map locked params back to enums for convergence tracking
        paradigm = Paradigm.CORTEX if lock.params.paradigm == "Cortex" else Paradigm.MYCELIUM

        convergence = self.tracker.update(
            expert=routing.expert,
            paradigm=paradigm,
            burnout=snapshot.burnout_level,
            momentum=snapshot.momentum_phase,
            altitude=snapshot.altitude
        )

        logger.debug(f"  Convergence: xi={convergence.epistemic_tension:.3f}, "
                     f"attractor={convergence.attractor_basin.value}, "
                     f"stable={convergence.stable_exchanges}/3, "
                     f"converged={convergence.converged}")

        # =================================================================
        # STEP 6: COMMIT STATE CHANGES
        # =================================================================
        # Calculate new reflection_count (batch-invariance: update AFTER processing)
        new_reflection_count = snapshot.reflection_count + 1

        # Reset reflection count on early convergence
        if lock.converged:
            logger.info("Early convergence detected - resetting reflection count")
            new_reflection_count = 0

        state_updates = {
            "exchange_count": snapshot.exchange_count + 1,
            "reflection_count": new_reflection_count,  # Batch-invariance: increment after processing
            "convergence_attractor": convergence.attractor_basin.value,
            "epistemic_tension": convergence.epistemic_tension,
            "stable_exchanges": convergence.stable_exchanges
        }

        # Update mode based on signals
        if signals.mode_detected:
            mode_map = {
                "exploring": CognitiveMode.EXPLORING,
                "focused": CognitiveMode.FOCUSED,
                "teaching": CognitiveMode.TEACHING,
                "recovery": CognitiveMode.RECOVERY
            }
            if signals.mode_detected in mode_map:
                state_updates["mode"] = mode_map[signals.mode_detected]

        self.state_manager.batch_update(state_updates)

        # =================================================================
        # BUILD RESULT
        # =================================================================
        processing_time = (time.time() - start_time) * 1000

        result = NexusResult(
            signals=signals,
            routing=routing,
            lock=lock,
            convergence=convergence,
            processing_time_ms=processing_time,
            state_checksum=state_checksum
        )

        self._last_result = result

        logger.info(f"NEXUS Pipeline complete: {result.to_anchor()} ({processing_time:.1f}ms)")

        return result

    def get_last_result(self) -> Optional[NexusResult]:
        """Get the last processing result."""
        return self._last_result

    def get_state(self) -> CognitiveState:
        """Get current cognitive state."""
        return self.state_manager.get_state()

    def reset_session(self) -> None:
        """Reset session state (new task/session)."""
        self.locker.reset()
        self.tracker.reset()
        self.state_manager.reset()
        self._last_result = None
        logger.info("Session reset")

    def calibrate(self, focus_level: str = None, urgency: str = None) -> None:
        """
        Calibrate cognitive state from non-invasive questions.

        Args:
            focus_level: 'scattered', 'moderate', or 'locked_in'
            urgency: 'relaxed', 'moderate', or 'deadline'
        """
        self.state_manager.calibrate(focus_level, urgency)

    def update_burnout(self, level: BurnoutLevel) -> None:
        """Update burnout level."""
        self.state_manager.batch_update({"burnout_level": level})

    def update_energy(self, level: EnergyLevel) -> None:
        """Update energy level."""
        self.state_manager.batch_update({"energy_level": level})

    def complete_task(self) -> None:
        """Record task completion."""
        state = self.state_manager.get_state()
        state.complete_task()
        self.state_manager.save()


# =============================================================================
# Factory Function
# =============================================================================

def create_orchestrator() -> CognitiveOrchestrator:
    """Create a CognitiveOrchestrator instance with default modules."""
    return CognitiveOrchestrator()


__all__ = [
    'NexusResult', 'CognitiveOrchestrator', 'create_orchestrator'
]
