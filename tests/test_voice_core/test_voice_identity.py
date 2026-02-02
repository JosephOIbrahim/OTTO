"""
Tests for voice_identity module.

Tests voice character enforcement functions:
- remove_forbidden_phrases()
- limit_for_speech()
- should_respond_with_voice()
- prepare_text_for_voice()
"""

import pytest
from otto.voice_core import (
    VoiceIdentity,
    VoiceTone,
    SpeakingStyle,
    DEFAULT_IDENTITY,
    adjust_for_context,
    voice_for_emotion,
    FORBIDDEN_SPOKEN_PHRASES,
    MAX_SPOKEN_WORDS,
    MAX_SPOKEN_SENTENCES,
    VOICE_RESPONSE_MAX_LENGTH,
    remove_forbidden_phrases,
    limit_for_speech,
    should_respond_with_voice,
    prepare_text_for_voice,
)
from otto.voice_core.tts import TTSVoice


class TestVoiceIdentityBasic:
    """Tests for VoiceIdentity dataclass."""

    def test_default_identity_exists(self):
        """DEFAULT_IDENTITY should be pre-configured."""
        assert DEFAULT_IDENTITY is not None
        assert DEFAULT_IDENTITY.name == "OTTO"
        assert DEFAULT_IDENTITY.tone == VoiceTone.FRIENDLY
        assert DEFAULT_IDENTITY.style == SpeakingStyle.CONVERSATIONAL

    def test_greeting_by_tone(self):
        """Greetings should vary by tone."""
        identity = VoiceIdentity(tone=VoiceTone.FRIENDLY)
        assert "Hey there" in identity.get_greeting()

        identity = VoiceIdentity(tone=VoiceTone.PROFESSIONAL)
        assert "Hello" in identity.get_greeting()

    def test_farewell_by_tone(self):
        """Farewells should vary by tone."""
        identity = VoiceIdentity(tone=VoiceTone.CALM)
        assert "care" in identity.get_farewell().lower()

    def test_acknowledgment_by_tone(self):
        """Acknowledgments should vary by tone."""
        identity = VoiceIdentity(tone=VoiceTone.ENERGETIC)
        assert "Awesome" in identity.get_acknowledgment()


class TestAdjustForContext:
    """Tests for adjust_for_context function."""

    def test_error_context_slows_speech(self):
        """Error context should slow speech for clarity."""
        adjusted = adjust_for_context(DEFAULT_IDENTITY, "error")
        assert adjusted.speed < DEFAULT_IDENTITY.speed
        assert adjusted.tone == VoiceTone.CALM

    def test_success_context_speeds_up(self):
        """Success context should be upbeat."""
        adjusted = adjust_for_context(DEFAULT_IDENTITY, "success")
        assert adjusted.speed > DEFAULT_IDENTITY.speed
        assert adjusted.tone == VoiceTone.ENERGETIC

    def test_unknown_context_returns_unchanged(self):
        """Unknown context should return original identity."""
        adjusted = adjust_for_context(DEFAULT_IDENTITY, "unknown_context")
        assert adjusted.speed == DEFAULT_IDENTITY.speed
        assert adjusted.tone == DEFAULT_IDENTITY.tone


class TestVoiceForEmotion:
    """Tests for voice_for_emotion function."""

    def test_happy_returns_nova(self):
        """Happy emotion should use NOVA voice."""
        assert voice_for_emotion("happy") == TTSVoice.NOVA

    def test_sad_returns_shimmer(self):
        """Sad emotion should use SHIMMER voice."""
        assert voice_for_emotion("sad") == TTSVoice.SHIMMER

    def test_case_insensitive(self):
        """Emotion lookup should be case-insensitive."""
        assert voice_for_emotion("HAPPY") == TTSVoice.NOVA
        assert voice_for_emotion("Happy") == TTSVoice.NOVA

    def test_unknown_returns_default(self):
        """Unknown emotion should return NOVA (default)."""
        assert voice_for_emotion("unknown") == TTSVoice.NOVA


class TestForbiddenPhrases:
    """Tests for remove_forbidden_phrases function."""

    def test_removes_clinical_phrases(self):
        """Should remove clinical/robotic phrases."""
        text = "Here's the answer. Does that make sense?"
        result = remove_forbidden_phrases(text)
        assert "Does that make sense?" not in result
        assert "Here's the answer." in result

    def test_removes_ai_self_references(self):
        """Should remove AI self-references."""
        text = "As an AI, I cannot provide medical advice."
        result = remove_forbidden_phrases(text)
        assert "As an AI" not in result
        assert "I cannot" not in result

    def test_removes_multiple_phrases(self):
        """Should remove multiple forbidden phrases from same text."""
        text = "I hope this helps! Let me know if you have questions. Feel free to ask."
        result = remove_forbidden_phrases(text)
        assert "I hope this helps" not in result
        assert "Let me know if you have questions" not in result
        assert "Feel free to ask" not in result

    def test_case_insensitive_removal(self):
        """Should remove phrases case-insensitively."""
        text = "AS AN AI, I'm here to help."
        result = remove_forbidden_phrases(text)
        assert "AS AN AI" not in result.upper()
        assert "I'm here to help" not in result

    def test_cleans_whitespace(self):
        """Should clean up resulting whitespace."""
        text = "Here.   Does that make sense?   There."
        result = remove_forbidden_phrases(text)
        assert "   " not in result  # No triple spaces

    def test_preserves_non_forbidden_text(self):
        """Should preserve text that isn't forbidden."""
        text = "Pick the smallest task and do that first."
        result = remove_forbidden_phrases(text)
        assert result == text

    def test_all_forbidden_phrases_removed(self):
        """All phrases in FORBIDDEN_SPOKEN_PHRASES should be removed."""
        for phrase in FORBIDDEN_SPOKEN_PHRASES:
            text = f"Start {phrase} End"
            result = remove_forbidden_phrases(text)
            assert phrase.lower() not in result.lower()


