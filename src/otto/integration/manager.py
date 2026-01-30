"""
Integration Manager
===================

Orchestrates all external integrations:
- Registry of adapters
- Background sync scheduling
- Context aggregation
- Health monitoring

This is the single entry point for the rest of OTTO OS
to access external context.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .adapter import IntegrationAdapter, IntegrationError
from .models import (
    CalendarContext,
    ExternalContext,
    HealthStatus,
    IntegrationConfig,
    IntegrationStatus,
    IntegrationType,
    TaskContext,
)

logger = logging.getLogger(__name__)


class IntegrationManager:
    """
    Central manager for all external integrations.

    Responsibilities:
    1. Adapter registry (register/unregister adapters)
    2. Background sync (periodic context refresh)
    3. Context aggregation (combine all contexts)
    4. Health monitoring (track adapter health)

    Usage:
        manager = IntegrationManager(otto_dir)
        await manager.start()

        # Get aggregated context
        context = await manager.get_context()

        # Or get specific context
        calendar = await manager.get_calendar_context()

        await manager.stop()
    """

    # Default sync interval (5 minutes)
    DEFAULT_SYNC_INTERVAL = timedelta(minutes=5)

    # Minimum sync interval (1 minute)
    MIN_SYNC_INTERVAL = timedelta(minutes=1)

    def __init__(
        self,
        otto_dir: Optional[Path] = None,
        sync_interval: Optional[timedelta] = None,
    ):
        """
        Initialize integration manager.

        Args:
            otto_dir: OTTO data directory (for config storage)
            sync_interval: How often to sync (default: 5 minutes)
        """
        self.otto_dir = otto_dir or Path.home() / ".otto"
        self.sync_interval = sync_interval or self.DEFAULT_SYNC_INTERVAL

        # Adapter registry
        self._adapters: Dict[str, IntegrationAdapter] = {}

        # Cached context
        self._context: ExternalContext = ExternalContext.empty()

        # Background sync
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False

        # Event for signaling context updates
        self._context_updated = asyncio.Event()

    # =========================================================================
    # Adapter Registry
    # =========================================================================

    def register_adapter(self, adapter: IntegrationAdapter) -> None:
        """
        Register an adapter.

        Args:
            adapter: Adapter instance to register

        Raises:
            ValueError: If adapter with same name already registered
        """
        name = adapter.service_name

        if name in self._adapters:
            raise ValueError(f"Adapter '{name}' already registered")

        self._adapters[name] = adapter
        logger.info(f"Registered adapter: {name}")

    def unregister_adapter(self, service_name: str) -> bool:
        """
        Unregister an adapter.

        Args:
            service_name: Name of adapter to remove

        Returns:
            True if adapter was removed, False if not found
        """
        if service_name in self._adapters:
            del self._adapters[service_name]
            logger.info(f"Unregistered adapter: {service_name}")
            return True
        return False

    def get_adapter(self, service_name: str) -> Optional[IntegrationAdapter]:
        """
        Get adapter by name.

        Args:
            service_name: Adapter service name

        Returns:
            Adapter instance or None
        """
        return self._adapters.get(service_name)

    def list_adapters(self) -> List[str]:
        """
        List all registered adapter names.

        Returns:
            List of service names
        """
        return list(self._adapters.keys())

    def get_adapters_by_type(
        self, integration_type: IntegrationType
    ) -> List[IntegrationAdapter]:
        """
        Get all adapters of a specific type.

        Args:
            integration_type: Type to filter by

        Returns:
            List of matching adapters
        """
        return [
            a for a in self._adapters.values()
            if a.integration_type == integration_type
        ]

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """
        Start the integration manager.

        Initializes all adapters and starts background sync.
        """
        if self._running:
            logger.warning("IntegrationManager already running")
            return

        logger.info("Starting IntegrationManager")
        self._running = True

        # Initialize all adapters
        for name, adapter in self._adapters.items():
            try:
                await adapter.initialize()
                logger.info(f"Initialized adapter: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize {name}: {e}")

        # Initial sync
        await self._sync_all()

        # Start background sync
        self._sync_task = asyncio.create_task(self._background_sync())
        logger.info("IntegrationManager started")

    async def stop(self) -> None:
        """
        Stop the integration manager.

        Cancels background sync and shuts down adapters.
        """
        if not self._running:
            return

        logger.info("Stopping IntegrationManager")
        self._running = False

        # Cancel background sync
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None

        # Shutdown all adapters
        for name, adapter in self._adapters.items():
            try:
                await adapter.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down {name}: {e}")

        logger.info("IntegrationManager stopped")

    # =========================================================================
    # Context Retrieval
    # =========================================================================

    async def get_context(self, force_refresh: bool = False) -> ExternalContext:
        """
        Get aggregated external context.

        Args:
            force_refresh: If True, refresh all adapters first

        Returns:
            Aggregated context from all integrations
        """
        if force_refresh:
            await self._sync_all()

        return self._context

    async def get_calendar_context(self) -> Optional[CalendarContext]:
        """
        Get calendar context specifically.

        Returns:
            Calendar context or None if no calendar adapter
        """
        adapters = self.get_adapters_by_type(IntegrationType.CALENDAR)
        if not adapters:
            return None

        # Use first enabled calendar adapter
        for adapter in adapters:
            if adapter.is_enabled:
                ctx = await adapter.get_context()
                if isinstance(ctx, CalendarContext):
                    return ctx

        return CalendarContext.empty()

    async def get_task_context(self) -> Optional[TaskContext]:
        """
        Get task context specifically.

        Returns:
            Task context or None if no task adapter
        """
        adapters = self.get_adapters_by_type(IntegrationType.TASK_MANAGER)
        if not adapters:
            return None

        # Use first enabled task adapter
        for adapter in adapters:
            if adapter.is_enabled:
                ctx = await adapter.get_context()
                if isinstance(ctx, TaskContext):
                    return ctx

        return TaskContext.empty()

    async def wait_for_update(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for next context update.

        Args:
            timeout: Maximum seconds to wait (None = forever)

        Returns:
            True if update received, False if timeout
        """
        self._context_updated.clear()
        try:
            await asyncio.wait_for(self._context_updated.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # =========================================================================
    # Health Monitoring
    # =========================================================================

    async def get_health(self) -> Dict[str, HealthStatus]:
        """
        Get health status of all adapters.

        Returns:
            Dictionary of service_name -> HealthStatus
        """
        return {
            name: await adapter.get_health()
            for name, adapter in self._adapters.items()
        }

    async def get_overall_health(self) -> IntegrationStatus:
        """
        Get overall integration health.

        Returns:
            HEALTHY if all OK
            DEGRADED if some errors
            ERROR if all errors
            NOT_CONFIGURED if no adapters
        """
        if not self._adapters:
            return IntegrationStatus.NOT_CONFIGURED

        health = await self.get_health()
        statuses = [h.status for h in health.values()]

        if all(s == IntegrationStatus.HEALTHY for s in statuses):
            return IntegrationStatus.HEALTHY
        if all(s == IntegrationStatus.ERROR for s in statuses):
            return IntegrationStatus.ERROR
        return IntegrationStatus.DEGRADED

    # =========================================================================
    # Manual Sync
    # =========================================================================

    async def sync(self, service_name: Optional[str] = None) -> bool:
        """
        Manually trigger sync.

        Args:
            service_name: Specific adapter to sync (None = all)

        Returns:
            True if sync successful
        """
        if service_name:
            adapter = self._adapters.get(service_name)
            if not adapter:
                logger.warning(f"Adapter not found: {service_name}")
                return False
            try:
                await adapter.get_context()
                return True
            except Exception as e:
                logger.error(f"Sync failed for {service_name}: {e}")
                return False
        else:
            await self._sync_all()
            return True

    # =========================================================================
    # Private Methods
    # =========================================================================

    async def _sync_all(self) -> None:
        """Sync all adapters and aggregate context."""
        logger.debug("Syncing all integrations")

        calendar_context: Optional[CalendarContext] = None
        task_context: Optional[TaskContext] = None
        available = []

        # Sync calendar adapters
        for adapter in self.get_adapters_by_type(IntegrationType.CALENDAR):
            if adapter.is_enabled:
                try:
                    ctx = await adapter.get_context()
                    if isinstance(ctx, CalendarContext):
                        calendar_context = ctx
                        available.append(adapter.service_name)
                        break  # Use first successful
                except Exception as e:
                    logger.error(f"Calendar sync failed: {e}")

        # Sync task adapters
        for adapter in self.get_adapters_by_type(IntegrationType.TASK_MANAGER):
            if adapter.is_enabled:
                try:
                    ctx = await adapter.get_context()
                    if isinstance(ctx, TaskContext):
                        task_context = ctx
                        available.append(adapter.service_name)
                        break  # Use first successful
                except Exception as e:
                    logger.error(f"Task sync failed: {e}")

        # Update aggregated context
        self._context = ExternalContext(
            calendar=calendar_context,
            tasks=task_context,
            last_updated=datetime.now(),
            available_integrations=available,
        )

        # Signal update
        self._context_updated.set()
        logger.debug(f"Context updated: {len(available)} integrations available")

    async def _background_sync(self) -> None:
        """Background sync loop."""
        while self._running:
            try:
                await asyncio.sleep(self.sync_interval.total_seconds())
                if self._running:
                    await self._sync_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background sync error: {e}")
                # Continue running, will retry next interval

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize manager state to dictionary.

        Returns:
            Dictionary with manager info
        """
        return {
            "running": self._running,
            "sync_interval_seconds": self.sync_interval.total_seconds(),
            "adapters": {
                name: adapter.to_dict()
                for name, adapter in self._adapters.items()
            },
            "context": self._context.to_dict(),
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_integration_manager(
    otto_dir: Optional[Path] = None,
    sync_interval_minutes: int = 5,
) -> IntegrationManager:
    """
    Create an IntegrationManager with default settings.

    Args:
        otto_dir: OTTO data directory
        sync_interval_minutes: Sync interval in minutes

    Returns:
        Configured IntegrationManager
    """
    return IntegrationManager(
        otto_dir=otto_dir,
        sync_interval=timedelta(minutes=sync_interval_minutes),
    )


__all__ = [
    "IntegrationManager",
    "create_integration_manager",
]
