"""
OTTO TUI Widgets
================

[He2025] Compliant widget components for the TUI dashboard.

All widgets follow these principles:
1. Deterministic rendering (same state → same output)
2. No internal mutable state
3. Fixed layout calculations
4. Isolated computation (no cross-widget dependencies)
"""

from .cognitive_state import CognitiveStateWidget
from .project_card import ProjectCardWidget
from .alert_feed import AlertFeedWidget
from .command_bar import CommandBarWidget

__all__ = [
    "CognitiveStateWidget",
    "ProjectCardWidget",
    "AlertFeedWidget",
    "CommandBarWidget",
]
