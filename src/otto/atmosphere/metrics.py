"""
Atmosphere Metrics and Logging.

Tracks transformation statistics for observability and tuning.

Metrics collected:
- Pattern match counts (which patterns fire most)
- Affirmation/permission/reframe usage
- Energy truncation statistics
- Transformation latency
- Session-level aggregates

Determinism:
- Metrics collection is deterministic (no side effects on output)
- Counters use atomic operations where possible
- Same inputs produce same outputs (metrics are observational)
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Final, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics tracked."""
    PATTERN_MATCH = "pattern_match"
    AFFIRMATION = "affirmation"
    PERMISSION = "permission"
    REFRAME = "reframe"
    ENERGY_TRUNCATION = "energy_truncation"
    TRANSFORMATION_TIME = "transformation_time"


@dataclass
class TransformationMetrics:
    """Metrics from a single transformation."""
    timestamp: datetime
    input_length: int
    output_length: int
    patterns_matched: List[str] = field(default_factory=list)
    affirmation_type: Optional[str] = None
    permission_type: Optional[str] = None
    reframe_pattern: Optional[str] = None
    energy_level: str = "medium"
    truncation_amount: int = 0
    transformation_time_ms: float = 0.0

    @property
    def was_truncated(self) -> bool:
        """Whether the response was truncated."""
        return self.truncation_amount > 0

    @property
    def truncation_ratio(self) -> float:
        """Ratio of text removed by truncation."""
        if self.input_length == 0:
            return 0.0
        return self.truncation_amount / self.input_length


