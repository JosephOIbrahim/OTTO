"""
Tests for OTTO WebSocket API
============================

Tests real-time communication, subscriptions, and alerts.
"""

import asyncio
import json
import pytest
import time

from otto.api.websocket import (
    MessageType,
    Channel,
    AlertSeverity,
    WebSocketMessage,
    Alert,
    WebSocketConnection,
    WebSocketHub,
    StateChangeMonitor,
    get_websocket_hub,
    reset_websocket_hub,
)


# =============================================================================
# Message Tests
# =============================================================================

class TestWebSocketMessage:
    """Tests for WebSocketMessage."""

    def test_message_creation(self):
        """Test message creation."""
        msg = WebSocketMessage(
            type=MessageType.PING,
            data={"test": "value"},
        )

        assert msg.type == MessageType.PING
        assert msg.data == {"test": "value"}
        assert msg.id is not None
        assert msg.timestamp > 0

    def test_message_to_dict(self):
        """Test message serialization to dict."""
        msg = WebSocketMessage(
            type=MessageType.STATE_UPDATE,
            channel=Channel.STATE,
            data={"mode": "focused"},
        )

        data = msg.to_dict()
        assert data["type"] == "state_update"
        assert data["channel"] == "state"
        assert data["data"] == {"mode": "focused"}

    def test_message_to_json(self):
        """Test message serialization to JSON."""
        msg = WebSocketMessage(
            type=MessageType.PONG,
            data={"time": 12345},
        )

        json_str = msg.to_json()
        parsed = json.loads(json_str)
        assert parsed["type"] == "pong"

    def test_message_from_dict(self):
        """Test message creation from dict."""
        data = {
            "type": "subscribe",
            "channel": "alerts",
            "data": {"test": True},
            "id": "msg123",
            "timestamp": 1000.0,
        }

        msg = WebSocketMessage.from_dict(data)
        assert msg.type == MessageType.SUBSCRIBE
        assert msg.channel == Channel.ALERTS
        assert msg.id == "msg123"

    def test_message_from_json(self):
        """Test message parsing from JSON."""
        json_str = '{"type": "ping", "data": null}'
        msg = WebSocketMessage.from_json(json_str)

        assert msg.type == MessageType.PING

    def test_message_roundtrip(self):
        """Test message roundtrip serialization."""
        original = WebSocketMessage(
            type=MessageType.COMMAND,
            channel=Channel.COMMANDS,
            data={"command": "health"},
        )

        json_str = original.to_json()
        restored = WebSocketMessage.from_json(json_str)

        assert restored.type == original.type
        assert restored.channel == original.channel
        assert restored.data == original.data


class TestAlert:
    """Tests for Alert."""

    def test_alert_creation(self):
        """Test alert creation."""
        alert = Alert(
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="This is a test",
            source="test",
        )

        assert alert.severity == AlertSeverity.WARNING
        assert alert.title == "Test Alert"
        assert alert.timestamp > 0

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = Alert(
            severity=AlertSeverity.CRITICAL,
            title="Critical",
            message="Something bad",
            source="monitor",
            data={"level": "RED"},
        )

        data = alert.to_dict()
        assert data["severity"] == "critical"
        assert data["title"] == "Critical"
        assert data["data"] == {"level": "RED"}


# =============================================================================
# Connection Tests
# =============================================================================

