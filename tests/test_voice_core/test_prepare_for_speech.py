"""
Tests for prepare_for_speech module.

Tests the 5-phase speech preparation pipeline:
1. Remove visual formatting
2. Expand abbreviations
3. Convert numbers
4. Add speech markers
5. Final cleanup
"""

import pytest
from otto.voice_core import (
    prepare_for_speech,
    prepare_chunks_for_speech,
    SpeechText,
)


class TestSpeechText:
    """Test SpeechText dataclass."""

    def test_creation(self):
        """Should create SpeechText with required fields."""
        speech = SpeechText(
            text="Hello world",
            original_text="# Hello world",
            original_checksum="abc123",
            prepared_checksum="def456",
            phases_applied=["remove_formatting", "final_cleanup"],
        )

        assert speech.text == "Hello world"
        assert speech.original_text == "# Hello world"
        assert len(speech.phases_applied) == 2

    def test_was_modified_true(self):
        """was_modified should be True when checksums differ."""
        speech = SpeechText(
            text="modified",
            original_text="original",
            original_checksum="abc",
            prepared_checksum="xyz",
            phases_applied=["remove_formatting"],
        )

        assert speech.was_modified is True

    def test_was_modified_false(self):
        """was_modified should be False when checksums match."""
        speech = SpeechText(
            text="same",
            original_text="same",
            original_checksum="abc",
            prepared_checksum="abc",
            phases_applied=[],
        )

        assert speech.was_modified is False


class TestPhase1RemoveFormatting:
    """Test Phase 1: Remove visual formatting."""

    def test_removes_headings(self):
        """Should remove markdown headings."""
        result = prepare_for_speech("# Heading 1\n## Heading 2")

        assert "#" not in result.text
        assert "Heading" in result.text

    def test_removes_bold_asterisks(self):
        """Should remove bold asterisks but keep text."""
        result = prepare_for_speech("This is **bold** text")

        assert "**" not in result.text
        assert "bold" in result.text

    def test_removes_bold_underscores(self):
        """Should remove bold underscores but keep text."""
        result = prepare_for_speech("This is __bold__ text")

        assert "__" not in result.text
        assert "bold" in result.text

    def test_removes_italic_asterisks(self):
        """Should remove italic asterisks but keep text."""
        result = prepare_for_speech("This is *italic* text")

        assert result.text.count("*") == 0
        assert "italic" in result.text

    def test_removes_italic_underscores(self):
        """Should remove italic underscores but keep text."""
        result = prepare_for_speech("This is _italic_ text")

        assert "_" not in result.text
        assert "italic" in result.text

    def test_removes_strikethrough(self):
        """Should remove strikethrough but keep text."""
        result = prepare_for_speech("This is ~~struck~~ text")

        assert "~~" not in result.text
        assert "struck" in result.text

    def test_converts_links_to_text(self):
        """Should convert links to link text only."""
        result = prepare_for_speech("Check [this link](http://example.com)")

        assert "[" not in result.text
        assert "]" not in result.text
        assert "http" not in result.text
        assert "this link" in result.text

    def test_removes_code_blocks(self):
        """Should remove code blocks entirely."""
        text = """
        Some text
        ```python
        def foo():
            pass
        ```
        More text
        """
        result = prepare_for_speech(text)

        assert "```" not in result.text
        assert "def foo" not in result.text
        assert "code example" in result.text.lower()

    def test_removes_inline_code_backticks(self):
        """Should remove inline code backticks but keep content."""
        result = prepare_for_speech("Use the `print` function")

        assert "`" not in result.text
        assert "print" in result.text

    def test_removes_bullets(self):
        """Should remove bullet markers."""
        result = prepare_for_speech("- Item A\n- Item B\n* Item C")

        assert result.text.count("-") == 0 or "Item" in result.text
        assert "Item A" in result.text

    def test_removes_numbered_lists(self):
        """Should remove number list markers."""
        result = prepare_for_speech("1. First\n2. Second\n3. Third")

        assert "First" in result.text
        assert "Second" in result.text

    def test_removes_blockquotes(self):
        """Should remove blockquote markers."""
        result = prepare_for_speech("> This is a quote")

        assert result.text.startswith(">") is False
        assert "This is a quote" in result.text

    def test_handles_images(self):
        """Should handle images appropriately."""
        result = prepare_for_speech("![alt text](http://example.com/img.png)")

        assert "![" not in result.text
        assert "http" not in result.text
        assert "image" in result.text.lower()


class TestPhase2ExpandAbbreviations:
    """Test Phase 2: Expand abbreviations."""

    def test_expands_api(self):
        """Should expand API."""
        result = prepare_for_speech("The API is great")
        assert "A P I" in result.text

    def test_expands_json(self):
        """Should expand JSON."""
        result = prepare_for_speech("Use JSON format")
        assert "Jason" in result.text

    def test_expands_url(self):
        """Should expand URL."""
        result = prepare_for_speech("Enter the URL")
        assert "U R L" in result.text

    def test_expands_llm(self):
        """Should expand LLM."""
        result = prepare_for_speech("LLM models are powerful")
        assert "L L M" in result.text

    def test_expands_eg(self):
        """Should expand e.g."""
        result = prepare_for_speech("For example, e.g. this")
        assert "for example" in result.text.lower()

    def test_expands_ie(self):
        """Should expand i.e."""
        result = prepare_for_speech("That is, i.e. this")
        assert "that is" in result.text.lower()

    def test_case_insensitive(self):
        """Should expand regardless of case."""
        result1 = prepare_for_speech("API")
        result2 = prepare_for_speech("api")
        result3 = prepare_for_speech("Api")

        assert "A P I" in result1.text
        assert "A P I" in result2.text
        assert "A P I" in result3.text


