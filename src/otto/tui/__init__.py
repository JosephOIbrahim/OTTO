"""
OTTO TUI Dashboard
==================

Terminal User Interface for OTTO OS cognitive state monitoring.

Determinism:
- All visual mappings from fixed constants
- Immutable state management
- Deterministic rendering pipeline
- Fixed widget layout order

Usage:
    from otto.tui import run_dashboard
    asyncio.run(run_dashboard())

    # Or from CLI
    python -m otto.tui

Components:
    - OTTODashboard: Main application
    - StateStore: Immutable state management
    - CognitiveStateWidget: Cognitive state display
    - ProjectCardWidget: Active project display
    - AlertFeedWidget: Recent alerts display
    - CommandBarWidget: Keyboard shortcuts display
    - TUIWebSocketClient: Real-time updates
"""

from .constants import (
    TUI_VERSION,
    HE2025_PRINCIPLES_APPLIED,
    BURNOUT_LEVELS,
    BURNOUT_COLORS,
    ENERGY_LEVELS,
    MOMENTUM_PHASES,
    MODES,
    ALTITUDES,
    PROJECT_STATUSES,
    ALERT_SEVERITIES,
    KEYBOARD_SHORTCUTS,
    verify_constants_integrity,
)

from .state import (
    CognitiveState,
    Project,
    Alert,
    TUIState,
    StateStore,
    get_store,
    reset_store,
    update_cognitive_state,
    update_projects,
    add_alert,
    set_connection_state,
    apply_state_update,
)

from .widgets import (
    CognitiveStateWidget,
    ProjectCardWidget,
    AlertFeedWidget,
    CommandBarWidget,
)

from .app import (
    OTTODashboard,
    create_dashboard,
    run_dashboard,
    main,
)

from .websocket_client import (
    TUIWebSocketClient,
    ConnectionState,
    get_websocket_client,
    reset_websocket_client,
)

__all__ = [
    # Version
    "TUI_VERSION",
    "HE2025_PRINCIPLES_APPLIED",
    # Constants
    "BURNOUT_LEVELS",
    "BURNOUT_COLORS",
    "ENERGY_LEVELS",
    "MOMENTUM_PHASES",
    "MODES",
    "ALTITUDES",
    "PROJECT_STATUSES",
    "ALERT_SEVERITIES",
    "KEYBOARD_SHORTCUTS",
    "verify_constants_integrity",
    # State
    "CognitiveState",
    "Project",
    "Alert",
    "TUIState",
    "StateStore",
    "get_store",
    "reset_store",
    "update_cognitive_state",
    "update_projects",
    "add_alert",
    "set_connection_state",
    "apply_state_update",
    # Widgets
    "CognitiveStateWidget",
    "ProjectCardWidget",
    "AlertFeedWidget",
    "CommandBarWidget",
    # App
    "OTTODashboard",
    "create_dashboard",
    "run_dashboard",
    "main",
    # WebSocket
    "TUIWebSocketClient",
    "ConnectionState",
    "get_websocket_client",
    "reset_websocket_client",
]

__version__ = TUI_VERSION
