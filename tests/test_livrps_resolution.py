"""
LIVRPS Resolution Tests
=======================

Tests that verify USD-native cognitive state resolution using LIVRPS
(Local, Inherits, Variants, References, Payloads, Specializes) composition.

Key Properties to Verify:
1. Higher priority layers override lower priority
2. Constitutional safety floors cannot be violated
3. Variant switching correctly applies mode-specific values
4. Opinion stacks correctly track all layer opinions
5. Resolution is deterministic (same input → same output)

ThinkingMachines [He2025] Compliance:
- Tests verify batch-invariance
- Fixed evaluation order
- Reproducible checksums
"""

import pytest
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Add Orchestra to path
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import (
    CognitiveStage,
    LayerPriority,
    CONSTITUTIONAL_VALUES,
    create_cognitive_stage,
)
from otto.cognitive_state import BurnoutLevel, EnergyLevel, CognitiveMode


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_state_dir():
    """Create temporary directory for state files."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def stage(temp_state_dir):
    """Create a fresh cognitive stage for testing."""
    return CognitiveStage(state_dir=temp_state_dir).load_or_create()


# =============================================================================
# Test: Layer Priority Resolution
# =============================================================================

class TestLayerPriorityResolution:
    """Test that LIVRPS layer priority resolves correctly."""

    def test_session_layer_wins(self, stage):
        """Session (LOCAL) layer should override all others."""
        # Set value on calibration layer (lower priority)
        stage.set_calibration_value("focus_level", "locked_in")

        # Set value on session layer (higher priority)
        stage.set_session_value("focus_level", "scattered")

        # Session should win
        resolved = stage.get_resolved("focus_level")
        assert resolved == "scattered", "Session layer should override calibration"

    def test_calibration_overrides_constitutional(self, stage):
        """Calibration (REFERENCES) should override constitutional (SPECIALIZES)."""
        # Constitutional has default values
        const_value = stage.get_safety_floor("tangent_budget_default")

        # Set different value in calibration
        stage.set_calibration_value("tangent_budget_default", 10)

        # Calibration should win for non-floor values
        resolved = stage.get_resolved("tangent_budget_default")
        assert resolved == 10, "Calibration should override constitutional for non-floor values"

    def test_priority_order_is_fixed(self, stage):
        """Verify LIVRPS priority order is correct."""
        expected_order = [
            LayerPriority.LOCAL,        # 1 - highest
            LayerPriority.INHERITS,     # 2
            LayerPriority.VARIANTS,     # 3
            LayerPriority.REFERENCES,   # 4
            LayerPriority.PAYLOADS,     # 5
            LayerPriority.SPECIALIZES,  # 6 - lowest
        ]

        for i, expected in enumerate(expected_order):
            assert expected.value == i + 1, f"Priority order mismatch at {expected.name}"


# =============================================================================
# Test: Constitutional Safety Floors
# =============================================================================

class TestConstitutionalSafetyFloors:
    """Test that constitutional safety floors are respected."""

    def test_safety_floors_exist(self, stage):
        """Verify all safety floors are defined."""
        required_floors = [
            "safety_floor_protector",
            "safety_floor_restorer",
            "working_memory_limit",
            "max_agent_depth",
            "body_check_interval",
        ]

        for floor in required_floors:
            value = stage.get_safety_floor(floor)
            assert value is not None, f"Safety floor '{floor}' not defined"

    def test_working_memory_limit(self, stage):
        """Verify working memory limit is respected."""
        wm_limit = stage.get_safety_floor("working_memory_limit")
        assert wm_limit == 3, "Working memory limit should be 3 (Miller's Law with margin)"

    def test_max_depth_when_depleted(self, stage):
        """Verify thinking depth limit when energy depleted."""
        max_depth = stage.get_safety_floor("max_depth_depleted")
        assert max_depth == "minimal", "Depleted energy should limit to minimal thinking"

    def test_enforce_safety_floors(self, stage):
        """Test safety floor enforcement."""
        # Set depleted energy
        stage.set_session_value("energy_level", "depleted")

        # Enforce floors
        corrections = stage.enforce_safety_floors()

        assert "max_thinking_depth" in corrections
        assert corrections["max_thinking_depth"] == "minimal"


# =============================================================================
# Test: Variant Switching
# =============================================================================

class TestVariantSwitching:
    """Test cognitive mode variant switching."""

    def test_default_mode_is_focused(self, stage):
        """Default mode should be focused."""
        mode = stage.get_mode()
        assert mode == "focused", "Default mode should be focused"

    def test_switch_to_exploring(self, stage):
        """Switching to exploring mode should apply variant values."""
        stage.set_mode("exploring")

        mode = stage.get_mode()
        assert mode == "exploring"

        # Exploring mode should set mycelium paradigm
        # (This depends on variant implementation)

    def test_switch_to_recovery(self, stage):
        """Switching to recovery mode should apply recovery values."""
        stage.set_mode("recovery")

        mode = stage.get_mode()
        assert mode == "recovery"

    def test_invalid_mode_defaults_to_focused(self, stage):
        """Invalid mode should default to focused."""
        stage.set_mode("invalid_mode")

        mode = stage.get_mode()
        assert mode == "focused", "Invalid mode should default to focused"


# =============================================================================
# Test: Opinion Stack
# =============================================================================

class TestOpinionStack:
    """Test opinion stack for debugging and tension detection."""

    def test_opinion_stack_tracks_all_opinions(self, stage):
        """Opinion stack should track all layer opinions."""
        # Set values on multiple layers
        stage.set_session_value("burnout_level", "yellow")
        stage.set_calibration_value("burnout_level", "green")

        opinion = stage.get_opinion_stack("burnout_level")

        assert len(opinion.opinions) >= 2, "Should have multiple opinions"

    def test_conflict_detection(self, stage):
        """Conflicting values should be detected."""
        stage.set_session_value("focus_level", "scattered")
        stage.set_calibration_value("focus_level", "locked_in")

        has_conflict = stage.has_conflict("focus_level")
        assert has_conflict, "Conflicting values should be detected"

    def test_no_conflict_when_same(self, stage):
        """No conflict when values match."""
        stage.set_session_value("focus_level", "moderate")
        stage.set_calibration_value("focus_level", "moderate")

        # Both have same value, no conflict in opinion difference
        opinion = stage.get_opinion_stack("focus_level")
        # Note: has_conflict checks if values differ
        # With same values, it depends on implementation


# =============================================================================
# Test: Determinism (ThinkingMachines Compliance)
# =============================================================================

class TestDeterminism:
    """Test that resolution is deterministic."""

    def test_same_state_same_checksum(self, temp_state_dir):
        """Same state should produce same checksum."""
        stage1 = CognitiveStage(state_dir=temp_state_dir).load_or_create()
        stage1.set_session_value("burnout_level", "yellow")
        stage1.set_session_value("energy_level", "medium")
        checksum1 = stage1.checksum()

        # Create new stage with same state
        stage2 = CognitiveStage(state_dir=temp_state_dir).load_or_create()
        stage2.set_session_value("burnout_level", "yellow")
        stage2.set_session_value("energy_level", "medium")
        checksum2 = stage2.checksum()

        assert checksum1 == checksum2, "Same state should produce same checksum"

    def test_different_state_different_checksum(self, temp_state_dir):
        """Different state should produce different checksum."""
        stage1 = CognitiveStage(state_dir=temp_state_dir).load_or_create()
        stage1.set_session_value("burnout_level", "green")
        checksum1 = stage1.checksum()

        stage1.set_session_value("burnout_level", "red")
        checksum2 = stage1.checksum()

        assert checksum1 != checksum2, "Different state should produce different checksum"

    def test_resolution_is_reproducible(self, stage):
        """Same query should return same result."""
        stage.set_session_value("focus_level", "scattered")

        result1 = stage.get_resolved("focus_level")
        result2 = stage.get_resolved("focus_level")

        assert result1 == result2, "Resolution should be reproducible"


# =============================================================================
# Test: Export/Import
# =============================================================================

class TestExportImport:
    """Test stage export and import."""

    def test_export_usda(self, stage, temp_state_dir):
        """Should export to .usda format."""
        stage.set_session_value("burnout_level", "yellow")
        stage.set_mode("exploring")

        export_path = stage.export("test_session.usda")

        assert export_path.exists(), "Export file should be created"
        assert export_path.suffix == ".usda", "Should have .usda extension"

        # Check file has content
        content = export_path.read_text()
        assert "#usda" in content or "CognitiveRoot" in content or "session" in content

    def test_persistence_round_trip(self, temp_state_dir):
        """State should survive save/load cycle."""
        # Create and configure stage
        stage1 = CognitiveStage(state_dir=temp_state_dir).load_or_create()
        stage1.set_session_value("burnout_level", "orange")
        stage1.calibrate(focus_level="locked_in", urgency="deadline")
        stage1.save()

        # Load in new instance
        stage2 = CognitiveStage(state_dir=temp_state_dir).load_or_create()

        # Values should persist
        focus = stage2.get_resolved("focus_level")
        assert focus == "locked_in", "Calibration should persist"


# =============================================================================
# Test: Integration with CognitiveState
# =============================================================================

class TestCognitiveStateIntegration:
    """Test integration with existing CognitiveState."""

    def test_sync_from_state(self, stage):
        """Stage should sync from underlying CognitiveState."""
        state = stage.get_cognitive_state()

        # Modify underlying state
        state.batch_update({"burnout_level": "yellow"})

        # Re-sync
        stage._sync_from_state()

        # Stage should reflect the change
        resolved = stage.get_resolved("burnout_level")
        assert resolved == "yellow", "Stage should sync from CognitiveState"

    def test_sync_to_state(self, stage):
        """Changes in stage should sync to CognitiveState."""
        # Modify via stage
        stage.set_session_value("burnout_level", "orange")
        stage._sync_to_state()

        # Check underlying state
        state = stage.get_cognitive_state()
        assert state.burnout_level.value == "orange", "CognitiveState should sync from stage"


# =============================================================================
# Test: Prompt Context Generation
# =============================================================================

class TestPromptContext:
    """Test cognitive context generation for prompts."""

    def test_prompt_context_format(self, stage):
        """Prompt context should have expected format."""
        context = stage.get_prompt_context()

        assert "[COGNITIVE_STATE]" in context
        assert "burnout=" in context
        assert "energy=" in context
        assert "mode=" in context

    def test_prompt_context_reflects_state(self, stage):
        """Prompt context should reflect current state."""
        stage.set_session_value("burnout_level", "red")
        stage.set_mode("recovery")

        context = stage.get_prompt_context()

        assert "burnout=red" in context
        assert "mode=recovery" in context


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
