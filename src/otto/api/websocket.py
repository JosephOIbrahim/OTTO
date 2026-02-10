"""
OTTO WebSocket API
==================

Real-time bidirectional communication for mobile clients.

Features:
- Live state updates (push, not poll)
- Command acknowledgments
- Burnout/energy alerts
- Project status changes

Protocol:
    Client → Server: JSON messages
    Server → Client: JSON messages

Message Types:
    subscribe     - Subscribe to channels
    unsubscribe   - Unsubscribe from channels
    command       - Execute command
    ping          - Keep-alive

    state_update  - Cognitive state changed
    alert         - Burnout/energy warning
    ack           - Command acknowledgment
    error         - Error message
    pong          - Keep-alive response

Determinism:
- FIXED message format
- DETERMINISTIC: message type → handler mapping
"""

import asyncio
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from weakref import WeakSet

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class MessageType(Enum):
    """WebSocket message types."""
    # Client → Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    COMMAND = "command"
    PING = "ping"
    AUTH = "auth"

    # Server → Client
    STATE_UPDATE = "state_update"
    ALERT = "alert"
    ACK = "ack"
    ERROR = "error"
    PONG = "pong"
    WELCOME = "welcome"


class Channel(Enum):
    """Subscription channels."""
    STATE = "state"           # Cognitive state updates
    PROJECTS = "projects"     # Project changes
    SECURITY = "security"     # Security posture changes
    ALERTS = "alerts"         # Burnout/energy alerts
    COMMANDS = "commands"     # Command results
    ALL = "all"               # All channels


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class WebSocketMessage:
    """WebSocket message structure."""
    type: MessageType
    channel: Optional[Channel] = None
    data: Optional[Dict[str, Any]] = None
    id: str = field(default_factory=lambda: secrets.token_hex(8))
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "channel": self.channel.value if self.channel else None,
            "data": self.data,
            "id": self.id,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebSocketMessage":
        """Create from dictionary."""
        msg_type = MessageType(data.get("type", "error"))
        channel = None
        if data.get("channel"):
            try:
                channel = Channel(data["channel"])
            except ValueError:
                pass

        return cls(
            type=msg_type,
            channel=channel,
            data=data.get("data"),
            id=data.get("id", secrets.token_hex(8)),
            timestamp=data.get("timestamp", time.time()),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """Parse from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class Alert:
    """Alert notification."""
    severity: AlertSeverity
    title: str
    message: str
    source: str
    timestamp: float = field(default_factory=time.time)
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp,
            "data": self.data,
        }


# =============================================================================
# WebSocket Connection
# =============================================================================

class WebSocketConnection:
    """
    Represents a single WebSocket connection.

    Manages:
    - Authentication state
    - Channel subscriptions
    - Message queue
    - Keep-alive
    """

    PING_INTERVAL = 30  # seconds
    PING_TIMEOUT = 10   # seconds

    def __init__(
        self,
        connection_id: str,
        send_callback: Callable[[str], None],
    ):
        self.connection_id = connection_id
        self.send_callback = send_callback
        self.subscriptions: Set[Channel] = set()
        self.authenticated = False
        self.user_id: Optional[str] = None
        self.device_id: Optional[str] = None
        self.connected_at = time.time()
        self.last_ping = time.time()
        self.last_pong = time.time()
        self._message_queue: asyncio.Queue = asyncio.Queue()

    async def send(self, message: WebSocketMessage) -> None:
        """Send a message to the client."""
        try:
            self.send_callback(message.to_json())
        except Exception as e:
            logger.error(f"Failed to send message to {self.connection_id}: {e}")

    async def send_json(self, data: Dict[str, Any]) -> None:
        """Send raw JSON data."""
        try:
            self.send_callback(json.dumps(data, sort_keys=True))
        except Exception as e:
            logger.error(f"Failed to send to {self.connection_id}: {e}")

    def subscribe(self, channel: Channel) -> None:
        """Subscribe to a channel."""
        if channel == Channel.ALL:
            self.subscriptions = set(Channel)
        else:
            self.subscriptions.add(channel)

    def unsubscribe(self, channel: Channel) -> None:
        """Unsubscribe from a channel."""
        if channel == Channel.ALL:
            self.subscriptions.clear()
        else:
            self.subscriptions.discard(channel)

    def is_subscribed(self, channel: Channel) -> bool:
        """Check if subscribed to a channel."""
        return channel in self.subscriptions or Channel.ALL in self.subscriptions


# =============================================================================
# WebSocket Hub
# =============================================================================

class WebSocketHub:
    """
    Central hub for managing WebSocket connections.

    Handles:
    - Connection registration/removal
    - Message routing
    - Channel broadcasts
    - State change notifications
    """

    def __init__(self):
        self._connections: Dict[str, WebSocketConnection] = {}
        self._user_connections: Dict[str, Set[str]] = {}  # user_id → connection_ids
        self._handlers: Dict[MessageType, Callable] = {}
        self._state_cache: Dict[str, Any] = {}
        self._setup_handlers()

    def _setup_handlers(self):
        """Register message handlers."""
        self._handlers = {
            MessageType.SUBSCRIBE: self._handle_subscribe,
            MessageType.UNSUBSCRIBE: self._handle_unsubscribe,
            MessageType.COMMAND: self._handle_command,
            MessageType.PING: self._handle_ping,
            MessageType.AUTH: self._handle_auth,
        }

    # =========================================================================
    # Connection Management
    # =========================================================================

    def register(
        self,
        connection_id: str,
        send_callback: Callable[[str], None],
    ) -> WebSocketConnection:
        """Register a new connection."""
        conn = WebSocketConnection(connection_id, send_callback)
        self._connections[connection_id] = conn

        logger.info(f"WebSocket connected: {connection_id}")

        # Send welcome message synchronously via callback
        # Direct callback avoids event loop dependency
        welcome_msg = WebSocketMessage(
            type=MessageType.WELCOME,
            data={
                "connection_id": connection_id,
                "server_time": time.time(),
                "channels": [c.value for c in Channel],
            },
        )
        try:
            send_callback(welcome_msg.to_json())
        except Exception as e:
            logger.warning(f"Failed to send welcome message: {e}")

        return conn

    def unregister(self, connection_id: str) -> None:
        """Remove a connection."""
        conn = self._connections.pop(connection_id, None)
        if conn:
            # Remove from user mapping
            if conn.user_id and conn.user_id in self._user_connections:
                self._user_connections[conn.user_id].discard(connection_id)

            logger.info(f"WebSocket disconnected: {connection_id}")

    def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """Get a connection by ID."""
        return self._connections.get(connection_id)

    @property
    def connection_count(self) -> int:
        """Number of active connections."""
        return len(self._connections)

    # =========================================================================
    # Message Handling
    # =========================================================================

    async def handle_message(
        self,
        connection_id: str,
        raw_message: str,
    ) -> None:
        """Handle an incoming message."""
        conn = self._connections.get(connection_id)
        if not conn:
            return

        try:
            message = WebSocketMessage.from_json(raw_message)
        except (json.JSONDecodeError, ValueError) as e:
            await conn.send(WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": f"Invalid message format: {e}"},
            ))
            return

        handler = self._handlers.get(message.type)
        if handler:
            await handler(conn, message)
        else:
            await conn.send(WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": f"Unknown message type: {message.type.value}"},
            ))

    async def _handle_subscribe(
        self,
        conn: WebSocketConnection,
        message: WebSocketMessage,
    ) -> None:
        """Handle subscription request."""
        channels = message.data.get("channels", []) if message.data else []

        for channel_name in channels:
            try:
                channel = Channel(channel_name)
                conn.subscribe(channel)
            except ValueError:
                pass

        await conn.send(WebSocketMessage(
            type=MessageType.ACK,
            data={
                "action": "subscribe",
                "channels": [c.value for c in conn.subscriptions],
            },
            id=message.id,
        ))

        # Send current state if subscribed to state channel
        if Channel.STATE in conn.subscriptions:
            await self._send_current_state(conn)

    async def _handle_unsubscribe(
        self,
        conn: WebSocketConnection,
        message: WebSocketMessage,
    ) -> None:
        """Handle unsubscription request."""
        channels = message.data.get("channels", []) if message.data else []

        for channel_name in channels:
            try:
                channel = Channel(channel_name)
                conn.unsubscribe(channel)
            except ValueError:
                pass

        await conn.send(WebSocketMessage(
            type=MessageType.ACK,
            data={
                "action": "unsubscribe",
                "channels": [c.value for c in conn.subscriptions],
            },
            id=message.id,
        ))

    async def _handle_command(
        self,
        conn: WebSocketConnection,
        message: WebSocketMessage,
    ) -> None:
        """Handle command execution."""
        if not message.data:
            await conn.send(WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": "No command data"},
                id=message.id,
            ))
            return

        command = message.data.get("command", "")
        args = message.data.get("args", {})

        try:
            from .mobile import get_mobile_api
            api = get_mobile_api()
            result = await api.execute_command(command, args)

            await conn.send(WebSocketMessage(
                type=MessageType.ACK,
                channel=Channel.COMMANDS,
                data=result,
                id=message.id,
            ))
        except Exception as e:
            await conn.send(WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": str(e)},
                id=message.id,
            ))

    async def _handle_ping(
        self,
        conn: WebSocketConnection,
        message: WebSocketMessage,
    ) -> None:
        """Handle ping/keep-alive."""
        conn.last_ping = time.time()
        await conn.send(WebSocketMessage(
            type=MessageType.PONG,
            data={"server_time": time.time()},
            id=message.id,
        ))
        conn.last_pong = time.time()

    async def _handle_auth(
        self,
        conn: WebSocketConnection,
        message: WebSocketMessage,
    ) -> None:
        """Handle authentication."""
        if not message.data:
            await conn.send(WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": "No auth data"},
                id=message.id,
            ))
            return

        token = message.data.get("token", "")

        try:
            from .mobile import get_mobile_api
            api = get_mobile_api()
            session = api.devices.validate_access_token(token)

            if session:
                conn.authenticated = True
                conn.user_id = session.user_id
                conn.device_id = session.device_id

                # Track user connection
                if conn.user_id not in self._user_connections:
                    self._user_connections[conn.user_id] = set()
                self._user_connections[conn.user_id].add(conn.connection_id)

                await conn.send(WebSocketMessage(
                    type=MessageType.ACK,
                    data={"authenticated": True, "user_id": conn.user_id},
                    id=message.id,
                ))
            else:
                await conn.send(WebSocketMessage(
                    type=MessageType.ERROR,
                    data={"error": "Invalid token"},
                    id=message.id,
                ))
        except Exception as e:
            await conn.send(WebSocketMessage(
                type=MessageType.ERROR,
                data={"error": str(e)},
                id=message.id,
            ))

    async def _send_current_state(self, conn: WebSocketConnection) -> None:
        """Send current state to a connection."""
        try:
            from .mobile import get_mobile_api
            api = get_mobile_api()
            state = await api.get_sync_state(conn.device_id or "unknown")

            await conn.send(WebSocketMessage(
                type=MessageType.STATE_UPDATE,
                channel=Channel.STATE,
                data=state,
            ))
        except Exception as e:
            logger.warning(f"Failed to send state: {e}")

    # =========================================================================
    # Broadcasting
    # =========================================================================

    async def broadcast(
        self,
        channel: Channel,
        message_type: MessageType,
        data: Dict[str, Any],
    ) -> int:
        """Broadcast a message to all subscribers of a channel."""
        message = WebSocketMessage(
            type=message_type,
            channel=channel,
            data=data,
        )

        sent = 0
        for conn in self._connections.values():
            if conn.is_subscribed(channel):
                await conn.send(message)
                sent += 1

        return sent

    async def broadcast_state_update(self, state: Dict[str, Any]) -> int:
        """Broadcast a state update."""
        self._state_cache["cognitive_state"] = state
        return await self.broadcast(
            Channel.STATE,
            MessageType.STATE_UPDATE,
            state,
        )

    async def broadcast_alert(self, alert: Alert) -> int:
        """Broadcast an alert."""
        return await self.broadcast(
            Channel.ALERTS,
            MessageType.ALERT,
            alert.to_dict(),
        )

    async def send_to_user(
        self,
        user_id: str,
        message: WebSocketMessage,
    ) -> int:
        """Send a message to all connections of a user."""
        connection_ids = self._user_connections.get(user_id, set())
        sent = 0

        for conn_id in connection_ids:
            conn = self._connections.get(conn_id)
            if conn:
                await conn.send(message)
                sent += 1

        return sent


# =============================================================================
# State Change Monitor
# =============================================================================

class StateChangeMonitor:
    """
    Monitors cognitive state changes and triggers WebSocket broadcasts.

    Detects:
    - Burnout level changes
    - Energy level changes
    - Mode switches
    - Project status changes
    """

    BURNOUT_THRESHOLDS = {
        "GREEN": 0,
        "YELLOW": 1,
        "ORANGE": 2,
        "RED": 3,
    }

    def __init__(self, hub: WebSocketHub):
        self.hub = hub
        self._last_state: Dict[str, Any] = {}
        self._check_interval = 5  # seconds

    async def check_state(self, current_state: Dict[str, Any]) -> None:
        """Check for state changes and broadcast if needed."""
        changes: List[Dict[str, Any]] = []

        # Check burnout changes
        old_burnout = self._last_state.get("burnout_level", "GREEN")
        new_burnout = current_state.get("burnout_level", "GREEN")
        if old_burnout != new_burnout:
            changes.append({
                "field": "burnout_level",
                "old": old_burnout,
                "new": new_burnout,
            })

            # Generate alert for worsening burnout
            old_level = self.BURNOUT_THRESHOLDS.get(old_burnout, 0)
            new_level = self.BURNOUT_THRESHOLDS.get(new_burnout, 0)
            if new_level > old_level:
                await self.hub.broadcast_alert(Alert(
                    severity=AlertSeverity.WARNING if new_burnout == "YELLOW" else AlertSeverity.CRITICAL,
                    title=f"Burnout: {new_burnout}",
                    message=self._get_burnout_message(new_burnout),
                    source="state_monitor",
                    data={"old": old_burnout, "new": new_burnout},
                ))

        # Check energy changes
        old_energy = self._last_state.get("energy_level", "medium")
        new_energy = current_state.get("energy_level", "medium")
        if old_energy != new_energy:
            changes.append({
                "field": "energy_level",
                "old": old_energy,
                "new": new_energy,
            })

            # Alert on depleted energy
            if new_energy == "depleted":
                await self.hub.broadcast_alert(Alert(
                    severity=AlertSeverity.WARNING,
                    title="Energy Depleted",
                    message="Consider taking a break.",
                    source="state_monitor",
                ))

        # Check mode changes
        old_mode = self._last_state.get("active_mode")
        new_mode = current_state.get("active_mode")
        if old_mode and new_mode and old_mode != new_mode:
            changes.append({
                "field": "active_mode",
                "old": old_mode,
                "new": new_mode,
            })

        # Broadcast state update if changes occurred
        if changes:
            await self.hub.broadcast_state_update({
                **current_state,
                "_changes": changes,
            })

        self._last_state = current_state.copy()

    def _get_burnout_message(self, level: str) -> str:
        """Get burnout alert message."""
        messages = {
            "YELLOW": "Consider taking a break soon.",
            "ORANGE": "You need a break. What's the blocker?",
            "RED": "Stop and rest. Recovery is necessary.",
        }
        return messages.get(level, "Check your burnout level.")


# =============================================================================
# Singleton
# =============================================================================

_websocket_hub: Optional[WebSocketHub] = None


def get_websocket_hub() -> WebSocketHub:
    """Get the global WebSocket hub."""
    global _websocket_hub
    if _websocket_hub is None:
        _websocket_hub = WebSocketHub()
    return _websocket_hub


def reset_websocket_hub() -> None:
    """Reset the global WebSocket hub (for testing)."""
    global _websocket_hub
    _websocket_hub = None


__all__ = [
    # Enums
    "MessageType",
    "Channel",
    "AlertSeverity",
    # Data classes
    "WebSocketMessage",
    "Alert",
    # Classes
    "WebSocketConnection",
    "WebSocketHub",
    "StateChangeMonitor",
    # Singleton
    "get_websocket_hub",
    "reset_websocket_hub",
]
