"""
Profile Integration
====================

Maps intake game traits to ProfileManager fields.

The intake game uses descriptive trait names (e.g., "night_owl", "deep_work")
while the Profile dataclass uses normalized vocabularies from the cognitive
substrate spec (e.g., "late", "deep").

[He2025] Compliance:
- Trait mapping uses sorted key iteration
- All float values use round(value, 6)
- Deterministic conversion functions
"""

from typing import Any, Dict

from otto.core.profile import (
    ProfileManager,
    get_profile_manager,
    Profile,
)


# =============================================================================
# Trait Mapping Tables (sorted keys for determinism)
# =============================================================================

# Chronotype: intake → Profile
CHRONOTYPE_MAP = {
    "early_bird": "early",
    "night_owl": "late",
    "variable": "flexible",
}

# Work style: intake → Profile
WORK_STYLE_MAP = {
    "burst": "pomodoro",
    "deep_work": "deep",
    "task_switcher": "flow",
}

# Stress response: intake → Profile
STRESS_RESPONSE_MAP = {
    "avoid": "pause",
    "confront": "push",
    "deflect": "pivot",
    "process": "pause",
}

# Intervention style: intake → Profile
INTERVENTION_STYLE_MAP = {
    "gentle": "gentle",
    "moderate": "moderate",
    "firm": "firm",
    "guardian": "firm",
    "companion": "gentle",
    "tool": "moderate",
}


# =============================================================================
# Trait Conversion Functions
# =============================================================================

def map_chronotype(value: str) -> str:
    """
    Map intake chronotype to Profile vocabulary.

    [He2025]: Uses lookup table for determinism.
    """
    return CHRONOTYPE_MAP.get(value, "flexible")


def map_work_style(value: str) -> str:
    """
    Map intake work_style to Profile vocabulary.

    [He2025]: Uses lookup table for determinism.
    """
    return WORK_STYLE_MAP.get(value, "flow")


def map_stress_response(value: str) -> str:
    """
    Map intake stress_response to Profile vocabulary.

    [He2025]: Uses lookup table for determinism.
    """
    return STRESS_RESPONSE_MAP.get(value, "pause")


def map_intervention_style(value: str) -> str:
    """
    Map intake intervention_style or otto_role to Profile vocabulary.

    [He2025]: Uses lookup table for determinism.
    """
    return INTERVENTION_STYLE_MAP.get(value, "gentle")


def normalize_float(value: float) -> float:
    """
    Normalize float to 0.0-1.0 range with [He2025] precision.

    [He2025] Compliance: Uses round(value, 6) for float comparison.
    """
    clamped = max(0.0, min(1.0, value))
    return round(clamped, 6)


def derive_focus_level(traits: Dict[str, Any]) -> str:
    """
    Derive focus_level from intake traits.

    Uses focus_duration_minutes and context_switch_cost to determine focus level.

    [He2025] Compliance: Fixed thresholds, deterministic branching.
    """
    duration = traits.get("focus_duration_minutes", 45)
    switch_cost = traits.get("context_switch_cost", 0.5)

    # High focus: long duration + high switch cost
    if duration >= 90 and switch_cost >= 0.6:
        return "locked_in"
    elif duration <= 25 or switch_cost <= 0.3:
        return "scattered"
    else:
        return "moderate"


def derive_tangent_tendency(traits: Dict[str, Any]) -> float:
    """
    Derive tangent_tendency from intake traits.

    Based on work_style and context_switch_cost.

    [He2025] Compliance: Fixed formula, round(6).
    """
    work_style = traits.get("work_style", "flow")
    switch_cost = traits.get("context_switch_cost", 0.5)

    # Task switchers have higher tangent tendency
    if work_style == "task_switcher":
        base = 0.7
    elif work_style == "deep_work":
        base = 0.3
    else:
        base = 0.5

    # High switch cost = lower tangent tendency (they avoid switching)
    adjusted = base * (1.0 - switch_cost * 0.3)
    return normalize_float(adjusted)


