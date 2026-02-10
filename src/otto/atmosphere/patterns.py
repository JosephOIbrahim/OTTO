"""
Language Pattern Transformation for OTTO Atmosphere.

Transforms instructional language into supportive language.

The Six Atmosphere Principles:
1. Current, Not Dam: "Let's..." instead of "You should..."
2. Effort Over Outcome: Acknowledge the push, not the result
3. Permission Before Request: Grant permission before guilt forms
4. "We" Not "You Should": Collaborative, not commanding
5. Soft Landings: "Picking back up:" instead of "You forgot to..."
6. Breathing Room: Silence is better than noise

Determinism:
- Sorted pattern lists for deterministic iteration
- Fixed seed (0xCAFEBABE) for replacement selection
- Same inputs always produce same outputs
"""

import re
from dataclasses import dataclass
from typing import Dict, Final, List, Optional, Tuple

# Fixed seed for deterministic replacement selection
ATMOSPHERE_SEED: Final[int] = 0xCAFEBABE


@dataclass
class PatternReplacement:
    """A pattern and its possible replacements."""
    pattern: str
    replacements: Tuple[str, ...]
    flags: int = re.IGNORECASE


# Sorted pattern lists for deterministic iteration
# Patterns sorted by regex string for reproducibility
INSTRUCTIONAL_PATTERNS: Final[List[PatternReplacement]] = sorted([
    # "You should" variants
    PatternReplacement(
        r"\bYou should\b",
        ("Let's", "We could", "One way:"),
    ),
    PatternReplacement(
        r"\bYou need to\b",
        ("Let's", "Here's the move:"),
    ),
    PatternReplacement(
        r"\bYou have to\b",
        ("Let's", "Here's the move:"),
    ),
    PatternReplacement(
        r"\bYou must\b",
        ("Let's", "Here's the move:"),
    ),
    PatternReplacement(
        r"\bYou might want to\b",
        ("One option:", "Could try:"),
    ),
    PatternReplacement(
        r"\bYou could try\b",
        ("Could try:", "One way:"),
    ),

    # "Make sure" variants (remove entirely)
    PatternReplacement(
        r"\bMake sure (to |that )?\b",
        ("",),
    ),
    PatternReplacement(
        r"\bBe sure (to |that )?\b",
        ("",),
    ),
    PatternReplacement(
        r"\bEnsure (that )?\b",
        ("",),
    ),

    # "Don't forget" variants
    PatternReplacement(
        r"\bDon't forget (to )?\b",
        ("When you're ready:", "Also:"),
    ),
    PatternReplacement(
        r"\bRemember (to )?\b",
        ("Also:", ""),
    ),

    # Noise phrases (remove entirely)
    PatternReplacement(
        r"\bLet me know if\b[^.!?]*[.!?]?",
        ("",),
    ),
    PatternReplacement(
        r"\bFeel free\b[^.!?]*[.!?]?",
        ("",),
    ),
    PatternReplacement(
        r"\bDon't hesitate to\b",
        ("",),
    ),
    PatternReplacement(
        r"\bPlease (feel free to |don't hesitate to )?\b",
        ("",),
    ),

    # "I suggest" variants
    PatternReplacement(
        r"\bI (would )?suggest (that )?(you )?\b",
        ("Could try:", "One way:"),
    ),
    PatternReplacement(
        r"\bI (would )?recommend (that )?(you )?\b",
        ("", "One way:"),
    ),
    PatternReplacement(
        r"\bMy recommendation (is|would be) (to )?\b",
        ("Could:", "Try:"),
    ),

    # "It's important" variants
    PatternReplacement(
        r"\bIt('s| is) important (to |that )?\b",
        ("",),
    ),
    PatternReplacement(
        r"\bIt('s| is) essential (to |that )?\b",
        ("",),
    ),
    PatternReplacement(
        r"\bIt('s| is) crucial (to |that )?\b",
        ("",),
    ),

    # "Try to" → cleaner
    PatternReplacement(
        r"\bTry to\b",
        ("",),
    ),

    # "You can" → direct
    PatternReplacement(
        r"\bYou can\b",
        ("Can", ""),
    ),

    # "You will need to" → direct
    PatternReplacement(
        r"\bYou will need to\b",
        ("Need to", ""),
    ),

    # First person hedging
    PatternReplacement(
        r"\bI think (that )?\b",
        ("",),
    ),
    PatternReplacement(
        r"\bI believe (that )?\b",
        ("",),
    ),

], key=lambda p: p.pattern)


class LanguageTransformer:
    """
    Transforms instructional language into supportive language.

    Deterministic transformation:
    - Patterns applied in sorted order
    - Seed-based replacement selection
    - Same inputs → same outputs
    """

    def __init__(self, seed: int = ATMOSPHERE_SEED):
        """
        Initialize transformer.

        Args:
            seed: Seed for deterministic replacement selection
        """
        self.seed = seed
        self._pattern_cache: Dict[str, re.Pattern] = {}

    def transform(self, text: str) -> str:
        """
        Transform text by removing instructional patterns.

        Fixed order:
        1. Apply patterns in sorted order
        2. Use deterministic replacement selection
        3. Clean up whitespace

        Args:
            text: Input text to transform

        Returns:
            Transformed text
        """
        result = text

        # Apply patterns in sorted order (deterministic)
        for pattern_def in INSTRUCTIONAL_PATTERNS:
            result = self._apply_pattern(result, pattern_def)

        # Clean up whitespace
        result = self._cleanup(result)

        return result

    def _apply_pattern(self, text: str, pattern_def: PatternReplacement) -> str:
        """
        Apply a single pattern replacement.

        Deterministic replacement selection using hash.
        """
        # Get or compile regex
        if pattern_def.pattern not in self._pattern_cache:
            self._pattern_cache[pattern_def.pattern] = re.compile(
                pattern_def.pattern, pattern_def.flags
            )
        regex = self._pattern_cache[pattern_def.pattern]

        def replacer(match: re.Match) -> str:
            # Deterministic selection: hash of (seed, pattern, match position)
            selection_key = hash((self.seed, pattern_def.pattern, match.start()))
            replacement = pattern_def.replacements[selection_key % len(pattern_def.replacements)]

            # If removing entirely, just return empty
            if replacement == "":
                return ""

            # Add space after if replacement doesn't end with punctuation
            if replacement and not replacement.endswith((":", ".", "!", "?")):
                return replacement + " "
            return replacement + " "

        return regex.sub(replacer, text)

    def _cleanup(self, text: str) -> str:
        """Clean up whitespace artifacts from transformations."""
        # Multiple spaces → single space
        text = re.sub(r" {2,}", " ", text)
        # Space before punctuation
        text = re.sub(r" +([.,!?:;])", r"\1", text)
        # Multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Leading/trailing whitespace per line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        # Capitalize first letter after cleanup
        text = text.strip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]
        return text


def transform_language(text: str, seed: int = ATMOSPHERE_SEED) -> str:
    """
    Transform instructional language into supportive language.

    Convenience function for one-off transformation.

    Args:
        text: Input text
        seed: Seed for deterministic replacement selection

    Returns:
        Transformed text
    """
    transformer = LanguageTransformer(seed=seed)
    return transformer.transform(text)


__all__ = [
    "LanguageTransformer",
    "transform_language",
    "PatternReplacement",
    "INSTRUCTIONAL_PATTERNS",
    "ATMOSPHERE_SEED",
]
