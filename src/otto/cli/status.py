#!/usr/bin/env python3
r"""
Orchestra Terminal Status - Zero Friction Integration

Usage:
  orchestra-status          # Full status line
  orchestra-status --short  # Minimal (for prompts)
  orchestra-status --json   # JSON output
  orchestra-status --tmux   # tmux status bar format

Designed for shell prompt integration:
  PS1='$(orchestra-status --short) \$ '

Or tmux:
  set -g status-right '#(orchestra-status --tmux)'
"""

import json
import sys
from pathlib import Path
from typing import Optional

# Enable UTF-8 and ANSI on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    # Enable ANSI escape sequences on Windows 10+
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# State file location
STATE_FILE = Path.home() / ".orchestra" / "state" / "cognitive_state.json"

# ANSI color codes (works in most terminals)
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Burnout colors
    GREEN = "\033[38;5;41m"   # Bright green
    YELLOW = "\033[38;5;220m" # Yellow
    ORANGE = "\033[38;5;208m" # Orange
    RED = "\033[38;5;196m"    # Red

    # Other
    BLUE = "\033[38;5;75m"    # Blue
    PURPLE = "\033[38;5;141m" # Purple
    GRAY = "\033[38;5;245m"   # Gray

# State mappings
BURNOUT_COLORS = {
    "GREEN": Colors.GREEN,
    "YELLOW": Colors.YELLOW,
    "ORANGE": Colors.ORANGE,
    "RED": Colors.RED
}

MODE_SYMBOLS = {
    "work": ("→", Colors.GREEN),
    "delegate": ("⫸", Colors.BLUE),
    "protect": ("◈", Colors.PURPLE)
}

MOMENTUM_BARS = {
    "cold_start": "▁",
    "building": "▃",
    "rolling": "▅",
    "peak": "█",
    "crashed": "▁"
}

ALTITUDE_SHORT = {
    "30000ft": "30K",
    "15000ft": "15K",
    "5000ft": "5K",
    "Ground": "GND"
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
        "paradigm": "Cortex"
    }

    if not STATE_FILE.exists():
        return default

    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
            # Merge with defaults
            return {**default, **data}
    except Exception:
        return default


def format_short(state: dict, color: bool = True) -> str:
    """
    Minimal format for shell prompts.
    Example: ◈ GREEN
    """
    burnout = state.get("burnout_level", "GREEN")

    if color:
        c = BURNOUT_COLORS.get(burnout, Colors.GREEN)
        return f"{c}◈{Colors.RESET}"
    else:
        return f"◈{burnout[0]}"  # Just first letter: G/Y/O/R


def format_prompt(state: dict, color: bool = True) -> str:
    """
    Prompt-friendly format.
    Example: ◈ GREEN | WORK | ▅
    """
    burnout = state.get("burnout_level", "GREEN")
    mode = state.get("decision_mode", "work")
    momentum = state.get("momentum_phase", "rolling")

    burnout_color = BURNOUT_COLORS.get(burnout, Colors.GREEN)
    mode_sym, mode_color = MODE_SYMBOLS.get(mode, ("→", Colors.GREEN))
    momentum_bar = MOMENTUM_BARS.get(momentum, "▅")

    if color:
        return (
            f"{burnout_color}◈{Colors.RESET} "
            f"{burnout_color}{burnout}{Colors.RESET} "
            f"{Colors.DIM}│{Colors.RESET} "
            f"{mode_color}{mode.upper()}{Colors.RESET} "
            f"{Colors.DIM}│{Colors.RESET} "
            f"{burnout_color}{momentum_bar}{Colors.RESET}"
        )
    else:
        return f"◈ {burnout} | {mode.upper()} | {momentum_bar}"


