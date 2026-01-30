"""
Calibration Learner
===================

Implements Hebbian learning with bounded weights for expert calibration.

Learning rule:
    w_new = w_old + alpha * (outcome - expected) * activation

Bounds:
- Safety experts (validator, restorer) have minimum weight floors
- No expert can exceed maximum weight ceiling
- Total weights normalized to sum to 1.0

ThinkingMachines [He2025] Compliance:
- Fixed learning rate
- Fixed weight bounds
- Deterministic update formula
- Reproducible weight evolution
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .outcome_tracker import OutcomeTracker, Outcome, OutcomeType

logger = logging.getLogger(__name__)


@dataclass
class LearnedWeight:
    """
    A learned expert weight with metadata.

    Attributes:
        expert: Expert name
        weight: Current weight (0.0-1.0, normalized)
        base_weight: Original weight before learning
        updates: Number of weight updates
        last_outcome_score: Score from last outcome
        trend: Recent trend (improving/stable/declining)
    """
    expert: str
    weight: float
    base_weight: float
    updates: int = 0
    last_outcome_score: float = 0.5
    trend: str = "stable"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearnedWeight':
        """Create from dictionary."""
        return cls(**data)


class CalibrationLearner:
    """
    Implements Hebbian learning for expert weight calibration.

    Uses outcome feedback to adjust expert selection weights,
    respecting safety floors and normalization constraints.

    Example:
        >>> learner = CalibrationLearner()
        >>> learner.update_from_outcome(Outcome(
        ...     expert="validator",
        ...     outcome_type=OutcomeType.ACCEPTED,
        ...     signals=["frustrated"]
        ... ))
        >>> weights = learner.get_weights()
        >>> print(weights["validator"])  # Should be slightly higher
    """

    # Default expert weights (equal distribution)
    DEFAULT_WEIGHTS = {
        "validator": 1/7,
        "scaffolder": 1/7,
        "restorer": 1/7,
        "refocuser": 1/7,
        "celebrator": 1/7,
        "socratic": 1/7,
        "direct": 1/7,
    }

    # Safety floors - these experts cannot go below these weights
    # This ensures safety-critical experts are always available
    WEIGHT_FLOORS = {
        "validator": 0.10,   # Safety: emotional support
        "restorer": 0.08,    # Safety: burnout prevention
        "scaffolder": 0.05,  # Important for stuck users
    }

    # Maximum weight for any expert (prevents over-specialization)
    WEIGHT_CEILING = 0.40

    # Learning parameters
    LEARNING_RATE = 0.05
    MOMENTUM = 0.9  # For smoothing updates

    DEFAULT_DIR = Path.home() / ".otto" / "calibration"
    WEIGHTS_FILE = "learned_weights.json"

    def __init__(
        self,
        otto_dir: Path = None,
        learning_rate: float = None,
        initial_weights: Dict[str, float] = None
    ):
        """
        Initialize calibration learner.

        Args:
            otto_dir: Base directory for OTTO data
            learning_rate: Learning rate for weight updates
            initial_weights: Optional custom initial weights
        """
        self.otto_dir = otto_dir or self.DEFAULT_DIR
        self.learning_rate = learning_rate or self.LEARNING_RATE

        self._weights: Dict[str, LearnedWeight] = {}
        self._velocity: Dict[str, float] = {}  # For momentum

        # Initialize weights
        base_weights = initial_weights or self.DEFAULT_WEIGHTS
        for expert, weight in base_weights.items():
            self._weights[expert] = LearnedWeight(
                expert=expert,
                weight=weight,
                base_weight=weight,
            )
            self._velocity[expert] = 0.0

        # Load persisted weights
        self.otto_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load learned weights from disk."""
        weights_path = self.otto_dir / self.WEIGHTS_FILE

        if weights_path.exists():
            try:
                data = json.loads(weights_path.read_text())
                for expert, weight_data in data.get("weights", {}).items():
                    if expert in self._weights:
                        self._weights[expert] = LearnedWeight.from_dict(weight_data)
                logger.debug(f"Loaded learned weights for {len(self._weights)} experts")
            except Exception as e:
                logger.warning(f"Could not load learned weights: {e}")

    def save(self) -> None:
        """Save learned weights to disk."""
        weights_path = self.otto_dir / self.WEIGHTS_FILE

        data = {
            "version": "1.0",
            "updated": time.time(),
            "learning_rate": self.learning_rate,
            "weights": {exp: w.to_dict() for exp, w in self._weights.items()}
        }

        # Atomic write
        temp_path = weights_path.with_suffix(".tmp")
        try:
            temp_path.write_text(json.dumps(data, indent=2))
            temp_path.replace(weights_path)
            logger.debug("Saved learned weights")
        except Exception as e:
            logger.error(f"Failed to save learned weights: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def update_from_outcome(self, outcome: Outcome) -> Dict[str, float]:
        """
        Update weights based on an outcome.

        Implements Hebbian learning:
            delta = alpha * (outcome_score - expected) * activation
            w_new = w_old + momentum * velocity + delta

        Args:
            outcome: The outcome to learn from

        Returns:
            Updated weights dictionary
        """
        expert = outcome.expert
        if expert not in self._weights:
            logger.warning(f"Unknown expert in outcome: {expert}")
            return self.get_weights()

        # Calculate outcome score (0.0 to 1.0)
        score = outcome.score()

        # Expected score is current weight (normalized expectation)
        current_weight = self._weights[expert].weight
        expected = current_weight

        # Calculate delta with Hebbian rule
        # activation = 1.0 (the expert was selected)
        delta = self.learning_rate * (score - expected)

        # Apply momentum
        self._velocity[expert] = (
            self.MOMENTUM * self._velocity[expert] + delta
        )

        # Update weight
        new_weight = current_weight + self._velocity[expert]

        # Apply bounds
        new_weight = self._apply_bounds(expert, new_weight)

        # Update learned weight
        self._weights[expert].weight = new_weight
        self._weights[expert].updates += 1
        self._weights[expert].last_outcome_score = score

        # Update trend
        self._update_trend(expert, score)

        # Normalize all weights
        self._normalize_weights()

        logger.debug(
            f"Updated {expert}: {current_weight:.3f} -> {new_weight:.3f} "
            f"(score={score:.2f}, delta={delta:.4f})"
        )

        return self.get_weights()

    def _apply_bounds(self, expert: str, weight: float) -> float:
        """Apply floor and ceiling bounds to a weight."""
        # Apply floor
        floor = self.WEIGHT_FLOORS.get(expert, 0.01)
        weight = max(floor, weight)

        # Apply ceiling
        weight = min(self.WEIGHT_CEILING, weight)

        return weight

    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1.0."""
        total = sum(w.weight for w in self._weights.values())
        if total > 0:
            for w in self._weights.values():
                w.weight /= total

    def _update_trend(self, expert: str, recent_score: float) -> None:
        """Update trend for an expert based on recent outcomes."""
        lw = self._weights[expert]

        if lw.updates < 5:
            lw.trend = "stable"
            return

        # Simple trend based on weight change
        weight_change = lw.weight - lw.base_weight

        if weight_change > 0.05:
            lw.trend = "improving"
        elif weight_change < -0.05:
            lw.trend = "declining"
        else:
            lw.trend = "stable"

    def update_batch(self, outcomes: List[Outcome]) -> Dict[str, float]:
        """
        Update weights from a batch of outcomes.

        Processes outcomes in order for determinism.

        Args:
            outcomes: List of outcomes to learn from

        Returns:
            Updated weights dictionary
        """
        for outcome in outcomes:
            self.update_from_outcome(outcome)

        return self.get_weights()

    def get_weights(self) -> Dict[str, float]:
        """Get current weights as simple dictionary."""
        return {exp: w.weight for exp, w in self._weights.items()}

    def get_learned_weights(self) -> Dict[str, LearnedWeight]:
        """Get full LearnedWeight objects."""
        return self._weights.copy()

    def get_weight(self, expert: str) -> float:
        """Get weight for a specific expert."""
        if expert in self._weights:
            return self._weights[expert].weight
        return self.DEFAULT_WEIGHTS.get(expert, 1/7)

    def get_adjustment(self, expert: str) -> float:
        """Get the adjustment from base weight."""
        if expert in self._weights:
            lw = self._weights[expert]
            return lw.weight - lw.base_weight
        return 0.0

    def reset_expert(self, expert: str) -> None:
        """Reset an expert's weight to base."""
        if expert in self._weights:
            lw = self._weights[expert]
            lw.weight = lw.base_weight
            lw.updates = 0
            lw.trend = "stable"
            self._velocity[expert] = 0.0
            self._normalize_weights()

    def reset_all(self) -> None:
        """Reset all weights to base values."""
        for expert in self._weights:
            self.reset_expert(expert)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of learned weights."""
        return {
            "learning_rate": self.learning_rate,
            "total_updates": sum(w.updates for w in self._weights.values()),
            "weights": {
                exp: {
                    "current": w.weight,
                    "base": w.base_weight,
                    "adjustment": w.weight - w.base_weight,
                    "updates": w.updates,
                    "trend": w.trend,
                }
                for exp, w in self._weights.items()
            }
        }

    def suggest_recalibration(self) -> List[Dict[str, Any]]:
        """
        Suggest experts that may need recalibration.

        Returns list of suggestions based on:
        - Large negative adjustments (expert underperforming)
        - High update count with declining trend
        """
        suggestions = []

        for exp, lw in self._weights.items():
            adjustment = lw.weight - lw.base_weight

            # Significant negative adjustment
            if adjustment < -0.05 and lw.updates >= 10:
                suggestions.append({
                    "expert": exp,
                    "reason": "underperforming",
                    "adjustment": adjustment,
                    "updates": lw.updates,
                    "recommendation": f"Consider when to use '{exp}' expert"
                })

            # Declining trend with many updates
            if lw.trend == "declining" and lw.updates >= 20:
                suggestions.append({
                    "expert": exp,
                    "reason": "declining_trend",
                    "trend": lw.trend,
                    "updates": lw.updates,
                    "recommendation": f"'{exp}' expert effectiveness declining"
                })

        return suggestions


def create_calibration_learner(
    otto_dir: Path = None,
    learning_rate: float = None
) -> CalibrationLearner:
    """Factory function to create a CalibrationLearner."""
    return CalibrationLearner(otto_dir, learning_rate)


__all__ = [
    "CalibrationLearner",
    "LearnedWeight",
    "create_calibration_learner",
]
