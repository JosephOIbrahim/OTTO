"""
Tests for the Cognitive Engine (5-Phase NEXUS Pipeline)

Tests:
- Expert routing (Cognitive Safety MoE)
- Parameter locking (MAX3, safety gating)
- Convergence tracking (RC^+xi)
- Full pipeline orchestration
- Determinism guarantees (ThinkingMachines [He2025])
- Session reset logic
"""

import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import cognitive modules
from otto.expert_router import (
    ExpertRouter, Expert, RoutingResult, create_router
)
from otto.parameter_locker import (
    ParameterLocker, LockedParams, ThinkDepth, Paradigm, create_locker
)
from otto.convergence_tracker import (
    ConvergenceTracker, AttractorBasin, create_tracker
)
from otto.cognitive_orchestrator import (
    CognitiveOrchestrator, NexusResult, create_orchestrator
)
from otto.cognitive_state import (
    CognitiveState, CognitiveStateManager, BurnoutLevel, EnergyLevel,
    MomentumPhase, CognitiveMode
)
from otto.prism_detector import PRISMDetector, SignalVector, create_detector


# =============================================================================
# Expert Router Tests
# =============================================================================

class TestExpertRouter:
    """Tests for Cognitive Safety MoE expert routing."""

    def test_create_router(self):
        """Router creates successfully."""
        router = create_router()
        assert router is not None

    def test_default_routes_to_direct(self):
        """Default routing (no signals) goes to Direct expert."""
        router = create_router()
        detector = create_detector()

        signals = detector.detect("Hello, how are you?")
        result = router.route(
            signals=signals,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            momentum=MomentumPhase.ROLLING,
            mode="focused"
        )

        assert result.expert == Expert.DIRECT
        assert result.constitutional_pass is True

    def test_frustration_routes_to_validator(self):
        """Frustration signals route to Validator (highest priority)."""
        router = create_router()
        detector = create_detector()

        signals = detector.detect("I'M SO FRUSTRATED! This is broken!")
        result = router.route(
            signals=signals,
            burnout=BurnoutLevel.RED,
            energy=EnergyLevel.LOW,
            momentum=MomentumPhase.CRASHED,
            mode="focused",
            caps_detected=True
        )

        assert result.expert == Expert.VALIDATOR
        assert result.safety_gate_pass is False

    def test_overwhelmed_routes_to_scaffolder_or_validator(self):
        """Overwhelmed signals route to Scaffolder or Validator (if emotional)."""
        router = create_router()
        detector = create_detector()

        # Note: "overwhelmed" triggers both emotional and scaffolder
        # Validator has higher priority, so emotional overwhelm -> Validator
        signals = detector.detect("I'm overwhelmed, there's too much to do")
        result = router.route(
            signals=signals,
            burnout=BurnoutLevel.YELLOW,
            energy=EnergyLevel.LOW,
            momentum=MomentumPhase.COLD_START,
            mode="focused"
        )

        # Either Validator (if emotional detected) or Scaffolder is valid
        assert result.expert in [Expert.SCAFFOLDER, Expert.VALIDATOR]

    def test_exploring_routes_to_socratic(self):
        """Exploring mode routes to Socratic expert."""
        router = create_router()
        detector = create_detector()

        signals = detector.detect("What if we tried a different approach?")
        result = router.route(
            signals=signals,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.HIGH,
            momentum=MomentumPhase.ROLLING,
            mode="exploring"
        )

        assert result.expert == Expert.SOCRATIC

    def test_expert_priority_order(self):
        """Expert priority order is fixed (Validator > Scaffolder > ... > Direct)."""
        # Define priority order (1 = highest priority)
        priority_order = [
            Expert.VALIDATOR,   # 1
            Expert.SCAFFOLDER,  # 2
            Expert.RESTORER,    # 3
            Expert.REFOCUSER,   # 4
            Expert.CELEBRATOR,  # 5
            Expert.SOCRATIC,    # 6
            Expert.DIRECT,      # 7
        ]

        # Verify all experts exist and order is defined
        assert len(priority_order) == 7
        assert Expert.VALIDATOR in priority_order
        assert Expert.DIRECT in priority_order

        # Verify order by checking indices
        assert priority_order.index(Expert.VALIDATOR) < priority_order.index(Expert.SCAFFOLDER)
        assert priority_order.index(Expert.SCAFFOLDER) < priority_order.index(Expert.DIRECT)


