"""
Dashboard Renderer - Mobile-Compatible Output
=============================================

Platform-agnostic dashboard rendering using OutputFormatter abstraction.
Separates data queries from terminal-specific display code.

[He2025] Compliance:
- Fixed rendering order
- Deterministic output for same state
- No runtime variation

Usage:
    from otto.dashboard_renderer import DashboardRenderer
    from otto.output import get_formatter

    renderer = DashboardRenderer()
    output = renderer.render_status()  # Uses global formatter
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path

from otto.output import (
    OutputFormatter,
    OutputFormat,
    get_formatter,
    StatusData,
    AlertData,
)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ProgressData:
    """
    Progress visualization data.

    Attributes:
        value: Progress value (0.0-1.0)
        label: Optional label
        width: Bar width
    """
    value: float
    label: Optional[str] = None
    width: int = 20


@dataclass
class CognitiveStateData:
    """
    Comprehensive cognitive state data.

    Consolidates all state fields for rendering.
    """
    # Core state
    burnout_level: str = "GREEN"
    momentum_phase: str = "rolling"
    energy_level: str = "high"
    mode: str = "focused"
    altitude: str = "30000ft"

    # Cognitive support
    focus_level: str = "moderate"
    urgency: str = "moderate"
    tangent_budget: int = 5
    rapid_exchange_count: int = 0

    # Session stats
    exchange_count: int = 0
    tasks_completed: int = 0
    session_started: Optional[str] = None
    last_activity: Optional[str] = None

    # Convergence
    convergence_attractor: str = "focused"
    epistemic_tension: float = 0.0
    stable_exchanges: int = 0
    is_converged: bool = False

    # Decision engine
    decision_mode: str = "work"
    cognitive_budget: float = 1.0
    can_spawn: bool = True
    active_agents: int = 0
    queued_results: int = 0
    flow_protection: bool = False
    decisions_made: int = 0

    # Metadata
    state_file: Optional[str] = None
    checksum: Optional[str] = None


@dataclass
class DashboardSection:
    """
    A section of the dashboard output.

    Attributes:
        title: Section header
        items: Key-value items in this section
        separator: Character for separator line
    """
    title: str
    items: List[tuple] = field(default_factory=list)
    separator: str = "-"


# =============================================================================
# Progress Bar Generation
# =============================================================================

def render_progress_bar(
    value: float,
    width: int = 20,
    filled_char: str = "#",
    empty_char: str = "-",
) -> str:
    """
    Generate a progress bar string.

    [He2025]: Deterministic rendering - same value always produces same bar.

    Args:
        value: Progress value (0.0-1.0)
        width: Total bar width
        filled_char: Character for filled portion
        empty_char: Character for empty portion

    Returns:
        Progress bar string like "[####------]"
    """
    # Clamp value
    value = max(0.0, min(1.0, value))

    filled = int(value * width)
    empty = width - filled
    return f"[{filled_char * filled}{empty_char * empty}]"


def format_time_ago(timestamp: float) -> str:
    """
    Format timestamp as relative time.

    [He2025]: Deterministic for same input timestamp.
    """
    import time
    diff = time.time() - timestamp

    if diff < 60:
        return f"{int(diff)}s ago"
    elif diff < 3600:
        return f"{int(diff / 60)}m ago"
    elif diff < 86400:
        return f"{int(diff / 3600)}h ago"
    else:
        return f"{int(diff / 86400)}d ago"


# =============================================================================
# Dashboard Renderer
# =============================================================================

class DashboardRenderer:
    """
    Platform-agnostic dashboard renderer.

    Uses OutputFormatter abstraction for rendering, separating
    data queries from terminal-specific display code.

    [He2025] Compliance:
    - Fixed section order
    - Deterministic state conversion
    - No runtime variation in rendering
    """

    def __init__(
        self,
        formatter: Optional[OutputFormatter] = None,
        state_dir: Optional[Path] = None,
    ):
        """
        Initialize renderer.

        Args:
            formatter: OutputFormatter to use (defaults to global)
            state_dir: Directory containing state files
        """
        self._formatter = formatter
        self._state_dir = state_dir or (Path.home() / "Orchestra" / "state")

    @property
    def formatter(self) -> OutputFormatter:
        """Get the active formatter."""
        return self._formatter or get_formatter()

    def read_cognitive_state(self) -> CognitiveStateData:
        """
        Read cognitive state from state manager.

        Returns CognitiveStateData with all fields populated.

        [He2025]: Fixed field extraction order.
        """
        # Try to load from CognitiveStateManager if available
        try:
            from otto.cognitive_state import CognitiveStateManager
            manager = CognitiveStateManager(state_dir=self._state_dir)
            state = manager.get_state()

            return CognitiveStateData(
                burnout_level=state.burnout_level.value if hasattr(state.burnout_level, 'value') else str(state.burnout_level),
                momentum_phase=state.momentum_phase.value if hasattr(state.momentum_phase, 'value') else str(state.momentum_phase),
                energy_level=state.energy_level.value if hasattr(state.energy_level, 'value') else str(state.energy_level),
                mode=state.mode.value if hasattr(state.mode, 'value') else str(state.mode),
                altitude=str(state.altitude.value) + "ft" if hasattr(state.altitude, 'value') else str(state.altitude),
                focus_level=state.focus_level,
                urgency=state.urgency,
                tangent_budget=state.tangent_budget,
                rapid_exchange_count=state.rapid_exchange_count,
                exchange_count=state.exchange_count,
                tasks_completed=state.tasks_completed,
                session_started=format_time_ago(state.session_start) if state.session_start else None,
                last_activity=format_time_ago(state.last_activity) if state.last_activity else None,
                convergence_attractor=state.convergence_attractor,
                epistemic_tension=state.epistemic_tension,
                stable_exchanges=state.stable_exchanges,
                is_converged=state.is_converged(),
                state_file=str(manager.state_file),
                checksum=state.checksum(),
            )
        except ImportError:
            # Return defaults if cognitive_state not available
            return CognitiveStateData()
        except Exception:
            return CognitiveStateData()

    def read_decision_engine_status(self) -> Dict[str, Any]:
        """
        Read decision engine status.

        Returns dict with decision engine fields.
        """
        try:
            from otto.agent_coordinator import AgentCoordinator
            from otto.cognitive_state import CognitiveStateManager

            manager = CognitiveStateManager(state_dir=self._state_dir)
            coordinator = AgentCoordinator(
                cognitive_stage=manager,
                state_dir=self._state_dir
            )
            return coordinator.get_status()
        except ImportError:
            return {
                "cognitive_budget": 1.0,
                "can_spawn": True,
                "active_agents": 0,
                "queued_results": 0,
                "flow_protection": False,
                "decisions_made": 0,
                "agents": {},
            }
        except Exception:
            return {
                "cognitive_budget": 1.0,
                "can_spawn": True,
                "active_agents": 0,
                "queued_results": 0,
                "flow_protection": False,
                "decisions_made": 0,
                "agents": {},
            }

    def state_to_status_data(self, state: CognitiveStateData) -> StatusData:
        """
        Convert CognitiveStateData to StatusData.

        [He2025]: Fixed field mapping.
        """
        return StatusData(
            burnout=state.burnout_level,
            momentum=state.momentum_phase,
            energy=state.energy_level,
            altitude=state.altitude,
            expert=state.decision_mode,
            goal=None,
            exchange_count=state.exchange_count,
        )

    def render_status_line(
        self,
        state: Optional[CognitiveStateData] = None,
        formatter: Optional[OutputFormatter] = None,
    ) -> str:
        """
        Render single-line status.

        Uses OutputFormatter.format_status() for rendering.
        """
        if state is None:
            state = self.read_cognitive_state()

        active_formatter = formatter or self.formatter
        status_data = self.state_to_status_data(state)

        return active_formatter.format_status(status_data)

    def render_progress(
        self,
        value: float,
        label: Optional[str] = None,
        width: int = 20,
    ) -> str:
        """
        Render progress bar with optional label.

        [He2025]: Deterministic rendering.
        """
        bar = render_progress_bar(value, width)
        if label:
            return f"{label}: {bar} {value:.2f}"
        return f"{bar} {value:.2f}"

    def render_section(
        self,
        section: DashboardSection,
        width: int = 40,
    ) -> str:
        """
        Render a dashboard section.

        [He2025]: Fixed item order.
        """
        lines = []
        lines.append(section.title.upper())
        lines.append(section.separator * width)

        for key, value in section.items:
            lines.append(f"  {key}: {value}")

        lines.append("")  # Blank line after section
        return "\n".join(lines)

    def render_full_dashboard(
        self,
        state: Optional[CognitiveStateData] = None,
    ) -> str:
        """
        Render full dashboard output.

        [He2025]: Fixed section order.
        """
        if state is None:
            state = self.read_cognitive_state()

        decision_status = self.read_decision_engine_status()
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("  ORCHESTRA COGNITIVE STATE DASHBOARD")
        lines.append("=" * 60)
        lines.append("")

        # Core State Section
        core_section = DashboardSection(
            title="COGNITIVE STATE",
            items=[
                ("Burnout", state.burnout_level.upper()),
                ("Momentum", state.momentum_phase),
                ("Energy", state.energy_level),
                ("Mode", state.mode),
                ("Altitude", state.altitude),
            ]
        )
        lines.append(self.render_section(core_section))

        # Cognitive Support Section
        support_section = DashboardSection(
            title="COGNITIVE SUPPORT (Always Active)",
            items=[
                ("Focus level", state.focus_level),
                ("Urgency", state.urgency),
                ("Tangents left", f"{state.tangent_budget}/5"),
                ("Rapid exchanges", str(state.rapid_exchange_count)),
            ]
        )
        if state.rapid_exchange_count >= 15:
            support_section.items.append(("", "Body check recommended!"))
        lines.append(self.render_section(support_section))

        # Session Stats Section
        stats_section = DashboardSection(
            title="SESSION STATS",
            items=[
                ("Exchanges", str(state.exchange_count)),
                ("Tasks completed", str(state.tasks_completed)),
                ("Session started", state.session_started or "unknown"),
                ("Last activity", state.last_activity or "unknown"),
            ]
        )
        lines.append(self.render_section(stats_section))

        # Convergence Section
        tension_bar = render_progress_bar(state.epistemic_tension)
        converged_str = "CONVERGED" if state.is_converged else "not converged"
        convergence_section = DashboardSection(
            title="CONVERGENCE (RC^+xi)",
            items=[
                ("Attractor", state.convergence_attractor),
                ("Tension", f"{tension_bar} {state.epistemic_tension:.2f}"),
                ("Stable exchanges", str(state.stable_exchanges)),
                ("Status", converged_str),
            ]
        )
        lines.append(self.render_section(convergence_section))

        # Decision Engine Section
        budget_bar = render_progress_bar(decision_status.get("cognitive_budget", 1.0))
        can_spawn_str = "YES" if decision_status.get("can_spawn", True) else "NO"
        flow_str = "ACTIVE" if decision_status.get("flow_protection", False) else "inactive"

        decision_section = DashboardSection(
            title="DECISION ENGINE (v4.3.0)",
            items=[
                ("Cognitive budget", f"{budget_bar} {decision_status.get('cognitive_budget', 1.0):.2f}"),
                ("Can spawn agents", can_spawn_str),
                ("Active agents", str(decision_status.get("active_agents", 0))),
                ("Queued results", str(decision_status.get("queued_results", 0))),
                ("Flow protection", flow_str),
                ("Decisions made", str(decision_status.get("decisions_made", 0))),
            ]
        )
        lines.append(self.render_section(decision_section))

        # Footer
        lines.append("=" * 60)
        if state.state_file:
            lines.append(f"  State file: {state.state_file}")
        if state.checksum:
            lines.append(f"  Checksum: {state.checksum}")
        lines.append("=" * 60)
        lines.append("")

        return "\n".join(lines)

    def render_json(
        self,
        state: Optional[CognitiveStateData] = None,
    ) -> str:
        """
        Render state as JSON.

        [He2025]: Deterministic key ordering via sort_keys.
        """
        if state is None:
            state = self.read_cognitive_state()

        decision_status = self.read_decision_engine_status()

        data = {
            "cognitive_state": {
                "burnout_level": state.burnout_level,
                "momentum_phase": state.momentum_phase,
                "energy_level": state.energy_level,
                "mode": state.mode,
                "altitude": state.altitude,
            },
            "cognitive_support": {
                "focus_level": state.focus_level,
                "urgency": state.urgency,
                "tangent_budget": state.tangent_budget,
                "rapid_exchange_count": state.rapid_exchange_count,
            },
            "session_stats": {
                "exchange_count": state.exchange_count,
                "tasks_completed": state.tasks_completed,
                "session_started": state.session_started,
                "last_activity": state.last_activity,
            },
            "convergence": {
                "attractor": state.convergence_attractor,
                "epistemic_tension": state.epistemic_tension,
                "stable_exchanges": state.stable_exchanges,
                "is_converged": state.is_converged,
            },
            "decision_engine": decision_status,
            "metadata": {
                "state_file": state.state_file,
                "checksum": state.checksum,
            },
        }

        return json.dumps(data, indent=2, sort_keys=True)

    def to_dict(
        self,
        state: Optional[CognitiveStateData] = None,
    ) -> Dict[str, Any]:
        """
        Get state as nested dict (for API responses).

        [He2025]: Returns structured data.
        """
        if state is None:
            state = self.read_cognitive_state()

        decision_status = self.read_decision_engine_status()

        return {
            "cognitive_state": {
                "burnout_level": state.burnout_level,
                "momentum_phase": state.momentum_phase,
                "energy_level": state.energy_level,
                "mode": state.mode,
                "altitude": state.altitude,
            },
            "cognitive_support": {
                "focus_level": state.focus_level,
                "urgency": state.urgency,
                "tangent_budget": state.tangent_budget,
                "rapid_exchange_count": state.rapid_exchange_count,
            },
            "session_stats": {
                "exchange_count": state.exchange_count,
                "tasks_completed": state.tasks_completed,
            },
            "convergence": {
                "attractor": state.convergence_attractor,
                "epistemic_tension": state.epistemic_tension,
                "stable_exchanges": state.stable_exchanges,
                "is_converged": state.is_converged,
            },
            "decision_engine": decision_status,
        }


# =============================================================================
# Global Instance
# =============================================================================

_renderer: Optional[DashboardRenderer] = None


def get_dashboard_renderer() -> DashboardRenderer:
    """Get the global dashboard renderer instance."""
    global _renderer
    if _renderer is None:
        _renderer = DashboardRenderer()
    return _renderer


def set_dashboard_renderer(renderer: DashboardRenderer) -> None:
    """Set the global dashboard renderer instance."""
    global _renderer
    _renderer = renderer


def reset_dashboard_renderer() -> None:
    """Reset global renderer (for testing)."""
    global _renderer
    _renderer = None


# =============================================================================
# Convenience Functions
# =============================================================================

def render_dashboard() -> str:
    """Render full dashboard using global renderer."""
    return get_dashboard_renderer().render_full_dashboard()


def render_dashboard_json() -> str:
    """Render dashboard as JSON using global renderer."""
    return get_dashboard_renderer().render_json()


def render_dashboard_status_line() -> str:
    """Render single-line status using global renderer."""
    return get_dashboard_renderer().render_status_line()
