"""
OTTO Atmosphere Layer
=====================

Transforms rigid, robotic responses into supportive, flowing communication.

Core Philosophy: "The current that carries, not the dam that blocks"

Determinism:
- Sorted pattern lists for deterministic iteration
- Fixed transformation order in pipeline
- Same inputs always produce same outputs
- Seed-based replacement selection
- Sorted expert bypass rules (deterministic)
"""

from .patterns import (
    transform_language,
    LanguageTransformer,
    INSTRUCTIONAL_PATTERNS,
)
from .affirmations import (
    get_affirmation,
    Affirmation,
    AffirmationType,
)
from .permissions import (
    get_permission,
    Permission,
    PermissionType,
    should_grant_permission,
)
from .reframes import (
    get_reframe,
    Reframe,
    detect_struggle,
    REFRAMES,
)
from .energy import (
    match_energy,
    EnergyProfile,
    EnergyLevel,
)
from .pipeline import (
    apply_atmosphere,
    AtmosphereContext,
    AtmospherePipeline,
    TransformPhase,
    EXPERT_BYPASS_RULES,
    REFRAME_ALLOWED_EXPERTS,
)
from .signals import (
    AtmosphereSignals,
    SignalSeverity,
    extract_signals,
    aggregate_session_signals,
)
from .confidence import (
    SignalCategory,
    ConfidenceScore,
    DetectionContext,
    TuningConfig,
    calculate_confidence,
    detect_with_confidence,
    get_highest_confidence,
)
from .metrics import (
    MetricType,
    TransformationMetrics,
    SessionMetrics,
    MetricsCollector,
    TransformationTimer,
    get_metrics_collector,
    record_transformation,
    start_session,
    end_session,
    get_session_summary,
)

__all__ = [
    # Patterns
    "transform_language",
    "LanguageTransformer",
    "INSTRUCTIONAL_PATTERNS",
    # Affirmations
    "get_affirmation",
    "Affirmation",
    "AffirmationType",
    # Permissions
    "get_permission",
    "Permission",
    "PermissionType",
    "should_grant_permission",
    # Reframes
    "get_reframe",
    "Reframe",
    "detect_struggle",
    "REFRAMES",
    # Energy
    "match_energy",
    "EnergyProfile",
    "EnergyLevel",
    # Pipeline
    "apply_atmosphere",
    "AtmosphereContext",
    "AtmospherePipeline",
    "TransformPhase",
    "EXPERT_BYPASS_RULES",
    "REFRAME_ALLOWED_EXPERTS",
    # Signals (cognitive state integration)
    "AtmosphereSignals",
    "SignalSeverity",
    "extract_signals",
    "aggregate_session_signals",
    # Confidence scoring
    "SignalCategory",
    "ConfidenceScore",
    "DetectionContext",
    "TuningConfig",
    "calculate_confidence",
    "detect_with_confidence",
    "get_highest_confidence",
    # Metrics
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
