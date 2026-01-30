"""
USD Profile Writer

Writes the personality profile as a valid USDA file.
This follows USD (Universal Scene Description) syntax.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ProfileData:
    """Data structure for profile information"""
    traits: dict[str, Any]


def format_usd_value(value: Any) -> str:
    """Format a Python value as USD syntax"""
    if isinstance(value, str):
        return f'"{value}"'
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, int):
        return str(value)
    elif isinstance(value, float):
        return f"{value:.2f}"
    elif isinstance(value, list):
        if not value:
            return "[]"
        if isinstance(value[0], int):
            return f"[{', '.join(str(v) for v in value)}]"
        elif isinstance(value[0], str):
            return f"[{', '.join(f'\"{v}\"' for v in value)}]"
        else:
            return f"[{', '.join(str(v) for v in value)}]"
    else:
        return str(value)


def write_profile(profile_data: ProfileData, path: Path) -> None:
    """
    Write personality profile as USD file.

    The profile uses USD composition semantics:
    - Base profile: From intake game (this file)
    - Calibration: Learned overrides (separate layer)
    - Session: Current state (highest priority)

    LIVRPS resolution means Session > Calibration > Base
    """

    now = datetime.now().isoformat()
    traits = profile_data.traits

    # Categorize traits
    chronotype_traits = {}
    work_style_traits = {}
    stress_traits = {}
    protection_traits = {}
    recovery_traits = {}
    energy_traits = {}
    meta_traits = {}

    for key, value in traits.items():
        if key in ("chronotype", "peak_hours", "recovery_hours"):
            chronotype_traits[key] = value
        elif key in ("work_style", "focus_duration_minutes", "context_switch_cost",
                     "interruption_recovery_minutes", "notification_sensitivity"):
            work_style_traits[key] = value
        elif key in ("stress_response", "overwhelm_threshold"):
            stress_traits[key] = value
        elif key in ("protection_firmness", "allow_override", "override_cooldown_minutes",
                     "otto_role", "intervention_style"):
            protection_traits[key] = value
        elif key in ("preferred_recovery", "recovery_social_need"):
            recovery_traits[key] = value
        elif key in ("decision_fatigue_sensitivity", "max_daily_decisions"):
            energy_traits[key] = value
        else:
            meta_traits[key] = value

    # Generate USD content
    content = f'''#usda 1.0
(
    doc = "OTTO OS Personality Profile"
    customLayerData = {{
        string otto_version = "0.1.0"
        string created_by = "intake_game"
        string created_at = "{now}"
    }}
)

def "OttoProfile" (
    kind = "personality"
    doc = "Base personality profile from intake game"
)
{{
    # ═══════════════════════════════════════════════════════════════════════════
    # CHRONOTYPE
    # When you're sharpest, when you need protection
    # ═══════════════════════════════════════════════════════════════════════════
'''

    for key, value in chronotype_traits.items():
        if key == "peak_hours" or key == "recovery_hours":
            content += f'    int[] {key} = {format_usd_value(value)}\n'
        else:
            content += f'    string {key} = {format_usd_value(value)}\n'

    content += '''
    # ═══════════════════════════════════════════════════════════════════════════
    # WORK STYLE
    # How you approach tasks, handle focus
    # ═══════════════════════════════════════════════════════════════════════════
'''

    for key, value in work_style_traits.items():
        if isinstance(value, str):
            content += f'    string {key} = {format_usd_value(value)}\n'
        elif isinstance(value, float):
            content += f'    float {key} = {format_usd_value(value)}\n'
        else:
            content += f'    int {key} = {format_usd_value(value)}\n'

    content += '''
    # ═══════════════════════════════════════════════════════════════════════════
    # STRESS RESPONSE
    # How you handle overwhelm
    # ═══════════════════════════════════════════════════════════════════════════
'''

    for key, value in stress_traits.items():
        if isinstance(value, str):
            content += f'    string {key} = {format_usd_value(value)}\n'
        else:
            content += f'    float {key} = {format_usd_value(value)}\n'

    content += '''
    # ═══════════════════════════════════════════════════════════════════════════
    # PROTECTION PREFERENCES
    # How OTTO should guard your wellbeing
    # ═══════════════════════════════════════════════════════════════════════════
'''

    for key, value in protection_traits.items():
        if isinstance(value, str):
            content += f'    string {key} = {format_usd_value(value)}\n'
        elif isinstance(value, bool):
            content += f'    bool {key} = {format_usd_value(value)}\n'
        elif isinstance(value, float):
            content += f'    float {key} = {format_usd_value(value)}\n'
        else:
            content += f'    int {key} = {format_usd_value(value)}\n'

    content += '''
    # ═══════════════════════════════════════════════════════════════════════════
    # RECOVERY STYLE
    # What helps when you're depleted
    # ═══════════════════════════════════════════════════════════════════════════
'''

    for key, value in recovery_traits.items():
        if isinstance(value, str):
            content += f'    string {key} = {format_usd_value(value)}\n'
        else:
            content += f'    float {key} = {format_usd_value(value)}\n'

    content += '''
    # ═══════════════════════════════════════════════════════════════════════════
    # ENERGY PATTERNS
    # Decision fatigue, capacity
    # ═══════════════════════════════════════════════════════════════════════════
'''

    for key, value in energy_traits.items():
        if isinstance(value, float):
            content += f'    float {key} = {format_usd_value(value)}\n'
        else:
            content += f'    int {key} = {format_usd_value(value)}\n'

    content += '''
}

def "OttoProfile/Calibration" (
    doc = "Learned overrides from usage patterns - OTTO populates this over time"
)
{
    # This layer is populated as OTTO learns your patterns
    # Via LIVRPS, these values override the base profile
    #
    # Example overrides OTTO might learn:
    # float protection_firmness = 0.7    # learned: you ignore gentle nudges
    # int focus_duration_minutes = 120   # learned: you focus longer than you said
}

def "OttoProfile/Session" (
    doc = "Current session state - highest priority, resets each session"
)
{
    # Real-time state during a session
    # Highest priority in LIVRPS resolution

    string current_energy = "unknown"
    string current_mood = "unknown"
    int exchanges_this_session = 0
    bool user_requested_no_protection = false
}
'''

    # Write file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_profile(path: Path) -> dict[str, Any] | None:
    """
    Read a USD profile and return parsed traits.

    Note: This is a simple parser. For full USD support,
    use the pxr.Usd library.
    """
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    traits = {}

    # Simple line-by-line parser for common patterns
    for line in content.split("\n"):
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#") or line.startswith("(") or line.startswith(")"):
            continue

        # Parse attribute assignments
        if "=" in line and not line.startswith("def") and not line.startswith("string doc"):
            # Remove type prefix
            for type_prefix in ("string ", "int ", "float ", "bool ", "int[] "):
                if line.startswith(type_prefix):
                    line = line[len(type_prefix):]
                    break

            # Split on first =
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Parse value
                if value.startswith('"') and value.endswith('"'):
                    traits[key] = value[1:-1]
                elif value == "true":
                    traits[key] = True
                elif value == "false":
                    traits[key] = False
                elif value.startswith("[") and value.endswith("]"):
                    # Parse list
                    inner = value[1:-1]
                    if inner:
                        items = [x.strip().strip('"') for x in inner.split(",")]
                        # Try to convert to int
                        try:
                            traits[key] = [int(x) for x in items]
                        except ValueError:
                            traits[key] = items
                    else:
                        traits[key] = []
                elif "." in value:
                    try:
                        traits[key] = float(value)
                    except ValueError:
                        traits[key] = value
                else:
                    try:
                        traits[key] = int(value)
                    except ValueError:
                        traits[key] = value

    return traits
