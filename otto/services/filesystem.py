"""File system watcher service — activity patterns.

Produces categorical signals about file system activity without
exposing any file paths, names, or content.

Signals produced::

    activity_level: idle / active / intense
    file_churn:     low / medium / high

Privacy boundary (Patent Claim #3)::

    RAW:         "Created: /src/components/Auth.tsx", 47 events/5min
    CATEGORICAL: activity_level=active, file_churn=medium

[He2025]: Classification thresholds are fixed constants.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from otto.services.base import CategoricalSignal


@dataclass(frozen=True)
class FileSystemSnapshot:
    """Internal filesystem activity state.

    Raw data — NEVER exposed through ``get_signals()``.

    Attributes:
        events_in_window: File events in the tracking window.
        window_seconds: Size of the tracking window (seconds).
    """

    events_in_window: int
    window_seconds: float


def _classify_activity(events: int, window_seconds: float) -> str:
    """Classify activity level from event rate."""
    if window_seconds <= 0:
        return "idle"

    rate = events / (window_seconds / 60.0)  # events per minute
    if rate > 20:
        return "intense"
    if rate > 3:
        return "active"
    return "idle"


def _classify_churn(events: int, window_seconds: float) -> str:
    """Classify file churn from event rate."""
    if window_seconds <= 0:
        return "low"

    rate = events / (window_seconds / 60.0)
    if rate > 30:
        return "high"
    if rate > 5:
        return "medium"
    return "low"


class FileSystemWatcher:
    """File system watcher — activity pattern detection.

    Tracks file system events and produces categorical signals
    about activity levels without exposing any file information.

    Supports two modes:

    1. **Snapshot provider** (injected): For testing or external
       integrations.  Provider returns a ``FileSystemSnapshot``.
    2. **Internal tracking**: Call ``record_event()`` to register
       file events.  Events outside the window are pruned.

    Args:
        snapshot_provider: Callable returning a FileSystemSnapshot.
            If ``None``, uses internal event tracking.
        window_seconds: Tracking window size (default 300 = 5 min).
    """

    def __init__(
        self,
        snapshot_provider: Callable[[], FileSystemSnapshot | None] | None = None,
        window_seconds: float = 300.0,
    ) -> None:
        self._provider = snapshot_provider
        self._running = False
        self._window_seconds = window_seconds
        self._events: deque[datetime] = deque()

    @property
    def name(self) -> str:
        return "filesystem_watcher"

    @property
    def tier(self) -> int:
        return 1

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True
        self._events.clear()

    def stop(self) -> None:
        self._running = False

    def record_event(self) -> None:
        """Record a file system event.

        Only used when no ``snapshot_provider`` is injected.
        Events older than the window are pruned on next
        ``get_signals()`` call.
        """
        self._events.append(datetime.now(timezone.utc))

    def get_signals(self) -> list[CategoricalSignal]:
        """Get filesystem activity signals.

        Privacy: Only activity categories leave.
        No file paths or names exposed.

        [He2025]: Signals returned in sorted (category, value) order.
        """
        if self._provider is not None:
            snapshot = self._provider()
            if snapshot is None:
                return []
        else:
            self._prune_old_events()
            snapshot = FileSystemSnapshot(
                events_in_window=len(self._events),
                window_seconds=self._window_seconds,
            )

        now = datetime.now(timezone.utc)

        signals = [
            CategoricalSignal(
                category="activity_level",
                value=_classify_activity(
                    snapshot.events_in_window,
                    snapshot.window_seconds,
                ),
                confidence=0.85,
                source=self.name,
                timestamp=now,
            ),
            CategoricalSignal(
                category="file_churn",
                value=_classify_churn(
                    snapshot.events_in_window,
                    snapshot.window_seconds,
                ),
                confidence=0.8,
                source=self.name,
                timestamp=now,
            ),
        ]

        return sorted(signals, key=lambda s: (s.category, s.value))

    def _prune_old_events(self) -> None:
        """Remove events older than the tracking window."""
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self._window_seconds,
        )
        while self._events and self._events[0] < cutoff:
            self._events.popleft()
