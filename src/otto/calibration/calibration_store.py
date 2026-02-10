"""
Calibration Store
=================

Persistence layer for learned calibration values.

Stores calibration data in USD ASCII format (calibration.usda) for:
- Cross-session persistence
- Human-readable debugging
- Compatibility with USD tooling

File format:
    #usda 1.0
    def "Calibration" {
        custom string focus_level = "locked_in"
        custom float focus_level:confidence = 0.85
        custom int focus_level:observations = 12
        ...
    }

Determinism:
- Fixed serialization format
- Deterministic load order
- Atomic writes for crash safety
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CalibrationValue:
    """
    A learned calibration value with confidence metadata.

    Attributes:
        name: Value name (e.g., "focus_level", "expert_weight:protector")
        value: The learned value
        confidence: Confidence score 0.0-1.0 (from RC^+xi convergence)
        observations: Number of observations contributing to this value
        last_updated: Timestamp of last update
        stable_count: Consecutive observations with same value
    """
    name: str
    value: Any
    confidence: float = 0.5
    observations: int = 1
    last_updated: float = field(default_factory=time.time)
    stable_count: int = 1

    def update(self, new_value: Any, learning_rate: float = 0.1) -> None:
        """
        Update value with new observation.

        Uses exponential moving average for numeric values,
        mode tracking for categorical values.
        """
        self.observations += 1
        self.last_updated = time.time()

        if new_value == self.value:
            # Same value - increase confidence
            self.stable_count += 1
            self.confidence = min(1.0, self.confidence + learning_rate * 0.5)
        else:
            # Different value - decrease confidence, maybe update
            self.stable_count = 1
            self.confidence = max(0.0, self.confidence - learning_rate)

            # If confidence drops below threshold, switch to new value
            if self.confidence < 0.3:
                self.value = new_value
                self.confidence = 0.5  # Reset to neutral

    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if value is confident enough to use."""
        return self.confidence >= threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalibrationValue':
        """Create from dictionary."""
        return cls(**data)


