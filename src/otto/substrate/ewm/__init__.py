"""
External Working Memory (EWM) Module
====================================

Implements external working memory support for cognitive orchestration.

Components:
- SessionAnchor: Goal tracking with timestamps
- TimeBeacon: Elapsed time estimation (combats time blindness)
- ProjectFriction: Multi-project management with warnings
- EWMManager: Unified state management

ThinkingMachines [He2025] Compliance:
- Deterministic state persistence
- Fixed beacon intervals
- Consistent friction thresholds
"""

from .schemas import (
    EWMState,
    Project,
    ProjectFriction,
    SessionAnchor,
    TimeBeacon,
)
from .manager import EWMManager

# Module-level singleton
_manager: EWMManager | None = None


def get_manager() -> EWMManager:
    """Get or create the singleton EWM manager."""
    global _manager
    if _manager is None:
        _manager = EWMManager()
    return _manager


__all__ = [
    "EWMManager",
    "EWMState",
    "Project",
    "ProjectFriction",
    "SessionAnchor",
    "TimeBeacon",
    "get_manager",
]
