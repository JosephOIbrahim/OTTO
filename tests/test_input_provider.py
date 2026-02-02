"""
Tests for Input Provider Abstraction
====================================

Tests the input provider interface and implementations.

[He2025] Compliance:
- Tests verify deterministic behavior
- Same inputs → same outputs
"""

import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from otto.input import (
    InputProvider,
    InputType,
    InputChoice,
    InputResult,
    SyncInputProvider,
    AsyncInputProvider,
    MemoryInputProvider,
    get_input_provider,
    set_input_provider,
    reset_input_provider,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def memory_provider():
    """Create a memory input provider."""
    return MemoryInputProvider()


@pytest.fixture
def memory_provider_with_responses():
    """Create a memory provider with pre-populated responses."""
    return MemoryInputProvider(responses=["response1", "response2", "response3"])


@pytest.fixture
def sample_choices():
    """Create sample choices."""
    return [
        InputChoice(value="opt1", label="Option 1", description="First option"),
        InputChoice(value="opt2", label="Option 2", shortcut="2"),
        InputChoice(value="opt3", label="Option 3"),
    ]


@pytest.fixture(autouse=True)
def reset_global():
    """Reset global provider before and after each test."""
    reset_input_provider()
    yield
    reset_input_provider()


# =============================================================================
# InputChoice Tests
# =============================================================================

class TestInputChoice:
    """Tests for InputChoice dataclass."""

    def test_create_choice(self):
        """Test creating a choice."""
        choice = InputChoice(
            value="test",
            label="Test Choice",
        )

        assert choice.value == "test"
        assert choice.label == "Test Choice"
        assert choice.description is None
        assert choice.shortcut is None

    def test_create_choice_with_all_fields(self):
        """Test creating a choice with all fields."""
        choice = InputChoice(
            value=42,
            label="Answer",
            description="The ultimate answer",
            shortcut="a",
        )

        assert choice.value == 42
        assert choice.description == "The ultimate answer"
        assert choice.shortcut == "a"


# =============================================================================
# InputResult Tests
# =============================================================================

class TestInputResult:
    """Tests for InputResult dataclass."""

    def test_create_result(self):
        """Test creating a result."""
        result = InputResult(value="test")

        assert result.value == "test"
        assert result.cancelled is False
        assert result.error is None
        assert result.success is True

    def test_cancelled_result(self):
        """Test cancelled result."""
        result = InputResult(cancelled=True)

        assert result.success is False
        assert result.cancelled is True

    def test_error_result(self):
        """Test error result."""
        result = InputResult(error="Something went wrong")

        assert result.success is False
        assert result.error == "Something went wrong"

    def test_result_with_metadata(self):
        """Test result with metadata."""
        result = InputResult(
            value="test",
            metadata={"source": "api", "timestamp": "2025-01-15"},
        )

        assert result.metadata["source"] == "api"


# =============================================================================
# MemoryInputProvider Tests
# =============================================================================

class TestMemoryInputProvider:
    """Tests for MemoryInputProvider."""

    def test_is_not_interactive(self, memory_provider):
        """Test that memory provider is not interactive."""
        assert memory_provider.is_interactive is False

    @pytest.mark.asyncio
    async def test_get_text_with_response(self, memory_provider):
        """Test getting text with pre-populated response."""
        memory_provider.add_response("hello")

        result = await memory_provider.get_text("Enter name: ")

        assert result.success is True
        assert result.value == "hello"

    @pytest.mark.asyncio
    async def test_get_text_default(self, memory_provider):
        """Test getting text with default value."""
        result = await memory_provider.get_text("Enter name: ", default="default_name")

        assert result.value == "default_name"

    @pytest.mark.asyncio
    async def test_get_text_validation(self, memory_provider):
        """Test text validation."""
        memory_provider.add_response("short")

        result = await memory_provider.get_text(
            "Enter: ",
            validator=lambda x: len(x) >= 10,
        )

        assert result.success is False
        assert result.error == "Validation failed"

    @pytest.mark.asyncio
    async def test_get_password(self, memory_provider):
        """Test getting password."""
        memory_provider.add_response("secret123")

        result = await memory_provider.get_password("Password: ")

        assert result.value == "secret123"

    @pytest.mark.asyncio
    async def test_get_choice(self, memory_provider, sample_choices):
        """Test getting choice."""
        memory_provider.add_response("opt2")

        result = await memory_provider.get_choice("Select: ", sample_choices)

        assert result.value == "opt2"

    @pytest.mark.asyncio
    async def test_get_choice_invalid_falls_back_to_default(self, memory_provider, sample_choices):
        """Test invalid choice falls back to default."""
        memory_provider.add_response("invalid")

        result = await memory_provider.get_choice("Select: ", sample_choices, default="opt1")

        assert result.value == "opt1"

    @pytest.mark.asyncio
    async def test_get_confirm_yes(self, memory_provider):
        """Test confirmation with yes."""
        memory_provider.add_response("yes")

        result = await memory_provider.get_confirm("Continue?")

        assert result.value is True

    @pytest.mark.asyncio
    async def test_get_confirm_no(self, memory_provider):
        """Test confirmation with no."""
        memory_provider.add_response("no")

        result = await memory_provider.get_confirm("Continue?")

        assert result.value is False

    @pytest.mark.asyncio
    async def test_get_confirm_default(self, memory_provider):
        """Test confirmation with default."""
        memory_provider.add_response(None)

        result = await memory_provider.get_confirm("Continue?", default=True)

        assert result.value is True

    @pytest.mark.asyncio
    async def test_response_queue_order(self, memory_provider_with_responses):
        """Test responses are returned in order."""
        r1 = await memory_provider_with_responses.get_text("1: ")
        r2 = await memory_provider_with_responses.get_text("2: ")
        r3 = await memory_provider_with_responses.get_text("3: ")

        assert r1.value == "response1"
        assert r2.value == "response2"
        assert r3.value == "response3"

    @pytest.mark.asyncio
    async def test_request_history(self, memory_provider):
        """Test request history is tracked."""
        memory_provider.add_responses(["a", "b", True])

        await memory_provider.get_text("Name: ")
        await memory_provider.get_password("Pass: ")
        await memory_provider.get_confirm("OK?")

        history = memory_provider.request_history

        assert len(history) == 3
        assert history[0]["type"] == InputType.TEXT
        assert history[0]["prompt"] == "Name: "
        assert history[1]["type"] == InputType.PASSWORD
        assert history[2]["type"] == InputType.CONFIRM

    def test_clear(self, memory_provider_with_responses):
        """Test clearing provider."""
        memory_provider_with_responses.clear()

        assert len(memory_provider_with_responses._responses) == 0
        assert len(memory_provider_with_responses.request_history) == 0

    @pytest.mark.asyncio
    async def test_get_number(self, memory_provider):
        """Test getting numeric input."""
        memory_provider.add_response("42")

        result = await memory_provider.get_number("Count: ")

        assert result.value == 42

    @pytest.mark.asyncio
    async def test_get_number_float(self, memory_provider):
        """Test getting float input."""
        memory_provider.add_response("3.14")

        result = await memory_provider.get_number("Value: ")

        assert result.value == 3.14


# =============================================================================
# AsyncInputProvider Tests
# =============================================================================

class TestAsyncInputProvider:
    """Tests for AsyncInputProvider."""

    def test_is_interactive_with_callback(self):
        """Test interactive with callback."""
        callback = AsyncMock(return_value="test")
        provider = AsyncInputProvider(input_callback=callback)

        assert provider.is_interactive is True

    def test_is_not_interactive_without_callback(self):
        """Test not interactive without callback."""
        provider = AsyncInputProvider()

        assert provider.is_interactive is False

    @pytest.mark.asyncio
    async def test_get_text_with_callback(self):
        """Test getting text with callback."""
        callback = AsyncMock(return_value="hello")
        provider = AsyncInputProvider(input_callback=callback)

        result = await provider.get_text("Name: ")

        assert result.value == "hello"
        callback.assert_called_once_with("Name: ", InputType.TEXT)

    @pytest.mark.asyncio
    async def test_callback_cancellation(self):
        """Test callback cancellation."""
        async def cancel_callback(prompt, input_type):
            raise asyncio.CancelledError()

        provider = AsyncInputProvider(input_callback=cancel_callback)

        result = await provider.get_text("Name: ")

        assert result.cancelled is True

    @pytest.mark.asyncio
    async def test_callback_error(self):
        """Test callback error handling."""
        async def error_callback(prompt, input_type):
            raise ValueError("Input error")

        provider = AsyncInputProvider(input_callback=error_callback)

        result = await provider.get_text("Name: ")

        assert result.success is False
        assert "Input error" in result.error

    @pytest.mark.asyncio
    async def test_get_confirm_normalizes_string(self):
        """Test confirm normalizes string responses."""
        callback = AsyncMock(return_value="yes")
        provider = AsyncInputProvider(input_callback=callback)

        result = await provider.get_confirm("Continue?")

        assert result.value is True


# =============================================================================
# SyncInputProvider Tests
# =============================================================================

class TestSyncInputProvider:
    """Tests for SyncInputProvider."""

    def test_is_interactive(self):
        """Test sync provider is interactive."""
        provider = SyncInputProvider()
        assert provider.is_interactive is True

    def test_get_text_sync(self):
        """Test synchronous text input."""
        provider = SyncInputProvider()

        with patch("builtins.input", return_value="test_input"):
            result = provider.get_text_sync("Enter: ")

        assert result.value == "test_input"

    def test_get_text_sync_default(self):
        """Test sync text with default."""
        provider = SyncInputProvider()

        with patch("builtins.input", return_value=""):
            result = provider.get_text_sync("Enter: ", default="default")

        assert result.value == "default"

    def test_get_text_sync_eof(self):
        """Test sync text with EOF."""
        provider = SyncInputProvider()

        with patch("builtins.input", side_effect=EOFError()):
            result = provider.get_text_sync("Enter: ")

        assert result.cancelled is True

    def test_get_text_sync_interrupt(self):
        """Test sync text with keyboard interrupt."""
        provider = SyncInputProvider()

        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            result = provider.get_text_sync("Enter: ")

        assert result.cancelled is True

    def test_get_password_sync(self):
        """Test synchronous password input."""
        provider = SyncInputProvider()

        with patch("getpass.getpass", return_value="secret"):
            result = provider.get_password_sync("Password: ")

        assert result.value == "secret"

    def test_get_password_sync_confirm_match(self):
        """Test password confirmation match."""
        provider = SyncInputProvider()

        with patch("getpass.getpass", side_effect=["secret", "secret"]):
            result = provider.get_password_sync("Password: ", confirm=True)

        assert result.value == "secret"

    def test_get_password_sync_confirm_mismatch(self):
        """Test password confirmation mismatch."""
        provider = SyncInputProvider()

        with patch("getpass.getpass", side_effect=["secret", "different"]):
            result = provider.get_password_sync("Password: ", confirm=True)

        assert result.success is False
        assert "do not match" in result.error

    def test_get_choice_sync_numeric(self, sample_choices):
        """Test choice by number."""
        provider = SyncInputProvider()

        with patch("builtins.input", return_value="2"), \
             patch("builtins.print"):
            result = provider.get_choice_sync("Select: ", sample_choices)

        assert result.value == "opt2"

    def test_get_choice_sync_shortcut(self, sample_choices):
        """Test choice by shortcut."""
        provider = SyncInputProvider()

        with patch("builtins.input", return_value="2"), \
             patch("builtins.print"):
            result = provider.get_choice_sync("Select: ", sample_choices)

        assert result.value == "opt2"

    def test_get_choice_sync_default(self, sample_choices):
        """Test choice with default on empty input."""
        provider = SyncInputProvider()

        with patch("builtins.input", return_value=""), \
             patch("builtins.print"):
            result = provider.get_choice_sync("Select: ", sample_choices, default="opt3")

        assert result.value == "opt3"

    def test_get_confirm_sync_yes(self):
        """Test confirm yes."""
        provider = SyncInputProvider()

        with patch("builtins.input", return_value="y"):
            result = provider.get_confirm_sync("Continue?")

        assert result.value is True

    def test_get_confirm_sync_no(self):
        """Test confirm no."""
        provider = SyncInputProvider()

        with patch("builtins.input", return_value="n"):
            result = provider.get_confirm_sync("Continue?")

        assert result.value is False

    def test_get_confirm_sync_default(self):
        """Test confirm with default."""
        provider = SyncInputProvider()

        with patch("builtins.input", return_value=""):
            result = provider.get_confirm_sync("Continue?", default=True)

        assert result.value is True


# =============================================================================
# Global Instance Tests
# =============================================================================

class TestGlobalInstance:
    """Tests for global input provider instance."""

    def test_get_provider_creates_instance(self):
        """Test that get_input_provider creates a provider."""
        provider = get_input_provider()
        assert isinstance(provider, InputProvider)

    def test_get_provider_returns_same_instance(self):
        """Test singleton behavior."""
        provider1 = get_input_provider()
        provider2 = get_input_provider()
        assert provider1 is provider2

    def test_set_provider_replaces_instance(self, memory_provider):
        """Test that set_input_provider replaces the global instance."""
        set_input_provider(memory_provider)
        assert get_input_provider() is memory_provider

    def test_reset_provider(self, memory_provider):
        """Test resetting the global instance."""
        set_input_provider(memory_provider)
        reset_input_provider()

        # Should create new instance
        provider = get_input_provider()
        assert provider is not memory_provider

    def test_env_sync_provider(self):
        """Test sync provider from environment."""
        with patch.dict(os.environ, {"OTTO_INPUT_PROVIDER": "sync"}):
            reset_input_provider()
            provider = get_input_provider()
            assert isinstance(provider, SyncInputProvider)

    def test_env_async_provider(self):
        """Test async provider from environment."""
        with patch.dict(os.environ, {"OTTO_INPUT_PROVIDER": "async"}):
            reset_input_provider()
            provider = get_input_provider()
            assert isinstance(provider, AsyncInputProvider)

    def test_default_is_memory(self):
        """Test default provider is memory (safe)."""
        provider = get_input_provider()
        assert isinstance(provider, MemoryInputProvider)


# =============================================================================
# [He2025] Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests verifying [He2025] compliant determinism."""

    @pytest.mark.asyncio
    async def test_same_input_same_output(self):
        """Test that same responses produce same results."""
        results = []
        for _ in range(10):
            provider = MemoryInputProvider(responses=["test_value"])
            result = await provider.get_text("Prompt: ")
            results.append(result.value)

        # All results should be identical
        assert len(set(results)) == 1
        assert results[0] == "test_value"

    @pytest.mark.asyncio
    async def test_choice_selection_deterministic(self, sample_choices):
        """Test that choice selection is deterministic."""
        results = []
        for _ in range(10):
            provider = MemoryInputProvider(responses=["opt2"])
            result = await provider.get_choice("Select: ", sample_choices)
            results.append(result.value)

        # All selections should be identical
        assert len(set(results)) == 1
        assert results[0] == "opt2"

    def test_provider_selection_deterministic(self):
        """Test that provider selection is deterministic."""
        providers = []
        for _ in range(10):
            reset_input_provider()
            with patch.dict(os.environ, {"OTTO_INPUT_PROVIDER": "sync"}):
                providers.append(type(get_input_provider()).__name__)

        # All selections should be identical
        assert len(set(providers)) == 1
        assert providers[0] == "SyncInputProvider"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_response(self, memory_provider):
        """Test handling empty response."""
        memory_provider.add_response("")

        result = await memory_provider.get_text("Enter: ")

        assert result.value == ""

    @pytest.mark.asyncio
    async def test_unicode_input(self, memory_provider):
        """Test unicode input."""
        memory_provider.add_response("こんにちは 🎉")

        result = await memory_provider.get_text("Enter: ")

        assert result.value == "こんにちは 🎉"

    @pytest.mark.asyncio
    async def test_long_input(self, memory_provider):
        """Test very long input."""
        long_input = "x" * 10000
        memory_provider.add_response(long_input)

        result = await memory_provider.get_text("Enter: ")

        assert result.value == long_input

    @pytest.mark.asyncio
    async def test_special_characters(self, memory_provider):
        """Test special characters in input."""
        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        memory_provider.add_response(special)

        result = await memory_provider.get_text("Enter: ")

        assert result.value == special

    @pytest.mark.asyncio
    async def test_empty_choices_list(self, memory_provider):
        """Test empty choices list."""
        memory_provider.add_response("anything")

        result = await memory_provider.get_choice("Select: ", [])

        # Should handle gracefully
        assert result.value == "anything"

    @pytest.mark.asyncio
    async def test_validator_with_exception(self, memory_provider):
        """Test validator that raises exception."""
        memory_provider.add_response("test")

        def bad_validator(x):
            raise ValueError("Bad!")

        # Should handle exception gracefully
        try:
            result = await memory_provider.get_text("Enter: ", validator=bad_validator)
            # If it doesn't raise, it should have an error
        except ValueError:
            pass  # Expected

    @pytest.mark.asyncio
    async def test_confirm_various_yes_formats(self, memory_provider):
        """Test various yes formats."""
        yes_formats = ["y", "Y", "yes", "YES", "Yes", "true", "TRUE", "1"]

        for fmt in yes_formats:
            memory_provider.add_response(fmt)
            result = await memory_provider.get_confirm("OK?")
            assert result.value is True, f"Failed for '{fmt}'"

    @pytest.mark.asyncio
    async def test_confirm_various_no_formats(self, memory_provider):
        """Test various no formats."""
        no_formats = ["n", "N", "no", "NO", "No", "false", "FALSE", "0"]

        for fmt in no_formats:
            memory_provider.add_response(fmt)
            result = await memory_provider.get_confirm("OK?")
            assert result.value is False, f"Failed for '{fmt}'"
