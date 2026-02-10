#!/usr/bin/env python3
"""
Enhanced TUI Dashboard - Phase 7
================================

Real-time terminal dashboard with agent monitoring and progress visualization.

Features:
- Live agent execution monitoring
- Progress bars with ETA calculation
- Cognitive state visualization
- Interactive controls
- Determinism status display

Usage:
  python -m otto.cli.tui_enhanced              # Launch enhanced TUI
  python -m otto.cli.tui_enhanced --minimal    # Minimal mode (less detail)

Keyboard:
  q / Ctrl+C  - Quit
  r           - Refresh
  a           - Toggle agent panel
  p           - Toggle progress detail
  1-4         - Set burnout level (testing)

Determinism:
- Fixed display phases
- Deterministic color mapping
- Bounded update frequency
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.style import Style
    from rich.align import Align
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
    from rich.columns import Columns
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# =============================================================================
# Determinism Compliance: Fixed Display Constants
# =============================================================================

class DisplayPhase(Enum):
    """Fixed display phases for deterministic rendering."""
    IDLE = "idle"
    PROCESSING = "processing"
    AGENT_ACTIVE = "agent_active"
    ERROR = "error"


# Burnout color mapping (FIXED - no runtime variation)
BURNOUT_STYLES = {
    "GREEN": Style(color="green", bold=True),
    "YELLOW": Style(color="yellow", bold=True),
    "ORANGE": Style(color="dark_orange", bold=True),
    "RED": Style(color="red", bold=True),
}

# Decision mode styles (FIXED)
MODE_STYLES = {
    "work": Style(color="green"),
    "delegate": Style(color="blue"),
    "protect": Style(color="magenta"),
}

# Agent status styles (FIXED)
AGENT_STATUS_STYLES = {
    "running": Style(color="cyan"),
    "completed": Style(color="green"),
    "failed": Style(color="red"),
    "aborted": Style(color="yellow"),
}

# Momentum visualization (FIXED mapping)
MOMENTUM_VISUAL = {
    "cold_start": ("▁▁▁▁▁▁▁▁▁▁", 0.1),
    "building": ("███▁▁▁▁▁▁▁", 0.35),
    "rolling": ("██████▁▁▁▁", 0.65),
    "peak": ("██████████", 1.0),
    "crashed": ("▁▁▁▁▁▁▁▁▁▁", 0.05),
}

# Energy visualization (FIXED mapping)
ENERGY_VISUAL = {
    "high": "████",
    "medium": "███░",
    "low": "██░░",
    "depleted": "█░░░",
}


# =============================================================================
# State Files
# =============================================================================

STATE_FILE = Path.home() / ".orchestra" / "state" / "cognitive_state.json"
AGENT_STATE_FILE = Path.home() / ".orchestra" / "state" / "agent_state.json"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AgentDisplayInfo:
    """Agent information for display."""
    agent_id: str
    agent_type: str
    task: str
    status: str
    current_step: int = 0
    total_steps: int = 0
    start_time: float = 0.0
    duration_seconds: float = 0.0

    @property
    def percentage(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100

    @property
    def progress_bar(self) -> str:
        width = 15
        filled = int(width * self.percentage / 100)
        return "█" * filled + "░" * (width - filled)


@dataclass
class DashboardState:
    """Complete dashboard state."""
    # Cognitive state
    burnout_level: str = "GREEN"
    decision_mode: str = "work"
    momentum_phase: str = "rolling"
    energy_level: str = "high"
    working_memory_used: int = 2
    tangent_budget: int = 5
    altitude: str = "30000ft"
    paradigm: str = "Cortex"

    # Agent state
    active_agents: List[AgentDisplayInfo] = field(default_factory=list)
    completed_agents: List[AgentDisplayInfo] = field(default_factory=list)

    # Session stats
    exchange_count: int = 0
    tasks_completed: int = 0
    session_minutes: int = 0

    # Display phase
    display_phase: DisplayPhase = DisplayPhase.IDLE
    last_update: datetime = field(default_factory=datetime.now)


# =============================================================================
# State Reader
# =============================================================================

def read_cognitive_state() -> Dict[str, Any]:
    """Read cognitive state from file."""
    default = {
        "burnout_level": "GREEN",
        "decision_mode": "work",
        "momentum_phase": "rolling",
        "energy_level": "high",
        "working_memory_used": 2,
        "tangent_budget": 5,
        "altitude": "30000ft",
        "paradigm": "Cortex",
        "exchange_count": 0,
        "tasks_completed": 0,
        "session_minutes": 0,
    }

    if not STATE_FILE.exists():
        return default

    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
            return {**default, **data}
    except Exception:
        return default


def read_agent_state() -> List[AgentDisplayInfo]:
    """Read active agent state from file."""
    if not AGENT_STATE_FILE.exists():
        return []

    try:
        with open(AGENT_STATE_FILE) as f:
            data = json.load(f)
            agents = []
            for agent_data in data.get("agents", []):
                agents.append(AgentDisplayInfo(
                    agent_id=agent_data.get("agent_id", "unknown"),
                    agent_type=agent_data.get("agent_type", "unknown"),
                    task=agent_data.get("task", "")[:50],
                    status=agent_data.get("status", "running"),
                    current_step=agent_data.get("current_step", 0),
                    total_steps=agent_data.get("total_steps", 1),
                    start_time=agent_data.get("start_time", time.time()),
                    duration_seconds=agent_data.get("duration_seconds", 0.0),
                ))
            return agents
    except Exception:
        return []


def write_state(state: Dict[str, Any]) -> None:
    """Write state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# =============================================================================
