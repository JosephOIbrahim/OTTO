"""User interface layer — chat, dashboard, styles.

Platform-agnostic components:
    ChatMessage          — Frozen conversation message
    ChatSession          — Core conversation orchestration
    ConversationHistory  — Message management + token estimation
    DashboardState       — Cognitive state for display
    CognitiveSummary     — Human-readable state descriptions

Rendering:
    styles module        — Colors and theme constants
    tui module           — Terminal UI (requires textual)
"""

from otto_v3.ui.chat import ChatMessage, ChatSession, ConversationHistory
from otto_v3.ui.dashboard import (
    CognitiveSummary,
    DashboardState,
    EFFORT_DESCRIPTIONS,
    EXPERT_DESCRIPTIONS,
)
from otto_v3.ui.styles import (
    DEFAULT_THEME,
    EFFORT_COLORS,
    EXPERT_COLORS,
    SIGNAL_LABELS,
    ThemeColors,
)

__all__ = [
    "ChatMessage",
    "ChatSession",
    "CognitiveSummary",
    "ConversationHistory",
    "DashboardState",
    "DEFAULT_THEME",
    "EFFORT_COLORS",
    "EFFORT_DESCRIPTIONS",
    "EXPERT_COLORS",
    "EXPERT_DESCRIPTIONS",
    "SIGNAL_LABELS",
    "ThemeColors",
]