class TestWebSocketConnection:
    """Tests for WebSocketConnection."""

    def test_connection_creation(self):
        """Test connection creation."""
        messages = []
        conn = WebSocketConnection("conn1", lambda m: messages.append(m))

        assert conn.connection_id == "conn1"
        assert not conn.authenticated
        assert len(conn.subscriptions) == 0

    def test_subscribe(self):
        """Test channel subscription."""
        conn = WebSocketConnection("conn1", lambda m: None)

        conn.subscribe(Channel.STATE)
        assert Channel.STATE in conn.subscriptions

        conn.subscribe(Channel.ALERTS)
        assert len(conn.subscriptions) == 2

    def test_subscribe_all(self):
        """Test subscribing to all channels."""
        conn = WebSocketConnection("conn1", lambda m: None)

        conn.subscribe(Channel.ALL)
        assert Channel.ALL in conn.subscriptions

    def test_unsubscribe(self):
        """Test channel unsubscription."""
        conn = WebSocketConnection("conn1", lambda m: None)

        conn.subscribe(Channel.STATE)
        conn.subscribe(Channel.ALERTS)
        conn.unsubscribe(Channel.STATE)

        assert Channel.STATE not in conn.subscriptions
        assert Channel.ALERTS in conn.subscriptions

    def test_unsubscribe_all(self):
        """Test unsubscribing from all channels."""
        conn = WebSocketConnection("conn1", lambda m: None)

        conn.subscribe(Channel.STATE)
        conn.subscribe(Channel.ALERTS)
        conn.unsubscribe(Channel.ALL)

        assert len(conn.subscriptions) == 0

    def test_is_subscribed(self):
        """Test subscription check."""
        conn = WebSocketConnection("conn1", lambda m: None)

        conn.subscribe(Channel.STATE)

        assert conn.is_subscribed(Channel.STATE)
        assert not conn.is_subscribed(Channel.ALERTS)

    def test_is_subscribed_all(self):
        """Test subscription check with ALL channel."""
        conn = WebSocketConnection("conn1", lambda m: None)

        conn.subscribe(Channel.ALL)

        assert conn.is_subscribed(Channel.STATE)
        assert conn.is_subscribed(Channel.ALERTS)
        assert conn.is_subscribed(Channel.COMMANDS)

    @pytest.mark.asyncio
    async def test_send(self):
        """Test sending a message."""
        messages = []
        conn = WebSocketConnection("conn1", lambda m: messages.append(m))

        await conn.send(WebSocketMessage(
            type=MessageType.PONG,
            data={"test": True},
        ))

        assert len(messages) == 1
        parsed = json.loads(messages[0])
        assert parsed["type"] == "pong"


# =============================================================================
# Hub Tests
# =============================================================================

