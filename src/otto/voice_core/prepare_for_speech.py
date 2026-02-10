"""
Prepare text for speech synthesis.

Implements a fixed 5-phase pipeline per Determinism:
1. Remove visual formatting (markdown, code blocks)
2. Expand abbreviations deterministically
3. Convert numbers to speakable text
4. Add speech markers (pauses, emphasis)
5. Final cleanup

Each phase is deterministic and order-independent for batch invariance.
"""

import re
from dataclasses import dataclass
from typing import Optional

from .determinism import (
    ABBREVIATION_EXPANSIONS,
    NUMBER_WORDS,
    TENS_WORDS,
    COGNITIVE_TILE_SIZE,
    compute_checksum,
    batch_invariant_process,
)


@dataclass
class SpeechText:
    """Text prepared for speech synthesis."""

    text: str
    """Speech-ready text."""

    original_text: str
    """Original input text."""

    original_checksum: str
    """Checksum of original text."""

    prepared_checksum: str
    """Checksum of prepared text."""

    phases_applied: list[str]
    """List of phases that modified the text."""

    @property
    def was_modified(self) -> bool:
        """Return True if text was modified."""
        return self.original_checksum != self.prepared_checksum


# === Phase 1: Remove Visual Formatting ===

# Patterns for visual elements (compiled once for performance)
_PATTERNS = {
    "code_block": re.compile(r"```[\s\S]*?```", re.MULTILINE),
    "inline_code": re.compile(r"`[^`]+`"),
    "heading": re.compile(r"^\s*#{1,6}\s*", re.MULTILINE),
    "bold_asterisk": re.compile(r"\*\*([^*]+)\*\*"),
    "bold_underscore": re.compile(r"__([^_]+)__"),
    "italic_asterisk": re.compile(r"\*([^*]+)\*"),
    "italic_underscore": re.compile(r"_([^_]+)_"),
    "strikethrough": re.compile(r"~~([^~]+)~~"),
    "link": re.compile(r"\[([^\]]+)\]\([^)]+\)"),
    "image": re.compile(r"!\[([^\]]*)\]\([^)]+\)"),
    "bullet": re.compile(r"^\s*[-*+]\s+", re.MULTILINE),
    "numbered": re.compile(r"^\s*\d+\.\s+", re.MULTILINE),
    "blockquote": re.compile(r"^\s*>\s*", re.MULTILINE),
    "horizontal_rule": re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE),
    "table_separator": re.compile(r"\|[-:]+\|", re.MULTILINE),
    "table_cell": re.compile(r"\|"),
}


def _phase1_remove_formatting(text: str) -> str:
    """
    Phase 1: Remove visual formatting.

    Operations (FIXED order):
    1. Remove code blocks (with content)
    2. Remove inline code backticks (keep content)
    3. Remove heading markers
    4. Convert bold/italic to plain text
    5. Convert links to link text only
    6. Remove images (describe as "image")
    7. Remove bullets and numbering
    8. Remove blockquotes
    9. Remove horizontal rules
    10. Clean up tables
    """
    # 1. Code blocks - replace with "[code example]"
    text = _PATTERNS["code_block"].sub(" [code example] ", text)

    # 2. Inline code - keep content, remove backticks
    text = _PATTERNS["inline_code"].sub(lambda m: m.group(0)[1:-1], text)

    # 3. Headings - remove markers
    text = _PATTERNS["heading"].sub("", text)

    # 4. Bold/italic - keep text
    text = _PATTERNS["bold_asterisk"].sub(r"\1", text)
    text = _PATTERNS["bold_underscore"].sub(r"\1", text)
    text = _PATTERNS["italic_asterisk"].sub(r"\1", text)
    text = _PATTERNS["italic_underscore"].sub(r"\1", text)
    text = _PATTERNS["strikethrough"].sub(r"\1", text)

    # 5. Images - replace with description (MUST run before links)
    text = _PATTERNS["image"].sub(r"image: \1", text)

    # 6. Links - keep link text
    text = _PATTERNS["link"].sub(r"\1", text)

    # 7. Bullets and numbering
    text = _PATTERNS["bullet"].sub("", text)
    text = _PATTERNS["numbered"].sub("", text)

    # 8. Blockquotes
    text = _PATTERNS["blockquote"].sub("", text)

    # 9. Horizontal rules
    text = _PATTERNS["horizontal_rule"].sub(" ", text)

    # 10. Tables
    text = _PATTERNS["table_separator"].sub("", text)
    text = _PATTERNS["table_cell"].sub(" ", text)

    return text


# === Phase 2: Expand Abbreviations ===

def _phase2_expand_abbreviations(text: str) -> str:
    """
    Phase 2: Expand abbreviations deterministically.

    Uses ABBREVIATION_EXPANSIONS dict with sorted iteration
    for reproducible results.
    """
    # Sort keys for deterministic order
    for abbrev in sorted(ABBREVIATION_EXPANSIONS.keys()):
        expansion = ABBREVIATION_EXPANSIONS[abbrev]
        # Word boundary matching to avoid partial replacements
        pattern = r"\b" + re.escape(abbrev) + r"\b"
        text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)

    return text


# === Phase 3: Convert Numbers ===

