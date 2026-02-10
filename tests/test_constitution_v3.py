"""Tests for the constitutional layer — Day 1 of OTTO OS v3.0.

These tests verify that:
1. Principles and safety floors are truly immutable (frozen)
2. Safety floor values match the specification exactly
3. validate() accepts valid constitutions and rejects violations
4. No clinical language appears in any user-facing string constant
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from otto.core.constitution import (
    CLINICAL_BLOCKLIST,
    ConstitutionalPrinciples,
    ConstitutionViolation,
    SafetyFloors,
    validate,
)


# ===================================================================
# Fixture: default instances
# ===================================================================

@pytest.fixture
def principles() -> ConstitutionalPrinciples:
    return ConstitutionalPrinciples()


@pytest.fixture
def floors() -> SafetyFloors:
    return SafetyFloors()


# ===================================================================
# Test: Principles are frozen (immutable)
# ===================================================================

class TestPrinciplesFrozen:
    """ConstitutionalPrinciples must be immutable after creation."""

    def test_cannot_modify_safety_first(self, principles: ConstitutionalPrinciples) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            principles.safety_first = "something else"  # type: ignore[misc]

    def test_cannot_modify_ship_over_perfect(self, principles: ConstitutionalPrinciples) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            principles.ship_over_perfect = "nope"  # type: ignore[misc]

    def test_cannot_modify_rest_is_productive(self, principles: ConstitutionalPrinciples) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            principles.rest_is_productive = "tampered"  # type: ignore[misc]

    def test_cannot_add_new_attribute(self, principles: ConstitutionalPrinciples) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            principles.new_field = "surprise"  # type: ignore[attr-defined]

    def test_cannot_delete_attribute(self, principles: ConstitutionalPrinciples) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            del principles.safety_first  # type: ignore[misc]

    def test_all_fields_are_immutable(self, principles: ConstitutionalPrinciples) -> None:
        """Every single principle field must reject assignment."""
        for field in sorted(dataclasses.fields(principles), key=lambda f: f.name):
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(principles, field.name, "tampered")

    def test_has_exactly_10_principles(self, principles: ConstitutionalPrinciples) -> None:
        assert len(dataclasses.fields(principles)) == 10


# ===================================================================
# Test: Safety floors are frozen and correct
# ===================================================================

class TestSafetyFloors:
    """SafetyFloors must be immutable and match the specification."""

    def test_protector_floor_value(self, floors: SafetyFloors) -> None:
        assert floors.protector == 0.10

    def test_decomposer_floor_value(self, floors: SafetyFloors) -> None:
        assert floors.decomposer == 0.05

    def test_restorer_floor_value(self, floors: SafetyFloors) -> None:
        assert floors.restorer == 0.05

    def test_total_equals_0_20(self, floors: SafetyFloors) -> None:
        assert abs(floors.total - 0.20) < 1e-9

    def test_dynamic_budget_equals_0_80(self, floors: SafetyFloors) -> None:
        assert abs(floors.dynamic_budget - 0.80) < 1e-9

    def test_cannot_modify_protector(self, floors: SafetyFloors) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            floors.protector = 0.0  # type: ignore[misc]

    def test_cannot_modify_decomposer(self, floors: SafetyFloors) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            floors.decomposer = 0.0  # type: ignore[misc]

    def test_cannot_modify_restorer(self, floors: SafetyFloors) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            floors.restorer = 0.0  # type: ignore[misc]

    def test_cannot_lower_floors_via_new_instance(self) -> None:
        """Even if you create a new instance with lower values,
        validate() must reject it."""
        tampered = SafetyFloors(protector=0.01, decomposer=0.01, restorer=0.01)
        with pytest.raises(ConstitutionViolation, match="Protector floor"):
            validate(floors=tampered)

    def test_floors_are_frozen_dataclass(self) -> None:
        assert dataclasses.is_dataclass(SafetyFloors)
        # Check frozen by trying to set on an instance
        floors = SafetyFloors()
        with pytest.raises(dataclasses.FrozenInstanceError):
            floors.protector = 0.99  # type: ignore[misc]


# ===================================================================
# Test: validate() function
# ===================================================================

class TestValidate:
    """validate() must accept valid constitutions and reject violations."""

    def test_default_passes(self) -> None:
        """Default values must always pass validation."""
        validate()  # Should not raise

    def test_explicit_defaults_pass(
        self,
        principles: ConstitutionalPrinciples,
        floors: SafetyFloors,
    ) -> None:
        validate(principles=principles, floors=floors)

    def test_protector_below_minimum_fails(self) -> None:
        with pytest.raises(ConstitutionViolation, match="Protector"):
            validate(floors=SafetyFloors(protector=0.09, decomposer=0.05, restorer=0.05))

    def test_decomposer_below_minimum_fails(self) -> None:
        with pytest.raises(ConstitutionViolation, match="Decomposer"):
            validate(floors=SafetyFloors(protector=0.10, decomposer=0.04, restorer=0.05))

    def test_restorer_below_minimum_fails(self) -> None:
        with pytest.raises(ConstitutionViolation, match="Restorer"):
            validate(floors=SafetyFloors(protector=0.10, decomposer=0.05, restorer=0.04))

    def test_floors_above_minimum_still_validates(self) -> None:
        """Higher floors are fine — they're ABOVE the minimum."""
        high_floors = SafetyFloors(protector=0.15, decomposer=0.10, restorer=0.10)
        # This should fail on total != 0.20
        with pytest.raises(ConstitutionViolation, match="total"):
            validate(floors=high_floors)

    def test_all_zeros_fails(self) -> None:
        with pytest.raises(ConstitutionViolation):
            validate(floors=SafetyFloors(protector=0.0, decomposer=0.0, restorer=0.0))

    def test_validate_is_deterministic(
        self,
        principles: ConstitutionalPrinciples,
        floors: SafetyFloors,
    ) -> None:
        """Running validate() 100 times must produce the same result."""
        for _ in range(100):
            validate(principles=principles, floors=floors)