# Panel Builders
# =============================================================================

def build_header_panel(state: DashboardState) -> Panel:
    """Build header panel with title and time."""
    burnout_style = BURNOUT_STYLES.get(state.burnout_level, BURNOUT_STYLES["GREEN"])

    header_text = Text()
    header_text.append("◈ ", style=burnout_style)
    header_text.append("OTTO", style="bold white")
    header_text.append(" OS", style="dim white")
    header_text.append("  │  ", style="dim")
    header_text.append(time.strftime("%H:%M:%S"), style="dim")
    header_text.append("  │  ", style="dim")
    header_text.append(f"Phase 7 TUI", style="dim cyan")

    return Panel(
        Align.center(header_text),
        style="dim",
        border_style="dim",
    )


def build_burnout_panel(state: DashboardState) -> Panel:
    """Build burnout level display panel."""
    burnout_style = BURNOUT_STYLES.get(state.burnout_level, BURNOUT_STYLES["GREEN"])

    burnout_text = Text()
    burnout_text.append(f"\n{state.burnout_level}\n", style=burnout_style)
    burnout_text.append("BURNOUT LEVEL", style="dim")

    return Panel(
        Align.center(burnout_text),
        border_style=burnout_style,
    )


def build_mode_panel(state: DashboardState) -> Panel:
    """Build decision mode display panel."""
    mode_style = MODE_STYLES.get(state.decision_mode, MODE_STYLES["work"])

    mode_text = Text()
    mode_text.append(f"\n{state.decision_mode.upper()}\n", style=mode_style)
    mode_text.append("DECISION MODE", style="dim")

    return Panel(
        Align.center(mode_text),
        border_style=mode_style,
    )