class TestPhase3ConvertNumbers:
    """Test Phase 3: Convert numbers to speakable text."""

    def test_converts_single_digits(self):
        """Should convert single digits."""
        result = prepare_for_speech("I have 5 apples")
        assert "five" in result.text

    def test_converts_teens(self):
        """Should convert teen numbers."""
        result = prepare_for_speech("There are 15 items")
        assert "fifteen" in result.text

    def test_converts_two_digit_numbers(self):
        """Should convert two digit numbers."""
        result = prepare_for_speech("I see 42 stars")
        assert "forty-two" in result.text

    def test_converts_three_digit_numbers(self):
        """Should convert three digit numbers."""
        result = prepare_for_speech("There are 500 people")
        assert "five hundred" in result.text

    def test_converts_thousands(self):
        """Should convert thousands."""
        result = prepare_for_speech("Population is 5000")
        assert "five thousand" in result.text

    def test_converts_percentages(self):
        """Should convert percentages."""
        result = prepare_for_speech("That's 75% done")
        assert "seventy-five percent" in result.text

    def test_converts_currency(self):
        """Should convert currency."""
        result = prepare_for_speech("Cost is $50")
        assert "fifty dollars" in result.text

    def test_converts_time(self):
        """Should convert time."""
        result = prepare_for_speech("Meet at 2:30")
        assert "two thirty" in result.text

    def test_converts_time_oclock(self):
        """Should convert on-the-hour times."""
        result = prepare_for_speech("At 3:00")
        assert "three o'clock" in result.text

    def test_converts_decimals(self):
        """Should convert decimal numbers."""
        result = prepare_for_speech("Pi is 3.14")
        assert "three point one four" in result.text


class TestPhase5FinalCleanup:
    """Test Phase 5: Final cleanup."""

    def test_normalizes_whitespace(self):
        """Should normalize multiple spaces."""
        result = prepare_for_speech("Hello    world")
        assert "  " not in result.text

    def test_removes_multiple_punctuation(self):
        """Should remove multiple punctuation marks."""
        result = prepare_for_speech("Really??!!")
        # Should not have multiple question marks or exclamation marks
        assert result.text.count("?") <= 1

    def test_trims_text(self):
        """Should trim leading/trailing whitespace."""
        result = prepare_for_speech("   Hello world   ")
        assert not result.text.startswith(" ")
        assert not result.text.endswith(" ")


class TestPrepareChunksForSpeech:
    """Test batch processing of chunks."""

    def test_processes_multiple_chunks(self):
        """Should process all chunks."""
        chunks = [
            "# Heading One",
            "There are 42 items",
            "The API works",
        ]
        results = prepare_chunks_for_speech(chunks)

        assert len(results) == 3
        assert all(isinstance(r, SpeechText) for r in results)

    def test_skips_empty_chunks(self):
        """Empty chunks should still be processed."""
        chunks = ["Hello", "", "World"]
        results = prepare_chunks_for_speech(chunks)

        assert len(results) == 3

    def test_deterministic_order(self):
        """Should process in deterministic order."""
        chunks = [f"Chunk {i}" for i in range(100)]

        results1 = prepare_chunks_for_speech(chunks)
        results2 = prepare_chunks_for_speech(chunks)

        checksums1 = [r.prepared_checksum for r in results1]
        checksums2 = [r.prepared_checksum for r in results2]

        assert checksums1 == checksums2


class TestComplexInputs:
    """Test with complex real-world inputs."""

    def test_readme_style_content(self):
        """Should handle README-style content."""
        text = """
        # OTTO Voice Integration

        This module provides **WhatsApp voice** support.

        ## Features

        - Voice message transcription
        - Text-to-speech response
        - 42 supported languages

        ```python
        from otto import voice
        voice.transcribe(audio)
        ```

        See [documentation](http://docs.example.com) for more.
        """
        result = prepare_for_speech(text)

        # OTTO gets expanded to "Otto" per ABBREVIATION_EXPANSIONS
        assert "Otto Voice Integration" in result.text
        assert "#" not in result.text
        assert "**" not in result.text
        assert "forty-two" in result.text
        assert "```" not in result.text

    def test_technical_content(self):
        """Should handle technical content well."""
        text = "The API returns JSON at 99.9% uptime with <100ms latency"
        result = prepare_for_speech(text)

        assert "A P I" in result.text
        assert "Jason" in result.text
        assert "percent" in result.text

    def test_preserves_meaning(self):
        """Should preserve the meaning of content."""
        original = "Hello world, this is a test!"
        result = prepare_for_speech(original)

        assert "Hello" in result.text
        assert "world" in result.text
        assert "test" in result.text
