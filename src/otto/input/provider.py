"""
Input Provider Abstraction
==========================

Platform-agnostic input handling to replace terminal-specific input.

Supports:
- Synchronous input (terminal stdin)
- Asynchronous input (APIs, mobile)
- Memory-based input (testing)

Determinism:
- Fixed provider selection order
- Deterministic behavior in testing
- No runtime variation in input logic
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class InputType(Enum):
    """Types of input requests."""
    TEXT = "text"          # Free-form text input
    PASSWORD = "password"  # Hidden password input
    CHOICE = "choice"      # Select from options
    CONFIRM = "confirm"    # Yes/no confirmation
    NUMBER = "number"      # Numeric input
    MULTILINE = "multiline"  # Multi-line text


@dataclass
class InputChoice:
    """
    A choice option for selection inputs.

    Attributes:
        value: The value returned when selected
        label: Display label for the choice
        description: Optional description
        shortcut: Optional keyboard shortcut
    """
    value: Any
    label: str
    description: Optional[str] = None
    shortcut: Optional[str] = None


@dataclass
class InputResult:
    """
    Result of an input operation.

    Attributes:
        value: The input value
        cancelled: Whether input was cancelled
        error: Optional error message
        metadata: Additional metadata
    """
    value: Any = None
    cancelled: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if input was successful."""
        return not self.cancelled and self.error is None


