"""
Tests for atmosphere micro-affirmations.

Verifies:
- Affirmations are detected appropriately
- Energy matching works
- Determinism (same input → same selection)
"""

import pytest
from otto.atmosphere.affirmations import (
    Affirmation,
    AffirmationType,
    AFFIRMATIONS,
    get_affirmation,
    maybe_get_affirmation,
    detect_affirmation_type,
    EFFORT_SIGNALS,
    COMPLETION_SIGNALS,
)
from otto.atmosphere.patterns import ATMOSPHERE_SEED


class TestAffirmationDetection:
    """Tests for affirmation type detection."""

    def test_completion_detected(self):
        """Completion signals should be detected."""
        result = detect_affirmation_type("Finally done with this feature!")
        assert result == AffirmationType.COMPLETION

    def test_effort_detected(self):
        """Effort signals should be detected."""
        result = detect_affirmation_type("That was really hard to figure out")
        assert result == AffirmationType.EFFORT

    def test_return_detected(self):
        """Return signals should be detected."""
        result = detect_affirmation_type("Back to working on this")
        assert result == AffirmationType.RETURN

    def test_start_detected(self):
        """Start signals should be detected."""
        result = detect_affirmation_type("Starting the new feature")
        assert result == AffirmationType.START

    def test_momentum_based_detection(self):
        """Should detect based on momentum if no explicit signals."""
        # Crashed momentum → RECOVERY
        result = detect_affirmation_type("ok", momentum_phase="crashed")
        assert result == AffirmationType.RECOVERY

        # Building momentum → PROGRESS
        result = detect_affirmation_type("ok", momentum_phase="building")
        assert result == AffirmationType.PROGRESS

    def test_no_detection_for_neutral(self):
        """Neutral messages without signals might not get affirmation."""
        result = detect_affirmation_type("How does this work?", momentum_phase="rolling")
        # rolling → PERSISTENCE
        assert result == AffirmationType.PERSISTENCE


class TestGetAffirmation:
    """Tests for getting affirmations."""

    def test_get_completion_affirmation(self):
        """Should get completion affirmation."""
        result = get_affirmation(AffirmationType.COMPLETION, "medium")
        assert result is not None
        assert result.type == AffirmationType.COMPLETION

    def test_energy_matching_depleted(self):
        """Depleted energy should get subtle affirmation."""
        result = get_affirmation(AffirmationType.COMPLETION, "depleted")
        assert result is not None
        # Depleted gets "Done." not "Shipped!"
        assert result.text in ("Done.", "Complete.")

    def test_energy_matching_high(self):
        """High energy can get enthusiastic affirmation."""
        result = get_affirmation(AffirmationType.COMPLETION, "high")
        assert result is not None

    def test_determinism(self):
        """Same inputs should produce same output."""
        result1 = get_affirmation(
            AffirmationType.EFFORT, "medium", seed=ATMOSPHERE_SEED
        )
        result2 = get_affirmation(
            AffirmationType.EFFORT, "medium", seed=ATMOSPHERE_SEED
        )
        assert result1.text == result2.text


class TestMaybeGetAffirmation:
    """Tests for combined detection and selection."""

    def test_returns_affirmation_when_earned(self):
        """Should return affirmation when signals detected."""
        result = maybe_get_affirmation(
            "Finally finished this!",
            momentum_phase="building",
            energy_level="medium",
        )
        assert result is not None
        assert isinstance(result, Affirmation)

    def test_returns_none_for_questions(self):
        """Questions without signals might not earn affirmation."""
        result = maybe_get_affirmation(
            "What does this function do?",
            momentum_phase="cold_start",
            energy_level="high",
        )
        # cold_start has no affirmation type
        assert result is None


class TestAffirmationLists:
    """Tests for affirmation list structure."""

    def test_all_types_have_affirmations(self):
        """Every affirmation type should have affirmations."""
        for atype in AffirmationType:
            assert atype in AFFIRMATIONS
            assert len(AFFIRMATIONS[atype]) > 0

    def test_lists_are_sorted(self):
        """Affirmation lists should be sorted for determinism."""
        for atype, affirmations in AFFIRMATIONS.items():
            texts = [a.text for a in affirmations]
            assert texts == sorted(texts), f"{atype} list not sorted"

    def test_signal_lists_sorted(self):
        """Signal lists should be sorted."""
        assert list(EFFORT_SIGNALS) == sorted(EFFORT_SIGNALS)
        assert list(COMPLETION_SIGNALS) == sorted(COMPLETION_SIGNALS)
