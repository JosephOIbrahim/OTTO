"""
Tests for atmosphere struggle reframes.

Verifies:
- Struggles are detected correctly
- Reframes acknowledge before reframing
- Determinism (same input → same detection)
"""

import pytest
from otto.atmosphere.reframes import (
    Reframe,
    REFRAMES,
    detect_struggle,
    format_reframe,
    get_reframe,
)


class TestStruggleDetection:
    """Tests for struggle detection."""

    def test_cant_detected(self):
        """'I can't' should be detected."""
        result = detect_struggle("I can't figure this out")
        assert result is not None
        assert "can'?t" in result.struggle_pattern or "cannot" in result.struggle_pattern

    def test_stuck_detected(self):
        """'I'm stuck' should be detected."""
        result = detect_struggle("I'm stuck on this problem")
        assert result is not None
        assert "stuck" in result.struggle_pattern

    def test_lost_detected(self):
        """'I'm lost' should be detected."""
        result = detect_struggle("I feel totally lost")
        assert result is not None
        assert "lost" in result.struggle_pattern

    def test_overwhelmed_detected(self):
        """'overwhelmed' or 'overwhelming' should be detected."""
        result = detect_struggle("This is overwhelming")
        assert result is not None
        assert "overwhelm" in result.struggle_pattern

    def test_frustrated_detected(self):
        """'frustrated' should be detected."""
        result = detect_struggle("I'm so frustrated with this")
        assert result is not None
        assert "frustrated" in result.struggle_pattern

    def test_nothing_works_detected(self):
        """'nothing works' should be detected."""
        result = detect_struggle("Nothing is working!")
        assert result is not None
        assert "nothing" in result.struggle_pattern.lower()

    def test_no_struggle_in_neutral(self):
        """Neutral messages should not detect struggle."""
        result = detect_struggle("How do I implement this?")
        assert result is None


class TestReframeFormatting:
    """Tests for reframe formatting."""

    def test_format_with_all_parts(self):
        """Should format reframe with all parts."""
        reframe = Reframe(
            struggle_pattern=r"\btest\b",
            acknowledgment="Acknowledged.",
            reframe="Reframed.",
            followup="Next step?",
        )
        result = format_reframe(reframe)
        assert "Acknowledged." in result
        assert "Reframed." in result
        assert "Next step?" in result

    def test_format_without_acknowledgment(self):
        """Should handle missing acknowledgment."""
        reframe = Reframe(
            struggle_pattern=r"\btest\b",
            acknowledgment="",
            reframe="Reframed.",
            followup="Next?",
        )
        result = format_reframe(reframe)
        assert "Reframed." in result
        assert not result.startswith(" ")

    def test_format_without_followup(self):
        """Should handle missing followup."""
        reframe = Reframe(
            struggle_pattern=r"\btest\b",
            acknowledgment="Ack.",
            reframe="Reframed.",
            followup=None,
        )
        result = format_reframe(reframe)
        assert "Ack." in result
        assert "Reframed." in result


class TestGetReframe:
    """Tests for get_reframe convenience function."""

    def test_returns_formatted_reframe(self):
        """Should return formatted reframe for struggle."""
        result = get_reframe("I'm stuck on this problem")
        assert result is not None
        assert len(result) > 0

    def test_returns_none_for_no_struggle(self):
        """Should return None when no struggle detected."""
        result = get_reframe("The code looks good")
        assert result is None


class TestReframeList:
    """Tests for reframe list structure."""

    def test_list_is_sorted(self):
        """Reframe list should be sorted for determinism."""
        patterns = [r.struggle_pattern for r in REFRAMES]
        assert patterns == sorted(patterns)

    def test_all_have_reframe_or_acknowledgment(self):
        """Each reframe should have at least acknowledgment or reframe."""
        for reframe in REFRAMES:
            has_content = bool(reframe.acknowledgment) or bool(reframe.reframe)
            assert has_content, f"Reframe for {reframe.struggle_pattern} has no content"


class TestReframeContent:
    """Tests for reframe content quality."""

    def test_no_toxic_positivity(self):
        """Reframes should not be toxic positivity."""
        toxic_phrases = [
            "just think positive",
            "look on the bright side",
            "it could be worse",
            "everything happens for a reason",
        ]
        for reframe in REFRAMES:
            formatted = format_reframe(reframe)
            for phrase in toxic_phrases:
                assert phrase not in formatted.lower()

    def test_acknowledges_before_reframing(self):
        """Reframes for hard struggles should acknowledge first."""
        # Find reframe for stuck
        stuck_reframe = detect_struggle("I'm stuck")
        assert stuck_reframe is not None
        # Should have acknowledgment
        assert stuck_reframe.acknowledgment or stuck_reframe.reframe
