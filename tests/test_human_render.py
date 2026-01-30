"""
Tests for Human Render Layer
=============================

Tests dignity-first language transformation.
"""

import pytest

from otto.render import (
    HumanRender,
    render_status,
    render_protection_message,
    render_welcome,
    FORBIDDEN_WORDS,
    STATE_PHRASES,
    PROTECTION_PHRASES,
)
from otto.render.phrases import contains_forbidden_word, validate_phrase
from otto.render.human_render import ProtectionEvent
from otto.cognitive_state import (
    CognitiveState,
    BurnoutLevel,
    MomentumPhase,
    EnergyLevel,
)
from otto.prism_detector import SignalVector


class TestForbiddenWords:
    """Tests for forbidden word detection."""

    def test_detects_clinical_terms(self):
        """Test that clinical terms are detected."""
        assert contains_forbidden_word("You have ADHD symptoms") is True
        assert contains_forbidden_word("This disorder affects focus") is True
        assert contains_forbidden_word("executive function deficit") is True

    def test_allows_human_language(self):
        """Test that human-friendly language is allowed."""
        assert contains_forbidden_word("You seem stuck") is False
        assert contains_forbidden_word("Feeling scattered today") is False
        assert contains_forbidden_word("Pretty wiped") is False

    def test_case_insensitive(self):
        """Test case insensitive detection."""
        assert contains_forbidden_word("ADHD") is True
        assert contains_forbidden_word("Adhd") is True
        assert contains_forbidden_word("adhd") is True


class TestValidatePhrase:
    """Tests for phrase validation."""

    def test_valid_phrase(self):
        """Test validation of clean phrases."""
        is_valid, reason = validate_phrase("You're doing great")
        assert is_valid is True
        assert reason == "OK"

    def test_invalid_phrase(self):
        """Test validation of phrases with forbidden words."""
        is_valid, reason = validate_phrase("Manage your ADHD symptoms")
        assert is_valid is False
        assert "forbidden" in reason.lower()


class TestStatePhrases:
    """Tests for state phrase dictionary."""

    def test_all_burnout_levels_have_phrases(self):
        """Test that all burnout levels have phrase entries."""
        for level in ["green", "yellow", "orange", "red"]:
            key = f"burnout_{level}"
            assert key in STATE_PHRASES
            assert "short" in STATE_PHRASES[key]
            assert "status" in STATE_PHRASES[key]

    def test_all_energy_levels_have_phrases(self):
        """Test that all energy levels have phrase entries."""
        for level in ["high", "medium", "low", "depleted"]:
            key = f"energy_{level}"
            assert key in STATE_PHRASES

    def test_no_forbidden_words_in_phrases(self):
        """Test that no phrases contain forbidden words."""
        for key, phrases in STATE_PHRASES.items():
            for phrase_key, phrase in phrases.items():
                assert not contains_forbidden_word(phrase), \
                    f"Forbidden word in STATE_PHRASES[{key}][{phrase_key}]: {phrase}"


class TestProtectionPhrases:
    """Tests for protection phrase dictionary."""

    def test_no_forbidden_words_in_protection(self):
        """Test that no protection phrases contain forbidden words."""
        for key, phrases in PROTECTION_PHRASES.items():
            for phrase_key, phrase in phrases.items():
                assert not contains_forbidden_word(phrase), \
                    f"Forbidden word in PROTECTION_PHRASES[{key}][{phrase_key}]: {phrase}"


