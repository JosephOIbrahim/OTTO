"""
Tests for atmosphere language pattern transformation.

Verifies:
- Instructional patterns are removed/replaced
- Determinism (same input → same output)
- Forbidden phrases eliminated
"""

import pytest
from otto.atmosphere.patterns import (
    LanguageTransformer,
    transform_language,
    INSTRUCTIONAL_PATTERNS,
    ATMOSPHERE_SEED,
)


class TestLanguageTransformer:
    """Tests for LanguageTransformer class."""

    def test_you_should_transformation(self):
        """'You should' should become 'Let's' or similar."""
        transformer = LanguageTransformer()
        result = transformer.transform("You should check the logs.")
        assert "You should" not in result
        # Should have some replacement
        assert len(result) > 10

    def test_you_need_to_transformation(self):
        """'You need to' should become 'Let's' or 'Here's the move:'."""
        transformer = LanguageTransformer()
        result = transformer.transform("You need to restart the server.")
        assert "You need to" not in result

    def test_make_sure_removed(self):
        """'Make sure' should be removed entirely."""
        transformer = LanguageTransformer()
        result = transformer.transform("Make sure to save your work first.")
        assert "Make sure" not in result
        assert "make sure" not in result.lower()

    def test_let_me_know_removed(self):
        """'Let me know if you have questions' should be removed."""
        transformer = LanguageTransformer()
        result = transformer.transform(
            "Here's the fix. Let me know if you have questions."
        )
        assert "Let me know" not in result

    def test_feel_free_removed(self):
        """'Feel free to' should be removed."""
        transformer = LanguageTransformer()
        result = transformer.transform("Feel free to ask if you need help.")
        assert "Feel free" not in result
        assert "feel free" not in result.lower()

    def test_determinism(self):
        """Same input with same seed should produce same output."""
        text = "You should definitely try this approach. Make sure to test it."

        result1 = transform_language(text, seed=ATMOSPHERE_SEED)
        result2 = transform_language(text, seed=ATMOSPHERE_SEED)

        assert result1 == result2

    def test_different_seeds_may_differ(self):
        """Different seeds can produce different outputs."""
        text = "You should check the code."

        result1 = transform_language(text, seed=123)
        result2 = transform_language(text, seed=456)

        # Both should have transformed, but might differ
        assert "You should" not in result1
        assert "You should" not in result2

    def test_whitespace_cleanup(self):
        """Should clean up whitespace artifacts."""
        transformer = LanguageTransformer()
        result = transformer.transform("You should  check   this.")
        # No double spaces
        assert "  " not in result

    def test_capitalization_preserved(self):
        """First letter should be capitalized after transformation."""
        transformer = LanguageTransformer()
        result = transformer.transform("You should start here.")
        assert result[0].isupper()

    def test_pattern_list_sorted(self):
        """Pattern list should be sorted for determinism."""
        patterns = [p.pattern for p in INSTRUCTIONAL_PATTERNS]
        assert patterns == sorted(patterns)


class TestHardRules:
    """Tests for hard rules that MUST pass (from spec)."""

    @pytest.mark.parametrize("forbidden", [
        "You should",
        "Make sure",
        "Let me know if",
        "Feel free",
    ])
    def test_forbidden_phrases_removed(self, forbidden):
        """Forbidden phrases must not appear in transformed output."""
        transformer = LanguageTransformer()

        # Test with phrase at start
        text = f"{forbidden} check the logs."
        result = transformer.transform(text)
        assert forbidden not in result
        assert forbidden.lower() not in result.lower()

    def test_i_suggest_transformation(self):
        """'I suggest' variants should be transformed."""
        transformer = LanguageTransformer()
        result = transformer.transform("I would suggest that you try this.")
        assert "I would suggest" not in result
        assert "I suggest" not in result

    def test_its_important_removed(self):
        """'It's important' should be removed."""
        transformer = LanguageTransformer()
        result = transformer.transform("It's important to test your code.")
        assert "It's important" not in result
        assert "important to" not in result.lower()


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_string(self):
        """Empty string should return empty."""
        result = transform_language("")
        assert result == ""

    def test_no_patterns(self):
        """Text without patterns should pass through."""
        text = "The code works great."
        result = transform_language(text)
        assert result == text

    def test_multiple_patterns(self):
        """Multiple patterns in one text should all be transformed."""
        text = "You should check this. Make sure to test it. Feel free to ask."
        result = transform_language(text)
        assert "You should" not in result
        assert "Make sure" not in result
        assert "Feel free" not in result

    def test_preserve_content(self):
        """Should preserve non-pattern content."""
        text = "The function returns true. You should call it with params."
        result = transform_language(text)
        assert "function returns true" in result
