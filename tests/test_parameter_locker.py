"""
Tests for parameter locker module.

Tests:
- ThinkDepth enum and budgets
- Paradigm enum
- LockStatus enum
- LockedParams dataclass and checksum computation
- ParameterLocker lock() method
- Cognitive safety gating (burnout/energy → depth caps)
- MAX3 bounded reflection
- Paradigm selection (Cortex vs Mycelium)
- Deterministic checksum computation [He2025]
"""

import pytest
from unittest.mock import MagicMock

from otto.parameter_locker import (
    ThinkDepth,
    Paradigm,
    LockStatus,
    LockedParams,
    LockResult,
    ParameterLocker,
    DEPTH_BUDGETS,
    create_locker,
)
from otto.expert_router import Expert, RoutingResult
from otto.cognitive_state import BurnoutLevel, EnergyLevel, Altitude


class TestThinkDepth:
    """Test ThinkDepth enum."""

    def test_depth_values(self):
        """Should have correct depth values."""
        assert ThinkDepth.MINIMAL.value == "minimal"
        assert ThinkDepth.STANDARD.value == "standard"
        assert ThinkDepth.DEEP.value == "deep"
        assert ThinkDepth.ULTRADEEP.value == "ultradeep"

    def test_depth_budgets(self):
        """Should have correct token budgets."""
        assert DEPTH_BUDGETS[ThinkDepth.MINIMAL] == 1_000
        assert DEPTH_BUDGETS[ThinkDepth.STANDARD] == 8_000
        assert DEPTH_BUDGETS[ThinkDepth.DEEP] == 32_000
        assert DEPTH_BUDGETS[ThinkDepth.ULTRADEEP] == 128_000


class TestParadigm:
    """Test Paradigm enum."""

    def test_paradigm_values(self):
        """Should have correct paradigm values."""
        assert Paradigm.CORTEX.value == "Cortex"
        assert Paradigm.MYCELIUM.value == "Mycelium"


class TestLockStatus:
    """Test LockStatus enum."""

    def test_status_values(self):
        """Should have correct status values."""
        assert LockStatus.UNLOCKED.value == "unlocked"
        assert LockStatus.LOCKING.value == "locking"
        assert LockStatus.LOCKED.value == "locked"


class TestLockedParams:
    """Test LockedParams dataclass."""

    def test_creation(self):
        """Should create locked params with computed checksums."""
        params = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard"
        )

        assert params.expert == "direct"
        assert params.paradigm == "Cortex"
        assert params.altitude == "30000ft"
        assert params.think_depth == "standard"
        assert params.checksum != ""
        assert len(params.checksum) == 6

    def test_deterministic_checksum(self):
        """
        Same params should produce same checksum.

        ThinkingMachines [He2025]: Same inputs → same outputs
        """
        params1 = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard"
        )

        params2 = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard"
        )

        assert params1.checksum == params2.checksum

    def test_checksum_excludes_reflection_iteration(self):
        """
        Checksum should exclude reflection_iteration for batch-invariance.

        ThinkingMachines [He2025]: Same routing → same checksum regardless of iteration
        """
        params1 = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard",
            reflection_iteration=0
        )

        params2 = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard",
            reflection_iteration=3
        )

        # Routing checksum should be identical
        assert params1.checksum == params2.checksum

        # Session checksum should differ
        assert params1.session_checksum != params2.session_checksum

    def test_different_params_different_checksum(self):
        """Different params should produce different checksums."""
        params1 = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard"
        )

        params2 = LockedParams(
            expert="validator",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard"
        )

        assert params1.checksum != params2.checksum

    def test_to_anchor(self):
        """Should format as anchor string."""
        params = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard"
        )

        anchor = params.to_anchor()
        assert anchor.startswith("[EXEC:")
        assert "direct" in anchor
        assert "Cortex" in anchor
        assert "30000ft" in anchor
        assert "standard" in anchor

    def test_to_dict(self):
        """Should serialize to dict."""
        params = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard",
            reflection_iteration=1
        )

        d = params.to_dict()
        assert d["expert"] == "direct"
        assert d["paradigm"] == "Cortex"
        assert d["altitude"] == "30000ft"
        assert d["think_depth"] == "standard"
        assert d["reflection_iteration"] == 1
        assert "checksum" in d
        assert "session_checksum" in d

    def test_can_reflect_under_max(self):
        """Should allow reflection under MAX3."""
        params = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard",
            reflection_iteration=0,
            max_reflections=3
        )

        assert params.can_reflect() is True

    def test_can_reflect_at_max(self):
        """Should not allow reflection at MAX3."""
        params = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard",
            reflection_iteration=3,
            max_reflections=3
        )

        assert params.can_reflect() is False


