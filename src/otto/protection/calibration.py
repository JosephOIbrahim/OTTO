"""
Protection Calibration Learning
===============================

Learns from user overrides to adjust protection firmness over time.

Determinism:
- FIXED adjustment amounts (deterministic)
- BOUNDED firmness range (0.0 to 1.0)
- DETERMINISTIC learning rules

Learning Rules:
- User overrides 3+ times in session → decrease firmness by 0.05
- User accepts suggestions 3+ times → increase firmness by 0.02
- Firmness bounded: min 0.1, max 0.9 (always some protection)

This implements the feedback loop described in BLUEPRINT.md:
"IF user overrides 3+ times → adjust protection_firmness down"
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED - determinism compliant)
# =============================================================================

# Thresholds for learning triggers
OVERRIDE_THRESHOLD = 3      # Overrides before adjustment
ACCEPT_THRESHOLD = 3        # Acceptances before adjustment

# Adjustment amounts (FIXED)
FIRMNESS_DECREASE = 0.05    # Decrease when user overrides
FIRMNESS_INCREASE = 0.02    # Increase when user accepts

# Bounds (FIXED)
FIRMNESS_MIN = 0.1          # Never fully disable protection
FIRMNESS_MAX = 0.9          # Never make it impossible to continue

# Calibration file
CALIBRATION_FILENAME = "calibration.json"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class CalibrationEvent:
    """A single calibration event."""
    event_type: str          # "override" or "accept"
    timestamp: str           # ISO format
    old_firmness: float
    new_firmness: float
    trigger: str             # What protection event was being responded to


@dataclass
class CalibrationState:
    """
    Current calibration state.

    Tracks session-level counts and cross-session learned adjustments.
    """
    # Session counts (reset each session)
    session_overrides: int = 0
    session_accepts: int = 0

    # Learned adjustment (persists across sessions)
    learned_firmness_adjustment: float = 0.0

    # History for debugging/analysis
    adjustment_history: List[Dict[str, Any]] = field(default_factory=list)

    # Last update timestamp
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_overrides": self.session_overrides,
            "session_accepts": self.session_accepts,
            "learned_firmness_adjustment": self.learned_firmness_adjustment,
            "adjustment_history": self.adjustment_history[-10:],  # Keep last 10
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalibrationState":
        """Deserialize from dictionary."""
        return cls(
            session_overrides=data.get("session_overrides", 0),
            session_accepts=data.get("session_accepts", 0),
            learned_firmness_adjustment=data.get("learned_firmness_adjustment", 0.0),
            adjustment_history=data.get("adjustment_history", []),
            last_updated=data.get("last_updated"),
        )


# =============================================================================
# Calibration Engine
# =============================================================================

class CalibrationEngine:
    """
    Learns user preferences from protection interactions.

    Tracks overrides and acceptances, adjusting firmness recommendation
    based on patterns. The actual firmness value is stored in profile,
    but this engine provides adjustment recommendations.

    Determinism:
    - All thresholds are FIXED constants
    - Adjustments are DETERMINISTIC
    - Bounds prevent extreme values
    """

    def __init__(self, otto_dir: Optional[Path] = None):
        """
        Initialize calibration engine.

        Args:
            otto_dir: OTTO data directory (default: ~/.otto)
        """
        self.otto_dir = otto_dir or Path.home() / ".otto"
        self.state = CalibrationState()
        self._load_state()

    def _get_calibration_path(self) -> Path:
        """Get path to calibration file."""
        return self.otto_dir / "state" / CALIBRATION_FILENAME

    def _load_state(self) -> None:
        """Load calibration state from disk."""
        path = self._get_calibration_path()

        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                self.state = CalibrationState.from_dict(data)
                logger.debug(f"Loaded calibration state: adjustment={self.state.learned_firmness_adjustment}")
            except Exception as e:
                logger.warning(f"Failed to load calibration state: {e}")
                self.state = CalibrationState()
        else:
            self.state = CalibrationState()

    def _save_state(self) -> None:
        """Save calibration state to disk."""
        path = self._get_calibration_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        self.state.last_updated = datetime.now().isoformat()

        try:
            with open(path, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2, sort_keys=True)
            logger.debug("Saved calibration state")
        except Exception as e:
            logger.warning(f"Failed to save calibration state: {e}")

    def record_override(self, trigger: str, current_firmness: float) -> Optional[float]:
        """
        Record that user overrode a protection suggestion.

        Args:
            trigger: What protection event was overridden
            current_firmness: Current firmness value

        Returns:
            New recommended firmness if adjustment made, None otherwise
        """
        self.state.session_overrides += 1

        # Check if threshold reached for adjustment
        if self.state.session_overrides >= OVERRIDE_THRESHOLD:
            # Calculate new firmness
            new_adjustment = self.state.learned_firmness_adjustment - FIRMNESS_DECREASE
            new_firmness = max(FIRMNESS_MIN, current_firmness + new_adjustment)

            # Record the event
            event = {
                "event_type": "override",
                "timestamp": datetime.now().isoformat(),
                "old_firmness": current_firmness,
                "new_firmness": new_firmness,
                "trigger": trigger,
                "session_count": self.state.session_overrides,
            }
            self.state.adjustment_history.append(event)
            self.state.learned_firmness_adjustment = new_adjustment

            # Reset session count after adjustment
            self.state.session_overrides = 0

            self._save_state()

            logger.info(f"Calibration: Decreased firmness {current_firmness:.2f} → {new_firmness:.2f}")
            return new_firmness

        return None

    def record_accept(self, trigger: str, current_firmness: float) -> Optional[float]:
        """
        Record that user accepted a protection suggestion.

        Args:
            trigger: What protection event was accepted
            current_firmness: Current firmness value

        Returns:
            New recommended firmness if adjustment made, None otherwise
        """
        self.state.session_accepts += 1

        # Check if threshold reached for adjustment
        if self.state.session_accepts >= ACCEPT_THRESHOLD:
            # Calculate new firmness
            new_adjustment = self.state.learned_firmness_adjustment + FIRMNESS_INCREASE
            new_firmness = min(FIRMNESS_MAX, current_firmness + new_adjustment)

            # Record the event
            event = {
                "event_type": "accept",
                "timestamp": datetime.now().isoformat(),
                "old_firmness": current_firmness,
                "new_firmness": new_firmness,
                "trigger": trigger,
                "session_count": self.state.session_accepts,
            }
            self.state.adjustment_history.append(event)
            self.state.learned_firmness_adjustment = new_adjustment

            # Reset session count after adjustment
            self.state.session_accepts = 0

            self._save_state()

            logger.info(f"Calibration: Increased firmness {current_firmness:.2f} → {new_firmness:.2f}")
            return new_firmness

        return None

    def get_recommended_firmness(self, base_firmness: float) -> float:
        """
        Get recommended firmness based on learned adjustment.

        Args:
            base_firmness: User's base firmness from profile

        Returns:
            Adjusted firmness value (bounded)
        """
        adjusted = base_firmness + self.state.learned_firmness_adjustment
        return max(FIRMNESS_MIN, min(FIRMNESS_MAX, adjusted))

    def reset_session(self) -> None:
        """Reset session-level counts without affecting learned adjustment."""
        self.state.session_overrides = 0
        self.state.session_accepts = 0
        logger.debug("Reset session calibration counts")

    def get_summary(self) -> Dict[str, Any]:
        """Get calibration summary for display."""
        return {
            "session_overrides": self.state.session_overrides,
            "session_accepts": self.state.session_accepts,
            "learned_adjustment": self.state.learned_firmness_adjustment,
            "recent_events": len(self.state.adjustment_history),
        }


def create_calibration_engine(otto_dir: Optional[Path] = None) -> CalibrationEngine:
    """Factory function to create CalibrationEngine."""
    return CalibrationEngine(otto_dir)


__all__ = [
    "CalibrationEngine",
    "CalibrationState",
    "CalibrationEvent",
    "create_calibration_engine",
    "OVERRIDE_THRESHOLD",
    "ACCEPT_THRESHOLD",
    "FIRMNESS_DECREASE",
    "FIRMNESS_INCREASE",
    "FIRMNESS_MIN",
    "FIRMNESS_MAX",
]
