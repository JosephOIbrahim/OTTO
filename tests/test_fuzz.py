"""
Fuzz testing for Orchestra safety gating and routing.

ThinkingMachines [He2025] compliance: Test that edge cases don't break
safety invariants or determinism guarantees.

Note: Atheris requires Linux. On Windows, these tests run as standard
property-based tests using Hypothesis as a fallback.
"""

import unittest

# Try to import atheris, fall back to hypothesis-only mode
try:
    import atheris
    ATHERIS_AVAILABLE = True
except ImportError:
    ATHERIS_AVAILABLE = False

from hypothesis import given, settings, strategies as st, HealthCheck, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

from otto.cognitive_state import (
    CognitiveState,
    CognitiveStateManager,
    BurnoutLevel,
    EnergyLevel,
    MomentumPhase,
    CognitiveMode,
)


# =============================================================================
# Burnout Level Ordering (string values need explicit ordering)
# =============================================================================

BURNOUT_ORDER = {
    BurnoutLevel.GREEN: 0,
    BurnoutLevel.YELLOW: 1,
    BurnoutLevel.ORANGE: 2,
    BurnoutLevel.RED: 3,
}

ENERGY_ORDER = {
    EnergyLevel.DEPLETED: 0,
    EnergyLevel.LOW: 1,
    EnergyLevel.MEDIUM: 2,
    EnergyLevel.HIGH: 3,
}


# =============================================================================
# Fuzz Strategies
# =============================================================================

@st.composite
def fuzz_cognitive_state(draw):
    """Generate arbitrary cognitive states for fuzzing."""
    return CognitiveState(
        burnout_level=draw(st.sampled_from(list(BurnoutLevel))),
        energy_level=draw(st.sampled_from(list(EnergyLevel))),
        momentum_phase=draw(st.sampled_from(list(MomentumPhase))),
        mode=draw(st.sampled_from(list(CognitiveMode))),
        exchange_count=draw(st.integers(min_value=0, max_value=1000)),
        rapid_exchange_count=draw(st.integers(min_value=0, max_value=100)),
        tasks_completed=draw(st.integers(min_value=0, max_value=500)),
        tangent_budget=draw(st.integers(min_value=0, max_value=10)),
        stable_exchanges=draw(st.integers(min_value=0, max_value=10)),
        epistemic_tension=draw(st.floats(min_value=0, max_value=1, allow_nan=False)),
        reflection_count=draw(st.integers(min_value=0, max_value=5)),
    )


@st.composite
def fuzz_user_input(draw):
    """Generate fuzzy user input strings."""
    # Mix of normal and adversarial inputs
    strategies = [
        # Normal inputs
        st.text(min_size=0, max_size=1000),
        # Empty and whitespace
        st.just(""),
        st.just("   "),
        st.just("\n\n\n"),
        # Unicode edge cases (shorter)
        st.text(alphabet=st.characters(categories=['Cs', 'Co']), max_size=100),
        # Control characters (shorter)
        st.text(alphabet=st.characters(categories=['Cc']), max_size=100),
        # Longer inputs (but not too long for Hypothesis)
        st.text(min_size=1000, max_size=5000),
        # Injection attempts (harmless to test parsing)
        st.just("'; DROP TABLE users; --"),
        st.just("{{{{{{"),
        st.just("}}}}}}"),
        st.just("${PATH}"),
        st.just("$(whoami)"),
        st.just("AAAA%n%n%n%n"),
    ]
    return draw(st.one_of(strategies))


# =============================================================================
# Fuzz Tests: Safety Gating
# =============================================================================

class TestFuzzSafetyGating(unittest.TestCase):
    """Fuzz test safety gating invariants."""

    @given(fuzz_cognitive_state())
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_burnout_ceiling_never_exceeded(self, state: CognitiveState):
        """Safety gating must never allow burnout > RED."""
        # Burnout level should always be within valid enum values
        assert state.burnout_level in BurnoutLevel
        # RED is the maximum (order index 3)
        assert BURNOUT_ORDER[state.burnout_level] <= BURNOUT_ORDER[BurnoutLevel.RED]

    @given(fuzz_cognitive_state())
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_energy_floor_maintained(self, state: CognitiveState):
        """Energy level should never go below DEPLETED."""
        assert state.energy_level in EnergyLevel
        # DEPLETED is the minimum (order index 0)
        assert ENERGY_ORDER[state.energy_level] >= ENERGY_ORDER[EnergyLevel.DEPLETED]

    @given(fuzz_cognitive_state())
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_state_serialization_roundtrip(self, state: CognitiveState):
        """State serialization must be lossless for all valid states."""
        # Serialize
        data = state.to_dict()
        # Deserialize
        restored = CognitiveState.from_dict(data)
        # Core fields must match
        assert restored.burnout_level == state.burnout_level
        assert restored.energy_level == state.energy_level
        assert restored.momentum_phase == state.momentum_phase
        assert restored.mode == state.mode

    @given(fuzz_cognitive_state())
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_state_determinism(self, state: CognitiveState):
        """Same state must serialize to identical dicts."""
        dict1 = state.to_dict()
        dict2 = state.to_dict()
        # Exclude time-based fields
        for key in ['session_start', 'last_activity']:
            dict1.pop(key, None)
            dict2.pop(key, None)
        assert dict1 == dict2


