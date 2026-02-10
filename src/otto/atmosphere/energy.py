"""
Energy Matching for OTTO Atmosphere.

Match user's energy level and provide appropriate lift.

Key insight:
- Depleted → Don't try to energize
- Hyperfocus → Stay out of the way
- Match first, then gentle lift

Determinism:
- Fixed energy profiles
- Deterministic response modifications
- Same inputs always produce same outputs
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final, Optional


class EnergyLevel(Enum):
    """Energy levels with response implications."""
    DEPLETED = "depleted"   # Very low - calm, minimal
    LOW = "low"             # Low - calm, short
    MEDIUM = "medium"       # Normal - neutral
    HIGH = "high"           # High - engaged, enthusiastic
    HYPERFOCUS = "hyperfocus"  # In flow - stay out of way


@dataclass
class EnergyProfile:
    """
    Energy profile for response adaptation.

    Defines how responses should be modified based on energy.
    """
    level: EnergyLevel
    response_tone: str      # calm, neutral, engaged
    max_length: int         # Maximum response length (chars)
    lift_factor: float      # 0.0 = match exactly, 0.5 = moderate lift
    celebration_style: str  # subtle, moderate, enthusiastic, minimal


# Fixed energy profiles
ENERGY_PROFILES: Final[dict[EnergyLevel, EnergyProfile]] = {
    EnergyLevel.DEPLETED: EnergyProfile(
        level=EnergyLevel.DEPLETED,
        response_tone="calm",
        max_length=100,
        lift_factor=0.0,  # No lift - just meet them
        celebration_style="subtle",  # "Done."
    ),
    EnergyLevel.LOW: EnergyProfile(
        level=EnergyLevel.LOW,
        response_tone="calm",
        max_length=200,
        lift_factor=0.1,  # Tiny lift
        celebration_style="subtle",
    ),
    EnergyLevel.MEDIUM: EnergyProfile(
        level=EnergyLevel.MEDIUM,
        response_tone="neutral",
        max_length=500,
        lift_factor=0.3,  # Moderate lift
        celebration_style="moderate",
    ),
    EnergyLevel.HIGH: EnergyProfile(
        level=EnergyLevel.HIGH,
        response_tone="engaged",
        max_length=800,
        lift_factor=0.5,  # Can lift
        celebration_style="enthusiastic",
    ),
    EnergyLevel.HYPERFOCUS: EnergyProfile(
        level=EnergyLevel.HYPERFOCUS,
        response_tone="matched",  # Don't interrupt
        max_length=300,  # Keep short - don't break flow
        lift_factor=0.0,  # No lift - stay out of way
        celebration_style="minimal",  # Barely acknowledge
    ),
}


def get_energy_profile(energy_level: str) -> EnergyProfile:
    """
    Get the energy profile for a given energy level string.

    Args:
        energy_level: Energy level as string

    Returns:
        EnergyProfile for that level
    """
    # Map string to enum
    level_map = {
        "depleted": EnergyLevel.DEPLETED,
        "low": EnergyLevel.LOW,
        "medium": EnergyLevel.MEDIUM,
        "high": EnergyLevel.HIGH,
        "hyperfocus": EnergyLevel.HYPERFOCUS,
        "hyperfocused": EnergyLevel.HYPERFOCUS,  # Alias
    }

    level = level_map.get(energy_level.lower(), EnergyLevel.MEDIUM)
    return ENERGY_PROFILES[level]


def truncate_to_energy(response: str, profile: EnergyProfile) -> str:
    """
    Truncate response to energy-appropriate length.

    Prefers sentence boundaries when truncating.

    Args:
        response: Original response
        profile: Energy profile

    Returns:
        Truncated response
    """
    if len(response) <= profile.max_length:
        return response

    # Find a good truncation point (sentence boundary)
    truncated = response[:profile.max_length]

    # Look for last sentence boundary
    for punct in [". ", "! ", "? "]:
        last_punct = truncated.rfind(punct)
        if last_punct > profile.max_length // 2:  # Must be past halfway
            return truncated[:last_punct + 1].strip()

    # No good boundary - truncate at word boundary
    last_space = truncated.rfind(" ")
    if last_space > profile.max_length // 2:
        return truncated[:last_space].strip()

    # Last resort - hard truncate
    return truncated.strip()


def should_add_breathing_room(response: str, profile: EnergyProfile) -> bool:
    """
    Determine if response needs breathing room (remove trailing noise).

    Low energy = more breathing room needed.

    Args:
        response: Response text
        profile: Energy profile

    Returns:
        True if should remove trailing filler
    """
    # Always add breathing room for depleted/low
    if profile.level in (EnergyLevel.DEPLETED, EnergyLevel.LOW):
        return True

    # Hyperfocus also wants minimal
    if profile.level == EnergyLevel.HYPERFOCUS:
        return True

    return False


def add_breathing_room(response: str) -> str:
    """
    Remove trailing filler to add breathing room.

    Strips phrases like:
    - "Let me know if you have questions"
    - "Feel free to ask"
    - "I'm here to help"

    Args:
        response: Original response

    Returns:
        Response with breathing room
    """
    import re

    # Trailing noise patterns (already stripped by voice adapter,
    # but double-check for atmosphere)
    trailing_noise = [
        r"\.?\s*Let me know if.*$",
        r"\.?\s*Feel free to.*$",
        r"\.?\s*I'?m here to help.*$",
        r"\.?\s*Happy to help.*$",
        r"\.?\s*Hope this helps.*$",
        r"\.?\s*Is there anything else.*$",
        r"\.?\s*Does that (help|make sense).*$",
    ]

    for pattern in trailing_noise:
        response = re.sub(pattern, ".", response, flags=re.IGNORECASE)

    # Clean up double periods
    response = re.sub(r"\.{2,}", ".", response)

    return response.strip()


def match_energy(
    response: str,
    energy_level: str,
) -> str:
    """
    Match response to user's energy level.

    Fixed transformation order:
    1. Get energy profile
    2. Add breathing room if needed
    3. Truncate to appropriate length

    Args:
        response: Original response
        energy_level: Current energy level

    Returns:
        Energy-matched response
    """
    profile = get_energy_profile(energy_level)

    # Step 1: Add breathing room if needed
    if should_add_breathing_room(response, profile):
        response = add_breathing_room(response)

    # Step 2: Truncate to energy-appropriate length
    response = truncate_to_energy(response, profile)

    return response


def get_celebration_prefix(
    energy_level: str,
    is_completion: bool = False,
) -> Optional[str]:
    """
    Get energy-appropriate celebration prefix.

    Args:
        energy_level: Current energy level
        is_completion: Whether celebrating a completion

    Returns:
        Celebration prefix or None
    """
    if not is_completion:
        return None

    profile = get_energy_profile(energy_level)

    celebrations = {
        "subtle": "Done.",
        "moderate": "Nice.",
        "enthusiastic": "Shipped!",
        "minimal": "",  # No celebration - don't break flow
    }

    return celebrations.get(profile.celebration_style, "")


__all__ = [
    "EnergyLevel",
    "EnergyProfile",
    "ENERGY_PROFILES",
    "get_energy_profile",
    "match_energy",
    "truncate_to_energy",
    "should_add_breathing_room",
    "add_breathing_room",
    "get_celebration_prefix",
]
