"""
Micro-Affirmations for OTTO Atmosphere.

Brief, genuine acknowledgments woven into responses.

Rules:
- Affirmations are earned, not sprinkled
- Match energy (depleted → "Done." not "Nice work!")
- Never forced or excessive
- One per response max

Determinism:
- Sorted affirmation lists for deterministic selection
- Fixed seed for reproducible selection
- Same inputs always produce same outputs
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Final, List, Optional, Tuple

from .patterns import ATMOSPHERE_SEED


class AffirmationType(Enum):
    """Types of micro-affirmations."""
    EFFORT = "effort"           # Acknowledging the push
    PROGRESS = "progress"       # Forward motion
    PERSISTENCE = "persistence" # Kept going
    RECOVERY = "recovery"       # Back at it
    COMPLETION = "completion"   # Finished something
    START = "start"             # Beginning something
    RETURN = "return"           # Coming back after break


@dataclass
class Affirmation:
    """A micro-affirmation with energy context."""
    text: str
    type: AffirmationType
    energy_level: str = "any"  # "high", "medium", "low", "depleted", "any"


# Sorted affirmation lists per type for deterministic selection
AFFIRMATIONS: Final[Dict[AffirmationType, List[Affirmation]]] = {
    AffirmationType.EFFORT: sorted([
        Affirmation("That was a push.", AffirmationType.EFFORT, "any"),
        Affirmation("Hard one.", AffirmationType.EFFORT, "any"),
        Affirmation("Not easy.", AffirmationType.EFFORT, "any"),
        Affirmation("Pushed through.", AffirmationType.EFFORT, "any"),
        Affirmation("Effort counts.", AffirmationType.EFFORT, "any"),
    ], key=lambda a: a.text),

    AffirmationType.PROGRESS: sorted([
        Affirmation("Moving.", AffirmationType.PROGRESS, "any"),
        Affirmation("Forward.", AffirmationType.PROGRESS, "any"),
        Affirmation("Progress.", AffirmationType.PROGRESS, "any"),
        Affirmation("That's forward.", AffirmationType.PROGRESS, "any"),
        Affirmation("Step taken.", AffirmationType.PROGRESS, "any"),
    ], key=lambda a: a.text),

    AffirmationType.PERSISTENCE: sorted([
        Affirmation("Still here.", AffirmationType.PERSISTENCE, "any"),
        Affirmation("Kept going.", AffirmationType.PERSISTENCE, "any"),
        Affirmation("Didn't quit.", AffirmationType.PERSISTENCE, "any"),
        Affirmation("Stayed with it.", AffirmationType.PERSISTENCE, "any"),
    ], key=lambda a: a.text),

    AffirmationType.RECOVERY: sorted([
        Affirmation("Back at it.", AffirmationType.RECOVERY, "any"),
        Affirmation("Picked it up.", AffirmationType.RECOVERY, "any"),
        Affirmation("Returned.", AffirmationType.RECOVERY, "any"),
        Affirmation("Back.", AffirmationType.RECOVERY, "any"),
    ], key=lambda a: a.text),

    AffirmationType.COMPLETION: sorted([
        Affirmation("Done.", AffirmationType.COMPLETION, "depleted"),
        Affirmation("Done.", AffirmationType.COMPLETION, "low"),
        Affirmation("Finished.", AffirmationType.COMPLETION, "medium"),
        Affirmation("Shipped.", AffirmationType.COMPLETION, "high"),
        Affirmation("Complete.", AffirmationType.COMPLETION, "any"),
    ], key=lambda a: a.text),

    AffirmationType.START: sorted([
        Affirmation("Starting.", AffirmationType.START, "any"),
        Affirmation("First step.", AffirmationType.START, "any"),
        Affirmation("Beginning.", AffirmationType.START, "any"),
        Affirmation("Kicking off.", AffirmationType.START, "high"),
    ], key=lambda a: a.text),

    AffirmationType.RETURN: sorted([
        Affirmation("Welcome back.", AffirmationType.RETURN, "any"),
        Affirmation("Picking up.", AffirmationType.RETURN, "any"),
        Affirmation("Resuming.", AffirmationType.RETURN, "any"),
        Affirmation("Back at it.", AffirmationType.RETURN, "any"),
    ], key=lambda a: a.text),
}


# Signals that indicate an affirmation is earned
EFFORT_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "hard", "struggle", "struggled", "difficult", "tough",
    "challenging", "finally", "hours", "worked", "tried",
    "pushed", "fought", "grinding",
]))

COMPLETION_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "done", "finished", "completed", "shipped", "deployed",
    "merged", "fixed", "resolved", "passed",  # Note: "working" removed - conflicts with return
]))

RETURN_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "back", "returning", "picking up", "resuming", "continue",
    "where we left", "last time", "again",
]))

START_SIGNALS: Final[Tuple[str, ...]] = tuple(sorted([
    "starting", "begin", "beginning", "new", "first",
    "kicking off", "let's start", "ready to",
]))


def detect_affirmation_type(
    user_message: str,
    momentum_phase: str = "building",
) -> Optional[AffirmationType]:
    """
    Detect if an affirmation is earned based on user message and context.

    Deterministic: fixed signal priority order.

    Args:
        user_message: The user's message
        momentum_phase: Current momentum phase

    Returns:
        AffirmationType if earned, None if not
    """
    msg_lower = user_message.lower()

    # Priority 1: Completion signals
    for signal in COMPLETION_SIGNALS:
        if signal in msg_lower:
            return AffirmationType.COMPLETION

    # Priority 2: Return signals (after break)
    for signal in RETURN_SIGNALS:
        if signal in msg_lower:
            return AffirmationType.RETURN

    # Priority 3: Effort signals
    for signal in EFFORT_SIGNALS:
        if signal in msg_lower:
            return AffirmationType.EFFORT

    # Priority 4: Start signals
    for signal in START_SIGNALS:
        if signal in msg_lower:
            return AffirmationType.START

    # Priority 5: Momentum-based
    if momentum_phase == "crashed":
        return AffirmationType.RECOVERY
    if momentum_phase == "building":
        return AffirmationType.PROGRESS
    if momentum_phase == "rolling":
        return AffirmationType.PERSISTENCE

    return None


def get_affirmation(
    affirmation_type: AffirmationType,
    energy_level: str = "medium",
    seed: int = ATMOSPHERE_SEED,
) -> Optional[Affirmation]:
    """
    Get an appropriate affirmation for the type and energy level.

    Deterministic selection using hash.

    Args:
        affirmation_type: Type of affirmation needed
        energy_level: Current energy level
        seed: Seed for deterministic selection

    Returns:
        Affirmation or None if no match
    """
    if affirmation_type not in AFFIRMATIONS:
        return None

    candidates = AFFIRMATIONS[affirmation_type]

    # Filter by energy level
    energy_matches = [
        a for a in candidates
        if a.energy_level in (energy_level, "any")
    ]

    if not energy_matches:
        # Fall back to "any" energy affirmations
        energy_matches = [a for a in candidates if a.energy_level == "any"]

    if not energy_matches:
        return None

    # Deterministic selection
    selection_key = hash((seed, affirmation_type.value, energy_level))
    return energy_matches[selection_key % len(energy_matches)]


def maybe_get_affirmation(
    user_message: str,
    momentum_phase: str = "building",
    energy_level: str = "medium",
    seed: int = ATMOSPHERE_SEED,
) -> Optional[Affirmation]:
    """
    Get an affirmation if one is earned.

    Convenience function that combines detection and selection.

    Args:
        user_message: The user's message
        momentum_phase: Current momentum phase
        energy_level: Current energy level
        seed: Seed for deterministic selection

    Returns:
        Affirmation if earned, None otherwise
    """
    affirmation_type = detect_affirmation_type(user_message, momentum_phase)
    if affirmation_type is None:
        return None

    return get_affirmation(affirmation_type, energy_level, seed)


__all__ = [
    "Affirmation",
    "AffirmationType",
    "AFFIRMATIONS",
    "get_affirmation",
    "maybe_get_affirmation",
    "detect_affirmation_type",
    "EFFORT_SIGNALS",
    "COMPLETION_SIGNALS",
    "RETURN_SIGNALS",
    "START_SIGNALS",
]