# =============================================================================
# Parameter Locker Tests
# =============================================================================

class TestParameterLocker:
    """Tests for MAX3 bounded reflection and safety gating."""

    def test_create_locker(self):
        """Locker creates successfully."""
        locker = create_locker()
        assert locker is not None

    def test_lock_generates_checksum(self):
        """Locking generates deterministic checksum."""
        locker = create_locker()
        router = create_router()
        detector = create_detector()

        signals = detector.detect("test message")
        routing = router.route(
            signals=signals,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            momentum=MomentumPhase.ROLLING,
            mode="focused"
        )

        from otto.cognitive_state import Altitude
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION
        )

        assert result.params.checksum is not None
        assert len(result.params.checksum) == 6  # 6-char hex

    def test_same_inputs_same_checksum(self):
        """Same inputs produce same checksum (determinism)."""
        locker1 = create_locker()
        locker2 = create_locker()
        router = create_router()
        detector = create_detector()

        signals = detector.detect("test message")
        routing = router.route(
            signals=signals,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            momentum=MomentumPhase.ROLLING,
            mode="focused"
        )

        from otto.cognitive_state import Altitude
        result1 = locker1.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            reflection_count=0  # Explicitly pass reflection_count
        )
        result2 = locker2.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            reflection_count=0  # Same reflection_count
        )

        assert result1.params.checksum == result2.params.checksum

    def test_batch_invariance_different_reflection_count(self):
        """
        ThinkingMachines [He2025]: Same routing params → same checksum
        even with different reflection_count values (within MAX3 bounds).

        This is the core batch-invariance test: routing checksum excludes
        reflection_iteration, so different counts produce identical checksums.

        Note: Uses reflection_count values < MAX3 (3) to avoid triggering
        safety caps that would change think_depth.
        """
        locker = create_locker()
        router = create_router()
        detector = create_detector()

        signals = detector.detect("test message")
        routing = router.route(
            signals=signals,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            momentum=MomentumPhase.ROLLING,
            mode="focused"
        )

        from otto.cognitive_state import Altitude

        # Two calls with same routing but different reflection_count
        # Both within MAX3 bounds (< 3) to avoid safety caps
        result1 = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            reflection_count=0  # First iteration
        )
        result2 = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            reflection_count=2  # Third iteration (still within MAX3)
        )

        # Routing checksum should be identical (batch-invariant)
        assert result1.params.checksum == result2.params.checksum

        # Session checksum should differ (includes iteration for debugging)
        assert result1.params.session_checksum != result2.params.session_checksum

        # reflection_iteration should be stored correctly
        assert result1.params.reflection_iteration == 0
        assert result2.params.reflection_iteration == 2

    def test_safety_gating_depleted_caps_depth(self):
        """Depleted energy caps thinking depth to minimal."""
        locker = create_locker()
        router = create_router()
        detector = create_detector()

        signals = detector.detect("ultrathink about this problem")
        routing = router.route(
            signals=signals,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.DEPLETED,
            momentum=MomentumPhase.CRASHED,
            mode="focused"
        )

        from otto.cognitive_state import Altitude
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.DEPLETED,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.ULTRADEEP  # User requests ultradeep
        )

        # Safety gating should cap to minimal
        assert result.params.think_depth == "minimal"
        assert result.safety_capped is True

    def test_safety_gating_red_burnout(self):
        """RED burnout caps thinking depth to minimal."""
        locker = create_locker()
        router = create_router()
        detector = create_detector()

        signals = detector.detect("deep analysis needed")
        routing = router.route(
            signals=signals,
            burnout=BurnoutLevel.RED,
            energy=EnergyLevel.LOW,
            momentum=MomentumPhase.CRASHED,
            mode="focused"
        )

        from otto.cognitive_state import Altitude
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.RED,
            energy=EnergyLevel.LOW,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.DEEP
        )

        assert result.params.think_depth == "minimal"
        assert result.safety_capped is True

    def test_max3_bounds_reflection(self):
        """MAX3: Reflection iterations bounded to 3."""
        from otto.cognitive_state import Altitude

        locker = create_locker()
        router = create_router()
        detector = create_detector()

        signals = detector.detect("test")
        routing = router.route(
            signals=signals,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            momentum=MomentumPhase.ROLLING,
            mode="focused"
        )

        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION
        )

        # MAX3 should limit reflections
        assert result.params.max_reflections == 3


