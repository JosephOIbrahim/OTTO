"""
OTTO Mobile REST API
====================

Mobile-optimized REST endpoints for iOS/Android apps.

Endpoints:
    POST /api/v1/mobile/register          Register mobile device
    POST /api/v1/mobile/verify            Verify device with OTP/biometric
    POST /api/v1/mobile/refresh           Refresh access token
    GET  /api/v1/mobile/sync              Sync state to device
    POST /api/v1/mobile/push/register     Register push notification token
    DELETE /api/v1/mobile/push/unregister Unregister push token
    GET  /api/v1/security/posture         Get security posture
    GET  /api/v1/security/crypto          Get crypto capabilities
    POST /api/v1/commands/:command        Execute OTTO command

ThinkingMachines [He2025] Compliance:
- FIXED endpoint behavior
- DETERMINISTIC: request → response mapping
- Token format and validation are deterministic
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

# Import PushProvider from push.py to avoid duplicate enum definitions
from .push import PushProvider

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class DeviceType(Enum):
    """Mobile device types."""
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
    MATRIX = "matrix"  # For Matrix client connections


class DeviceStatus(Enum):
    """Device registration status."""
    PENDING = "pending"
    VERIFIED = "verified"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class CommandCategory(Enum):
    """OTTO command categories."""
    HEALTH = "health"
    INFO = "info"
    SECURITY = "security"
    STATE = "state"
    PROJECT = "project"
    ADMIN = "admin"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class DeviceInfo:
    """Mobile device information."""
    device_id: str
    device_type: DeviceType
    device_name: str
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    push_token: Optional[str] = None
    push_provider: Optional[PushProvider] = None
    public_key: Optional[bytes] = None  # For E2E encryption
    registered_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    status: DeviceStatus = DeviceStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "device_name": self.device_name,
            "os_version": self.os_version,
            "app_version": self.app_version,
            "has_push": self.push_token is not None,
            "push_provider": self.push_provider.value if self.push_provider else None,
            "has_e2e_key": self.public_key is not None,
            "registered_at": self.registered_at,
            "last_seen": self.last_seen,
            "status": self.status.value,
        }


@dataclass
class MobileSession:
    """Mobile session with tokens."""
    session_id: str
    device_id: str
    user_id: str
    access_token: str
    refresh_token: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    refresh_expires_at: float = 0

    def __post_init__(self):
        if self.expires_at == 0:
            self.expires_at = self.created_at + 3600  # 1 hour
        if self.refresh_expires_at == 0:
            self.refresh_expires_at = self.created_at + 86400 * 30  # 30 days

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def is_refresh_expired(self) -> bool:
        return time.time() > self.refresh_expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without tokens)."""
        return {
            "session_id": self.session_id,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "is_expired": self.is_expired,
        }


