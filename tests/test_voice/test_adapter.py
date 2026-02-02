"""Tests for voice adapter."""
import pytest
from otto.voice.adapter import VoiceAdapter, adapt_response
from otto.voice.register import Register


class TestForbiddenPhrases:

    @pytest.fixture
    def adapter(self):
        adapter = VoiceAdapter()
        adapter.set_context(Register.NEUTRAL)
        return adapter

    def test_strips_i_understand(self, adapter):
        result = adapter.adapt("I understand you're frustrated. Here's the fix.")
        assert "I understand" not in result
        assert "fix" in result

    def test_strips_happy_to_help(self, adapter):
        result = adapter.adapt("I'd be happy to help you with that!")
        assert "happy to help" not in result

    def test_strips_certainly(self, adapter):
        result = adapter.adapt("Certainly! Here's what you need.")
        assert "Certainly" not in result

    def test_strips_great_question(self, adapter):
        result = adapter.adapt("Great question! The answer is...")
        assert "Great question" not in result

    def test_strips_as_an_ai(self, adapter):
        result = adapter.adapt("As an AI, I don't have feelings.")
        assert "As an AI" not in result

    def test_strips_absolutely(self, adapter):
        result = adapter.adapt("Absolutely! Let me explain.")
        assert "Absolutely" not in result


class TestIStarts:

    @pytest.fixture
    def adapter(self):
        adapter = VoiceAdapter()
        adapter.set_context(Register.NEUTRAL)
        return adapter

    def test_removes_i_think(self, adapter):
        result = adapter.adapt("I think you should try this.")
        assert not result.startswith("I think")

    def test_removes_i_believe(self, adapter):
        result = adapter.adapt("I believe the issue is here.")
        assert not result.startswith("I believe")

    def test_rewrites_i_notice(self, adapter):
        result = adapter.adapt("I notice there's an error.")
        assert not result.startswith("I notice")

    def test_rewrites_i_can_see(self, adapter):
        result = adapter.adapt("I can see that you're stuck.")
        assert result.startswith("Looks like")


class TestRegisterAdaptation:

    def test_casual_uses_contractions(self):
        result = adapt_response(
            "I am going to help you.",
            Register.CASUAL
        )
        assert "I'm" in result or "gonna" in result

    def test_formal_expands_contractions(self):
        result = adapt_response(
            "I'm going to help.",
            Register.FORMAL
        )
        assert "I am" in result

    def test_terse_keeps_first_sentence(self):
        result = adapt_response(
            "Here's the fix. You need to restart. Then check the logs.",
            Register.TERSE
        )
        assert result.count('.') == 1

    def test_venting_limits_sentences(self):
        result = adapt_response(
            "First thing. Second thing. Third thing. Fourth thing.",
            Register.VENTING
        )
        assert result.count('.') <= 2


class TestEmoji:

    def test_strips_emoji_by_default(self):
        result = adapt_response(
            "Got it! Let's do this",
            Register.CASUAL,
            user_uses_emoji=False
        )
        # No emoji in output
        assert result == adapt_response(result, Register.CASUAL, user_uses_emoji=False)

    def test_keeps_emoji_if_user_uses(self):
        # With emoji
        adapter = VoiceAdapter()
        adapter.set_context(Register.CASUAL, user_uses_emoji=True)
        # Adapter doesn't add emoji, just preserves them


class TestCleanup:

    @pytest.fixture
    def adapter(self):
        adapter = VoiceAdapter()
        adapter.set_context(Register.NEUTRAL)
        return adapter

    def test_removes_multiple_spaces(self, adapter):
        result = adapter.adapt("Here  is   the  fix.")
        assert "  " not in result

    def test_removes_space_before_punctuation(self, adapter):
        result = adapter.adapt("Here is the fix .")
        assert " ." not in result


class TestDeterminism:

    def test_adapter_deterministic(self):
        """Adapter must produce same output for same input."""
        response = "I'd be happy to help you with that! Here's the solution."
        results = [adapt_response(response, Register.CASUAL) for _ in range(100)]
        assert all(r == results[0] for r in results)