class TestLockResult:
    """Test LockResult dataclass."""

    def test_creation(self):
        """Should create lock result."""
        params = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard"
        )

        result = LockResult(
            status=LockStatus.LOCKED,
            params=params,
            safety_capped=False
        )

        assert result.status == LockStatus.LOCKED
        assert result.params == params
        assert result.safety_capped is False

    def test_to_dict(self):
        """Should serialize to dict."""
        params = LockedParams(
            expert="direct",
            paradigm="Cortex",
            altitude="30000ft",
            think_depth="standard"
        )

        result = LockResult(
            status=LockStatus.LOCKED,
            params=params,
            safety_capped=True,
            original_depth="deep",
            converged=False
        )

        d = result.to_dict()
        assert d["status"] == "locked"
        assert d["safety_capped"] is True
        assert d["original_depth"] == "deep"
        assert d["converged"] is False
        assert "params" in d


class TestParameterLockerInit:
    """Test ParameterLocker initialization."""

    def test_default_init(self):
        """Should initialize with defaults."""
        locker = ParameterLocker()

        assert locker.max_reflections == 3
        assert locker.epsilon == 0.1
        assert locker._current_lock is None

    def test_custom_init(self):
        """Should accept custom parameters."""
        locker = ParameterLocker(max_reflections=5, epsilon=0.05)

        assert locker.max_reflections == 5
        assert locker.epsilon == 0.05


class TestParameterLockerLock:
    """Test ParameterLocker.lock() method."""

    @pytest.fixture
    def locker(self):
        """Create a parameter locker."""
        return ParameterLocker()

    @pytest.fixture
    def routing(self):
        """Create a mock routing result."""
        return RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

    def test_basic_lock(self, locker, routing):
        """Should lock params successfully."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.ARCHITECTURE,
            requested_depth=ThinkDepth.STANDARD,
            mode="focused"
        )

        assert result.status == LockStatus.LOCKED
        assert result.params.expert == "direct"
        assert result.params.think_depth == "standard"
        assert result.safety_capped is False

    def test_lock_stores_current(self, locker, routing):
        """Should store current lock result."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.ARCHITECTURE
        )

        assert locker.get_current_lock() == result


