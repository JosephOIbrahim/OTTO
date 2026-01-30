"""
Tests for Calibration Store
============================

Tests for the persistence layer for learned calibration values.
"""

import pytest
import tempfile
import json
from pathlib import Path

from otto.calibration import (
    CalibrationStore,
    CalibrationValue,
    create_calibration_store,
)


class TestCalibrationValue:
    """Tests for CalibrationValue dataclass."""

    def test_default_values(self):
        """CalibrationValue has sensible defaults."""
        cv = CalibrationValue(name="test", value="hello")
        assert cv.name == "test"
        assert cv.value == "hello"
        assert cv.confidence == 0.5
        assert cv.observations == 1
        assert cv.stable_count == 1

    def test_update_same_value_increases_confidence(self):
        """Repeated same value increases confidence."""
        cv = CalibrationValue(name="test", value="stable")
        initial_confidence = cv.confidence

        cv.update("stable")

        assert cv.confidence > initial_confidence
        assert cv.stable_count == 2
        assert cv.observations == 2

    def test_update_different_value_decreases_confidence(self):
        """Different value decreases confidence."""
        cv = CalibrationValue(name="test", value="stable", confidence=0.8)
        initial_confidence = cv.confidence

        cv.update("different")

        assert cv.confidence < initial_confidence
        assert cv.stable_count == 1
        assert cv.value == "stable"  # Value unchanged yet

    def test_update_switches_value_on_low_confidence(self):
        """Value switches when confidence drops below threshold."""
        cv = CalibrationValue(name="test", value="old", confidence=0.3)

        cv.update("new")

        # Confidence was at threshold, should switch
        assert cv.value == "new"
        assert cv.confidence == 0.5  # Reset to neutral

    def test_confidence_bounded_at_1(self):
        """Confidence cannot exceed 1.0."""
        cv = CalibrationValue(name="test", value="stable", confidence=0.95)

        for _ in range(10):
            cv.update("stable")

        assert cv.confidence <= 1.0

    def test_confidence_bounded_at_0(self):
        """Confidence cannot go below 0.0."""
        cv = CalibrationValue(name="test", value="stable", confidence=0.1)

        for i in range(10):
            cv.update(f"different_{i}")

        assert cv.confidence >= 0.0

    def test_is_confident_threshold(self):
        """is_confident respects threshold."""
        cv = CalibrationValue(name="test", value="stable", confidence=0.6)

        assert not cv.is_confident(threshold=0.7)
        assert cv.is_confident(threshold=0.5)

    def test_to_dict(self):
        """to_dict produces serializable dict."""
        cv = CalibrationValue(name="test", value="hello")
        d = cv.to_dict()

        assert d["name"] == "test"
        assert d["value"] == "hello"
        assert "confidence" in d
        assert "observations" in d

    def test_from_dict_roundtrip(self):
        """from_dict restores from to_dict."""
        cv = CalibrationValue(name="test", value="hello", confidence=0.8)
        d = cv.to_dict()
        restored = CalibrationValue.from_dict(d)

        assert restored.name == cv.name
        assert restored.value == cv.value
        assert restored.confidence == cv.confidence


class TestCalibrationStore:
    """Tests for CalibrationStore."""

    def test_create_store(self):
        """Store can be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = create_calibration_store(Path(tmpdir))
            assert store is not None

    def test_set_and_get(self):
        """Can set and get values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))

            store.set("focus_level", "locked_in", confidence=0.8)
            value = store.get("focus_level")

            assert value is not None
            assert value.value == "locked_in"
            assert value.confidence == 0.8

    def test_get_value_simple(self):
        """get_value returns just the value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))
            store.set("theme", "dark")

            assert store.get_value("theme") == "dark"
            assert store.get_value("nonexistent") is None
            assert store.get_value("nonexistent", "default") == "default"

    def test_get_confident_value(self):
        """get_confident_value respects threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))
            store.set("low_conf", "maybe", confidence=0.5)
            store.set("high_conf", "definitely", confidence=0.9)

            assert store.get_confident_value("low_conf") is None
            assert store.get_confident_value("high_conf") == "definitely"
            assert store.get_confident_value("low_conf", threshold=0.4) == "maybe"

    def test_record_observation(self):
        """record_observation tracks values with learning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))

            # First observation - low confidence
            cv = store.record_observation("preference", "option_a")
            assert cv.confidence == 0.3

            # Same observation - increases confidence
            cv = store.record_observation("preference", "option_a")
            assert cv.confidence > 0.3

    def test_list_values(self):
        """list_values returns all value names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))
            store.set("a", 1)
            store.set("b", 2)
            store.set("c", 3)

            names = store.list_values()
            assert "a" in names
            assert "b" in names
            assert "c" in names

    def test_list_confident_values(self):
        """list_confident_values filters by confidence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))
            store.set("confident", "yes", confidence=0.9)
            store.set("uncertain", "maybe", confidence=0.4)

            confident = store.list_confident_values()
            assert "confident" in confident
            assert "uncertain" not in confident

    def test_delete(self):
        """delete removes values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))
            store.set("temp", "value")

            assert store.delete("temp") is True
            assert store.get("temp") is None
            assert store.delete("nonexistent") is False

    def test_clear(self):
        """clear removes all values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))
            store.set("a", 1)
            store.set("b", 2)

            store.clear()

            assert len(store.list_values()) == 0

    def test_save_and_load(self):
        """Values persist across store instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Create and save
            store1 = CalibrationStore(path)
            store1.set("persistent", "value", confidence=0.85)
            store1.save()

            # Load in new instance
            store2 = CalibrationStore(path)
            value = store2.get("persistent")

            assert value is not None
            assert value.value == "value"
            assert value.confidence == 0.85

    def test_usda_export(self):
        """USDA file is created for debugging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            store = CalibrationStore(path)
            store.set("focus_level", "locked_in", confidence=0.8)
            store.save()

            usda_path = path / "calibration.usda"
            assert usda_path.exists()

            content = usda_path.read_text()
            assert "#usda 1.0" in content
            assert "focus_level" in content

    def test_get_summary(self):
        """get_summary provides overview."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))
            store.set("a", 1, confidence=0.9)
            store.set("b", 2, confidence=0.5)

            summary = store.get_summary()

            assert summary["total_values"] == 2
            assert summary["confident_values"] == 1
            assert "a" in summary["values"]


class TestCalibrationStoreEdgeCases:
    """Edge case tests for CalibrationStore."""

    def test_handles_missing_directory(self):
        """Store creates directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "calibration"
            store = CalibrationStore(path)
            store.set("test", "value")
            store.save()

            assert path.exists()

    def test_handles_corrupted_json(self):
        """Store handles corrupted JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            json_path = path / "calibration.json"
            json_path.write_text("not valid json")

            # Should not crash
            store = CalibrationStore(path)
            assert len(store.list_values()) == 0

    def test_atomic_write_on_save(self):
        """Save uses atomic write pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            store = CalibrationStore(path)
            store.set("test", "value")
            store.save()

            # No temp file should remain
            tmp_path = path / "calibration.tmp"
            assert not tmp_path.exists()

    def test_update_existing_value(self):
        """set updates existing values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(Path(tmpdir))
            store.set("key", "initial")
            store.set("key", "updated")

            assert store.get_value("key") == "updated"
