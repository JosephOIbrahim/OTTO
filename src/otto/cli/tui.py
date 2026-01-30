#!/usr/bin/env python3
"""
Orchestra TUI Dashboard - Full Terminal UI

Usage:
  orchestra              # Launch TUI dashboard
  orchestra --watch      # Auto-refresh every second
  orchestra --once       # Display once and exit

Keyboard:
  q / Ctrl+C  - Quit
  r           - Refresh
  1-4         - Set burnout level (for testing)
  w/d/p       - Set mode work/delegate/protect (for testing)

Requirements:
  pip install rich
"""

import json
import sys
import time
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.style import Style
    from rich.align import Align
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# State file location
STATE_FILE = Path.home() / ".orchestra" / "state" / "cognitive_state.json"

# Color mappings
BURNOUT_STYLES = {
    "GREEN": Style(color="green", bold=True),
    "YELLOW": Style(color="yellow", bold=True),
    "ORANGE": Style(color="dark_orange", bold=True),
    "RED": Style(color="red", bold=True)
}

MODE_STYLES = {
    "work": Style(color="green"),
    "delegate": Style(color="blue"),
    "protect": Style(color="magenta")
}

MOMENTUM_VISUAL = {
    "cold_start": ("▁▁▁▁▁▁▁▁▁▁", 0.1),
    "building": ("███▁▁▁▁▁▁▁", 0.35),
    "rolling": ("██████▁▁▁▁", 0.65),
    "peak": ("██████████", 1.0),
    "crashed": ("▁▁▁▁▁▁▁▁▁▁", 0.05)
}

ENERGY_VISUAL = {
    "high": "████",
    "medium": "███░",
    "low": "██░░",
    "depleted": "█░░░"
}


def read_state() -> dict:
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
        "current_task": None
    }

    if not STATE_FILE.exists():
        return default

    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
            return {**default, **data}
    except Exception:
        return default


