"""
Cognitive State Widget
======================

Determinism widget displaying cognitive state.

Principles:
1. Render is a pure function of CognitiveState
2. All visual mappings from constants (FIXED)
3. No internal mutable state
4. Deterministic layout calculation
"""

from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.style import Style
from typing import Optional

from ..state import CognitiveState
from ..constants import (
    BURNOUT_COLORS,
    BURNOUT_ICONS,
    BURNOUT_SEGMENTS,
    BURNOUT_STATUS_TEXT,
    ENERGY_COLORS,
    ENERGY_ICONS,
    ENERGY_PERCENTAGES,
    MOMENTUM_COLORS,
    MOMENTUM_ICONS,
    MOMENTUM_DESCRIPTIONS,
    MODE_COLORS,
    MODE_ICONS,
    ALTITUDE_COLORS,
    ALTITUDE_DESCRIPTIONS,
)


class CognitiveStateWidget:
    """
    Widget displaying current cognitive state.

    Determinism:
    - No internal mutable state
    - Render is pure function of input
    - All mappings from FIXED constants
    """

    def __init__(self, state: Optional[CognitiveState] = None):
        """Initialize with optional state."""
        self._state = state or CognitiveState()

    def update(self, state: CognitiveState) -> "CognitiveStateWidget":
        """
        Create new widget with updated state.

        Determinism: Returns new instance, doesn't mutate.
        """
        return CognitiveStateWidget(state)

    def _render_burnout_bar(self, level: str, width: int = 10) -> Text:
        """
        Render burnout progress bar.

        Determinism: Pure function, FIXED mappings.
        """
        segments = BURNOUT_SEGMENTS.get(level, 0)
        color_name, _ = BURNOUT_COLORS.get(level, ("white", "#ffffff"))

        filled = "█" * segments
        empty = "░" * (width - segments)

        text = Text()
        text.append(filled, style=color_name)
        text.append(empty, style="dim")
        return text

    def _render_energy_bar(self, level: str) -> Text:
        """
        Render energy bar.

        Determinism: Pure function, FIXED mappings.
        """
        icon = ENERGY_ICONS.get(level, "████████")
        color_name, _ = ENERGY_COLORS.get(level, ("white", "#ffffff"))
        percentage = ENERGY_PERCENTAGES.get(level, 100)

        text = Text()
        text.append(icon, style=color_name)
        text.append(f" {percentage}%", style="dim")
        return text

    def _render_mode(self, mode: str) -> Text:
        """
        Render mode indicator.

        Determinism: Pure function, FIXED mappings.
        """
        icon = MODE_ICONS.get(mode, "○")
        color_name, _ = MODE_COLORS.get(mode, ("white", "#ffffff"))

        text = Text()
        text.append(icon, style=color_name)
        text.append(f" {mode.upper()}", style=f"bold {color_name}")
        return text

    def _render_momentum(self, phase: str) -> Text:
        """
        Render momentum indicator.

        Determinism: Pure function, FIXED mappings.
        """
        icon = MOMENTUM_ICONS.get(phase, "○")
        color_name, _ = MOMENTUM_COLORS.get(phase, ("white", "#ffffff"))
        description = MOMENTUM_DESCRIPTIONS.get(phase, "")

        text = Text()
        text.append(icon, style=color_name)
        text.append(f" {phase}", style=color_name)
        text.append(f" ({description})", style="dim")
        return text

    def _render_altitude(self, altitude: str) -> Text:
        """
        Render altitude indicator.

        Determinism: Pure function, FIXED mappings.
        """
        color_name, _ = ALTITUDE_COLORS.get(altitude, ("white", "#ffffff"))
        description = ALTITUDE_DESCRIPTIONS.get(altitude, "")

        text = Text()
        text.append(altitude, style=f"bold {color_name}")
        text.append(f" - {description}", style="dim")
        return text

    def _render_burnout_with_label(self, level: str) -> Text:
        """
        Render burnout with label and status.

        Determinism: Pure function, FIXED mappings.
        """
        icon = BURNOUT_ICONS.get(level, "●")
        color_name, _ = BURNOUT_COLORS.get(level, ("white", "#ffffff"))
        status_text = BURNOUT_STATUS_TEXT.get(level, "Unknown")

        text = Text()
        text.append(icon, style=color_name)
        text.append(f" {level}", style=f"bold {color_name}")
        text.append(f" ({status_text})", style="dim")
        return text

    def render(self) -> Panel:
        """
        Render the complete cognitive state widget.

        Determinism:
        - Pure function of self._state
        - Fixed layout structure
        - All mappings from constants
        """
        state = self._state

        # Create table with FIXED structure
        table = Table.grid(padding=(0, 2))
        table.add_column("Label", style="bold", width=12)
        table.add_column("Value")
        table.add_column("Label2", style="bold", width=12)
        table.add_column("Value2")

        # Row 1: Mode and Energy
        table.add_row(
            "Mode:",
            self._render_mode(state.active_mode),
            "Energy:",
            self._render_energy_bar(state.energy_level),
        )

        # Row 2: Burnout bar
        burnout_bar = Text()
        burnout_bar.append("Burnout: [")
        burnout_bar.append_text(self._render_burnout_bar(state.burnout_level))
        burnout_bar.append("] ")
        burnout_bar.append_text(self._render_burnout_with_label(state.burnout_level))

        table.add_row(
            "",
            burnout_bar,
            "",
            "",
        )

        # Row 3: Momentum and Altitude
        table.add_row(
            "Momentum:",
            self._render_momentum(state.momentum_phase),
            "Altitude:",
            self._render_altitude(state.current_altitude),
        )

        # Row 4: Session info
        session_text = Text()
        duration = state.session_duration_minutes
        if duration > 0:
            hours = duration // 60
            mins = duration % 60
            if hours > 0:
                session_text.append(f"{hours}h {mins}m", style="cyan")
            else:
                session_text.append(f"{mins} min", style="cyan")
        else:
            session_text.append("Just started", style="dim")

        exchanges_text = Text()
        exchanges_text.append(str(state.exchange_count), style="cyan")
        exchanges_text.append(" exchanges", style="dim")

        table.add_row(
            "Session:",
            session_text,
            "Exchanges:",
            exchanges_text,
        )

        return Panel(
            table,
            title="[bold cyan]Cognitive State[/bold cyan]",
            border_style="cyan",
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


def render_cognitive_state(state: CognitiveState) -> Panel:
    """
    Functional interface for rendering cognitive state.

    Determinism: Pure function, no side effects.
    """
    widget = CognitiveStateWidget(state)
    return widget.render()