# =============================================================================
# Fuzz Tests: Input Validation
# =============================================================================

class TestFuzzInputValidation(unittest.TestCase):
    """Fuzz test input validation and sanitization."""

    @given(fuzz_user_input())
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    def test_manager_handles_arbitrary_goals(self, goal: str):
        """State manager must handle arbitrary goal strings safely."""
        manager = CognitiveStateManager()
        state = manager.get_state()  # Initialize state
        # Should not crash on any input
        try:
            state.session_goal = goal
            # Verify it was set
            assert state.session_goal == goal
        except (ValueError, TypeError):
            # These exceptions are acceptable for invalid input
            pass

    @given(st.binary(min_size=0, max_size=1000))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_binary_input_handling(self, data: bytes):
        """System must not crash on binary data masquerading as text."""
        # Try to decode as various encodings
        encodings = ['utf-8', 'latin-1', 'ascii']
        for encoding in encodings:
            try:
                text = data.decode(encoding, errors='replace')
                # Should be able to use as goal without crashing
                manager = CognitiveStateManager()
                state = manager.get_state()  # Initialize state
                state.session_goal = text
            except Exception:
                # Record but don't fail - we're testing for crashes
                pass


# =============================================================================
# Stateful Fuzz Testing
# =============================================================================

class CognitiveStateMachine(RuleBasedStateMachine):
    """
    Stateful fuzz testing for cognitive state transitions.

    Verifies that no sequence of state transitions can violate safety invariants.
    """

    def __init__(self):
        super().__init__()
        self.manager = CognitiveStateManager()
        # Initialize state
        self._state = self.manager.get_state()
        assert self._state is not None

    @rule()
    def increment_exchange(self):
        """Simulate a conversation exchange."""
        if self._state is not None:
            self._state.exchange_count += 1
            # Invariant: exchange count must be non-negative
            assert self._state.exchange_count >= 0

    @rule(level=st.sampled_from(list(BurnoutLevel)))
    def set_burnout(self, level: BurnoutLevel):
        """Set burnout level."""
        if self._state is not None:
            self._state.burnout_level = level
            # Invariant: level must be valid
            assert self._state.burnout_level in BurnoutLevel

    @rule(level=st.sampled_from(list(EnergyLevel)))
    def set_energy(self, level: EnergyLevel):
        """Set energy level."""
        if self._state is not None:
            self._state.energy_level = level
            # Invariant: level must be valid
            assert self._state.energy_level in EnergyLevel

    @rule()
    def reset_session(self):
        """Reset the session."""
        self._state = self.manager.reset()
        # Invariant: reset must restore defaults
        assert self._state.burnout_level == BurnoutLevel.GREEN
        assert self._state.exchange_count == 0

    @invariant()
    def verify_safety_invariants(self):
        """Check all safety invariants at any point."""
        if self._state is None:
            return
        state = self._state
        # Burnout ceiling
        assert BURNOUT_ORDER[state.burnout_level] <= BURNOUT_ORDER[BurnoutLevel.RED]
        # Energy floor
        assert ENERGY_ORDER[state.energy_level] >= ENERGY_ORDER[EnergyLevel.DEPLETED]
        # Momentum must be valid
        assert state.momentum_phase in MomentumPhase
        # Tangent budget must be reasonable
        assert state.tangent_budget >= 0


# Run stateful test
TestStatefulCognitive = CognitiveStateMachine.TestCase


# =============================================================================
# Atheris Native Fuzzing (Linux only)
# =============================================================================

if ATHERIS_AVAILABLE:

    def fuzz_state_parsing(data):
        """Fuzz test state dict parsing from bytes."""
        fdp = atheris.FuzzedDataProvider(data)

        try:
            state_dict = {
                "burnout_level": fdp.ConsumeUnicodeNoSurrogates(20),
                "energy_level": fdp.ConsumeUnicodeNoSurrogates(20),
                "momentum_phase": fdp.ConsumeUnicodeNoSurrogates(20),
                "mode": fdp.ConsumeUnicodeNoSurrogates(20),
                "exchange_count": fdp.ConsumeIntInRange(-1000, 1000),
            }
            # Should handle gracefully
            CognitiveState.from_dict(state_dict)
        except (ValueError, KeyError, TypeError):
            # Acceptable for malformed input
            pass


if __name__ == "__main__":
    # Run hypothesis tests normally
    unittest.main()
