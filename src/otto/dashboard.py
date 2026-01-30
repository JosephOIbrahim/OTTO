"""
Orchestra Dashboard Module
==========================

Provides a CLI dashboard for viewing and managing cognitive state.

Features:
- View current cognitive state (burnout, momentum, energy, mode)
- Toggle cognitive safety mode on/off
- View PRISM signal analysis
- Progress visualization
- Recovery menu access

Usage:
    python -m orchestra.dashboard status
    python -m orchestra.dashboard cognitive-safety on
    python -m orchestra.dashboard cognitive-safety off
    python -m orchestra.dashboard reset
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .cognitive_state import (
    CognitiveStateManager, CognitiveState,
    BurnoutLevel, MomentumPhase, EnergyLevel, CognitiveMode
)
from .adhd_support import (
    CognitiveSafetyManager, RECOVERY_OPTIONS, RecoveryOption,
    # Backward compatibility alias
    ADHDSupportManager
)
from .agent_coordinator import AgentCoordinator, DecisionMode


# =============================================================================
# Display Constants
# =============================================================================

# ANSI color codes (for terminal display)
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "orange": "\033[38;5;208m",
    "red": "\033[91m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "gray": "\033[90m"
}

# Burnout color mapping
BURNOUT_COLORS = {
    BurnoutLevel.GREEN: "green",
    BurnoutLevel.YELLOW: "yellow",
    BurnoutLevel.ORANGE: "orange",
    BurnoutLevel.RED: "red"
}

# Decision mode color mapping (v4.3.0)
DECISION_MODE_COLORS = {
    DecisionMode.WORK: "green",      # Direct action - productive
    DecisionMode.DELEGATE: "blue",   # Spawning agents - parallel
    DecisionMode.PROTECT: "yellow"   # Flow protection - mindful
}

# Progress bar characters
PROGRESS_FILLED = "#"
PROGRESS_EMPTY = "-"


# =============================================================================
# Dashboard Class
# =============================================================================

class Dashboard:
    """CLI dashboard for Orchestra cognitive state management."""

    def __init__(self, state_dir: Path = None):
        """
        Initialize dashboard.

        Args:
            state_dir: Directory containing state files
        """
        self.state_dir = state_dir or (Path.home() / "Orchestra" / "state")
        self.state_manager = CognitiveStateManager(state_dir=self.state_dir)
        self.use_colors = sys.stdout.isatty()

        # Decision engine coordinator (v4.3.0)
        self.coordinator = AgentCoordinator(
            cognitive_stage=self.state_manager,
            state_dir=self.state_dir
        )

    def _color(self, text: str, color: str) -> str:
        """Apply color to text if terminal supports it."""
        if self.use_colors and color in COLORS:
            return f"{COLORS[color]}{text}{COLORS['reset']}"
        return text

    def _progress_bar(self, value: float, width: int = 20) -> str:
        """Generate progress bar string."""
        filled = int(value * width)
        empty = width - filled
        return f"[{PROGRESS_FILLED * filled}{PROGRESS_EMPTY * empty}]"

    def _format_burnout(self, level: BurnoutLevel) -> str:
        """Format burnout level with color."""
        color = BURNOUT_COLORS.get(level, "reset")
        return self._color(level.value.upper(), color)

    def _format_decision_mode(self, mode: DecisionMode) -> str:
        """Format decision mode with color."""
        color = DECISION_MODE_COLORS.get(mode, "reset")
        return self._color(mode.value.upper(), color)

    def _format_time_ago(self, timestamp: float) -> str:
        """Format timestamp as 'X ago'."""
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

    def status(self) -> None:
        """Display current cognitive state."""
        state = self.state_manager.get_state()

        # Header
        print()
        print(self._color("=" * 60, "cyan"))
        print(self._color("  ORCHESTRA COGNITIVE STATE DASHBOARD", "bold"))
        print(self._color("=" * 60, "cyan"))
        print()

        # Core state
        print(self._color("COGNITIVE STATE", "bold"))
        print("-" * 40)
        print(f"  Burnout:   {self._format_burnout(state.burnout_level)}")
        print(f"  Momentum:  {self._color(state.momentum_phase.value, 'blue')}")
        print(f"  Energy:    {self._color(state.energy_level.value, 'green' if state.energy_level == EnergyLevel.HIGH else 'yellow')}")
        print(f"  Mode:      {self._color(state.mode.value, 'cyan')}")
        print(f"  Altitude:  {state.altitude.value}ft")
        print()

        # Cognitive support (always active)
        focus_color = {"scattered": "yellow", "moderate": "blue", "locked_in": "green"}.get(state.focus_level, "blue")
        urgency_color = {"relaxed": "green", "moderate": "blue", "deadline": "red"}.get(state.urgency, "blue")
        print(self._color("COGNITIVE SUPPORT (Always Active)", "bold"))
        print("-" * 40)
        print(f"  Focus level:      {self._color(state.focus_level, focus_color)}")
        print(f"  Urgency:          {self._color(state.urgency, urgency_color)}")
        print(f"  Tangents left:    {state.tangent_budget}/5")
        print(f"  Rapid exchanges:  {state.rapid_exchange_count}")
        if state.rapid_exchange_count >= 15:
            print(f"  {self._color('Body check recommended!', 'yellow')}")
        print()

        # Session stats
        print(self._color("SESSION STATS", "bold"))
        print("-" * 40)
        print(f"  Exchanges:        {state.exchange_count}")
        print(f"  Tasks completed:  {state.tasks_completed}")
        print(f"  Session started:  {self._format_time_ago(state.session_start)}")
        print(f"  Last activity:    {self._format_time_ago(state.last_activity)}")
        print()

        # Convergence
        print(self._color("CONVERGENCE (RC^+xi)", "bold"))
        print("-" * 40)
        tension_bar = self._progress_bar(state.epistemic_tension)
        converged = self._color("CONVERGED", "green") if state.is_converged() else self._color("not converged", "gray")
        print(f"  Attractor:        {state.convergence_attractor}")
        print(f"  Tension:          {tension_bar} {state.epistemic_tension:.2f}")
        print(f"  Stable exchanges: {state.stable_exchanges}")
        print(f"  Status:           {converged}")
        print()

        # Decision Engine State (v4.3.0)
        coordinator_status = self.coordinator.get_status()
        print(self._color("DECISION ENGINE (v4.3.0)", "bold"))
        print("-" * 40)
        budget_bar = self._progress_bar(coordinator_status["cognitive_budget"])
        can_spawn = self._color("YES", "green") if coordinator_status["can_spawn"] else self._color("NO", "red")
        flow_prot = self._color("ACTIVE", "yellow") if coordinator_status["flow_protection"] else self._color("inactive", "gray")
        print(f"  Cognitive budget: {budget_bar} {coordinator_status['cognitive_budget']:.2f}")
        print(f"  Can spawn agents: {can_spawn}")
        print(f"  Active agents:    {coordinator_status['active_agents']}")
        print(f"  Queued results:   {coordinator_status['queued_results']}")
        print(f"  Flow protection:  {flow_prot}")
        print(f"  Decisions made:   {coordinator_status['decisions_made']}")
        print()

        # Footer
        print(self._color("=" * 60, "cyan"))
        print(f"  State file: {self.state_manager.state_file}")
        print(f"  Checksum:   {state.checksum()}")
        print(self._color("=" * 60, "cyan"))
        print()

    def calibrate(self, focus_level: str = None, urgency: str = None) -> None:
        """
        Calibrate cognitive state.

        Per GUIDING_PRINCIPLES.md Principle 2: Non-Invasive Calibration
        """
        state = self.state_manager.get_state()

        if focus_level:
            if focus_level not in ("scattered", "moderate", "locked_in"):
                print(f"Invalid focus level: {focus_level}")
                print("Valid options: scattered, moderate, locked_in")
                return
            state.focus_level = focus_level

        if urgency:
            if urgency not in ("relaxed", "moderate", "deadline"):
                print(f"Invalid urgency: {urgency}")
                print("Valid options: relaxed, moderate, deadline")
                return
            state.urgency = urgency

        self.state_manager.save()

        print(self._color("Calibration Updated", "green"))
        print()
        print(f"  Focus level: {self._color(state.focus_level, 'cyan')}")
        print(f"  Urgency:     {self._color(state.urgency, 'cyan')}")
        print()
        print("Behavior adapts to your state:")
        if state.focus_level == "scattered":
            print("  - More scaffolding, slower pace")
            print("  - Fewer options, more structure")
            print("  - Higher threshold for interruptions")
        elif state.focus_level == "locked_in":
            print("  - Minimal interruption")
            print("  - Trust the flow")
            print("  - Lower threshold for surfacing tensions")

    def reset(self, confirm: bool = False) -> None:
        """Reset cognitive state to defaults."""
        if not confirm:
            print("This will reset all cognitive state to defaults.")
            response = input("Are you sure? (yes/no): ").strip().lower()
            if response != "yes":
                print("Reset cancelled.")
                return

        self.state_manager.reset()
        print(self._color("Cognitive state reset to defaults.", "green"))

    def recovery_menu(self) -> None:
        """Show recovery menu (for RED burnout)."""
        state = self.state_manager.get_state()

        if state.burnout_level != BurnoutLevel.RED:
            print(f"Recovery menu is for RED burnout state.")
            print(f"Current burnout level: {self._format_burnout(state.burnout_level)}")
            return

        print()
        print(self._color("=" * 60, "red"))
        print(self._color("  RECOVERY OPTIONS", "bold"))
        print(self._color("=" * 60, "red"))
        print()
        print(self._color("You're in RED burnout. No judgment. Let's figure out what helps.", "yellow"))
        print()

        for i, (opt, info) in enumerate(RECOVERY_OPTIONS.items(), 1):
            print(f"  {i}. {self._color(info['label'], 'cyan')}")
            print(f"     {info['description']}")
            print()

        print(self._color("-" * 60, "red"))
        print()

    def show_signals(self, text: str = None) -> None:
        """Show PRISM signal analysis for text."""
        from .prism_detector import PRISMDetector

        if not text:
            text = input("Enter text to analyze: ")

        detector = PRISMDetector()
        signals = detector.detect(text)

        print()
        print(self._color("PRISM SIGNAL ANALYSIS", "bold"))
        print("-" * 40)
        print(f"Input: {text[:60]}...")
        print()

        # Emotional signals
        if signals.emotional:
            print(self._color("Emotional:", "yellow"))
            for signal, score in signals.emotional.items():
                bar = self._progress_bar(score, 10)
                print(f"  {signal}: {bar} {score:.2f}")
            print(f"  Overall score: {signals.emotional_score:.2f}")
            print()

        # Mode signals
        if signals.mode:
            print(self._color("Mode:", "blue"))
            for signal, score in signals.mode.items():
                bar = self._progress_bar(score, 10)
                print(f"  {signal}: {bar} {score:.2f}")
            print(f"  Detected: {signals.mode_detected}")
            print()

        # Domain signals
        if signals.domain:
            print(self._color("Domain:", "cyan"))
            for signal, score in signals.domain.items():
                bar = self._progress_bar(score, 10)
                print(f"  {signal}: {bar} {score:.2f}")
            print(f"  Primary: {signals.primary_domain}")
            print()

        # Task signals
        if signals.task:
            print(self._color("Task:", "green"))
            for signal, score in signals.task.items():
                bar = self._progress_bar(score, 10)
                print(f"  {signal}: {bar} {score:.2f}")
            print(f"  Primary: {signals.primary_task}")
            print()

        # Priority signal
        priority = signals.get_priority_signal()
        print(self._color("PRIORITY SIGNAL:", "bold"))
        print(f"  Category: {priority[0].name}")
        print(f"  Signal:   {priority[1]}")
        print(f"  Score:    {priority[2]:.2f}")
        print()

        if signals.requires_intervention():
            print(self._color("INTERVENTION REQUIRED", "red"))

    def decisions(self) -> None:
        """Show decision engine status and queued results (v4.3.0)."""
        status = self.coordinator.get_status()

        print()
        print(self._color("=" * 60, "cyan"))
        print(self._color("  DECISION ENGINE STATUS (v4.3.0)", "bold"))
        print(self._color("=" * 60, "cyan"))
        print()

        # Current state
        print(self._color("ROUTING STATE", "bold"))
        print("-" * 40)
        can_spawn = self._color("YES", "green") if status["can_spawn"] else self._color("NO", "red")
        flow_prot = self._color("ACTIVE", "yellow") if status["flow_protection"] else self._color("inactive", "gray")
        budget_bar = self._progress_bar(status["cognitive_budget"])

        print(f"  Cognitive budget: {budget_bar} {status['cognitive_budget']:.2f}")
        print(f"  Can spawn agents: {can_spawn}")
        print(f"  Flow protection:  {flow_prot}")
        print()

        # Active agents
        print(self._color("ACTIVE AGENTS", "bold"))
        print("-" * 40)
        if status["agents"]:
            for agent_id, task in status["agents"].items():
                print(f"  [{agent_id[:8]}] {task[:50]}...")
        else:
            print(f"  {self._color('No active agents', 'gray')}")
        print()

        # Queued results
        print(self._color("QUEUED RESULTS (PROTECT mode)", "bold"))
        print("-" * 40)
        pending = self.coordinator.get_pending_results_for_delivery()
        if pending:
            for result in pending:
                priority_color = "red" if result.priority == 1 else "yellow" if result.priority == 2 else "gray"
                print(f"  [{self._color(f'P{result.priority}', priority_color)}] {result.result_type}: {result.summary[:40]}...")
        else:
            print(f"  {self._color('No queued results', 'gray')}")
        print()

        # Decision history summary
        print(self._color("SESSION SUMMARY", "bold"))
        print("-" * 40)
        print(f"  Decisions made:   {status['decisions_made']}")
        print(f"  Queued results:   {status['queued_results']}")
        print()

        # Routing table info
        print(self._color("ROUTING TABLE", "bold"))
        print("-" * 40)
        print(f"  Mode: {self._color('TABLE-DRIVEN', 'green')} (ThinkingMachines [He2025])")
        print(f"  Deterministic: {self._color('YES', 'green')}")
        print(f"  Decision modes: WORK | DELEGATE | PROTECT")
        print()

        print(self._color("=" * 60, "cyan"))
        print()


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Orchestra Cognitive State Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dashboard status                    Show current cognitive state
  dashboard calibrate scattered       Set focus to scattered
  dashboard calibrate locked_in       Set focus to locked_in
  dashboard calibrate --urgency deadline  Set urgency
  dashboard reset                     Reset state to defaults
  dashboard recovery                  Show recovery menu
  dashboard signals "text"            Analyze text signals
  dashboard decisions                 Show decision engine status (v4.3.0)
        """
    )

    parser.add_argument(
        "command",
        choices=["status", "calibrate", "reset", "recovery", "signals", "decisions"],
        help="Command to execute"
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="Command arguments"
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="State directory path"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    args = parser.parse_args()

    dashboard = Dashboard(state_dir=args.state_dir)
    if args.no_color:
        dashboard.use_colors = False

    if args.command == "status":
        dashboard.status()

    elif args.command == "calibrate":
        if not args.args:
            state = dashboard.state_manager.get_state()
            print(f"Current calibration:")
            print(f"  Focus level: {state.focus_level}")
            print(f"  Urgency: {state.urgency}")
            print()
            print("Usage:")
            print("  calibrate [focus_level]        Set focus (scattered/moderate/locked_in)")
            print("  calibrate --urgency [level]    Set urgency (relaxed/moderate/deadline)")
        elif args.args[0] == "--urgency" and len(args.args) > 1:
            dashboard.calibrate(urgency=args.args[1])
        elif args.args[0] in ("scattered", "moderate", "locked_in"):
            dashboard.calibrate(focus_level=args.args[0])
        else:
            print(f"Unknown argument: {args.args[0]}")
            print("Valid focus levels: scattered, moderate, locked_in")

    elif args.command == "reset":
        confirm = "--confirm" in args.args or "-y" in args.args
        dashboard.reset(confirm=confirm)

    elif args.command == "recovery":
        dashboard.recovery_menu()

    elif args.command == "signals":
        text = " ".join(args.args) if args.args else None
        dashboard.show_signals(text)

    elif args.command == "decisions":
        dashboard.decisions()


if __name__ == "__main__":
    main()


__all__ = ['Dashboard', 'main']
