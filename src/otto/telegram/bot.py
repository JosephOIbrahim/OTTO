"""
OTTO Telegram Bot
=================

Telegram bot runner using python-telegram-bot library.

[He2025] Compliance:
- Deterministic message processing order
- Fixed evaluation sequence in handlers
- Session state managed by TelegramAdapter

Requirements:
    pip install python-telegram-bot>=20.0

Environment:
    TELEGRAM_BOT_TOKEN: Your bot token from @BotFather

Usage:
    from otto.telegram import create_bot

    bot = create_bot()
    bot.run()
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Final, Optional

from .adapter import TelegramAdapter, TelegramMessage, TelegramResponse
from .approval import TelegramApprovalHandler, get_telegram_approval_handler
from .services import TelegramServiceRouter, get_service_router

logger = logging.getLogger(__name__)

# Check for telegram library
try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CallbackQueryHandler,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning(
        "python-telegram-bot not installed. "
        "Install with: pip install python-telegram-bot>=20.0"
    )


# [He2025] Fixed constants
_DEFAULT_SESSION_PATH: Final[str] = "data/telegram_sessions.json"
_CLEANUP_INTERVAL_SECONDS: Final[int] = 3600  # 1 hour


class OTTOTelegramBot:
    """
    Telegram bot for OTTO cognitive support.

    [He2025] Compliance:
    - Fixed handler registration order
    - Deterministic message processing
    - Session cleanup on fixed interval

    Usage:
        bot = OTTOTelegramBot(token="YOUR_BOT_TOKEN")
        bot.run()
    """

    def __init__(
        self,
        token: str,
        adapter: Optional[TelegramAdapter] = None,
        session_path: Optional[Path] = None,
    ):
        """
        Initialize the Telegram bot.

        Args:
            token: Telegram bot token from @BotFather
            adapter: TelegramAdapter instance (creates default if None)
            session_path: Path to session storage
        """
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "python-telegram-bot is required. "
                "Install with: pip install python-telegram-bot>=20.0"
            )

        self.token = token
        self.session_path = session_path or Path(_DEFAULT_SESSION_PATH)

        # Ensure session directory exists
        self.session_path.parent.mkdir(parents=True, exist_ok=True)

        # Create adapter with session persistence
        self.adapter = adapter or TelegramAdapter(
            session_store_path=self.session_path
        )

        # Approval handler for inline button approvals
        self._approval_handler = get_telegram_approval_handler()

        # Service router for MCP integration
        self._service_router = get_service_router()

        # Application will be created on run()
        self._application: Optional[Application] = None
        self._running = False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        message = self._to_telegram_message(update)
        response = self.adapter.process_message(message)
        await self._send_response(update, response)

    async def help_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /help command."""
        message = self._to_telegram_message(update)
        response = self.adapter.process_message(message)
        await self._send_response(update, response)

    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /status command."""
        message = self._to_telegram_message(update)
        response = self.adapter.process_message(message)
        await self._send_response(update, response)

    async def reset_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /reset command."""
        message = self._to_telegram_message(update)
        response = self.adapter.process_message(message)
        await self._send_response(update, response)

    async def calibrate_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /calibrate command."""
        message = self._to_telegram_message(update)
        response = self.adapter.process_message(message)
        await self._send_response(update, response)

    async def approve_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /approve command - show pending approvals and stats.

        [He2025] Fixed output format.
        """
        from ..services.approval import get_approval_gate

        gate = get_approval_gate()
        stats = gate.get_stats()
        pending = gate.get_pending()

        lines = ["*Approval Status*\n"]

        # Stats
        lines.append(f"*Total requests:* {stats['total_requests']}")
        lines.append(f"*Approved:* {stats['approved']}")
        lines.append(f"*Denied:* {stats['denied']}")
        if stats['total_requests'] > 0:
            rate = stats['approval_rate'] * 100
            lines.append(f"*Approval rate:* {rate:.1f}%")

        # Pending
        lines.append(f"\n*Pending:* {len(pending)}")
        if pending:
            for req in pending[:5]:  # Show max 5
                lines.append(f"  • {req.action} ({req.actor})")

        # Trust-based auto-approvals
        lines.append(f"\n*Trusted actions:* {stats['trust_records']}")

        text = "\n".join(lines)

        try:
            await update.message.reply_text(
                text=text,
                parse_mode="Markdown",
            )
        except Exception:
            await update.message.reply_text(text=text)

    async def services_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /services command - list available MCP services.

        [He2025] Fixed output format.
        """
        services = self._service_router.list_services()

        lines = ["*Available Services*\n"]
        for service in services:
            lines.append(f"• /{service} - {service.title()} operations")

        lines.append("\n*Usage:*")
        lines.append("/calendar today - Today's events")
        lines.append("/tasks list - List tasks")
        lines.append("/email inbox - Check inbox")

        text = "\n".join(lines)

        try:
            await update.message.reply_text(
                text=text,
                parse_mode="Markdown",
            )
        except Exception:
            await update.message.reply_text(text=text)

    async def service_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle service commands (/calendar, /tasks, /email, /notion).

        Routes to MCP services via TelegramServiceRouter.
        """
        if not update.message or not update.message.text:
            return

        text = update.message.text
        chat_id = update.message.chat_id

        # Route to service
        response = await self._service_router.route(text, chat_id=chat_id)

        try:
            await update.message.reply_text(
                text=response.text,
                parse_mode="Markdown",
            )
        except Exception:
            # Fallback without markdown
            await update.message.reply_text(text=response.text)

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle incoming text messages.

        [He2025] Processing order:
        1. Convert to normalized message
        2. Process through adapter (-> orchestrator)
        3. Send response
        """
        if not update.message or not update.message.text:
            return

        message = self._to_telegram_message(update)
        response = self.adapter.process_message(message)
        await self._send_response(update, response)

    async def handle_callback_query(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle callback queries from inline buttons.

        [He2025] Fixed processing order:
        1. Check if approval callback
        2. Delegate to approval handler
        3. Log result
        """
        query = update.callback_query

        if not query or not query.data:
            return

        # Check if this is an approval callback
        if self._approval_handler.is_approval_callback(query.data):
            handled = await self._approval_handler.handle_callback(query, context)
            if handled:
                logger.debug(f"Approval callback handled: {query.data}")
            return

        # Unknown callback - answer to prevent loading state
        try:
            await query.answer("Unknown action")
        except Exception as e:
            logger.debug(f"Could not answer callback: {e}")

    async def error_handler(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle errors in message processing."""
        logger.exception(f"Exception while handling update: {context.error}")

        if isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Something went wrong. Please try again.",
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    def _to_telegram_message(self, update: Update) -> TelegramMessage:
        """Convert Telegram Update to normalized TelegramMessage."""
        msg = update.message

        reply_to_id = None
        if msg.reply_to_message:
            reply_to_id = msg.reply_to_message.message_id

        return TelegramMessage(
            message_id=msg.message_id,
            user_id=msg.from_user.id,
            chat_id=msg.chat_id,
            text=msg.text or "",
            timestamp=msg.date.timestamp(),
            reply_to_message_id=reply_to_id,
        )

    async def _send_response(
        self,
        update: Update,
        response: TelegramResponse
    ) -> None:
        """Send response back to Telegram."""
        # Truncate if needed
        response = response.truncate()

        try:
            await update.message.reply_text(
                text=response.text,
                parse_mode=response.parse_mode,
            )
        except Exception as e:
            logger.error(f"Failed to send response: {e}")
            # Try without parse mode (in case of markdown issues)
            try:
                await update.message.reply_text(text=response.text)
            except Exception as e2:
                logger.error(f"Failed to send plain text: {e2}")

    async def _cleanup_sessions_periodic(self) -> None:
        """Periodically clean up expired sessions."""
        while self._running:
            await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
            if self._running:
                self.adapter.cleanup_expired_sessions()

    def run(self, webhook_url: Optional[str] = None) -> None:
        """
        Run the bot.

        Args:
            webhook_url: If provided, use webhook mode instead of polling
        """
        logger.info("Starting OTTO Telegram bot...")

        # Build application
        self._application = (
            Application.builder()
            .token(self.token)
            .build()
        )

        # Wire up approval handler to send messages via bot
        async def send_approval_message(chat_id, text, reply_markup, parse_mode="Markdown"):
            return await self._application.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        self._approval_handler.set_send_message(send_approval_message)

        # [He2025] Fixed handler registration order
        # 1. Command handlers (highest priority)
        self._application.add_handler(CommandHandler("start", self.start))
        self._application.add_handler(CommandHandler("help", self.help_command))
        self._application.add_handler(CommandHandler("status", self.status_command))
        self._application.add_handler(CommandHandler("reset", self.reset_command))
        self._application.add_handler(CommandHandler("calibrate", self.calibrate_command))
        self._application.add_handler(CommandHandler("approve", self.approve_command))
        self._application.add_handler(CommandHandler("services", self.services_command))

        # Service commands (route to MCP)
        self._application.add_handler(CommandHandler("calendar", self.service_command))
        self._application.add_handler(CommandHandler("tasks", self.service_command))
        self._application.add_handler(CommandHandler("email", self.service_command))
        self._application.add_handler(CommandHandler("notion", self.service_command))

        # 2. Callback query handler (for inline buttons)
        self._application.add_handler(CallbackQueryHandler(self.handle_callback_query))

        # 3. Message handler (catch-all for text)
        self._application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )

        # 4. Error handler
        self._application.add_error_handler(self.error_handler)

        self._running = True

        if webhook_url:
            # Webhook mode (for production)
            logger.info(f"Running in webhook mode: {webhook_url}")
            self._application.run_webhook(
                listen="0.0.0.0",
                port=int(os.environ.get("PORT", 8443)),
                webhook_url=webhook_url,
            )
        else:
            # Polling mode (for development)
            logger.info("Running in polling mode")
            self._application.run_polling(allowed_updates=Update.ALL_TYPES)

        self._running = False
        logger.info("OTTO Telegram bot stopped")

    def stop(self) -> None:
        """Stop the bot gracefully."""
        self._running = False
        if self._application:
            self._application.stop()


def create_bot(
    token: Optional[str] = None,
    session_path: Optional[Path] = None,
) -> OTTOTelegramBot:
    """
    Create and configure a Telegram bot instance.

    Args:
        token: Bot token (defaults to TELEGRAM_BOT_TOKEN env var)
        session_path: Path to session storage

    Returns:
        Configured OTTOTelegramBot instance

    Raises:
        ValueError: If no token provided and TELEGRAM_BOT_TOKEN not set
    """
    bot_token = token or os.environ.get("TELEGRAM_BOT_TOKEN")

    if not bot_token:
        raise ValueError(
            "No Telegram bot token provided. "
            "Set TELEGRAM_BOT_TOKEN environment variable or pass token directly."
        )

    return OTTOTelegramBot(token=bot_token, session_path=session_path)


def main() -> None:
    """Entry point for running the bot directly."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    try:
        bot = create_bot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


__all__ = [
    "OTTOTelegramBot",
    "create_bot",
    "TELEGRAM_AVAILABLE",
]
