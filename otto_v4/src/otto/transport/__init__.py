"""Pluggable transport layer for OTTO v5.0.

Transports handle the "how" of message delivery — CLI, WhatsApp,
Telegram, etc. The core engine handles the "what."
"""

from .base import Transport
from .cli_transport import CliTransport

__all__ = ["Transport", "CliTransport"]
