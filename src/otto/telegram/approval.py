"""
Telegram Approval Handler
=========================

Inline button approval flow for Telegram surface.

Determinism:
- Fixed callback data format
- Deterministic request matching
- Sorted pending request iteration

Integration:
- Wires into ApprovalGate via approval_handler callback
- Presents inline keyboard [Approve] [Deny]
- Records decisions to memory trails (via ApprovalGate)
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Final, Optional

from ..services.approval import ApprovalRequest, get_approval_gate

logger = logging.getLogger(__name__)


# Fixed constants
APPROVAL_CALLBACK_PREFIX: Final[str] = "approval:"
APPROVAL_SEED: Final[int] = 0xA990BEAD
DEFAULT_TIMEOUT_SECONDS: Final[float] = 60.0


@dataclass
class PendingApproval:
    """
    Tracks a pending approval request in Telegram.

    Deterministic state tracking.
    """
    request_id: str
    chat_id: int
    message_id: Optional[int] = None  # Message with inline buttons
    future: asyncio.Future = field(default_factory=asyncio.Future)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def callback_data_approve(self) -> str:
        """Callback data for approve button."""
        return f"{APPROVAL_CALLBACK_PREFIX}approve:{self.request_id}"

    @property
    def callback_data_deny(self) -> str:
        """Callback data for deny button."""
        return f"{APPROVAL_CALLBACK_PREFIX}deny:{self.request_id}"

    def is_expired(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> bool:
        """Check if request has expired."""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > timeout


class TelegramApprovalHandler:
    """
    Handles approval requests via Telegram inline buttons.

    Determinism:
    - Deterministic callback parsing
    - Sorted pending iteration
    - Fixed evaluation order

    Usage:
        handler = TelegramApprovalHandler()

        # Register as approval handler with ApprovalGate
        gate = get_approval_gate(approval_handler=handler.request_approval)

        # Handle callback queries in bot
        async def callback_handler(update, context):
            if handler.is_approval_callback(update.callback_query.data):
                await handler.handle_callback(update, context)
    """

    def __init__(self, send_message_func: Optional[Callable[..., Awaitable[Any]]] = None):
        """
        Initialize handler.

        Args:
            send_message_func: Async function to send messages with buttons.
                               Signature: (chat_id, text, reply_markup) -> Message
        """
        self._send_message = send_message_func
        self._pending: Dict[str, PendingApproval] = {}

    def set_send_message(self, func: Callable[..., Awaitable[Any]]) -> None:
        """Set the message sending function (for deferred initialization)."""
        self._send_message = func

    async def request_approval(
        self,
        request: ApprovalRequest,
        chat_id: Optional[int] = None,
    ) -> bool:
        """
        Request approval via Telegram inline buttons.

        This is the callback passed to ApprovalGate.

        Args:
            request: The approval request
            chat_id: Telegram chat ID (extracted from request.details if not provided)

        Returns:
            True if approved, False if denied
        """
        # Try to get chat_id from request details if not provided
        target_chat_id = chat_id or request.details.get("chat_id")

        if not target_chat_id:
            logger.warning(f"No chat_id for approval request {request.id}")
            return False

        if not self._send_message:
            logger.error("No send_message function configured")
            return False

        # Create pending approval
        pending = PendingApproval(
            request_id=request.id,
            chat_id=target_chat_id,
        )
        self._pending[request.id] = pending

        try:
            # Build approval message
            text = self._format_approval_message(request)

            # Send message with inline buttons
            message = await self._send_approval_message(
                chat_id=target_chat_id,
                text=text,
                pending=pending,
            )

            if message:
                pending.message_id = message.message_id

            # Wait for response (with timeout)
            approved = await asyncio.wait_for(
                pending.future,
                timeout=request.timeout_seconds,
            )

            return approved

        except asyncio.TimeoutError:
            logger.info(f"Approval request {request.id} timed out")
            # Clean up the message
            await self._cleanup_approval_message(pending)
            return False

        finally:
            # Remove from pending
            self._pending.pop(request.id, None)

    def _format_approval_message(self, request: ApprovalRequest) -> str:
        """
        Format approval request for Telegram display.

        Deterministic formatting.
        """
        policy = request.policy

        lines = ["*Approval Required*\n"]

        # Action description
        if policy:
            lines.append(f"*Action:* {policy.description}")
            lines.append(f"*Category:* {policy.category.value.upper()}")
            lines.append(f"*Risk:* {policy.risk_level}")
        else:
            lines.append(f"*Action:* {request.action}")

        # Actor/Service info
        lines.append(f"\n*Requested by:* {request.actor}")
        if request.service:
            lines.append(f"*Service:* {request.service}")
        if request.resource:
            lines.append(f"*Resource:* {request.resource}")

        # Details (if any meaningful ones)
        meaningful_details = {
            k: v for k, v in request.details.items()
            if k not in ("chat_id", "user_id", "session_id")
        }
        if meaningful_details:
            lines.append("\n*Details:*")
            for key, value in sorted(meaningful_details.items()):
                lines.append(f"  • {key}: {value}")

        lines.append(f"\n_Timeout: {request.timeout_seconds:.0f}s_")

        return "\n".join(lines)

    async def _send_approval_message(
        self,
        chat_id: int,
        text: str,
        pending: PendingApproval,
    ):
        """Send message with approval buttons."""
        try:
            # Import here to avoid circular imports and allow for telegram not installed
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton(
                        "✓ Approve",
                        callback_data=pending.callback_data_approve,
                    ),
                    InlineKeyboardButton(
                        "✗ Deny",
                        callback_data=pending.callback_data_deny,
                    ),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            return await self._send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"Failed to send approval message: {e}")
            return None

    async def _cleanup_approval_message(self, pending: PendingApproval) -> None:
        """Remove or update the approval message after timeout/completion."""
        # TODO: Edit message to show "Expired" or "Completed" state
        pass

    def is_approval_callback(self, callback_data: str) -> bool:
        """Check if callback data is for an approval."""
        return callback_data.startswith(APPROVAL_CALLBACK_PREFIX)

    def parse_callback(self, callback_data: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse callback data.

        Returns:
            (action, request_id) tuple, or (None, None) if invalid
        """
        if not self.is_approval_callback(callback_data):
            return None, None

        try:
            # Format: "approval:action:request_id"
            parts = callback_data.split(":", 2)
            if len(parts) != 3:
                return None, None

            _, action, request_id = parts
            return action, request_id

        except Exception:
            return None, None

    async def handle_callback(
        self,
        callback_query,
        context=None,
    ) -> bool:
        """
        Handle a callback query for approval.

        Args:
            callback_query: Telegram CallbackQuery object
            context: Telegram context (optional)

        Returns:
            True if handled, False otherwise
        """
        action, request_id = self.parse_callback(callback_query.data)

        if not action or not request_id:
            return False

        # Find pending request
        pending = self._pending.get(request_id)

        if not pending:
            # Request expired or already handled
            try:
                await callback_query.answer(
                    "This approval request has expired or was already handled."
                )
            except Exception:
                pass
            return True

        # Process decision
        approved = action == "approve"

        try:
            # Answer the callback query
            await callback_query.answer(
                "Approved" if approved else "Denied"
            )

            # Update the message to show result
            result_text = "✓ *Approved*" if approved else "✗ *Denied*"
            try:
                await callback_query.edit_message_text(
                    text=f"{callback_query.message.text}\n\n{result_text}",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.debug(f"Could not edit message: {e}")

            # Resolve the future
            if not pending.future.done():
                pending.future.set_result(approved)

            return True

        except Exception as e:
            logger.error(f"Error handling approval callback: {e}")
            # Try to resolve anyway
            if not pending.future.done():
                pending.future.set_result(False)
            return True

    def get_pending_count(self) -> int:
        """Get number of pending approvals."""
        return len(self._pending)

    def cleanup_expired(self) -> int:
        """
        Clean up expired pending approvals.

        Iterate in sorted order.

        Returns:
            Number of approvals cleaned up
        """
        expired = []

        for request_id in sorted(self._pending.keys()):
            pending = self._pending[request_id]
            if pending.is_expired():
                expired.append(request_id)

        for request_id in expired:
            pending = self._pending.pop(request_id)
            if not pending.future.done():
                pending.future.set_result(False)

        return len(expired)


# Module-level singleton
_handler: Optional[TelegramApprovalHandler] = None


def get_telegram_approval_handler() -> TelegramApprovalHandler:
    """Get or create the Telegram approval handler singleton."""
    global _handler
    if _handler is None:
        _handler = TelegramApprovalHandler()
    return _handler


__all__ = [
    "TelegramApprovalHandler",
    "PendingApproval",
    "get_telegram_approval_handler",
    "APPROVAL_CALLBACK_PREFIX",
]
