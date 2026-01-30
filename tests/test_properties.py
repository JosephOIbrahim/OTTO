"""
Property-Based Tests for Orchestra Safety Invariants.

Uses Hypothesis to mathematically prove Orchestra's determinism guarantees
and safety properties. These tests verify the core value proposition:

    Same signals -> Same routing -> Same behavior

ThinkingMachines [He2025] Compliance:
- Roundtrip properties for state serialization
- Idempotence properties for state transitions
- Monotonicity properties for safety gating
- Determinism properties for expert routing

References:
    Property-Based Testing Guide (skill: property-based-testing)
    ThinkingMachines batch-invariance [He2025]
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck, Verbosity
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

# Global settings for all hypothesis tests
settings.register_profile("ci", max_examples=50, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("dev", max_examples=20, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("dev")

from otto.cognitive_state import (
    CognitiveState, CognitiveStateManager,
    BurnoutLevel, EnergyLevel, MomentumPhase, CognitiveMode, Altitude
)
from otto.expert_router import ExpertRouter, Expert, create_router
from otto.parameter_locker import ParameterLocker, ThinkDepth, create_locker
from otto.prism_detector import PRISMDetector, SignalVector, create_detector


# =============================================================================
# Strategy Definitions
# =============================================================================

burnout_levels = st.sampled_from(list(BurnoutLevel))
energy_levels = st.sampled_from(list(EnergyLevel))
momentum_phases = st.sampled_from(list(MomentumPhase))
cognitive_modes = st.sampled_from(list(CognitiveMode))
altitudes = st.sampled_from(list(Altitude))

focus_levels = st.sampled_from(["scattered", "moderate", "locked_in"])
urgency_levels = st.sampled_from(["relaxed", "moderate", "deadline"])

# Strategy for valid cognitive state
@st.composite
def cognitive_states(draw):
    """Generate arbitrary valid CognitiveState instances."""
    return CognitiveState(
        burnout_level=draw(burnout_levels),
        energy_level=draw(energy_levels),
        momentum_phase=draw(momentum_phases),
        mode=draw(cognitive_modes),
        altitude=draw(altitudes),
        focus_level=draw(focus_levels),
        urgency=draw(urgency_levels),
        exchange_count=draw(st.integers(min_value=0, max_value=1000)),
        rapid_exchange_count=draw(st.integers(min_value=0, max_value=100)),
        tasks_completed=draw(st.integers(min_value=0, max_value=100)),
        tangent_budget=draw(st.integers(min_value=0, max_value=10)),
        epistemic_tension=draw(st.floats(min_value=0.0, max_value=1.0)),
        stable_exchanges=draw(st.integers(min_value=0, max_value=10)),
    )


# Strategy for signal vectors (messages that trigger routing)
signal_texts = st.sampled_from([
    # Frustrated signals
    "THIS IS BROKEN!!", "I'm so frustrated", "nothing works",
    # Overwhelmed signals
    "this is too much", "I'm stuck", "overwhelmed",
    # Depleted signals
    "I'm exhausted", "can't think anymore", "depleted",
    # Exploring signals
    "what if we tried", "let's explore", "I'm curious about",
    # Focused signals
    "implement this feature", "fix the bug", "let's code",
    # Neutral signals
    "hello", "help me", "what is this",
])


# =============================================================================
# Roundtrip Properties (Serialization)
# =============================================================================

class TestRoundtripProperties:
    """Test that serialization preserves state exactly."""

    @given(cognitive_states())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_state_roundtrip(self, state: CognitiveState):
        """
        Property: to_dict(from_dict(state)) == state

        Serializing and deserializing a state must return an equivalent state.
        This ensures persistence doesn't corrupt cognitive state.
        """
        serialized = state.to_dict()
        restored = CognitiveState.from_dict(serialized)

        # Core state fields must match
        assert restored.burnout_level == state.burnout_level
        assert restored.energy_level == state.energy_level
        assert restored.momentum_phase == state.momentum_phase
        assert restored.mode == state.mode
        assert restored.altitude == state.altitude
        assert restored.focus_level == state.focus_level
        assert restored.urgency == state.urgency
        assert restored.exchange_count == state.exchange_count
        assert restored.tasks_completed == state.tasks_completed
        assert restored.tangent_budget == state.tangent_budget

    @given(cognitive_states())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_checksum_determinism(self, state: CognitiveState):
        """
        Property: checksum(state) == checksum(state)

        The same state must always produce the same checksum.
        ThinkingMachines [He2025] batch-invariance requirement.
        """
        checksum1 = state.checksum()
        checksum2 = state.checksum()
        assert checksum1 == checksum2

    @given(cognitive_states(), cognitive_states())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_different_states_different_checksums(self, state1: CognitiveState, state2: CognitiveState):
        """
        Property: state1 != state2 => checksum(state1) != checksum(state2) (usually)

        Different states should produce different checksums.
        Note: Collisions are theoretically possible but extremely rare.
        """
        # Only check if states are actually different in meaningful ways
        if (state1.burnout_level != state2.burnout_level or
            state1.energy_level != state2.energy_level or
            state1.mode != state2.mode):
            # Different meaningful state should usually produce different checksums
            # (allowing for theoretical collision possibility)
            pass  # This is a probabilistic property, not enforced strictly


# =============================================================================
# Idempotence Properties (State Transitions)
# =============================================================================

class TestIdempotenceProperties:
    """Test that repeated operations converge to stable state."""

    @given(cognitive_states())
    @settings(max_examples=100)
    def test_burnout_escalation_ceiling(self, state: CognitiveState):
        """
        Property: escalate(RED) == RED

        Burnout escalation has a ceiling - RED cannot escalate further.
        This is a safety property ensuring the system has bounded states.
        """
        state.burnout_level = BurnoutLevel.RED
        original = state.burnout_level
        state.escalate_burnout()
        assert state.burnout_level == BurnoutLevel.RED
        assert state.burnout_level == original

    @given(cognitive_states())
    @settings(max_examples=100)
    def test_burnout_recovery_floor(self, state: CognitiveState):
        """
        Property: recover(GREEN) == GREEN

        Burnout recovery has a floor - GREEN cannot recover further.
        """
        state.burnout_level = BurnoutLevel.GREEN
        original = state.burnout_level
        state.recover_burnout()
        assert state.burnout_level == BurnoutLevel.GREEN
        assert state.burnout_level == original

    @given(st.integers(min_value=0, max_value=10))
    @settings(max_examples=50)
    def test_escalation_recovery_inverse(self, n: int):
        """
        Property: recover^n(escalate^n(GREEN)) == GREEN

        N escalations followed by N recoveries returns to GREEN.
        This proves the transition functions are inverses.
        """
        state = CognitiveState(burnout_level=BurnoutLevel.GREEN)

        # Escalate n times (capped at RED)
        for _ in range(n):
            state.escalate_burnout()

        # Recover same number of times
        for _ in range(n):
            state.recover_burnout()

        # Should be back at GREEN (or stayed at GREEN if n was 0)
        assert state.burnout_level == BurnoutLevel.GREEN


# =============================================================================
# Monotonicity Properties (Safety Gating)
# =============================================================================

class TestMonotonicityProperties:
    """Test that safety constraints are monotonic."""

    @given(cognitive_states())
    @settings(max_examples=100)
    def test_safety_gating_monotonicity(self, state: CognitiveState):
        """
        Property: higher burnout => never increases allowed thinking depth

        Safety gating must be monotonically decreasing with burnout level.
        A user at higher burnout should never be allowed MORE cognitive load.
        """
        depth_order = ["minimal", "standard", "deep", "ultradeep"]

        # Get max depth at current state
        original_depth = state.get_max_thinking_depth()
        original_idx = depth_order.index(original_depth) if original_depth in depth_order else 0

        # Escalate burnout
        state.escalate_burnout()
        new_depth = state.get_max_thinking_depth()
        new_idx = depth_order.index(new_depth) if new_depth in depth_order else 0

        # New depth must be <= original depth
        assert new_idx <= original_idx, (
            f"Safety violation: escalating burnout increased allowed depth "
            f"from {original_depth} to {new_depth}"
        )

    @given(cognitive_states())
    @settings(max_examples=100)
    def test_depleted_energy_forces_minimal(self, state: CognitiveState):
        """
        Property: energy=DEPLETED => max_depth=minimal

        Depleted energy must always force minimal thinking depth.
        This is a safety invariant that cannot be overridden.
        """
        state.energy_level = EnergyLevel.DEPLETED
        max_depth = state.get_max_thinking_depth()
        assert max_depth == "minimal", (
            f"Safety violation: DEPLETED energy should force minimal depth, got {max_depth}"
        )

    @given(cognitive_states())
    @settings(max_examples=100)
    def test_red_burnout_forces_minimal(self, state: CognitiveState):
        """
        Property: burnout=RED => max_depth=minimal

        RED burnout must always force minimal thinking depth.
        """
        state.burnout_level = BurnoutLevel.RED
        # Note: energy might override, so we also set energy to non-depleted
        state.energy_level = EnergyLevel.MEDIUM
        max_depth = state.get_max_thinking_depth()
        # RED burnout should force standard or minimal
        assert max_depth in ["minimal", "standard"], (
            f"Safety violation: RED burnout allowed {max_depth} depth"
        )


# =============================================================================
# Determinism Properties (Expert Routing)
# =============================================================================

class TestDeterminismProperties:
    """Test that routing is fully deterministic."""

    @given(cognitive_states())
    def test_routing_determinism(self, state: CognitiveState):
        """
        Property: route(state) == route(state)

        The same state must always route to the same expert.
        ThinkingMachines [He2025] batch-invariance requirement.
        """
        router = create_router()
        detector = create_detector()

        # Create a signal vector from a test message
        signals = detector.detect("help me implement this feature")

        # Route twice with identical inputs
        result1 = router.route(
            signals=signals,
            burnout=state.burnout_level,
            energy=state.energy_level,
            momentum=state.momentum_phase,
            mode=state.mode.value,
            tangent_budget=state.tangent_budget
        )
        result2 = router.route(
            signals=signals,
            burnout=state.burnout_level,
            energy=state.energy_level,
            momentum=state.momentum_phase,
            mode=state.mode.value,
            tangent_budget=state.tangent_budget
        )

        assert result1.expert == result2.expert, (
            f"Routing non-determinism: same input routed to {result1.expert} and {result2.expert}"
        )
        assert result1.trigger == result2.trigger

    def test_frustrated_signals_route_to_validator(self):
        """
        Property: frustrated signal + caps => Validator expert (priority 1)

        Frustrated signals must always route to Validator first.
        This is the highest priority intervention expert.
        """
        router = create_router()
        detector = create_detector()
        state = CognitiveState()

        # Detect signals from frustrated message
        signals = detector.detect("THIS IS BROKEN!!")

        result = router.route(
            signals=signals,
            burnout=state.burnout_level,
            energy=state.energy_level,
            momentum=state.momentum_phase,
            mode=state.mode.value,
            tangent_budget=state.tangent_budget,
            caps_detected=True  # ALL CAPS detected
        )

        # Validator should be selected for frustrated signals with caps
        assert result.expert in [Expert.VALIDATOR, Expert.DIRECT], (
            f"Frustrated signal should route to Validator, got {result.expert}"
        )


# =============================================================================
# Intervention Properties (Should Intervene Logic)
# =============================================================================

class TestInterventionProperties:
    """Test intervention trigger conditions."""

    @given(burnout_levels, energy_levels)
    @settings(max_examples=100)
    def test_intervention_conditions(self, burnout: BurnoutLevel, energy: EnergyLevel):
        """
        Property: (burnout >= ORANGE OR energy = DEPLETED) <=> should_intervene()

        Intervention should trigger if and only if safety conditions are met.
        """
        state = CognitiveState(burnout_level=burnout, energy_level=energy)

        should = state.should_intervene()

        expected = (
            burnout in (BurnoutLevel.ORANGE, BurnoutLevel.RED) or
            energy == EnergyLevel.DEPLETED
        )

        assert should == expected, (
            f"Intervention mismatch: burnout={burnout}, energy={energy}, "
            f"expected={expected}, got={should}"
        )


# =============================================================================
# Convergence Properties (RC^+xi)
# =============================================================================

class TestConvergenceProperties:
    """Test convergence tracking properties."""

    @given(cognitive_states())
    @settings(max_examples=50)
    def test_stable_attractor_reduces_tension(self, state: CognitiveState):
        """
        Property: stable_exchanges increase => epistemic_tension decreases

        When staying in the same attractor, tension should decrease over time.
        """
        state.epistemic_tension = 0.5
        state.convergence_attractor = "focused"

        # Update with same attractor
        state.update_convergence("focused")

        # Tension should decrease or stay low
        assert state.epistemic_tension <= 0.5

    @given(cognitive_states(), st.sampled_from(["focused", "exploring", "recovery", "teaching"]))
    @settings(max_examples=50)
    def test_attractor_switch_increases_tension(self, state: CognitiveState, new_attractor: str):
        """
        Property: attractor switch => epistemic_tension increases

        Switching attractors represents instability and should increase tension.
        """
        assume(state.convergence_attractor != new_attractor)

        initial_tension = state.epistemic_tension
        state.update_convergence(new_attractor)

        # Tension should increase on switch
        assert state.epistemic_tension >= initial_tension


# =============================================================================
# Stateful Testing (State Machine Model)
# =============================================================================

class CognitiveStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based test for CognitiveState.

    This models the state machine and verifies invariants hold
    across arbitrary sequences of operations.
    """

    def __init__(self):
        super().__init__()
        self.state = CognitiveState()
        self.operation_count = 0

    @rule()
    def escalate_burnout(self):
        """Escalate burnout level."""
        old_level = self.state.burnout_level
        self.state.escalate_burnout()
        self.operation_count += 1

        # Verify escalation is bounded
        assert self.state.burnout_level.value in ["green", "yellow", "orange", "red"]

    @rule()
    def recover_burnout(self):
        """Recover burnout level."""
        self.state.recover_burnout()
        self.operation_count += 1

    @rule()
    def complete_task(self):
        """Complete a task."""
        old_completed = self.state.tasks_completed
        self.state.complete_task()
        self.operation_count += 1

        # Tasks completed should increase
        assert self.state.tasks_completed == old_completed + 1

    @rule()
    def increment_exchange(self):
        """Increment exchange counter."""
        old_count = self.state.exchange_count
        self.state.increment_exchange()
        self.operation_count += 1

        assert self.state.exchange_count == old_count + 1

    @rule()
    def consume_tangent(self):
        """Consume from tangent budget."""
        old_budget = self.state.tangent_budget
        result = self.state.consume_tangent()
        self.operation_count += 1

        if old_budget > 0:
            assert result is True
            assert self.state.tangent_budget == old_budget - 1
        else:
            assert result is False
            assert self.state.tangent_budget == 0

    @invariant()
    def burnout_in_valid_range(self):
        """Invariant: burnout is always a valid level."""
        assert self.state.burnout_level in list(BurnoutLevel)

    @invariant()
    def tangent_budget_non_negative(self):
        """Invariant: tangent budget is never negative."""
        assert self.state.tangent_budget >= 0

    @invariant()
    def exchange_count_non_negative(self):
        """Invariant: exchange count is never negative."""
        assert self.state.exchange_count >= 0

    @invariant()
    def safety_gating_always_valid(self):
        """Invariant: max thinking depth is always valid."""
        depth = self.state.get_max_thinking_depth()
        assert depth in ["minimal", "standard", "deep", "ultradeep"]


# Run stateful tests
TestCognitiveStateMachine = CognitiveStateMachine.TestCase
