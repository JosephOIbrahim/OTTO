"""
Calibrate Skill (/calibrate)
============================

Re-calibrate cognitive state through non-invasive questions.

This skill asks 2-3 quick questions to adjust:
- Focus level (scattered/moderate/locked_in)
- Urgency (relaxed/moderate/deadline)
- Energy (high/medium/low/depleted)

Calibration affects how Orchestra adapts its behavior:
- Scattered focus → more scaffolding, slower pace
- High urgency → less interruption
- Low energy → simpler tasks, recovery suggestions
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add Orchestra to path if needed
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import create_cognitive_stage


# =============================================================================
# Skill Definition (for Claude Code registration)
# =============================================================================

CALIBRATE_SKILL_DEFINITION = {
    "name": "calibrate",
    "description": "Quick calibration - assess focus, urgency, and energy to adapt pacing",
    "triggers": ["/calibrate", "calibrate", "recalibrate"],
    "questions": [
        {
            "question": "How's your focus right now?",
            "header": "Focus",
            "multiSelect": False,
            "options": [
                {"label": "Scattered", "description": "Jumping between things, hard to settle"},
                {"label": "Moderate (Recommended)", "description": "Normal focus, can work steadily"},
                {"label": "Locked in", "description": "Deep focus, in the zone"},
            ]
        },
        {
            "question": "What's the time pressure?",
            "header": "Urgency",
            "multiSelect": False,
            "options": [
                {"label": "Relaxed", "description": "No deadline, exploration OK"},
                {"label": "Moderate (Recommended)", "description": "Reasonable timeline"},
                {"label": "Deadline", "description": "Time-sensitive, need to ship"},
            ]
        },
        {
            "question": "Energy level?",
            "header": "Energy",
            "multiSelect": False,
            "options": [
                {"label": "High", "description": "Feeling sharp and ready"},
                {"label": "Medium (Recommended)", "description": "Normal capacity"},
                {"label": "Low", "description": "Bit tired but can work"},
                {"label": "Depleted", "description": "Running on empty"},
            ]
        }
    ]
}


# =============================================================================
# Skill Implementation
# =============================================================================

def calibrate_skill(answers: Dict[str, str] = None) -> str:
    """
    Run calibration skill.

    Args:
        answers: Dict mapping question headers to selected option labels
                 e.g., {"Focus": "Scattered", "Urgency": "Deadline", "Energy": "Low"}

    Returns:
        Formatted response string
    """
    stage = create_cognitive_stage()

    if not answers:
        # Return questions prompt
        return _format_calibration_prompt()

    # Map answers to values
    focus_map = {
        "Scattered": "scattered",
        "Moderate": "moderate",
        "Moderate (Recommended)": "moderate",
        "Locked in": "locked_in",
    }

    urgency_map = {
        "Relaxed": "relaxed",
        "Moderate": "moderate",
        "Moderate (Recommended)": "moderate",
        "Deadline": "deadline",
    }

    energy_map = {
        "High": "high",
        "Medium": "medium",
        "Medium (Recommended)": "medium",
        "Low": "low",
        "Depleted": "depleted",
    }

    # Extract and map values
    focus = focus_map.get(answers.get("Focus", ""), "moderate")
    urgency = urgency_map.get(answers.get("Urgency", ""), "moderate")
    energy = energy_map.get(answers.get("Energy", ""), "medium")

    # Apply calibration
    stage.calibrate(
        focus_level=focus,
        urgency=urgency,
        energy_estimate=energy,
    )

    # Generate response based on calibration
    return _format_calibration_response(focus, urgency, energy)


def _format_calibration_prompt() -> str:
    """Format the calibration questions prompt."""
    return """Let me quickly calibrate to your current state.

I'll ask 3 quick questions about focus, urgency, and energy.
This helps me adapt my pacing and level of scaffolding."""


def _format_calibration_response(focus: str, urgency: str, energy: str) -> str:
    """Format the calibration result response."""
    lines = ["Calibration complete."]

    # Add behavior adjustments based on calibration
    adjustments = []

    if focus == "scattered":
        adjustments.append("More scaffolding, slower pace")
        adjustments.append("Fewer options presented at once")
        adjustments.append("Confirming each step before proceeding")
    elif focus == "locked_in":
        adjustments.append("Minimal interruption, stay out of your way")
        adjustments.append("Trusting your flow state")

    if urgency == "deadline":
        adjustments.append("Prioritizing shipping over polish")
        adjustments.append("Less exploration, more direct execution")
    elif urgency == "relaxed":
        adjustments.append("Room for exploration and tangents")

    if energy == "low":
        adjustments.append("Suggesting easier tasks first")
        adjustments.append("Watching for fatigue signals")
    elif energy == "depleted":
        adjustments.append("Recovery mode - easy wins only")
        adjustments.append("Recommending breaks")

    if adjustments:
        lines.append("\n**Adjustments:**")
        for adj in adjustments:
            lines.append(f"- {adj}")

    # Show current state summary
    lines.append(f"\n**Current calibration:**")
    lines.append(f"- Focus: {focus}")
    lines.append(f"- Urgency: {urgency}")
    lines.append(f"- Energy: {energy}")

    return "\n".join(lines)


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    """Run calibrate skill from command line."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Orchestra Calibrate Skill")
    parser.add_argument("--focus", choices=["scattered", "moderate", "locked_in"],
                        help="Focus level")
    parser.add_argument("--urgency", choices=["relaxed", "moderate", "deadline"],
                        help="Urgency level")
    parser.add_argument("--energy", choices=["high", "medium", "low", "depleted"],
                        help="Energy level")
    parser.add_argument("--json", action="store_true",
                        help="Output skill definition as JSON")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(CALIBRATE_SKILL_DEFINITION, indent=2))
    elif args.focus or args.urgency or args.energy:
        answers = {}
        if args.focus:
            answers["Focus"] = args.focus.replace("_", " ").title()
        if args.urgency:
            answers["Urgency"] = args.urgency.title()
        if args.energy:
            answers["Energy"] = args.energy.title()

        print(calibrate_skill(answers))
    else:
        print(calibrate_skill())
