"""
OTTO OS Personality Intake

A 10-minute Hybrid CLI experience that helps OTTO understand
how you work—without diagnostic language, without clinical framing.

Just scenarios and choices.

[He2025] Compliance:
- Trait accumulation uses sorted key iteration
- Deterministic profile generation
- Integration with ProfileManager via LIVRPS layers
"""

from .game import IntakeGame, run_intake
from .scenarios import Scenario, ScenarioResult
from .profile_writer import write_profile
from .profile_integration import (
    convert_intake_to_profile,
    load_intake_to_profile_manager,
)

__all__ = [
    "IntakeGame",
    "run_intake",
    "Scenario",
    "ScenarioResult",
    "write_profile",
    "convert_intake_to_profile",
    "load_intake_to_profile_manager",
]
