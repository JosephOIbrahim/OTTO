"""
Command Bar Widget
==================

Determinism widget displaying keyboard shortcuts and status.

Principles:
1. All shortcuts from FIXED constants
2. Render is pure function
3. No internal mutable state
4. Deterministic layout
"""

from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typing import Optional

from ..constants import KEYBOARD_SHORTCUTS


class CommandBarWidget:
    """
    Widget displaying keyboard shortcuts and connection status.

    Determinism:
    - Shortcuts from FIXED constant
    - No internal mutable state
    - Render is pure function
    """

    def __init__(
        self,
        connected: bool = False,
        error_message: str = "",
        current_input: str = "",
    ):
        """Initialize with status."""
        self._connected = connected
        self._error_message = error_message
        self._current_input = current_input

    def update(
        self,
        connected: bool = False,
        error_message: str = "",
        current_input: str = "",
    ) -> "CommandBarWidget":
        """
        Create new widget with updated status.

        Determinism: Returns new instance, doesn't mutate.
        """
        return CommandBarWidget(connected, error_message, current_input)

    def _render_shortcuts(self) -> Text:
        """
        Render keyboard shortcuts.

        Determinism:
        - FIXED shortcut list from constants
        - Deterministic formatting
        """
        text = Text()

        # Iterate in fixed order (tuple order is deterministic)
        for i, (key, command, description) in enumerate(KEYBOARD_SHORTCUTS):
            if i > 0:
                text.append("  ")

            text.append("[", style="dim")
            text.append(key, style="bold cyan")
            text.append("]", style="dim")
            text.append(description, style="")

        return text

    def _render_status_indicator(self) -> Text:
        """
        Render connection status indicator.

        Determinism: Pure function, fixed status mapping.
        """
        text = Text()

        if self._connected:
            text.append("● ", style="bold green")
            text.append("Connected", style="green")
        else:
            text.append("○ ", style="bold red")
            text.append("Disconnected", style="red")

        return text

    def _render_error(self) -> Optional[Text]:
        """
        Render error message if present.

        Determinism: Pure function.
        """
        if not self._error_message:
            return None

        text = Text()
        text.append("Error: ", style="bold red")
        text.append(self._error_message, style="red")
        return text

    def render(self) -> Panel:
        """
        Render the complete command bar widget.

        Determinism:
        - Pure function of state
        - Fixed layout structure
        """
        # Build content
        table = Table.grid(expand=True)
        table.add_column("Shortcuts", ratio=3)
        table.add_column("Status", justify="right", ratio=1)

        # Shortcuts row
        shortcuts = self._render_shortcuts()
        status = self._render_status_indicator()

        table.add_row(shortcuts, status)

        # Error row if present
        error = self._render_error()
        if error:
            table.add_row(error, Text())

        # Input row if command mode
        if self._current_input:
            input_text = Text()
            input_text.append("> ", style="bold cyan")
            input_text.append(self._current_input, style="")
            input_text.append("_", style="blink")
            table.add_row(input_text, Text())

        return Panel(
            table,
            border_style="dim",
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


def render_command_bar(
    connected: bool = False,
    error_message: str = "",
    current_input: str = "",
) -> Panel:
    """
    Functional interface for rendering command bar.

    Determinism: Pure function, no side effects.
    """
    widget = CommandBarWidget(connected, error_message, current_input)
    return widget.render()