def format_full(state: dict, color: bool = True) -> str:
    """
    Full status line.
    Example: ◈ GREEN | WORK | ▅ ROLLING | 30K | 2/3 | T:5 | CORTEX
    """
    burnout = state.get("burnout_level", "GREEN")
    mode = state.get("decision_mode", "work")
    momentum = state.get("momentum_phase", "rolling")
    altitude = state.get("altitude", "30000ft")
    wm = state.get("working_memory_used", 2)
    tangent = state.get("tangent_budget", 5)
    paradigm = state.get("paradigm", "Cortex")

    burnout_color = BURNOUT_COLORS.get(burnout, Colors.GREEN)
    mode_sym, mode_color = MODE_SYMBOLS.get(mode, ("→", Colors.GREEN))
    momentum_bar = MOMENTUM_BARS.get(momentum, "▅")
    alt_short = ALTITUDE_SHORT.get(altitude, "30K")

    if color:
        sep = f"{Colors.DIM}│{Colors.RESET}"
        return (
            f"{burnout_color}◈ {burnout}{Colors.RESET} {sep} "
            f"{mode_color}{mode.upper()}{Colors.RESET} {sep} "
            f"{burnout_color}{momentum_bar}{Colors.RESET} {Colors.DIM}{momentum.upper().replace('_', ' ')}{Colors.RESET} {sep} "
            f"{Colors.GRAY}{alt_short}{Colors.RESET} {sep} "
            f"{Colors.GRAY}{wm}/3{Colors.RESET} {sep} "
            f"{Colors.GRAY}T:{tangent}{Colors.RESET} {sep} "
            f"{Colors.GRAY}{paradigm.upper()}{Colors.RESET}"
        )
    else:
        return f"◈ {burnout} | {mode.upper()} | {momentum_bar} {momentum.upper()} | {alt_short} | {wm}/3 | T:{tangent} | {paradigm.upper()}"


def format_tmux(state: dict) -> str:
    """
    tmux status bar format (no ANSI, uses tmux colors).
    Example: #[fg=green]◈ GREEN#[default] | WORK | ▅
    """
    burnout = state.get("burnout_level", "GREEN")
    mode = state.get("decision_mode", "work")
    momentum = state.get("momentum_phase", "rolling")

    tmux_colors = {
        "GREEN": "green",
        "YELLOW": "yellow",
        "ORANGE": "colour208",
        "RED": "red"
    }

    mode_colors = {
        "work": "green",
        "delegate": "blue",
        "protect": "magenta"
    }

    bc = tmux_colors.get(burnout, "green")
    mc = mode_colors.get(mode, "green")
    momentum_bar = MOMENTUM_BARS.get(momentum, "▅")

    return f"#[fg={bc}]◈ {burnout}#[default] │ #[fg={mc}]{mode.upper()}#[default] │ #[fg={bc}]{momentum_bar}#[default]"


def format_json(state: dict) -> str:
    """JSON output for scripting."""
    return json.dumps(state, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Orchestra cognitive state for terminal integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  orchestra-status              # Full colored status
  orchestra-status --short      # Minimal (just icon)
  orchestra-status --prompt     # For shell prompts
  orchestra-status --tmux       # For tmux status bar
  orchestra-status --no-color   # Without ANSI colors
  orchestra-status --json       # JSON output

Shell Integration:
  # Bash/Zsh - add to ~/.bashrc or ~/.zshrc:
  export PS1='$(orchestra-status --short) \\$ '

  # Or with full prompt:
  export PS1='$(orchestra-status --prompt)\\n\\$ '

tmux Integration:
  # Add to ~/.tmux.conf:
  set -g status-right '#(orchestra-status --tmux)'
        """
    )

    parser.add_argument("--short", action="store_true", help="Minimal output (icon only)")
    parser.add_argument("--prompt", action="store_true", help="Prompt-friendly format")
    parser.add_argument("--tmux", action="store_true", help="tmux status bar format")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")

    args = parser.parse_args()

    state = read_state()
    use_color = not args.no_color and sys.stdout.isatty()

    if args.json:
        print(format_json(state))
    elif args.tmux:
        print(format_tmux(state))
    elif args.short:
        print(format_short(state, color=use_color))
    elif args.prompt:
        print(format_prompt(state, color=use_color))
    else:
        print(format_full(state, color=use_color))


if __name__ == "__main__":
    main()
