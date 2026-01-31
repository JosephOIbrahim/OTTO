"""
OTTO TUI Constants
==================

[He2025] Compliance: All mappings are FIXED at module load time.

This module defines all constant mappings used throughout the TUI.
No runtime variation is permitted. These constants ensure that:
1. Same state → Same visual output (deterministic rendering)
2. Fixed evaluation order (tuple ordering preserves insertion order)
3. No batch-variance (widget isolation)

Reference: He, Horace and Thinking Machines Lab,
"Defeating Nondeterminism in LLM Inference", Sep 2025.
"""

from typing import Tuple, Final

# =============================================================================
# VERSION - Increment on any behavioral change
# =============================================================================

TUI_VERSION: Final[str] = "1.0.0"
HE2025_COMPLIANT: Final[bool] = True

# =============================================================================
# BURNOUT LEVEL MAPPINGS
# [He2025]: Fixed mapping, no runtime variation
# =============================================================================

# Ordered tuple (not dict) to ensure deterministic iteration
BURNOUT_LEVELS: Final[Tuple[str, ...]] = ("GREEN", "YELLOW", "ORANGE", "RED")

# FIXED color mapping: level → (rich_color, hex_code)
BURNOUT_COLORS: Final[dict] = {
    "GREEN": ("green", "#10b981"),
    "YELLOW": ("yellow", "#f59e0b"),
    "ORANGE": ("dark_orange", "#f97316"),
    "RED": ("red", "#ef4444"),
}

# FIXED icon mapping
BURNOUT_ICONS: Final[dict] = {
    "GREEN": "●",
    "YELLOW": "◐",
    "ORANGE": "◑",
    "RED": "○",
}

# FIXED progress bar segments (out of 10)
BURNOUT_SEGMENTS: Final[dict] = {
    "GREEN": 2,
    "YELLOW": 4,
    "ORANGE": 7,
    "RED": 10,
}

# FIXED status text
BURNOUT_STATUS_TEXT: Final[dict] = {
    "GREEN": "Healthy",
    "YELLOW": "Elevated",
    "ORANGE": "Warning",
    "RED": "Critical",
}

# =============================================================================
# ENERGY LEVEL MAPPINGS
# [He2025]: Fixed mapping, no runtime variation
# =============================================================================

ENERGY_LEVELS: Final[Tuple[str, ...]] = ("high", "medium", "low", "depleted")

ENERGY_COLORS: Final[dict] = {
    "high": ("bright_green", "#22c55e"),
    "medium": ("yellow", "#eab308"),
    "low": ("dark_orange", "#f97316"),
    "depleted": ("red", "#ef4444"),
}

ENERGY_ICONS: Final[dict] = {
    "high": "████████",
    "medium": "██████░░",
    "low": "████░░░░",
    "depleted": "██░░░░░░",
}

ENERGY_PERCENTAGES: Final[dict] = {
    "high": 100,
    "medium": 75,
    "low": 50,
    "depleted": 25,
}

# =============================================================================
# MOMENTUM PHASE MAPPINGS
# [He2025]: Fixed mapping, no runtime variation
# =============================================================================

MOMENTUM_PHASES: Final[Tuple[str, ...]] = (
    "cold_start",
    "building",
    "rolling",
    "peak",
    "crashed",
)

MOMENTUM_COLORS: Final[dict] = {
    "cold_start": ("dim", "#6b7280"),
    "building": ("cyan", "#06b6d4"),
    "rolling": ("green", "#22c55e"),
    "peak": ("bright_yellow", "#fbbf24"),
    "crashed": ("red", "#ef4444"),
}

MOMENTUM_ICONS: Final[dict] = {
    "cold_start": "○",
    "building": "◔",
    "rolling": "◑",
    "peak": "●",
    "crashed": "✕",
}

MOMENTUM_DESCRIPTIONS: Final[dict] = {
    "cold_start": "Starting up",
    "building": "Gaining momentum",
    "rolling": "In flow",
    "peak": "Peak performance",
    "crashed": "Recovery needed",
}

