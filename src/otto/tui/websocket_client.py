"""
OTTO TUI WebSocket Client
=========================

Determinism WebSocket client for real-time updates.

Principles:
1. Fixed reconnection intervals (no exponential backoff variance)
2. Deterministic message handling order
3. Fixed channel subscription list
4. Reproducible state dispatch sequence

Reference: He, Horace and Thinking Machines Lab,
"Defeating Nondeterminism in LLM Inference", Sep 2025.
"""

import asyncio
import json
import time
from typing import Optional, Callable, Dict, Any, List
from enum import Enum
import logging

from .state import StateStore, Alert, get_store
from .constants import (
    WEBSOCKET_RECONNECT_INTERVAL_MS,
)

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class TUIWebSocketClient:
    """
    WebSocket client for TUI real-time updates.

    Determinism:
    - Fixed reconnection interval (no jitter)
    - Deterministic message type → handler mapping
    - Fixed channel subscription order
    - State updates dispatched in arrival order
    """

    # Fixed channel list, subscribed in this order
    CHANNELS = ("state", "alerts", "projects")

    # Fixed message type → handler mapping
    MESSAGE_HANDLERS = (
        "welcome",
        "state_update",
        "alert",
        "ack",
        "error",
        "pong",
    )

    def __init__(
        self,
        store: Optional[StateStore] = None,
        url: str = "ws://localhost:8080/ws",
        reconnect_interval_ms: int = WEBSOCKET_RECONNECT_INTERVAL_MS,
    ):
        """
        Initialize WebSocket client.

        Args:
            store: State store for dispatching updates
            url: WebSocket server URL
            reconnect_interval_ms: Fixed reconnection interval
        """
        self._store = store or get_store()
        self._url = url
        self._reconnect_interval = reconnect_interval_ms / 1000.0
        self._state = ConnectionState.DISCONNECTED
        self._websocket = None
        self._running = False
        self._ping_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None

    @property
    def connected(self) -> bool:
        """Check if connected."""
        return self._state == ConnectionState.CONNECTED

    async def connect(self) -> bool:
        """
        Connect to WebSocket server.

        Determinism: Deterministic connection sequence.
        """
        try:
            # Import here to avoid dependency if not using websockets
            import websockets

            self._state = ConnectionState.CONNECTING
            self._store.dispatch("CONNECTION_UPDATE", {
                "connected": False,
                "error": "Connecting...",
            })

            self._websocket = await websockets.connect(self._url)
            self._state = ConnectionState.CONNECTED

            # Subscribe to channels in FIXED order
            await self._subscribe_channels()

            self._store.dispatch("CONNECTION_UPDATE", {
                "connected": True,
                "error": "",
            })

            logger.info(f"Connected to {self._url}")
            return True

        except Exception as e:
            self._state = ConnectionState.DISCONNECTED
            self._store.dispatch("CONNECTION_UPDATE", {
                "connected": False,
                "error": str(e),
            })
            logger.error(f"Connection failed: {e}")
            return False

    async def _subscribe_channels(self) -> None:
        """
        Subscribe to channels in fixed order.

        Determinism: Fixed channel order from CHANNELS tuple.
        """
        if not self._websocket:
            return

        # Subscribe in fixed order
        message = json.dumps({
            "type": "subscribe",
            "data": {"channels": list(self.CHANNELS)},
        })
        await self._websocket.send(message)
        logger.debug(f"Subscribed to channels: {self.CHANNELS}")

    async def disconnect(self) -> None:
        """Disconnect from WebSocket server."""
        self._running = False

        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None

        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None

        if self._websocket:
            await self._websocket.close()
            self._websocket = None

        self._state = ConnectionState.DISCONNECTED
        self._store.dispatch("CONNECTION_UPDATE", {
            "connected": False,
            "error": "",
        })

    async def run(self) -> None:
        """
        Run the WebSocket client with automatic reconnection.

        Determinism:
        - Fixed reconnection interval (no exponential backoff)
        - Deterministic reconnection loop
        """
        self._running = True

        while self._running:
            if self._state != ConnectionState.CONNECTED:
                connected = await self.connect()
                if not connected:
                    # Fixed interval, no jitter
                    await asyncio.sleep(self._reconnect_interval)
                    continue

            try:
                # Start tasks
                self._ping_task = asyncio.create_task(self._ping_loop())
                self._receive_task = asyncio.create_task(self._receive_loop())

                # Wait for either task to complete (usually due to disconnect)
                done, pending = await asyncio.wait(
                    [self._ping_task, self._receive_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()

            except Exception as e:
                logger.error(f"Error in run loop: {e}")

            # Disconnected, will reconnect
            self._state = ConnectionState.RECONNECTING
            self._store.dispatch("CONNECTION_UPDATE", {
                "connected": False,
                "error": "Reconnecting...",
            })

            # Fixed interval
            await asyncio.sleep(self._reconnect_interval)

    async def _ping_loop(self) -> None:
        """
        Send periodic pings.

        Determinism: Fixed ping interval.
        """
        PING_INTERVAL = 30.0  # Fixed interval

        while self._running and self._websocket:
            await asyncio.sleep(PING_INTERVAL)

            if self._websocket:
                try:
                    message = json.dumps({
                        "type": "ping",
                        "id": f"ping_{time.time()}",
                    })
                    await self._websocket.send(message)
                except Exception as e:
                    logger.error(f"Ping failed: {e}")
                    break

    async def _receive_loop(self) -> None:
        """
        Receive and process messages.

        Determinism:
        - Messages processed in arrival order
        - Fixed message type → handler mapping
        """
        while self._running and self._websocket:
            try:
                message = await self._websocket.recv()
                await self._handle_message(message)
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break

    async def _handle_message(self, raw_message: str) -> None:
        """
        Handle incoming message.

        Determinism:
        - Fixed message type → handler mapping
        - Deterministic dispatch order
        """
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {raw_message[:100]}")
            return

        message_type = data.get("type")

        # Fixed handler mapping
        handlers = {
            "welcome": self._handle_welcome,
            "state_update": self._handle_state_update,
            "alert": self._handle_alert,
            "ack": self._handle_ack,
            "error": self._handle_error,
            "pong": self._handle_pong,
        }

        handler = handlers.get(message_type)
        if handler:
            await handler(data)
        else:
            logger.debug(f"Unknown message type: {message_type}")

    async def _handle_welcome(self, data: Dict[str, Any]) -> None:
        """Handle welcome message."""
        logger.info("Received welcome from server")
        self._store.dispatch("ALERT_ADD", {
            "id": f"welcome_{time.time()}",
            "timestamp": time.time(),
            "severity": "info",
            "title": "Connected",
            "message": "WebSocket connection established",
            "source": "websocket",
        })

    async def _handle_state_update(self, data: Dict[str, Any]) -> None:
        """
        Handle state update message.

        Determinism: Dispatch in fixed field order.
        """
        state_data = data.get("data", {})

        # Extract fields in fixed order
        update = {}
        for field in (
            "active_mode",
            "burnout_level",
            "energy_level",
            "momentum_phase",
            "current_altitude",
            "exchange_count",
        ):
            if field in state_data:
                update[field] = state_data[field]

        if update:
            self._store.dispatch("COGNITIVE_UPDATE", update)

    async def _handle_alert(self, data: Dict[str, Any]) -> None:
        """Handle alert message."""
        alert_data = data.get("data", {})
        self._store.dispatch("ALERT_ADD", {
            "id": alert_data.get("id", f"alert_{time.time()}"),
            "timestamp": alert_data.get("timestamp", time.time()),
            "severity": alert_data.get("severity", "info"),
            "title": alert_data.get("title", "Alert"),
            "message": alert_data.get("message", ""),
            "source": alert_data.get("source", "server"),
        })

    async def _handle_ack(self, data: Dict[str, Any]) -> None:
        """Handle command acknowledgment."""
        logger.debug(f"Command ack: {data.get('id')}")

    async def _handle_error(self, data: Dict[str, Any]) -> None:
        """Handle error message."""
        error_data = data.get("data", {})
        self._store.dispatch("ALERT_ADD", {
            "id": f"error_{time.time()}",
            "timestamp": time.time(),
            "severity": "error",
            "title": "Error",
            "message": error_data.get("message", "Unknown error"),
            "source": "server",
        })

    async def _handle_pong(self, data: Dict[str, Any]) -> None:
        """Handle pong response."""
        logger.debug("Received pong")

    async def send_command(self, command: str, args: Optional[Dict[str, Any]] = None) -> None:
        """
        Send a command to the server.

        Determinism: Fixed message structure.
        """
        if not self._websocket:
            return

        message = json.dumps({
            "type": "command",
            "id": f"cmd_{time.time()}",
            "data": {
                "command": command,
                **(args or {}),
            },
        })

        await self._websocket.send(message)


# =============================================================================
# Factory Functions
# =============================================================================

_client: Optional[TUIWebSocketClient] = None


def get_websocket_client(
    url: str = "ws://localhost:8080/ws",
    store: Optional[StateStore] = None,
) -> TUIWebSocketClient:
    """Get or create the singleton WebSocket client."""
    global _client
    if _client is None:
        _client = TUIWebSocketClient(store=store, url=url)
    return _client


def reset_websocket_client() -> None:
    """Reset the WebSocket client (for testing)."""
    global _client
    if _client is not None:
        asyncio.create_task(_client.disconnect())
    _client = None
