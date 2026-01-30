"""
Tension Skill (/tension)
========================

Surface any pending cognitive tensions.

Tensions are points where the model is uncertain or where
multiple valid approaches exist. Instead of auto-resolving,
we surface these for user decision.

Types of tension:
- Attribute conflicts (layers disagree)
- Mode mismatches (signals vs current mode)
- Safety tensions (requests vs constraints)
- Epistemic uncertainty (high xi value)
- Approach choices (multiple valid paths)
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

# Add Orchestra to path if needed
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import create_cognitive_stage
from otto.tension_surfacer import create_tension_surfacer, TensionReport
from otto.prism_detector import create_detector


# =============================================================================
# Skill Definition
# =============================================================================

TENSION_SKILL_DEFINITION = {
    "name": "tension",
    "description": "Surface any pending cognitive tensions for resolution",
    "triggers": ["/tension", "/tensions", "show tensions", "what's conflicting"],
    "questions": []  # No questions needed
}


# =============================================================================
# Skill Implementation
# =============================================================================

def tension_skill(recent_message: str = "") -> str:
    """
    Surface pending tensions.

    Args:
        recent_message: Optional recent user message for context

    Returns:
        Formatted tensions string
    """
    stage = create_cognitive_stage()

    # Detect current signals if message provided
    signals = None
    if recent_message:
        detector = create_detector()
        signals = detector.detect(recent_message)

    # Get tension report
    surfacer = create_tension_surfacer(stage)
    report = surfacer.detect(signals, recent_message)

    return _format_tension_report(report, stage)


def _format_tension_report(report: TensionReport, stage) -> str:
    """Format tension report for display."""
    lines = []

    if not report.has_tensions():
        lines.extend([
            "**No tensions detected.**",
            "",
            "Current state is coherent. No conflicts or uncertainties requiring attention.",
            "",
            f"Epistemic tension: {stage.get_resolved('epistemic_tension') or 0:.2f}",
        ])
        return "\n".join(lines)

    # Header
    lines.extend([
        "```",
        "╔══════════════════════════════════════════════════╗",
        "║               TENSIONS DETECTED                  ║",
        f"║           Total Score: {report.total_tension_score:.2f}                       ║",
        "╚══════════════════════════════════════════════════╝",
        "```",
        "",
    ])

    # Critical tensions first
    critical = report.get_critical_tensions()
    if critical:
        lines.append("### 🚨 CRITICAL (Requires Attention)")
        lines.append("")
        for tension in critical:
            lines.extend(_format_single_tension(tension))
            lines.append("")

    # Other surfaceable tensions
    surfaceable = [t for t in report.get_surfaceable_tensions()
                   if t not in critical]
    if surfaceable:
        lines.append("### ⚠️ Pending Tensions")
        lines.append("")
        for tension in surfaceable:
            lines.extend(_format_single_tension(tension))
            lines.append("")

    # Auto-resolved (informational)
    if report.auto_resolved:
        lines.append("### ✓ Auto-Resolved (Low Priority)")
        lines.append("")
        for tension in report.auto_resolved:
            lines.append(f"- {tension.description} → resolved via LIVRPS")

    return "\n".join(lines)


def _format_single_tension(tension) -> List[str]:
    """Format a single tension for display."""
    lines = []

    # Severity badge
    severity_badges = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }
    badge = severity_badges.get(tension.severity.value, "⚪")

    lines.append(f"**{badge} {tension.description}**")

    # Type
    lines.append(f"Type: `{tension.tension_type.value}`")

    # Conflicting opinions
    if tension.opinions:
        lines.append("Opinions:")
        for layer, value in tension.opinions:
            lines.append(f"  - {layer}: `{value}`")

    # Options
    if tension.options:
        lines.append("Options:")
        for i, opt in enumerate(tension.options, 1):
            label = opt.get("label", f"Option {i}")
            desc = opt.get("description", "")
            lines.append(f"  {i}. **{label}**: {desc}")

    # Current vs recommended
    if tension.current_value and tension.recommended_value:
        lines.append(f"Current: `{tension.current_value}` → Recommended: `{tension.recommended_value}`")

    return lines


def resolve_tension(tension_index: int, choice: int) -> str:
    """
    Resolve a specific tension with user choice.

    Args:
        tension_index: Which tension (0-indexed)
        choice: Which option chosen (1-indexed)

    Returns:
        Confirmation message
    """
    stage = create_cognitive_stage()
    surfacer = create_tension_surfacer(stage)
    report = surfacer.detect()

    if tension_index >= len(report.tensions):
        return "Invalid tension index"

    tension = report.tensions[tension_index]

    if choice > len(tension.options):
        return "Invalid choice"

    option = tension.options[choice - 1]
    action = option.get("action", "")

    # Apply the action
    if action.startswith("set_mode:"):
        mode = action.split(":")[1]
        stage.set_mode(mode)
        stage.save()
        return f"Mode set to {mode}"

    elif action == "enter_recovery":
        stage.set_mode("recovery")
        stage.save()
        return "Entered recovery mode"

    elif action == "calibrate":
        return "Please run /calibrate to improve state prediction"

    else:
        return f"Choice acknowledged: {option.get('label', 'Unknown')}"


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    """Run tension skill from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Orchestra Tension Skill")
    parser.add_argument("--message", "-m", type=str, default="",
                        help="Recent user message for context")
    parser.add_argument("--resolve", type=int, nargs=2,
                        metavar=("TENSION_INDEX", "CHOICE"),
                        help="Resolve tension N with choice M")
    args = parser.parse_args()

    if args.resolve:
        print(resolve_tension(args.resolve[0], args.resolve[1]))
    else:
        print(tension_skill(args.message))
