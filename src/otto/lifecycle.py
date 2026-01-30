"""
Lifecycle management for Framework Orchestrator.

Provides:
- Graceful shutdown handling
- Signal handlers (SIGTERM, SIGINT)
- Cleanup registration
- State persistence on shutdown
"""

import asyncio
import logging
import signal
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_handler_name(handler: Callable) -> str:
    """Get handler name safely for logging."""
    return getattr(handler, '__name__', repr(handler))


class LifecycleState(Enum):
    """Orchestrator lifecycle states."""
    STARTING = "starting"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class ShutdownContext:
    """Context passed to shutdown handlers."""
    signal_received: Optional[str] = None
    reason: str = "unknown"
    timeout: float = 10.0
    state_to_save: Optional[Dict[str, Any]] = None


class LifecycleManager:
    """
    Manages orchestrator lifecycle including graceful shutdown.

    Features:
    - Signal handling (SIGTERM, SIGINT)
    - Cleanup handler registration
    - Graceful shutdown with timeout
    - State preservation

    Usage:
        lifecycle = LifecycleManager()

        # Register cleanup handlers
        lifecycle.register_shutdown_handler(save_state)
        lifecycle.register_shutdown_handler(close_connections)

        # Setup signal handlers
        lifecycle.setup_signal_handlers(asyncio.get_event_loop())

        # Check shutdown state
        if lifecycle.is_shutting_down:
            return  # Don't start new work
    """

    def __init__(
        self,
        shutdown_timeout: float = 10.0,
        handler_timeout: float = 5.0
    ):
        """
        Initialize lifecycle manager.

        Args:
            shutdown_timeout: Maximum time to wait for graceful shutdown
            handler_timeout: Maximum time for each shutdown handler to complete
        """
        self.shutdown_timeout = shutdown_timeout
        self.handler_timeout = handler_timeout
        self.state = LifecycleState.STARTING
        self._shutdown_handlers: List[Callable[[ShutdownContext], Coroutine]] = []
        self._sync_shutdown_handlers: List[Callable[[ShutdownContext], None]] = []
        self._pending_tasks: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._signal_received: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Check if orchestrator is in running state."""
        return self.state == LifecycleState.RUNNING

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self.state == LifecycleState.SHUTTING_DOWN

    @property
    def is_stopped(self) -> bool:
        """Check if orchestrator has stopped."""
        return self.state == LifecycleState.STOPPED

    def mark_running(self) -> None:
        """Mark orchestrator as running."""
        self.state = LifecycleState.RUNNING
        logger.info("Orchestrator entered RUNNING state")

    def register_shutdown_handler(
        self,
        handler: Callable[[ShutdownContext], Coroutine]
    ) -> None:
        """
        Register an async cleanup handler to run during shutdown.

        Handlers are called in reverse registration order (LIFO).

        Args:
            handler: Async function taking ShutdownContext
        """
        self._shutdown_handlers.append(handler)
        logger.debug(f"Registered shutdown handler: {_get_handler_name(handler)}")

    def register_sync_shutdown_handler(
        self,
        handler: Callable[[ShutdownContext], None]
    ) -> None:
        """
        Register a synchronous cleanup handler.

        Args:
            handler: Function taking ShutdownContext
        """
        self._sync_shutdown_handlers.append(handler)
        logger.debug(f"Registered sync shutdown handler: {_get_handler_name(handler)}")

    def track_task(self, task: asyncio.Task) -> None:
        """
        Track a task for graceful shutdown.

        Args:
            task: Async task to track
        """
        self._pending_tasks.append(task)

        # Auto-remove when done
        def remove_task(t):
            if t in self._pending_tasks:
                self._pending_tasks.remove(t)

        task.add_done_callback(remove_task)

    def setup_signal_handlers(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """
        Setup signal handlers for graceful shutdown.

        Handles SIGTERM and SIGINT (Ctrl+C).

        Args:
            loop: Event loop (uses running loop if None)
        """
        if sys.platform == 'win32':
            # Windows doesn't support add_signal_handler
            # Use signal.signal instead
            signal.signal(signal.SIGINT, self._sync_signal_handler)
            signal.signal(signal.SIGTERM, self._sync_signal_handler)
            logger.info("Signal handlers configured (Windows mode)")
        else:
            # Unix - use async signal handlers
            loop = loop or asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(self._handle_signal(s))
                )
            logger.info("Signal handlers configured (Unix mode)")

    def _sync_signal_handler(self, signum: int, frame) -> None:
        """Synchronous signal handler for Windows."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name}")
        self._signal_received = sig_name

        # Set the event to trigger shutdown
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._shutdown_event.set)
        except RuntimeError:
            # No running loop, just set state
            self.state = LifecycleState.SHUTTING_DOWN

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle shutdown signal."""
        sig_name = sig.name
        logger.info(f"Received signal {sig_name}")
        self._signal_received = sig_name
        self._shutdown_event.set()
        await self.shutdown(reason=f"Signal {sig_name}")

    async def shutdown(
        self,
        reason: str = "requested",
        state_to_save: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Perform graceful shutdown.

        1. Set shutting_down state
        2. Stop accepting new tasks
        3. Wait for in-flight tasks (with timeout)
        4. Run shutdown handlers
        5. Mark as stopped

        Args:
            reason: Reason for shutdown
            state_to_save: Optional state dict for handlers
        """
        if self.state == LifecycleState.SHUTTING_DOWN:
            logger.debug("Shutdown already in progress")
            return

        if self.state == LifecycleState.STOPPED:
            logger.debug("Already stopped")
            return

        self.state = LifecycleState.SHUTTING_DOWN
        logger.info(f"Starting graceful shutdown: {reason}")

        context = ShutdownContext(
            signal_received=self._signal_received,
            reason=reason,
            timeout=self.shutdown_timeout,
            state_to_save=state_to_save
        )

        # Wait for pending tasks
        if self._pending_tasks:
            logger.info(f"Waiting for {len(self._pending_tasks)} pending task(s)")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._pending_tasks, return_exceptions=True),
                    timeout=self.shutdown_timeout
                )
                logger.info("All pending tasks completed")
            except asyncio.TimeoutError:
                logger.warning(
                    f"Shutdown timeout ({self.shutdown_timeout}s) - "
                    f"cancelling {len(self._pending_tasks)} task(s)"
                )
                for task in self._pending_tasks:
                    task.cancel()

        # Run async shutdown handlers (reverse order)
        for handler in reversed(self._shutdown_handlers):
            try:
                logger.debug(f"Running shutdown handler: {_get_handler_name(handler)}")
                await asyncio.wait_for(
                    handler(context),
                    timeout=self.handler_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Shutdown handler {_get_handler_name(handler)} timed out")
            except Exception as e:
                logger.error(f"Shutdown handler {_get_handler_name(handler)} failed: {e}")

        # Run sync shutdown handlers
        for handler in reversed(self._sync_shutdown_handlers):
            try:
                handler(context)
            except Exception as e:
                logger.error(f"Sync shutdown handler {_get_handler_name(handler)} failed: {e}")

        self.state = LifecycleState.STOPPED
        logger.info("Shutdown complete")

    async def wait_for_shutdown(self) -> None:
        """
        Wait for shutdown signal.

        Useful for main loops:
            await lifecycle.wait_for_shutdown()
        """
        await self._shutdown_event.wait()

    def request_shutdown(self, reason: str = "requested") -> None:
        """
        Request shutdown from non-async context.

        Args:
            reason: Reason for shutdown
        """
        self._shutdown_event.set()
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self.shutdown(reason=reason))
        except RuntimeError:
            # No running loop
            self.state = LifecycleState.SHUTTING_DOWN


async def run_with_lifecycle(
    main_coro: Coroutine,
    lifecycle: Optional[LifecycleManager] = None,
    shutdown_timeout: float = 10.0,
    handler_timeout: float = 5.0
) -> Any:
    """
    Run a coroutine with lifecycle management.

    Sets up signal handlers and ensures graceful shutdown.

    Args:
        main_coro: Main coroutine to run
        lifecycle: LifecycleManager (creates new if None)
        shutdown_timeout: Timeout for graceful shutdown
        handler_timeout: Timeout for each shutdown handler

    Returns:
        Result of main coroutine
    """
    lifecycle = lifecycle or LifecycleManager(
        shutdown_timeout=shutdown_timeout,
        handler_timeout=handler_timeout
    )

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    lifecycle.setup_signal_handlers(loop)

    lifecycle.mark_running()

    try:
        return await main_coro
    finally:
        if not lifecycle.is_stopped:
            await lifecycle.shutdown(reason="Main coroutine completed")
