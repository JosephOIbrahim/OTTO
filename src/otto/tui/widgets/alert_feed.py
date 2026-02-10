"""
Alert Feed Widget
=================

Determinism widget displaying recent alerts.

Principles:
1. Render is a pure function of alerts tuple
2. All visual mappings from constants (FIXED)
3. Deterministic sorting by timestamp
4. Fixed maximum display count
"""

from rich.console import Console, ConsoleOptions, RenderResult
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typing import Tuple
from datetime import datetime
import time

from ..state import Alert
from ..constants import (
    ALERT_COLORS,
    ALERT_ICONS,
    ALERT_FEED_MAX_ITEMS,
)


class AlertFeedWidget:
    """
    Widget displaying recent alerts.

    Determinism:
    - No internal mutable state
    - Render is pure function of input
    - Deterministic sorting
    - Fixed max items
    """

    def __init__(
        self,
        alerts: Tuple[Alert, ...] = (),
        max_items: int = ALERT_FEED_MAX_ITEMS,
    ):
        """Initialize with alerts tuple."""
        self._alerts = alerts
        self._max_items = max_items

    def update(self, alerts: Tuple[Alert, ...]) -> "AlertFeedWidget":
        """
        Create new widget with updated alerts.

        Determinism: Returns new instance, doesn't mutate.
        """
        return AlertFeedWidget(alerts, self._max_items)

    def _format_timestamp(self, timestamp: float) -> str:
        """
        Format timestamp for display.

        Determinism: Deterministic formatting.
        Uses fixed format string, no locale-dependent formatting.
        """
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%H:%M")

    def _get_relative_time(self, timestamp: float) -> str:
        """
        Get relative time description.

        Determinism:
        - Fixed thresholds for relative time
        - Deterministic based on delta
        """
        now = time.time()
        delta = now - timestamp

        # Fixed thresholds
        if delta < 60:
            return "just now"
        elif delta < 3600:
            minutes = int(delta / 60)
            return f"{minutes}m ago"
        elif delta < 86400:
            hours = int(delta / 3600)
            return f"{hours}h ago"
        else:
            days = int(delta / 86400)
            return f"{days}d ago"

    def _render_alert_icon(self, severity: str) -> Text:
        """
        Render alert severity icon.

        Determinism: Pure function, FIXED mappings.
        """
        icon = ALERT_ICONS.get(severity, "○")
        color_name, _ = ALERT_COLORS.get(severity, ("white", "#ffffff"))

        text = Text()
        text.append(icon, style=color_name)
        return text

    def _render_alert_row(self, alert: Alert) -> Text:
        """
        Render a single alert row.

        Determinism:
        - Pure function of Alert
        - Fixed format structure
        """
        color_name, _ = ALERT_COLORS.get(alert.severity, ("white", "#ffffff"))

        text = Text()

        # Time
        text.append(self._format_timestamp(alert.timestamp), style="dim")
        text.append(" ")

        # Icon
        text.append_text(self._render_alert_icon(alert.severity))
        text.append(" ")

        # Title
        text.append(alert.title, style=f"bold {color_name}")

        # Message (truncated)
        if alert.message:
            text.append(": ", style="dim")
            message = alert.message
            if len(message) > 50:
                message = message[:47] + "..."
            text.append(message, style="")

        return text

    def render(self) -> Panel:
        """
        Render the complete alert feed widget.

        Determinism:
        - Pure function of self._alerts
        - Deterministic sorting
        - Fixed layout structure
        """
        if not self._alerts:
            content = Text("No recent alerts", style="dim italic")
            return Panel(
                content,
                title="[bold blue]Recent Alerts[/bold blue]",
                border_style="blue",
            )

        # Sort alerts deterministically
        # Sort by timestamp descending, then by id for stability
        sorted_alerts = sorted(
            self._alerts,
            key=lambda a: (-a.timestamp, a.id)
        )[:self._max_items]

        # Build content
        lines = []
        for alert in sorted_alerts:
            lines.append(self._render_alert_row(alert))

        # Join with newlines
        content = Text()
        for i, line in enumerate(lines):
            if i > 0:
                content.append("\n")
            content.append_text(line)

        return Panel(
            content,
            title="[bold blue]Recent Alerts[/bold blue]",
            border_style="blue",
        )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Rich console protocol for direct rendering."""
        yield self.render()


def render_alert_feed(alerts: Tuple[Alert, ...]) -> Panel:
    """
    Functional interface for rendering alert feed.

    Determinism: Pure function, no side effects.
    """
    widget = AlertFeedWidget(alerts)
    return widget.render()