class CalibrationStore:
    """
    Persistent store for calibration values.

    Manages reading/writing calibration.usda and provides
    type-safe access to learned values.

    Example:
        >>> store = CalibrationStore(Path("~/.otto"))
        >>> store.set("focus_level", "locked_in", confidence=0.8)
        >>> store.save()
        >>> value = store.get("focus_level")
        >>> print(value.value, value.confidence)
        locked_in 0.8
    """

    DEFAULT_DIR = Path.home() / ".otto"
    CALIBRATION_FILE = "calibration.json"  # JSON for reliability, USDA for export
    CALIBRATION_USDA = "calibration.usda"

    def __init__(self, otto_dir: Path = None):
        """
        Initialize calibration store.

        Args:
            otto_dir: Base directory for OTTO data (default: ~/.otto)
        """
        self.otto_dir = otto_dir or self.DEFAULT_DIR
        self.otto_dir.mkdir(parents=True, exist_ok=True)

        self._values: Dict[str, CalibrationValue] = {}
        self._dirty = False

        # Load existing calibration
        self._load()

    def _load(self) -> None:
        """Load calibration from disk."""
        json_path = self.otto_dir / self.CALIBRATION_FILE

        if json_path.exists():
            try:
                data = json.loads(json_path.read_text())
                for name, value_data in data.get("values", {}).items():
                    self._values[name] = CalibrationValue.from_dict(value_data)
                logger.debug(f"Loaded {len(self._values)} calibration values")
            except Exception as e:
                logger.warning(f"Could not load calibration: {e}")
                self._values = {}

    def save(self) -> None:
        """Save calibration to disk (atomic write)."""
        if not self._dirty and self._values:
            return  # No changes

        json_path = self.otto_dir / self.CALIBRATION_FILE

        data = {
            "version": "1.0",
            "updated": time.time(),
            "values": {name: val.to_dict() for name, val in self._values.items()}
        }

        # Atomic write
        temp_path = json_path.with_suffix(".tmp")
        try:
            temp_path.write_text(json.dumps(data, indent=2))
            temp_path.replace(json_path)
            self._dirty = False
            logger.debug(f"Saved {len(self._values)} calibration values")
        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")
            if temp_path.exists():
                temp_path.unlink()

        # Also export USDA for debugging
        self._export_usda()

    def _export_usda(self) -> None:
        """Export calibration as USDA file for debugging."""
        usda_path = self.otto_dir / self.CALIBRATION_USDA

        lines = [
            '#usda 1.0',
            '(',
            '    doc = "OTTO OS Learned Calibration Values"',
            ')',
            '',
            'def "Calibration"',
            '{',
        ]

        for name, val in sorted(self._values.items()):
            # Format value based on type
            if isinstance(val.value, str):
                value_str = f'"{val.value}"'
            elif isinstance(val.value, bool):
                value_str = "true" if val.value else "false"
            elif isinstance(val.value, float):
                value_str = f"{val.value:.4f}"
            else:
                value_str = str(val.value)

            # Safe name (replace special chars)
            safe_name = name.replace(":", "_").replace(".", "_")

            lines.append(f'    custom string {safe_name} = {value_str}')
            lines.append(f'    custom float {safe_name}_confidence = {val.confidence:.3f}')
            lines.append(f'    custom int {safe_name}_observations = {val.observations}')
            lines.append('')

        lines.append('}')
        lines.append('')

        try:
            usda_path.write_text('\n'.join(lines))
        except Exception as e:
            logger.debug(f"Could not export USDA: {e}")

    def get(self, name: str) -> Optional[CalibrationValue]:
        """Get a calibration value by name."""
        return self._values.get(name)

    def get_value(self, name: str, default: Any = None) -> Any:
        """Get just the value (not the CalibrationValue wrapper)."""
        val = self._values.get(name)
        if val is None:
            return default
        return val.value

    def get_confident_value(
        self,
        name: str,
        default: Any = None,
        threshold: float = 0.7
    ) -> Any:
        """Get value only if confidence exceeds threshold."""
        val = self._values.get(name)
        if val is None or not val.is_confident(threshold):
            return default
        return val.value

    def set(
        self,
        name: str,
        value: Any,
        confidence: float = None,
        observations: int = None
    ) -> CalibrationValue:
        """
        Set a calibration value.

        If the value already exists, updates it. Otherwise creates new.

        Args:
            name: Value name
            value: The value to store
            confidence: Optional confidence override
            observations: Optional observation count override

        Returns:
            The CalibrationValue (new or updated)
        """
        if name in self._values:
            existing = self._values[name]
            # Explicit set - directly update the value (no learning behavior)
            existing.value = value
            existing.last_updated = time.time()
            if confidence is not None:
                existing.confidence = confidence
            if observations is not None:
                existing.observations = observations
        else:
            self._values[name] = CalibrationValue(
                name=name,
                value=value,
                confidence=confidence or 0.5,
                observations=observations or 1,
            )

        self._dirty = True
        return self._values[name]

    def record_observation(self, name: str, value: Any) -> CalibrationValue:
        """
        Record an observation of a value.

        Updates existing value with learning, or creates new with low confidence.
        """
        if name in self._values:
            self._values[name].update(value)
        else:
            self._values[name] = CalibrationValue(
                name=name,
                value=value,
                confidence=0.3,  # Low initial confidence
                observations=1,
            )

        self._dirty = True
        return self._values[name]

    def list_values(self) -> List[str]:
        """List all calibration value names."""
        return list(self._values.keys())

    def list_confident_values(self, threshold: float = 0.7) -> List[str]:
        """List only confident calibration value names."""
        return [
            name for name, val in self._values.items()
            if val.is_confident(threshold)
        ]

    def get_all(self) -> Dict[str, CalibrationValue]:
        """Get all calibration values."""
        return self._values.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of calibration state."""
        confident = self.list_confident_values()
        return {
            "total_values": len(self._values),
            "confident_values": len(confident),
            "values": {
                name: {
                    "value": val.value,
                    "confidence": val.confidence,
                    "observations": val.observations,
                }
                for name, val in self._values.items()
            }
        }

    def clear(self) -> None:
        """Clear all calibration values."""
        self._values = {}
        self._dirty = True

    def delete(self, name: str) -> bool:
        """Delete a specific calibration value."""
        if name in self._values:
            del self._values[name]
            self._dirty = True
            return True
        return False


def create_calibration_store(otto_dir: Path = None) -> CalibrationStore:
    """Factory function to create a CalibrationStore."""
    return CalibrationStore(otto_dir)


__all__ = [
    "CalibrationStore",
    "CalibrationValue",
    "create_calibration_store",
]
