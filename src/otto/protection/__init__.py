"""
Protection Module
=================

OTTO's core protection layer - "AI that protects you from yourself."

This module detects overuse patterns and offers protection without
being patronizing. It respects user autonomy while providing safety nets.

Key Components:
- OveruseDetector: Detects patterns suggesting user is pushing too hard
- ProtectionEngine: Makes protection decisions based on state + preferences
- CalibrationEngine: Learns from overrides to adjust protection firmness
"""

from .overuse_detector import (
    OveruseDetector,
    OveruseSignal,
    create_overuse_detector,
)

from .protection_engine import (
    ProtectionEngine,
    ProtectionDecision,
    ProtectionAction,
    create_protection_engine,
)

from .calibration import (
    CalibrationEngine,
    CalibrationState,
    create_calibration_engine,
    OVERRIDE_THRESHOLD,
    ACCEPT_THRESHOLD,
    FIRMNESS_MIN,
    FIRMNESS_MAX,
)

__all__ = [
    'OveruseDetector',
    'OveruseSignal',
    'create_overuse_detector',
    'ProtectionEngine',
    'ProtectionDecision',
    'ProtectionAction',
    'create_protection_engine',
    'CalibrationEngine',
    'CalibrationState',
    'create_calibration_engine',
    'OVERRIDE_THRESHOLD',
    'ACCEPT_THRESHOLD',
    'FIRMNESS_MIN',
    'FIRMNESS_MAX',
]
