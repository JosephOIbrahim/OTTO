"""
Tests for atmosphere energy matching.

Verifies:
- Energy profiles are correct
- Response truncation works
- Breathing room is added appropriately
"""

import pytest
from otto.atmosphere.energy import (
    EnergyLevel,
    EnergyProfile,
    ENERGY_PROFILES,
    get_energy_profile,
    match_energy,
    truncate_to_energy,
    should_add_breathing_room,
    add_breathing_room,
    get_celebration_prefix,
)


class TestEnergyProfiles:
    """Tests for energy profile structure."""

    def test_all_levels_have_profiles(self):
        """Every energy level should have a profile."""
        for level in EnergyLevel:
            assert level in ENERGY_PROFILES

    def test_depleted_is_most_restrictive(self):
        """Depleted should have shortest max_length."""
        depleted = ENERGY_PROFILES[EnergyLevel.DEPLETED]
        for level in EnergyLevel:
            if level != EnergyLevel.DEPLETED:
                other = ENERGY_PROFILES[level]
                assert depleted.max_length <= other.max_length

    def test_hyperfocus_has_no_lift(self):
        """Hyperfocus should have zero lift (stay out of way)."""
        hyperfocus = ENERGY_PROFILES[EnergyLevel.HYPERFOCUS]
        assert hyperfocus.lift_factor == 0.0

    def test_depleted_has_no_lift(self):
        """Depleted should have zero lift (just meet them)."""
        depleted = ENERGY_PROFILES[EnergyLevel.DEPLETED]
        assert depleted.lift_factor == 0.0


class TestGetEnergyProfile:
    """Tests for energy profile retrieval."""

    def test_get_by_string(self):
        """Should get profile by string level."""
        profile = get_energy_profile("depleted")
        assert profile.level == EnergyLevel.DEPLETED

    def test_case_insensitive(self):
        """Should handle different cases."""
        profile = get_energy_profile("MEDIUM")
        assert profile.level == EnergyLevel.MEDIUM

    def test_hyperfocused_alias(self):
        """Should handle 'hyperfocused' alias."""
        profile = get_energy_profile("hyperfocused")
        assert profile.level == EnergyLevel.HYPERFOCUS

    def test_unknown_defaults_to_medium(self):
        """Unknown levels should default to MEDIUM."""
        profile = get_energy_profile("unknown_level")
        assert profile.level == EnergyLevel.MEDIUM


class TestTruncation:
    """Tests for response truncation."""

    def test_short_response_unchanged(self):
        """Short responses should not be truncated."""
        profile = get_energy_profile("medium")  # max_length=500
        response = "This is a short response."
        result = truncate_to_energy(response, profile)
        assert result == response

    def test_long_response_truncated(self):
        """Long responses should be truncated."""
        profile = get_energy_profile("depleted")  # max_length=100
        response = "A" * 200
        result = truncate_to_energy(response, profile)
        assert len(result) <= profile.max_length

    def test_truncates_at_sentence_boundary(self):
        """Should prefer sentence boundaries when truncating."""
        profile = get_energy_profile("depleted")  # max_length=100
        response = "First sentence. Second sentence. Third sentence which is longer."
        result = truncate_to_energy(response, profile)
        # Should end at a sentence
        assert result.endswith(".")


class TestBreathingRoom:
    """Tests for breathing room functionality."""

    def test_depleted_needs_breathing_room(self):
        """Depleted should need breathing room."""
        profile = get_energy_profile("depleted")
        assert should_add_breathing_room("any response", profile) is True

    def test_low_needs_breathing_room(self):
        """Low energy should need breathing room."""
        profile = get_energy_profile("low")
        assert should_add_breathing_room("any response", profile) is True

    def test_hyperfocus_needs_breathing_room(self):
        """Hyperfocus should need breathing room (minimal responses)."""
        profile = get_energy_profile("hyperfocus")
        assert should_add_breathing_room("any response", profile) is True

    def test_high_energy_no_breathing_room(self):
        """High energy doesn't necessarily need breathing room."""
        profile = get_energy_profile("high")
        assert should_add_breathing_room("any response", profile) is False

    def test_add_breathing_room_removes_filler(self):
        """Should remove trailing filler phrases."""
        response = "Here's the fix. Let me know if you have questions."
        result = add_breathing_room(response)
        assert "Let me know" not in result

    def test_add_breathing_room_removes_hope_helps(self):
        """Should remove 'Hope this helps'."""
        response = "Try this approach. Hope this helps!"
        result = add_breathing_room(response)
        assert "Hope this helps" not in result


class TestMatchEnergy:
    """Tests for full energy matching."""

    def test_match_depleted(self):
        """Depleted energy should truncate and add breathing room."""
        response = "Here's a detailed explanation. " * 10 + "Let me know if you need help."
        result = match_energy(response, "depleted")
        assert len(result) <= 100
        assert "Let me know" not in result

    def test_match_hyperfocus(self):
        """Hyperfocus should keep responses short."""
        response = "Here's a detailed explanation. " * 10
        result = match_energy(response, "hyperfocus")
        assert len(result) <= 300


class TestCelebrationPrefix:
    """Tests for energy-appropriate celebrations."""

    def test_depleted_celebration_subtle(self):
        """Depleted gets subtle celebration."""
        result = get_celebration_prefix("depleted", is_completion=True)
        assert result == "Done."

    def test_hyperfocus_celebration_minimal(self):
        """Hyperfocus gets minimal/no celebration."""
        result = get_celebration_prefix("hyperfocus", is_completion=True)
        assert result == ""  # Don't break flow

    def test_no_completion_no_celebration(self):
        """Non-completion should not get celebration."""
        result = get_celebration_prefix("high", is_completion=False)
        assert result is None


class TestHardRules:
    """Tests for hard rules that MUST pass (from spec)."""

    def test_depleted_response_short(self):
        """Depleted energy must produce response <= 100 chars."""
        long_response = "This is a very long response. " * 20
        result = match_energy(long_response, "depleted")
        assert len(result) <= 100

    def test_hyperfocus_response_short(self):
        """Hyperfocus must produce response <= 300 chars."""
        long_response = "This is a very long response. " * 20
        result = match_energy(long_response, "hyperfocus")
        assert len(result) <= 300