def write_state(state: dict) -> None:
    """Write state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def create_dashboard(state: dict, console: Console) -> Layout:
    """Create the dashboard layout."""

    burnout = state.get("burnout_level", "GREEN")
    mode = state.get("decision_mode", "work")
    momentum = state.get("momentum_phase", "rolling")
    energy = state.get("energy_level", "high")
    wm = state.get("working_memory_used", 2)
    tangent = state.get("tangent_budget", 5)
    altitude = state.get("altitude", "30000ft")
    paradigm = state.get("paradigm", "Cortex")
    task = state.get("current_task")

    burnout_style = BURNOUT_STYLES.get(burnout, BURNOUT_STYLES["GREEN"])
    mode_style = MODE_STYLES.get(mode, MODE_STYLES["work"])
    momentum_bar, momentum_pct = MOMENTUM_VISUAL.get(momentum, MOMENTUM_VISUAL["rolling"])
    energy_bar = ENERGY_VISUAL.get(energy, ENERGY_VISUAL["high"])

    # Create layout
    layout = Layout()

    # Header
    header_text = Text()
    header_text.append("◈ ", style=burnout_style)
    header_text.append("ORCHESTRA", style="bold white")
    header_text.append("  │  ", style="dim")
    header_text.append(time.strftime("%H:%M:%S"), style="dim")

    header = Panel(
        Align.center(header_text),
        style="dim",
        border_style="dim"
    )

    # Main burnout display
    burnout_text = Text()
    burnout_text.append(f"\n{burnout}\n", style=burnout_style)
    burnout_text.append("BURNOUT LEVEL", style="dim")

    burnout_panel = Panel(
        Align.center(burnout_text),
        border_style=burnout_style
    )

    # Mode display
    mode_text = Text()
    mode_text.append(f"\n{mode.upper()}\n", style=mode_style)
    mode_text.append("DECISION MODE", style="dim")

    mode_panel = Panel(
        Align.center(mode_text),
        border_style=mode_style
    )

    # Metrics table
    metrics = Table(show_header=False, box=None, padding=(0, 2))
    metrics.add_column("Label", style="dim", width=16)
    metrics.add_column("Value", width=20)
    metrics.add_column("Label2", style="dim", width=16)
    metrics.add_column("Value2", width=20)

    # Row 1: Momentum + Energy
    momentum_text = Text()
    momentum_text.append(momentum_bar, style=burnout_style)
    momentum_text.append(f" {momentum.upper().replace('_', ' ')}", style="dim")

    energy_text = Text()
    energy_text.append(energy_bar, style=burnout_style)
    energy_text.append(f" {energy.upper()}", style="dim")

    metrics.add_row("MOMENTUM", momentum_text, "ENERGY", energy_text)

    # Row 2: Working Memory + Tangent Budget
    wm_text = Text()
    wm_slots = "●" * wm + "○" * (3 - wm)
    wm_text.append(wm_slots, style=burnout_style)
    wm_text.append(f" {wm}/3", style="dim")

    tangent_text = Text()
    tangent_text.append(str(tangent), style="bold white")
    tangent_text.append(" of 5", style="dim")

    metrics.add_row("WORKING MEMORY", wm_text, "TANGENT BUDGET", tangent_text)

    # Row 3: Altitude + Paradigm
    alt_map = {"30000ft": "30K VISION", "15000ft": "15K ARCH", "5000ft": "5K COMP", "Ground": "GND CODE"}
    alt_text = Text(alt_map.get(altitude, altitude), style="white")

    paradigm_text = Text(paradigm.upper(), style="white")

    metrics.add_row("ALTITUDE", alt_text, "PARADIGM", paradigm_text)

    metrics_panel = Panel(
        metrics,
        title="[dim]COGNITIVE STATE[/dim]",
        border_style="dim"
    )

    # Task panel (if present)
    if task:
        task_panel = Panel(
            Text(task, style="italic"),
            title="[dim]CURRENT TASK[/dim]",
            border_style="dim"
        )
    else:
        task_panel = None

    # Footer
    footer_text = Text()
    footer_text.append("q", style="bold")
    footer_text.append(" quit  ", style="dim")
    footer_text.append("r", style="bold")
    footer_text.append(" refresh  ", style="dim")
    footer_text.append("1-4", style="bold")
    footer_text.append(" burnout  ", style="dim")
    footer_text.append("w/d/p", style="bold")
    footer_text.append(" mode", style="dim")

    footer = Panel(
        Align.center(footer_text),
        style="dim",
        border_style="dim"
    )

    # Assemble layout
    layout.split_column(
        Layout(header, size=3),
        Layout(name="main"),
        Layout(footer, size=3)
    )

    # Main area
    main_layout = layout["main"]
    main_layout.split_column(
        Layout(name="top", size=7),
        Layout(metrics_panel, name="metrics"),
    )

    # Top row: burnout + mode
    layout["top"].split_row(
        Layout(burnout_panel),
        Layout(mode_panel)
    )

    # Add task if present
    if task_panel:
        layout["metrics"].split_column(
            Layout(metrics_panel, ratio=2),
            Layout(task_panel, ratio=1)
        )

    return layout


def run_tui(watch: bool = False):
    """Run the TUI dashboard."""
    if not RICH_AVAILABLE:
        print("Error: rich library required. Install with: pip install rich")
        sys.exit(1)

    console = Console()

    if watch:
        # Live updating mode
        try:
            with Live(console=console, refresh_per_second=1, screen=True) as live:
                while True:
                    state = read_state()
                    layout = create_dashboard(state, console)
                    live.update(layout)
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        # Single display with keyboard input
        import select
        import tty
        import termios

        console.clear()

        try:
            # Set terminal to raw mode for single key input
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

            while True:
                state = read_state()
                layout = create_dashboard(state, console)

                console.clear()
                console.print(layout)

                # Wait for input with timeout
                if select.select([sys.stdin], [], [], 1)[0]:
                    key = sys.stdin.read(1)

                    if key in ('q', 'Q', '\x03'):  # q or Ctrl+C
                        break
                    elif key == 'r':
                        continue  # Refresh
                    elif key == '1':
                        state["burnout_level"] = "GREEN"
                        write_state(state)
                    elif key == '2':
                        state["burnout_level"] = "YELLOW"
                        write_state(state)
                    elif key == '3':
                        state["burnout_level"] = "ORANGE"
                        write_state(state)
                    elif key == '4':
                        state["burnout_level"] = "RED"
                        write_state(state)
                    elif key == 'w':
                        state["decision_mode"] = "work"
                        write_state(state)
                    elif key == 'd':
                        state["decision_mode"] = "delegate"
                        write_state(state)
                    elif key == 'p':
                        state["decision_mode"] = "protect"
                        write_state(state)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        finally:
            # Restore terminal settings
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except Exception:
                pass


def run_once():
    """Display dashboard once and exit."""
    if not RICH_AVAILABLE:
        print("Error: rich library required. Install with: pip install rich")
        sys.exit(1)

    console = Console()
    state = read_state()
    layout = create_dashboard(state, console)
    console.print(layout)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Orchestra TUI Dashboard")
    parser.add_argument("--watch", "-w", action="store_true", help="Auto-refresh mode")
    parser.add_argument("--once", "-1", action="store_true", help="Display once and exit")

    args = parser.parse_args()

    if args.once:
        run_once()
    elif args.watch:
        run_tui(watch=True)
    else:
        run_tui(watch=False)


if __name__ == "__main__":
    main()
