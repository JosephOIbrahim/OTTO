"""UI style constants — colors, themes, expert palettes.

Platform-agnostic style definitions.  No framework dependency.
Used by TUI (Textual) and any future rendering surfaces.

Constitutional: All labels follow dignity-first language.
No clinical terminology.

All dicts sorted by key at module load.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeColors:
    """OTTO UI color palette.

    Dark theme by default — reduced eye strain for long sessions.
    Colors are hex strings usable by most UI frameworks.
    """

    primary: str = "#6C63FF"
    secondary: str = "#FFB74D"
    success: str = "#4CAF50"
    warning: str = "#FF9800"
    danger: str = "#F44336"
    text: str = "#E0E0E0"
    text_dim: str = "#9E9E9E"
    background: str = "#1E1E2E"
    surface: str = "#2D2D44"


# Default theme instance
DEFAULT_THEME = ThemeColors()


# Expert-specific accent colors Sorted by expert name
EXPERT_COLORS: dict[str, str] = dict(sorted({
    "acknowledger": "#FFEAA7",  # Warm yellow
    "decomposer": "#4ECDC4",    # Teal
    "executor": "#98D8C8",      # Mint
    "guide": "#DDA0DD",         # Plum
    "protector": "#FF6B6B",     # Soft red
    "redirector": "#96CEB4",    # Sage
    "restorer": "#45B7D1",      # Sky blue
}.items()))


# Effort level colors Sorted by level name
EFFORT_COLORS: dict[str, str] = dict(sorted({
    "high": "#FF9800",    # Orange
    "low": "#4CAF50",     # Green
    "max": "#F44336",     # Red
    "medium": "#FFB74D",  # Amber
}.items()))


# Signal category labels — user-facing, constitutional
# Sorted by category name
SIGNAL_LABELS: dict[str, str] = dict(sorted({
    "activity_level": "Activity",
    "app_context": "Current Focus",
    "commit_velocity": "Dev Flow",
    "context_switches": "Focus Changes",
    "day_type": "Day",
    "file_churn": "File Activity",
    "process_load": "System Load",
    "stuck_signal": "Blockers",
    "time_period": "Time",
    "time_pressure": "Time Pressure",
    "uncommitted_changes": "Unsaved Work",
}.items()))
