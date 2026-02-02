"""
Proactive Permission Grants for OTTO Atmosphere.

Grant permission before guilt forms.

ADHD brains often need explicit permission to:
- Stop working
- Rest
- Ship imperfect work
- Go slow
- Change direction
- Skip things
- Ask for help

[He2025] ThinkingMachines Compliance:
- Sorted permission lists for deterministic selection
- Fixed trigger priority order
- Same inputs always produce same outputs
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Final, List, Optional, Tuple

from .patterns import ATMOSPHERE_SEED


class PermissionType(Enum):
    """Types of permission grants."""
    STOP = "stop"           # Permission to stop working
    REST = "rest"           # Permission to rest
    IMPERFECT = "imperfect" # Permission to ship imperfect
    SLOW = "slow"           # Permission to go slow
    CHANGE = "change"       # Permission to change direction
    SKIP = "skip"           # Permission to skip things
    LATER = "later"         # Permission to do it later
    HELP = "help"           # Permission to ask for help
    FEEL = "feel"           # Permission to feel frustrated/etc


@dataclass
class Permission:
    """A permission grant."""
    text: str
    type: PermissionType


# [He2025] Sorted permission lists per type for deterministic selection
PERMISSIONS: Final[Dict[PermissionType, List[Permission]]] = {
    PermissionType.STOP: sorted([
        Permission("This can stop here.", PermissionType.STOP),
        Permission("Done is done.", PermissionType.STOP),
        Permission("Good stopping point.", PermissionType.STOP),
        Permission("Enough for now.", PermissionType.STOP),
    ], key=lambda p: p.text),

    PermissionType.REST: sorted([
        Permission("Rest is productive.", PermissionType.REST),
        Permission("Tomorrow exists.", PermissionType.REST),
        Permission("Break is valid.", PermissionType.REST),
        Permission("Recovery counts.", PermissionType.REST),
    ], key=lambda p: p.text),

    PermissionType.IMPERFECT: sorted([
        Permission("Good enough ships.", PermissionType.IMPERFECT),
        Permission("Polish later.", PermissionType.IMPERFECT),
        Permission("Done beats perfect.", PermissionType.IMPERFECT),
        Permission("Ship it.", PermissionType.IMPERFECT),
    ], key=lambda p: p.text),

    PermissionType.SLOW: sorted([
        Permission("Slow is fine.", PermissionType.SLOW),
        Permission("No rush.", PermissionType.SLOW),
        Permission("Take your time.", PermissionType.SLOW),
        Permission("Your pace.", PermissionType.SLOW),
    ], key=lambda p: p.text),

    PermissionType.CHANGE: sorted([
        Permission("Changing direction is valid.", PermissionType.CHANGE),
        Permission("Pivot is progress.", PermissionType.CHANGE),
        Permission("Course correction allowed.", PermissionType.CHANGE),
        Permission("New direction works.", PermissionType.CHANGE),
    ], key=lambda p: p.text),

    PermissionType.SKIP: sorted([
        Permission("Skip it.", PermissionType.SKIP),
        Permission("Not everything matters.", PermissionType.SKIP),
        Permission("Let it go.", PermissionType.SKIP),
        Permission("Move past it.", PermissionType.SKIP),
    ], key=lambda p: p.text),

    PermissionType.LATER: sorted([
        Permission("Later works.", PermissionType.LATER),
        Permission("Park it.", PermissionType.LATER),
        Permission("Save for later.", PermissionType.LATER),
        Permission("Not now is fine.", PermissionType.LATER),
    ], key=lambda p: p.text),

    PermissionType.HELP: sorted([
        Permission("Ask for help.", PermissionType.HELP),
        Permission("You don't have to know.", PermissionType.HELP),
        Permission("Get support.", PermissionType.HELP),
        Permission("Reach out.", PermissionType.HELP),
    ], key=lambda p: p.text),

    PermissionType.FEEL: sorted([
        Permission("Frustration is information.", PermissionType.FEEL),
        Permission("Feelings are data.", PermissionType.FEEL),
        Permission("Valid response.", PermissionType.FEEL),
        Permission("Makes sense to feel that.", PermissionType.FEEL),
    ], key=lambda p: p.text),
}


# Signals that indicate permission should be granted
STOP_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "done", "stopping", "stop", "enough", "that's it",
    "finished for", "calling it", "wrapping up",
]))

REST_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "tired", "exhausted", "burnt out", "drained",
    "no energy", "depleted", "need a break", "can't focus",
]))

IMPERFECT_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "not perfect", "not done", "not quite", "almost",
    "one more thing", "let me just", "should polish",
    "could be better", "needs work",
]))

SLOW_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "taking forever", "so slow", "behind", "not fast enough",
    "too slow", "everyone else", "should be faster",
]))

CHANGE_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "wrong direction", "not working", "pivot", "change approach",
    "try something else", "different", "abandon",
]))

FRUSTRATION_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "frustrated", "annoyed", "angry", "ugh", "argh",
    "hate this", "why won't", "nothing works",
]))


def should_grant_permission(
    user_message: str,
    burnout_level: str = "GREEN",
    energy_level: str = "medium",
    momentum_phase: str = "building",
) -> Optional[PermissionType]:
    """
    Determine if permission should be proactively granted.

    [He2025] Fixed priority order for deterministic evaluation.

    Args:
        user_message: The user's message
        burnout_level: Current burnout level (GREEN/YELLOW/ORANGE/RED)
        energy_level: Current energy level
        momentum_phase: Current momentum phase

    Returns:
        PermissionType if should grant, None otherwise
    """
    msg_lower = user_message.lower()

    # Priority 1: Burnout-based permissions (most urgent)
    if burnout_level == "RED":
        return PermissionType.STOP
    if burnout_level == "ORANGE":
        return PermissionType.REST

    # Priority 2: Energy-based permissions
    if energy_level == "depleted":
        return PermissionType.REST

    # Priority 3: Frustration signals → permission to feel
    for signal in FRUSTRATION_SIGNALS:
        if signal in msg_lower:
            return PermissionType.FEEL

    # Priority 4: Rest signals
    for signal in REST_SIGNALS:
        if signal in msg_lower:
            return PermissionType.REST

    # Priority 5: Perfectionism signals → permission to ship imperfect
    for signal in IMPERFECT_SIGNALS:
        if signal in msg_lower:
            return PermissionType.IMPERFECT

    # Priority 6: Slow signals
    for signal in SLOW_SIGNALS:
        if signal in msg_lower:
            return PermissionType.SLOW

    # Priority 7: Change signals
    for signal in CHANGE_SIGNALS:
        if signal in msg_lower:
            return PermissionType.CHANGE

    # Priority 8: Stop signals
    for signal in STOP_SIGNALS:
        if signal in msg_lower:
            return PermissionType.STOP

    # Priority 9: Long session (momentum-based)
    if momentum_phase == "crashed":
        return PermissionType.REST

    return None


def get_permission(
    permission_type: PermissionType,
    seed: int = ATMOSPHERE_SEED,
) -> Permission:
    """
    Get a permission grant of the specified type.

    [He2025] Deterministic selection using hash.

    Args:
        permission_type: Type of permission to grant
        seed: Seed for deterministic selection

    Returns:
        Permission grant
    """
    if permission_type not in PERMISSIONS:
        # Default fallback
        return Permission("This is valid.", permission_type)

    candidates = PERMISSIONS[permission_type]

    # Deterministic selection
    selection_key = hash((seed, permission_type.value))
    return candidates[selection_key % len(candidates)]


def maybe_get_permission(
    user_message: str,
    burnout_level: str = "GREEN",
    energy_level: str = "medium",
    momentum_phase: str = "building",
    seed: int = ATMOSPHERE_SEED,
) -> Optional[Permission]:
    """
    Get a permission if one should be granted.

    Convenience function that combines detection and selection.

    Args:
        user_message: The user's message
        burnout_level: Current burnout level
        energy_level: Current energy level
        momentum_phase: Current momentum phase
        seed: Seed for deterministic selection

    Returns:
        Permission if should grant, None otherwise
    """
    permission_type = should_grant_permission(
        user_message, burnout_level, energy_level, momentum_phase
    )
    if permission_type is None:
        return None

    return get_permission(permission_type, seed)


__all__ = [
    "Permission",
    "PermissionType",
    "PERMISSIONS",
    "get_permission",
    "maybe_get_permission",
    "should_grant_permission",
]
