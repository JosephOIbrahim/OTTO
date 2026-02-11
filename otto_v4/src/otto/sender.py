"""Outbound nudge sender for OTTO v5.0.

Sends nudges through a Transport, gated by the constitutional layer.
The constitutional check happens BEFORE any outbound API call.

Usage:
    sender = NudgeSender(transport, state_store)
    result = await sender.send_nudge(commitment, "user")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .constitutional import should_suppress
from .log import get_logger
from .models import Commitment
from .nudge import format_nudge
from .state import StateStore
from .transport.base import DeliveryResult, Transport

_log = get_logger(__name__)


@dataclass
class SendAttempt:
    """Record of a send attempt for tracking."""

    commitment_id: str
    recipient: str
    success: bool
    suppressed: bool
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NudgeSender:
    """Sends nudges through a transport with constitutional gating.

    The key invariant: constitutional checks happen BEFORE any
    transport.send() call. OTTO never sends a nudge that violates
    safety principles.
    """

    def __init__(
        self,
        transport: Transport,
        state_store: StateStore,
    ) -> None:
        self._transport = transport
        self._state_store = state_store
        self._attempts: list[SendAttempt] = []

    @property
    def attempts(self) -> list[SendAttempt]:
        """All send attempts for this sender's lifetime."""
        return list(self._attempts)

    @property
    def successful_count(self) -> int:
        return sum(1 for a in self._attempts if a.success)

    @property
    def suppressed_count(self) -> int:
        return sum(1 for a in self._attempts if a.suppressed)

    async def send_nudge(
        self,
        commitment: Commitment,
        recipient: str,
        *,
        reason: str = "overdue",
    ) -> SendAttempt:
        """Send a nudge for a commitment, gated by constitutional layer.

        Parameters
        ----------
        commitment:
            The commitment to nudge about.
        recipient:
            Who to send to.
        reason:
            "overdue" or "stale" — used for template selection.

        Returns
        -------
        SendAttempt
            Record of what happened (sent, suppressed, or failed).
        """
        state = self._state_store.load()

        # Constitutional gate: check BEFORE sending
        suppression = should_suppress(state, "nudge")
        if suppression is not None:
            self._state_store.increment_suppressed()
            attempt = SendAttempt(
                commitment_id=commitment.id,
                recipient=recipient,
                success=False,
                suppressed=True,
                reason=suppression.reason,
            )
            self._attempts.append(attempt)
            _log.info(
                "Nudge suppressed for %s: %s",
                commitment.commitment_text[:30],
                suppression.reason,
            )
            return attempt

        # Generate nudge text
        nudge_text = format_nudge(commitment, reason)

        # Send via transport
        delivery = await self._transport.send(recipient, nudge_text)

        if delivery.success:
            self._state_store.increment_nudges_sent()

        attempt = SendAttempt(
            commitment_id=commitment.id,
            recipient=recipient,
            success=delivery.success,
            suppressed=False,
            reason=delivery.error if not delivery.success else "sent",
        )
        self._attempts.append(attempt)

        if delivery.success:
            _log.info("Nudge sent for: %s", commitment.commitment_text[:30])
        else:
            _log.warning(
                "Nudge delivery failed for %s: %s",
                commitment.commitment_text[:30],
                delivery.error,
            )

        return attempt
