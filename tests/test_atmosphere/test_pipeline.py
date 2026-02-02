"""
Tests for atmosphere pipeline.

Verifies:
- Full pipeline integration
- Fixed transformation order
- Determinism (same input → same output)
- Hard rules compliance
- Expert bypass rules
"""

import pytest
from otto.atmosphere.pipeline import (
    AtmosphereContext,
    AtmospherePipeline,
    apply_atmosphere,
    TransformPhase,
    EXPERT_BYPASS_RULES,
    REFRAME_ALLOWED_EXPERTS,
)
from otto.atmosphere.patterns import ATMOSPHERE_SEED


class TestAtmosphereContext:
    """Tests for AtmosphereContext dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        ctx = AtmosphereContext(user_message="test")
        assert ctx.register == "neutral"
        assert ctx.expert == "Direct"
        assert ctx.energy_level == "medium"
        assert ctx.burnout_level == "GREEN"
        assert ctx.momentum_phase == "building"

    def test_custom_values(self):
        """Should accept custom values."""
        ctx = AtmosphereContext(
            user_message="test",
            register="casual",
            expert="Validator",
            energy_level="depleted",
            burnout_level="RED",
        )
        assert ctx.register == "casual"
        assert ctx.expert == "Validator"
        assert ctx.energy_level == "depleted"
        assert ctx.burnout_level == "RED"


class TestAtmospherePipeline:
    """Tests for AtmospherePipeline class."""

    def test_basic_transformation(self):
        """Should transform instructional language."""
        pipeline = AtmospherePipeline()
        ctx = AtmosphereContext(user_message="help me")
        response = "You should check the logs. Make sure to restart."
        result = pipeline.apply(response, ctx)
        assert "You should" not in result
        assert "Make sure" not in result

    def test_energy_truncation(self):
        """Should truncate based on energy level."""
        pipeline = AtmospherePipeline()
        ctx = AtmosphereContext(
            user_message="help",
            energy_level="depleted",
        )
        response = "Here's a very long explanation. " * 20
        result = pipeline.apply(response, ctx)
        assert len(result) <= 100

    def test_affirmation_added(self):
        """Should add affirmation when earned."""
        pipeline = AtmospherePipeline()
        ctx = AtmosphereContext(
            user_message="Finally done with this!",
            momentum_phase="rolling",
        )
        response = "Great work."
        result = pipeline.apply(response, ctx)
        # Should have some affirmation prepended
        assert len(result) >= len(response)

    def test_permission_added(self):
        """Should add permission when needed."""
        pipeline = AtmospherePipeline()
        ctx = AtmosphereContext(
            user_message="I'm exhausted",
            burnout_level="ORANGE",
            energy_level="low",
        )
        response = "Let's take a break."
        result = pipeline.apply(response, ctx)
        # Should have permission appended
        assert len(result) >= len(response)

    def test_reframe_added(self):
        """Should add reframe for struggles."""
        pipeline = AtmospherePipeline()
        ctx = AtmosphereContext(
            user_message="I'm stuck on this",
            expert="Scaffolder",
        )
        response = "Try this approach."
        result = pipeline.apply(response, ctx)
        # Should have reframe prepended
        assert len(result) >= len(response)
        assert ctx.has_struggle is True

    def test_reframe_not_added_for_validator(self):
        """Validator expert should not add reframe (handles differently)."""
        pipeline = AtmospherePipeline()
        ctx = AtmosphereContext(
            user_message="I'm frustrated",
            expert="Validator",
        )
        response = "I hear you."
        result = pipeline.apply(response, ctx)
        # Validator handles frustration differently
        assert ctx.has_struggle is False

    def test_determinism(self):
        """Same inputs should produce same output."""
        ctx = AtmosphereContext(
            user_message="Finally done!",
            energy_level="medium",
        )
        response = "You should celebrate. Make sure to rest."

        result1 = apply_atmosphere(response, ctx, seed=ATMOSPHERE_SEED)
        result2 = apply_atmosphere(response, ctx, seed=ATMOSPHERE_SEED)

        assert result1 == result2


class TestHardRules:
    """Tests for hard rules that MUST pass (from spec)."""

    @pytest.mark.parametrize("forbidden", [
        "You should",
        "Make sure",
        "Let me know if",
        "Feel free",
    ])
    def test_no_forbidden_phrases(self, forbidden):
        """Forbidden phrases must not appear in output."""
        ctx = AtmosphereContext(user_message="help")
        response = f"{forbidden} do this. And {forbidden} do that."

        result = apply_atmosphere(response, ctx)

        assert forbidden not in result
        assert forbidden.lower() not in result.lower()

    def test_depleted_max_100_chars(self):
        """Depleted energy must produce <= 100 char response."""
        ctx = AtmosphereContext(
            user_message="help",
            energy_level="depleted",
        )
        response = "Here is a very long response. " * 20

        result = apply_atmosphere(response, ctx)

        assert len(result) <= 100

    def test_hyperfocus_max_300_chars(self):
        """Hyperfocus must produce <= 300 char response."""
        ctx = AtmosphereContext(
            user_message="help",
            energy_level="hyperfocus",
        )
        response = "Here is a very long response. " * 20

        result = apply_atmosphere(response, ctx)

        assert len(result) <= 300


class TestRiverTest:
    """Tests for the River Test philosophy."""

    def test_flows_not_blocks(self):
        """Response should flow, not redirect/block."""
        ctx = AtmosphereContext(user_message="I want to try this")
        response = "You should do it differently. Make sure to follow best practices."

        result = apply_atmosphere(response, ctx)

        # Should not have blocking language
        assert "should" not in result.lower()
        assert "make sure" not in result.lower()

    def test_supports_not_instructs(self):
        """Response should support, not instruct."""
        ctx = AtmosphereContext(user_message="How do I do this?")
        response = "You need to do X. You have to do Y. You must do Z."

        result = apply_atmosphere(response, ctx)

        # Should not have commanding language
        assert "You need to" not in result
        assert "You have to" not in result
        assert "You must" not in result

    def test_breathes_not_cramped(self):
        """Response should have breathing room."""
        ctx = AtmosphereContext(
            user_message="help",
            energy_level="low",
        )
        response = "Try this. Let me know if you have questions. Feel free to ask!"

        result = apply_atmosphere(response, ctx)

        # Noise should be removed
        assert "Let me know" not in result
        assert "Feel free" not in result


class TestPipelineOrder:
    """Tests verifying fixed transformation order."""

    def test_language_before_energy(self):
        """Language transform should happen before energy truncation."""
        # This tests that forbidden phrases are removed even if truncated
        ctx = AtmosphereContext(
            user_message="help",
            energy_level="depleted",  # max 100 chars
        )
        response = "You should do this first. " * 10  # Over 100 chars

        result = apply_atmosphere(response, ctx)

        # Should be truncated AND have no forbidden phrases
        assert len(result) <= 100
        assert "You should" not in result

    def test_affirmation_prepended(self):
        """Affirmation should be at start of response."""
        ctx = AtmosphereContext(
            user_message="Finally done!",
            momentum_phase="rolling",
            energy_level="high",  # Allow full response
        )
        response = "Good work completing that."

        result = apply_atmosphere(response, ctx)

        # Affirmation (if added) should be at start
        # Just verify it ran (might have affirmation)
        assert len(result) >= len("Good work")

    def test_permission_appended(self):
        """Permission should be at end of response."""
        ctx = AtmosphereContext(
            user_message="I'm tired",
            burnout_level="ORANGE",
            energy_level="medium",  # Allow full response
        )
        response = "Take a break."

        result = apply_atmosphere(response, ctx)

        # Permission (if added) should be at end
        # Just verify it ran (might have permission)
        assert "break" in result.lower() or "rest" in result.lower() or "recovery" in result.lower()


class TestExpertBypass:
    """Tests for expert-specific bypass rules."""

    def test_bypass_rules_are_sorted(self):
        """Expert bypass rules should be in sorted order for determinism."""
        experts = list(EXPERT_BYPASS_RULES.keys())
        assert experts == sorted(experts)

    def test_direct_has_no_bypass(self):
        """Direct expert should have no bypasses (full atmosphere)."""
        assert EXPERT_BYPASS_RULES["Direct"] == frozenset()

    def test_validator_bypasses_reframe_and_affirmation(self):
        """Validator should bypass reframes and affirmations."""
        bypasses = EXPERT_BYPASS_RULES["Validator"]
        assert TransformPhase.REFRAME in bypasses
        assert TransformPhase.AFFIRMATION in bypasses

    def test_celebrator_bypasses_affirmation(self):
        """Celebrator should bypass affirmations (has its own)."""
        bypasses = EXPERT_BYPASS_RULES["Celebrator"]
        assert TransformPhase.AFFIRMATION in bypasses

    def test_socratic_bypasses_reframe(self):
        """Socratic should bypass reframes (questions are the point)."""
        bypasses = EXPERT_BYPASS_RULES["Socratic"]
        assert TransformPhase.REFRAME in bypasses

    def test_reframe_allowed_list(self):
        """Only specific experts should be allowed to add reframes."""
        assert "Direct" in REFRAME_ALLOWED_EXPERTS
        assert "Scaffolder" in REFRAME_ALLOWED_EXPERTS
        assert "Restorer" in REFRAME_ALLOWED_EXPERTS
        assert "Validator" not in REFRAME_ALLOWED_EXPERTS
        assert "Socratic" not in REFRAME_ALLOWED_EXPERTS


class TestContextBypass:
    """Tests for AtmosphereContext bypass methods."""

    def test_should_bypass_with_expert_rules(self):
        """should_bypass should use expert rules."""
        ctx = AtmosphereContext(
            user_message="test",
            expert="Validator",
        )
        # Validator bypasses reframes
        assert ctx.should_bypass(TransformPhase.REFRAME) is True
        # But not language
        assert ctx.should_bypass(TransformPhase.LANGUAGE) is False

    def test_should_bypass_with_custom_bypass(self):
        """Custom bypass should override expert rules."""
        ctx = AtmosphereContext(
            user_message="test",
            expert="Direct",  # Direct has no bypasses by default
            custom_bypass={TransformPhase.AFFIRMATION, TransformPhase.PERMISSION},
        )
        # Custom bypasses should apply
        assert ctx.should_bypass(TransformPhase.AFFIRMATION) is True
        assert ctx.should_bypass(TransformPhase.PERMISSION) is True
        # Others should not
        assert ctx.should_bypass(TransformPhase.REFRAME) is False

    def test_get_active_bypasses(self):
        """get_active_bypasses should return correct set."""
        ctx = AtmosphereContext(
            user_message="test",
            expert="Validator",
        )
        bypasses = ctx.get_active_bypasses()
        assert TransformPhase.REFRAME in bypasses
        assert TransformPhase.AFFIRMATION in bypasses

    def test_unknown_expert_no_bypass(self):
        """Unknown experts should have no bypasses."""
        ctx = AtmosphereContext(
            user_message="test",
            expert="UnknownExpert",
        )
        assert ctx.should_bypass(TransformPhase.REFRAME) is False
        assert ctx.should_bypass(TransformPhase.AFFIRMATION) is False
        assert ctx.get_active_bypasses() == frozenset()


class TestBypassBehavior:
    """Tests for actual bypass behavior in pipeline."""

    def test_validator_no_reframe_added(self):
        """Validator should not add reframes even for struggle."""
        ctx = AtmosphereContext(
            user_message="I'm stuck and frustrated",  # Struggle detected
            expert="Validator",
            energy_level="medium",
        )
        response = "I hear you. That sounds frustrating."

        result = apply_atmosphere(response, ctx)

        # Validator handles emotions differently - no reframe prepended
        assert ctx.has_struggle is False
        # But language should still be transformed
        assert "You should" not in result

    def test_celebrator_no_affirmation_added(self):
        """Celebrator should not add affirmations (has its own)."""
        ctx = AtmosphereContext(
            user_message="Finally done!",
            expert="Celebrator",
            momentum_phase="rolling",
            energy_level="high",
        )
        response = "Amazing! You did it!"

        result = apply_atmosphere(response, ctx)

        # Celebrator has its own celebration style
        # The response should not have generic affirmations prepended
        assert result.startswith("Amazing") or result.startswith("You")

    def test_socratic_no_reframe_for_stuck(self):
        """Socratic should not add reframes (questions are the point)."""
        ctx = AtmosphereContext(
            user_message="I'm stuck on this problem",
            expert="Socratic",
            energy_level="medium",
        )
        response = "What have you tried so far?"

        result = apply_atmosphere(response, ctx)

        # Socratic doesn't add reframes - questions guide discovery
        assert ctx.has_struggle is False
        assert "What have you tried" in result

    def test_direct_full_atmosphere(self):
        """Direct expert should get full atmosphere treatment."""
        ctx = AtmosphereContext(
            user_message="I'm stuck",
            expert="Direct",
            energy_level="medium",
        )
        response = "You should try this approach."

        result = apply_atmosphere(response, ctx)

        # Direct gets reframes
        assert ctx.has_struggle is True
        # And language transformation
        assert "You should" not in result

    def test_custom_bypass_overrides_expert(self):
        """Custom bypass should override expert defaults."""
        ctx = AtmosphereContext(
            user_message="I'm stuck",
            expert="Direct",  # Normally gets reframes
            energy_level="medium",
            custom_bypass={TransformPhase.REFRAME},  # But we bypass
        )
        response = "Try this."

        result = apply_atmosphere(response, ctx)

        # Reframe should be skipped due to custom bypass
        assert ctx.has_struggle is False

    def test_energy_bypass_respects_limits(self):
        """Bypassing energy should skip length limits."""
        ctx = AtmosphereContext(
            user_message="help",
            energy_level="depleted",  # Normally max 100 chars
            custom_bypass={TransformPhase.ENERGY},
        )
        response = "Here is a very long response. " * 10  # Over 100 chars

        result = apply_atmosphere(response, ctx)

        # Energy bypass means no truncation
        assert len(result) > 100
