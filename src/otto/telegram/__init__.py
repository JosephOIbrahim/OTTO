"""
OTTO OS Telegram Integration
============================

Telegram bot adapter for OTTO cognitive system.

[He2025] Compliance:
- Deterministic session state per user_id
- Fixed evaluation order in message processing
- Sorted key iteration for session management
"""

from .adapter import TelegramAdapter, TelegramSession
from .approval import TelegramApprovalHandler, get_telegram_approval_handler
from .bot import OTTOTelegramBot, create_bot

__all__ = [
    "TelegramAdapter",
    "TelegramSession",
    "TelegramApprovalHandler",
    "get_telegram_approval_handler",
    "OTTOTelegramBot",
    "create_bot",
]
