"""
Overuse Detector
================

Detects patterns suggesting the user is pushing past their limits.

Detection Signals:
- Time elapsed without breaks
- Rapid consecutive exchanges
- Override patterns (repeatedly ignoring suggestions)
- Energy/burnout signal combinations
- Hyperfocus without body checks

This is behavioral pattern recognition, not surveillance.
We track aggregates for protection, not specifics for monitoring.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

from ..cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel

logger = logging.getLogger(__name__)


class OveruseType(Enum):
    """Types of overuse patterns."""
    TIME_EXTENDED = "time_extended"       # Long session without break
    RAPID_EXCHANGE = "rapid_exchange"     # Many quick exchanges
    OVERRIDE_PATTERN = "override_pattern" # Repeatedly ignoring suggestions
    ENERGY_MISMATCH = "energy_mismatch"   # Low energy but still pushing
    HYPERFOCUS = "hyperfocus"             # Deep focus without body check


@dataclass
class OveruseSignal:
    """A detected overuse signal."""
    overuse_type: OveruseType
    severity: float  # 0.0 to 1.0
    duration_minutes: int = 0
    override_count: int = 0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.overuse_type.value,
            "severity": self.severity,
            "duration_minutes": self.duration_minutes,
            "override_count": self.override_count,
            "message": self.message,
        }


class OveruseDetector:
    """
    Detects overuse patterns from cognitive state and session data.

    Thresholds are calibrated conservatively - we'd rather miss some
    overuse than annoy users with false positives.
    """

    # Time thresholds (in minutes)
    TIME_YELLOW = 45      # Gentle mention
    TIME_ORANGE = 90      # Suggest break
    TIME_RED = 150        # Firm suggestion

    # Rapid exchange thresholds
    RAPID_THRESHOLD = 20  # Exchanges before body check

    # Override thresholds
    OVERRIDE_WARNING = 2  # Overrides before noting pattern
    OVERRIDE_CONCERN = 5  # Overrides that indicate problem

    def __init__(self):
        """Initialize detector."""
        self._override_count: int = 0
        self._last_protection_time: float = 0
        self._protection_cooldown: int = 300  # 5 minutes between suggestions

    def detect(self, state: CognitiveState) -> List[OveruseSignal]:
        """
        Detect all overuse signals from current state.

        Args:
            state: Current cognitive state

        Returns:
            List of detected overuse signals, sorted by severity
        """
        signals = []

        # Time-based detection
        time_signal = self._detect_time_overuse(state)
        if time_signal:
            signals.append(time_signal)

        # Rapid exchange detection
        rapid_signal = self._detect_rapid_exchange(state)
        if rapid_signal:
            signals.append(rapid_signal)

        # Energy mismatch detection
        energy_signal = self._detect_energy_mismatch(state)
        if energy_signal:
            signals.append(energy_signal)

        # Override pattern detection
        if self._override_count >= self.OVERRIDE_WARNING:
            signals.append(OveruseSignal(
                overuse_type=OveruseType.OVERRIDE_PATTERN,
                severity=min(self._override_count / 10.0, 1.0),
                override_count=self._override_count,
                message=f"You've overridden {self._override_count} times this session"
            ))

        # Sort by severity (highest first)
        signals.sort(key=lambda s: s.severity, reverse=True)

        return signals

    def _detect_time_overuse(self, state: CognitiveState) -> Optional[OveruseSignal]:
        """Detect if session has gone too long without break."""
        elapsed_seconds = time.time() - state.session_start
        elapsed_minutes = int(elapsed_seconds / 60)

        if elapsed_minutes < self.TIME_YELLOW:
            return None

        if elapsed_minutes >= self.TIME_RED:
            severity = 0.9
            message = f"You've been at it for {elapsed_minutes // 60}+ hours"
        elif elapsed_minutes >= self.TIME_ORANGE:
            severity = 0.6
            message = f"About {elapsed_minutes} minutes in"
        else:  # TIME_YELLOW
            severity = 0.3
            message = f"Coming up on {elapsed_minutes} minutes"

        return OveruseSignal(
            overuse_type=OveruseType.TIME_EXTENDED,
            severity=severity,
            duration_minutes=elapsed_minutes,
            message=message
        )

    def _detect_rapid_exchange(self, state: CognitiveState) -> Optional[OveruseSignal]:
        """Detect rapid consecutive exchanges without body check."""
        if state.rapid_exchange_count < self.RAPID_THRESHOLD:
            return None

        # Severity increases with count
        severity = min(state.rapid_exchange_count / 40.0, 1.0)

        return OveruseSignal(
            overuse_type=OveruseType.RAPID_EXCHANGE,
            severity=severity,
            message=f"{state.rapid_exchange_count} quick exchanges - body check?"
        )

    def _detect_energy_mismatch(self, state: CognitiveState) -> Optional[OveruseSignal]:
        """Detect low energy but still pushing (energy mismatch)."""
        # Only trigger if energy is low/depleted but not in recovery mode
        if state.energy_level not in (EnergyLevel.LOW, EnergyLevel.DEPLETED):
            return None

        # Check if still actively working (high exchange rate indicates pushing)
        if state.exchange_count < 5:
            return None

        if state.energy_level == EnergyLevel.DEPLETED:
            severity = 0.8
            message = "You seem pretty wiped but still going"
        else:
            severity = 0.4
            message = "Running low but pushing through"

        return OveruseSignal(
            overuse_type=OveruseType.ENERGY_MISMATCH,
            severity=severity,
            message=message
        )

    def record_override(self) -> None:
        """Record that user overrode a protection suggestion."""
        self._override_count += 1
        logger.info(f"Protection override recorded. Total: {self._override_count}")

    def reset_overrides(self) -> None:
        """Reset override count (e.g., after break or new session)."""
        self._override_count = 0

    def should_suggest_protection(self, signals: List[OveruseSignal]) -> bool:
        """
        Check if we should suggest protection based on signals.

        Respects cooldown to avoid nagging.
        """
        if not signals:
            return False

        # Check cooldown
        elapsed = time.time() - self._last_protection_time
        if elapsed < self._protection_cooldown:
            return False

        # Only suggest if we have a meaningful signal
        max_severity = max(s.severity for s in signals)
        return max_severity >= 0.3

    def mark_protection_suggested(self) -> None:
        """Mark that we suggested protection (for cooldown tracking)."""
        self._last_protection_time = time.time()

    def get_primary_signal(self, signals: List[OveruseSignal]) -> Optional[OveruseSignal]:
        """Get the highest severity signal."""
        if not signals:
            return None
        return signals[0]  # Already sorted by severity

    def set_cooldown(self, seconds: int) -> None:
        """Set protection suggestion cooldown."""
        self._protection_cooldown = seconds


def create_overuse_detector() -> OveruseDetector:
    """Factory function to create an OveruseDetector."""
    return OveruseDetector()


__all__ = [
    'OveruseType',
    'OveruseSignal',
    'OveruseDetector',
    'create_overuse_detector',
]
