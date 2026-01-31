"""
Tests for OTTO Mobile API
=========================

Tests device registration, authentication, sync, and command execution.
"""

import asyncio
import pytest
import time

from otto.api.mobile import (
    # Enums
    DeviceType,
    DeviceStatus,
    PushProvider,
    # Data classes
    DeviceInfo,
    MobileSession,
    SyncState,
    CryptoCapabilities,
    CommandResult,
    # Managers
    MobileDeviceManager,
    MobileSyncManager,
    MobileCommandExecutor,
    # API
    MobileAPI,
    get_mobile_api,
    reset_mobile_api,
    # Routes
    get_mobile_routes,
)


# =============================================================================
# Device Manager Tests
# =============================================================================

class TestMobileDeviceManager:
    """Tests for MobileDeviceManager."""

    def setup_method(self):
        """Create fresh manager for each test."""
        self.manager = MobileDeviceManager()

    def test_register_device(self):
        """Test device registration."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="iPhone 15",
            os_version="17.0",
            app_version="1.0.0",
        )

        assert device_id is not None
        assert len(device_id) == 16  # SHA256 truncated
        assert len(otp) == 6  # OTP length
        assert otp.isdigit()  # Numeric OTP

    def test_register_android_device(self):
        """Test Android device registration."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.ANDROID,
            device_name="Pixel 8",
            os_version="14",
        )

        device = self.manager.get_device(device_id)
        assert device is not None
        assert device.device_type == DeviceType.ANDROID
        assert device.status == DeviceStatus.PENDING

    def test_register_matrix_device(self):
        """Test Matrix client device registration."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.MATRIX,
            device_name="Element iOS",
        )

        device = self.manager.get_device(device_id)
        assert device.device_type == DeviceType.MATRIX

    def test_verify_device_success(self):
        """Test successful device verification."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="Test iPhone",
        )

        session = self.manager.verify_device(device_id, otp, "user123")

        assert session is not None
        assert session.device_id == device_id
        assert session.user_id == "user123"
        assert session.access_token is not None
        assert session.refresh_token is not None
        assert not session.is_expired

        device = self.manager.get_device(device_id)
        assert device.status == DeviceStatus.VERIFIED

    def test_verify_device_wrong_otp(self):
        """Test verification with wrong OTP."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="Test iPhone",
        )

        session = self.manager.verify_device(device_id, "000000", "user123")
        assert session is None

    def test_verify_device_unknown_device(self):
        """Test verification for unknown device."""
        session = self.manager.verify_device("unknown", "123456", "user123")
        assert session is None

    def test_refresh_session(self):
        """Test session refresh."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="Test iPhone",
        )
        session = self.manager.verify_device(device_id, otp, "user123")

        new_session = self.manager.refresh_session(session.refresh_token)

        assert new_session is not None
        assert new_session.session_id != session.session_id
        assert new_session.device_id == device_id
        assert new_session.access_token != session.access_token

    def test_refresh_session_invalid_token(self):
        """Test refresh with invalid token."""
        new_session = self.manager.refresh_session("invalid_token")
        assert new_session is None

    def test_validate_access_token(self):
        """Test access token validation."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="Test iPhone",
        )
        session = self.manager.verify_device(device_id, otp, "user123")

        validated = self.manager.validate_access_token(session.access_token)

        assert validated is not None
        assert validated.session_id == session.session_id

    def test_validate_access_token_invalid(self):
        """Test validation with invalid token."""
        validated = self.manager.validate_access_token("invalid_token")
        assert validated is None

    def test_register_push_token(self):
        """Test push notification token registration."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="Test iPhone",
        )
        self.manager.verify_device(device_id, otp, "user123")

        success = self.manager.register_push_token(
            device_id,
            "apns_token_123",
            PushProvider.APNS,
        )

        assert success
        device = self.manager.get_device(device_id)
        assert device.push_token == "apns_token_123"
        assert device.push_provider == PushProvider.APNS

    def test_register_push_token_fcm(self):
        """Test FCM push token registration."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.ANDROID,
            device_name="Test Pixel",
        )
        self.manager.verify_device(device_id, otp, "user123")

        success = self.manager.register_push_token(
            device_id,
            "fcm_token_456",
            PushProvider.FCM,
        )

        assert success
        device = self.manager.get_device(device_id)
        assert device.push_provider == PushProvider.FCM

    def test_register_push_token_unverified_device(self):
        """Test push token registration for unverified device."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="Test iPhone",
        )

        success = self.manager.register_push_token(
            device_id,
            "token",
            PushProvider.APNS,
        )

        assert not success  # Device not verified

    def test_unregister_push_token(self):
        """Test push token unregistration."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="Test iPhone",
        )
        self.manager.verify_device(device_id, otp, "user123")
        self.manager.register_push_token(device_id, "token", PushProvider.APNS)

        success = self.manager.unregister_push_token(device_id)

        assert success
        device = self.manager.get_device(device_id)
        assert device.push_token is None

    def test_revoke_device(self):
        """Test device revocation."""
        device_id, otp = self.manager.register_device(
            device_type=DeviceType.IOS,
            device_name="Test iPhone",
        )
        self.manager.verify_device(device_id, otp, "user123")

        success = self.manager.revoke_device(device_id)

        assert success
        device = self.manager.get_device(device_id)
        assert device.status == DeviceStatus.REVOKED

    def test_get_devices_for_user(self):
        """Test getting all devices for a user."""
        device1, otp1 = self.manager.register_device(DeviceType.IOS, "iPhone")
        device2, otp2 = self.manager.register_device(DeviceType.ANDROID, "Pixel")
        device3, otp3 = self.manager.register_device(DeviceType.WEB, "Browser")

        self.manager.verify_device(device1, otp1, "user1")
        self.manager.verify_device(device2, otp2, "user1")
        self.manager.verify_device(device3, otp3, "user2")

        user1_devices = self.manager.get_devices_for_user("user1")
        assert len(user1_devices) == 2

        user2_devices = self.manager.get_devices_for_user("user2")
        assert len(user2_devices) == 1


# =============================================================================
# Session Tests
# =============================================================================

class TestMobileSession:
    """Tests for MobileSession."""

    def test_session_creation(self):
        """Test session creation with defaults."""
        session = MobileSession(
            session_id="test123",
            device_id="device456",
            user_id="user789",
            access_token="access_token",
            refresh_token="refresh_token",
        )

        assert session.session_id == "test123"
        assert not session.is_expired
        assert not session.is_refresh_expired
        assert session.expires_at > session.created_at
        assert session.refresh_expires_at > session.expires_at

    def test_session_to_dict(self):
        """Test session serialization."""
        session = MobileSession(
            session_id="test123",
            device_id="device456",
            user_id="user789",
            access_token="access_token",
            refresh_token="refresh_token",
        )

        data = session.to_dict()

        assert data["session_id"] == "test123"
        assert "access_token" not in data  # Tokens not in dict
        assert "refresh_token" not in data


# =============================================================================
# Sync Manager Tests
# =============================================================================

class TestMobileSyncManager:
    """Tests for MobileSyncManager."""

    def setup_method(self):
        """Create fresh manager."""
        self.manager = MobileSyncManager()

    def test_get_sync_state(self):
        """Test getting sync state."""
        state = self.manager.get_sync_state("device123")

        assert state.version >= 0
        assert state.timestamp > 0
        assert isinstance(state.cognitive_state, dict)
        assert isinstance(state.projects, list)
        assert len(state.checksum) == 16

    def test_sync_state_has_cognitive_state(self):
        """Test sync state includes cognitive state."""
        state = self.manager.get_sync_state("device123")

        assert "active_mode" in state.cognitive_state
        assert "burnout_level" in state.cognitive_state
        assert "momentum_phase" in state.cognitive_state

    def test_sync_state_to_dict(self):
        """Test sync state serialization."""
        state = self.manager.get_sync_state("device123")
        data = state.to_dict()

        assert "version" in data
        assert "timestamp" in data
        assert "cognitive_state" in data
        assert "checksum" in data


# =============================================================================
# Command Executor Tests
# =============================================================================

class TestMobileCommandExecutor:
    """Tests for MobileCommandExecutor."""

    def setup_method(self):
        """Create fresh executor."""
        self.executor = MobileCommandExecutor()

    @pytest.mark.asyncio
    async def test_execute_health_command(self):
        """Test health command execution."""
        result = await self.executor.execute("health")

        assert result.success
        assert result.command == "health"
        assert "status" in result.result
        assert result.execution_time_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_info_command(self):
        """Test info command execution."""
        result = await self.executor.execute("info")

        assert result.success
        assert result.result["name"] == "OTTO OS"
        assert "version" in result.result

    @pytest.mark.asyncio
    async def test_execute_secure_command(self):
        """Test secure command execution."""
        result = await self.executor.execute("secure", {"action": "status"})

        assert result.success
        assert "algorithm" in result.result

    @pytest.mark.asyncio
    async def test_execute_state_command(self):
        """Test state command execution."""
        result = await self.executor.execute("state")

        assert result.success
        assert "active_mode" in result.result

    @pytest.mark.asyncio
    async def test_execute_projects_command(self):
        """Test projects command execution."""
        result = await self.executor.execute("projects")

        assert result.success
        assert "projects" in result.result

    @pytest.mark.asyncio
    async def test_execute_help_command(self):
        """Test help command execution."""
        result = await self.executor.execute("help")

        assert result.success
        assert "commands" in result.result
        assert "health" in result.result["commands"]

    @pytest.mark.asyncio
    async def test_execute_unknown_command(self):
        """Test unknown command execution."""
        result = await self.executor.execute("unknown_cmd")

        assert not result.success
        assert result.error is not None

    def test_command_result_to_dict(self):
        """Test command result serialization."""
        result = CommandResult(
            success=True,
            command="test",
            result={"key": "value"},
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["command"] == "test"


# =============================================================================
# Mobile API Tests
# =============================================================================

class TestMobileAPI:
    """Tests for MobileAPI."""

    def setup_method(self):
        """Create fresh API."""
        reset_mobile_api()
        self.api = MobileAPI()

    @pytest.mark.asyncio
    async def test_register_device(self):
        """Test device registration via API."""
        result = await self.api.register_device(
            device_type="ios",
            device_name="Test iPhone",
            os_version="17.0",
        )

        assert "device_id" in result
        assert "otp" in result
        assert result["next_step"] == "verify"

    @pytest.mark.asyncio
    async def test_register_device_invalid_type(self):
        """Test registration with invalid device type."""
        result = await self.api.register_device(
            device_type="invalid",
            device_name="Test",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_verify_device(self):
        """Test device verification via API."""
        reg = await self.api.register_device("ios", "Test iPhone")

        result = await self.api.verify_device(
            device_id=reg["device_id"],
            otp=reg["otp"],
            user_id="testuser",
        )

        assert result["success"]
        assert "access_token" in result
        assert "refresh_token" in result

    @pytest.mark.asyncio
    async def test_verify_device_wrong_otp(self):
        """Test verification with wrong OTP."""
        reg = await self.api.register_device("ios", "Test iPhone")

        result = await self.api.verify_device(
            device_id=reg["device_id"],
            otp="000000",
            user_id="testuser",
        )

        assert not result["success"]
        assert "error" in result

    @pytest.mark.asyncio
    async def test_refresh_token(self):
        """Test token refresh via API."""
        reg = await self.api.register_device("ios", "Test iPhone")
        verify = await self.api.verify_device(reg["device_id"], reg["otp"], "user")

        result = await self.api.refresh_token(verify["refresh_token"])

        assert result["success"]
        assert "access_token" in result
        assert result["access_token"] != verify["access_token"]

    @pytest.mark.asyncio
    async def test_get_sync_state(self):
        """Test sync state via API."""
        result = await self.api.get_sync_state("device123")

        assert "version" in result
        assert "cognitive_state" in result
        assert "checksum" in result

    @pytest.mark.asyncio
    async def test_register_push(self):
        """Test push registration via API."""
        reg = await self.api.register_device("ios", "Test iPhone")
        await self.api.verify_device(reg["device_id"], reg["otp"], "user")

        result = await self.api.register_push(
            device_id=reg["device_id"],
            push_token="test_token",
            provider="apns",
        )

        assert result["success"]

    @pytest.mark.asyncio
    async def test_register_push_invalid_provider(self):
        """Test push registration with invalid provider."""
        result = await self.api.register_push(
            device_id="device",
            push_token="token",
            provider="invalid",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_unregister_push(self):
        """Test push unregistration via API."""
        reg = await self.api.register_device("ios", "Test iPhone")
        await self.api.verify_device(reg["device_id"], reg["otp"], "user")
        await self.api.register_push(reg["device_id"], "token", "apns")

        result = await self.api.unregister_push(reg["device_id"])

        assert result["success"]

    @pytest.mark.asyncio
    async def test_execute_command(self):
        """Test command execution via API."""
        result = await self.api.execute_command("health")

        assert result["success"]
        assert result["command"] == "health"

    @pytest.mark.asyncio
    async def test_get_crypto_capabilities(self):
        """Test getting crypto capabilities."""
        result = await self.api.get_crypto_capabilities()

        assert "classical" in result
        assert "post_quantum" in result
        assert "e2e" in result
        assert result["classical"]["available"] is True

    @pytest.mark.asyncio
    async def test_get_security_posture(self):
        """Test getting security posture."""
        result = await self.api.get_security_posture()

        # May return error if security posture API not configured
        assert "status" in result or "error" in result


# =============================================================================
# Routes Tests
# =============================================================================

class TestMobileRoutes:
    """Tests for mobile routes."""

    def test_get_mobile_routes(self):
        """Test getting mobile routes."""
        routes = get_mobile_routes()

        assert len(routes) > 0
        assert all(hasattr(r, "path_pattern") for r in routes)

    def test_routes_have_required_attributes(self):
        """Test routes have all required attributes."""
        routes = get_mobile_routes()

        for route in routes:
            assert route.method in ["GET", "POST", "DELETE", "PATCH"]
            assert route.path_pattern.startswith("/api/v1/")
            assert route.jsonrpc_method.startswith("otto.")
            assert route.rate_limit > 0

    def test_mobile_register_route_exists(self):
        """Test mobile register route exists."""
        routes = get_mobile_routes()
        paths = [r.path_pattern for r in routes]

        assert "/api/v1/mobile/register" in paths

    def test_mobile_sync_route_exists(self):
        """Test mobile sync route exists."""
        routes = get_mobile_routes()
        paths = [r.path_pattern for r in routes]

        assert "/api/v1/mobile/sync" in paths

    def test_security_routes_exist(self):
        """Test security routes exist."""
        routes = get_mobile_routes()
        paths = [r.path_pattern for r in routes]

        assert "/api/v1/security/posture" in paths
        assert "/api/v1/security/crypto" in paths

    def test_command_route_exists(self):
        """Test command execution route exists."""
        routes = get_mobile_routes()
        paths = [r.path_pattern for r in routes]

        assert "/api/v1/commands/:command" in paths


# =============================================================================
# Data Classes Tests
# =============================================================================

class TestDeviceInfo:
    """Tests for DeviceInfo."""

    def test_device_info_creation(self):
        """Test device info creation."""
        device = DeviceInfo(
            device_id="test123",
            device_type=DeviceType.IOS,
            device_name="iPhone 15",
            os_version="17.0",
        )

        assert device.device_id == "test123"
        assert device.device_type == DeviceType.IOS
        assert device.status == DeviceStatus.PENDING

    def test_device_info_to_dict(self):
        """Test device info serialization."""
        device = DeviceInfo(
            device_id="test123",
            device_type=DeviceType.ANDROID,
            device_name="Pixel 8",
            push_token="fcm_token",
            push_provider=PushProvider.FCM,
        )

        data = device.to_dict()

        assert data["device_id"] == "test123"
        assert data["device_type"] == "android"
        assert data["has_push"] is True
        assert data["push_provider"] == "fcm"


class TestCryptoCapabilities:
    """Tests for CryptoCapabilities."""

    def test_default_capabilities(self):
        """Test default crypto capabilities."""
        caps = CryptoCapabilities()

        assert caps.classical_available is True
        assert caps.pq_available is False

    def test_pq_enabled_capabilities(self):
        """Test PQ-enabled capabilities."""
        caps = CryptoCapabilities(
            pq_available=True,
            pq_algorithm="ML-KEM-768",
            hybrid_mode=True,
        )

        assert caps.pq_available is True
        assert caps.hybrid_mode is True

    def test_capabilities_to_dict(self):
        """Test capabilities serialization."""
        caps = CryptoCapabilities(
            pq_available=True,
            pq_algorithm="ML-KEM-768",
        )
        data = caps.to_dict()

        assert data["classical"]["available"] is True
        assert data["post_quantum"]["available"] is True
        assert data["post_quantum"]["algorithm"] == "ML-KEM-768"


class TestSyncState:
    """Tests for SyncState."""

    def test_sync_state_checksum(self):
        """Test sync state checksum generation."""
        state = SyncState(
            version=1,
            timestamp=time.time(),
            cognitive_state={"mode": "focused"},
            projects=[],
            notifications=[],
            pending_commands=[],
        )

        assert len(state.checksum) == 16
        assert state.checksum.isalnum()

    def test_sync_state_checksum_deterministic(self):
        """Test checksum is deterministic for same input."""
        base_args = {
            "version": 1,
            "timestamp": 1000.0,
            "cognitive_state": {"mode": "focused"},
            "projects": [],
            "notifications": [],
            "pending_commands": [],
        }

        state1 = SyncState(**base_args)
        state2 = SyncState(**base_args)

        assert state1.checksum == state2.checksum


# =============================================================================
# Singleton Tests
# =============================================================================

class TestMobileAPISingleton:
    """Tests for MobileAPI singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_mobile_api()

    def test_get_mobile_api(self):
        """Test getting mobile API singleton."""
        api1 = get_mobile_api()
        api2 = get_mobile_api()

        assert api1 is api2

    def test_reset_mobile_api(self):
        """Test resetting mobile API singleton."""
        api1 = get_mobile_api()
        reset_mobile_api()
        api2 = get_mobile_api()

        assert api1 is not api2
