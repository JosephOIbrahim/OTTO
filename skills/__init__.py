"""
Orchestra Claude Code Skills
============================

Skills (slash commands) for explicit cognitive state interaction.

Skills:
- /calibrate: Re-calibrate focus/urgency/energy
- /status: Show cognitive state dashboard
- /tension: Surface any pending tensions
- /recover: Recovery menu when overwhelmed

These skills integrate with Claude Code's skill system.
"""

from .calibrate import calibrate_skill, CALIBRATE_SKILL_DEFINITION
from .status import status_skill, STATUS_SKILL_DEFINITION
from .tension import tension_skill, TENSION_SKILL_DEFINITION
from .recover import recover_skill, RECOVER_SKILL_DEFINITION

# Skill definitions for Claude Code registration
ORCHESTRA_SKILLS = {
    "calibrate": CALIBRATE_SKILL_DEFINITION,
    "status": STATUS_SKILL_DEFINITION,
    "tension": TENSION_SKILL_DEFINITION,
    "recover": RECOVER_SKILL_DEFINITION,
}

__all__ = [
    'calibrate_skill',
    'status_skill',
    'tension_skill',
    'recover_skill',
    'CALIBRATE_SKILL_DEFINITION',
    'STATUS_SKILL_DEFINITION',
    'TENSION_SKILL_DEFINITION',
    'RECOVER_SKILL_DEFINITION',
    'ORCHESTRA_SKILLS',
]
