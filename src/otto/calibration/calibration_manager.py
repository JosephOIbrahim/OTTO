"""
Calibration Manager
===================

Orchestrates all calibration operations for OTTO OS.

This is the main entry point for the calibration subsystem:
- Coordinates CalibrationStore, OutcomeTracker, and CalibrationLearner
- Provides high-level API for calibration operations
- Integrates with cognitive orchestrator via hooks

Architecture:
    ProtocolRouter → CalibrationManager → [Store, Tracker, Learner]
                                       ↓
                              calibration.usda (persistence)

ThinkingMachines [He2025] Compliance:
- Fixed learning pipeline
- Deterministic weight updates
- Reproducible calibration state
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .calibration_store import CalibrationStore, CalibrationValue, create_calibration_store
from .outcome_tracker import OutcomeTracker, Outcome, OutcomeType, create_outcome_tracker
from .calibration_learner import CalibrationLearner, LearnedWeight, create_calibration_learner

logger = logging.getLogger(__name__)


@dataclass
class CalibrationSnapshot:
    """
    A point-in-time snapshot of calibration state.

    Used for debugging and cross-session analysis.
    """
    weights: Dict[str, float]
    confident_values: Dict[str, Any]
    total_outcomes: int
    patterns_detected: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "weights": self.weights,
            "confident_values": self.confident_values,
            "total_outcomes": self.total_outcomes,
            "patterns_detected": self.patterns_detected,
            "suggestions": self.suggestions,
        }


class CalibrationManager:
    """
    Orchestrates calibration operations for OTTO OS.

    Provides a unified interface for:
    - Recording outcomes and learning from them
    - Querying learned values and weights
    - Getting recalibration suggestions
    - Persisting calibration state

    Example:
        >>> manager = CalibrationManager()
        >>> manager.record_outcome(
        ...     expert="validator",
        ...     accepted=True,
        ...     signals=["frustrated"],
        ...     task_type="support"
        ... )
        >>> weights = manager.get_expert_weights()
        >>> print(weights["validator"])  # Slightly higher after acceptance
    """

    DEFAULT_DIR = Path.home() / ".otto" / "calibration"

    def __init__(
        self,
        otto_dir: Path = None,
        learning_rate: float = None,
        auto_save: bool = True,
        persist: bool = True
    ):
        """
        Initialize calibration manager.

        Args:
            otto_dir: Base directory for OTTO data
            learning_rate: Learning rate for weight updates
            auto_save: Whether to auto-save after each update
            persist: Whether to persist data to disk
        """
        self.otto_dir = otto_dir or self.DEFAULT_DIR
        self.auto_save = auto_save
        self.persist = persist

        # Initialize components
        self.store = create_calibration_store(self.otto_dir)
        self.tracker = create_outcome_tracker(self.otto_dir, persist=persist)
        self.learner = create_calibration_learner(self.otto_dir, learning_rate)

        logger.debug(f"CalibrationManager initialized at {self.otto_dir}")

    # =========================================================================
    # Outcome Recording
    # =========================================================================

    def record_outcome(
        self,
        expert: str,
        accepted: bool = True,
        partial: bool = False,
        override: bool = False,
        signals: List[str] = None,
        task_type: str = "general",
        context: Dict[str, Any] = None
    ) -> Dict[str, float]:
        """
        Record an outcome and update weights.

        This is the main learning entry point. Records what happened
        and adjusts expert weights accordingly.

        Args:
            expert: The expert that was selected
            accepted: Whether user accepted the response
            partial: Whether response was partially accepted
            override: Whether user explicitly overrode
            signals: Signals that triggered this expert
            task_type: Type of task
            context: Additional context

        Returns:
            Updated expert weights
        """
        # Determine outcome type
        if override:
            outcome_type = OutcomeType.OVERRIDE
        elif partial:
            outcome_type = OutcomeType.PARTIAL
        elif accepted:
            outcome_type = OutcomeType.ACCEPTED
        else:
            outcome_type = OutcomeType.REJECTED

        # Record in tracker
        outcome = self.tracker.record(
            expert=expert,
            outcome_type=outcome_type,
            signals=signals,
            task_type=task_type,
            context=context,
        )

        # Update weights via learner
        weights = self.learner.update_from_outcome(outcome)

        # Auto-save if enabled
        if self.auto_save:
            self.save()

        logger.debug(
            f"Recorded outcome: {expert} -> {outcome_type.value}, "
            f"new weight: {weights.get(expert, 0):.3f}"
        )

        return weights

    def record_accepted(
        self,
        expert: str,
        signals: List[str] = None,
        **kwargs
    ) -> Dict[str, float]:
        """Convenience method to record an accepted outcome."""
        return self.record_outcome(expert, accepted=True, signals=signals, **kwargs)

    def record_rejected(
        self,
        expert: str,
        signals: List[str] = None,
        **kwargs
    ) -> Dict[str, float]:
        """Convenience method to record a rejected outcome."""
        return self.record_outcome(expert, accepted=False, signals=signals, **kwargs)

    def record_override(
        self,
        expert: str,
        signals: List[str] = None,
        **kwargs
    ) -> Dict[str, float]:
        """Convenience method to record an override outcome."""
        return self.record_outcome(expert, override=True, signals=signals, **kwargs)

    # =========================================================================
    # Calibration Value Management
    # =========================================================================

    def observe(self, name: str, value: Any) -> CalibrationValue:
        """
        Record an observation of a calibration value.

        Uses RC^+xi convergence tracking to build confidence.

        Args:
            name: Value name (e.g., "focus_level", "preferred_altitude")
            value: Observed value

        Returns:
            Updated CalibrationValue with confidence
        """
        cal_value = self.store.record_observation(name, value)

        if self.auto_save:
            self.save()

        return cal_value

    def get_value(self, name: str, default: Any = None) -> Any:
        """Get a calibration value (any confidence)."""
        return self.store.get_value(name, default)

    def get_confident_value(
        self,
        name: str,
        default: Any = None,
        threshold: float = 0.7
    ) -> Any:
        """Get a calibration value only if confident."""
        return self.store.get_confident_value(name, default, threshold)

    def set_value(
        self,
        name: str,
        value: Any,
        confidence: float = None
    ) -> CalibrationValue:
        """
        Explicitly set a calibration value.

        Use this for values that don't need learning (e.g., user preferences).
        """
        cal_value = self.store.set(name, value, confidence)

        if self.auto_save:
            self.save()

        return cal_value

    # =========================================================================
    # Expert Weight Queries
    # =========================================================================

    def get_expert_weights(self) -> Dict[str, float]:
        """Get current expert weights (simple dict)."""
        return self.learner.get_weights()

    def get_expert_weight(self, expert: str) -> float:
        """Get weight for a specific expert."""
        return self.learner.get_weight(expert)

    def get_learned_weights(self) -> Dict[str, LearnedWeight]:
        """Get full LearnedWeight objects with metadata."""
        return self.learner.get_learned_weights()

    def get_weight_adjustment(self, expert: str) -> float:
        """Get how much an expert's weight has changed from base."""
        return self.learner.get_adjustment(expert)

    # =========================================================================
    # Statistics and Analysis
    # =========================================================================

    def get_expert_stats(self, expert: str) -> Dict[str, Any]:
        """Get statistics for a specific expert."""
        return self.tracker.get_expert_stats(expert)

    def get_signal_stats(self, signal: str) -> Dict[str, Any]:
        """Get statistics for a specific signal."""
        return self.tracker.get_signal_stats(signal)

    def get_all_stats(self) -> Dict[str, Any]:
        """Get overall calibration statistics."""
        return self.tracker.get_all_stats()

    def get_patterns(self) -> List[Dict[str, Any]]:
        """
        Detect patterns in outcomes.

        Returns patterns like signal-expert mismatches and declining experts.
        """
        return self.tracker.get_patterns()

    def get_suggestions(self) -> List[Dict[str, Any]]:
        """
        Get recalibration suggestions.

        Based on underperforming experts and declining trends.
        """
        return self.learner.suggest_recalibration()

    # =========================================================================
    # Snapshots and Summaries
    # =========================================================================

    def snapshot(self) -> CalibrationSnapshot:
        """
        Take a snapshot of current calibration state.

        Useful for debugging and cross-session analysis.
        """
        return CalibrationSnapshot(
            weights=self.get_expert_weights(),
            confident_values={
                name: self.store.get_value(name)
                for name in self.store.list_confident_values()
            },
            total_outcomes=len(self.tracker.get_recent(count=10000)),
            patterns_detected=self.get_patterns(),
            suggestions=self.get_suggestions(),
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of calibration state."""
        learner_summary = self.learner.get_summary()
        store_summary = self.store.get_summary()
        tracker_stats = self.get_all_stats()

        return {
            "weights": learner_summary,
            "values": store_summary,
            "outcomes": tracker_stats,
            "patterns": self.get_patterns(),
            "suggestions": self.get_suggestions(),
        }

    # =========================================================================
    # Persistence
    # =========================================================================

    def save(self) -> None:
        """Save all calibration data to disk."""
        if not self.persist:
            return

        self.store.save()
        self.tracker.save()
        self.learner.save()
        logger.debug("Calibration data saved")

    def reset_expert(self, expert: str) -> None:
        """Reset a specific expert's learned weight to base."""
        self.learner.reset_expert(expert)
        if self.auto_save:
            self.save()

    def reset_all_weights(self) -> None:
        """Reset all expert weights to base values."""
        self.learner.reset_all()
        if self.auto_save:
            self.save()

    def clear_outcomes(self) -> None:
        """Clear all recorded outcomes."""
        self.tracker.clear()
        if self.auto_save:
            self.save()

    def clear_values(self) -> None:
        """Clear all calibration values."""
        self.store.clear()
        if self.auto_save:
            self.save()

    def reset_all(self) -> None:
        """Reset all calibration state."""
        self.reset_all_weights()
        self.clear_outcomes()
        self.clear_values()

    # =========================================================================
    # Session Management
    # =========================================================================

    def start_session(self) -> None:
        """Start a new session (for outcome grouping)."""
        self.tracker.start_new_session()

    # =========================================================================
    # Integration Helpers
    # =========================================================================

    def apply_to_routing(self, base_weights: Dict[str, float]) -> Dict[str, float]:
        """
        Apply learned adjustments to base routing weights.

        This is the LIVRPS integration point - calibration layer
        overrides base profile weights.

        Args:
            base_weights: Weights from base profile

        Returns:
            Adjusted weights incorporating learning
        """
        learned = self.get_expert_weights()

        # LIVRPS: Calibration (L12) overrides Base (L11)
        # Use learned weights where available, fall back to base
        adjusted = {}
        for expert, base_weight in base_weights.items():
            if expert in learned:
                # Blend: 70% learned, 30% base (gradual adaptation)
                adjusted[expert] = 0.7 * learned[expert] + 0.3 * base_weight
            else:
                adjusted[expert] = base_weight

        # Normalize to sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def should_adjust_expert(self, expert: str) -> Optional[str]:
        """
        Check if an expert should be adjusted based on patterns.

        Returns suggestion reason if adjustment needed, None otherwise.
        """
        suggestions = self.get_suggestions()
        for suggestion in suggestions:
            if suggestion.get("expert") == expert:
                return suggestion.get("reason")
        return None


def create_calibration_manager(
    otto_dir: Path = None,
    learning_rate: float = None,
    auto_save: bool = True,
    persist: bool = True
) -> CalibrationManager:
    """Factory function to create a CalibrationManager."""
    return CalibrationManager(
        otto_dir=otto_dir,
        learning_rate=learning_rate,
        auto_save=auto_save,
        persist=persist,
    )


__all__ = [
    "CalibrationManager",
    "CalibrationSnapshot",
    "create_calibration_manager",
]
