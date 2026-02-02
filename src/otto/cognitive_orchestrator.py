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
from typing import Optional, Dict, Any, Union
import logging

# [He2025] Determinism utilities
from .determinism import sorted_max_key

# Cognitive modules
from .prism_detector import PRISMDetector, SignalVector, create_detector
# Knowledge layer for Phase 0 fast path
from .substrate.knowledge import get_unified_search, RetrievalResult
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

# Lazy imports to avoid circular dependency:
# - hooks module imports from cognitive_orchestrator
# - We import hooks/trails inside methods that use them

logger = logging.getLogger(__name__)

# Confidence threshold for knowledge fast path short-circuit
KNOWLEDGE_CONFIDENCE_THRESHOLD = 0.85


# =============================================================================
# Pattern Tracker (PATTERN Trail Learning)
# =============================================================================

class PatternTracker:
    """
    Tracks state transitions and deposits PATTERN trails for successful patterns.

    PATTERN trails record emergent learning from:
    - stuck → resolved: User went from stuck/overwhelmed to focused
    - momentum_up: Successful momentum transitions (cold_start→building, etc.)
    - recovery_success: Burnout/energy improved after intervention

    ThinkingMachines [He2025] Compliance:
    - Fixed evaluation order for pattern detection
    - Deterministic trail signals
    - State comparison uses snapshot values only
    """

    def __init__(self):
        self._previous_state: Optional[Dict[str, Any]] = None
        self._previous_detected_state: Optional[str] = None
        self._session_id: str = "pattern_tracker"

    def set_session_id(self, session_id: str) -> None:
        """Set session ID for trail attribution."""
        self._session_id = session_id

    def capture_before(
        self,
        state_snapshot: 'CognitiveState',
        detected_state: Optional[str] = None
    ) -> None:
        """
        Capture state BEFORE processing.

        Args:
            state_snapshot: Immutable state snapshot
            detected_state: PRISM-detected emotional state (stuck, overwhelmed, etc.)
        """
        self._previous_state = {
            "burnout": state_snapshot.burnout_level.value,
            "momentum": state_snapshot.momentum_phase.value,
            "energy": state_snapshot.energy_level.value,
            "mode": state_snapshot.mode.value,
        }
        self._previous_detected_state = detected_state

    def check_and_deposit(
        self,
        new_state: 'CognitiveState',
        new_detected_state: Optional[str] = None,
        expert_used: Optional[str] = None
    ) -> list:
        """
        Check for successful patterns and deposit PATTERN trails.

        Args:
            new_state: State after processing
            new_detected_state: New PRISM-detected state
            expert_used: Which expert handled this exchange

        Returns:
            List of patterns detected and deposited
        """
        if self._previous_state is None:
            return []

        patterns_deposited = []

        # 1. Check stuck → resolved
        stuck_states = {"stuck", "overwhelmed", "frustrated"}
        resolved_states = {"focused", None}  # None means no negative state detected

        if (self._previous_detected_state in stuck_states and
            new_detected_state in resolved_states):
            pattern = self._deposit_pattern(
                signal=f"stuck_resolved|from:{self._previous_detected_state}|expert:{expert_used or 'unknown'}",
                metadata={
                    "from_state": self._previous_detected_state,
                    "to_state": new_detected_state or "focused",
                    "expert": expert_used,
                    "pattern_type": "stuck_resolved"
                }
            )
            if pattern:
                patterns_deposited.append(pattern)

        # 2. Check momentum transitions (positive)
        momentum_upgrades = [
            ("cold_start", "building"),
            ("building", "rolling"),
            ("rolling", "peak"),
            ("crashed", "cold_start"),  # Recovery from crash
            ("crashed", "building"),    # Strong recovery from crash
        ]

        prev_momentum = self._previous_state["momentum"]
        new_momentum = new_state.momentum_phase.value

        for from_m, to_m in momentum_upgrades:
            if prev_momentum == from_m and new_momentum == to_m:
                pattern = self._deposit_pattern(
                    signal=f"momentum_up|{from_m}→{to_m}",
                    metadata={
                        "from_momentum": from_m,
                        "to_momentum": to_m,
                        "pattern_type": "momentum_up"
                    }
                )
                if pattern:
                    patterns_deposited.append(pattern)
                break

        # 3. Check recovery success (burnout improved)
        burnout_order = ["green", "yellow", "orange", "red"]
        prev_burnout_idx = burnout_order.index(self._previous_state["burnout"])
        new_burnout_idx = burnout_order.index(new_state.burnout_level.value)

        if new_burnout_idx < prev_burnout_idx:  # Improved (lower is better)
            pattern = self._deposit_pattern(
                signal=f"recovery_success|burnout|{self._previous_state['burnout']}→{new_state.burnout_level.value}",
                metadata={
                    "from_burnout": self._previous_state["burnout"],
                    "to_burnout": new_state.burnout_level.value,
                    "expert": expert_used,
                    "pattern_type": "recovery_burnout"
                }
            )
            if pattern:
                patterns_deposited.append(pattern)

        # 4. Check energy recovery
        energy_order = ["depleted", "low", "medium", "high"]
        prev_energy_idx = energy_order.index(self._previous_state["energy"])
        new_energy_idx = energy_order.index(new_state.energy_level.value)

        if new_energy_idx > prev_energy_idx:  # Improved (higher is better)
            pattern = self._deposit_pattern(
                signal=f"recovery_success|energy|{self._previous_state['energy']}→{new_state.energy_level.value}",
                metadata={
                    "from_energy": self._previous_state["energy"],
                    "to_energy": new_state.energy_level.value,
                    "pattern_type": "recovery_energy"
                }
            )
            if pattern:
                patterns_deposited.append(pattern)

        return patterns_deposited

    def _deposit_pattern(self, signal: str, metadata: dict) -> Optional[str]:
        """
        Deposit a PATTERN trail.

        Args:
            signal: Trail signal string
            metadata: Additional metadata

        Returns:
            Signal if deposited, None on error
        """
        try:
            from .trails import Trail, TrailType, get_store

            store = get_store()
            trail = Trail(
                trail_type=TrailType.PATTERN,
                path="cognitive_orchestrator",  # Attach to orchestrator
                signal=signal,
                deposited_by=self._session_id,
                metadata=metadata,
                half_life_days=14.0  # PATTERN trails last longer (2 weeks)
            )

            store.deposit(trail)
            logger.info(f"PATTERN trail deposited: {signal}")
            return signal

        except Exception as e:
            logger.warning(f"Failed to deposit PATTERN trail: {e}")
            return None


