"""Simple nudge scheduler for OTTO.

Runs check_and_nudge on a fixed interval in a background thread,
gated by the constitutional layer. No external dependencies.

Usage:
    from otto.scheduler import NudgeScheduler
    scheduler = NudgeScheduler(interval_seconds=60)
    scheduler.start()   # non-blocking
    scheduler.stop()    # clean shutdown
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from .constitutional import should_suppress
from .log import get_logger
from .transport.base import Transport
from .modes import (
    AcknowledgerMode,
    DecomposerMode,
    ExecutorMode,
    GuideMode,
    ProtectorMode,
    RedirectorMode,
    RestorerMode,
)
from .learner import compute_ucb_adjustments
from .router import route_and_execute
from .signals import Signal, SignalType
from .state import StateStore
from .store import CommitmentStore
from .trails import TrailStore

_log = get_logger(__name__)


class NudgeScheduler:
    """Background scheduler that runs nudge checks on a fixed interval.

    Constitutional gating is applied before each check — if the user
    is in RED burnout or depleted, nudges are suppressed silently.
    """

    def __init__(
        self,
        store: CommitmentStore,
        state_store: StateStore,
        interval_seconds: int = 60,
        transport: Transport | None = None,
    ) -> None:
        self._store = store
        self._state_store = state_store
        self._interval = interval_seconds
        self._transport = transport
        self._timer: threading.Timer | None = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the scheduler (non-blocking)."""
        with self._lock:
            if self._running:
                return
            self._running = True
            _log.info(
                "Nudge scheduler started (interval=%ds)", self._interval
            )
            self._schedule_next()

    def stop(self) -> None:
        """Stop the scheduler and cancel any pending timer."""
        with self._lock:
            self._running = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            _log.info("Nudge scheduler stopped")

    def _schedule_next(self) -> None:
        """Schedule the next check."""
        if not self._running:
            return
        self._timer = threading.Timer(self._interval, self._run_check)
        self._timer.daemon = True
        self._timer.start()

    def _run_check(self) -> None:
        """Run a single nudge check via NEXUS pipeline with constitutional gating."""
        try:
            # Constitutional gate (fast-fail)
            state = self._state_store.load()
            suppression = should_suppress(state, "nudge")

            if suppression is not None:
                _log.info(
                    "Scheduled nudge suppressed: %s", suppression.reason
                )
                self._state_store.increment_suppressed()
            else:
                # PRISM -> NEXUS -> Modes pipeline
                signals = [Signal(type=SignalType.COMMITMENT_DETECTED, confidence=0.8)]

                # UCB1-based learning adjustments from outcome history
                trail_store = TrailStore(self._state_store._db_path)
                adjustments = compute_ucb_adjustments(signals, trail_store)

                modes = [
                    ExecutorMode(store=self._store),
                    ProtectorMode(),
                    RestorerMode(),
                    DecomposerMode(),
                    AcknowledgerMode(),
                    RedirectorMode(),
                    GuideMode(),
                ]
                response = route_and_execute(signals, state, modes, trail_adjustments=adjustments)

                if response is not None and response.text:
                    if response.suppress_others:
                        _log.info("Scheduled nudge: safety mode activated: %s", response.text[:80])
                    else:
                        _log.info("Scheduled nudge via NEXUS: %s", response.text[:80])

                    # Send via transport if configured
                    if self._transport is not None:
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(
                            self._transport.send("user", response.text)
                        )
                        if result.success:
                            _log.info("Nudge delivered via %s", result.transport)
                        else:
                            _log.warning("Nudge delivery failed: %s", result.error)
                else:
                    _log.debug("Scheduled nudge: nothing to nudge about")

        except Exception:
            _log.exception("Error in scheduled nudge check")

        # Schedule the next run regardless of outcome
        with self._lock:
            if self._running:
                self._schedule_next()