def build_metrics_panel(state: DashboardState) -> Panel:
    """Build cognitive metrics table panel."""
    burnout_style = BURNOUT_STYLES.get(state.burnout_level, BURNOUT_STYLES["GREEN"])

    metrics = Table(show_header=False, box=None, padding=(0, 2))
    metrics.add_column("Label", style="dim", width=16)
    metrics.add_column("Value", width=20)
    metrics.add_column("Label2", style="dim", width=16)
    metrics.add_column("Value2", width=20)

    # Row 1: Momentum + Energy
    momentum_bar, _ = MOMENTUM_VISUAL.get(state.momentum_phase, MOMENTUM_VISUAL["rolling"])
    momentum_text = Text()
    momentum_text.append(momentum_bar, style=burnout_style)
    momentum_text.append(f" {state.momentum_phase.upper().replace('_', ' ')}", style="dim")

    energy_bar = ENERGY_VISUAL.get(state.energy_level, ENERGY_VISUAL["high"])
    energy_text = Text()
    energy_text.append(energy_bar, style=burnout_style)
    energy_text.append(f" {state.energy_level.upper()}", style="dim")

    metrics.add_row("MOMENTUM", momentum_text, "ENERGY", energy_text)

    # Row 2: Working Memory + Tangent Budget
    wm_slots = "●" * state.working_memory_used + "○" * (3 - min(state.working_memory_used, 3))
    wm_text = Text()
    wm_text.append(wm_slots, style=burnout_style)
    wm_text.append(f" {state.working_memory_used}/3", style="dim")

    tangent_text = Text()
    tangent_text.append(str(state.tangent_budget), style="bold white")
    tangent_text.append(" of 5", style="dim")

    metrics.add_row("WORKING MEMORY", wm_text, "TANGENT BUDGET", tangent_text)

    # Row 3: Altitude + Paradigm
    alt_map = {"30000ft": "30K VISION", "15000ft": "15K ARCH", "5000ft": "5K COMP", "Ground": "GND CODE"}
    alt_text = Text(alt_map.get(state.altitude, state.altitude), style="white")
    paradigm_text = Text(state.paradigm.upper(), style="white")

    metrics.add_row("ALTITUDE", alt_text, "PARADIGM", paradigm_text)

    return Panel(
        metrics,
        title="[dim]COGNITIVE STATE[/dim]",
        border_style="dim",
    )


def build_agent_panel(state: DashboardState) -> Panel:
    """Build active agent monitoring panel."""
    if not state.active_agents:
        content = Text("No active agents", style="dim italic")
        return Panel(
            Align.center(content),
            title="[dim]AGENT MONITOR[/dim]",
            border_style="dim",
        )

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Agent", style="cyan", width=12)
    table.add_column("Task", width=25)
    table.add_column("Progress", width=20)
    table.add_column("Status", width=10)

    for agent in state.active_agents[:5]:  # Max 5 visible
        status_style = AGENT_STATUS_STYLES.get(agent.status, Style())

        progress_text = Text()
        progress_text.append(agent.progress_bar, style="cyan")
        progress_text.append(f" {agent.percentage:.0f}%", style="dim")

        table.add_row(
            agent.agent_type[:10],
            agent.task[:23] + "..." if len(agent.task) > 23 else agent.task,
            progress_text,
            Text(agent.status.upper(), style=status_style),
        )

    return Panel(
        table,
        title=f"[dim]AGENT MONITOR ({len(state.active_agents)} active)[/dim]",
        border_style="cyan",
    )