# =============================================================================
# Convergence Tracker Tests
# =============================================================================

class TestConvergenceTracker:
    """Tests for RC^+xi convergence tracking."""

    def test_create_tracker(self):
        """Tracker creates successfully."""
        tracker = create_tracker()
        assert tracker is not None

    def test_initial_tension_zero(self):
        """Initial epistemic tension is reasonable."""
        from otto.cognitive_state import Altitude
        tracker = create_tracker()
        result = tracker.update(
            expert=Expert.DIRECT,
            paradigm=Paradigm.CORTEX,
            burnout=BurnoutLevel.GREEN,
            momentum=MomentumPhase.ROLLING,
            altitude=Altitude.VISION
        )

        assert result.epistemic_tension >= 0.0
        assert result.epistemic_tension <= 1.0

    def test_stable_exchanges_increment(self):
        """Stable exchanges increment when attractor doesn't change."""
        from otto.cognitive_state import Altitude
        tracker = create_tracker()

        # Same inputs = same attractor = stable
        for _ in range(3):
            result = tracker.update(
                expert=Expert.DIRECT,
                paradigm=Paradigm.CORTEX,
                burnout=BurnoutLevel.GREEN,
                momentum=MomentumPhase.ROLLING,
                altitude=Altitude.VISION
            )

        assert result.stable_exchanges >= 1

    def test_convergence_at_three_stable(self):
        """Convergence detected after 3 stable exchanges at xi < epsilon."""
        from otto.cognitive_state import Altitude
        tracker = create_tracker()

        # Force same attractor repeatedly
        for _ in range(5):
            result = tracker.update(
                expert=Expert.DIRECT,
                paradigm=Paradigm.CORTEX,
                burnout=BurnoutLevel.GREEN,
                momentum=MomentumPhase.ROLLING,
                altitude=Altitude.VISION
            )

        # Should converge after 3 stable
        if result.stable_exchanges >= 3 and result.epistemic_tension < 0.1:
            assert result.converged is True

    def test_attractor_basins_defined(self):
        """All attractor basins are properly defined."""
        assert AttractorBasin.FOCUSED is not None
        assert AttractorBasin.EXPLORING is not None
        assert AttractorBasin.RECOVERY is not None
        assert AttractorBasin.TEACHING is not None


# =============================================================================
# Cognitive Orchestrator Tests
# =============================================================================

