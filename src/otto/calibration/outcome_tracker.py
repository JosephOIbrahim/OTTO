"""
Outcome Tracker
===============

Records expert acceptance/rejection patterns for learning.

Tracks:
- Which expert was selected for a task
- Whether the user accepted or rejected the response
- Context signals that led to the selection
- Task characteristics (type, complexity)

This data feeds into the CalibrationLearner for weight updates.

Determinism:
- Fixed outcome categories
- Deterministic outcome scoring
- Bounded history (prevents unbounded memory)
"""

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Deque

logger = logging.getLogger(__name__)


class OutcomeType(Enum):
    """Types of outcomes for expert selections."""
    ACCEPTED = "accepted"           # User accepted response
    REJECTED = "rejected"           # User rejected/corrected response
    PARTIAL = "partial"             # Partially accepted
    IGNORED = "ignored"             # User didn't engage
    OVERRIDE = "override"           # User explicitly overrode


@dataclass
class Outcome:
    """
    A recorded outcome from an expert selection.

    Attributes:
        expert: The expert that was selected
        outcome_type: Type of outcome (accepted, rejected, etc.)
        signals: Signals that triggered this expert
        task_type: Type of task (implement, debug, explore, etc.)
        context: Additional context about the interaction
        timestamp: When this outcome occurred
        session_id: Session identifier for grouping
    """
    expert: str
    outcome_type: OutcomeType
    signals: List[str] = field(default_factory=list)
    task_type: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""

    def score(self) -> float:
        """
        Convert outcome to numeric score for learning.

        Returns:
            Score between 0.0 (bad) and 1.0 (good)
        """
        scores = {
            OutcomeType.ACCEPTED: 1.0,
            OutcomeType.PARTIAL: 0.7,
            OutcomeType.IGNORED: 0.5,
            OutcomeType.REJECTED: 0.2,
            OutcomeType.OVERRIDE: 0.0,
        }
        return scores.get(self.outcome_type, 0.5)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["outcome_type"] = self.outcome_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Outcome':
        """Create from dictionary."""
        data = data.copy()
        data["outcome_type"] = OutcomeType(data["outcome_type"])
        return cls(**data)


