"""
Recover Skill (/recover)
========================

Recovery menu for when overwhelmed or burned out.

Offers options based on current state:
1. Done for today (save state, stop)
2. Switch to easy wins (low-effort tasks)
3. Talk it out (no code, just discussion)
4. 15-minute break (pause and reassess)
5. Scope cut (reduce requirements)

This skill is proactively suggested when burnout reaches ORANGE/RED.
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add Orchestra to path if needed
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import create_cognitive_stage
from otto.cognitive_support import RECOVERY_OPTIONS, RecoveryOption


# =============================================================================
# Skill Definition
# =============================================================================

RECOVER_SKILL_DEFINITION = {
    "name": "recover",
    "description": "Recovery menu when overwhelmed - offers options for rest, easy wins, or scope reduction",
    "triggers": ["/recover", "/recovery", "I need a break", "I'm overwhelmed", "help me recover"],
    "questions": [
        {
            "question": "What would help right now?",
            "header": "Recovery",
            "multiSelect": False,
            "options": [
                {
                    "label": "Done for today",
                    "description": "Save state and stop. Tomorrow is fine."
                },
                {
                    "label": "Easy wins only",
                    "description": "Switch to low-effort, high-dopamine tasks."
                },
                {
                    "label": "Talk it out",
                    "description": "No code - just discussion and clarification."
                },
                {
                    "label": "15-minute break",
                    "description": "Step away, then reassess energy."
                },
                {
                    "label": "Scope cut",
                    "description": "Reduce requirements to minimum viable."
                }
            ]
        }
    ]
}


# =============================================================================
# Skill Implementation
# =============================================================================

def recover_skill(choice: str = None) -> str:
    """
    Show recovery menu or apply chosen recovery option.

    Args:
        choice: Selected recovery option (if provided)

    Returns:
        Formatted response string
    """
    stage = create_cognitive_stage()
    state = stage.get_cognitive_state()

    if not choice:
        # Show the recovery menu
        return _format_recovery_menu(state)

    # Apply the chosen recovery option
    return _apply_recovery_option(choice, stage)


def _format_recovery_menu(state) -> str:
    """Format the recovery menu."""
    lines = [
        "```",
        "╔══════════════════════════════════════════════════╗",
        "║               RECOVERY OPTIONS                   ║",
        "╚══════════════════════════════════════════════════╝",
        "```",
        "",
        "You're running on empty. **No judgment.** What would help right now?",
        "",
    ]

    # Add current state context
    lines.extend([
        f"**Current state:**",
        f"- Burnout: {state.burnout_level.value.upper()}",
        f"- Energy: {state.energy_level.value}",
        f"- Momentum: {state.momentum_phase.value}",
        "",
    ])

    # Add options
    for i, (option, info) in enumerate(RECOVERY_OPTIONS.items(), 1):
        lines.append(f"**{i}. {info['label']}**")
        lines.append(f"   {info['description']}")
        lines.append("")

    lines.append("Choose what feels right. There's no wrong answer.")

    return "\n".join(lines)


def _apply_recovery_option(choice: str, stage) -> str:
    """Apply the selected recovery option."""
    state = stage.get_cognitive_state()

    # Map choice to option
    choice_lower = choice.lower()

    if "done" in choice_lower or "today" in choice_lower:
        return _apply_done_for_today(stage)

    elif "easy" in choice_lower or "win" in choice_lower:
        return _apply_easy_wins(stage)

    elif "talk" in choice_lower or "discuss" in choice_lower:
        return _apply_talk_it_out(stage)

    elif "break" in choice_lower or "15" in choice_lower:
        return _apply_short_break(stage)

    elif "scope" in choice_lower or "cut" in choice_lower:
        return _apply_scope_cut(stage)

    else:
        return f"I didn't recognize that option. Please choose from the recovery menu."


def _apply_done_for_today(stage) -> str:
    """Apply 'Done for today' recovery option."""
    state = stage.get_cognitive_state()

    # Set recovery mode
    stage.set_mode("recovery")
    stage.set_session_value("burnout_level", "orange")  # Acknowledge but don't worsen

    # Save state
    stage.save()

    return """**Done for today.** Good choice.

Your session state has been saved. When you come back:
- We'll remember where you left off
- We'll start fresh with calibration
- No guilt, no pressure

Rest is productive. See you next time."""


def _apply_easy_wins(stage) -> str:
    """Apply 'Easy wins only' recovery option."""
    # Set recovery mode with easy tasks filter
    stage.set_mode("recovery")
    stage.set_session_value("task_filter", "easy_only")

    # Lower burnout slightly (easy wins help)
    state = stage.get_cognitive_state()
    if state.burnout_level.value in ("red", "orange"):
        state.recover_burnout()

    stage.save()

    return """**Easy wins mode activated.**

I'll focus on:
- Quick, completable tasks
- Low cognitive load
- High-dopamine completions

What's something small you could finish right now?
Even a tiny win helps rebuild momentum."""


def _apply_talk_it_out(stage) -> str:
    """Apply 'Talk it out' recovery option."""
    # Set teaching/discussion mode
    stage.set_mode("teaching")
    stage.set_session_value("code_generation", "disabled")

    stage.save()

    return """**Talk it out mode.**

No code, no implementation - just conversation.

What's on your mind? We can:
- Clarify what you're trying to build
- Work through a tricky concept
- Figure out what's actually blocking you
- Or just decompress

No pressure to produce anything."""


def _apply_short_break(stage) -> str:
    """Apply '15-minute break' recovery option."""
    stage.set_session_value("break_scheduled", True)

    # Reset rapid exchange counter (body check)
    state = stage.get_cognitive_state()
    state.reset_rapid_exchanges()

    stage.save()

    return """**15-minute break scheduled.**

Step away from the screen. Seriously.

Suggestions:
- Get some water
- Move your body (stretch, walk)
- Look at something far away
- Use the bathroom if needed

When you come back, we'll check in on energy and continue.

I'll be here. Take your time."""


def _apply_scope_cut(stage) -> str:
    """Apply 'Scope cut' recovery option."""
    stage.set_session_value("scope_mode", "minimal")
    stage.set_mode("focused")  # Focused on reduced scope

    stage.save()

    return """**Scope cut mode.**

Let's reduce to minimum viable.

Current approach:
- Cut all nice-to-haves
- Focus on one core feature
- Ship working over complete
- Polish later (or never)

What's the absolute minimum that would be useful?
What can we cut entirely?

Shipping beats perfect. Always."""


def acknowledge_break_return() -> str:
    """Handle return from break."""
    stage = create_cognitive_stage()
    stage.set_session_value("break_scheduled", False)

    # Recover one level of burnout
    state = stage.get_cognitive_state()
    state.recover_burnout()

    stage.save()

    return """Welcome back.

How are you feeling?
- Better → Let's continue with something manageable
- Same → Maybe switch to easy wins?
- Worse → Consider calling it for today

No pressure. What feels right?"""


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    """Run recover skill from command line."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Orchestra Recover Skill")
    parser.add_argument("--choice", type=str,
                        help="Recovery option to apply")
    parser.add_argument("--return", dest="returning", action="store_true",
                        help="Returning from break")
    parser.add_argument("--json", action="store_true",
                        help="Output skill definition as JSON")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(RECOVER_SKILL_DEFINITION, indent=2))
    elif args.returning:
        print(acknowledge_break_return())
    elif args.choice:
        print(recover_skill(args.choice))
    else:
        print(recover_skill())