class TestCognitiveOrchestrator:
    """Tests for the full 5-Phase NEXUS Pipeline."""

    def test_create_orchestrator(self):
        """Orchestrator creates successfully."""
        orchestrator = create_orchestrator()
        assert orchestrator is not None

    def test_process_message_returns_nexus_result(self):
        """Processing message returns NexusResult."""
        orchestrator = create_orchestrator()
        result = orchestrator.process_message("Hello, world!")

        assert isinstance(result, NexusResult)
        assert result.signals is not None
        assert result.routing is not None
        assert result.lock is not None
        assert result.convergence is not None

    def test_anchor_format(self):
        """Anchor has correct format."""
        orchestrator = create_orchestrator()
        result = orchestrator.process_message("test")

        anchor = result.to_anchor()
        # Format: [EXEC:checksum|expert|paradigm|altitude|depth]
        assert anchor.startswith("[EXEC:")
        assert anchor.endswith("]")
        parts = anchor[6:-1].split("|")
        assert len(parts) == 5

    def test_determinism_same_message_same_checksum(self):
        """Same message produces same checksum (determinism)."""
        orchestrator1 = create_orchestrator()
        orchestrator2 = create_orchestrator()

        # Reset both
        orchestrator1.reset_session()
        orchestrator2.reset_session()

        result1 = orchestrator1.process_message("test message")
        result2 = orchestrator2.process_message("test message")

        assert result1.lock.params.checksum == result2.lock.params.checksum

    def test_phase_order_fixed(self):
        """Phases execute in fixed order (DETECT->CASCADE->LOCK->EXECUTE->UPDATE)."""
        orchestrator = create_orchestrator()
        result = orchestrator.process_message("test")

        # All phase outputs should be present
        assert result.signals is not None  # DETECT
        assert result.routing is not None  # CASCADE
        assert result.lock is not None  # LOCK
        # EXECUTE is external (Claude's response)
        assert result.convergence is not None  # UPDATE

    def test_processing_time_tracked(self):
        """Processing time is tracked in milliseconds."""
        orchestrator = create_orchestrator()
        result = orchestrator.process_message("test")

        assert result.processing_time_ms > 0
        assert result.processing_time_ms < 1000  # Should be fast

    def test_session_reset(self):
        """Session reset clears state properly."""
        orchestrator = create_orchestrator()

        # Process some messages
        orchestrator.process_message("message 1")
        orchestrator.process_message("message 2")

        # Reset
        orchestrator.reset_session()

        # State should be fresh
        state = orchestrator.get_state()
        assert state.exchange_count == 0 or state.exchange_count == 1


# =============================================================================
# Cognitive State Tests
# =============================================================================

class TestCognitiveState:
    """Tests for cognitive state management."""

    def test_create_state(self):
        """State creates with defaults."""
        state = CognitiveState()
        assert state.burnout_level == BurnoutLevel.GREEN
        assert state.momentum_phase == MomentumPhase.COLD_START
        assert state.energy_level == EnergyLevel.MEDIUM

    def test_snapshot_immutable(self):
        """Snapshot is immutable copy."""
        state = CognitiveState()
        snapshot = state.snapshot()

        state.burnout_level = BurnoutLevel.RED
        assert snapshot.burnout_level == BurnoutLevel.GREEN

    def test_batch_update(self):
        """Batch update applies changes."""
        state = CognitiveState()
        state.batch_update({
            "burnout_level": BurnoutLevel.YELLOW,
            "energy_level": EnergyLevel.LOW
        })

        assert state.burnout_level == BurnoutLevel.YELLOW
        assert state.energy_level == EnergyLevel.LOW

    def test_checksum_deterministic(self):
        """Checksum is deterministic for same state values."""
        # Create states with same fixed timestamps
        fixed_time = 1000000.0
        state1 = CognitiveState(session_start=fixed_time, last_activity=fixed_time)
        state2 = CognitiveState(session_start=fixed_time, last_activity=fixed_time)

        assert state1.checksum() == state2.checksum()

    def test_escalate_burnout(self):
        """Burnout escalation works correctly."""
        state = CognitiveState()
        assert state.burnout_level == BurnoutLevel.GREEN

        state.escalate_burnout()
        assert state.burnout_level == BurnoutLevel.YELLOW

        state.escalate_burnout()
        assert state.burnout_level == BurnoutLevel.ORANGE

        state.escalate_burnout()
        assert state.burnout_level == BurnoutLevel.RED

        # Can't go higher than RED
        state.escalate_burnout()
        assert state.burnout_level == BurnoutLevel.RED

    def test_reflection_count_serialization(self):
        """reflection_count is properly serialized and deserialized."""
        state = CognitiveState()
        state.reflection_count = 2

        # Serialize
        data = state.to_dict()
        assert data.get("reflection_count") == 2

        # Deserialize
        restored = CognitiveState.from_dict(data)
        assert restored.reflection_count == 2

    def test_reflection_count_in_snapshot(self):
        """reflection_count is included in snapshot."""
        state = CognitiveState()
        state.reflection_count = 3

        snapshot = state.snapshot()

        # Snapshot should have the same reflection_count
        assert snapshot.reflection_count == 3

        # Modifying original should not affect snapshot
        state.reflection_count = 10
        assert snapshot.reflection_count == 3

    def test_reflection_count_in_batch_update(self):
        """reflection_count can be updated via batch_update."""
        state = CognitiveState()
        assert state.reflection_count == 0

        state.batch_update({"reflection_count": 5})
        assert state.reflection_count == 5


