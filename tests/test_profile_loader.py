"""
Tests for Profile Loader
=========================

Tests profile loading with LIVRPS resolution.
"""

import pytest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from otto.profile_loader import (
    ProfileLoader,
    ResolvedProfile,
    DEFAULT_PROFILE,
    load_profile,
)
from otto.intake.profile_writer import write_profile, ProfileData


class TestResolvedProfile:
    """Tests for ResolvedProfile dataclass."""

    def test_default_values(self):
        """Test default profile values."""
        profile = ResolvedProfile()
        assert profile.chronotype == "variable"
        assert profile.protection_firmness == 0.5
        assert profile.otto_role == "companion"
        assert profile.profile_source == "defaults"

    def test_to_dict(self):
        """Test serialization to dict."""
        profile = ResolvedProfile()
        data = profile.to_dict()
        assert "chronotype" in data
        assert "protection_firmness" in data
        assert "otto_role" in data

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "chronotype": "night_owl",
            "protection_firmness": 0.8,
            "otto_role": "guardian",
        }
        profile = ResolvedProfile.from_dict(data)
        assert profile.chronotype == "night_owl"
        assert profile.protection_firmness == 0.8
        assert profile.otto_role == "guardian"

    def test_is_in_peak_hours(self):
        """Test peak hours detection."""
        profile = ResolvedProfile(peak_hours=[10, 11, 12])
        assert profile.is_in_peak_hours(10) is True
        assert profile.is_in_peak_hours(15) is False

    def test_is_in_recovery_hours(self):
        """Test recovery hours detection."""
        profile = ResolvedProfile(recovery_hours=[21, 22, 23])
        assert profile.is_in_recovery_hours(22) is True
        assert profile.is_in_recovery_hours(10) is False

    def test_get_protection_threshold(self):
        """Test protection threshold calculation."""
        # Low firmness = high threshold (intervene late)
        gentle = ResolvedProfile(protection_firmness=0.0)
        assert gentle.get_protection_threshold() == pytest.approx(0.8)

        # High firmness = low threshold (intervene early)
        firm = ResolvedProfile(protection_firmness=1.0)
        assert firm.get_protection_threshold() == pytest.approx(0.4)

        # Medium firmness = medium threshold
        moderate = ResolvedProfile(protection_firmness=0.5)
        assert moderate.get_protection_threshold() == pytest.approx(0.6)


class TestProfileLoader:
    """Tests for ProfileLoader class."""

    def test_loads_defaults_when_no_profile(self):
        """Test that defaults are used when no profile exists."""
        with TemporaryDirectory() as tmpdir:
            loader = ProfileLoader(Path(tmpdir))
            profile = loader.load()

            assert profile.profile_source == "defaults"
            assert profile.chronotype == DEFAULT_PROFILE["chronotype"]
            assert profile.protection_firmness == DEFAULT_PROFILE["protection_firmness"]

    def test_loads_base_profile_from_usda(self):
        """Test loading base profile from USD file."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)

            # Create a profile
            profile_data = ProfileData(traits={
                "chronotype": "morning_person",
                "protection_firmness": 0.7,
                "otto_role": "guardian",
            })
            write_profile(profile_data, otto_dir / "profile.usda")

            # Load it
            loader = ProfileLoader(otto_dir)
            profile = loader.load()

            assert profile.chronotype == "morning_person"
            assert profile.protection_firmness == 0.7
            assert profile.otto_role == "guardian"
            assert profile.profile_source == "intake"

    def test_calibration_overrides_base(self):
        """Test that calibration layer overrides base profile."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)

            # Create base profile
            base_data = ProfileData(traits={
                "chronotype": "morning_person",
                "protection_firmness": 0.5,
            })
            write_profile(base_data, otto_dir / "profile.usda")

            # Create calibration with override
            calibration_data = ProfileData(traits={
                "protection_firmness": 0.9,  # Override firmness
            })
            write_profile(calibration_data, otto_dir / "calibration.usda")

            # Load and verify override
            loader = ProfileLoader(otto_dir)
            profile = loader.load()

            assert profile.chronotype == "morning_person"  # From base
            assert profile.protection_firmness == 0.9  # From calibration
            assert profile.profile_source == "calibrated"

    def test_session_overrides_calibration(self):
        """Test that session layer overrides calibration."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)

            # Create base profile
            base_data = ProfileData(traits={
                "chronotype": "morning_person",
            })
            write_profile(base_data, otto_dir / "profile.usda")

            # Create session state
            session_dir = otto_dir / "state"
            session_dir.mkdir(parents=True)
            session_file = session_dir / "session.json"
            session_file.write_text(json.dumps({
                "current_energy": "low",
                "current_mood": "focused",
            }))

            # Load and verify session values
            loader = ProfileLoader(otto_dir)
            profile = loader.load()

            assert profile.current_energy == "low"
            assert profile.current_mood == "focused"

    def test_profile_exists(self):
        """Test profile existence check."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)
            loader = ProfileLoader(otto_dir)

            assert loader.profile_exists() is False

            # Create profile
            write_profile(ProfileData(traits={}), otto_dir / "profile.usda")

            assert loader.profile_exists() is True

    def test_save_session(self):
        """Test saving session state."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)
            loader = ProfileLoader(otto_dir)

            profile = ResolvedProfile(
                current_energy="high",
                current_mood="excited",
                exchanges_this_session=10,
            )

            loader.save_session(profile)

            # Verify saved
            session_file = otto_dir / "state" / "session.json"
            assert session_file.exists()

            with open(session_file) as f:
                data = json.load(f)

            assert data["current_energy"] == "high"
            assert data["current_mood"] == "excited"
            assert data["exchanges_this_session"] == 10

    def test_caching(self):
        """Test that profile is cached after first load."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)
            loader = ProfileLoader(otto_dir)

            profile1 = loader.load()
            profile2 = loader.load()

            assert profile1 is profile2  # Same object

    def test_force_reload(self):
        """Test force reload bypasses cache."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)
            loader = ProfileLoader(otto_dir)

            profile1 = loader.load()

            # Force reload
            loader.clear_cache()
            profile2 = loader.load(force_reload=True)

            # Different objects (reloaded)
            assert profile1 is not profile2


class TestLoadProfileFunction:
    """Tests for load_profile convenience function."""

    def test_loads_profile(self):
        """Test convenience function."""
        with TemporaryDirectory() as tmpdir:
            profile = load_profile(Path(tmpdir))
            assert isinstance(profile, ResolvedProfile)
            assert profile.profile_source == "defaults"