def build_progress_panel(state: DashboardState) -> Panel:
    """Build detailed progress panel for current agent."""
    if not state.active_agents:
        return Panel(
            Align.center(Text("Waiting for agent activity...", style="dim")),
            title="[dim]PROGRESS[/dim]",
            border_style="dim",
        )

    # Show most recent agent's progress
    agent = state.active_agents[0]

    content = Text()
    content.append(f"\n{agent.agent_type.upper()}\n", style="bold cyan")
    content.append(f"Task: {agent.task}\n\n", style="dim")

    # Large progress bar
    bar_width = 30
    filled = int(bar_width * agent.percentage / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    content.append(f"[{bar}]\n", style="cyan")
    content.append(f"Step {agent.current_step}/{agent.total_steps} ({agent.percentage:.1f}%)\n\n", style="white")

    # Duration/ETA
    if agent.duration_seconds > 0:
        content.append(f"Duration: {agent.duration_seconds:.1f}s", style="dim")

    return Panel(
        Align.center(content),
        title="[dim]CURRENT PROGRESS[/dim]",
        border_style="cyan",
    )


def build_session_panel(state: DashboardState) -> Panel:
    """Build session statistics panel."""
    stats = Text()
    stats.append(f"Exchanges: {state.exchange_count}  │  ", style="dim")
    stats.append(f"Tasks: {state.tasks_completed}  │  ", style="dim")
    stats.append(f"Session: {state.session_minutes}m", style="dim")

    return Panel(
        Align.center(stats),
        border_style="dim",
    )


def build_footer_panel(show_agent_panel: bool = True) -> Panel:
    """Build footer with keyboard shortcuts."""
    footer_text = Text()
    footer_text.append("q", style="bold")
    footer_text.append(" quit  ", style="dim")
    footer_text.append("r", style="bold")
    footer_text.append(" refresh  ", style="dim")
    footer_text.append("a", style="bold")
    footer_text.append(f" agents{'✓' if show_agent_panel else ''}  ", style="dim")
    footer_text.append("1-4", style="bold")
    footer_text.append(" burnout", style="dim")

    return Panel(
        Align.center(footer_text),
        style="dim",
        border_style="dim",
    )


# =============================================================================
# Dashboard Layout Builder
# =============================================================================

def create_dashboard_layout(
    state: DashboardState,
    show_agent_panel: bool = True,
    show_progress_detail: bool = True,
) -> Layout:
    """Create the full dashboard layout."""

    layout = Layout()

    # Main structure
    layout.split_column(
        Layout(build_header_panel(state), name="header", size=3),
        Layout(name="main"),
        Layout(build_session_panel(state), name="session", size=3),
        Layout(build_footer_panel(show_agent_panel), name="footer", size=3),
    )

    # Main area split
    main = layout["main"]

    if show_agent_panel and state.active_agents:
        # With agent panel
        main.split_column(
            Layout(name="top", size=7),
            Layout(build_metrics_panel(state), name="metrics", size=6),
            Layout(name="agents"),
        )

        # Agent area split
        if show_progress_detail:
            layout["agents"].split_row(
                Layout(build_agent_panel(state), ratio=3),
                Layout(build_progress_panel(state), ratio=2),
            )
        else:
            layout["agents"].update(build_agent_panel(state))
    else:
        # Without agent panel
        main.split_column(
            Layout(name="top", size=7),
            Layout(build_metrics_panel(state), name="metrics"),
        )

    # Top row: burnout + mode
    layout["top"].split_row(
        Layout(build_burnout_panel(state)),
        Layout(build_mode_panel(state)),
    )

    return layout


# =============================================================================
# Dashboard Runner
# =============================================================================

class EnhancedTUI:
    """Enhanced TUI dashboard runner."""

    def __init__(self, minimal: bool = False):
        self.console = Console()
        self.minimal = minimal
        self.show_agent_panel = True
        self.show_progress_detail = True
        self.running = True

    def read_state(self) -> DashboardState:
        """Read complete dashboard state."""
        cognitive = read_cognitive_state()
        agents = read_agent_state()

        active = [a for a in agents if a.status == "running"]
        completed = [a for a in agents if a.status != "running"]

        return DashboardState(
            burnout_level=cognitive.get("burnout_level", "GREEN"),
            decision_mode=cognitive.get("decision_mode", "work"),
            momentum_phase=cognitive.get("momentum_phase", "rolling"),
            energy_level=cognitive.get("energy_level", "high"),
            working_memory_used=cognitive.get("working_memory_used", 2),
            tangent_budget=cognitive.get("tangent_budget", 5),
            altitude=cognitive.get("altitude", "30000ft"),
            paradigm=cognitive.get("paradigm", "Cortex"),
            active_agents=active,
            completed_agents=completed,
            exchange_count=cognitive.get("exchange_count", 0),
            tasks_completed=cognitive.get("tasks_completed", 0),
            session_minutes=cognitive.get("session_minutes", 0),
            display_phase=DisplayPhase.AGENT_ACTIVE if active else DisplayPhase.IDLE,
        )

    def handle_key(self, key: str, state_dict: Dict[str, Any]) -> bool:
        """Handle keyboard input. Returns True if should quit."""
        if key in ('q', 'Q', '\x03'):  # q or Ctrl+C
            return True
        elif key == 'r':
            pass  # Refresh handled by loop
        elif key == 'a':
            self.show_agent_panel = not self.show_agent_panel
        elif key == 'p':
            self.show_progress_detail = not self.show_progress_detail
        elif key == '1':
            state_dict["burnout_level"] = "GREEN"
            write_state(state_dict)
        elif key == '2':
            state_dict["burnout_level"] = "YELLOW"
            write_state(state_dict)
        elif key == '3':
            state_dict["burnout_level"] = "ORANGE"
            write_state(state_dict)
        elif key == '4':
            state_dict["burnout_level"] = "RED"
            write_state(state_dict)
        return False

    def run_live(self) -> None:
        """Run with auto-refresh."""
        try:
            with Live(console=self.console, refresh_per_second=2, screen=True) as live:
                while self.running:
                    state = self.read_state()
                    layout = create_dashboard_layout(
                        state,
                        show_agent_panel=self.show_agent_panel and not self.minimal,
                        show_progress_detail=self.show_progress_detail and not self.minimal,
                    )
                    live.update(layout)
                    time.sleep(0.5)
        except KeyboardInterrupt:
            pass

    def run_interactive(self) -> None:
        """Run with keyboard input."""
        # Platform-specific keyboard handling
        if sys.platform == "win32":
            self._run_interactive_windows()
        else:
            self._run_interactive_unix()

    def _run_interactive_windows(self) -> None:
        """Windows interactive mode."""
        import msvcrt

        while self.running:
            state = self.read_state()
            state_dict = read_cognitive_state()

            layout = create_dashboard_layout(
                state,
                show_agent_panel=self.show_agent_panel and not self.minimal,
                show_progress_detail=self.show_progress_detail and not self.minimal,
            )

            self.console.clear()
            self.console.print(layout)

            # Check for key with timeout
            start = time.time()
            while time.time() - start < 1.0:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore')
                    if self.handle_key(key, state_dict):
                        self.running = False
                        break
                time.sleep(0.05)

    def _run_interactive_unix(self) -> None:
        """Unix interactive mode."""
        import select
        import tty
        import termios

        try:
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

            while self.running:
                state = self.read_state()
                state_dict = read_cognitive_state()

                layout = create_dashboard_layout(
                    state,
                    show_agent_panel=self.show_agent_panel and not self.minimal,
                    show_progress_detail=self.show_progress_detail and not self.minimal,
                )

                self.console.clear()
                self.console.print(layout)

                # Wait for input with timeout
                if select.select([sys.stdin], [], [], 1)[0]:
                    key = sys.stdin.read(1)
                    if self.handle_key(key, state_dict):
                        break

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
        finally:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except Exception:
                pass


def run_once() -> None:
    """Display dashboard once and exit."""
    if not RICH_AVAILABLE:
        print("Error: rich library required. Install with: pip install rich")
        sys.exit(1)

    console = Console()
    tui = EnhancedTUI()
    state = tui.read_state()
    layout = create_dashboard_layout(state)
    console.print(layout)


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="OTTO OS Enhanced TUI Dashboard")
    parser.add_argument("--watch", "-w", action="store_true", help="Auto-refresh mode")
    parser.add_argument("--once", "-1", action="store_true", help="Display once and exit")
    parser.add_argument("--minimal", "-m", action="store_true", help="Minimal display mode")

    args = parser.parse_args()

    if not RICH_AVAILABLE:
        print("Error: rich library required. Install with: pip install rich")
        sys.exit(1)

    if args.once:
        run_once()
    else:
        tui = EnhancedTUI(minimal=args.minimal)
        if args.watch:
            tui.run_live()
        else:
            tui.run_interactive()


if __name__ == "__main__":
    main()
