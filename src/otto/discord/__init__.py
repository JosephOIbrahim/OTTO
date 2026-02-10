"""
OTTO OS Discord Integration
===========================

Discord bot adapter for OTTO cognitive system.

Determinism:
- Deterministic session state per user_id
- Fixed evaluation order in message processing
- Sorted key iteration for session management
"""

from .adapter import DiscordAdapter, DiscordSession, DiscordMessage, DiscordResponse
from .bot import OTTODiscordBot, create_bot, DISCORD_AVAILABLE

__all__ = [
    "DiscordAdapter",
    "DiscordSession",
    "DiscordMessage",
    "DiscordResponse",
    "OTTODiscordBot",
    "create_bot",
    "DISCORD_AVAILABLE",
]
