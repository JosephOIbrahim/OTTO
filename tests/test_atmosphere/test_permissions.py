"""
Tests for atmosphere proactive permissions.

Verifies:
- Permissions granted at appropriate times
- Burnout/energy triggers work
- Determinism (same input → same selection)
"""

import pytest
from otto.atmosphere.permissions import (
    Permission,
    PermissionType,
    PERMISSIONS,
    get_permission,
    maybe_get_permission,
    should_grant_permission,
)
from otto.atmosphere.patterns import ATMOSPHERE_SEED


class TestPermissionDetection:
    """Tests for permission need detection."""

    def test_red_burnout_triggers_stop(self):
        """RED burnout should trigger STOP permission."""
        result = should_grant_permission(
            "anything",
            burnout_level="RED",
        )
        assert result == PermissionType.STOP

    def test_orange_burnout_triggers_rest(self):
        """ORANGE burnout should trigger REST permission."""
        result = should_grant_permission(
            "anything",
            burnout_level="ORANGE",
        )
        assert result == PermissionType.REST

    def test_depleted_energy_triggers_rest(self):
        """Depleted energy should trigger REST permission."""
        result = should_grant_permission(
            "anything",
            energy_level="depleted",
        )
        assert result == PermissionType.REST

    def test_frustration_signals_trigger_feel(self):
        """Frustration signals should trigger FEEL permission."""
        result = should_grant_permission(
            "I'm so frustrated with this bug",
            burnout_level="GREEN",
        )
        assert result == PermissionType.FEEL

    def test_perfectionism_triggers_imperfect(self):
        """Perfectionism signals should trigger IMPERFECT permission."""
        result = should_grant_permission(
            "It's almost ready, let me just polish this one more thing",
            burnout_level="GREEN",
        )
        assert result == PermissionType.IMPERFECT

    def test_slow_signals_trigger_slow(self):
        """Slow signals should trigger SLOW permission."""
        result = should_grant_permission(
            "This is taking forever",
            burnout_level="GREEN",
        )
        assert result == PermissionType.SLOW

    def test_crashed_momentum_triggers_rest(self):
        """Crashed momentum should trigger REST permission."""
        result = should_grant_permission(
            "ok",
            burnout_level="GREEN",
            momentum_phase="crashed",
        )
        assert result == PermissionType.REST

    def test_no_permission_for_normal_state(self):
        """Normal state without signals should not trigger permission."""
        result = should_grant_permission(
            "How do I implement this feature?",
            burnout_level="GREEN",
            energy_level="medium",
            momentum_phase="building",
        )
        assert result is None


class TestGetPermission:
    """Tests for getting permissions."""

    def test_get_rest_permission(self):
        """Should get REST permission."""
        result = get_permission(PermissionType.REST)
        assert result.type == PermissionType.REST
        assert len(result.text) > 0

    def test_get_stop_permission(self):
        """Should get STOP permission."""
        result = get_permission(PermissionType.STOP)
        assert result.type == PermissionType.STOP

    def test_determinism(self):
        """Same inputs should produce same output."""
        result1 = get_permission(PermissionType.REST, seed=ATMOSPHERE_SEED)
        result2 = get_permission(PermissionType.REST, seed=ATMOSPHERE_SEED)
        assert result1.text == result2.text


class TestMaybeGetPermission:
    """Tests for combined detection and selection."""

    def test_returns_permission_when_needed(self):
        """Should return permission when state warrants it."""
        result = maybe_get_permission(
            "I'm exhausted",
            burnout_level="ORANGE",
            energy_level="low",
        )
        assert result is not None
        assert isinstance(result, Permission)

    def test_returns_none_when_not_needed(self):
        """Should return None when no permission needed."""
        result = maybe_get_permission(
            "What's the best way to do this?",
            burnout_level="GREEN",
            energy_level="high",
            momentum_phase="rolling",
        )
        assert result is None


class TestPermissionLists:
    """Tests for permission list structure."""

    def test_all_types_have_permissions(self):
        """Every permission type should have permissions."""
        for ptype in PermissionType:
            assert ptype in PERMISSIONS
            assert len(PERMISSIONS[ptype]) > 0

    def test_lists_are_sorted(self):
        """Permission lists should be sorted for determinism."""
        for ptype, permissions in PERMISSIONS.items():
            texts = [p.text for p in permissions]
            assert texts == sorted(texts), f"{ptype} list not sorted"


class TestPermissionPriority:
    """Tests for permission priority order."""

    def test_burnout_overrides_signals(self):
        """Burnout-based permissions should override signal-based."""
        # Even with frustration signal, RED burnout wins
        result = should_grant_permission(
            "I'm frustrated with this",
            burnout_level="RED",
        )
        assert result == PermissionType.STOP  # Not FEEL
