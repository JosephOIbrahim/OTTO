"""Constitutional layer — FROZEN. IMMUTABLE. NON-NEGOTIABLE.

This module defines the principles and safety floors that govern all of
OTTO OS. These are frozen dataclasses: any attempt to modify a field after
construction raises FrozenInstanceError. No code in the system may lower
safety floors or alter constitutional principles at runtime.

Patent claims #1 (LIVRPS) and #2 (Safety Floors) are implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Constitutional Principles (10 frozen principles)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConstitutionalPrinciples:
    """Immutable principles that govern all OTTO OS behavior.

    Every user-facing string in this class has been reviewed for:
    - No clinical language (no diagnostic labels, no deficit framing)
    - No guilt/shame language (no "you should have")
    - No minimizing language (no "just", "simply", "easy")
    """

    safety_first: str = "User emotional and cognitive safety is paramount"
    ship_over_perfect: str = "Working code beats perfect plans"
    protect_momentum: str = "Never break flow state without consent"
    write_it_down: str = "If it is not persisted, it did not happen"
    rest_is_productive: str = "Recovery is not laziness"
    one_at_a_time: str = "Focus is a finite resource"
    user_knows_best: str = "User sovereignty over all defaults"
    no_clinical_language: str = "Never use diagnostic labels in user-facing text"
    privacy_is_law: str = "Raw data never leaves the device"
    determinism_required: str = "Same input plus same state equals same output"


# ---------------------------------------------------------------------------
# Safety Floors (Patent Claim #2)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SafetyFloors:
    """Minimum expert activation levels. Constitutional — cannot be lowered.

    These floors guarantee that protective experts are ALWAYS active,
    regardless of detected signals or cognitive state. They are checked
    in the BOUND phase of the NEXUS routing pipeline, before expert
    selection.

    The three floored experts consume 20% of total activation budget,
    leaving 80% for dynamic allocation among all 7 experts.
    """

    protector: float = 0.10   # Always >= 10% activation
    decomposer: float = 0.05  # Always >= 5% activation
    restorer: float = 0.05    # Always >= 5% activation

    @property
    def total(self) -> float:
        """Sum of all safety floors. Must equal 0.20."""
        return self.protector + self.decomposer + self.restorer

    @property
    def dynamic_budget(self) -> float:
        """Remaining activation budget for non-floored experts."""
        return 1.0 - self.total


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ConstitutionViolation(Exception):
    """Raised when constitutional invariants are violated."""


def validate(
    principles: ConstitutionalPrinciples | None = None,
    floors: SafetyFloors | None = None,
) -> None:
    """Validate that constitutional invariants hold.

    Call this at startup and periodically at runtime. If anything has
    been tampered with, this raises ConstitutionViolation immediately.

    Args:
        principles: Principles to validate. Uses defaults if None.
        floors: Safety floors to validate. Uses defaults if None.

    Raises:
        ConstitutionViolation: If any invariant is violated.
    """
    if principles is None:
        principles = ConstitutionalPrinciples()
    if floors is None:
        floors = SafetyFloors()

    # --- Floor value checks ---
    if floors.protector < 0.10:
        raise ConstitutionViolation(
            f"Protector floor {floors.protector} is below minimum 0.10"
        )
    if floors.decomposer < 0.05:
        raise ConstitutionViolation(
            f"Decomposer floor {floors.decomposer} is below minimum 0.05"
        )
    if floors.restorer < 0.05:
        raise ConstitutionViolation(
            f"Restorer floor {floors.restorer} is below minimum 0.05"
        )

    # --- Total budget check ---
    expected_total = 0.20
    if abs(floors.total - expected_total) > 1e-9:
        raise ConstitutionViolation(
            f"Safety floor total {floors.total} != expected {expected_total}"
        )

    # --- Principles completeness check ---
    expected_count = 10
    actual_count = len([
        f.name for f in principles.__dataclass_fields__.values()
    ])
    if actual_count != expected_count:
        raise ConstitutionViolation(
            f"Expected {expected_count} principles, found {actual_count}"
        )

    # --- No empty principles ---
    for field_name in sorted(principles.__dataclass_fields__):
        value = getattr(principles, field_name)
        if not isinstance(value, str) or not value.strip():
            raise ConstitutionViolation(
                f"Principle '{field_name}' must be a non-empty string"
            )


# ---------------------------------------------------------------------------
# Clinical language blocklist (for validation tooling)
# ---------------------------------------------------------------------------

# These terms must NEVER appear in user-facing strings.
# Used by tests and CI to scan for violations.
CLINICAL_BLOCKLIST: tuple[str, ...] = (
    "adhd",
    "add",
    "executive dysfunction",
    "neurodivergent deficit",
    "disorder",
    "diagnosis",
    "symptom",
    "impairment",
    "deficit",
    "abnormal",
    "dysfunctional",
    "your adhd",
    "your condition",
    "you should have",
)
