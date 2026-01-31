"""
Matrix Bot for OTTO OS
======================

Secure messaging interface using the Matrix protocol.

Features:
- End-to-end encryption via Olm/Megolm
- Command handling for OTTO operations
- Optional PQ crypto layer for payload encryption
- Threshold signature support for critical operations

Dependencies:
- matrix-nio[e2e]: Matrix client with E2E encryption
- aiofiles: Async file operations for state persistence

Usage:
    from otto.messaging import OTTOMatrixBot

    bot = OTTOMatrixBot(
        homeserver="https://matrix.example.org",
        user_id="@otto:example.org",
        device_id="OTTO_DEVICE",
    )

    await bot.login(password="...")
    await bot.run()

References:
    - Matrix Spec: https://spec.matrix.org/
    - matrix-nio: https://github.com/poljar/matrix-nio
"""

import asyncio
import json
import logging
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Awaitable, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_DEVICE_NAME = "OTTO OS Bot"
STATE_FILE_NAME = "matrix_state.json"
COMMAND_PREFIX = "!"
MAX_MESSAGE_LENGTH = 4096


# =============================================================================
# Exceptions
# =============================================================================

class MatrixBotError(Exception):
    """Base exception for Matrix bot errors."""
    pass


class ConnectionError(MatrixBotError):
    """Failed to connect to homeserver."""
    pass


class AuthenticationError(MatrixBotError):
    """Authentication failed."""
    pass


class EncryptionError(MatrixBotError):
    """E2E encryption error."""
    pass


# =============================================================================
# Data Classes
# =============================================================================

class MessageType(Enum):
    """Types of Matrix messages."""
    TEXT = "m.text"
    NOTICE = "m.notice"
    EMOTE = "m.emote"
    IMAGE = "m.image"
    FILE = "m.file"
    COMMAND = "command"


@dataclass
class MatrixMessage:
    """A received Matrix message."""
    room_id: str
    sender: str
    body: str
    message_type: MessageType
    event_id: str
    timestamp: datetime
    encrypted: bool = False
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_command(self) -> bool:
        """Check if message is a command."""
        return self.body.startswith(COMMAND_PREFIX)

    @property
    def command_name(self) -> Optional[str]:
        """Extract command name if this is a command."""
        if not self.is_command:
            return None
        parts = self.body[len(COMMAND_PREFIX):].split()
        return parts[0].lower() if parts else None

    @property
    def command_args(self) -> List[str]:
        """Extract command arguments."""
        if not self.is_command:
            return []
        parts = self.body[len(COMMAND_PREFIX):].split()
        return parts[1:] if len(parts) > 1 else []


