"""
Production Hardening Module
===========================

Provides production reliability features for cognitive state management.

Components:
- StateManager: Graceful degradation, backup on write, recovery
- HandoffManager: Session end detection, cross-session continuity
- StateResult: Operation result with metadata

ThinkingMachines [He2025] Compliance:
- Deterministic checksums (SHA256, sorted keys)
- Consistent default handling
- Reproducible backup timestamps (microsecond precision)
- Fixed handoff detection patterns
"""

from .state_manager import StateManager, StateResult
from .handoff import HandoffDocument, HandoffManager

# Module-level singletons
_state_manager: StateManager | None = None
_handoff_manager: HandoffManager | None = None


def get_state_manager() -> StateManager:
    """Get or create the singleton state manager."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def get_handoff_manager() -> HandoffManager:
    """Get or create the singleton handoff manager."""
    global _handoff_manager
    if _handoff_manager is None:
        _handoff_manager = HandoffManager()
    return _handoff_manager


__all__ = [
    "HandoffDocument",
    "HandoffManager",
    "StateManager",
    "StateResult",
    "get_handoff_manager",
    "get_state_manager",
]
