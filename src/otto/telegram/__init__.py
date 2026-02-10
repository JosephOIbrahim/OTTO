"""
OTTO OS Telegram Integration
============================

Telegram bot adapter for OTTO cognitive system.

Determinism:
- Deterministic session state per user_id
- Fixed evaluation order in message processing
- Sorted key iteration for session management
"""

from .adapter import TelegramAdapter, TelegramSession
from .approval import TelegramApprovalHandler, get_telegram_approval_handler
from .bot import OTTOTelegramBot, create_bot
from .services import TelegramServiceRouter, get_service_router

__all__ = [
    "TelegramAdapter",
    "TelegramSession",
    "TelegramApprovalHandler",
    "get_telegram_approval_handler",
    "TelegramServiceRouter",
    "get_service_router",
    "OTTOTelegramBot",
    "create_bot",
]