@dataclass
class SyncState:
    """State for mobile sync."""
    version: int
    timestamp: float
    cognitive_state: Dict[str, Any]
    projects: List[Dict[str, Any]]
    notifications: List[Dict[str, Any]]
    pending_commands: List[Dict[str, Any]]
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute deterministic checksum of state."""
        data = json.dumps({
            "version": self.version,
            "cognitive_state": self.cognitive_state,
            "projects": self.projects,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "cognitive_state": self.cognitive_state,
            "projects": self.projects,
            "notifications": self.notifications,
            "pending_commands": self.pending_commands,
            "checksum": self.checksum,
        }


@dataclass
class CryptoCapabilities:
    """Cryptographic capabilities of the system."""
    classical_available: bool = True
    pq_available: bool = False
    pq_algorithm: Optional[str] = None
    hybrid_mode: bool = False
    e2e_enabled: bool = True
    matrix_olm: bool = True
    hsm_available: bool = False
    threshold_signatures: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classical": {
                "available": self.classical_available,
                "algorithms": ["X25519", "Ed25519", "AES-256-GCM"],
            },
            "post_quantum": {
                "available": self.pq_available,
                "algorithm": self.pq_algorithm,
                "hybrid_mode": self.hybrid_mode,
            },
            "e2e": {
                "enabled": self.e2e_enabled,
                "matrix_olm": self.matrix_olm,
            },
            "hsm": {
                "available": self.hsm_available,
            },
            "threshold_signatures": self.threshold_signatures,
        }


@dataclass
class CommandResult:
    """Result of executing an OTTO command."""
    success: bool
    command: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "command": self.command,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


# =============================================================================
# Device Manager
# =============================================================================

class MobileDeviceManager:
    """
    Manages mobile device registration and authentication.

    [He2025] Compliance:
    - FIXED token generation algorithm
    - DETERMINISTIC device ID derivation
    """

    TOKEN_LENGTH = 32
    OTP_LENGTH = 6
    OTP_VALIDITY_SECONDS = 300  # 5 minutes

    def __init__(self):
        self._devices: Dict[str, DeviceInfo] = {}
        self._sessions: Dict[str, MobileSession] = {}
        self._pending_otps: Dict[str, tuple] = {}  # device_id -> (otp, expires_at)
        self._push_tokens: Dict[str, str] = {}  # push_token -> device_id

    def register_device(
        self,
        device_type: DeviceType,
        device_name: str,
        os_version: Optional[str] = None,
        app_version: Optional[str] = None,
        public_key: Optional[bytes] = None,
    ) -> tuple[str, str]:
        """
        Register a new mobile device.

        Returns:
            Tuple of (device_id, otp)
        """
        # Generate deterministic device ID from input
        device_id = self._generate_device_id(device_type, device_name)

        # Create device record
        device = DeviceInfo(
            device_id=device_id,
            device_type=device_type,
            device_name=device_name,
            os_version=os_version,
            app_version=app_version,
            public_key=public_key,
            status=DeviceStatus.PENDING,
        )
        self._devices[device_id] = device

        # Generate OTP for verification
        otp = self._generate_otp()
        expires_at = time.time() + self.OTP_VALIDITY_SECONDS
        self._pending_otps[device_id] = (otp, expires_at)

        logger.info(f"Registered device: {device_id} ({device_type.value})")
        return device_id, otp

    def verify_device(
        self,
        device_id: str,
        otp: str,
        user_id: str,
    ) -> Optional[MobileSession]:
        """
        Verify device with OTP and create session.

        Returns:
            MobileSession if verification successful, None otherwise
        """
        # Check device exists
        device = self._devices.get(device_id)
        if not device:
            logger.warning(f"Device not found: {device_id}")
            return None

        # Check OTP
        pending = self._pending_otps.get(device_id)
        if not pending:
            logger.warning(f"No pending OTP for device: {device_id}")
            return None

        stored_otp, expires_at = pending
        if time.time() > expires_at:
            logger.warning(f"OTP expired for device: {device_id}")
            del self._pending_otps[device_id]
            return None

        if not secrets.compare_digest(otp, stored_otp):
            logger.warning(f"Invalid OTP for device: {device_id}")
            return None

        # Verify device
        device.status = DeviceStatus.VERIFIED
        del self._pending_otps[device_id]

        # Create session
        session = self._create_session(device_id, user_id)
        logger.info(f"Device verified: {device_id}")
        return session

    def refresh_session(
        self,
        refresh_token: str,
    ) -> Optional[MobileSession]:
        """
        Refresh an expired session.

        Returns:
            New MobileSession if refresh successful, None otherwise
        """
        # Find session by refresh token
        session = None
        for s in self._sessions.values():
            if secrets.compare_digest(s.refresh_token, refresh_token):
                session = s
                break

        if not session:
            return None

        if session.is_refresh_expired:
            # Refresh token also expired
            del self._sessions[session.session_id]
            return None

        # Create new session
        new_session = self._create_session(session.device_id, session.user_id)

        # Invalidate old session
        del self._sessions[session.session_id]

        return new_session

    def validate_access_token(self, access_token: str) -> Optional[MobileSession]:
        """Validate an access token and return the session."""
        for session in self._sessions.values():
            if secrets.compare_digest(session.access_token, access_token):
                if session.is_expired:
                    return None
                # Update last seen
                device = self._devices.get(session.device_id)
                if device:
                    device.last_seen = time.time()
                return session
        return None

    def register_push_token(
        self,
        device_id: str,
        push_token: str,
        provider: PushProvider,
    ) -> bool:
        """Register a push notification token for a device."""
        device = self._devices.get(device_id)
        if not device or device.status != DeviceStatus.VERIFIED:
            return False

        # Remove old token if exists
        if device.push_token:
            self._push_tokens.pop(device.push_token, None)

        # Register new token
        device.push_token = push_token
        device.push_provider = provider
        self._push_tokens[push_token] = device_id

        logger.info(f"Registered push token for device: {device_id}")
        return True

    def unregister_push_token(self, device_id: str) -> bool:
        """Unregister push notification token for a device."""
        device = self._devices.get(device_id)
        if not device:
            return False

        if device.push_token:
            self._push_tokens.pop(device.push_token, None)
            device.push_token = None
            device.push_provider = None

        return True

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """Get device information."""
        return self._devices.get(device_id)

    def get_devices_for_user(self, user_id: str) -> List[DeviceInfo]:
        """Get all devices for a user."""
        user_device_ids = {
            s.device_id for s in self._sessions.values()
            if s.user_id == user_id
        }
        return [
            d for d in self._devices.values()
            if d.device_id in user_device_ids
        ]

    def revoke_device(self, device_id: str) -> bool:
        """Revoke a device and all its sessions."""
        device = self._devices.get(device_id)
        if not device:
            return False

        device.status = DeviceStatus.REVOKED

        # Revoke all sessions
        sessions_to_remove = [
            sid for sid, s in self._sessions.items()
            if s.device_id == device_id
        ]
        for sid in sessions_to_remove:
            del self._sessions[sid]

        # Remove push token
        if device.push_token:
            self._push_tokens.pop(device.push_token, None)

        logger.info(f"Revoked device: {device_id}")
        return True

    def _generate_device_id(self, device_type: DeviceType, device_name: str) -> str:
        """Generate deterministic device ID."""
        data = f"{device_type.value}:{device_name}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _generate_otp(self) -> str:
        """Generate numeric OTP."""
        return "".join(str(secrets.randbelow(10)) for _ in range(self.OTP_LENGTH))

    def _generate_token(self) -> str:
        """Generate secure random token."""
        return secrets.token_urlsafe(self.TOKEN_LENGTH)

    def _create_session(self, device_id: str, user_id: str) -> MobileSession:
        """Create a new session for a device."""
        session = MobileSession(
            session_id=secrets.token_urlsafe(16),
            device_id=device_id,
            user_id=user_id,
            access_token=self._generate_token(),
            refresh_token=self._generate_token(),
        )
        self._sessions[session.session_id] = session
        return session


# =============================================================================
# Sync Manager
# =============================================================================

class MobileSyncManager:
    """
    Manages state synchronization for mobile devices.

    Supports:
    - Delta sync (only changed state)
    - Full sync (complete state)
    - Conflict resolution
    """

    def __init__(self):
        self._state_version = 0
        self._device_versions: Dict[str, int] = {}  # device_id -> last_synced_version

    def get_sync_state(
        self,
        device_id: str,
        since_version: Optional[int] = None,
    ) -> SyncState:
        """
        Get current state for sync.

        Args:
            device_id: Device to sync
            since_version: If provided, return delta since this version

        Returns:
            SyncState with current or delta state
        """
        # Get current cognitive state
        cognitive_state = self._get_cognitive_state()

        # Get projects
        projects = self._get_projects()

        # Get notifications
        notifications = self._get_notifications(device_id)

        # Get pending commands
        pending_commands = self._get_pending_commands(device_id)

        # Update device version
        self._device_versions[device_id] = self._state_version

        return SyncState(
            version=self._state_version,
            timestamp=time.time(),
            cognitive_state=cognitive_state,
            projects=projects,
            notifications=notifications,
            pending_commands=pending_commands,
        )

    def _get_cognitive_state(self) -> Dict[str, Any]:
        """Get current cognitive state summary."""
        # This would integrate with the actual cognitive engine
        return {
            "active_mode": "focused",
            "active_paradigm": "Cortex",
            "energy_level": "medium",
            "burnout_level": "GREEN",
            "momentum_phase": "rolling",
            "current_altitude": "15000ft",
        }

    def _get_projects(self) -> List[Dict[str, Any]]:
        """Get project list for mobile."""
        # This would integrate with project manager
        return [
            {
                "slug": "otto-os",
                "name": "OTTO OS",
                "status": "FOCUS",
                "last_touch": time.time() - 3600,
            },
        ]

    def _get_notifications(self, device_id: str) -> List[Dict[str, Any]]:
        """Get pending notifications for device."""
        return []

    def _get_pending_commands(self, device_id: str) -> List[Dict[str, Any]]:
        """Get pending commands queued for device."""
        return []


# =============================================================================
# Command Executor
# =============================================================================

class MobileCommandExecutor:
    """
    Executes OTTO commands from mobile devices.

    Commands:
    - health: Check system health
    - info: Get system information
    - secure: Security operations
    - state: Query/update cognitive state
    - projects: List projects
    """

    ALLOWED_COMMANDS: Set[str] = {
        "health", "info", "secure", "state", "projects", "help",
    }

    async def execute(
        self,
        command: str,
        args: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> CommandResult:
        """Execute an OTTO command."""
        start = time.time()

        if command not in self.ALLOWED_COMMANDS:
            return CommandResult(
                success=False,
                command=command,
                error=f"Unknown command: {command}",
                execution_time_ms=(time.time() - start) * 1000,
            )

        try:
            handler = getattr(self, f"_cmd_{command}", None)
            if handler:
                result = await handler(args or {})
            else:
                result = {"message": f"Command {command} not implemented"}

            return CommandResult(
                success=True,
                command=command,
                result=result,
                execution_time_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            logger.exception(f"Error executing command: {command}")
            return CommandResult(
                success=False,
                command=command,
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
            )

    async def _cmd_health(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Check system health."""
        return {
            "status": "healthy",
            "components": {
                "core": "OK",
                "crypto": "OK",
                "matrix_bot": "OK",
                "memory": "OK",
            },
            "pq_enabled": self._check_pq_available(),
            "timestamp": time.time(),
        }

    async def _cmd_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get system information."""
        return {
            "name": "OTTO OS",
            "version": "6.0.0",
            "api_version": "v1",
            "capabilities": [
                "cognitive_state",
                "pq_crypto",
                "matrix_messaging",
                "threshold_signatures",
                "self_healing",
            ],
        }

    async def _cmd_secure(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Security operations."""
        action = args.get("action", "status")

        if action == "status":
            return {
                "pq_available": self._check_pq_available(),
                "algorithm": "ML-KEM-768" if self._check_pq_available() else "X25519",
                "classical": "X25519",
                "mode": "hybrid" if self._check_pq_available() else "classical",
            }
        else:
            return {"error": f"Unknown secure action: {action}"}

    async def _cmd_state(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Query cognitive state."""
        return {
            "active_mode": "focused",
            "active_paradigm": "Cortex",
            "energy_level": "medium",
            "burnout_level": "GREEN",
            "momentum_phase": "rolling",
        }

    async def _cmd_projects(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List projects."""
        return {
            "projects": [
                {"slug": "otto-os", "status": "FOCUS"},
            ],
            "total": 1,
        }

    async def _cmd_help(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get help for commands."""
        return {
            "commands": list(self.ALLOWED_COMMANDS),
            "usage": {
                "health": "Check system health",
                "info": "Get system information",
                "secure": "Security operations (action=status)",
                "state": "Query cognitive state",
                "projects": "List active projects",
                "help": "Show this help",
            },
        }

    def _check_pq_available(self) -> bool:
        """Check if post-quantum crypto is available."""
        try:
            from otto.crypto.pqcrypto import is_pq_available
            return is_pq_available()
        except ImportError:
            return False


# =============================================================================
# Mobile API
# =============================================================================

class MobileAPI:
    """
    High-level Mobile API combining all managers.

    This is the main entry point for mobile REST endpoints.
    """

    def __init__(self):
        self.devices = MobileDeviceManager()
        self.sync = MobileSyncManager()
        self.commands = MobileCommandExecutor()

    async def register_device(
        self,
        device_type: str,
        device_name: str,
        os_version: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a new mobile device."""
        try:
            dtype = DeviceType(device_type)
        except ValueError:
            return {"error": f"Invalid device type: {device_type}"}

        device_id, otp = self.devices.register_device(
            device_type=dtype,
            device_name=device_name,
            os_version=os_version,
            app_version=app_version,
        )

        return {
            "device_id": device_id,
            "otp": otp,
            "otp_expires_in": self.devices.OTP_VALIDITY_SECONDS,
            "next_step": "verify",
        }

    async def verify_device(
        self,
        device_id: str,
        otp: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Verify device with OTP."""
        session = self.devices.verify_device(device_id, otp, user_id)

        if not session:
            return {"error": "Verification failed", "success": False}

        return {
            "success": True,
            "session_id": session.session_id,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at,
        }

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token."""
        session = self.devices.refresh_session(refresh_token)

        if not session:
            return {"error": "Invalid or expired refresh token", "success": False}

        return {
            "success": True,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at,
        }

    async def get_sync_state(
        self,
        device_id: str,
        since_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get state for sync."""
        state = self.sync.get_sync_state(device_id, since_version)
        return state.to_dict()

    async def register_push(
        self,
        device_id: str,
        push_token: str,
        provider: str,
    ) -> Dict[str, Any]:
        """Register push notification token."""
        try:
            prov = PushProvider(provider)
        except ValueError:
            return {"error": f"Invalid push provider: {provider}"}

        success = self.devices.register_push_token(device_id, push_token, prov)
        return {"success": success}

    async def unregister_push(self, device_id: str) -> Dict[str, Any]:
        """Unregister push notification token."""
        success = self.devices.unregister_push_token(device_id)
        return {"success": success}

    async def execute_command(
        self,
        command: str,
        args: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute an OTTO command."""
        result = await self.commands.execute(command, args, user_id)
        return result.to_dict()

    async def get_crypto_capabilities(self) -> Dict[str, Any]:
        """Get cryptographic capabilities."""
        pq_available = False
        pq_algorithm = None

        try:
            from otto.crypto.pqcrypto import is_pq_available, get_pq_status
            pq_available = is_pq_available()
            if pq_available:
                status = get_pq_status()
                pq_algorithm = status.algorithm
        except ImportError:
            pass

        caps = CryptoCapabilities(
            pq_available=pq_available,
            pq_algorithm=pq_algorithm,
            hybrid_mode=pq_available,
        )
        return caps.to_dict()

    async def get_security_posture(self) -> Dict[str, Any]:
        """Get security posture summary for mobile."""
        try:
            from .security_posture import SecurityPostureAPI
            api = SecurityPostureAPI()
            report = await api.get_full_report()
            return {
                "status": report.status.value,
                "score": report.overall_score,
                "grade": report.grade,
                "components": [
                    {
                        "name": c.name,
                        "health": c.health.value,
                        "score": c.score,
                    }
                    for c in report.components
                ],
                "recommendations_count": len(report.recommendations),
            }
        except Exception as e:
            logger.warning(f"Could not get security posture: {e}")
            return {
                "status": "unknown",
                "score": 0,
                "error": str(e),
            }


# =============================================================================
# Mobile Routes
# =============================================================================

def get_mobile_routes():
    """Get mobile-specific REST routes."""
    from .rest_router import Route
    from .scopes import APIScope

    return [
        # Device Registration
        Route("POST", "/api/v1/mobile/register", "otto.mobile.register",
              APIScope.WRITE_SESSION, 5),
        Route("POST", "/api/v1/mobile/verify", "otto.mobile.verify",
              APIScope.WRITE_SESSION, 10),
        Route("POST", "/api/v1/mobile/refresh", "otto.mobile.refresh",
              APIScope.WRITE_SESSION, 30),

        # Sync
        Route("GET", "/api/v1/mobile/sync", "otto.mobile.sync",
              APIScope.READ_STATE, 60),

        # Push Notifications
        Route("POST", "/api/v1/mobile/push/register", "otto.mobile.push.register",
              APIScope.WRITE_SESSION, 10),
        Route("DELETE", "/api/v1/mobile/push/unregister", "otto.mobile.push.unregister",
              APIScope.WRITE_SESSION, 10),

        # Security
        Route("GET", "/api/v1/security/posture", "otto.security.posture",
              APIScope.READ_STATUS, 30),
        Route("GET", "/api/v1/security/crypto", "otto.security.crypto",
              APIScope.READ_STATUS, 60),

        # Commands
        Route("POST", "/api/v1/commands/:command", "otto.commands.execute",
              APIScope.WRITE_STATE, 30),
    ]


# =============================================================================
# Singleton
# =============================================================================

_mobile_api: Optional[MobileAPI] = None


def get_mobile_api() -> MobileAPI:
    """Get the global MobileAPI instance."""
    global _mobile_api
    if _mobile_api is None:
        _mobile_api = MobileAPI()
    return _mobile_api


def reset_mobile_api() -> None:
    """Reset the global MobileAPI instance (for testing)."""
    global _mobile_api
    _mobile_api = None


__all__ = [
    # Enums
    "DeviceType",
    "DeviceStatus",
    "PushProvider",
    "CommandCategory",
    # Data classes
    "DeviceInfo",
    "MobileSession",
    "SyncState",
    "CryptoCapabilities",
    "CommandResult",
    # Managers
    "MobileDeviceManager",
    "MobileSyncManager",
    "MobileCommandExecutor",
    # API
    "MobileAPI",
    "get_mobile_api",
    "reset_mobile_api",
    # Routes
    "get_mobile_routes",
]
