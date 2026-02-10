"""
Struggle Reframes for OTTO Atmosphere.

Transform struggle narratives into growth narratives.

Rules:
- Only reframe detected struggles (in user message)
- Never toxic positivity
- Acknowledge before reframing
- One reframe per response max

Determinism:
- Sorted struggle patterns for deterministic detection
- Fixed reframe lists for reproducible selection
- Same inputs always produce same outputs
"""

import re
from dataclasses import dataclass
from typing import Dict, Final, List, Optional, Tuple

from .patterns import ATMOSPHERE_SEED


@dataclass
class Reframe:
    """A struggle reframe."""
    struggle_pattern: str      # Regex to detect the struggle
    acknowledgment: str        # First acknowledge
    reframe: str              # Then reframe
    followup: Optional[str]   # Optional next step


# Sorted reframe list for deterministic matching
REFRAMES: Final[List[Reframe]] = sorted([
    # Core struggle patterns
    Reframe(
        struggle_pattern=r"\b(i can'?t|cannot|unable to)\b",
        acknowledgment="",
        reframe="Not yet.",
        followup="What's the smallest piece?",
    ),
    Reframe(
        struggle_pattern=r"\b(i'?m stuck|stuck on|stuck at)\b",
        acknowledgment="Stuck is information.",
        reframe="You're at the edge of what you know.",
        followup="What part is clearest?",
    ),
    Reframe(
        struggle_pattern=r"\b(i'?m lost|feel lost|totally lost)\b",
        acknowledgment="",
        reframe="Lost is the start of finding.",
        followup="What's the last thing that made sense?",
    ),
    Reframe(
        struggle_pattern=r"\b(don'?t understand|doesn'?t make sense)\b",
        acknowledgment="Understanding builds.",
        reframe="",
        followup="What part is clearest?",
    ),
    Reframe(
        struggle_pattern=r"\b(overwhelm(ed|ing)?|too much|so much)\b",
        acknowledgment="That's a signal, not a failure.",
        reframe="",
        followup="Let's shrink the view.",
    ),
    Reframe(
        struggle_pattern=r"\b(keep failing|keeps failing|always fail)\b",
        acknowledgment="Attempts are data.",
        reframe="",
        followup="What did the last one teach?",
    ),
    Reframe(
        struggle_pattern=r"\b(i'?m frustrated|so frustrated|frustrating)\b",
        acknowledgment="Frustration means you care.",
        reframe="",
        followup="What's the friction?",
    ),
    Reframe(
        struggle_pattern=r"\b(nothing works|nothing is working)\b",
        acknowledgment="That's exhausting.",
        reframe="Something changed, though.",
        followup="What was different about the last attempt?",
    ),
    Reframe(
        struggle_pattern=r"\b(i'?m not smart enough|too dumb|too stupid)\b",
        acknowledgment="This is hard, not you.",
        reframe="Confusion is where learning happens.",
        followup=None,
    ),
    Reframe(
        struggle_pattern=r"\b(i suck at|i'?m bad at|terrible at)\b",
        acknowledgment="",
        reframe="You're in the learning phase.",
        followup="Everyone starts here.",
    ),
    Reframe(
        struggle_pattern=r"\b(give up|giving up|want to quit)\b",
        acknowledgment="That urge makes sense.",
        reframe="Rest is an option too.",
        followup="What would help right now?",
    ),
    Reframe(
        struggle_pattern=r"\b(waste of time|wasted time|wasting time)\b",
        acknowledgment="",
        reframe="Exploration isn't waste.",
        followup="What did you learn?",
    ),
    Reframe(
        struggle_pattern=r"\b(never going to|will never|won'?t ever)\b",
        acknowledgment="",
        reframe="Not yet.",
        followup="What's one step closer?",
    ),
    Reframe(
        struggle_pattern=r"\b(no idea|have no clue|clueless)\b",
        acknowledgment="Starting from scratch is valid.",
        reframe="",
        followup="What would you try first?",
    ),
    Reframe(
        struggle_pattern=r"\b(hate this|hate it|i hate)\b",
        acknowledgment="That's fair.",
        reframe="Frustration is information.",
        followup="What specifically?",
    ),

    # === NEW: Edge case patterns ===

    # Why-based questions (implying struggle)
    Reframe(
        struggle_pattern=r"\bwhy (won'?t|doesn'?t|isn'?t|can'?t) (this|it) work\b",
        acknowledgment="Good question.",
        reframe="Let's debug together.",
        followup="What's the expected vs actual behavior?",
    ),
    Reframe(
        struggle_pattern=r"\bwhy (is this|does this) (so hard|not working)\b",
        acknowledgment="It's a fair question.",
        reframe="",
        followup="What's the specific blocker?",
    ),

    # Self-deprecating patterns
    Reframe(
        struggle_pattern=r"\b(i'?m probably|must be) (doing something|missing something) (wrong|dumb|stupid|obvious)\b",
        acknowledgment="You're troubleshooting, not failing.",
        reframe="",
        followup="Walk me through what you tried.",
    ),
    Reframe(
        struggle_pattern=r"\b(this is|i'?m being) (stupid|dumb|an idiot)\b",
        acknowledgment="You're learning, not failing.",
        reframe="This stuff is hard.",
        followup=None,
    ),
    Reframe(
        struggle_pattern=r"\bwhat am i (doing|missing|not getting)\b",
        acknowledgment="Good instinct to question.",
        reframe="",
        followup="Let's trace through it.",
    ),

    # Comparison-based struggles
    Reframe(
        struggle_pattern=r"\b(everyone else|others|other people) (gets?|understands?|can)\b",
        acknowledgment="Comparison isn't fair to you.",
        reframe="Everyone's path is different.",
        followup="What's your specific wall?",
    ),
    Reframe(
        struggle_pattern=r"\bshould (be able to|know|understand) (this|how)\b",
        acknowledgment="'Should' is heavy.",
        reframe="You're where you are.",
        followup="What's the gap?",
    ),

    # Time pressure patterns
    Reframe(
        struggle_pattern=r"\b(been at this|working on this) for (hours|days|forever)\b",
        acknowledgment="That's a lot of effort.",
        reframe="Time invested isn't wasted.",
        followup="Fresh eyes might help. What's the core issue?",
    ),
    Reframe(
        struggle_pattern=r"\b(taking|this is taking) (forever|too long|so long)\b",
        acknowledgment="Time blindness is real.",
        reframe="",
        followup="Break or push through?",
    ),

    # Error fatigue
    Reframe(
        struggle_pattern=r"\b(another|same|yet another) (error|bug|problem)\b",
        acknowledgment="Error fatigue is real.",
        reframe="Each error narrows the search space.",
        followup="What changed between attempts?",
    ),
    Reframe(
        struggle_pattern=r"\b(keeps? (breaking|failing|erroring)|broken again)\b",
        acknowledgment="That's exhausting.",
        reframe="Patterns in failures are clues.",
        followup="When does it NOT fail?",
    ),

    # Confusion indicators
    Reframe(
        struggle_pattern=r"\b(confused|confusing|makes no sense)\b",
        acknowledgment="Confusion is the frontier.",
        reframe="You're in the learning zone.",
        followup="What part is most confusing?",
    ),
    Reframe(
        struggle_pattern=r"\b(don'?t know what i'?m doing|no clue what to do)\b",
        acknowledgment="That's a valid place to start.",
        reframe="",
        followup="What's one thing you DO know?",
    ),

    # Doubt patterns
    Reframe(
        struggle_pattern=r"\b(not sure if|don'?t know if) (this is right|i'?m doing this right)\b",
        acknowledgment="Doubt is part of learning.",
        reframe="",
        followup="What would 'right' look like?",
    ),
    Reframe(
        struggle_pattern=r"\b(am i|is this) (on the right track|doing this correctly)\b",
        acknowledgment="Good to check.",
        reframe="",
        followup="What's your expected outcome?",
    ),

    # Scope overwhelm
    Reframe(
        struggle_pattern=r"\b(where do i (even )?start|don'?t know where to (start|begin))\b",
        acknowledgment="Big tasks are hard to start.",
        reframe="",
        followup="What's the smallest first step?",
    ),
    Reframe(
        struggle_pattern=r"\b(this is (huge|massive|enormous)|too (big|complex))\b",
        acknowledgment="Scope can be scary.",
        reframe="Every big thing is small pieces.",
        followup="Let's chunk it.",
    ),
], key=lambda r: r.struggle_pattern)