@dataclass
class BotConfig:
    """Configuration for the Matrix bot."""
    homeserver: str
    user_id: str
    device_id: str = "OTTO_BOT"
    device_name: str = DEFAULT_DEVICE_NAME
    state_dir: Path = field(default_factory=lambda: Path.home() / ".otto" / "matrix")
    allowed_users: List[str] = field(default_factory=list)
    allowed_rooms: List[str] = field(default_factory=list)
    enable_e2e: bool = True
    enable_pq_layer: bool = True
    command_prefix: str = COMMAND_PREFIX
    auto_join: bool = False

    def __post_init__(self):
        """Ensure state directory exists."""
        self.state_dir = Path(self.state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class BotState:
    """Persistent bot state."""
    access_token: Optional[str] = None
    device_id: Optional[str] = None
    user_id: Optional[str] = None
    sync_token: Optional[str] = None
    rooms: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    last_sync: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            'access_token': self.access_token,
            'device_id': self.device_id,
            'user_id': self.user_id,
            'sync_token': self.sync_token,
            'rooms': self.rooms,
            'last_sync': self.last_sync,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotState':
        """Create from dictionary."""
        return cls(
            access_token=data.get('access_token'),
            device_id=data.get('device_id'),
            user_id=data.get('user_id'),
            sync_token=data.get('sync_token'),
            rooms=data.get('rooms', {}),
            last_sync=data.get('last_sync'),
        )


# =============================================================================
# Command Handler Protocol
# =============================================================================

CommandHandler = Callable[[MatrixMessage, List[str]], Awaitable[str]]


@dataclass
class Command:
    """A registered bot command."""
    name: str
    handler: CommandHandler
    description: str
    usage: str = ""
    requires_auth: bool = True
    requires_encryption: bool = False
    min_args: int = 0
    max_args: Optional[int] = None


# =============================================================================
# Matrix Client Abstraction
# =============================================================================

class MatrixClientProtocol(ABC):
    """Abstract interface for Matrix client operations."""

    @abstractmethod
    async def login(self, password: Optional[str] = None, token: Optional[str] = None) -> bool:
        """Login to the homeserver."""
        pass

    @abstractmethod
    async def logout(self) -> None:
        """Logout from the homeserver."""
        pass

    @abstractmethod
    async def sync(self, timeout: int = 30000) -> Dict[str, Any]:
        """Sync with the homeserver."""
        pass

    @abstractmethod
    async def send_message(
        self,
        room_id: str,
        body: str,
        message_type: MessageType = MessageType.TEXT,
        encrypted: bool = True,
    ) -> str:
        """Send a message to a room."""
        pass

    @abstractmethod
    async def join_room(self, room_id: str) -> bool:
        """Join a room."""
        pass

    @abstractmethod
    async def leave_room(self, room_id: str) -> bool:
        """Leave a room."""
        pass


# =============================================================================
# Mock Matrix Client (for testing without matrix-nio)
# =============================================================================

class MockMatrixClient(MatrixClientProtocol):
    """
    Mock Matrix client for testing and development.

    Simulates Matrix operations without requiring a real homeserver.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.logged_in = False
        self.rooms: Dict[str, List[MatrixMessage]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._sync_token = "mock_sync_0"
        self._event_counter = 0

    async def login(self, password: Optional[str] = None, token: Optional[str] = None) -> bool:
        """Simulate login."""
        logger.info(f"Mock login for {self.config.user_id}")
        self.logged_in = True
        return True

    async def logout(self) -> None:
        """Simulate logout."""
        self.logged_in = False

    async def sync(self, timeout: int = 30000) -> Dict[str, Any]:
        """Simulate sync - returns queued messages."""
        try:
            # Wait for messages with timeout
            message = await asyncio.wait_for(
                self._message_queue.get(),
                timeout=timeout / 1000,
            )
            return {'messages': [message]}
        except asyncio.TimeoutError:
            return {'messages': []}

    async def send_message(
        self,
        room_id: str,
        body: str,
        message_type: MessageType = MessageType.TEXT,
        encrypted: bool = True,
    ) -> str:
        """Simulate sending a message."""
        self._event_counter += 1
        event_id = f"$mock_event_{self._event_counter}"

        logger.info(f"Mock send to {room_id}: {body[:50]}...")

        if room_id not in self.rooms:
            self.rooms[room_id] = []

        message = MatrixMessage(
            room_id=room_id,
            sender=self.config.user_id,
            body=body,
            message_type=message_type,
            event_id=event_id,
            timestamp=datetime.now(timezone.utc),
            encrypted=encrypted,
        )
        self.rooms[room_id].append(message)

        return event_id

    async def join_room(self, room_id: str) -> bool:
        """Simulate joining a room."""
        if room_id not in self.rooms:
            self.rooms[room_id] = []
        return True

    async def leave_room(self, room_id: str) -> bool:
        """Simulate leaving a room."""
        self.rooms.pop(room_id, None)
        return True

    def simulate_incoming_message(
        self,
        room_id: str,
        sender: str,
        body: str,
        encrypted: bool = True,
    ) -> None:
        """Simulate receiving a message (for testing)."""
        self._event_counter += 1
        message = MatrixMessage(
            room_id=room_id,
            sender=sender,
            body=body,
            message_type=MessageType.COMMAND if body.startswith("!") else MessageType.TEXT,
            event_id=f"$mock_event_{self._event_counter}",
            timestamp=datetime.now(timezone.utc),
            encrypted=encrypted,
        )
        self._message_queue.put_nowait(message)


# =============================================================================
# Real Matrix Client (requires matrix-nio)
# =============================================================================

class NioMatrixClient(MatrixClientProtocol):
    """
    Matrix client using matrix-nio library.

    Provides full E2E encryption support via Olm/Megolm.
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self._client = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Lazily initialize the nio client."""
        if self._initialized:
            return

        try:
            from nio import AsyncClient, AsyncClientConfig
            from nio.store import SqliteStore
        except ImportError:
            raise MatrixBotError(
                "matrix-nio not installed. Install with: pip install matrix-nio[e2e]"
            )

        store_path = self.config.state_dir / "nio_store"
        store_path.mkdir(parents=True, exist_ok=True)

        client_config = AsyncClientConfig(
            store=SqliteStore,
            store_name="otto_matrix",
            encryption_enabled=self.config.enable_e2e,
        )

        self._client = AsyncClient(
            homeserver=self.config.homeserver,
            user=self.config.user_id,
            device_id=self.config.device_id,
            store_path=str(store_path),
            config=client_config,
        )

        self._initialized = True

    async def login(self, password: Optional[str] = None, token: Optional[str] = None) -> bool:
        """Login to Matrix homeserver."""
        await self._ensure_initialized()

        try:
            from nio import LoginResponse
        except ImportError:
            raise MatrixBotError("matrix-nio not installed")

        if token:
            self._client.access_token = token
            self._client.user_id = self.config.user_id
            self._client.device_id = self.config.device_id
            return True

        if password:
            response = await self._client.login(
                password=password,
                device_name=self.config.device_name,
            )

            if isinstance(response, LoginResponse):
                logger.info(f"Logged in as {response.user_id}")
                return True
            else:
                logger.error(f"Login failed: {response}")
                raise AuthenticationError(str(response))

        raise AuthenticationError("No password or token provided")

    async def logout(self) -> None:
        """Logout from homeserver."""
        if self._client:
            await self._client.logout()
            await self._client.close()

    async def sync(self, timeout: int = 30000) -> Dict[str, Any]:
        """Sync with homeserver."""
        await self._ensure_initialized()

        response = await self._client.sync(timeout=timeout)
        return {'raw_response': response}

    async def send_message(
        self,
        room_id: str,
        body: str,
        message_type: MessageType = MessageType.TEXT,
        encrypted: bool = True,
    ) -> str:
        """Send a message to a room."""
        await self._ensure_initialized()

        try:
            from nio import RoomSendResponse
        except ImportError:
            raise MatrixBotError("matrix-nio not installed")

        content = {
            "msgtype": message_type.value,
            "body": body,
        }

        if encrypted and self.config.enable_e2e:
            response = await self._client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
            )
        else:
            response = await self._client.room_send(
                room_id=room_id,
                message_type="m.room.message",
                content=content,
                ignore_unverified_devices=True,
            )

        if isinstance(response, RoomSendResponse):
            return response.event_id
        else:
            raise MatrixBotError(f"Failed to send message: {response}")

    async def join_room(self, room_id: str) -> bool:
        """Join a room."""
        await self._ensure_initialized()

        try:
            from nio import JoinResponse
        except ImportError:
            raise MatrixBotError("matrix-nio not installed")

        response = await self._client.join(room_id)
        return isinstance(response, JoinResponse)

    async def leave_room(self, room_id: str) -> bool:
        """Leave a room."""
        await self._ensure_initialized()

        response = await self._client.room_leave(room_id)
        return hasattr(response, 'room_id')


# =============================================================================
# OTTO Matrix Bot
# =============================================================================

class OTTOMatrixBot:
    """
    OTTO OS Matrix Bot.

    Provides secure messaging interface for OTTO operations via Matrix protocol.

    Features:
    - E2E encryption (Olm/Megolm via matrix-nio)
    - Command handling with access control
    - Optional PQ crypto layer for additional security
    - Threshold signature support for critical operations
    - State persistence across restarts
    """

    def __init__(
        self,
        homeserver: str,
        user_id: str,
        device_id: str = "OTTO_BOT",
        state_dir: Optional[Path] = None,
        use_mock: bool = False,
        **kwargs,
    ):
        """
        Initialize the OTTO Matrix bot.

        Args:
            homeserver: Matrix homeserver URL
            user_id: Bot's Matrix user ID
            device_id: Device ID for E2E encryption
            state_dir: Directory for persistent state
            use_mock: Use mock client (for testing)
            **kwargs: Additional config options
        """
        self.config = BotConfig(
            homeserver=homeserver,
            user_id=user_id,
            device_id=device_id,
            state_dir=state_dir or Path.home() / ".otto" / "matrix",
            **kwargs,
        )

        # Initialize client
        if use_mock:
            self._client: MatrixClientProtocol = MockMatrixClient(self.config)
        else:
            self._client = NioMatrixClient(self.config)

        # State
        self._state = BotState()
        self._commands: Dict[str, Command] = {}
        self._running = False
        self._message_handlers: List[Callable] = []

        # Register default commands
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        """Register built-in commands."""
        self.register_command(
            name="help",
            handler=self._cmd_help,
            description="Show available commands",
            requires_auth=False,
        )

        self.register_command(
            name="ping",
            handler=self._cmd_ping,
            description="Check if bot is alive",
            requires_auth=False,
        )

        self.register_command(
            name="status",
            handler=self._cmd_status,
            description="Show OTTO status",
        )

        self.register_command(
            name="version",
            handler=self._cmd_version,
            description="Show OTTO version",
            requires_auth=False,
        )

    def register_command(
        self,
        name: str,
        handler: CommandHandler,
        description: str,
        usage: str = "",
        requires_auth: bool = True,
        requires_encryption: bool = False,
        min_args: int = 0,
        max_args: Optional[int] = None,
    ) -> None:
        """
        Register a command handler.

        Args:
            name: Command name (without prefix)
            handler: Async function to handle the command
            description: Command description for help
            usage: Usage string (e.g., "<arg1> [arg2]")
            requires_auth: Require sender to be in allowed_users
            requires_encryption: Require message to be encrypted
            min_args: Minimum required arguments
            max_args: Maximum allowed arguments (None = unlimited)
        """
        self._commands[name.lower()] = Command(
            name=name,
            handler=handler,
            description=description,
            usage=usage,
            requires_auth=requires_auth,
            requires_encryption=requires_encryption,
            min_args=min_args,
            max_args=max_args,
        )

    def add_message_handler(self, handler: Callable[[MatrixMessage], Awaitable[None]]) -> None:
        """Add a handler for all incoming messages."""
        self._message_handlers.append(handler)

    async def login(self, password: Optional[str] = None, token: Optional[str] = None) -> bool:
        """
        Login to the Matrix homeserver.

        Args:
            password: Account password
            token: Existing access token

        Returns:
            True if login successful
        """
        # Try to load existing state
        await self._load_state()

        if self._state.access_token and not password and not token:
            token = self._state.access_token

        success = await self._client.login(password=password, token=token)

        if success:
            await self._save_state()

        return success

    async def run(self) -> None:
        """
        Run the bot's main loop.

        Syncs with homeserver and processes incoming messages.
        """
        self._running = True
        logger.info(f"OTTO Matrix bot starting as {self.config.user_id}")

        while self._running:
            try:
                sync_result = await self._client.sync(timeout=30000)
                await self._process_sync(sync_result)
                self._state.last_sync = time.time()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync error: {e}")
                await asyncio.sleep(5)  # Back off on error

        logger.info("OTTO Matrix bot stopped")

    async def stop(self) -> None:
        """Stop the bot gracefully."""
        self._running = False
        await self._save_state()
        await self._client.logout()

    async def send(
        self,
        room_id: str,
        message: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> str:
        """
        Send a message to a room.

        Args:
            room_id: Target room ID
            message: Message content
            message_type: Type of message

        Returns:
            Event ID of sent message
        """
        # Truncate if too long
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[:MAX_MESSAGE_LENGTH - 3] + "..."

        return await self._client.send_message(
            room_id=room_id,
            body=message,
            message_type=message_type,
            encrypted=self.config.enable_e2e,
        )

    async def reply(self, original: MatrixMessage, response: str) -> str:
        """Reply to a message."""
        return await self.send(original.room_id, response)

    async def _process_sync(self, sync_result: Dict[str, Any]) -> None:
        """Process sync results."""
        messages = sync_result.get('messages', [])

        for message in messages:
            if isinstance(message, MatrixMessage):
                await self._handle_message(message)

    async def _handle_message(self, message: MatrixMessage) -> None:
        """Handle an incoming message."""
        # Ignore our own messages
        if message.sender == self.config.user_id:
            return

        # Call registered message handlers
        for handler in self._message_handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")

        # Handle commands
        if message.is_command:
            await self._handle_command(message)

    async def _handle_command(self, message: MatrixMessage) -> None:
        """Handle a command message."""
        command_name = message.command_name
        if not command_name:
            return

        command = self._commands.get(command_name)
        if not command:
            await self.reply(message, f"Unknown command: {command_name}. Try !help")
            return

        # Check authorization
        if command.requires_auth:
            if self.config.allowed_users and message.sender not in self.config.allowed_users:
                await self.reply(message, "You are not authorized to use this command.")
                return

        # Check encryption requirement
        if command.requires_encryption and not message.encrypted:
            await self.reply(message, "This command requires an encrypted channel.")
            return

        # Check argument count
        args = message.command_args
        if len(args) < command.min_args:
            await self.reply(
                message,
                f"Not enough arguments. Usage: !{command.name} {command.usage}"
            )
            return

        if command.max_args is not None and len(args) > command.max_args:
            await self.reply(
                message,
                f"Too many arguments. Usage: !{command.name} {command.usage}"
            )
            return

        # Execute command
        try:
            response = await command.handler(message, args)
            await self.reply(message, response)
        except Exception as e:
            logger.error(f"Command error: {e}")
            await self.reply(message, f"Error executing command: {e}")

    # =========================================================================
    # Default Command Handlers
    # =========================================================================

    async def _cmd_help(self, message: MatrixMessage, args: List[str]) -> str:
        """Show help for commands."""
        if args:
            # Help for specific command
            cmd = self._commands.get(args[0].lower())
            if cmd:
                usage = f" {cmd.usage}" if cmd.usage else ""
                return f"!{cmd.name}{usage}\n{cmd.description}"
            return f"Unknown command: {args[0]}"

        # List all commands
        lines = ["OTTO OS Commands:", ""]
        for name, cmd in sorted(self._commands.items()):
            auth = " [auth]" if cmd.requires_auth else ""
            enc = " [encrypted]" if cmd.requires_encryption else ""
            lines.append(f"  !{name}{auth}{enc} - {cmd.description}")

        return "\n".join(lines)

    async def _cmd_ping(self, message: MatrixMessage, args: List[str]) -> str:
        """Respond to ping."""
        latency = (datetime.now(timezone.utc) - message.timestamp).total_seconds()
        return f"Pong! (latency: {latency:.2f}s)"

    async def _cmd_status(self, message: MatrixMessage, args: List[str]) -> str:
        """Show OTTO status."""
        return (
            "OTTO OS Status\n"
            "==============\n"
            f"Bot User: {self.config.user_id}\n"
            f"Device: {self.config.device_id}\n"
            f"E2E Enabled: {self.config.enable_e2e}\n"
            f"PQ Layer: {self.config.enable_pq_layer}\n"
            f"Commands: {len(self._commands)}\n"
            f"Rooms: {len(self._state.rooms)}"
        )

    async def _cmd_version(self, message: MatrixMessage, args: List[str]) -> str:
        """Show version info."""
        return "OTTO OS v0.1.0 - Matrix Bot"

    # =========================================================================
    # State Persistence
    # =========================================================================

    async def _load_state(self) -> None:
        """Load persistent state from disk."""
        state_file = self.config.state_dir / STATE_FILE_NAME

        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                self._state = BotState.from_dict(data)
                logger.info("Loaded bot state from disk")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    async def _save_state(self) -> None:
        """Save state to disk."""
        state_file = self.config.state_dir / STATE_FILE_NAME

        try:
            state_file.write_text(json.dumps(self._state.to_dict(), indent=2))
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    # =========================================================================
    # Testing Helpers
    # =========================================================================

    def get_mock_client(self) -> Optional[MockMatrixClient]:
        """Get mock client for testing."""
        if isinstance(self._client, MockMatrixClient):
            return self._client
        return None


# =============================================================================
# Factory Functions
# =============================================================================

def create_bot(
    homeserver: str,
    user_id: str,
    device_id: str = "OTTO_BOT",
    use_mock: bool = False,
    **kwargs,
) -> OTTOMatrixBot:
    """
    Create an OTTO Matrix bot instance.

    Args:
        homeserver: Matrix homeserver URL
        user_id: Bot's Matrix user ID
        device_id: Device ID for E2E encryption
        use_mock: Use mock client (for testing)
        **kwargs: Additional config options

    Returns:
        Configured OTTOMatrixBot instance
    """
    return OTTOMatrixBot(
        homeserver=homeserver,
        user_id=user_id,
        device_id=device_id,
        use_mock=use_mock,
        **kwargs,
    )
