"""
Golden tests for real-world OTTO voice scenarios.

These tests validate that OTTO's voice responses maintain
the "calm friend on the phone" character across common use cases.

Per spec: OTTO sounds like a calm friend on the phone—someone who's been there.
NOT like Siri (corporate), Alexa (assistant-y), or a therapist (clinical).
"""

import pytest
from otto.voice_core import (
    remove_forbidden_phrases,
    limit_for_speech,
    should_respond_with_voice,
    prepare_text_for_voice,
    prepare_for_speech,
    FORBIDDEN_SPOKEN_PHRASES,
    MAX_SPOKEN_WORDS,
    MAX_SPOKEN_SENTENCES,
    VOICE_RESPONSE_MAX_LENGTH,
)


class TestBrainDumpScenario:
    """
    Scenario: User sends 45-second rambling voice message about being overwhelmed.

    Expected: Voice response, under 30 seconds, warm tone, one clear action.
    """

    # Simulated brain dump transcription
    BRAIN_DUMP_INPUT = """
    So like I've been meaning to do this thing for work but then I got distracted
    by my email and there were like fifteen things in there and then I started
    on one of those but then remembered the laundry and now it's been three hours
    and I haven't done the original thing and I feel terrible about it and I don't
    even know where to start anymore because everything feels like it needs to
    happen at once and I just can't seem to focus on any single thing.
    """

    # Good OTTO response (matches voice character)
    GOOD_RESPONSE = """
    Yeah, that spiral is rough. Here's the one thing: pick the smallest piece,
    like 10 minutes of work on the original task. Do just that. If you want to
    stop after, stop. That's enough.
    """

    # Bad response (clinical, therapist-like)
    BAD_RESPONSE = """
    I understand you're feeling overwhelmed. It's common to experience distraction
    cycles when dealing with multiple tasks. Here are some strategies you might
    consider: First, try the Pomodoro technique. Second, prioritize your tasks.
    Third, eliminate distractions. Does that make sense? Let me know if you have
    any questions. I hope this helps!
    """

    def test_good_response_passes_voice_check(self):
        """Good response should be suitable for voice."""
        prepared = prepare_text_for_voice(self.GOOD_RESPONSE)
        # Should not be significantly altered
        assert "smallest piece" in prepared
        assert "10 minutes" in prepared or "ten minutes" in prepared.lower()

    def test_good_response_under_word_limit(self):
        """Good response should be under 60 words."""
        prepared = prepare_text_for_voice(self.GOOD_RESPONSE)
        word_count = len(prepared.split())
        assert word_count <= MAX_SPOKEN_WORDS

    def test_bad_response_has_forbidden_phrases(self):
        """Bad response should contain forbidden phrases that get removed."""
        # Verify it has phrases that will be removed
        assert any(
            phrase.lower() in self.BAD_RESPONSE.lower()
            for phrase in FORBIDDEN_SPOKEN_PHRASES
        )

    def test_bad_response_cleaned_up(self):
        """Bad response should have forbidden phrases removed."""
        prepared = remove_forbidden_phrases(self.BAD_RESPONSE)
        assert "Does that make sense?" not in prepared
        assert "I hope this helps" not in prepared
        assert "I understand you're feeling" not in prepared

    def test_should_respond_with_voice_for_voice_input(self):
        """Should respond with voice to voice input."""
        assert should_respond_with_voice(
            user_sent_voice=True,
            response_length=len(self.GOOD_RESPONSE)
        ) is True


class TestTeenScenario:
    """
    Scenario: Teen user sends casual voice message.

    Expected: Casual, non-preachy response that matches their energy.
    """

    TEEN_INPUT = "yo can you remind me to text my friend later about the thing"

    # Good OTTO response (casual, matches energy)
    GOOD_RESPONSE = "Got it! I'll remind you about texting your friend."

    # Bad response (preachy, over-explaining)
    BAD_RESPONSE = """
    I'd be happy to help you with that reminder! As your AI assistant, I'm here
    to help you stay organized. I'll set a reminder for you to text your friend.
    Don't hesitate to ask if you need anything else. Is there anything else I
    can help you with today?
    """

    def test_good_response_stays_casual(self):
        """Good casual response should not be altered."""
        prepared = prepare_text_for_voice(self.GOOD_RESPONSE)
        assert "Got it" in prepared
        assert len(prepared.split()) < 20  # Short and sweet

    def test_bad_response_loses_ai_language(self):
        """Bad response should have AI language removed."""
        prepared = remove_forbidden_phrases(self.BAD_RESPONSE)
        assert "As your AI assistant" not in prepared
        assert "I'm here to help" not in prepared
        assert "Don't hesitate to" not in prepared

    def test_bad_response_gets_shorter(self):
        """Bad response should be significantly shorter after cleaning."""
        original_words = len(self.BAD_RESPONSE.split())
        prepared = prepare_text_for_voice(self.BAD_RESPONSE)
        prepared_words = len(prepared.split())
        # Should be much shorter due to forbidden phrases removal + limiting
        assert prepared_words < original_words