# =============================================================================
# Knowledge Result (Phase 0 Fast Path)
# =============================================================================

@dataclass
class KnowledgeResult:
    """
    Result from Phase 0 Knowledge Fast Path.

    When a factual query matches high-confidence knowledge (≥0.85),
    the pipeline short-circuits here instead of running full NEXUS.

    ThinkingMachines [He2025] Compliance:
    - Fixed confidence threshold (0.85)
    - Deterministic short-circuit decision
    """
    retrieval: RetrievalResult
    query: str
    short_circuited: bool = True
    processing_time_ms: float = 0.0

    @property
    def found(self) -> bool:
        """Whether knowledge was found."""
        return self.retrieval.found

    @property
    def top_prim(self):
        """Get the top-scoring prim if any."""
        if self.retrieval.prims:
            return self.retrieval.prims[0]
        return None

    def to_anchor(self) -> str:
        """Get anchor string for embedding in responses."""
        prim = self.top_prim
        path = prim.canonical_path if prim else "unknown"
        conf = f"{self.retrieval.top_confidence:.2f}"
        return f"[KNOW:{path}|conf={conf}]"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for WebSocket/dashboard."""
        prim = self.top_prim
        return {
            "phase": "knowledge",
            "short_circuited": self.short_circuited,
            "query": self.query,
            "found": self.found,
            "path": prim.canonical_path if prim else None,
            "confidence": self.retrieval.top_confidence,
            "summary": prim.summary if prim else None,
            "retrieval_method": self.retrieval.retrieval_method,
            "processing_time_ms": self.processing_time_ms,
        }


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
        """Get top signal from dict.

        [He2025] Uses sorted_max_key for deterministic tie-breaking.
        """
        if not signals:
            return None
        return sorted_max_key(signals)


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
        self._session_id: str = f"session_{int(time.time())}"

        # Initialize pattern tracker for PATTERN trail learning
        self.pattern_tracker = PatternTracker()
        self.pattern_tracker.set_session_id(self._session_id)

        # Initialize hook system with default hooks (lazy import to avoid circular)
        from .hooks import setup_default_hooks
        setup_default_hooks()

        # Fire SESSION_START hook
        self._fire_session_start_hook()

    def process_message(
        self,
        message: str,
        context: Dict[str, Any] = None,
        requested_depth: ThinkDepth = ThinkDepth.STANDARD
    ) -> Union[NexusResult, KnowledgeResult]:
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

        # [He2025] Capture state for PATTERN trail learning (before processing)
        self.pattern_tracker.capture_before(snapshot)

        logger.info(f"NEXUS Pipeline starting: state={state_checksum}")

        # =================================================================
        # PHASE 0: RETRIEVE (Knowledge Fast Path)
        # =================================================================
        # Check if this is a factual query that can be answered from knowledge
        if self.detector.detect_factual_query(message):
            logger.debug("Phase 0: RETRIEVE - Factual query detected")
            knowledge = get_unified_search()
            result = knowledge.search(message, max_results=1)

            if result.found and result.top_confidence >= KNOWLEDGE_CONFIDENCE_THRESHOLD:
                # Short-circuit: Return knowledge directly
                logger.info(f"Phase 0: Knowledge hit - {result.prims[0].canonical_path} "
                           f"(conf={result.top_confidence:.2f})")
                return self._build_knowledge_result(result, message, start_time)

            logger.debug(f"Phase 0: No high-confidence match "
                        f"(found={result.found}, conf={result.top_confidence:.2f})")

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

        # Deposit DECISION trail for routing choice
        # [He2025] Deterministic trail deposit - same routing = same trail
        self._deposit_decision_trail(
            expert=routing.expert.value,
            trigger=routing.trigger,
            alternatives=[e.value for e in routing.considered_experts] if hasattr(routing, 'considered_experts') else None
        )

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
        # PATTERN TRAIL DETECTION
        # =================================================================
        # [He2025] Check for successful patterns after state commit
        # Get detected emotional state from PRISM signals
        detected_emotional_state = None
        if signals.emotional:
            detected_emotional_state = sorted_max_key(signals.emotional)

        # Get updated state for pattern comparison
        updated_state = self.state_manager.get_state()
        patterns = self.pattern_tracker.check_and_deposit(
            new_state=updated_state,
            new_detected_state=detected_emotional_state,
            expert_used=routing.expert.value
        )

        if patterns:
            logger.info(f"PATTERN trails deposited: {patterns}")

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
        # Lazy import to avoid circular dependency
        from .hooks import execute_hooks, HookEvent, HookContext

        # Fire SESSION_END hook for current session
        end_context = HookContext(
            event=HookEvent.SESSION_END,
            session_id=self._session_id,
            metadata={"reason": "reset"}
        )
        execute_hooks(end_context)

        # Reset cognitive modules
        self.locker.reset()
        self.tracker.reset()
        self.state_manager.reset()
        self._last_result = None

        # Generate new session ID and fire SESSION_START
        self._session_id = f"session_{int(time.time())}"
        self.pattern_tracker.set_session_id(self._session_id)
        self._fire_session_start_hook()

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

    def _build_knowledge_result(
        self,
        retrieval: RetrievalResult,
        query: str,
        start_time: float
    ) -> KnowledgeResult:
        """
        Build result for knowledge fast path short-circuit.

        Args:
            retrieval: The knowledge retrieval result
            query: Original user query
            start_time: Processing start time for timing

        Returns:
            KnowledgeResult with short_circuited=True
        """
        processing_time = (time.time() - start_time) * 1000
        return KnowledgeResult(
            retrieval=retrieval,
            query=query,
            short_circuited=True,
            processing_time_ms=processing_time
        )

    def _fire_session_start_hook(self) -> None:
        """
        Fire SESSION_START hook for trail-based initialization.

        ThinkingMachines [He2025]: Deterministic hook execution order.
        """
        # Lazy import to avoid circular dependency
        from .hooks import execute_hooks, HookEvent, HookContext

        context = HookContext(
            event=HookEvent.SESSION_START,
            session_id=self._session_id,
            metadata={"orchestrator_version": "7.1.0"}
        )

        results = execute_hooks(context)

        for result in results:
            if result.context_injection:
                logger.debug(f"SESSION_START hook '{result.hook_name}' injected context")
            if result.trails_deposited > 0:
                logger.debug(f"SESSION_START hook '{result.hook_name}' deposited {result.trails_deposited} trails")

    def _deposit_decision_trail(
        self,
        expert: str,
        trigger: str,
        alternatives: Optional[list] = None,
        context_path: str = "cognitive_orchestrator"
    ) -> None:
        """
        Deposit a DECISION trail recording routing choice.

        DECISION trails record why choices were made, enabling:
        - Historical pattern analysis
        - Debugging of routing decisions
        - Learning from successful/failed paths

        ThinkingMachines [He2025]: Trail deposits are idempotent and deterministic.

        Args:
            expert: The expert that was selected
            trigger: What triggered this selection
            alternatives: Other experts that were considered
            context_path: File path context for the trail
        """
        try:
            # Lazy import to avoid circular dependency
            from .trails import Trail, TrailType, get_store

            store = get_store()
            alternatives_str = ",".join(alternatives) if alternatives else "none"

            trail = Trail(
                trail_type=TrailType.DECISION,
                path=context_path,
                signal=f"routed_to:{expert}|trigger:{trigger}|alternatives:{alternatives_str}",
                deposited_by=self._session_id,
                metadata={
                    "expert": expert,
                    "trigger": trigger,
                    "alternatives": alternatives or [],
                    "timestamp": time.time()
                },
                half_life_days=7.0  # DECISION trails decay in 1 week
            )

            store.deposit(trail)
            logger.debug(f"DECISION trail deposited: {expert} (trigger={trigger})")

        except Exception as e:
            # Trail deposit failures should not break the pipeline
            logger.warning(f"Failed to deposit DECISION trail: {e}")


# =============================================================================
# Factory Function
# =============================================================================

def create_orchestrator() -> CognitiveOrchestrator:
    """Create a CognitiveOrchestrator instance with default modules."""
    return CognitiveOrchestrator()


__all__ = [
    'NexusResult', 'KnowledgeResult', 'CognitiveOrchestrator', 'create_orchestrator',
    'KNOWLEDGE_CONFIDENCE_THRESHOLD'
]
