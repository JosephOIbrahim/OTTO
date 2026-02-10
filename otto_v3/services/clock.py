"""System clock service — temporal awareness.

Produces categorical signals about time of day, day type, and
time pressure.  Pure function of the current time — no external
dependencies, no raw data exposure.

Signals produced::

    time_period:    dawn / morning / afternoon / evening / night
    day_type:       weekday / weekend
    time_pressure:  none / approaching_eod / late_night

Privacy: Time categories only — no calendar data, no schedule
information.

Time boundaries are fixed constants.  Classification
is deterministic given the same time input.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Callable

from otto_v3.services.base import CategoricalSignal


# ── Time period boundaries ────────────────────────────────────
# Fixed constants, deterministic classification.

_DAWN_START = time(5, 0)
_MORNING_START = time(7, 0)
_AFTERNOON_START = time(12, 0)
_EVENING_START = time(17, 0)
_NIGHT_START = time(21, 0)

# End-of-day pressure thresholds
_EOD_WARNING = time(16, 0)   # 4 PM
_LATE_NIGHT = time(23, 0)    # 11 PM


def _classify_time_period(t: time) -> str:
    """Classify a time-of-day into a period category."""
    if t >= _NIGHT_START:
        return "night"
    if t >= _EVENING_START:
        return "evening"
    if t >= _AFTERNOON_START:
        return "afternoon"
    if t >= _MORNING_START:
        return "morning"
    if t >= _DAWN_START:
        return "dawn"
    return "night"  # Before dawn = still night


def _classify_day_type(weekday: int) -> str:
    """Classify day type from weekday number (0=Mon, 6=Sun)."""
    return "weekend" if weekday >= 5 else "weekday"


def _classify_time_pressure(t: time) -> str:
    """Classify time pressure level."""
    if t >= _LATE_NIGHT:
        return "late_night"
    if t >= _EOD_WARNING:
        return "approaching_eod"
    return "none"


class ClockService:
    """System clock — temporal awareness.

    Produces time-based categorical signals.  No external
    dependencies.  Fully deterministic given the same time input.

    Args:
        clock: Optional callable returning current datetime.
            Defaults to UTC now.  Injection point for testing.
    """

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._running = False

    @property
    def name(self) -> str:
        return "clock"

    @property
    def tier(self) -> int:
        return 1

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def get_signals(self) -> list[CategoricalSignal]:
        """Get time-based categorical signals.

        Signals returned in sorted (category, value) order.
        """
        now = self._clock()
        local_time = now.time()
        weekday = now.weekday()

        signals = [
            CategoricalSignal(
                category="day_type",
                value=_classify_day_type(weekday),
                confidence=1.0,
                source=self.name,
                timestamp=now,
            ),
            CategoricalSignal(
                category="time_period",
                value=_classify_time_period(local_time),
                confidence=1.0,
                source=self.name,
                timestamp=now,
            ),
            CategoricalSignal(
                category="time_pressure",
                value=_classify_time_pressure(local_time),
                confidence=1.0,
                source=self.name,
                timestamp=now,
            ),
        ]

        # Sort by (category, value) for determinism
        return sorted(signals, key=lambda s: (s.category, s.value))