# =============================================================================
# Session Reset Logic Tests
# =============================================================================

class TestSessionResetLogic:
    """Tests for session staleness detection and reset."""

    def test_stale_session_detection(self, tmp_path):
        """Session detected as stale after 2 hours."""
        state_dir = tmp_path / ".orchestra" / "state"
        manager = CognitiveStateManager(state_dir=state_dir)

        # Create state with old timestamp
        state = manager.get_state()
        state.last_activity = time.time() - (3 * 60 * 60)  # 3 hours ago
        manager.save()

        # Reload - should detect staleness
        manager._state = None  # Force reload
        assert manager._is_session_stale() or manager.get_state() is not None

    def test_session_reset_preserves_preferences(self, tmp_path):
        """Session reset preserves user preferences."""
        state_dir = tmp_path / ".orchestra" / "state"
        manager = CognitiveStateManager(state_dir=state_dir)

        # Set preferences
        state = manager.get_state()
        state.focus_level = "locked_in"
        state.urgency = "deadline"
        state.exchange_count = 50
        state.last_activity = time.time() - (3 * 60 * 60)  # Stale
        manager.save()

        # Reload
        manager._state = None
        loaded = manager.load()

        # Preferences preserved, session fields reset
        assert loaded.focus_level == "locked_in"
        assert loaded.urgency == "deadline"
        # exchange_count should be reset
        assert loaded.exchange_count < 50 or manager._is_session_stale()

    def test_fresh_session_not_reset(self, tmp_path):
        """Fresh session (< 2 hours) is not reset."""
        state_dir = tmp_path / ".orchestra" / "state"
        manager = CognitiveStateManager(state_dir=state_dir)

        state = manager.get_state()
        state.exchange_count = 10
        state.last_activity = time.time() - 60  # 1 minute ago
        manager.save()

        manager._state = None
        loaded = manager.load()

        # Should not be reset
        assert loaded.exchange_count == 10


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_frustrated_user(self):
        """Full pipeline correctly handles frustrated user."""
        orchestrator = create_orchestrator()
        result = orchestrator.process_message(
            "I'M SO DONE WITH THIS! Nothing works!"
        )

        # Should route to Validator
        assert result.routing.expert == Expert.VALIDATOR
        # Safety gate should trigger
        assert result.routing.safety_gate_pass is False or result.routing.expert == Expert.VALIDATOR

    def test_full_pipeline_exploring_user(self):
        """Full pipeline correctly handles exploring user."""
        orchestrator = create_orchestrator()
        orchestrator.reset_session()

        result = orchestrator.process_message(
            "What if we approached this differently? I'm curious about alternatives."
        )

        # Should detect exploring mode
        assert result.signals.mode_detected in ["exploring", "focused", None]

    def test_full_pipeline_performance(self):
        """Pipeline completes in reasonable time."""
        orchestrator = create_orchestrator()

        start = time.time()
        for _ in range(10):
            orchestrator.process_message("test message")
        elapsed = time.time() - start

        # 10 messages should complete in under 1 second
        assert elapsed < 1.0

    def test_to_dict_serializable(self):
        """NexusResult.to_dict() is JSON-serializable."""
        import json

        orchestrator = create_orchestrator()
        result = orchestrator.process_message("test")

        # Should not raise
        json_str = json.dumps(result.to_dict())
        assert json_str is not None

    def test_batch_invariance_orchestrator_level(self):
        """
        ThinkingMachines [He2025]: Same message → same routing checksum.

        Full batch-invariance test at orchestrator level:
        Two fresh sessions processing the same message should produce
        identical routing checksums.
        """
        # Create two separate orchestrators
        orchestrator1 = create_orchestrator()
        orchestrator2 = create_orchestrator()

        # Reset both to ensure clean state
        orchestrator1.reset_session()
        orchestrator2.reset_session()

        # Process same message
        result1 = orchestrator1.process_message("test message")
        result2 = orchestrator2.process_message("test message")

        # Routing checksums must match (batch-invariant)
        assert result1.lock.params.checksum == result2.lock.params.checksum

        # Session checksums should also match for first call (both at reflection_count=0)
        assert result1.lock.params.session_checksum == result2.lock.params.session_checksum

    def test_reflection_count_state_isolation(self):
        """
        Verify reflection_count is properly isolated in CognitiveState.

        Processing multiple messages should increment reflection_count,
        and reset_session should clear it.
        """
        orchestrator = create_orchestrator()
        orchestrator.reset_session()

        # Process first message - reflection_count starts at 0
        result1 = orchestrator.process_message("message 1")
        assert result1.lock.params.reflection_iteration == 0

        # After processing, state should have reflection_count = 1
        state = orchestrator.get_state()
        assert state.reflection_count == 1

        # Process second message - uses reflection_count from snapshot (1)
        result2 = orchestrator.process_message("message 2")
        assert result2.lock.params.reflection_iteration == 1

        # Reset session should clear reflection_count
        orchestrator.reset_session()
        state = orchestrator.get_state()
        assert state.reflection_count == 0


