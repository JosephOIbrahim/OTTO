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
from .bot import OTTOTelegramBot, create_bot

__all__ = [
    "TelegramAdapter",
    "TelegramSession",
    "OTTOTelegramBot",
    "create_bot",
]
