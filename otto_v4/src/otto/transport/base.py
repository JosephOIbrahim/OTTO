"""Transport protocol for OTTO v5.0.

Every transport surface (CLI, WhatsApp, Telegram) implements this
protocol. The core engine sends through whatever transport is active.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Message:
    """A message received via a transport.

    Attributes
    ----------
    text:
        The message content.
    sender:
        Who sent it (phone number, username, "cli", etc.).
    source:
        Transport name (e.g. "cli", "whatsapp").
    timestamp:
        When the message was received.
    metadata:
        Transport-specific metadata.
    """

    text: str
    sender: str = "user"
    source: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryResult:
    """Result of sending a message via transport.

    Attributes
    ----------
    success:
        Whether the message was delivered.
    transport:
        Which transport was used.
    error:
        Error message if delivery failed.
    """

    success: bool
    transport: str
    error: str = ""


@runtime_checkable
class Transport(Protocol):
    """Protocol all transports must implement."""

    @property
    def name(self) -> str:
        """Transport identifier (e.g. 'cli', 'whatsapp')."""
        ...

    async def send(self, recipient: str, text: str) -> DeliveryResult:
        """Send a message to a recipient.

        Parameters
        ----------
        recipient:
            Who to send to (phone number, "stdout", etc.).
        text:
            The message content.

        Returns
        -------
        DeliveryResult
            Whether delivery succeeded.
        """
        ...