class TestCognitiveSafetyGating:
    """
    Test cognitive safety gating logic.

    Per CLAUDE.md:
    - depleted → minimal
    - low energy → standard
    - RED burnout → minimal
    - ORANGE burnout → standard
    - high energy → ultradeep OK
    """

    @pytest.fixture
    def locker(self):
        return ParameterLocker()

    @pytest.fixture
    def routing(self):
        return RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

    def test_depleted_energy_caps_to_minimal(self, locker, routing):
        """Depleted energy should cap to minimal depth."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.DEPLETED,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.ULTRADEEP
        )

        assert result.params.think_depth == "minimal"
        assert result.safety_capped is True
        assert result.original_depth == "ultradeep"

    def test_red_burnout_caps_to_minimal(self, locker, routing):
        """RED burnout should cap to minimal depth."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.RED,
            energy=EnergyLevel.HIGH,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.DEEP
        )

        assert result.params.think_depth == "minimal"
        assert result.safety_capped is True

    def test_low_energy_caps_to_standard(self, locker, routing):
        """Low energy should cap to standard depth."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.LOW,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.DEEP
        )

        assert result.params.think_depth == "standard"
        assert result.safety_capped is True

    def test_orange_burnout_caps_to_standard(self, locker, routing):
        """ORANGE burnout should cap to standard depth."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.ORANGE,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.ULTRADEEP
        )

        assert result.params.think_depth == "standard"
        assert result.safety_capped is True

    def test_high_energy_allows_ultradeep(self, locker, routing):
        """High energy should allow ultradeep depth."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.HIGH,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.ULTRADEEP
        )

        assert result.params.think_depth == "ultradeep"
        assert result.safety_capped is False

    def test_medium_energy_default_allows_deep(self, locker, routing):
        """Medium energy with green burnout should allow deep depth."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.DEEP
        )

        assert result.params.think_depth == "deep"
        assert result.safety_capped is False

    def test_safety_never_increases_depth(self, locker, routing):
        """Safety gating should never increase depth above requested."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.HIGH,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.MINIMAL
        )

        # Even with high energy, should not increase above minimal
        assert result.params.think_depth == "minimal"
        assert result.safety_capped is False


class TestMAX3BoundedReflection:
    """Test MAX3 bounded reflection logic."""

    @pytest.fixture
    def locker(self):
        return ParameterLocker(max_reflections=3)

    @pytest.fixture
    def routing(self):
        return RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

    def test_reflection_count_in_params(self, locker, routing):
        """Should include reflection count in locked params."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            reflection_count=2
        )

        assert result.params.reflection_iteration == 2

    def test_max3_forces_minimal_depth(self, locker, routing):
        """At MAX3, should force minimal depth."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.HIGH,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.ULTRADEEP,
            reflection_count=3  # At MAX3
        )

        assert result.params.think_depth == "minimal"
        assert result.safety_capped is True

    def test_beyond_max3_forces_minimal(self, locker, routing):
        """Beyond MAX3, should force minimal depth."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.HIGH,
            altitude=Altitude.VISION,
            requested_depth=ThinkDepth.DEEP,
            reflection_count=5  # Beyond MAX3
        )

        assert result.params.think_depth == "minimal"


class TestEpsilonConvergence:
    """Test epsilon-based early convergence detection."""

    @pytest.fixture
    def locker(self):
        return ParameterLocker(epsilon=0.1)

    @pytest.fixture
    def routing(self):
        return RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

    def test_high_tension_not_converged(self, locker, routing):
        """High epistemic tension should not signal convergence."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            epistemic_tension=0.5,
            reflection_count=1
        )

        assert result.converged is False

    def test_low_tension_signals_convergence(self, locker, routing):
        """Low epistemic tension should signal convergence."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            epistemic_tension=0.05,  # Below epsilon
            reflection_count=1  # Must be > 0
        )

        assert result.converged is True

    def test_first_iteration_not_converged(self, locker, routing):
        """First iteration should not signal convergence even with low tension."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            epistemic_tension=0.01,
            reflection_count=0  # First iteration
        )

        assert result.converged is False


class TestParadigmSelection:
    """Test paradigm selection based on expert and mode."""

    @pytest.fixture
    def locker(self):
        return ParameterLocker()

    def test_default_paradigm_is_cortex(self, locker):
        """Default paradigm should be Cortex."""
        routing = RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            mode="focused"
        )

        assert result.params.paradigm == "Cortex"

    def test_exploring_mode_uses_mycelium(self, locker):
        """Exploring mode should use Mycelium paradigm."""
        routing = RoutingResult(
            expert=Expert.DIRECT,
            trigger="exploring"
        )

        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            mode="exploring"
        )

        assert result.params.paradigm == "Mycelium"

    def test_socratic_exploring_uses_mycelium(self, locker):
        """Socratic expert with exploring mode should use Mycelium."""
        routing = RoutingResult(
            expert=Expert.SOCRATIC,
            trigger="what if"
        )

        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.HIGH,
            altitude=Altitude.VISION,
            mode="exploring"
        )

        assert result.params.paradigm == "Mycelium"

    def test_socratic_teaching_uses_mycelium(self, locker):
        """Socratic expert with teaching mode should use Mycelium."""
        routing = RoutingResult(
            expert=Expert.SOCRATIC,
            trigger="explain"
        )

        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            mode="teaching"
        )

        assert result.params.paradigm == "Mycelium"

    def test_validator_uses_cortex(self, locker):
        """Validator expert should use Cortex (structured)."""
        routing = RoutingResult(
            expert=Expert.VALIDATOR,
            trigger="frustrated"
        )

        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION,
            mode="focused"
        )

        assert result.params.paradigm == "Cortex"


class TestAltitudeFormatting:
    """Test altitude formatting."""

    @pytest.fixture
    def locker(self):
        return ParameterLocker()

    @pytest.fixture
    def routing(self):
        return RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

    def test_vision_altitude(self, locker, routing):
        """Vision altitude should format as 30000ft."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION
        )

        assert result.params.altitude == "30000ft"

    def test_architecture_altitude(self, locker, routing):
        """Architecture altitude should format as 15000ft."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.ARCHITECTURE
        )

        assert result.params.altitude == "15000ft"

    def test_components_altitude(self, locker, routing):
        """Components altitude should format as 5000ft."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.COMPONENTS
        )

        assert result.params.altitude == "5000ft"

    def test_ground_altitude(self, locker, routing):
        """Ground altitude should format as Ground."""
        result = locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.GROUND
        )

        assert result.params.altitude == "Ground"