def derive_perfectionism_tendency(traits: Dict[str, Any]) -> float:
    """
    Derive perfectionism_tendency from intake traits.

    Based on decision_fatigue_sensitivity and overwhelm_threshold.

    [He2025] Compliance: Fixed formula, round(6).
    """
    fatigue = traits.get("decision_fatigue_sensitivity", 0.5)
    overwhelm = traits.get("overwhelm_threshold", 0.5)

    # High fatigue + low overwhelm threshold = perfectionist tendencies
    tendency = (fatigue + (1.0 - overwhelm)) / 2.0
    return normalize_float(tendency)


def derive_interruption_tolerance(traits: Dict[str, Any]) -> float:
    """
    Derive interruption_tolerance from intake traits.

    Based on notification_sensitivity and interruption_recovery_minutes.

    [He2025] Compliance: Fixed formula, round(6).
    """
    sensitivity = traits.get("notification_sensitivity", 0.5)
    recovery_mins = traits.get("interruption_recovery_minutes", 5)

    # Lower sensitivity + faster recovery = higher tolerance
    tolerance = (1.0 - sensitivity) * (1.0 - min(recovery_mins / 30.0, 1.0))
    return normalize_float(tolerance)


# =============================================================================
# Main Integration Function
# =============================================================================

def convert_intake_to_profile(intake_traits: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert intake game traits to Profile-compatible dictionary.

    Args:
        intake_traits: Raw traits from intake game

    Returns:
        Dictionary compatible with Profile.from_dict() and ProfileManager.load_intake_profile()

    [He2025] Compliance:
    - Sorted key iteration for determinism
    - All floats use round(6)
    - Fixed mapping tables
    """
    profile_data = {}

    # Direct mappings (with vocabulary translation)
    if "chronotype" in intake_traits:
        profile_data["chronotype"] = map_chronotype(intake_traits["chronotype"])

    if "work_style" in intake_traits:
        profile_data["work_style"] = map_work_style(intake_traits["work_style"])

    if "stress_response" in intake_traits:
        profile_data["stress_response"] = map_stress_response(intake_traits["stress_response"])

    if "intervention_style" in intake_traits:
        profile_data["intervention_style"] = map_intervention_style(intake_traits["intervention_style"])
    elif "otto_role" in intake_traits:
        profile_data["intervention_style"] = map_intervention_style(intake_traits["otto_role"])

    # Derived fields
    profile_data["focus_level"] = derive_focus_level(intake_traits)
    profile_data["tangent_tendency"] = derive_tangent_tendency(intake_traits)
    profile_data["perfectionism_tendency"] = derive_perfectionism_tendency(intake_traits)
    profile_data["interruption_tolerance"] = derive_interruption_tolerance(intake_traits)

    # Direct float mappings (normalize to 0-1)
    if "protection_firmness" in intake_traits:
        # Protection firmness maps to intervention style intensity
        firmness = intake_traits["protection_firmness"]
        if firmness >= 0.7:
            profile_data["intervention_style"] = "firm"
        elif firmness >= 0.4:
            profile_data["intervention_style"] = "moderate"
        else:
            profile_data["intervention_style"] = "gentle"

    # Protection settings
    if "allow_override" in intake_traits:
        profile_data["permission_grants_enabled"] = intake_traits["allow_override"]

    # Body check and crash prediction always enabled by default
    profile_data["body_check_enabled"] = True
    profile_data["crash_prediction_enabled"] = True

    # Ensure sorted keys for [He2025] determinism
    return {k: profile_data[k] for k in sorted(profile_data.keys())}


def load_intake_to_profile_manager(
    intake_traits: Dict[str, Any],
    manager: ProfileManager = None,
) -> Profile:
    """
    Load intake traits into ProfileManager and return the resolved Profile.

    This is the main integration point between intake game and profile system.

    Args:
        intake_traits: Raw traits from intake game
        manager: Optional ProfileManager instance (uses global if None)

    Returns:
        Resolved Profile with intake data loaded

    [He2025] Compliance:
    - Deterministic trait conversion
    - LIVRPS layer priority preserved
    """
    if manager is None:
        manager = get_profile_manager()

    # Convert intake traits to Profile-compatible format
    profile_data = convert_intake_to_profile(intake_traits)

    # Load into ProfileManager (this updates PAYLOADS layer)
    manager.load_intake_profile(profile_data)

    # Return the resolved profile
    return manager.get_profile()
