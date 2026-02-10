"""PRISM signal detection — cognitive input classification.

Two-stage detection pipeline:
    Stage 1 (Local): Fast regex pattern matching, no LLM required (<50ms)
    Stage 2 (Server): Opus 4.6 confirmation + nuance (future, API layer)

This package implements Stage 1. Stage 2 is handled by the API layer
when available, with Stage 1 as the always-available fallback.
"""

from otto.core.prism.signals import CognitiveSignal, Signal
from otto.core.prism.patterns import DetectionPattern, PATTERNS
from otto.core.prism.detector import PRISMDetector

__all__ = [
    "CognitiveSignal",
    "DetectionPattern",
    "PATTERNS",
    "PRISMDetector",
    "Signal",
]
