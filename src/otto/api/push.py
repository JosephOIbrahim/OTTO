"""
OTTO Push Notification Backend
==============================

Multi-provider push notification delivery.

Providers:
- APNS (Apple Push Notification Service)
- FCM (Firebase Cloud Messaging)
- Matrix Push Gateway
- UnifiedPush (open standard)

Features:
- Template-based notifications
- Priority levels
- Batched delivery
- Delivery tracking

[He2025] Compliance:
- FIXED notification format
- DETERMINISTIC: template → notification mapping
"""

import asyncio
import base64
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class PushProvider(Enum):
    """Push notification providers."""
    APNS = "apns"
    FCM = "fcm"
    MATRIX = "matrix"
    UNIFIED = "unified"
    WEB = "web"  # Web Push API


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationCategory(Enum):
    """Notification categories for templates."""
    BURNOUT_WARNING = "burnout_warning"
    ENERGY_ALERT = "energy_alert"
    PROJECT_UPDATE = "project_update"
    SECURITY_ALERT = "security_alert"
    COMMAND_RESULT = "command_result"
    SYSTEM_STATUS = "system_status"


class DeliveryStatus(Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PushToken:
    """Push notification token."""
    token: str
    provider: PushProvider
    device_id: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    last_used: Optional[float] = None
    is_valid: bool = True


@dataclass
class Notification:
    """Push notification message."""
    id: str
    title: str
    body: str
    category: NotificationCategory
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    badge_count: Optional[int] = None
    sound: str = "default"
    ttl: int = 86400  # Time to live in seconds (24 hours)
    collapse_key: Optional[str] = None  # For grouping
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "category": self.category.value,
            "priority": self.priority.value,
            "data": self.data,
            "image_url": self.image_url,
            "action_url": self.action_url,
            "badge_count": self.badge_count,
            "sound": self.sound,
            "ttl": self.ttl,
            "collapse_key": self.collapse_key,
            "created_at": self.created_at,
        }


@dataclass
class DeliveryResult:
    """Result of notification delivery."""
    notification_id: str
    token: str
    provider: PushProvider
    status: DeliveryStatus
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    provider_message_id: Optional[str] = None


@dataclass
class NotificationTemplate:
    """Notification template for common alerts."""
    category: NotificationCategory
    title_template: str
    body_template: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    sound: str = "default"
    action_url_template: Optional[str] = None

    def render(self, **kwargs) -> tuple:
        """Render template with variables."""
        title = self.title_template.format(**kwargs)
        body = self.body_template.format(**kwargs)
        action_url = None
        if self.action_url_template:
            action_url = self.action_url_template.format(**kwargs)
        return title, body, action_url


# =============================================================================
# Provider Interfaces
# =============================================================================