class InputProvider(ABC):
    """
    Abstract base class for input providers.

    Implementations provide platform-specific input handling
    while maintaining consistent input semantics.
    """

    @property
    @abstractmethod
    def is_interactive(self) -> bool:
        """Return whether this provider supports interactive input."""
        pass

    @abstractmethod
    async def get_text(
        self,
        prompt: str,
        default: Optional[str] = None,
        validator: Optional[Callable[[str], bool]] = None,
    ) -> InputResult:
        """
        Get text input from user.

        Args:
            prompt: Prompt to display
            default: Default value if no input
            validator: Optional validation function

        Returns:
            InputResult with text value
        """
        pass

    @abstractmethod
    async def get_password(
        self,
        prompt: str,
        confirm: bool = False,
    ) -> InputResult:
        """
        Get password input (hidden).

        Args:
            prompt: Prompt to display
            confirm: Whether to ask for confirmation

        Returns:
            InputResult with password value
        """
        pass

    @abstractmethod
    async def get_choice(
        self,
        prompt: str,
        choices: List[InputChoice],
        default: Optional[Any] = None,
    ) -> InputResult:
        """
        Get selection from choices.

        Args:
            prompt: Prompt to display
            choices: List of InputChoice options
            default: Default choice value

        Returns:
            InputResult with selected value
        """
        pass

    @abstractmethod
    async def get_confirm(
        self,
        prompt: str,
        default: bool = False,
    ) -> InputResult:
        """
        Get yes/no confirmation.

        Args:
            prompt: Question to ask
            default: Default answer

        Returns:
            InputResult with boolean value
        """
        pass

    async def get_number(
        self,
        prompt: str,
        default: Optional[float] = None,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> InputResult:
        """
        Get numeric input.

        Default implementation uses get_text with validation.
        """
        def validate(val: str) -> bool:
            try:
                num = float(val)
                if min_val is not None and num < min_val:
                    return False
                if max_val is not None and num > max_val:
                    return False
                return True
            except ValueError:
                return False

        default_str = str(default) if default is not None else None
        result = await self.get_text(
            prompt,
            default=default_str,
            validator=validate,
        )

        if result.success and result.value:
            try:
                result.value = float(result.value)
                if result.value == int(result.value):
                    result.value = int(result.value)
            except ValueError:
                result.error = "Invalid number"

        return result

    async def get_multiline(
        self,
        prompt: str,
        end_marker: str = "END",
    ) -> InputResult:
        """
        Get multi-line text input.

        Default implementation collects lines until end_marker.
        """
        lines = []
        result = await self.get_text(f"{prompt} (enter '{end_marker}' when done)")

        while result.success and result.value != end_marker:
            lines.append(result.value)
            result = await self.get_text(">")

        if result.success:
            result.value = "\n".join(lines)

        return result


class SyncInputProvider(InputProvider):
    """
    Synchronous input provider wrapping async interface.

    Useful for terminal-based input where async is not needed.
    """

    @property
    def is_interactive(self) -> bool:
        return True

    def get_text_sync(
        self,
        prompt: str,
        default: Optional[str] = None,
        validator: Optional[Callable[[str], bool]] = None,
    ) -> InputResult:
        """Synchronous text input."""
        try:
            value = input(prompt)
            if not value and default is not None:
                value = default

            if validator and not validator(value):
                return InputResult(error="Validation failed")

            return InputResult(value=value)
        except EOFError:
            return InputResult(cancelled=True)
        except KeyboardInterrupt:
            return InputResult(cancelled=True)

    def get_password_sync(
        self,
        prompt: str,
        confirm: bool = False,
    ) -> InputResult:
        """Synchronous password input."""
        try:
            import getpass
            password = getpass.getpass(prompt)

            if confirm:
                password2 = getpass.getpass("Confirm: ")
                if password != password2:
                    return InputResult(error="Passwords do not match")

            return InputResult(value=password)
        except EOFError:
            return InputResult(cancelled=True)
        except KeyboardInterrupt:
            return InputResult(cancelled=True)

    def get_choice_sync(
        self,
        prompt: str,
        choices: List[InputChoice],
        default: Optional[Any] = None,
    ) -> InputResult:
        """Synchronous choice selection."""
        # Display choices
        print(prompt)
        for i, choice in enumerate(choices, 1):
            prefix = f"  [{i}]"
            if choice.shortcut:
                prefix = f"  [{choice.shortcut}]"
            line = f"{prefix} {choice.label}"
            if choice.description:
                line += f" - {choice.description}"
            if default is not None and choice.value == default:
                line += " (default)"
            print(line)

        try:
            value = input("> ").strip()

            # Empty input uses default
            if not value and default is not None:
                return InputResult(value=default)

            # Try numeric selection
            try:
                idx = int(value) - 1
                if 0 <= idx < len(choices):
                    return InputResult(value=choices[idx].value)
            except ValueError:
                pass

            # Try shortcut match
            for choice in choices:
                if choice.shortcut and choice.shortcut.lower() == value.lower():
                    return InputResult(value=choice.value)

            # Try label match
            for choice in choices:
                if choice.label.lower() == value.lower():
                    return InputResult(value=choice.value)

            return InputResult(error=f"Invalid selection: {value}")
        except EOFError:
            return InputResult(cancelled=True)
        except KeyboardInterrupt:
            return InputResult(cancelled=True)

    def get_confirm_sync(
        self,
        prompt: str,
        default: bool = False,
    ) -> InputResult:
        """Synchronous confirmation."""
        suffix = " [Y/n]" if default else " [y/N]"
        try:
            value = input(prompt + suffix + " ").strip().lower()

            if not value:
                return InputResult(value=default)

            if value in ("y", "yes", "true", "1"):
                return InputResult(value=True)
            elif value in ("n", "no", "false", "0"):
                return InputResult(value=False)
            else:
                return InputResult(error=f"Invalid response: {value}")
        except EOFError:
            return InputResult(cancelled=True)
        except KeyboardInterrupt:
            return InputResult(cancelled=True)

    # Async wrappers for interface compliance
    async def get_text(self, prompt: str, **kwargs) -> InputResult:
        return self.get_text_sync(prompt, **kwargs)

    async def get_password(self, prompt: str, **kwargs) -> InputResult:
        return self.get_password_sync(prompt, **kwargs)

    async def get_choice(self, prompt: str, choices: List[InputChoice], **kwargs) -> InputResult:
        return self.get_choice_sync(prompt, choices, **kwargs)

    async def get_confirm(self, prompt: str, **kwargs) -> InputResult:
        return self.get_confirm_sync(prompt, **kwargs)


class AsyncInputProvider(InputProvider):
    """
    Asynchronous input provider for APIs and mobile.

    Uses a callback or queue-based input mechanism.
    """

    def __init__(
        self,
        input_callback: Optional[Callable[[str, InputType], Any]] = None,
    ):
        """
        Initialize async provider.

        Args:
            input_callback: Async callback to get input
                           Receives (prompt, input_type) and returns value
        """
        self._callback = input_callback
        self._pending_requests: asyncio.Queue = asyncio.Queue()
        self._responses: asyncio.Queue = asyncio.Queue()

    @property
    def is_interactive(self) -> bool:
        return self._callback is not None

    async def _request_input(
        self,
        prompt: str,
        input_type: InputType,
        **kwargs
    ) -> InputResult:
        """Request input via callback or queue."""
        if self._callback:
            try:
                value = await self._callback(prompt, input_type)
                return InputResult(value=value)
            except asyncio.CancelledError:
                return InputResult(cancelled=True)
            except Exception as e:
                return InputResult(error=str(e))
        else:
            # Queue-based: put request, wait for response
            await self._pending_requests.put({
                "prompt": prompt,
                "type": input_type,
                **kwargs
            })
            try:
                response = await self._responses.get()
                return InputResult(value=response)
            except asyncio.CancelledError:
                return InputResult(cancelled=True)

    async def provide_response(self, value: Any) -> None:
        """Provide a response to a pending request (for queue-based input)."""
        await self._responses.put(value)

    async def get_text(
        self,
        prompt: str,
        default: Optional[str] = None,
        validator: Optional[Callable[[str], bool]] = None,
    ) -> InputResult:
        result = await self._request_input(prompt, InputType.TEXT, default=default)

        if result.success:
            if not result.value and default:
                result.value = default
            if validator and result.value and not validator(result.value):
                result.error = "Validation failed"

        return result

    async def get_password(
        self,
        prompt: str,
        confirm: bool = False,
    ) -> InputResult:
        return await self._request_input(prompt, InputType.PASSWORD, confirm=confirm)

    async def get_choice(
        self,
        prompt: str,
        choices: List[InputChoice],
        default: Optional[Any] = None,
    ) -> InputResult:
        return await self._request_input(
            prompt,
            InputType.CHOICE,
            choices=[{"value": c.value, "label": c.label} for c in choices],
            default=default,
        )

    async def get_confirm(
        self,
        prompt: str,
        default: bool = False,
    ) -> InputResult:
        result = await self._request_input(prompt, InputType.CONFIRM, default=default)

        if result.success:
            # Normalize to boolean
            if isinstance(result.value, str):
                result.value = result.value.lower() in ("y", "yes", "true", "1")
            elif result.value is None:
                result.value = default

        return result


class MemoryInputProvider(InputProvider):
    """
    In-memory input provider for testing.

    Pre-populated with responses that are returned in order.
    """

    def __init__(
        self,
        responses: Optional[List[Any]] = None,
        default_response: Any = "",
    ):
        """
        Initialize memory provider.

        Args:
            responses: List of responses to return in order
            default_response: Response when list is exhausted
        """
        self._responses = list(responses) if responses else []
        self._default = default_response
        self._request_history: List[Dict[str, Any]] = []

    @property
    def is_interactive(self) -> bool:
        return False

    @property
    def request_history(self) -> List[Dict[str, Any]]:
        """Get history of input requests (for test assertions)."""
        return self._request_history

    def add_response(self, response: Any) -> None:
        """Add a response to the queue."""
        self._responses.append(response)

    def add_responses(self, responses: List[Any]) -> None:
        """Add multiple responses to the queue."""
        self._responses.extend(responses)

    def clear(self) -> None:
        """Clear responses and history."""
        self._responses.clear()
        self._request_history.clear()

    def _get_next_response(self) -> Any:
        """Get next response from queue or default."""
        if self._responses:
            return self._responses.pop(0)
        return self._default

    async def get_text(
        self,
        prompt: str,
        default: Optional[str] = None,
        validator: Optional[Callable[[str], bool]] = None,
    ) -> InputResult:
        self._request_history.append({
            "type": InputType.TEXT,
            "prompt": prompt,
            "default": default,
        })

        value = self._get_next_response()
        if not value and default:
            value = default

        if validator and value and not validator(value):
            return InputResult(error="Validation failed")

        return InputResult(value=value)

    async def get_password(
        self,
        prompt: str,
        confirm: bool = False,
    ) -> InputResult:
        self._request_history.append({
            "type": InputType.PASSWORD,
            "prompt": prompt,
            "confirm": confirm,
        })

        return InputResult(value=self._get_next_response())

    async def get_choice(
        self,
        prompt: str,
        choices: List[InputChoice],
        default: Optional[Any] = None,
    ) -> InputResult:
        self._request_history.append({
            "type": InputType.CHOICE,
            "prompt": prompt,
            "choices": [c.value for c in choices],
            "default": default,
        })

        value = self._get_next_response()

        # Validate choice is in options
        valid_values = [c.value for c in choices]
        if value not in valid_values:
            if default is not None:
                value = default
            elif valid_values:
                value = valid_values[0]

        return InputResult(value=value)

    async def get_confirm(
        self,
        prompt: str,
        default: bool = False,
    ) -> InputResult:
        self._request_history.append({
            "type": InputType.CONFIRM,
            "prompt": prompt,
            "default": default,
        })

        value = self._get_next_response()

        # Normalize to boolean
        if isinstance(value, str):
            value = value.lower() in ("y", "yes", "true", "1")
        elif value is None:
            value = default
        else:
            value = bool(value)

        return InputResult(value=value)


# =============================================================================
# Global Instance
# =============================================================================

_input_provider: Optional[InputProvider] = None


def get_input_provider() -> InputProvider:
    """
    Get the global input provider instance.

    Creates MemoryInputProvider by default for safety.
    Use OTTO_INPUT_PROVIDER env var to set default: 'sync', 'async', 'memory'.
    """
    global _input_provider
    if _input_provider is None:
        _input_provider = _create_default_provider()
    return _input_provider


def _create_default_provider() -> InputProvider:
    """
    Create default provider based on environment.

    Fixed selection order: env var → memory (safe default)
    """
    provider_env = os.environ.get("OTTO_INPUT_PROVIDER", "").lower()

    if provider_env == "sync":
        logger.debug("Using sync input provider from environment")
        return SyncInputProvider()
    elif provider_env == "async":
        logger.debug("Using async input provider from environment")
        return AsyncInputProvider()
    else:
        # Default to memory for safety (no blocking on stdin)
        logger.debug("Using memory input provider (default)")
        return MemoryInputProvider()


def set_input_provider(provider: InputProvider) -> None:
    """
    Set the global input provider.

    Useful for testing or platform-specific configuration.
    """
    global _input_provider
    _input_provider = provider


def reset_input_provider() -> None:
    """Reset global input provider (for testing)."""
    global _input_provider
    _input_provider = None
