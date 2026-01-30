"""
Session Start Hook
==================

Initializes Orchestra's cognitive tracking when a Claude Code session starts.

Responsibilities:
1. Load or create cognitive stage (USD-native state)
2. Run non-invasive calibration questions
3. Set initial session state
4. Return cognitive context for prompt injection

Usage in settings.json:
{
    "hooks": {
        "SessionStart": [{
            "type": "command",
            "command": "python -c \"from Orchestra.hooks import on_session_start; print(on_session_start())\""
        }]
    }
}
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Add Orchestra to path if needed
orchestra_path = Path(__file__).parent.parent / "src"
if str(orchestra_path) not in sys.path:
    sys.path.insert(0, str(orchestra_path))

from otto.cognitive_stage import CognitiveStage, create_cognitive_stage
from otto.prism_detector import PRISMDetector, create_detector
from otto.cognitive_support import CognitiveSupportManager

logger = logging.getLogger(__name__)


# =============================================================================
# Calibration Questions (Non-Invasive)
# =============================================================================

CALIBRATION_QUESTIONS = {
    "focus": {
        "question": "How's your focus right now?",
        "header": "Focus",
        "options": [
            {"label": "Scattered", "description": "Jumping between things, hard to settle", "value": "scattered"},
            {"label": "Moderate", "description": "Normal focus, can work steadily", "value": "moderate"},
            {"label": "Locked in", "description": "Deep focus, in the zone", "value": "locked_in"},
        ]
    },
    "urgency": {
        "question": "What's the time pressure?",
        "header": "Urgency",
        "options": [
            {"label": "Relaxed", "description": "No deadline, exploration OK", "value": "relaxed"},
            {"label": "Moderate", "description": "Reasonable timeline", "value": "moderate"},
            {"label": "Deadline", "description": "Time-sensitive, need to ship", "value": "deadline"},
        ]
    },
    "energy": {
        "question": "Energy level?",
        "header": "Energy",
        "options": [
            {"label": "High", "description": "Feeling sharp and ready", "value": "high"},
            {"label": "Medium", "description": "Normal capacity", "value": "medium"},
            {"label": "Low", "description": "Bit tired but can work", "value": "low"},
            {"label": "Depleted", "description": "Running on empty", "value": "depleted"},
        ]
    }
}


@dataclass
class CalibrationResult:
    """Result from calibration questions."""
    focus: str = "moderate"
    urgency: str = "moderate"
    energy: str = "medium"
    skipped: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "focus": self.focus,
            "urgency": self.urgency,
            "energy": self.energy,
            "skipped": self.skipped,
        }


@dataclass
class SessionStartResult:
    """Result from session start hook."""
    cognitive_context: str
    calibration: CalibrationResult
    stage_checksum: str
    using_pxr: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cognitive_context": self.cognitive_context,
            "calibration": self.calibration.to_dict(),
            "stage_checksum": self.stage_checksum,
            "using_pxr": self.using_pxr,
        }


# =============================================================================
# Session Start Hook Implementation
# =============================================================================

def on_session_start(calibration: CalibrationResult = None,
                     skip_calibration: bool = False) -> SessionStartResult:
    """
    Initialize cognitive tracking for a new session.

    This hook:
    1. Creates or loads the cognitive stage (USD-native)
    2. Applies calibration if provided
    3. Returns cognitive context for prompt injection

    Args:
        calibration: Optional pre-filled calibration results
        skip_calibration: If True, use defaults without asking

    Returns:
        SessionStartResult with cognitive context
    """
    # Create/load cognitive stage
    stage = create_cognitive_stage()

    # Apply calibration
    if calibration:
        stage.calibrate(
            focus_level=calibration.focus,
            urgency=calibration.urgency,
            energy_estimate=calibration.energy,
        )
    elif skip_calibration:
        # Use defaults
        calibration = CalibrationResult(skipped=True)
    else:
        # Return questions for user - actual calibration happens after
        calibration = CalibrationResult()  # Defaults until answered

    # Get cognitive context for prompt injection
    context = stage.get_prompt_context()

    # Save initial state
    stage.save()

    result = SessionStartResult(
        cognitive_context=context,
        calibration=calibration,
        stage_checksum=stage.checksum(),
        using_pxr=stage.using_pxr,
    )

    logger.info(f"Session started: checksum={result.stage_checksum}, pxr={result.using_pxr}")
    return result


def run_calibration() -> Dict[str, Any]:
    """
    Get calibration questions for user.

    Returns questions in Claude Code's AskUserQuestion format.
    """
    questions = []

    for key, q in CALIBRATION_QUESTIONS.items():
        questions.append({
            "question": q["question"],
            "header": q["header"],
            "multiSelect": False,
            "options": [
                {"label": opt["label"], "description": opt["description"]}
                for opt in q["options"]
            ]
        })

    return {"questions": questions}


def apply_calibration_answers(answers: Dict[str, str]) -> CalibrationResult:
    """
    Apply calibration answers from user.

    Args:
        answers: Dict mapping question headers to selected option labels

    Returns:
        CalibrationResult with mapped values
    """
    result = CalibrationResult()

    # Map answers to values
    for key, q in CALIBRATION_QUESTIONS.items():
        header = q["header"]
        if header in answers:
            selected_label = answers[header]
            # Find the value for this label
            for opt in q["options"]:
                if opt["label"] == selected_label:
                    setattr(result, key, opt["value"])
                    break

    return result


def get_initial_cognitive_context() -> str:
    """
    Get cognitive context without running full session start.

    Useful for quick context injection.
    """
    stage = create_cognitive_stage()
    return stage.get_prompt_context()


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    """Run session start from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Orchestra Session Start Hook")
    parser.add_argument("--skip-calibration", action="store_true",
                        help="Skip calibration, use defaults")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    result = on_session_start(skip_calibration=args.skip_calibration)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.cognitive_context)