class TestHumanRender:
    """Tests for HumanRender class."""

    def test_render_status_green(self):
        """Test status rendering for GREEN burnout."""
        state = CognitiveState(burnout_level=BurnoutLevel.GREEN)
        renderer = HumanRender(otto_role="companion")
        status = renderer.render_status(state)

        assert "good" in status.lower() or "okay" in status.lower()
        assert not contains_forbidden_word(status)

    def test_render_status_red(self):
        """Test status rendering for RED burnout."""
        state = CognitiveState(burnout_level=BurnoutLevel.RED)
        renderer = HumanRender(otto_role="companion")
        status = renderer.render_status(state)

        assert "wiped" in status.lower() or "fried" in status.lower()
        assert not contains_forbidden_word(status)

    def test_render_status_tool_role(self):
        """Test minimal status for tool role."""
        state = CognitiveState(
            burnout_level=BurnoutLevel.YELLOW,
            momentum_phase=MomentumPhase.ROLLING
        )
        renderer = HumanRender(otto_role="tool")
        status = renderer.render_status(state)

        # Tool mode should be minimal
        assert len(status) < 50

    def test_render_status_line(self):
        """Test status line formatting."""
        state = CognitiveState(
            burnout_level=BurnoutLevel.GREEN,
            momentum_phase=MomentumPhase.ROLLING,
            exchange_count=10
        )
        renderer = HumanRender()
        line = renderer.render_status_line(state, goal="Build feature", expert="Direct")

        assert "Goal: Build feature" in line
        assert "Direct" in line
        assert "GREEN" in line
        assert "rolling" in line

    def test_render_protection_gentle(self):
        """Test protection message rendering."""
        renderer = HumanRender(otto_role="companion")
        event = ProtectionEvent("time_check", "gentle", {"time": "45 minutes"})
        message = renderer.render_protection(event)

        assert "45 minutes" in message or "time" in message.lower()
        assert not contains_forbidden_word(message)

    def test_render_celebration(self):
        """Test celebration rendering."""
        renderer = HumanRender()

        # Should return one of the celebration phrases
        celebration = renderer.render_celebration("small_win")
        assert celebration is not None
        assert len(celebration) > 0

    def test_render_celebration_after_struggle(self):
        """Test celebration after struggle."""
        renderer = HumanRender()
        celebration = renderer.render_celebration("medium_win", after_struggle=True)

        # Should acknowledge the struggle
        assert "through" in celebration.lower() or "hard" in celebration.lower() \
               or "did" in celebration.lower()

    def test_render_welcome_new_session(self):
        """Test welcome for new session."""
        renderer = HumanRender(otto_role="companion")
        welcome = renderer.render_welcome()

        assert "working on" in welcome.lower() or "focus" in welcome.lower()

    def test_render_welcome_with_previous_session(self):
        """Test welcome with previous session data."""
        renderer = HumanRender(otto_role="companion")
        previous = {
            "task": "building the API",
            "burnout_level": "green",
        }
        welcome = renderer.render_welcome(previous, current_hour=10)

        assert "api" in welcome.lower() or "last" in welcome.lower()

    def test_render_goodbye_normal(self):
        """Test goodbye message."""
        state = CognitiveState(burnout_level=BurnoutLevel.GREEN)
        renderer = HumanRender(otto_role="companion")
        goodbye = renderer.render_goodbye(state)

        assert "saved" in goodbye.lower()

    def test_render_goodbye_tired(self):
        """Test goodbye when tired."""
        state = CognitiveState(burnout_level=BurnoutLevel.ORANGE)
        renderer = HumanRender(otto_role="companion")
        goodbye = renderer.render_goodbye(state)

        assert "rest" in goodbye.lower() or "earned" in goodbye.lower()

    def test_validate_output(self):
        """Test output validation."""
        renderer = HumanRender()

        assert renderer.validate_output("You seem stuck") is True
        assert renderer.validate_output("Your ADHD symptoms") is False


class TestRenderFunctions:
    """Tests for convenience functions."""

    def test_render_status_function(self):
        """Test render_status convenience function."""
        state = CognitiveState()
        status = render_status(state)
        assert isinstance(status, str)
        assert not contains_forbidden_word(status)

    def test_render_protection_message_function(self):
        """Test render_protection_message convenience function."""
        message = render_protection_message(
            "time_check",
            severity="moderate",
            otto_role="companion",
            time="2 hours"
        )
        assert isinstance(message, str)

    def test_render_welcome_function(self):
        """Test render_welcome convenience function."""
        welcome = render_welcome()
        assert isinstance(welcome, str)


class TestEmotionalResponses:
    """Tests for emotional response rendering."""

    def test_render_emotional_response_frustrated(self):
        """Test response to frustration."""
        renderer = HumanRender()
        signals = SignalVector(emotional={"frustrated": 0.8})
        response = renderer.render_emotional_response(signals)

        assert response is not None
        assert not contains_forbidden_word(response)

    def test_render_emotional_response_no_emotion(self):
        """Test no response when no emotion."""
        renderer = HumanRender()
        signals = SignalVector()
        response = renderer.render_emotional_response(signals)

        assert response is None

    def test_render_emotional_response_tool_mode(self):
        """Test tool mode doesn't give emotional responses."""
        renderer = HumanRender(otto_role="tool")
        signals = SignalVector(emotional={"frustrated": 0.8})
        response = renderer.render_emotional_response(signals)

        assert response is None
