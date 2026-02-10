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
from .nudge import check_and_nudge
from .state import StateStore
from .store import CommitmentStore

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
    ) -> None:
        self._store = store
        self._state_store = state_store
        self._interval = interval_seconds
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
        """Run a single nudge check with constitutional gating."""
        try:
            # Constitutional gate
            state = self._state_store.load()
            suppression = should_suppress(state, "nudge")

            if suppression is not None:
                _log.info(
                    "Scheduled nudge suppressed: %s", suppression.reason
                )
                self._state_store.increment_suppressed()
            else:
                nudges = check_and_nudge(self._store)
                if nudges:
                    _log.info(
                        "Scheduled nudge produced %d message(s)", len(nudges)
                    )
                    for msg in nudges:
                        _log.info("  Nudge: %s", msg[:80])
                else:
                    _log.debug("Scheduled nudge: nothing to nudge about")

        except Exception:
            _log.exception("Error in scheduled nudge check")

        # Schedule the next run regardless of outcome
        with self._lock:
            if self._running:
                self._schedule_next()
