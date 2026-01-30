"""
Integration Adapter Interface
=============================

Base class for all external service integrations.

Design Principles:
1. Read-first: All adapters support reading context
2. Write-with-consent: Write operations require explicit consent
3. Privacy-first: Only extract metadata, never raw content
4. Graceful degradation: Errors don't crash OTTO
5. Async-native: All operations are async for non-blocking behavior
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar

from .models import (
    HealthStatus,
    IntegrationConfig,
    IntegrationStatus,
    IntegrationType,
)

logger = logging.getLogger(__name__)


# Type variable for context type (CalendarContext, TaskContext, etc.)
ContextT = TypeVar("ContextT")


class IntegrationError(Exception):
    """Base exception for integration errors."""
    pass


class AuthenticationError(IntegrationError):
    """Raised when authentication fails."""
    pass


class RateLimitError(IntegrationError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[datetime] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ServiceUnavailableError(IntegrationError):
    """Raised when external service is unavailable."""
    pass


class IntegrationAdapter(ABC, Generic[ContextT]):
    """
    Abstract base class for external integrations.

    Subclasses implement service-specific logic while this base
    provides common functionality and enforces the contract.

    Type Parameters:
        ContextT: The context type this adapter produces
                  (e.g., CalendarContext, TaskContext)

    Example:
        class GoogleCalendarAdapter(IntegrationAdapter[CalendarContext]):
            async def get_context(self) -> CalendarContext:
                # Fetch from Google Calendar API
                ...
    """

    # Class-level constants (override in subclass)
    SERVICE_NAME: str = "base"
    INTEGRATION_TYPE: IntegrationType = IntegrationType.CALENDAR
    SUPPORTS_WRITE: bool = False  # Phase 5.1 is read-only

    def __init__(self, config: IntegrationConfig):
        """
        Initialize adapter with configuration.

        Args:
            config: Integration configuration (without sensitive data)
        """
        self.config = config
        self._health = HealthStatus(status=IntegrationStatus.NOT_CONFIGURED)
        self._last_context: Optional[ContextT] = None
        self._initialized = False

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def service_name(self) -> str:
        """Service identifier (e.g., 'google_calendar')."""
        return self.SERVICE_NAME

    @property
    def integration_type(self) -> IntegrationType:
        """Type of integration (calendar, task_manager, etc.)."""
        return self.INTEGRATION_TYPE

    @property
    def can_read(self) -> bool:
        """Whether reading is supported (always True)."""
        return True

    @property
    def can_write(self) -> bool:
        """Whether writing is supported."""
        return self.SUPPORTS_WRITE and self.config.enabled

    @property
    def is_enabled(self) -> bool:
        """Whether this integration is enabled."""
        return self.config.enabled

    @property
    def health(self) -> HealthStatus:
        """Current health status."""
        return self._health

    @property
    def last_context(self) -> Optional[ContextT]:
        """Last successfully retrieved context (cached)."""
        return self._last_context

    # =========================================================================
    # Abstract Methods (Must Implement)
    # =========================================================================

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the adapter (authenticate, verify connection).

        Called once before first use. Should:
        1. Load credentials from keyring
        2. Verify connection to service
        3. Update health status

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    async def _fetch_context(self) -> ContextT:
        """
        Fetch context from external service.

        This is the core method subclasses implement. It should:
        1. Call the external API
        2. Transform response to context model
        3. Extract only metadata (privacy-first)

        Returns:
            Context object with extracted metadata

        Raises:
            AuthenticationError: If auth fails
            RateLimitError: If rate limited
            ServiceUnavailableError: If service is down
            IntegrationError: For other errors
        """
        pass

    @abstractmethod
    def _create_empty_context(self) -> ContextT:
        """
        Create empty context when service unavailable.

        Used for graceful degradation.

        Returns:
            Empty/default context object
        """
        pass

    # =========================================================================
    # Optional Override Methods
    # =========================================================================

    async def shutdown(self) -> None:
        """
        Clean up resources on shutdown.

        Override if adapter holds resources (connections, etc.).
        """
        pass

    async def refresh_auth(self) -> bool:
        """
        Refresh authentication tokens.

        Override for OAuth-based services that need token refresh.

        Returns:
            True if refresh successful
        """
        return True

    # =========================================================================
    # Public API
    # =========================================================================

    async def get_context(self) -> ContextT:
        """
        Get current context from external service.

        This is the main public method. It handles:
        - Initialization check
        - Error handling with graceful degradation
        - Health status updates
        - Caching of last successful context

        Returns:
            Context object (or empty context on error)
        """
        if not self._initialized:
            success = await self.initialize()
            if not success:
                logger.warning(f"{self.service_name}: Initialization failed")
                return self._create_empty_context()
            self._initialized = True

        if not self.is_enabled:
            return self._create_empty_context()

        try:
            context = await self._fetch_context()

            # Update health
            self._health = HealthStatus(
                status=IntegrationStatus.HEALTHY,
                last_sync=datetime.now(),
            )

            # Cache successful context
            self._last_context = context
            self.config.last_sync = datetime.now()

            logger.debug(f"{self.service_name}: Context fetched successfully")
            return context

        except AuthenticationError as e:
            logger.error(f"{self.service_name}: Authentication failed: {e}")
            self._health = HealthStatus(
                status=IntegrationStatus.ERROR,
                error_message=f"Authentication failed: {e}",
            )
            # Try to refresh and retry once
            if await self.refresh_auth():
                try:
                    return await self._fetch_context()
                except Exception:
                    pass
            return self._fallback_context()

        except RateLimitError as e:
            logger.warning(f"{self.service_name}: Rate limited: {e}")
            self._health = HealthStatus(
                status=IntegrationStatus.DEGRADED,
                error_message="Rate limited",
                retry_after=e.retry_after,
            )
            return self._fallback_context()

        except ServiceUnavailableError as e:
            logger.warning(f"{self.service_name}: Service unavailable: {e}")
            self._health = HealthStatus(
                status=IntegrationStatus.ERROR,
                error_message=f"Service unavailable: {e}",
            )
            return self._fallback_context()

        except IntegrationError as e:
            logger.error(f"{self.service_name}: Integration error: {e}")
            self._health = HealthStatus(
                status=IntegrationStatus.ERROR,
                error_message=str(e),
            )
            return self._fallback_context()

        except Exception as e:
            logger.exception(f"{self.service_name}: Unexpected error: {e}")
            self._health = HealthStatus(
                status=IntegrationStatus.ERROR,
                error_message=f"Unexpected error: {e}",
            )
            return self._fallback_context()

    async def get_health(self) -> HealthStatus:
        """
        Get current health status.

        Returns:
            Health status object
        """
        return self._health

    def _fallback_context(self) -> ContextT:
        """
        Return fallback context on error.

        Uses last successful context if available,
        otherwise returns empty context.
        """
        if self._last_context is not None:
            logger.info(f"{self.service_name}: Using cached context")
            return self._last_context
        return self._create_empty_context()

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize adapter state to dictionary.

        Returns:
            Dictionary with adapter info (not sensitive data)
        """
        return {
            "service_name": self.service_name,
            "integration_type": self.integration_type.value,
            "enabled": self.is_enabled,
            "can_read": self.can_read,
            "can_write": self.can_write,
            "health": self._health.to_dict(),
            "last_sync": self.config.last_sync.isoformat() if self.config.last_sync else None,
        }


__all__ = [
    "IntegrationAdapter",
    "IntegrationError",
    "AuthenticationError",
    "RateLimitError",
    "ServiceUnavailableError",
]
