"""CLI transport for OTTO v5.0.

Sends messages to stdout. Receives messages from function calls
(the Click CLI handles actual stdin interaction).
"""

from __future__ import annotations

from .base import DeliveryResult

from ..log import get_logger

_log = get_logger(__name__)


class CliTransport:
    """Transport that prints messages to stdout.

    This is the simplest transport — used by the CLI and for testing.
    """

    def __init__(self, *, capture: bool = False) -> None:
        self._capture = capture
        self._sent: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return "cli"

    @property
    def sent_messages(self) -> list[tuple[str, str]]:
        """Messages sent (for testing). Only populated when capture=True."""
        return list(self._sent)

    async def send(self, recipient: str, text: str) -> DeliveryResult:
        """Send a message by printing to stdout.

        Parameters
        ----------
        recipient:
            Ignored for CLI (always prints to stdout).
        text:
            The message to display.
        """
        if self._capture:
            self._sent.append((recipient, text))
        else:
            print(text)

        _log.debug("CLI send to %s: %s", recipient, text[:50])
        return DeliveryResult(success=True, transport="cli")