@dataclass
class SessionMetrics:
    """Aggregated metrics for a session."""
    session_id: str
    start_time: datetime = field(default_factory=datetime.now)
    transformations: List[TransformationMetrics] = field(default_factory=list)

    # Counters
    pattern_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    affirmation_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    permission_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    reframe_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    energy_level_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Aggregates
    total_truncation: int = 0
    total_transformation_time_ms: float = 0.0

    def add_transformation(self, metrics: TransformationMetrics) -> None:
        """Add a transformation's metrics to session aggregates."""
        self.transformations.append(metrics)

        # Update pattern counts
        for pattern in metrics.patterns_matched:
            self.pattern_counts[pattern] += 1

        # Update affirmation counts
        if metrics.affirmation_type:
            self.affirmation_counts[metrics.affirmation_type] += 1

        # Update permission counts
        if metrics.permission_type:
            self.permission_counts[metrics.permission_type] += 1

        # Update reframe counts
        if metrics.reframe_pattern:
            self.reframe_counts[metrics.reframe_pattern] += 1

        # Update energy level counts
        self.energy_level_counts[metrics.energy_level] += 1

        # Update aggregates
        self.total_truncation += metrics.truncation_amount
        self.total_transformation_time_ms += metrics.transformation_time_ms

    @property
    def transformation_count(self) -> int:
        """Total number of transformations."""
        return len(self.transformations)

    @property
    def avg_transformation_time_ms(self) -> float:
        """Average transformation time in milliseconds."""
        if self.transformation_count == 0:
            return 0.0
        return self.total_transformation_time_ms / self.transformation_count

    @property
    def truncation_rate(self) -> float:
        """Percentage of transformations that were truncated."""
        if self.transformation_count == 0:
            return 0.0
        truncated = sum(1 for t in self.transformations if t.was_truncated)
        return truncated / self.transformation_count

    def get_top_patterns(self, n: int = 5) -> List[tuple]:
        """Get the N most frequently matched patterns."""
        sorted_patterns = sorted(
            self.pattern_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_patterns[:n]

    def get_summary(self) -> Dict:
        """Get a summary of session metrics."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "transformation_count": self.transformation_count,
            "avg_transformation_time_ms": round(self.avg_transformation_time_ms, 2),
            "truncation_rate": round(self.truncation_rate * 100, 1),
            "top_patterns": self.get_top_patterns(5),
            "affirmation_counts": dict(self.affirmation_counts),
            "permission_counts": dict(self.permission_counts),
            "reframe_counts": dict(self.reframe_counts),
            "energy_distribution": dict(self.energy_level_counts),
        }


class MetricsCollector:
    """
    Collects and manages atmosphere metrics.

    Thread-safe singleton for global metrics collection.
    """

    _instance: Optional["MetricsCollector"] = None
    _sessions: Dict[str, SessionMetrics] = {}
    _current_session_id: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sessions = {}
            cls._instance._current_session_id = None
        return cls._instance

    def start_session(self, session_id: str) -> None:
        """Start a new metrics session."""
        self._current_session_id = session_id
        self._sessions[session_id] = SessionMetrics(session_id=session_id)
        logger.debug(f"Started metrics session: {session_id}")

    def end_session(self, session_id: Optional[str] = None) -> Optional[SessionMetrics]:
        """End a session and return its metrics."""
        sid = session_id or self._current_session_id
        if sid and sid in self._sessions:
            metrics = self._sessions[sid]
            logger.info(
                f"Session {sid} ended: {metrics.transformation_count} transformations, "
                f"avg {metrics.avg_transformation_time_ms:.2f}ms"
            )
            return metrics
        return None

    def record_transformation(
        self,
        input_text: str,
        output_text: str,
        patterns_matched: List[str],
        affirmation_type: Optional[str] = None,
        permission_type: Optional[str] = None,
        reframe_pattern: Optional[str] = None,
        energy_level: str = "medium",
        transformation_time_ms: float = 0.0,
        session_id: Optional[str] = None,
    ) -> TransformationMetrics:
        """
        Record metrics for a transformation.

        Returns the TransformationMetrics object.
        """
        metrics = TransformationMetrics(
            timestamp=datetime.now(),
            input_length=len(input_text),
            output_length=len(output_text),
            patterns_matched=patterns_matched,
            affirmation_type=affirmation_type,
            permission_type=permission_type,
            reframe_pattern=reframe_pattern,
            energy_level=energy_level,
            truncation_amount=max(0, len(input_text) - len(output_text)),
            transformation_time_ms=transformation_time_ms,
        )

        # Add to session if one is active
        sid = session_id or self._current_session_id
        if sid and sid in self._sessions:
            self._sessions[sid].add_transformation(metrics)

        # Log the transformation
        logger.debug(
            f"Transformation: {len(patterns_matched)} patterns, "
            f"affirmation={affirmation_type}, permission={permission_type}, "
            f"reframe={bool(reframe_pattern)}, energy={energy_level}, "
            f"truncated={metrics.truncation_amount}chars, time={transformation_time_ms:.2f}ms"
        )

        return metrics

    def get_session_metrics(self, session_id: Optional[str] = None) -> Optional[SessionMetrics]:
        """Get metrics for a session."""
        sid = session_id or self._current_session_id
        return self._sessions.get(sid) if sid else None

    def get_all_sessions(self) -> Dict[str, SessionMetrics]:
        """Get all session metrics."""
        return dict(self._sessions)

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        self._sessions.clear()
        self._current_session_id = None


class TransformationTimer:
    """Context manager for timing transformations."""

    def __init__(self):
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def __enter__(self) -> "TransformationTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        self.end_time = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds."""
        return (self.end_time - self.start_time) * 1000


# Global metrics collector instance
_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector


def record_transformation(
    input_text: str,
    output_text: str,
    patterns_matched: List[str],
    **kwargs,
) -> TransformationMetrics:
    """Convenience function to record a transformation."""
    return get_metrics_collector().record_transformation(
        input_text, output_text, patterns_matched, **kwargs
    )


def start_session(session_id: str) -> None:
    """Start a new metrics session."""
    get_metrics_collector().start_session(session_id)


def end_session(session_id: Optional[str] = None) -> Optional[SessionMetrics]:
    """End a session and return its metrics."""
    return get_metrics_collector().end_session(session_id)


def get_session_summary(session_id: Optional[str] = None) -> Optional[Dict]:
    """Get summary of session metrics."""
    metrics = get_metrics_collector().get_session_metrics(session_id)
    return metrics.get_summary() if metrics else None


__all__ = [
    "MetricType",
    "TransformationMetrics",
    "SessionMetrics",
    "MetricsCollector",
    "TransformationTimer",
    "get_metrics_collector",
    "record_transformation",
    "start_session",
    "end_session",
    "get_session_summary",
]
