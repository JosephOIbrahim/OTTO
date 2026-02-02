"""
Status Renderer - Mobile-Compatible Output
==========================================

Platform-agnostic status rendering using OutputFormatter abstraction.
Separates data logic from terminal-specific display code.

[He2025] Compliance:
- Fixed rendering order
- Deterministic output for same state
- No runtime variation

Usage:
    from otto.cli.status_renderer import StatusRenderer
    from otto.output import get_formatter

    renderer = StatusRenderer()
    state = renderer.read_state()
    output = renderer.render(state)  # Uses global formatter
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from otto.output import (
    OutputFormatter,
    OutputFormat,
    get_formatter,
    StatusData,
)


# State mappings (data-only, no terminal codes)
MODE_SYMBOLS = {
    "work": "->",
    "delegate": "=>",
    "protect": "<>"
}

MOMENTUM_BARS = {
    "cold_start": "_",
    "building": "=",
    "rolling": "#",
    "peak": "*",
    "crashed": "!"
}

ALTITUDE_SHORT = {
    "30000ft": "30K",
    "15000ft": "15K",
    "5000ft": "5K",
    "Ground": "GND"
}


@dataclass
class StatusRenderConfig:
    """Configuration for status rendering.

    Attributes:
        state_file: Path to cognitive state file
        include_goal: Whether to include session goal
        include_paradigm: Whether to include paradigm
        include_memory: Whether to include working memory
        include_tangent: Whether to include tangent budget
    """
    state_file: Optional[Path] = None
    include_goal: bool = True
    include_paradigm: bool = True
    include_memory: bool = True
    include_tangent: bool = True

    def __post_init__(self):
        if self.state_file is None:
            self.state_file = Path.home() / ".orchestra" / "state" / "cognitive_state.json"


class StatusRenderer:
    """
    Platform-agnostic status renderer.

    Uses OutputFormatter abstraction for rendering, separating
    data logic from terminal-specific display code.

    [He2025] Compliance:
    - Fixed data extraction order
    - Deterministic state conversion
    - No runtime variation in rendering
    """

    def __init__(
        self,
        formatter: Optional[OutputFormatter] = None,
        config: Optional[StatusRenderConfig] = None,
    ):
        """
        Initialize renderer.

        Args:
            formatter: OutputFormatter to use (defaults to global)
            config: Rendering configuration
        """
        self._formatter = formatter
        self._config = config or StatusRenderConfig()

    @property
    def formatter(self) -> OutputFormatter:
        """Get the active formatter."""
        return self._formatter or get_formatter()

    @property
    def config(self) -> StatusRenderConfig:
        """Get the render configuration."""
        return self._config

    def read_state(self) -> Dict[str, Any]:
        """
        Read cognitive state from file.

        Returns default state if file doesn't exist or is invalid.

        [He2025]: Fixed default values, deterministic fallback.
        """
        default = {
            "burnout_level": "GREEN",
            "decision_mode": "work",
            "momentum_phase": "rolling",
            "energy_level": "high",
            "working_memory_used": 2,
            "tangent_budget": 5,
            "altitude": "30000ft",
            "paradigm": "Cortex",
            "goal": None,
            "exchange_count": 0,
        }

        state_file = self._config.state_file
        if not state_file.exists():
            return default

        try:
            with open(state_file) as f:
                data = json.load(f)
                # Merge with defaults (preserves deterministic fallback)
                return {**default, **data}
        except Exception:
            return default

    def state_to_status_data(self, state: Dict[str, Any]) -> StatusData:
        """
        Convert raw state dict to StatusData.

        [He2025]: Fixed field extraction order.
        """
        return StatusData(
            burnout=state.get("burnout_level", "GREEN"),
            momentum=state.get("momentum_phase", "rolling"),
            energy=state.get("energy_level", "high"),
            altitude=state.get("altitude", "30000ft"),
            expert=state.get("decision_mode", "work"),
            goal=state.get("goal"),
            exchange_count=state.get("exchange_count", 0),
        )

    def render(
        self,
        state: Optional[Dict[str, Any]] = None,
        formatter: Optional[OutputFormatter] = None,
    ) -> str:
        """
        Render state using formatter.

        Args:
            state: State dict (reads from file if None)
            formatter: Override formatter for this render

        Returns:
            Formatted status string
        """
        if state is None:
            state = self.read_state()

        active_formatter = formatter or self.formatter
        status_data = self.state_to_status_data(state)

        return active_formatter.format_status(status_data)

    def render_state(
        self,
        state: Optional[Dict[str, Any]] = None,
        formatter: Optional[OutputFormatter] = None,
    ) -> str:
        """
        Render full state dict.

        Args:
            state: State dict (reads from file if None)
            formatter: Override formatter for this render

        Returns:
            Formatted state string
        """
        if state is None:
            state = self.read_state()

        active_formatter = formatter or self.formatter
        return active_formatter.format_state(state)

    def render_short(self, state: Optional[Dict[str, Any]] = None) -> str:
        """
        Render minimal status.

        Returns burnout indicator only.
        """
        if state is None:
            state = self.read_state()

        burnout = state.get("burnout_level", "GREEN")
        return f"[{burnout[0]}]"  # G/Y/O/R

    def render_prompt(self, state: Optional[Dict[str, Any]] = None) -> str:
        """
        Render prompt-friendly format.

        Returns: burnout | mode | momentum
        """
        if state is None:
            state = self.read_state()

        burnout = state.get("burnout_level", "GREEN")
        mode = state.get("decision_mode", "work")
        momentum = state.get("momentum_phase", "rolling")
        momentum_bar = MOMENTUM_BARS.get(momentum, "#")

        return f"[{burnout}] {mode.upper()} {momentum_bar}"

    def render_full(self, state: Optional[Dict[str, Any]] = None) -> str:
        """
        Render full status line (no colors).

        Returns: burnout | mode | momentum | altitude | memory | tangent | paradigm
        """
        if state is None:
            state = self.read_state()

        burnout = state.get("burnout_level", "GREEN")
        mode = state.get("decision_mode", "work")
        momentum = state.get("momentum_phase", "rolling")
        altitude = state.get("altitude", "30000ft")
        wm = state.get("working_memory_used", 2)
        tangent = state.get("tangent_budget", 5)
        paradigm = state.get("paradigm", "Cortex")

        momentum_bar = MOMENTUM_BARS.get(momentum, "#")
        alt_short = ALTITUDE_SHORT.get(altitude, "30K")

        parts = [f"[{burnout}]", mode.upper(), f"{momentum_bar} {momentum.upper()}"]

        if self._config.include_memory:
            parts.append(f"{alt_short}")
            parts.append(f"{wm}/3")

        if self._config.include_tangent:
            parts.append(f"T:{tangent}")

        if self._config.include_paradigm:
            parts.append(paradigm.upper())

        return " | ".join(parts)

    def render_json(self, state: Optional[Dict[str, Any]] = None) -> str:
        """
        Render state as JSON.

        [He2025]: Deterministic key ordering via sort_keys.
        """
        if state is None:
            state = self.read_state()

        return json.dumps(state, indent=2, sort_keys=True)

    def to_dict(self, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get state as dict (for API responses).

        [He2025]: Returns copy to prevent mutation.
        """
        if state is None:
            state = self.read_state()

        return dict(state)


# =============================================================================
# Global Instance
# =============================================================================

_renderer: Optional[StatusRenderer] = None


def get_status_renderer() -> StatusRenderer:
    """Get the global status renderer instance."""
    global _renderer
    if _renderer is None:
        _renderer = StatusRenderer()
    return _renderer


def set_status_renderer(renderer: StatusRenderer) -> None:
    """Set the global status renderer instance."""
    global _renderer
    _renderer = renderer


def reset_status_renderer() -> None:
    """Reset global renderer (for testing)."""
    global _renderer
    _renderer = None


# =============================================================================
# Convenience Functions
# =============================================================================

def render_status(state: Optional[Dict[str, Any]] = None) -> str:
    """Render status using global renderer and formatter."""
    return get_status_renderer().render(state)


def render_status_json(state: Optional[Dict[str, Any]] = None) -> str:
    """Render status as JSON using global renderer."""
    return get_status_renderer().render_json(state)


def read_cognitive_state() -> Dict[str, Any]:
    """Read cognitive state using global renderer."""
    return get_status_renderer().read_state()