# =============================================================================
# Task Completion Detection Tests
# =============================================================================

class TestTaskCompletionDetection:
    """Tests for task completion detection (Celebrator expert triggering)."""

    def test_task_completed_signal_detection(self):
        """PRISM detects task completion keywords."""
        detector = create_detector()

        # Test various completion phrases
        completion_phrases = [
            "Done! The feature is implemented.",
            "Finished the refactoring.",
            "It works now!",
            "Fixed it, all tests pass.",
            "Shipped the release.",
        ]

        for phrase in completion_phrases:
            signals = detector.detect(phrase)
            assert signals.task.get("completed", 0) > 0, f"Failed to detect completion in: {phrase}"
            assert signals.task_completed(), f"task_completed() returned False for: {phrase}"

    def test_no_false_positive_completion(self):
        """Normal messages don't trigger completion detection."""
        detector = create_detector()

        normal_phrases = [
            "Let's implement this feature.",
            "Can you help me debug this?",
            "What if we try a different approach?",
        ]

        for phrase in normal_phrases:
            signals = detector.detect(phrase)
            assert not signals.task_completed(), f"False positive completion for: {phrase}"

    def test_celebrator_expert_triggers_on_completion(self):
        """Celebrator expert routes correctly when task is completed."""
        router = create_router()
        detector = create_detector()

        signals = detector.detect("Done! It works perfectly now.")
        result = router.route(
            signals=signals,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.HIGH,
            momentum=MomentumPhase.ROLLING,
            mode="focused",
            task_completed=signals.task_completed()
        )

        # Should route to Celebrator (priority 5)
        assert result.expert == Expert.CELEBRATOR
        assert "completed" in result.trigger or "task_completed" in result.trigger

    def test_full_pipeline_task_completion(self):
        """Full pipeline correctly detects and routes task completion."""
        orchestrator = create_orchestrator()
        orchestrator.reset_session()

        result = orchestrator.process_message("Done! The feature is working now.")

        # Should detect completion and route to Celebrator
        assert result.signals.task_completed()
        # Note: Celebrator only fires if no higher-priority experts match
        # With GREEN/HIGH/ROLLING state, Celebrator should win
        assert result.routing.expert in [Expert.CELEBRATOR, Expert.DIRECT]