class TestLockerReset:
    """Test locker reset functionality."""

    def test_reset_clears_current_lock(self):
        """Reset should clear current lock."""
        locker = ParameterLocker()
        routing = RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

        # Create a lock
        locker.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.VISION
        )
        assert locker.get_current_lock() is not None

        # Reset
        locker.reset()
        assert locker.get_current_lock() is None


class TestCreateLocker:
    """Test factory function."""

    def test_create_locker_defaults(self):
        """Should create locker with defaults."""
        locker = create_locker()

        assert locker.max_reflections == 3
        assert locker.epsilon == 0.1

    def test_create_locker_custom(self):
        """Should create locker with custom params."""
        locker = create_locker(max_reflections=5, epsilon=0.05)

        assert locker.max_reflections == 5
        assert locker.epsilon == 0.05


class TestDeterminism:
    """
    Test deterministic behavior.

    ThinkingMachines [He2025]: Same inputs → same outputs
    """

    def test_same_inputs_same_output(self):
        """Same inputs should produce identical lock results."""
        locker1 = ParameterLocker()
        locker2 = ParameterLocker()

        routing = RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

        result1 = locker1.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.ARCHITECTURE,
            requested_depth=ThinkDepth.STANDARD,
            mode="focused",
            epistemic_tension=0.3,
            reflection_count=1
        )

        result2 = locker2.lock(
            routing=routing,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.MEDIUM,
            altitude=Altitude.ARCHITECTURE,
            requested_depth=ThinkDepth.STANDARD,
            mode="focused",
            epistemic_tension=0.3,
            reflection_count=1
        )

        # All fields should match
        assert result1.params.checksum == result2.params.checksum
        assert result1.params.expert == result2.params.expert
        assert result1.params.paradigm == result2.params.paradigm
        assert result1.params.altitude == result2.params.altitude
        assert result1.params.think_depth == result2.params.think_depth
        assert result1.safety_capped == result2.safety_capped
        assert result1.converged == result2.converged

    def test_lock_order_independence(self):
        """Lock result should not depend on previous locks."""
        locker = ParameterLocker()

        routing1 = RoutingResult(
            expert=Expert.VALIDATOR,
            trigger="frustrated"
        )

        routing2 = RoutingResult(
            expert=Expert.DIRECT,
            trigger="focused"
        )

        # Lock with validator first
        locker.lock(
            routing=routing1,
            burnout=BurnoutLevel.RED,
            energy=EnergyLevel.LOW,
            altitude=Altitude.VISION
        )

        # Then lock with direct - should not be affected
        result = locker.lock(
            routing=routing2,
            burnout=BurnoutLevel.GREEN,
            energy=EnergyLevel.HIGH,
            altitude=Altitude.GROUND,
            requested_depth=ThinkDepth.DEEP
        )

        assert result.params.expert == "direct"
        assert result.params.think_depth == "deep"
        assert result.safety_capped is False
