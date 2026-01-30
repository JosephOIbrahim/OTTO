"""
OTTO OS Personality Intake

A 10-minute Hybrid CLI experience that helps OTTO understand
how you work—without diagnostic language, without clinical framing.

Just scenarios and choices.
"""

from .game import IntakeGame, run_intake
from .scenarios import Scenario, ScenarioResult
from .profile_writer import write_profile

__all__ = [
    "IntakeGame",
    "run_intake",
    "Scenario",
    "ScenarioResult",
    "write_profile",
]