class TestDepletedUserScenario:
    """
    Scenario: User sounds depleted, low energy.

    Expected: Gentle, short response with permission to rest.
    """

    DEPLETED_INPUT = "i don't know... i just can't today"

    # Good OTTO response (gentle, permissive)
    GOOD_RESPONSE = """
    That's okay. Sometimes the best thing is to stop trying for a bit.
    Rest if you need to.
    """

    # Bad response (pushy, solution-focused)
    BAD_RESPONSE = """
    I understand you're feeling stuck. Let me help you get back on track!
    Here are some quick wins you could try: First, just open the document.
    Second, write one sentence. Third, take a short break. You've got this!
    Feel free to ask if you need more suggestions. I'm here to help!
    """

    def test_good_response_stays_gentle(self):
        """Good gentle response should not be altered."""
        prepared = prepare_text_for_voice(self.GOOD_RESPONSE)
        assert "okay" in prepared.lower()
        assert "rest" in prepared.lower()

    def test_good_response_is_short(self):
        """Good response should be very short for depleted user."""
        prepared = prepare_text_for_voice(self.GOOD_RESPONSE)
        word_count = len(prepared.split())
        assert word_count < 30  # Extra short for depleted user

    def test_bad_response_cleaned_of_pushiness(self):
        """Bad response should lose pushy phrases."""
        prepared = remove_forbidden_phrases(self.BAD_RESPONSE)
        assert "I'm here to help" not in prepared
        assert "Feel free to ask" not in prepared
        assert "I understand you're feeling" not in prepared


class TestLongResponseScenario:
    """
    Scenario: OTTO generates a long informational response.

    Expected: Falls back to text instead of voice.
    """

    LONG_RESPONSE = " ".join(["explanation"] * 200)  # 200 words

    def test_long_response_uses_text(self):
        """Long responses should fall back to text."""
        assert should_respond_with_voice(
            user_sent_voice=True,
            response_length=len(self.LONG_RESPONSE)
        ) is False

    def test_voice_response_would_be_truncated(self):
        """If forced to voice, would be heavily truncated."""
        prepared = prepare_text_for_voice(self.LONG_RESPONSE)
        word_count = len(prepared.split())
        assert word_count <= MAX_SPOKEN_WORDS + 1  # +1 for ellipsis


class TestVoiceCharacterConsistency:
    """
    Tests that ensure OTTO's voice character is maintained.

    OTTO should sound like a calm friend, not a corporate assistant or therapist.
    """

    def test_forbidden_phrases_are_removed(self):
        """All FORBIDDEN_SPOKEN_PHRASES should be removed."""
        for phrase in FORBIDDEN_SPOKEN_PHRASES:
            text = f"Here's the answer. {phrase} That's it."
            prepared = remove_forbidden_phrases(text)
            assert phrase.lower() not in prepared.lower(), f"'{phrase}' was not removed"

    def test_no_therapist_speak(self):
        """Therapist-like phrases in forbidden list should be removed."""
        therapist_forbidden = [
            p for p in FORBIDDEN_SPOKEN_PHRASES
            if "understand" in p.lower() or "feeling" in p.lower()
        ]
        for phrase in therapist_forbidden:
            text = f"{phrase} Anyway, here's what to do."
            prepared = remove_forbidden_phrases(text)
            assert phrase.lower() not in prepared.lower()


class TestDeterministicGoldenOutputs:
    """
    Tests that golden scenarios produce deterministic outputs.

    Per [He2025]: Same input must produce same output across runs.
    """

    SCENARIOS = [
        TestBrainDumpScenario.GOOD_RESPONSE,
        TestBrainDumpScenario.BAD_RESPONSE,
        TestTeenScenario.GOOD_RESPONSE,
        TestTeenScenario.BAD_RESPONSE,
        TestDepletedUserScenario.GOOD_RESPONSE,
        TestDepletedUserScenario.BAD_RESPONSE,
    ]

    def test_prepare_text_is_deterministic(self):
        """prepare_text_for_voice should be deterministic for all scenarios."""
        for scenario in self.SCENARIOS:
            results = [prepare_text_for_voice(scenario) for _ in range(100)]
            assert all(r == results[0] for r in results), f"Non-deterministic: {scenario[:50]}..."

    def test_full_pipeline_is_deterministic(self):
        """Full speech preparation pipeline should be deterministic."""
        for scenario in self.SCENARIOS:
            # First prepare for voice character
            text = prepare_text_for_voice(scenario)
            # Then prepare for speech synthesis
            results = [prepare_for_speech(text) for _ in range(100)]
            # Check both text and checksums
            assert all(r.text == results[0].text for r in results)
            assert all(r.prepared_checksum == results[0].prepared_checksum for r in results)


class TestEdgeCases:
    """Edge cases for voice character enforcement."""

    def test_empty_input(self):
        """Should handle empty input gracefully."""
        assert remove_forbidden_phrases("") == ""
        assert limit_for_speech("") == ""
        assert prepare_text_for_voice("") == ""

    def test_only_forbidden_phrases(self):
        """Should handle input that's entirely forbidden phrases."""
        text = "Does that make sense? I hope this helps!"
        result = remove_forbidden_phrases(text)
        # Should be mostly empty or just punctuation/spaces
        assert len(result.split()) < 3

    def test_punctuation_only(self):
        """Should handle punctuation-only input."""
        assert limit_for_speech("...") == "..."

    def test_unicode_preserved(self):
        """Should preserve unicode characters."""
        text = "Here's the answer with émojis"
        result = prepare_text_for_voice(text)
        assert "émojis" in result

    def test_newlines_normalized(self):
        """Should normalize newlines in text."""
        text = "First line.\n\nSecond line."
        result = prepare_text_for_voice(text)
        assert "\n\n" not in result
