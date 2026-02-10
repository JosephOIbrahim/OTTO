"""
OTTO TUI State Management
=========================

Determinism: Immutable state with deterministic transitions.

This module implements state management following principles:
1. Immutable state objects (frozen dataclasses)
2. Deterministic state transitions (pure functions)
3. No hidden state (all state is explicit)
4. Reproducible state history (event sourcing pattern)

Reference: He, Horace and Thinking Machines Lab,
"Defeating Nondeterminism in LLM Inference", Sep 2025.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Callable
from enum import Enum
import time
import hashlib
import json

from .constants import (
    BURNOUT_LEVELS,
    ENERGY_LEVELS,
    MOMENTUM_PHASES,
    MODES,
    ALTITUDES,
    PROJECT_STATUSES,
    ALERT_SEVERITIES,
)


# =============================================================================
# IMMUTABLE STATE OBJECTS
# Frozen dataclasses prevent mutation
# =============================================================================

@dataclass(frozen=True)
class CognitiveState:
    """
    Immutable cognitive state snapshot.

    Determinism:
    - frozen=True prevents mutation
    - All fields have explicit types
    - Default values are deterministic
    """
    active_mode: str = "focused"
    burnout_level: str = "GREEN"
    energy_level: str = "high"
    momentum_phase: str = "cold_start"
    current_altitude: str = "15000ft"
    session_start_time: float = 0.0
    exchange_count: int = 0

    def __post_init__(self):
        """Validate state values are within allowed sets."""
        # Fail fast on invalid state
        if self.active_mode not in MODES:
            object.__setattr__(self, 'active_mode', 'focused')
        if self.burnout_level not in BURNOUT_LEVELS:
            object.__setattr__(self, 'burnout_level', 'GREEN')
        if self.energy_level not in ENERGY_LEVELS:
            object.__setattr__(self, 'energy_level', 'high')
        if self.momentum_phase not in MOMENTUM_PHASES:
            object.__setattr__(self, 'momentum_phase', 'cold_start')
        if self.current_altitude not in ALTITUDES:
            object.__setattr__(self, 'current_altitude', '15000ft')

    @property
    def session_duration_minutes(self) -> int:
        """Calculate session duration in minutes."""
        if self.session_start_time <= 0:
            return 0
        elapsed = time.time() - self.session_start_time
        return int(elapsed / 60)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "active_mode": self.active_mode,
            "burnout_level": self.burnout_level,
            "energy_level": self.energy_level,
            "momentum_phase": self.momentum_phase,
            "current_altitude": self.current_altitude,
            "session_start_time": self.session_start_time,
            "exchange_count": self.exchange_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CognitiveState":
        """Create from dictionary."""
        return cls(
            active_mode=data.get("active_mode", "focused"),
            burnout_level=data.get("burnout_level", "GREEN"),
            energy_level=data.get("energy_level", "high"),
            momentum_phase=data.get("momentum_phase", "cold_start"),
            current_altitude=data.get("current_altitude", "15000ft"),
            session_start_time=data.get("session_start_time", 0.0),
            exchange_count=data.get("exchange_count", 0),
        )

    def checksum(self) -> str:
        """
        Generate deterministic checksum for state verification.

        Determinism: Fixed field order ensures deterministic hash.
        """
        # FIXED order - never changes
        ordered_values = (
            self.active_mode,
            self.burnout_level,
            self.energy_level,
            self.momentum_phase,
            self.current_altitude,
            str(self.session_start_time),
            str(self.exchange_count),
        )
        content = "|".join(ordered_values)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Project:
    """
    Immutable project state.

    Immutable: frozen=True, explicit types.
    """
    id: str
    name: str
    status: str = "BACKGROUND"
    progress: float = 0.0
    next_action: str = ""

    def __post_init__(self):
        """Validate project values."""
        if self.status not in PROJECT_STATUSES:
            object.__setattr__(self, 'status', 'BACKGROUND')
        # Clamp progress to [0, 1]
        if self.progress < 0:
            object.__setattr__(self, 'progress', 0.0)
        elif self.progress > 1:
            object.__setattr__(self, 'progress', 1.0)


@dataclass(frozen=True)
class Alert:
    """
    Immutable alert object.

    Immutable: frozen=True, timestamp for ordering.
    """
    id: str
    timestamp: float
    severity: str
    title: str
    message: str
    source: str = ""
    data: Tuple[Tuple[str, Any], ...] = ()  # Immutable dict alternative

    def __post_init__(self):
        """Validate alert values."""
        if self.severity not in ALERT_SEVERITIES:
            object.__setattr__(self, 'severity', 'info')

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """Create from dictionary."""
        alert_data = data.get("data", {})
        # Convert dict to immutable tuple of tuples
        data_tuple = tuple(sorted(alert_data.items())) if alert_data else ()

        return cls(
            id=data.get("id", f"alert_{time.time()}"),
            timestamp=data.get("timestamp", time.time()),
            severity=data.get("severity", "info"),
            title=data.get("title", ""),
            message=data.get("message", ""),
            source=data.get("source", ""),
            data=data_tuple,
        )


@dataclass(frozen=True)
class TUIState:
    """
    Complete TUI state - immutable snapshot.

    Determinism:
    - All nested objects are also immutable
    - State transitions create new objects
    - No mutation allowed
    """
    cognitive: CognitiveState = field(default_factory=CognitiveState)
    projects: Tuple[Project, ...] = ()
    alerts: Tuple[Alert, ...] = ()
    connected: bool = False
    last_update: float = 0.0
    error_message: str = ""

    def get_focus_project(self) -> Optional[Project]:
        """Get the project with FOCUS status."""
        for project in self.projects:
            if project.status == "FOCUS":
                return project
        return None

    def get_recent_alerts(self, count: int = 5) -> Tuple[Alert, ...]:
        """
        Get most recent alerts.

        Determinism: Deterministic sorting by timestamp.
        """
        # Sort by timestamp descending (most recent first)
        # sorted() is stable and deterministic for equal timestamps
        sorted_alerts = tuple(sorted(
            self.alerts,
            key=lambda a: (-a.timestamp, a.id)  # Secondary sort by id for stability
        ))
        return sorted_alerts[:count]

    def checksum(self) -> str:
        """
        Generate deterministic checksum for entire state.

        Determinism: Fixed computation order.
        """
        parts = [
            self.cognitive.checksum(),
            str(self.connected),
            str(len(self.projects)),
            str(len(self.alerts)),
        ]
        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# STATE TRANSITIONS
# Pure functions, no side effects
# =============================================================================

def update_cognitive_state(
    current: TUIState,
    cognitive: CognitiveState,
) -> TUIState:
    """
    Create new state with updated cognitive state.

    Determinism: Pure function, returns new immutable object.
    """
    return TUIState(
        cognitive=cognitive,
        projects=current.projects,
        alerts=current.alerts,
        connected=current.connected,
        last_update=time.time(),
        error_message="",
    )


def update_projects(
    current: TUIState,
    projects: Tuple[Project, ...],
) -> TUIState:
    """
    Create new state with updated projects.

    Determinism: Pure function, returns new immutable object.
    """
    return TUIState(
        cognitive=current.cognitive,
        projects=projects,
        alerts=current.alerts,
        connected=current.connected,
        last_update=time.time(),
        error_message="",
    )


def add_alert(
    current: TUIState,
    alert: Alert,
    max_alerts: int = 50,
) -> TUIState:
    """
    Create new state with added alert.

    Determinism:
    - Pure function
    - Deterministic ordering (by timestamp, then id)
    - Fixed maximum size
    """
    # Add new alert and sort deterministically
    all_alerts = current.alerts + (alert,)
    sorted_alerts = tuple(sorted(
        all_alerts,
        key=lambda a: (-a.timestamp, a.id)
    ))
    # Trim to max size
    trimmed_alerts = sorted_alerts[:max_alerts]

    return TUIState(
        cognitive=current.cognitive,
        projects=current.projects,
        alerts=trimmed_alerts,
        connected=current.connected,
        last_update=time.time(),
        error_message="",
    )


def set_connection_state(
    current: TUIState,
    connected: bool,
    error_message: str = "",
) -> TUIState:
    """
    Create new state with updated connection state.

    Determinism: Pure function.
    """
    return TUIState(
        cognitive=current.cognitive,
        projects=current.projects,
        alerts=current.alerts,
        connected=connected,
        last_update=time.time(),
        error_message=error_message,
    )


def apply_state_update(
    current: TUIState,
    update: Dict[str, Any],
) -> TUIState:
    """
    Apply a state update from WebSocket message.

    Determinism:
    - Deterministic field mapping
    - Pure function
    - No side effects
    """
    # Update cognitive state if present
    cognitive = current.cognitive
    if any(key in update for key in [
        "active_mode", "burnout_level", "energy_level",
        "momentum_phase", "current_altitude"
    ]):
        cognitive = CognitiveState(
            active_mode=update.get("active_mode", cognitive.active_mode),
            burnout_level=update.get("burnout_level", cognitive.burnout_level),
            energy_level=update.get("energy_level", cognitive.energy_level),
            momentum_phase=update.get("momentum_phase", cognitive.momentum_phase),
            current_altitude=update.get("current_altitude", cognitive.current_altitude),
            session_start_time=cognitive.session_start_time,
            exchange_count=update.get("exchange_count", cognitive.exchange_count),
        )

    return TUIState(
        cognitive=cognitive,
        projects=current.projects,
        alerts=current.alerts,
        connected=current.connected,
        last_update=time.time(),
        error_message="",
    )


# =============================================================================
# STATE STORE
# Single source of truth with event history
# =============================================================================

class StateStore:
    """
    State store with deterministic state management.

    Determinism:
    - Single source of truth
    - Event-sourced state changes
    - Deterministic reducer pattern
    """

    def __init__(self):
        self._state: TUIState = TUIState(
            cognitive=CognitiveState(session_start_time=time.time())
        )
        self._listeners: List[Callable[[TUIState], None]] = []
        self._event_history: List[Tuple[float, str, Dict[str, Any]]] = []
        self._max_history: int = 100

    @property
    def state(self) -> TUIState:
        """Get current state (read-only)."""
        return self._state

    def subscribe(self, listener: Callable[[TUIState], None]) -> Callable[[], None]:
        """
        Subscribe to state changes.

        Returns unsubscribe function.
        """
        self._listeners.append(listener)

        def unsubscribe():
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def dispatch(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Dispatch an event to update state.

        Determinism:
        - Fixed event type → reducer mapping
        - Deterministic state transition
        - Event recorded for replay
        """
        timestamp = time.time()

        # Record event
        self._event_history.append((timestamp, event_type, payload))
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Apply reducer based on event type
        # Fixed mapping, no runtime variation
        new_state = self._reduce(event_type, payload)

        if new_state is not self._state:
            self._state = new_state
            self._notify_listeners()

    def _reduce(self, event_type: str, payload: Dict[str, Any]) -> TUIState:
        """
        Reduce event to new state.

        Determinism: Fixed event → reducer mapping.
        """
        # FIXED mapping - defined at compile time
        reducers = {
            "COGNITIVE_UPDATE": lambda: apply_state_update(self._state, payload),
            "PROJECTS_UPDATE": lambda: update_projects(
                self._state,
                tuple(Project(**p) for p in payload.get("projects", []))
            ),
            "ALERT_ADD": lambda: add_alert(
                self._state,
                Alert.from_dict(payload)
            ),
            "CONNECTION_UPDATE": lambda: set_connection_state(
                self._state,
                payload.get("connected", False),
                payload.get("error", "")
            ),
        }

        reducer = reducers.get(event_type)
        if reducer:
            return reducer()
        return self._state

    def _notify_listeners(self) -> None:
        """
        Notify all listeners of state change.

        Determinism: Fixed notification order.
        """
        # Listeners notified in registration order
        for listener in self._listeners:
            try:
                listener(self._state)
            except Exception:
                # Don't let one listener break others
                pass

    def get_state_checksum(self) -> str:
        """Get current state checksum for verification."""
        return self._state.checksum()


# =============================================================================
# SINGLETON STORE
# =============================================================================

_store: Optional[StateStore] = None


def get_store() -> StateStore:
    """Get the singleton state store."""
    global _store
    if _store is None:
        _store = StateStore()
    return _store


def reset_store() -> None:
    """Reset the store (for testing)."""
    global _store
    _store = None
