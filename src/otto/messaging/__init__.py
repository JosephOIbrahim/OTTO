"""
OTTO OS Messaging Module
========================

Secure mobile messaging for OTTO OS via Matrix protocol.

Features:
- Matrix bot with E2E encryption (Olm/Megolm)
- Additional PQ crypto layer (X25519 + ML-KEM-768)
- Threshold signature support for critical operations
- Command handling for OTTO operations

Components:
- matrix_bot: Core Matrix client and bot logic
- secure_channel: PQ crypto overlay
- commands: OTTO-specific command handlers

Quick Start:
    from otto.messaging import create_bot, register_otto_commands

    # Create bot
    bot = create_bot(
        homeserver="https://matrix.example.org",
        user_id="@otto:example.org",
    )

    # Register OTTO commands
    register_otto_commands(bot)

    # Login and run
    await bot.login(password="...")
    await bot.run()

Dependencies:
- matrix-nio[e2e]: For Matrix protocol support (optional, has mock)
- otto.crypto: For PQ cryptography

Security Model:
- Layer 1: Matrix Olm/Megolm (E2E encryption)
- Layer 2: OTTO PQ crypto (quantum-resistant payload encryption)
- Layer 3: Threshold signatures (N-of-M approval for critical ops)
"""

from .matrix_bot import (
    # Core bot
    OTTOMatrixBot,
    create_bot,
    # Config
    BotConfig,
    BotState,
    # Messages
    MatrixMessage,
    MessageType,
    # Commands
    Command,
    CommandHandler,
    # Clients
    MatrixClientProtocol,
    MockMatrixClient,
    NioMatrixClient,
    # Exceptions
    MatrixBotError,
    ConnectionError,
    AuthenticationError,
    EncryptionError,
)

from .secure_channel import (
    # Core
    SecureChannel,
    ThresholdSecureChannel,
    create_secure_channel,
    # Data types
    SecurePayload,
    KeyExchangeMessage,
    ChannelState,
    ChannelInfo,
    # Exceptions
    SecureChannelError,
    KeyExchangeError,
    DecryptionError,
    SignatureError,
    ReplayError,
)

from .commands import (
    OTTOCommands,
    register_otto_commands,
    otto_command,
)

__all__ = [
    # Matrix Bot
    "OTTOMatrixBot",
    "create_bot",
    "BotConfig",
    "BotState",
    "MatrixMessage",
    "MessageType",
    "Command",
    "CommandHandler",
    "MatrixClientProtocol",
    "MockMatrixClient",
    "NioMatrixClient",
    "MatrixBotError",
    "ConnectionError",
    "AuthenticationError",
    "EncryptionError",
    # Secure Channel
    "SecureChannel",
    "ThresholdSecureChannel",
    "create_secure_channel",
    "SecurePayload",
    "KeyExchangeMessage",
    "ChannelState",
    "ChannelInfo",
    "SecureChannelError",
    "KeyExchangeError",
    "DecryptionError",
    "SignatureError",
    "ReplayError",
    # Commands
    "OTTOCommands",
    "register_otto_commands",
    "otto_command",
]
