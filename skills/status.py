"""
Status Skill (/status)
======================

Display cognitive state dashboard.

Shows current:
- Burnout level (GREEN/YELLOW/ORANGE/RED)
- Momentum phase (cold_start/building/rolling/peak/crashed)
- Energy level
- Cognitive mode
- Session stats (exchanges, tasks completed)
- Epistemic tension
- Working memory usage
"""

import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Add Orchestra to path if needed
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import create_cognitive_stage
from otto.cognitive_support import CognitiveSupportManager


# =============================================================================
# Skill Definition
# =============================================================================

STATUS_SKILL_DEFINITION = {
    "name": "status",
    "description": "Show cognitive state dashboard - burnout, momentum, energy, and session stats",
    "triggers": ["/status", "/dashboard", "show status", "cognitive status"],
    "questions": []  # No questions needed
}


# =============================================================================
# Skill Implementation
# =============================================================================

def status_skill(verbose: bool = False) -> str:
    """
    Show cognitive state dashboard.

    Args:
        verbose: If True, show detailed breakdown

    Returns:
        Formatted dashboard string
    """
    stage = create_cognitive_stage()
    state = stage.get_cognitive_state()
    support = CognitiveSupportManager()

    # Calculate session duration
    start_time = datetime.fromtimestamp(state.session_start)
    duration_minutes = (datetime.now() - start_time).total_seconds() / 60

    # Get cognitive check
    check = support.check(state)

    # Build dashboard
    return _format_dashboard(stage, state, check, duration_minutes, verbose)


def _format_dashboard(stage, state, check, duration_minutes: float,
                      verbose: bool = False) -> str:
    """Format the cognitive state dashboard."""

    # Burnout indicator with color
    burnout_indicators = {
        "green": "🟢 GREEN",
        "yellow": "🟡 YELLOW",
        "orange": "🟠 ORANGE",
        "red": "🔴 RED",
    }
    burnout_display = burnout_indicators.get(state.burnout_level.value, state.burnout_level.value)

    # Momentum indicator
    momentum_indicators = {
        "cold_start": "⬜ Cold Start",
        "building": "🔥 Building",
        "rolling": "🚀 Rolling",
        "peak": "⚡ Peak",
        "crashed": "💔 Crashed",
    }
    momentum_display = momentum_indicators.get(state.momentum_phase.value, state.momentum_phase.value)

    # Energy indicator
    energy_indicators = {
        "high": "⚡ High",
        "medium": "🔋 Medium",
        "low": "🪫 Low",
        "depleted": "❌ Depleted",
    }
    energy_display = energy_indicators.get(state.energy_level.value, state.energy_level.value)

    # Mode indicator
    mode_indicators = {
        "focused": "🎯 Focused",
        "exploring": "🔍 Exploring",
        "teaching": "📚 Teaching",
        "recovery": "🧘 Recovery",
    }
    mode_display = mode_indicators.get(state.mode.value, state.mode.value)

    # Tension bar
    tension = state.epistemic_tension
    tension_bar = _make_bar(tension, 10, "▓", "░")

    # Progress bar for tasks (approximate)
    # Note: We don't have a total task count, so show raw number
    tasks_display = f"{state.tasks_completed} completed"

    # Build output
    lines = [
        "```",
        "╔══════════════════════════════════════════════════╗",
        "║            COGNITIVE STATE DASHBOARD             ║",
        "╠══════════════════════════════════════════════════╣",
        f"║  Burnout:    {burnout_display:<35}║",
        f"║  Momentum:   {momentum_display:<35}║",
        f"║  Energy:     {energy_display:<35}║",
        f"║  Mode:       {mode_display:<35}║",
        "╠══════════════════════════════════════════════════╣",
        f"║  Session:    {duration_minutes:.0f} min | {state.exchange_count} exchanges{' ' * (21 - len(str(state.exchange_count)))}║",
        f"║  Tasks:      {tasks_display:<35}║",
        f"║  Tangents:   {state.tangent_budget} remaining{' ' * 26}║",
        "╠══════════════════════════════════════════════════╣",
        f"║  Epistemic Tension: [{tension_bar}] {tension:.2f}{' ' * 10}║",
        f"║  Attractor: {state.convergence_attractor:<36}║",
        "╚══════════════════════════════════════════════════╝",
        "```",
    ]

    if verbose:
        lines.extend([
            "",
            "**Detailed State:**",
            f"- Focus calibration: {state.focus_level}",
            f"- Urgency: {state.urgency}",
            f"- Altitude: {state.altitude.value}ft",
            f"- Rapid exchanges: {state.rapid_exchange_count}",
            f"- Stable exchanges: {state.stable_exchanges}",
            f"- Using pxr: {stage.using_pxr}",
            f"- Checksum: {stage.checksum()}",
        ])

        if check.should_chunk:
            lines.append(f"- Should chunk tasks (>{check.chunk_size} items)")
        if check.body_check_needed:
            lines.append("- ⚠️ Body check recommended")
        if check.recovery_needed:
            lines.append("- ⚠️ Recovery recommended")

    # Add recommendations
    recommendations = _get_recommendations(state, check)
    if recommendations:
        lines.append("")
        lines.append("**Recommendations:**")
        for rec in recommendations:
            lines.append(f"- {rec}")

    return "\n".join(lines)


def _make_bar(value: float, width: int, filled: str = "█", empty: str = "░") -> str:
    """Make a progress bar."""
    filled_count = int(value * width)
    empty_count = width - filled_count
    return filled * filled_count + empty * empty_count


def _get_recommendations(state, check) -> list:
    """Get recommendations based on current state."""
    recs = []

    if state.burnout_level.value == "yellow":
        recs.append("Consider a short break soon")
    elif state.burnout_level.value == "orange":
        recs.append("What's the blocker? Maybe time to step back")
    elif state.burnout_level.value == "red":
        recs.append("Full stop recommended - try /recover")

    if state.energy_level.value == "depleted":
        recs.append("Energy depleted - switch to easy wins or rest")
    elif state.energy_level.value == "low":
        recs.append("Low energy - simpler tasks recommended")

    if state.momentum_phase.value == "crashed":
        recs.append("Momentum crashed - start with a tiny win to rebuild")
    elif state.momentum_phase.value == "peak":
        recs.append("Peak momentum - protect this state, keep going!")

    if check.body_check_needed:
        recs.append("Quick body check: Water? Stretch? Bathroom?")

    if state.tangent_budget <= 1:
        recs.append("Low tangent budget - stay focused on main goal")

    return recs


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    """Run status skill from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Orchestra Status Skill")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed state")
    args = parser.parse_args()

    print(status_skill(verbose=args.verbose))