class OutcomeTracker:
    """
    Tracks outcomes of expert selections for learning.

    Maintains a bounded history of recent outcomes and provides
    aggregation methods for learning algorithms.

    Example:
        >>> tracker = OutcomeTracker()
        >>> tracker.record(
        ...     expert="validator",
        ...     outcome_type=OutcomeType.ACCEPTED,
        ...     signals=["frustrated", "caps"],
        ...     task_type="support"
        ... )
        >>> stats = tracker.get_expert_stats("validator")
        >>> print(f"Acceptance rate: {stats['acceptance_rate']:.2f}")
    """

    MAX_OUTCOMES = 500  # Bounded history
    DEFAULT_DIR = Path.home() / ".otto" / "calibration"
    OUTCOMES_FILE = "outcomes.json"

    def __init__(
        self,
        otto_dir: Path = None,
        max_outcomes: int = None,
        persist: bool = True
    ):
        """
        Initialize outcome tracker.

        Args:
            otto_dir: Base directory for OTTO data
            max_outcomes: Maximum outcomes to keep in memory
            persist: Whether to persist outcomes to disk
        """
        self.otto_dir = otto_dir or self.DEFAULT_DIR
        self.max_outcomes = max_outcomes or self.MAX_OUTCOMES
        self.persist = persist

        self._outcomes: Deque[Outcome] = deque(maxlen=self.max_outcomes)
        self._session_counter = 0
        self._session_id = self._generate_session_id()

        if persist:
            self.otto_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    def _load(self) -> None:
        """Load outcomes from disk."""
        outcomes_path = self.otto_dir / self.OUTCOMES_FILE

        if outcomes_path.exists():
            try:
                data = json.loads(outcomes_path.read_text())
                for outcome_data in data.get("outcomes", []):
                    self._outcomes.append(Outcome.from_dict(outcome_data))
                logger.debug(f"Loaded {len(self._outcomes)} outcomes")
            except Exception as e:
                logger.warning(f"Could not load outcomes: {e}")

    def save(self) -> None:
        """Save outcomes to disk."""
        if not self.persist:
            return

        outcomes_path = self.otto_dir / self.OUTCOMES_FILE

        data = {
            "version": "1.0",
            "updated": time.time(),
            "outcomes": [o.to_dict() for o in self._outcomes]
        }

        # Atomic write
        temp_path = outcomes_path.with_suffix(".tmp")
        try:
            temp_path.write_text(json.dumps(data, indent=2))
            temp_path.replace(outcomes_path)
            logger.debug(f"Saved {len(self._outcomes)} outcomes")
        except Exception as e:
            logger.error(f"Failed to save outcomes: {e}")
            if temp_path.exists():
                temp_path.unlink()

    def record(
        self,
        expert: str,
        outcome_type: OutcomeType,
        signals: List[str] = None,
        task_type: str = "general",
        context: Dict[str, Any] = None
    ) -> Outcome:
        """
        Record an outcome.

        Args:
            expert: The expert that was selected
            outcome_type: Type of outcome
            signals: Signals that triggered this expert
            task_type: Type of task
            context: Additional context

        Returns:
            The recorded Outcome
        """
        outcome = Outcome(
            expert=expert,
            outcome_type=outcome_type,
            signals=signals or [],
            task_type=task_type,
            context=context or {},
            session_id=self._session_id,
        )

        self._outcomes.append(outcome)
        logger.debug(f"Recorded outcome: {expert} -> {outcome_type.value}")

        return outcome

    def record_accepted(self, expert: str, signals: List[str] = None, **kwargs) -> Outcome:
        """Convenience method to record an accepted outcome."""
        return self.record(expert, OutcomeType.ACCEPTED, signals, **kwargs)

    def record_rejected(self, expert: str, signals: List[str] = None, **kwargs) -> Outcome:
        """Convenience method to record a rejected outcome."""
        return self.record(expert, OutcomeType.REJECTED, signals, **kwargs)

    def record_override(self, expert: str, signals: List[str] = None, **kwargs) -> Outcome:
        """Convenience method to record an override outcome."""
        return self.record(expert, OutcomeType.OVERRIDE, signals, **kwargs)

    def get_recent(self, count: int = 50) -> List[Outcome]:
        """Get the most recent outcomes."""
        return list(self._outcomes)[-count:]

    def get_expert_outcomes(self, expert: str) -> List[Outcome]:
        """Get all outcomes for a specific expert."""
        return [o for o in self._outcomes if o.expert == expert]

    def get_signal_outcomes(self, signal: str) -> List[Outcome]:
        """Get all outcomes where a specific signal was present."""
        return [o for o in self._outcomes if signal in o.signals]

    def get_expert_stats(self, expert: str) -> Dict[str, Any]:
        """
        Get statistics for a specific expert.

        Returns:
            Dict with acceptance_rate, total_outcomes, score_avg, etc.
        """
        outcomes = self.get_expert_outcomes(expert)

        if not outcomes:
            return {
                "expert": expert,
                "total_outcomes": 0,
                "acceptance_rate": 0.5,  # Neutral default
                "score_avg": 0.5,
                "recent_trend": "neutral",
            }

        accepted = sum(1 for o in outcomes if o.outcome_type == OutcomeType.ACCEPTED)
        scores = [o.score() for o in outcomes]

        # Calculate recent trend (last 10 vs previous 10)
        recent = scores[-10:] if len(scores) >= 10 else scores
        previous = scores[-20:-10] if len(scores) >= 20 else scores[:len(scores)//2]

        recent_avg = sum(recent) / len(recent) if recent else 0.5
        previous_avg = sum(previous) / len(previous) if previous else 0.5

        if recent_avg > previous_avg + 0.1:
            trend = "improving"
        elif recent_avg < previous_avg - 0.1:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "expert": expert,
            "total_outcomes": len(outcomes),
            "acceptance_rate": accepted / len(outcomes),
            "score_avg": sum(scores) / len(scores),
            "recent_trend": trend,
            "outcome_counts": {
                ot.value: sum(1 for o in outcomes if o.outcome_type == ot)
                for ot in OutcomeType
            }
        }

    def get_signal_stats(self, signal: str) -> Dict[str, Any]:
        """Get statistics for outcomes involving a specific signal."""
        outcomes = self.get_signal_outcomes(signal)

        if not outcomes:
            return {
                "signal": signal,
                "total_outcomes": 0,
                "acceptance_rate": 0.5,
                "experts_used": {},
            }

        accepted = sum(1 for o in outcomes if o.outcome_type == OutcomeType.ACCEPTED)

        # Count expert usage for this signal
        expert_counts = {}
        for o in outcomes:
            expert_counts[o.expert] = expert_counts.get(o.expert, 0) + 1

        return {
            "signal": signal,
            "total_outcomes": len(outcomes),
            "acceptance_rate": accepted / len(outcomes),
            "experts_used": expert_counts,
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        if not self._outcomes:
            return {
                "total_outcomes": 0,
                "experts": {},
                "overall_acceptance_rate": 0.5,
            }

        # Get unique experts
        experts = set(o.expert for o in self._outcomes)

        return {
            "total_outcomes": len(self._outcomes),
            "experts": {exp: self.get_expert_stats(exp) for exp in experts},
            "overall_acceptance_rate": sum(
                1 for o in self._outcomes if o.outcome_type == OutcomeType.ACCEPTED
            ) / len(self._outcomes),
            "session_count": len(set(o.session_id for o in self._outcomes)),
        }

    def get_patterns(self) -> List[Dict[str, Any]]:
        """
        Detect patterns in outcomes for learning.

        Returns patterns like:
        - "signal X always rejected with expert Y"
        - "expert Z improving over time"
        """
        patterns = []

        # Pattern 1: Signal-expert rejection patterns
        signals = set()
        for o in self._outcomes:
            signals.update(o.signals)

        for signal in signals:
            signal_stats = self.get_signal_stats(signal)
            if signal_stats["total_outcomes"] >= 5:
                for expert, count in signal_stats["experts_used"].items():
                    expert_outcomes = [
                        o for o in self._outcomes
                        if o.expert == expert and signal in o.signals
                    ]
                    if len(expert_outcomes) >= 3:
                        rejection_rate = sum(
                            1 for o in expert_outcomes
                            if o.outcome_type in (OutcomeType.REJECTED, OutcomeType.OVERRIDE)
                        ) / len(expert_outcomes)

                        if rejection_rate >= 0.7:
                            patterns.append({
                                "type": "signal_expert_mismatch",
                                "signal": signal,
                                "expert": expert,
                                "rejection_rate": rejection_rate,
                                "observations": len(expert_outcomes),
                                "suggestion": f"Consider different expert for '{signal}'"
                            })

        # Pattern 2: Expert performance trends
        experts = set(o.expert for o in self._outcomes)
        for expert in experts:
            stats = self.get_expert_stats(expert)
            if stats["total_outcomes"] >= 10:
                if stats["recent_trend"] == "declining" and stats["score_avg"] < 0.5:
                    patterns.append({
                        "type": "expert_declining",
                        "expert": expert,
                        "score_avg": stats["score_avg"],
                        "trend": stats["recent_trend"],
                        "suggestion": f"Expert '{expert}' may need recalibration"
                    })

        return patterns

    def clear(self) -> None:
        """Clear all outcomes."""
        self._outcomes.clear()

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        self._session_counter += 1
        return f"session-{int(time.time())}-{self._session_counter}"

    def start_new_session(self) -> None:
        """Start a new session (updates session_id)."""
        self._session_id = self._generate_session_id()


def create_outcome_tracker(
    otto_dir: Path = None,
    persist: bool = True
) -> OutcomeTracker:
    """Factory function to create an OutcomeTracker."""
    return OutcomeTracker(otto_dir, persist=persist)


__all__ = [
    "OutcomeTracker",
    "Outcome",
    "OutcomeType",
    "create_outcome_tracker",
]
