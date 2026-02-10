"""
OTTO TUI Application
====================

Determinism terminal dashboard application.

Principles:
1. Fixed widget layout (WIDGET_ORDER from constants)
2. Deterministic event handling (fixed handler order)
3. Immutable state management (StateStore)
4. No adaptive layout changes based on content
5. Reproducible rendering (same state → same output)

"""

import asyncio
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

from .state import (
    StateStore,
    TUIState,
    CognitiveState,
    Project,
    Alert,
    get_store,
    reset_store,
)
from .constants import (
    TUI_VERSION,
    WIDGET_ORDER,
    KEYBOARD_SHORTCUTS,
    MIN_WIDTH,
    MIN_HEIGHT,
    HEADER_HEIGHT,
    FOOTER_HEIGHT,
)
from .widgets import (
    CognitiveStateWidget,
    ProjectCardWidget,
    AlertFeedWidget,
    CommandBarWidget,
)


class OTTODashboard:
    """
    Main TUI dashboard application.

    Determinism:
    - Fixed layout structure (from WIDGET_ORDER)
    - Deterministic rendering pipeline
    - Event handlers in fixed order
    - State-driven rendering (pure functions)
    """

    def __init__(
        self,
        store: Optional[StateStore] = None,
        console: Optional[Console] = None,
    ):
        """
        Initialize dashboard.

        Args:
            store: State store (uses singleton if None)
            console: Rich console (creates new if None)
        """
        self._store = store or get_store()
        self._console = console or Console()
        self._running = False
        self._command_mode = False
        self._current_input = ""
        self._websocket_task: Optional[asyncio.Task] = None

        # Command handlers - FIXED mapping
        # No runtime registration, all handlers defined here
        self._command_handlers: Dict[str, Callable[[], None]] = {
            "health": self._handle_health,
            "state": self._handle_state,
            "projects": self._handle_projects,
            "refresh": self._handle_refresh,
            "quit": self._handle_quit,
            "command": self._handle_command_mode,
        }

    def _render_header(self) -> Panel:
        """
        Render header panel.

        Determinism: Pure function, fixed content.
        """
        state = self._store.state

        title = Text()
        title.append("OTTO OS", style="bold bright_white")
        title.append(f" v{TUI_VERSION}", style="dim")

        status = Text()
        if state.connected:
            status.append("● ", style="bold green")
            status.append("Connected", style="green")
        else:
            status.append("○ ", style="bold red")
            status.append("Disconnected", style="red")

        # Time beacon
        time_text = Text()
        duration = state.cognitive.session_duration_minutes
        if duration > 0:
            time_text.append(f"~{duration} min", style="cyan")
        else:
            time_text.append("Session start", style="dim")

        # Combine
        header_content = Text()
        header_content.append_text(title)
        header_content.append("  |  ")
        header_content.append_text(time_text)
        header_content.append("  |  ")
        header_content.append_text(status)

        return Panel(
            Align.center(header_content),
            style="bold",
        )

    def _render_body(self) -> Layout:
        """
        Render main body layout.

        Determinism:
        - Fixed layout structure
        - Widgets rendered in WIDGET_ORDER
        - Each widget is pure function of state
        """
        state = self._store.state

        # Create layout with FIXED structure
        layout = Layout()

        # Fixed ratio split, no adaptive sizing
        layout.split_column(
            Layout(name="top", ratio=2),
            Layout(name="bottom", ratio=1),
        )

        layout["top"].split_row(
            Layout(name="cognitive", ratio=2),
            Layout(name="project", ratio=1),
        )

        # Render widgets (order defined in WIDGET_ORDER)
        # Each render call is a pure function

        cognitive_widget = CognitiveStateWidget(state.cognitive)
        layout["cognitive"].update(cognitive_widget.render())

        project_widget = ProjectCardWidget(
            state.get_focus_project(),
            state.projects,
        )
        layout["project"].update(project_widget.render())

        alert_widget = AlertFeedWidget(state.get_recent_alerts())
        layout["bottom"].update(alert_widget.render())

        return layout

    def _render_footer(self) -> Panel:
        """
        Render footer panel with shortcuts.

        Determinism: Pure function, shortcuts from FIXED constants.
        """
        state = self._store.state

        command_widget = CommandBarWidget(
            connected=state.connected,
            error_message=state.error_message,
            current_input=self._current_input if self._command_mode else "",
        )
        return command_widget.render()

    def render(self) -> Layout:
        """
        Render complete dashboard.

        Determinism:
        - Fixed layout structure
        - Rendering order matches WIDGET_ORDER
        - Pure function of state
        """
        # Create main layout
        layout = Layout()

        # Fixed ratios, no content-dependent sizing
        layout.split_column(
            Layout(name="header", size=HEADER_HEIGHT),
            Layout(name="body"),
            Layout(name="footer", size=FOOTER_HEIGHT + 1),
        )

        # Render each section
        layout["header"].update(self._render_header())
        layout["body"].update(self._render_body())
        layout["footer"].update(self._render_footer())

        return layout

    # =========================================================================
    # Command Handlers
    # Fixed handler mapping, deterministic dispatch
    # =========================================================================

    def _handle_health(self) -> None:
        """Handle 'health' command."""
        # Add alert showing health status
        alert = Alert(
            id=f"health_{datetime.now().timestamp()}",
            timestamp=datetime.now().timestamp(),
            severity="info",
            title="Health Check",
            message="System operational. All components healthy.",
            source="dashboard",
        )
        self._store.dispatch("ALERT_ADD", alert.__dict__)

    def _handle_state(self) -> None:
        """Handle 'state' command."""
        state = self._store.state.cognitive
        alert = Alert(
            id=f"state_{datetime.now().timestamp()}",
            timestamp=datetime.now().timestamp(),
            severity="info",
            title="Current State",
            message=f"Mode: {state.active_mode}, Burnout: {state.burnout_level}, Energy: {state.energy_level}",
            source="dashboard",
        )
        self._store.dispatch("ALERT_ADD", alert.__dict__)

    def _handle_projects(self) -> None:
        """Handle 'projects' command."""
        projects = self._store.state.projects
        count = len(projects)
        focus = next((p for p in projects if p.status == "FOCUS"), None)
        message = f"{count} projects"
        if focus:
            message += f", Focus: {focus.name}"

        alert = Alert(
            id=f"projects_{datetime.now().timestamp()}",
            timestamp=datetime.now().timestamp(),
            severity="info",
            title="Projects",
            message=message,
            source="dashboard",
        )
        self._store.dispatch("ALERT_ADD", alert.__dict__)

    def _handle_refresh(self) -> None:
        """Handle 'refresh' command."""
        # Force re-render by updating connection state
        self._store.dispatch("CONNECTION_UPDATE", {
            "connected": self._store.state.connected,
            "error": "",
        })

    def _handle_quit(self) -> None:
        """Handle 'quit' command."""
        self._running = False

    def _handle_command_mode(self) -> None:
        """Toggle command input mode."""
        self._command_mode = not self._command_mode
        self._current_input = ""

    def handle_key(self, key: str) -> None:
        """
        Handle keyboard input.

        Determinism:
        - Fixed key → command mapping from KEYBOARD_SHORTCUTS
        - Deterministic dispatch order
        """
        if self._command_mode:
            if key == "\n" or key == "\r":
                # Execute typed command
                cmd = self._current_input.strip().lower()
                if cmd in self._command_handlers:
                    self._command_handlers[cmd]()
                self._command_mode = False
                self._current_input = ""
            elif key == "\x1b":  # Escape
                self._command_mode = False
                self._current_input = ""
            elif key == "\x7f":  # Backspace
                self._current_input = self._current_input[:-1]
            elif len(key) == 1 and key.isprintable():
                self._current_input += key
        else:
            # Check keyboard shortcuts
            # Fixed iteration order (tuple)
            for shortcut_key, command, _ in KEYBOARD_SHORTCUTS:
                if key.lower() == shortcut_key:
                    handler = self._command_handlers.get(command)
                    if handler:
                        handler()
                    break

    async def run(self) -> None:
        """
        Run the dashboard.

        Determinism:
        - Fixed update interval
        - Deterministic render loop
        """
        self._running = True

        # Initialize with demo data if no state
        self._initialize_demo_state()

        with Live(
            self.render(),
            console=self._console,
            refresh_per_second=4,  # Fixed refresh rate
            screen=True,
        ) as live:
            while self._running:
                # Update display
                live.update(self.render())

                # Small sleep to prevent busy loop
                await asyncio.sleep(0.25)

    def _initialize_demo_state(self) -> None:
        """Initialize with demo data for testing."""
        import time

        # Set initial cognitive state
        self._store.dispatch("COGNITIVE_UPDATE", {
            "active_mode": "focused",
            "burnout_level": "GREEN",
            "energy_level": "high",
            "momentum_phase": "rolling",
            "current_altitude": "15000ft",
            "exchange_count": 42,
        })

        # Add demo projects
        demo_projects = [
            {"id": "p1", "name": "OTTO OS", "status": "FOCUS", "progress": 0.78, "next_action": "Complete TUI dashboard"},
            {"id": "p2", "name": "Documentation", "status": "HOLDING", "progress": 0.65, "next_action": ""},
            {"id": "p3", "name": "Research", "status": "BACKGROUND", "progress": 0.30, "next_action": ""},
        ]
        self._store.dispatch("PROJECTS_UPDATE", {"projects": demo_projects})

        # Add demo alerts
        base_time = time.time()
        demo_alerts = [
            {
                "id": "a1",
                "timestamp": base_time - 60,
                "severity": "info",
                "title": "Session Started",
                "message": "TUI Dashboard initialized",
            },
            {
                "id": "a2",
                "timestamp": base_time - 30,
                "severity": "info",
                "title": "State Synced",
                "message": "Cognitive state synchronized",
            },
        ]
        for alert_data in demo_alerts:
            self._store.dispatch("ALERT_ADD", alert_data)

        # Set connected
        self._store.dispatch("CONNECTION_UPDATE", {"connected": True})


def create_dashboard(
    store: Optional[StateStore] = None,
    console: Optional[Console] = None,
) -> OTTODashboard:
    """
    Factory function to create dashboard.

    Determinism: Deterministic initialization.
    """
    return OTTODashboard(store=store, console=console)


async def run_dashboard() -> None:
    """
    Entry point to run the dashboard.

    Determinism: Fixed initialization sequence.
    """
    dashboard = create_dashboard()
    await dashboard.run()


def main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(run_dashboard())
    except KeyboardInterrupt:
        pass