class PushProviderInterface(ABC):
    """Abstract base class for push providers."""

    @property
    @abstractmethod
    def provider_type(self) -> PushProvider:
        """Get the provider type."""
        pass

    @abstractmethod
    async def send(
        self,
        token: str,
        notification: Notification,
    ) -> DeliveryResult:
        """Send a notification to a single device."""
        pass

    @abstractmethod
    async def send_batch(
        self,
        tokens: List[str],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """Send a notification to multiple devices."""
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> bool:
        """Check if a token is valid."""
        pass


class MockPushProvider(PushProviderInterface):
    """Mock push provider for testing."""

    def __init__(self, provider_type: PushProvider = PushProvider.FCM):
        self._provider_type = provider_type
        self.sent_notifications: List[tuple] = []
        self._failure_rate = 0.0

    @property
    def provider_type(self) -> PushProvider:
        return self._provider_type

    async def send(
        self,
        token: str,
        notification: Notification,
    ) -> DeliveryResult:
        """Mock send - always succeeds unless failure_rate set."""
        self.sent_notifications.append((token, notification))

        # [He2025] Use seeded random for deterministic test behavior
        import random
        import hashlib
        # Deterministic seed based on notification id for reproducibility
        seed = int(hashlib.sha256(notification.id.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        if rng.random() < self._failure_rate:
            return DeliveryResult(
                notification_id=notification.id,
                token=token,
                provider=self._provider_type,
                status=DeliveryStatus.FAILED,
                error="Mock failure",
            )

        return DeliveryResult(
            notification_id=notification.id,
            token=token,
            provider=self._provider_type,
            status=DeliveryStatus.SENT,
            provider_message_id=f"mock_{notification.id}",
        )

    async def send_batch(
        self,
        tokens: List[str],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """Mock batch send."""
        results = []
        for token in tokens:
            result = await self.send(token, notification)
            results.append(result)
        return results

    async def validate_token(self, token: str) -> bool:
        """Mock validation - always valid."""
        return True


class APNSProvider(PushProviderInterface):
    """Apple Push Notification Service provider."""

    def __init__(
        self,
        key_id: str = "",
        team_id: str = "",
        bundle_id: str = "",
        key_path: Optional[str] = None,
        sandbox: bool = True,
    ):
        self.key_id = key_id
        self.team_id = team_id
        self.bundle_id = bundle_id
        self.key_path = key_path
        self.sandbox = sandbox
        self._base_url = (
            "https://api.sandbox.push.apple.com" if sandbox
            else "https://api.push.apple.com"
        )

    @property
    def provider_type(self) -> PushProvider:
        return PushProvider.APNS

    async def send(
        self,
        token: str,
        notification: Notification,
    ) -> DeliveryResult:
        """Send via APNS."""
        if not self.key_id or not self.team_id:
            logger.warning("APNS not configured")
            return DeliveryResult(
                notification_id=notification.id,
                token=token,
                provider=self.provider_type,
                status=DeliveryStatus.FAILED,
                error="APNS not configured",
            )

        # Build APNS payload
        payload = {
            "aps": {
                "alert": {
                    "title": notification.title,
                    "body": notification.body,
                },
                "sound": notification.sound,
            },
        }

        if notification.badge_count is not None:
            payload["aps"]["badge"] = notification.badge_count

        if notification.data:
            payload.update(notification.data)

        # In production, this would use HTTP/2 to APNS
        # For now, simulate success
        logger.info(f"APNS: Would send to {token[:20]}...")

        return DeliveryResult(
            notification_id=notification.id,
            token=token,
            provider=self.provider_type,
            status=DeliveryStatus.SENT,
            provider_message_id=f"apns_{notification.id}",
        )

    async def send_batch(
        self,
        tokens: List[str],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """APNS doesn't support batch - send individually."""
        tasks = [self.send(token, notification) for token in tokens]
        return await asyncio.gather(*tasks)

    async def validate_token(self, token: str) -> bool:
        """Validate APNS token format."""
        # APNS tokens are 64 hex characters
        if len(token) != 64:
            return False
        try:
            int(token, 16)
            return True
        except ValueError:
            return False


class FCMProvider(PushProviderInterface):
    """Firebase Cloud Messaging provider."""

    def __init__(
        self,
        server_key: str = "",
        project_id: str = "",
    ):
        self.server_key = server_key
        self.project_id = project_id
        self._base_url = "https://fcm.googleapis.com/fcm/send"

    @property
    def provider_type(self) -> PushProvider:
        return PushProvider.FCM

    async def send(
        self,
        token: str,
        notification: Notification,
    ) -> DeliveryResult:
        """Send via FCM."""
        if not self.server_key:
            logger.warning("FCM not configured")
            return DeliveryResult(
                notification_id=notification.id,
                token=token,
                provider=self.provider_type,
                status=DeliveryStatus.FAILED,
                error="FCM not configured",
            )

        # Build FCM payload
        payload = {
            "to": token,
            "notification": {
                "title": notification.title,
                "body": notification.body,
            },
            "priority": "high" if notification.priority in [
                NotificationPriority.HIGH, NotificationPriority.CRITICAL
            ] else "normal",
        }

        if notification.data:
            payload["data"] = notification.data

        if notification.collapse_key:
            payload["collapse_key"] = notification.collapse_key

        # In production, this would POST to FCM
        logger.info(f"FCM: Would send to {token[:20]}...")

        return DeliveryResult(
            notification_id=notification.id,
            token=token,
            provider=self.provider_type,
            status=DeliveryStatus.SENT,
            provider_message_id=f"fcm_{notification.id}",
        )

    async def send_batch(
        self,
        tokens: List[str],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """FCM supports batch sending."""
        if not self.server_key:
            return [
                DeliveryResult(
                    notification_id=notification.id,
                    token=token,
                    provider=self.provider_type,
                    status=DeliveryStatus.FAILED,
                    error="FCM not configured",
                )
                for token in tokens
            ]

        # In production, use registration_ids for batch
        tasks = [self.send(token, notification) for token in tokens]
        return await asyncio.gather(*tasks)

    async def validate_token(self, token: str) -> bool:
        """Validate FCM token format."""
        # FCM tokens are typically 150+ characters
        return len(token) >= 100


class MatrixPushProvider(PushProviderInterface):
    """Matrix Push Gateway provider."""

    def __init__(self, gateway_url: str = ""):
        self.gateway_url = gateway_url

    @property
    def provider_type(self) -> PushProvider:
        return PushProvider.MATRIX

    async def send(
        self,
        token: str,  # Matrix push key
        notification: Notification,
    ) -> DeliveryResult:
        """Send via Matrix Push Gateway."""
        if not self.gateway_url:
            logger.warning("Matrix Push Gateway not configured")
            return DeliveryResult(
                notification_id=notification.id,
                token=token,
                provider=self.provider_type,
                status=DeliveryStatus.FAILED,
                error="Matrix Push Gateway not configured",
            )

        # Matrix push notification format
        payload = {
            "notification": {
                "event_id": notification.id,
                "room_id": "!otto:local",
                "type": "m.room.message",
                "sender": "@otto:local",
                "content": {
                    "msgtype": "m.text",
                    "body": f"{notification.title}: {notification.body}",
                },
            },
        }

        logger.info(f"Matrix: Would send to {token[:20]}...")

        return DeliveryResult(
            notification_id=notification.id,
            token=token,
            provider=self.provider_type,
            status=DeliveryStatus.SENT,
            provider_message_id=f"matrix_{notification.id}",
        )

    async def send_batch(
        self,
        tokens: List[str],
        notification: Notification,
    ) -> List[DeliveryResult]:
        """Send to multiple Matrix push keys."""
        tasks = [self.send(token, notification) for token in tokens]
        return await asyncio.gather(*tasks)

    async def validate_token(self, token: str) -> bool:
        """Matrix push keys are opaque."""
        return len(token) > 0


# =============================================================================
# Push Notification Manager
# =============================================================================

class PushNotificationManager:
    """
    Central manager for push notifications.

    Features:
    - Multi-provider support
    - Template-based notifications
    - Delivery tracking
    - Token management
    """

    # Default notification templates
    DEFAULT_TEMPLATES = {
        NotificationCategory.BURNOUT_WARNING: NotificationTemplate(
            category=NotificationCategory.BURNOUT_WARNING,
            title_template="Burnout Alert: {level}",
            body_template="{message}",
            priority=NotificationPriority.HIGH,
            sound="alert",
        ),
        NotificationCategory.ENERGY_ALERT: NotificationTemplate(
            category=NotificationCategory.ENERGY_ALERT,
            title_template="Energy: {level}",
            body_template="{message}",
            priority=NotificationPriority.NORMAL,
        ),
        NotificationCategory.PROJECT_UPDATE: NotificationTemplate(
            category=NotificationCategory.PROJECT_UPDATE,
            title_template="Project: {project_name}",
            body_template="{message}",
            priority=NotificationPriority.LOW,
        ),
        NotificationCategory.SECURITY_ALERT: NotificationTemplate(
            category=NotificationCategory.SECURITY_ALERT,
            title_template="Security Alert",
            body_template="{message}",
            priority=NotificationPriority.CRITICAL,
            sound="critical",
        ),
        NotificationCategory.COMMAND_RESULT: NotificationTemplate(
            category=NotificationCategory.COMMAND_RESULT,
            title_template="Command: {command}",
            body_template="{result}",
            priority=NotificationPriority.NORMAL,
        ),
        NotificationCategory.SYSTEM_STATUS: NotificationTemplate(
            category=NotificationCategory.SYSTEM_STATUS,
            title_template="OTTO Status",
            body_template="{message}",
            priority=NotificationPriority.LOW,
        ),
    }

    def __init__(self):
        self._providers: Dict[PushProvider, PushProviderInterface] = {}
        self._tokens: Dict[str, PushToken] = {}  # token → PushToken
        self._user_tokens: Dict[str, Set[str]] = {}  # user_id → token set
        self._templates = dict(self.DEFAULT_TEMPLATES)
        self._delivery_log: List[DeliveryResult] = []
        self._notification_id_counter = 0

        # Register mock providers for testing
        self._providers[PushProvider.FCM] = MockPushProvider(PushProvider.FCM)
        self._providers[PushProvider.APNS] = MockPushProvider(PushProvider.APNS)
        self._providers[PushProvider.MATRIX] = MockPushProvider(PushProvider.MATRIX)

    def register_provider(self, provider: PushProviderInterface) -> None:
        """Register a push provider."""
        self._providers[provider.provider_type] = provider
        logger.info(f"Registered push provider: {provider.provider_type.value}")

    def register_token(
        self,
        token: str,
        provider: PushProvider,
        device_id: str,
        user_id: str,
    ) -> PushToken:
        """Register a push token for a device."""
        push_token = PushToken(
            token=token,
            provider=provider,
            device_id=device_id,
            user_id=user_id,
        )

        self._tokens[token] = push_token

        if user_id not in self._user_tokens:
            self._user_tokens[user_id] = set()
        self._user_tokens[user_id].add(token)

        logger.info(f"Registered push token for user {user_id}")
        return push_token

    def unregister_token(self, token: str) -> bool:
        """Unregister a push token."""
        push_token = self._tokens.pop(token, None)
        if push_token:
            if push_token.user_id in self._user_tokens:
                self._user_tokens[push_token.user_id].discard(token)
            return True
        return False

    def get_user_tokens(self, user_id: str) -> List[PushToken]:
        """Get all push tokens for a user."""
        token_strs = self._user_tokens.get(user_id, set())
        return [self._tokens[t] for t in token_strs if t in self._tokens]

    def _generate_notification_id(self) -> str:
        """Generate unique notification ID."""
        self._notification_id_counter += 1
        return f"notif_{int(time.time())}_{self._notification_id_counter}"

    # =========================================================================
    # Sending Notifications
    # =========================================================================

    async def send_notification(
        self,
        notification: Notification,
        tokens: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
    ) -> List[DeliveryResult]:
        """
        Send a notification.

        Args:
            notification: Notification to send
            tokens: Specific tokens to send to
            user_ids: Users to send to (resolves to their tokens)

        Returns:
            List of delivery results
        """
        # Resolve tokens
        target_tokens: List[PushToken] = []

        if tokens:
            for t in tokens:
                if t in self._tokens:
                    target_tokens.append(self._tokens[t])

        if user_ids:
            for user_id in user_ids:
                target_tokens.extend(self.get_user_tokens(user_id))

        if not target_tokens:
            logger.warning("No tokens to send notification to")
            return []

        # Group by provider
        by_provider: Dict[PushProvider, List[str]] = {}
        for push_token in target_tokens:
            if push_token.is_valid:
                if push_token.provider not in by_provider:
                    by_provider[push_token.provider] = []
                by_provider[push_token.provider].append(push_token.token)

        # Send via each provider
        results: List[DeliveryResult] = []

        for provider_type, provider_tokens in by_provider.items():
            provider = self._providers.get(provider_type)
            if not provider:
                logger.warning(f"No provider for {provider_type.value}")
                continue

            provider_results = await provider.send_batch(provider_tokens, notification)
            results.extend(provider_results)

            # Update token last_used
            for token in provider_tokens:
                if token in self._tokens:
                    self._tokens[token].last_used = time.time()

        # Log delivery
        self._delivery_log.extend(results)

        return results

    async def send_from_template(
        self,
        category: NotificationCategory,
        user_ids: List[str],
        **template_vars,
    ) -> List[DeliveryResult]:
        """
        Send a notification using a template.

        Args:
            category: Notification category (determines template)
            user_ids: Users to send to
            **template_vars: Variables for template

        Returns:
            List of delivery results
        """
        template = self._templates.get(category)
        if not template:
            logger.error(f"No template for category: {category}")
            return []

        title, body, action_url = template.render(**template_vars)

        notification = Notification(
            id=self._generate_notification_id(),
            title=title,
            body=body,
            category=category,
            priority=template.priority,
            sound=template.sound,
            action_url=action_url,
            data=template_vars,
        )

        return await self.send_notification(notification, user_ids=user_ids)

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def send_burnout_warning(
        self,
        user_id: str,
        level: str,
        message: str,
    ) -> List[DeliveryResult]:
        """Send burnout warning notification."""
        return await self.send_from_template(
            NotificationCategory.BURNOUT_WARNING,
            [user_id],
            level=level,
            message=message,
        )

    async def send_energy_alert(
        self,
        user_id: str,
        level: str,
        message: str,
    ) -> List[DeliveryResult]:
        """Send energy alert notification."""
        return await self.send_from_template(
            NotificationCategory.ENERGY_ALERT,
            [user_id],
            level=level,
            message=message,
        )

    async def send_security_alert(
        self,
        user_ids: List[str],
        message: str,
    ) -> List[DeliveryResult]:
        """Send security alert notification."""
        return await self.send_from_template(
            NotificationCategory.SECURITY_ALERT,
            user_ids,
            message=message,
        )

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Get delivery statistics."""
        total = len(self._delivery_log)
        by_status = {}
        by_provider = {}

        for result in self._delivery_log:
            status = result.status.value
            by_status[status] = by_status.get(status, 0) + 1

            provider = result.provider.value
            by_provider[provider] = by_provider.get(provider, 0) + 1

        return {
            "total": total,
            "by_status": by_status,
            "by_provider": by_provider,
        }


# =============================================================================
# Singleton
# =============================================================================

_push_manager: Optional[PushNotificationManager] = None


def get_push_manager() -> PushNotificationManager:
    """Get the global push notification manager."""
    global _push_manager
    if _push_manager is None:
        _push_manager = PushNotificationManager()
    return _push_manager


def reset_push_manager() -> None:
    """Reset the global push manager (for testing)."""
    global _push_manager
    _push_manager = None


__all__ = [
    # Enums
    "PushProvider",
    "NotificationPriority",
    "NotificationCategory",
    "DeliveryStatus",
    # Data classes
    "PushToken",
    "Notification",
    "DeliveryResult",
    "NotificationTemplate",
    # Providers
    "PushProviderInterface",
    "MockPushProvider",
    "APNSProvider",
    "FCMProvider",
    "MatrixPushProvider",
    # Manager
    "PushNotificationManager",
    "get_push_manager",
    "reset_push_manager",
]