# ===================================================================
# Test: No clinical language in string constants
# ===================================================================

class TestNoClinicalLanguage:
    """All user-facing strings must be free of clinical/diagnostic language."""

    def test_principles_no_clinical_terms(self, principles: ConstitutionalPrinciples) -> None:
        """Scan every principle string for clinical language."""
        for field in sorted(dataclasses.fields(principles), key=lambda f: f.name):
            value = getattr(principles, field.name)
            value_lower = value.lower()
            for term in CLINICAL_BLOCKLIST:
                assert term not in value_lower, (
                    f"Clinical term '{term}' found in principle "
                    f"'{field.name}': \"{value}\""
                )

    def test_principles_no_guilt_language(self, principles: ConstitutionalPrinciples) -> None:
        """No guilt/shame framing in principles."""
        guilt_patterns = [
            r"\byou should\b",
            r"\byou must\b",
            r"\byou need to\b",
            r"\bjust\b",
            r"\bsimply\b",
            r"\beasy\b",
        ]
        for field in sorted(dataclasses.fields(principles), key=lambda f: f.name):
            value = getattr(principles, field.name)
            for pattern in guilt_patterns:
                assert not re.search(pattern, value, re.IGNORECASE), (
                    f"Guilt/minimizing pattern '{pattern}' found in "
                    f"principle '{field.name}': \"{value}\""
                )

    def test_blocklist_is_nonempty(self) -> None:
        assert len(CLINICAL_BLOCKLIST) > 0

    def test_blocklist_is_tuple_not_set(self) -> None:
        """Tuple for [He2025] deterministic iteration order."""
        assert isinstance(CLINICAL_BLOCKLIST, tuple)

    def test_blocklist_entries_are_lowercase(self) -> None:
        """All blocklist entries must be lowercase for consistent matching."""
        for term in CLINICAL_BLOCKLIST:
            assert term == term.lower(), f"Blocklist term '{term}' is not lowercase"