class TestWebSocketHub:
    """Tests for WebSocketHub."""

    def setup_method(self):
        """Create fresh hub."""
        reset_websocket_hub()
        self.hub = WebSocketHub()

    def test_register_connection(self):
        """Test connection registration."""
        messages = []
        conn = self.hub.register("conn1", lambda m: messages.append(m))

        assert conn.connection_id == "conn1"
        assert self.hub.connection_count == 1
        assert len(messages) == 1  # Welcome message

    def test_unregister_connection(self):
        """Test connection removal."""
        self.hub.register("conn1", lambda m: None)
        self.hub.unregister("conn1")

        assert self.hub.connection_count == 0

    def test_get_connection(self):
        """Test getting a connection."""
        self.hub.register("conn1", lambda m: None)

        conn = self.hub.get_connection("conn1")
        assert conn is not None
        assert conn.connection_id == "conn1"

        missing = self.hub.get_connection("nonexistent")
        assert missing is None

    @pytest.mark.asyncio
    async def test_handle_subscribe_message(self):
        """Test handling subscribe message."""
        messages = []
        conn = self.hub.register("conn1", lambda m: messages.append(m))

        await self.hub.handle_message(
            "conn1",
            json.dumps({
                "type": "subscribe",
                "data": {"channels": ["state", "alerts"]},
            }),
        )

        assert Channel.STATE in conn.subscriptions
        assert Channel.ALERTS in conn.subscriptions

    @pytest.mark.asyncio
    async def test_handle_unsubscribe_message(self):
        """Test handling unsubscribe message."""
        conn = self.hub.register("conn1", lambda m: None)
        conn.subscribe(Channel.STATE)
        conn.subscribe(Channel.ALERTS)

        await self.hub.handle_message(
            "conn1",
            json.dumps({
                "type": "unsubscribe",
                "data": {"channels": ["state"]},
            }),
        )

        assert Channel.STATE not in conn.subscriptions
        assert Channel.ALERTS in conn.subscriptions

    @pytest.mark.asyncio
    async def test_handle_ping_message(self):
        """Test handling ping message."""
        messages = []
        self.hub.register("conn1", lambda m: messages.append(m))

        await self.hub.handle_message(
            "conn1",
            json.dumps({"type": "ping", "id": "ping123"}),
        )

        # Find pong response
        pong = None
        for msg in messages:
            data = json.loads(msg)
            if data.get("type") == "pong":
                pong = data
                break

        assert pong is not None
        assert pong["id"] == "ping123"

    @pytest.mark.asyncio
    async def test_handle_invalid_message(self):
        """Test handling invalid message."""
        messages = []
        self.hub.register("conn1", lambda m: messages.append(m))

        await self.hub.handle_message("conn1", "not valid json")

        # Should get error response
        error = None
        for msg in messages:
            data = json.loads(msg)
            if data.get("type") == "error":
                error = data
                break

        assert error is not None

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcasting to subscribers."""
        messages1 = []
        messages2 = []
        messages3 = []

        conn1 = self.hub.register("conn1", lambda m: messages1.append(m))
        conn2 = self.hub.register("conn2", lambda m: messages2.append(m))
        conn3 = self.hub.register("conn3", lambda m: messages3.append(m))

        conn1.subscribe(Channel.STATE)
        conn2.subscribe(Channel.STATE)
        # conn3 not subscribed

        messages1.clear()
        messages2.clear()
        messages3.clear()

        sent = await self.hub.broadcast(
            Channel.STATE,
            MessageType.STATE_UPDATE,
            {"test": "data"},
        )

        assert sent == 2
        assert len(messages1) == 1
        assert len(messages2) == 1
        assert len(messages3) == 0

    @pytest.mark.asyncio
    async def test_broadcast_state_update(self):
        """Test broadcasting state update."""
        messages = []
        conn = self.hub.register("conn1", lambda m: messages.append(m))
        conn.subscribe(Channel.STATE)
        messages.clear()

        await self.hub.broadcast_state_update({"mode": "focused"})

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "state_update"
        assert data["data"]["mode"] == "focused"

    @pytest.mark.asyncio
    async def test_broadcast_alert(self):
        """Test broadcasting alert."""
        messages = []
        conn = self.hub.register("conn1", lambda m: messages.append(m))
        conn.subscribe(Channel.ALERTS)
        messages.clear()

        await self.hub.broadcast_alert(Alert(
            severity=AlertSeverity.WARNING,
            title="Test",
            message="Test message",
            source="test",
        ))

        assert len(messages) == 1
        data = json.loads(messages[0])
        assert data["type"] == "alert"
        assert data["data"]["title"] == "Test"


# =============================================================================
# State Monitor Tests
# =============================================================================

class TestStateChangeMonitor:
    """Tests for StateChangeMonitor."""

    def setup_method(self):
        """Create fresh monitor."""
        self.hub = WebSocketHub()
        self.monitor = StateChangeMonitor(self.hub)

    @pytest.mark.asyncio
    async def test_burnout_change_alert(self):
        """Test alert on burnout change."""
        messages = []
        conn = self.hub.register("conn1", lambda m: messages.append(m))
        conn.subscribe(Channel.ALERTS)
        conn.subscribe(Channel.STATE)
        messages.clear()

        # Initial state
        await self.monitor.check_state({"burnout_level": "GREEN"})
        messages.clear()

        # Worsening burnout
        await self.monitor.check_state({"burnout_level": "YELLOW"})

        # Should have alert and state update
        alerts = [json.loads(m) for m in messages if json.loads(m).get("type") == "alert"]
        assert len(alerts) >= 1
        assert alerts[0]["data"]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_energy_depleted_alert(self):
        """Test alert on energy depletion."""
        messages = []
        conn = self.hub.register("conn1", lambda m: messages.append(m))
        conn.subscribe(Channel.ALERTS)
        messages.clear()

        await self.monitor.check_state({"energy_level": "medium"})
        messages.clear()

        await self.monitor.check_state({"energy_level": "depleted"})

        alerts = [json.loads(m) for m in messages if json.loads(m).get("type") == "alert"]
        assert len(alerts) >= 1

    @pytest.mark.asyncio
    async def test_no_alert_on_improvement(self):
        """Test no alert when burnout improves."""
        messages = []
        conn = self.hub.register("conn1", lambda m: messages.append(m))
        conn.subscribe(Channel.ALERTS)

        await self.monitor.check_state({"burnout_level": "ORANGE"})
        messages.clear()

        await self.monitor.check_state({"burnout_level": "GREEN"})

        # Should have state update but no warning alert
        alerts = [json.loads(m) for m in messages if json.loads(m).get("type") == "alert"]
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_state_update_on_change(self):
        """Test state update broadcast on changes."""
        messages = []
        conn = self.hub.register("conn1", lambda m: messages.append(m))
        conn.subscribe(Channel.STATE)
        messages.clear()

        await self.monitor.check_state({"active_mode": "focused"})
        messages.clear()

        await self.monitor.check_state({"active_mode": "exploring"})

        updates = [json.loads(m) for m in messages if json.loads(m).get("type") == "state_update"]
        assert len(updates) >= 1
        assert "_changes" in updates[0]["data"]


# =============================================================================
# Singleton Tests
# =============================================================================

class TestWebSocketSingleton:
    """Tests for WebSocket singleton."""

    def setup_method(self):
        """Reset singleton."""
        reset_websocket_hub()

    def test_get_websocket_hub(self):
        """Test getting singleton."""
        hub1 = get_websocket_hub()
        hub2 = get_websocket_hub()

        assert hub1 is hub2

    def test_reset_websocket_hub(self):
        """Test resetting singleton."""
        hub1 = get_websocket_hub()
        reset_websocket_hub()
        hub2 = get_websocket_hub()

        assert hub1 is not hub2
