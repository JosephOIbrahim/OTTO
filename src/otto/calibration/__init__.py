"""
Calibration Module
==================

Cross-session learning and user preference adaptation.

This module implements LIVRPS Layer 12 (Calibration) - learned overrides
that persist across sessions and adapt to user behavior patterns.

Architecture:
    Session (L13) → Calibration (L12) → Base Profile (L11) → Defaults (L10)

Components:
- CalibrationStore: Persistence layer for learned values (calibration.usda)
- OutcomeTracker: Records expert acceptance/rejection patterns
- CalibrationLearner: Hebbian learning with bounded weights
- ConfidenceScorer: RC^+xi convergence for learned values
- CalibrationManager: Orchestrates all calibration operations

Determinism:
- Fixed learning rate and bounds
- Deterministic weight updates
- Reproducible calibration values
"""

from .calibration_store import (
    CalibrationStore,
    CalibrationValue,
    create_calibration_store,
)

from .outcome_tracker import (
    OutcomeTracker,
    Outcome,
    OutcomeType,
    create_outcome_tracker,
)

from .calibration_learner import (
    CalibrationLearner,
    LearnedWeight,
    create_calibration_learner,
)

from .calibration_manager import (
    CalibrationManager,
    create_calibration_manager,
)

__all__ = [
    # Store
    "CalibrationStore",
    "CalibrationValue",
    "create_calibration_store",
    # Outcomes
    "OutcomeTracker",
    "Outcome",
    "OutcomeType",
    "create_outcome_tracker",
    # Learning
    "CalibrationLearner",
    "LearnedWeight",
    "create_calibration_learner",
    # Manager
    "CalibrationManager",
    "create_calibration_manager",
]
