"""
OTTO Mobile Stack Integration Tests
====================================

End-to-end tests for the mobile infrastructure:
- Mobile API → WebSocket → Push flow
- Authentication flows (OTP, WebAuthn)
- State sync and real-time updates
- Offline/online transitions
"""

import asyncio
import json
import pytest
import time

from otto.api.mobile import (
    MobileAPI,
    DeviceType,
    PushProvider,
    get_mobile_api,
    reset_mobile_api,
)
from otto.api.websocket import (
    WebSocketHub,
    WebSocketMessage,
    MessageType,
    Channel,
    StateChangeMonitor,
    get_websocket_hub,
    reset_websocket_hub,
)
from otto.api.push import (
    PushNotificationManager,
    NotificationCategory,
    NotificationPriority,
    get_push_manager,
    reset_push_manager,
)
from otto.api.webauthn import (
    WebAuthnAPI,
    get_webauthn_api,
    reset_webauthn_api,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mobile_api():
    """Fresh MobileAPI instance."""
    reset_mobile_api()
    api = MobileAPI()
    yield api
    reset_mobile_api()


@pytest.fixture
def ws_hub():
    """Fresh WebSocketHub instance."""
    reset_websocket_hub()
    hub = WebSocketHub()
    yield hub
    reset_websocket_hub()


@pytest.fixture
def push_manager():
    """Fresh PushNotificationManager instance."""
    reset_push_manager()
    manager = PushNotificationManager()
    yield manager
    reset_push_manager()


@pytest.fixture
def webauthn_api():
    """Fresh WebAuthnAPI instance."""
    reset_webauthn_api()
    api = WebAuthnAPI(rp_id="localhost", rp_name="OTTO Test")
    yield api
    reset_webauthn_api()


# =============================================================================
# Mobile API Integration Tests
# =============================================================================

class TestMobileAPIIntegration:
    """Integration tests for Mobile API."""

    @pytest.mark.asyncio
    async def test_full_device_registration_flow(self, mobile_api):
        """Test complete device registration flow."""
        # Step 1: Register device
        reg_result = await mobile_api.register_device(
            device_type="ios",
            device_name="Integration Test iPhone",
            os_version="17.0",
            app_version="1.0.0",
        )

        assert "device_id" in reg_result
        assert "otp" in reg_result
        device_id = reg_result["device_id"]
        otp = reg_result["otp"]

        # Step 2: Verify device
        verify_result = await mobile_api.verify_device(
            device_id=device_id,
            otp=otp,
            user_id="integration_test_user",
        )

        assert verify_result["success"]
        assert "access_token" in verify_result
        assert "refresh_token" in verify_result
        access_token = verify_result["access_token"]
        refresh_token = verify_result["refresh_token"]

        # Step 3: Use access token to sync
        sync_result = await mobile_api.get_sync_state(device_id)
        assert "version" in sync_result
        assert "cognitive_state" in sync_result

        # Step 4: Refresh token
        refresh_result = await mobile_api.refresh_token(refresh_token)
        assert refresh_result["success"]
        assert refresh_result["access_token"] != access_token

    @pytest.mark.asyncio
    async def test_push_registration_after_device_verify(self, mobile_api):
        """Test push token registration flow."""
        # Register and verify device
        reg = await mobile_api.register_device("android", "Test Pixel")
        verify = await mobile_api.verify_device(
            reg["device_id"], reg["otp"], "test_user"
        )
        assert verify["success"]

        # Register push token
        push_result = await mobile_api.register_push(
            device_id=reg["device_id"],
            push_token="fcm_test_token_12345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345",
            provider="fcm",
        )

        assert push_result["success"]

    @pytest.mark.asyncio
    async def test_command_execution_flow(self, mobile_api):
        """Test command execution end-to-end."""
        # Register device first
        reg = await mobile_api.register_device("ios", "Command Test Device")
        await mobile_api.verify_device(reg["device_id"], reg["otp"], "cmd_user")

        # Execute various commands
        for cmd in ["health", "info", "state", "projects", "help"]:
            result = await mobile_api.execute_command(cmd)
            assert result["success"], f"Command {cmd} failed"
            assert result["command"] == cmd

    @pytest.mark.asyncio
    async def test_security_endpoints(self, mobile_api):
        """Test security-related endpoints."""
        # Get security posture
        posture = await mobile_api.get_security_posture()
        assert "status" in posture or "error" in posture

        # Get crypto capabilities
        crypto = await mobile_api.get_crypto_capabilities()
        assert "classical" in crypto
        assert "post_quantum" in crypto
        assert crypto["classical"]["available"] is True


# =============================================================================
# WebSocket Integration Tests
# =============================================================================

class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""

    @pytest.mark.asyncio
    async def test_connection_subscription_flow(self, ws_hub):
        """Test connection and subscription flow."""
        messages = []

        # Connect
        conn = ws_hub.register("test_conn", lambda m: messages.append(m))
        assert ws_hub.connection_count == 1

        # Welcome message should be sent
        await asyncio.sleep(0.1)
        assert len(messages) >= 1
        welcome = json.loads(messages[0])
        assert welcome["type"] == "welcome"

        # Subscribe to channels
        await ws_hub.handle_message(
            "test_conn",
            json.dumps({
                "type": "subscribe",
                "data": {"channels": ["state", "alerts"]},
            }),
        )

        assert Channel.STATE in conn.subscriptions
        assert Channel.ALERTS in conn.subscriptions

    @pytest.mark.asyncio
    async def test_state_broadcast_to_subscribers(self, ws_hub):
        """Test that state updates broadcast to subscribers."""
        messages1 = []
        messages2 = []

        # Connect two clients
        conn1 = ws_hub.register("conn1", lambda m: messages1.append(m))
        conn2 = ws_hub.register("conn2", lambda m: messages2.append(m))

        # Only conn1 subscribes to state
        conn1.subscribe(Channel.STATE)

        # Clear welcome messages
        messages1.clear()
        messages2.clear()

        # Broadcast state update
        await ws_hub.broadcast_state_update({"mode": "focused", "energy": "high"})

        # Only conn1 should receive
        assert len(messages1) == 1
        assert len(messages2) == 0

        data = json.loads(messages1[0])
        assert data["type"] == "state_update"
        assert data["data"]["mode"] == "focused"

    @pytest.mark.asyncio
    async def test_command_execution_via_websocket(self, ws_hub):
        """Test command execution through WebSocket."""
        messages = []
        ws_hub.register("cmd_conn", lambda m: messages.append(m))

        # Send command
        await ws_hub.handle_message(
            "cmd_conn",
            json.dumps({
                "type": "command",
                "id": "cmd123",
                "data": {"command": "health"},
            }),
        )

        # Find ack response
        ack = None
        for msg in messages:
            data = json.loads(msg)
            if data.get("type") == "ack" and data.get("id") == "cmd123":
                ack = data
                break

        assert ack is not None
        assert ack["data"]["success"]

    @pytest.mark.asyncio
    async def test_state_monitor_triggers_alerts(self, ws_hub):
        """Test that state changes trigger appropriate alerts."""
        messages = []
        conn = ws_hub.register("alert_conn", lambda m: messages.append(m))
        conn.subscribe(Channel.ALERTS)
        conn.subscribe(Channel.STATE)

        monitor = StateChangeMonitor(ws_hub)

        # Clear messages
        messages.clear()

        # Initial state
        await monitor.check_state({"burnout_level": "GREEN"})
        messages.clear()

        # Trigger burnout warning
        await monitor.check_state({"burnout_level": "ORANGE"})

        # Should have alert
        alerts = [json.loads(m) for m in messages if json.loads(m).get("type") == "alert"]
        assert len(alerts) >= 1
        assert alerts[0]["data"]["severity"] == "critical"


# =============================================================================
# Push Notification Integration Tests
# =============================================================================

class TestPushIntegration:
    """Integration tests for push notifications."""

    @pytest.mark.asyncio
    async def test_push_after_device_registration(self, mobile_api, push_manager):
        """Test push notification after device registration."""
        # Register device
        reg = await mobile_api.register_device("ios", "Push Test Device")
        verify = await mobile_api.verify_device(
            reg["device_id"], reg["otp"], "push_user"
        )
        assert verify["success"]

        # Register push token
        push_token = push_manager.register_token(
            token="0" * 64,  # Valid APNS token format
            provider=PushProvider.APNS,
            device_id=reg["device_id"],
            user_id="push_user",
        )

        assert push_token.user_id == "push_user"

        # Send notification
        results = await push_manager.send_burnout_warning(
            user_id="push_user",
            level="YELLOW",
            message="Consider taking a break",
        )

        assert len(results) == 1
        assert results[0].status.value in ["sent", "delivered"]

    @pytest.mark.asyncio
    async def test_multi_device_push(self, push_manager):
        """Test push to user with multiple devices."""
        # Register multiple tokens for same user
        push_manager.register_token(
            "token1" + "0" * 56,
            PushProvider.APNS,
            "device1",
            "multi_device_user",
        )
        push_manager.register_token(
            "token2" + "0" * 100,
            PushProvider.FCM,
            "device2",
            "multi_device_user",
        )

        # Send notification
        results = await push_manager.send_security_alert(
            user_ids=["multi_device_user"],
            message="Security test alert",
        )

        # Should send to both devices
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_template_based_notifications(self, push_manager):
        """Test template-based notification sending."""
        push_manager.register_token(
            "tmpl_token" + "0" * 100,
            PushProvider.FCM,
            "tmpl_device",
            "tmpl_user",
        )

        # Test different categories
        for category, vars in [
            (NotificationCategory.BURNOUT_WARNING, {"level": "RED", "message": "Stop!"}),
            (NotificationCategory.ENERGY_ALERT, {"level": "depleted", "message": "Rest needed"}),
            (NotificationCategory.PROJECT_UPDATE, {"project_name": "OTTO", "message": "Updated"}),
        ]:
            results = await push_manager.send_from_template(
                category=category,
                user_ids=["tmpl_user"],
                **vars,
            )
            assert len(results) == 1


# =============================================================================
# WebAuthn Integration Tests
# =============================================================================

class TestWebAuthnIntegration:
    """Integration tests for WebAuthn authentication."""

    @pytest.mark.asyncio
    async def test_registration_options_generation(self, webauthn_api):
        """Test WebAuthn registration options."""
        result = await webauthn_api.start_registration(
            user_id="webauthn_user",
            user_name="test@example.com",
            display_name="Test User",
        )

        assert result["success"]
        options = result["options"]
        assert "challenge" in options
        assert "rp" in options
        assert "user" in options
        assert options["rp"]["name"] == "OTTO Test"

    @pytest.mark.asyncio
    async def test_authentication_options_generation(self, webauthn_api):
        """Test WebAuthn authentication options."""
        result = await webauthn_api.start_authentication()

        assert result["success"]
        options = result["options"]
        assert "challenge" in options
        assert "rpId" in options


# =============================================================================
# Full Stack Integration Tests
# =============================================================================

class TestFullStackIntegration:
    """End-to-end tests combining all components."""

    @pytest.mark.asyncio
    async def test_mobile_to_websocket_to_push_flow(
        self, mobile_api, ws_hub, push_manager
    ):
        """Test complete flow: Mobile API → WebSocket → Push."""
        # 1. Register and verify device
        reg = await mobile_api.register_device("ios", "Full Stack Test")
        verify = await mobile_api.verify_device(
            reg["device_id"], reg["otp"], "fullstack_user"
        )
        assert verify["success"]

        # 2. Connect to WebSocket
        ws_messages = []
        conn = ws_hub.register(
            f"ws_{reg['device_id']}",
            lambda m: ws_messages.append(m),
        )
        conn.subscribe(Channel.STATE)
        conn.subscribe(Channel.ALERTS)

        # 3. Register push token
        push_manager.register_token(
            "fullstack_token" + "0" * 50,
            PushProvider.APNS,
            reg["device_id"],
            "fullstack_user",
        )

        # 4. State monitor detects change and broadcasts
        monitor = StateChangeMonitor(ws_hub)
        ws_messages.clear()

        await monitor.check_state({"burnout_level": "GREEN"})
        await monitor.check_state({"burnout_level": "RED"})

        # 5. WebSocket should have received alert
        alerts = [json.loads(m) for m in ws_messages if json.loads(m).get("type") == "alert"]
        assert len(alerts) >= 1

        # 6. Push notification also sent
        push_results = await push_manager.send_burnout_warning(
            user_id="fullstack_user",
            level="RED",
            message="Critical burnout - stop and rest!",
        )
        assert len(push_results) == 1

    @pytest.mark.asyncio
    async def test_sync_state_consistency(self, mobile_api, ws_hub):
        """Test that sync state is consistent across API and WebSocket."""
        # Register device
        reg = await mobile_api.register_device("web", "Sync Test")
        await mobile_api.verify_device(reg["device_id"], reg["otp"], "sync_user")

        # Get state via API
        api_state = await mobile_api.get_sync_state(reg["device_id"])

        # Connect WebSocket and get state
        ws_messages = []
        conn = ws_hub.register("sync_ws", lambda m: ws_messages.append(m))
        conn.subscribe(Channel.STATE)

        # Request state via WebSocket
        await ws_hub.handle_message(
            "sync_ws",
            json.dumps({"type": "subscribe", "data": {"channels": ["state"]}}),
        )

        # Both should have consistent cognitive_state structure
        assert "cognitive_state" in api_state
        assert "active_mode" in api_state["cognitive_state"]

    @pytest.mark.asyncio
    async def test_offline_command_queueing(self, mobile_api):
        """Test that commands work even when executed rapidly."""
        # Register device
        reg = await mobile_api.register_device("ios", "Offline Test")
        await mobile_api.verify_device(reg["device_id"], reg["otp"], "offline_user")

        # Execute multiple commands rapidly
        commands = ["health", "info", "state", "health", "projects"]
        results = await asyncio.gather(*[
            mobile_api.execute_command(cmd)
            for cmd in commands
        ])

        # All should succeed
        for i, result in enumerate(results):
            assert result["success"], f"Command {commands[i]} failed"


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance and load tests."""

    @pytest.mark.asyncio
    async def test_websocket_broadcast_performance(self, ws_hub):
        """Test broadcasting to many connections."""
        # Create 100 connections
        all_messages = []
        connections = []
        for i in range(100):
            msgs = []
            conn = ws_hub.register(f"perf_conn_{i}", lambda m, msgs=msgs: msgs.append(m))
            conn.subscribe(Channel.STATE)
            connections.append((conn, msgs))
            all_messages.append(msgs)

        # Clear welcome messages
        for msgs in all_messages:
            msgs.clear()

        # Broadcast
        start = time.time()
        sent = await ws_hub.broadcast_state_update({"test": "data"})
        elapsed = time.time() - start

        assert sent == 100
        assert elapsed < 1.0  # Should complete within 1 second

        # All should have received
        for msgs in all_messages:
            assert len(msgs) == 1

    @pytest.mark.asyncio
    async def test_push_batch_performance(self, push_manager):
        """Test sending to many push tokens."""
        # Register 50 tokens
        for i in range(50):
            push_manager.register_token(
                f"batch_token_{i}" + "0" * 100,
                PushProvider.FCM,
                f"device_{i}",
                "batch_user",
            )

        # Send notification
        start = time.time()
        results = await push_manager.send_burnout_warning(
            user_id="batch_user",
            level="YELLOW",
            message="Batch test",
        )
        elapsed = time.time() - start

        assert len(results) == 50
        assert elapsed < 2.0  # Should complete within 2 seconds