def _number_to_words(n: int) -> str:
    """Convert integer to spoken words."""
    if n < 0:
        return "negative " + _number_to_words(-n)

    if n <= 20:
        return NUMBER_WORDS.get(n, str(n))

    if n < 100:
        tens, ones = divmod(n, 10)
        if ones == 0:
            return TENS_WORDS[tens]
        return f"{TENS_WORDS[tens]}-{NUMBER_WORDS[ones]}"

    if n < 1000:
        hundreds, remainder = divmod(n, 100)
        if remainder == 0:
            return f"{NUMBER_WORDS[hundreds]} hundred"
        return f"{NUMBER_WORDS[hundreds]} hundred {_number_to_words(remainder)}"

    if n < 1_000_000:
        thousands, remainder = divmod(n, 1000)
        if remainder == 0:
            return f"{_number_to_words(thousands)} thousand"
        return f"{_number_to_words(thousands)} thousand {_number_to_words(remainder)}"

    if n < 1_000_000_000:
        millions, remainder = divmod(n, 1_000_000)
        if remainder == 0:
            return f"{_number_to_words(millions)} million"
        return f"{_number_to_words(millions)} million {_number_to_words(remainder)}"

    # Fall back to digits for very large numbers
    return str(n)


def _decimal_to_words(text: str) -> str:
    """Convert decimal number string to spoken words."""
    if "." not in text:
        try:
            return _number_to_words(int(text))
        except ValueError:
            return text

    parts = text.split(".")
    if len(parts) != 2:
        return text

    try:
        integer_part = _number_to_words(int(parts[0]))
        # Read decimal digits individually
        decimal_digits = " ".join(NUMBER_WORDS.get(int(d), d) for d in parts[1])
        return f"{integer_part} point {decimal_digits}"
    except ValueError:
        return text


def _phase3_convert_numbers(text: str) -> str:
    """
    Phase 3: Convert numbers to speakable text.

    Handles:
    - Integers (42 -> "forty-two")
    - Decimals (3.14 -> "three point one four")
    - Percentages (50% -> "fifty percent")
    - Currency ($100 -> "one hundred dollars")
    - Times (3:30 -> "three thirty")
    """
    # Percentages
    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*%",
        lambda m: _decimal_to_words(m.group(1)) + " percent",
        text
    )

    # Currency (USD)
    text = re.sub(
        r"\$(\d+(?:\.\d{2})?)",
        lambda m: _decimal_to_words(m.group(1)) + " dollars",
        text
    )

    # Times (HH:MM)
    def time_to_words(m):
        hour, minute = int(m.group(1)), int(m.group(2))
        if minute == 0:
            return _number_to_words(hour) + " o'clock"
        return f"{_number_to_words(hour)} {_number_to_words(minute)}"

    text = re.sub(r"\b(\d{1,2}):(\d{2})\b", time_to_words, text)

    # Standalone numbers (not part of other patterns)
    text = re.sub(
        r"\b(\d+(?:\.\d+)?)\b",
        lambda m: _decimal_to_words(m.group(1)),
        text
    )

    return text


# === Phase 4: Add Speech Markers ===

def _phase4_add_speech_markers(text: str) -> str:
    """
    Phase 4: Add speech markers for natural prosody.

    Adds:
    - Pauses after sentences
    - Emphasis markers (not implemented by all TTS)
    - Natural breathing points
    """
    # Ensure sentence endings have proper pause
    text = re.sub(r"([.!?])\s+", r"\1 ", text)

    # Add pause after colons (list introductions)
    text = re.sub(r":\s+", ": ", text)

    # Add pause after commas in long sentences
    text = re.sub(r",\s+", ", ", text)

    # Ensure ellipsis creates pause
    text = re.sub(r"\.{3,}", "...", text)

    return text


# === Phase 5: Final Cleanup ===

def _phase5_final_cleanup(text: str) -> str:
    """
    Phase 5: Final cleanup for speech synthesis.

    Operations:
    - Normalize whitespace
    - Remove extra punctuation
    - Trim text
    """
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove multiple punctuation
    text = re.sub(r"([.!?]){2,}", r"\1", text)

    # Remove orphaned punctuation
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)

    # Trim
    text = text.strip()

    return text


# === Main Pipeline ===

def prepare_for_speech(
    text: str,
    skip_phases: Optional[list[int]] = None,
) -> SpeechText:
    """
    Prepare text for speech synthesis using 5-phase pipeline.

    Fixed phase order, deterministic operations,
    no dynamic algorithm switching.

    Args:
        text: Input text to prepare
        skip_phases: Optional list of phase numbers to skip (1-5)

    Returns:
        SpeechText with prepared text and metadata
    """
    skip_phases = skip_phases or []
    original_checksum = compute_checksum(text)
    phases_applied = []

    # Phase 1: Remove visual formatting
    if 1 not in skip_phases:
        text = _phase1_remove_formatting(text)
        phases_applied.append("remove_formatting")

    # Phase 2: Expand abbreviations
    if 2 not in skip_phases:
        text = _phase2_expand_abbreviations(text)
        phases_applied.append("expand_abbreviations")

    # Phase 3: Convert numbers
    if 3 not in skip_phases:
        text = _phase3_convert_numbers(text)
        phases_applied.append("convert_numbers")

    # Phase 4: Add speech markers
    if 4 not in skip_phases:
        text = _phase4_add_speech_markers(text)
        phases_applied.append("add_speech_markers")

    # Phase 5: Final cleanup
    if 5 not in skip_phases:
        text = _phase5_final_cleanup(text)
        phases_applied.append("final_cleanup")

    return SpeechText(
        text=text,
        original_text=text if not phases_applied else "",  # Only store if unchanged
        original_checksum=original_checksum,
        prepared_checksum=compute_checksum(text),
        phases_applied=phases_applied,
    )


def prepare_chunks_for_speech(
    chunks: list[str],
    tile_size: int = COGNITIVE_TILE_SIZE,
) -> list[SpeechText]:
    """
    Prepare multiple text chunks for speech.

    Uses batch-invariant processing.

    Args:
        chunks: List of text chunks
        tile_size: Fixed tile size for processing

    Returns:
        List of SpeechText results
    """
    return batch_invariant_process(
        chunks,
        prepare_for_speech,
        tile_size,
    )