# =============================================================================
# MODE MAPPINGS
# [He2025]: Fixed mapping, no runtime variation
# =============================================================================

MODES: Final[Tuple[str, ...]] = (
    "focused",
    "exploring",
    "teaching",
    "recovery",
)

MODE_COLORS: Final[dict] = {
    "focused": ("bright_blue", "#3b82f6"),
    "exploring": ("magenta", "#a855f7"),
    "teaching": ("cyan", "#06b6d4"),
    "recovery": ("yellow", "#eab308"),
}

MODE_ICONS: Final[dict] = {
    "focused": "◎",
    "exploring": "◇",
    "teaching": "◈",
    "recovery": "◌",
}

# =============================================================================
# ALTITUDE MAPPINGS
# [He2025]: Fixed mapping, no runtime variation
# =============================================================================

ALTITUDES: Final[Tuple[str, ...]] = (
    "30000ft",
    "15000ft",
    "5000ft",
    "Ground",
)

ALTITUDE_DESCRIPTIONS: Final[dict] = {
    "30000ft": "Vision/Goals (WHY)",
    "15000ft": "Architecture (HOW)",
    "5000ft": "Components",
    "Ground": "Code/Syntax",
}

ALTITUDE_COLORS: Final[dict] = {
    "30000ft": ("bright_cyan", "#22d3ee"),
    "15000ft": ("cyan", "#06b6d4"),
    "5000ft": ("blue", "#3b82f6"),
    "Ground": ("dim", "#6b7280"),
}

# =============================================================================
# PROJECT STATUS MAPPINGS
# [He2025]: Fixed mapping, no runtime variation
# =============================================================================

PROJECT_STATUSES: Final[Tuple[str, ...]] = (
    "FOCUS",
    "HOLDING",
    "BACKGROUND",
    "PARKED",
    "ARCHIVED",
)

PROJECT_STATUS_COLORS: Final[dict] = {
    "FOCUS": ("bright_green", "#22c55e"),
    "HOLDING": ("yellow", "#eab308"),
    "BACKGROUND": ("dim", "#6b7280"),
    "PARKED": ("dark_orange", "#f97316"),
    "ARCHIVED": ("dim", "#4b5563"),
}

PROJECT_STATUS_ICONS: Final[dict] = {
    "FOCUS": "◆",
    "HOLDING": "◇",
    "BACKGROUND": "○",
    "PARKED": "◌",
    "ARCHIVED": "·",
}

# =============================================================================
# ALERT SEVERITY MAPPINGS
# [He2025]: Fixed mapping, no runtime variation
# =============================================================================

ALERT_SEVERITIES: Final[Tuple[str, ...]] = (
    "info",
    "warning",
    "critical",
    "error",
)

ALERT_COLORS: Final[dict] = {
    "info": ("blue", "#3b82f6"),
    "warning": ("yellow", "#f59e0b"),
    "critical": ("red", "#ef4444"),
    "error": ("bright_red", "#dc2626"),
}

ALERT_ICONS: Final[dict] = {
    "info": "ℹ",
    "warning": "⚠",
    "critical": "⛔",
    "error": "✕",
}

# =============================================================================
# LAYOUT CONSTANTS
# [He2025]: Fixed layout, no adaptive computation
# =============================================================================

# Fixed widget order (never changes)
WIDGET_ORDER: Final[Tuple[str, ...]] = (
    "header",
    "cognitive_state",
    "project_card",
    "alert_feed",
    "command_bar",
    "footer",
)

# Fixed dimensions
MIN_WIDTH: Final[int] = 60
MIN_HEIGHT: Final[int] = 20
HEADER_HEIGHT: Final[int] = 3
FOOTER_HEIGHT: Final[int] = 2
ALERT_FEED_MAX_ITEMS: Final[int] = 5

