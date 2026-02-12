"""Tests for the optional LLM response generation layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from otto.response_gen import is_llm_enabled, maybe_rephrase


# ------------------------------------------------------------------
# is_llm_enabled
# ------------------------------------------------------------------


class TestIsLlmEnabled:

    def test_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            assert not is_llm_enabled()

    def test_enabled_with_true(self):
        with patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "true"}):
            assert is_llm_enabled()

    def test_enabled_with_1(self):
        with patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "1"}):
            assert is_llm_enabled()

    def test_enabled_with_yes(self):
        with patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "yes"}):
            assert is_llm_enabled()

    def test_enabled_case_insensitive(self):
        with patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "TRUE"}):
            assert is_llm_enabled()

    def test_disabled_with_false(self):
        with patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "false"}):
            assert not is_llm_enabled()

    def test_disabled_with_empty(self):
        with patch.dict("os.environ", {"OTTO_LLM_RESPONSES": ""}):
            assert not is_llm_enabled()


# ------------------------------------------------------------------
# maybe_rephrase — disabled path
# ------------------------------------------------------------------


class TestMaybeRephraseDisabled:

    async def test_passthrough_when_disabled(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await maybe_rephrase("Hello world")
        assert result == "Hello world"

    async def test_passthrough_empty_string(self):
        with patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "true"}):
            result = await maybe_rephrase("")
        assert result == ""

    async def test_passthrough_whitespace_only(self):
        with patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "true"}):
            result = await maybe_rephrase("   ")
        assert result == "   "

    async def test_passthrough_preserves_exact_text(self):
        text = "Permission granted: rest is productive."
        with patch.dict("os.environ", {}, clear=True):
            result = await maybe_rephrase(text, mode="restorer", action="grant_rest")
        assert result == text


# ------------------------------------------------------------------
# maybe_rephrase — enabled path (mocked LLM)
# ------------------------------------------------------------------


class TestMaybeRephraseEnabled:

    async def test_calls_anthropic_when_enabled(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Take a break. You've earned it.")]

        mock_client_instance = MagicMock()
        mock_client_instance.messages = MagicMock()
        mock_client_instance.messages.create = AsyncMock(return_value=mock_response)

        with (
            patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "true"}),
            patch("otto.response_gen.anthropic") as mock_anthropic,
        ):
            mock_anthropic.AsyncAnthropic.return_value = mock_client_instance
            result = await maybe_rephrase(
                "Permission granted: rest is productive.",
                mode="restorer",
                action="grant_rest",
            )

        assert result == "Take a break. You've earned it."
        mock_client_instance.messages.create.assert_called_once()

    async def test_falls_back_on_error(self):
        original = "Your commitments are safe."
        with (
            patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "true"}),
            patch("otto.response_gen.anthropic") as mock_anthropic,
        ):
            mock_anthropic.AsyncAnthropic.side_effect = Exception("API down")
            result = await maybe_rephrase(original)

        assert result == original

    async def test_mode_and_action_passed_to_prompt(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Rephrased.")]

        mock_client_instance = MagicMock()
        mock_client_instance.messages = MagicMock()
        mock_client_instance.messages.create = AsyncMock(return_value=mock_response)

        with (
            patch.dict("os.environ", {"OTTO_LLM_RESPONSES": "true"}),
            patch("otto.response_gen.anthropic") as mock_anthropic,
        ):
            mock_anthropic.AsyncAnthropic.return_value = mock_client_instance
            await maybe_rephrase("Hello", mode="protector", action="validate")

        call_args = mock_client_instance.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "protector" in user_msg
        assert "validate" in user_msg