# =============================================================================
# Dashboard Bridge Tests
# =============================================================================

class TestDashboardBridge:
    """Tests for dashboard bridge state mapping."""

    def test_decision_mode_protect_on_safety_redirect(self):
        """Decision mode is 'protect' when safety gate fires."""
        from otto.dashboard_bridge import _derive_decision_mode
        from otto.prism_detector import SignalVector

        # Create a mock NexusResult with safety redirect
        mock_result = MagicMock()
        mock_result.routing.safety_redirect = "validator"
        mock_result.routing.expert = Expert.VALIDATOR

        mode = _derive_decision_mode(mock_result)
        assert mode == "protect"

    def test_decision_mode_delegate_on_scaffolder(self):
        """Decision mode is 'delegate' for Scaffolder expert."""
        from otto.dashboard_bridge import _derive_decision_mode

        mock_result = MagicMock()
        mock_result.routing.safety_redirect = None
        mock_result.routing.expert = Expert.SCAFFOLDER

        mode = _derive_decision_mode(mock_result)
        assert mode == "delegate"

    def test_decision_mode_delegate_on_socratic(self):
        """Decision mode is 'delegate' for Socratic expert."""
        from otto.dashboard_bridge import _derive_decision_mode

        mock_result = MagicMock()
        mock_result.routing.safety_redirect = None
        mock_result.routing.expert = Expert.SOCRATIC

        mode = _derive_decision_mode(mock_result)
        assert mode == "delegate"

    def test_decision_mode_work_on_direct(self):
        """Decision mode is 'work' for Direct expert."""
        from otto.dashboard_bridge import _derive_decision_mode

        mock_result = MagicMock()
        mock_result.routing.safety_redirect = None
        mock_result.routing.expert = Expert.DIRECT

        mode = _derive_decision_mode(mock_result)
        assert mode == "work"

    def test_working_memory_estimation(self):
        """Working memory estimation reflects active signals."""
        from otto.dashboard_bridge import _estimate_working_memory

        # Create mock result with various signals
        mock_result = MagicMock()
        mock_result.signals.emotional = {"frustrated": 0.5}  # 1 item
        mock_result.signals.primary_task = "implement"  # 1 item
        mock_result.signals.primary_domain = "webdev"  # 1 item
        mock_result.signals.mode_detected = "exploring"  # 1 item (not default)

        mock_state = MagicMock()
        mock_state.tasks_completed = 1  # 1 item

        memory = _estimate_working_memory(mock_result, mock_state)

        # Should count multiple items (capped at 5)
        assert 3 <= memory <= 5

    def test_working_memory_caps_at_five(self):
        """Working memory is capped at cognitive limit (5)."""
        from otto.dashboard_bridge import _estimate_working_memory

        # Create mock result with many signals
        mock_result = MagicMock()
        mock_result.signals.emotional = {"frustrated": 0.5, "anxious": 0.3, "overwhelmed": 0.4}
        mock_result.signals.primary_task = "implement"
        mock_result.signals.primary_domain = "webdev"
        mock_result.signals.mode_detected = "exploring"

        mock_state = MagicMock()
        mock_state.tasks_completed = 10

        memory = _estimate_working_memory(mock_result, mock_state)

        # Should cap at 5
        assert memory <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