# =============================================================================
# KEYBOARD SHORTCUTS
# [He2025]: Fixed mapping, deterministic command dispatch
# =============================================================================

# Ordered tuple of (key, command, description)
KEYBOARD_SHORTCUTS: Final[Tuple[Tuple[str, str, str], ...]] = (
    ("h", "health", "System health"),
    ("s", "state", "Cognitive state"),
    ("p", "projects", "List projects"),
    ("c", "command", "Enter command"),
    ("r", "refresh", "Refresh display"),
    ("q", "quit", "Quit application"),
)

# =============================================================================
# REFRESH INTERVALS (milliseconds)
# [He2025]: Fixed intervals, no adaptive timing
# =============================================================================

WEBSOCKET_RECONNECT_INTERVAL_MS: Final[int] = 5000
STATE_POLL_INTERVAL_MS: Final[int] = 1000
ALERT_FADE_INTERVAL_MS: Final[int] = 30000

# =============================================================================
# DETERMINISM VERIFICATION
# =============================================================================

def verify_constants_integrity() -> bool:
    """
    Verify all constant mappings are complete and consistent.

    [He2025] Compliance: This function verifies that all mappings
    are properly defined for all enum values, preventing runtime
    KeyError exceptions that could cause nondeterministic behavior.

    Returns:
        True if all mappings are consistent, raises AssertionError otherwise.
    """
    # Verify burnout mappings
    for level in BURNOUT_LEVELS:
        assert level in BURNOUT_COLORS, f"Missing BURNOUT_COLORS[{level}]"
        assert level in BURNOUT_ICONS, f"Missing BURNOUT_ICONS[{level}]"
        assert level in BURNOUT_SEGMENTS, f"Missing BURNOUT_SEGMENTS[{level}]"
        assert level in BURNOUT_STATUS_TEXT, f"Missing BURNOUT_STATUS_TEXT[{level}]"

    # Verify energy mappings
    for level in ENERGY_LEVELS:
        assert level in ENERGY_COLORS, f"Missing ENERGY_COLORS[{level}]"
        assert level in ENERGY_ICONS, f"Missing ENERGY_ICONS[{level}]"
        assert level in ENERGY_PERCENTAGES, f"Missing ENERGY_PERCENTAGES[{level}]"

    # Verify momentum mappings
    for phase in MOMENTUM_PHASES:
        assert phase in MOMENTUM_COLORS, f"Missing MOMENTUM_COLORS[{phase}]"
        assert phase in MOMENTUM_ICONS, f"Missing MOMENTUM_ICONS[{phase}]"
        assert phase in MOMENTUM_DESCRIPTIONS, f"Missing MOMENTUM_DESCRIPTIONS[{phase}]"

    # Verify mode mappings
    for mode in MODES:
        assert mode in MODE_COLORS, f"Missing MODE_COLORS[{mode}]"
        assert mode in MODE_ICONS, f"Missing MODE_ICONS[{mode}]"

    # Verify altitude mappings
    for alt in ALTITUDES:
        assert alt in ALTITUDE_DESCRIPTIONS, f"Missing ALTITUDE_DESCRIPTIONS[{alt}]"
        assert alt in ALTITUDE_COLORS, f"Missing ALTITUDE_COLORS[{alt}]"

    # Verify project status mappings
    for status in PROJECT_STATUSES:
        assert status in PROJECT_STATUS_COLORS, f"Missing PROJECT_STATUS_COLORS[{status}]"
        assert status in PROJECT_STATUS_ICONS, f"Missing PROJECT_STATUS_ICONS[{status}]"

    # Verify alert mappings
    for severity in ALERT_SEVERITIES:
        assert severity in ALERT_COLORS, f"Missing ALERT_COLORS[{severity}]"
        assert severity in ALERT_ICONS, f"Missing ALERT_ICONS[{severity}]"

    return True


# Run verification at module load time
# [He2025]: Fail fast if constants are misconfigured
assert verify_constants_integrity(), "Constants integrity check failed"