class TestLimitForSpeech:
    """Tests for limit_for_speech function."""

    def test_limits_word_count(self):
        """Should limit text to MAX_SPOKEN_WORDS."""
        # Create text with 100 words
        text = " ".join(["word"] * 100)
        result = limit_for_speech(text)
        words = result.split()
        assert len(words) <= MAX_SPOKEN_WORDS + 1  # +1 for ellipsis word

    def test_limits_sentence_count(self):
        """Should limit text to MAX_SPOKEN_SENTENCES."""
        text = "First. Second. Third. Fourth. Fifth. Sixth."
        result = limit_for_speech(text)
        # Count sentence-ending punctuation
        sentence_count = result.count(".") + result.count("!") + result.count("?")
        assert sentence_count <= MAX_SPOKEN_SENTENCES + 1  # Allow for ellipsis

    def test_adds_ellipsis_when_truncated(self):
        """Should add ellipsis when truncated mid-sentence."""
        text = " ".join(["word"] * 100)  # No sentence endings
        result = limit_for_speech(text)
        assert result.endswith("...")

    def test_preserves_short_text(self):
        """Should not modify text under limits."""
        text = "This is short."
        result = limit_for_speech(text)
        assert result == text

    def test_custom_limits(self):
        """Should respect custom max_words and max_sentences."""
        text = "One. Two. Three."
        result = limit_for_speech(text, max_words=100, max_sentences=2)
        assert "Three" not in result


class TestShouldRespondWithVoice:
    """Tests for should_respond_with_voice function."""

    def test_user_preference_voice_wins(self):
        """User preference 'voice' should always return True."""
        assert should_respond_with_voice(
            user_sent_voice=False,
            user_preference="voice",
            response_length=1000
        ) is True

    def test_user_preference_text_wins(self):
        """User preference 'text' should always return False."""
        assert should_respond_with_voice(
            user_sent_voice=True,
            user_preference="text",
            response_length=100
        ) is False

    def test_mirrors_voice_input(self):
        """Should mirror voice input with voice output."""
        assert should_respond_with_voice(
            user_sent_voice=True,
            user_preference=None,
            response_length=100
        ) is True

    def test_text_input_returns_text(self):
        """Text input should return text output in auto mode."""
        assert should_respond_with_voice(
            user_sent_voice=False,
            user_preference=None,
            response_length=100
        ) is False

    def test_long_response_uses_text(self):
        """Long responses should use text even for voice input."""
        assert should_respond_with_voice(
            user_sent_voice=True,
            user_preference=None,
            response_length=VOICE_RESPONSE_MAX_LENGTH + 100
        ) is False

    def test_exact_threshold_uses_voice(self):
        """Response at exact threshold should still use voice."""
        assert should_respond_with_voice(
            user_sent_voice=True,
            user_preference=None,
            response_length=VOICE_RESPONSE_MAX_LENGTH
        ) is True


class TestPrepareTextForVoice:
    """Tests for prepare_text_for_voice function."""

    def test_combines_forbidden_and_limit(self):
        """Should remove forbidden phrases AND limit length."""
        # Long text with forbidden phrase
        words = ["word"] * 100
        text = " ".join(words) + " Does that make sense?"
        result = prepare_text_for_voice(text)

        # Should not have forbidden phrase
        assert "Does that make sense?" not in result
        # Should be limited in length
        assert len(result.split()) <= MAX_SPOKEN_WORDS + 1

    def test_order_of_operations(self):
        """Should remove forbidden phrases before limiting."""
        # Text where forbidden phrase is in the first 60 words
        text = "Does that make sense? " + " ".join(["word"] * 50)
        result = prepare_text_for_voice(text)
        assert "Does that make sense?" not in result


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_remove_forbidden_is_deterministic(self):
        """remove_forbidden_phrases should produce same output."""
        text = "I hope this helps! As an AI, I understand."
        results = [remove_forbidden_phrases(text) for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_limit_for_speech_is_deterministic(self):
        """limit_for_speech should produce same output."""
        text = " ".join(["word"] * 100)
        results = [limit_for_speech(text) for _ in range(100)]
        assert all(r == results[0] for r in results)

    def test_should_respond_is_deterministic(self):
        """should_respond_with_voice should produce same output."""
        results = [
            should_respond_with_voice(True, None, 300)
            for _ in range(100)
        ]
        assert all(r == results[0] for r in results)