def detect_struggle(message: str) -> Optional[Reframe]:
    """
    Detect if the message contains a struggle narrative.

    Deterministic: patterns checked in sorted order.

    Args:
        message: User's message

    Returns:
        Reframe if struggle detected, None otherwise
    """
    msg_lower = message.lower()

    # Check patterns in sorted order (deterministic)
    for reframe in REFRAMES:
        if re.search(reframe.struggle_pattern, msg_lower, re.IGNORECASE):
            return reframe

    return None


def format_reframe(reframe: Reframe) -> str:
    """
    Format a reframe into response text.

    Combines acknowledgment, reframe, and followup.

    Args:
        reframe: The reframe to format

    Returns:
        Formatted reframe text
    """
    parts = []

    if reframe.acknowledgment:
        parts.append(reframe.acknowledgment)

    if reframe.reframe:
        parts.append(reframe.reframe)

    if reframe.followup:
        parts.append(reframe.followup)

    return " ".join(parts)


def get_reframe(
    message: str,
    seed: int = ATMOSPHERE_SEED,
) -> Optional[str]:
    """
    Get a reframe for a struggle if one is detected.

    Convenience function that combines detection and formatting.

    Args:
        message: User's message
        seed: Seed (unused but kept for API consistency)

    Returns:
        Formatted reframe text if struggle detected, None otherwise
    """
    reframe = detect_struggle(message)
    if reframe is None:
        return None

    return format_reframe(reframe)


__all__ = [
    "Reframe",
    "REFRAMES",
    "detect_struggle",
    "format_reframe",
    "get_reframe",
]
