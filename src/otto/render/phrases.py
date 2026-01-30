"""
Human Phrases Dictionary
========================

Dignity-first language for OTTO's user-facing messages.

CRITICAL RULE: No clinical language.
- Never: ADHD, disorder, symptom, manage, cope, dysfunction, executive function
- Always: Human descriptions of states and feelings

These phrases transform internal cognitive states into supportive,
human language that doesn't label or diagnose.
"""

from typing import Dict, List

# =============================================================================
# FORBIDDEN WORDS - Never use these in output
# =============================================================================

FORBIDDEN_WORDS: List[str] = [
    # Clinical terms
    "adhd",
    "add",
    "disorder",
    "symptom",
    "syndrome",
    "dysfunction",
    "deficit",
    "diagnosis",
    "condition",
    "treatment",
    "therapy",
    "medication",

    # Pathologizing language
    "manage your",
    "cope with",
    "struggle with",
    "suffer from",
    "dealing with",

    # Clinical function terms
    "executive function",
    "working memory deficit",
    "attention deficit",
    "impulse control",

    # Othering language
    "normal people",
    "neurotypical",
    "neurodiverse",  # even positive labels are still labels
]


# =============================================================================
# STATE PHRASES - Human descriptions of cognitive states
# =============================================================================

STATE_PHRASES: Dict[str, Dict[str, str]] = {
    # Burnout levels
    "burnout_green": {
        "short": "Good",
        "status": "You're in a good place",
        "greeting": "Looking good!",
    },
    "burnout_yellow": {
        "short": "Getting there",
        "status": "You've been at it a while",
        "greeting": "Still going, huh?",
    },
    "burnout_orange": {
        "short": "Running hot",
        "status": "You've been going hard",
        "greeting": "Hey, you've been pushing",
    },
    "burnout_red": {
        "short": "Fried",
        "status": "You seem pretty wiped",
        "greeting": "Let's pause for a sec",
    },

    # Energy levels
    "energy_high": {
        "short": "Sharp",
        "status": "You're feeling sharp",
        "greeting": "Lots of energy today",
    },
    "energy_medium": {
        "short": "Steady",
        "status": "Cruising along",
        "greeting": "Solid vibes",
    },
    "energy_low": {
        "short": "Low",
        "status": "Running a bit low",
        "greeting": "Taking it easy today?",
    },
    "energy_depleted": {
        "short": "Empty",
        "status": "Tank's pretty empty",
        "greeting": "Rough day?",
    },

    # Momentum phases
    "momentum_cold_start": {
        "short": "Starting up",
        "status": "Just getting going",
        "note": "Small wins first",
    },
    "momentum_building": {
        "short": "Building",
        "status": "Getting into it",
        "note": "Keep feeding this",
    },
    "momentum_rolling": {
        "short": "Rolling",
        "status": "You're rolling",
        "note": "Protect this flow",
    },
    "momentum_peak": {
        "short": "Peak",
        "status": "You're on fire",
        "note": "Save your exit point",
    },
    "momentum_crashed": {
        "short": "Crashed",
        "status": "Momentum's gone",
        "note": "Tomorrow's fine",
    },

    # Focus states
    "focus_scattered": {
        "short": "Scattered",
        "status": "Thoughts bouncing around",
        "suggestion": "One thing at a time",
    },
    "focus_moderate": {
        "short": "Moderate",
        "status": "Focus is okay",
        "suggestion": "Good for normal work",
    },
    "focus_locked_in": {
        "short": "Locked in",
        "status": "You're locked in",
        "suggestion": "Don't break this",
    },

    # Emotional states
    "frustrated": {
        "short": "Frustrated",
        "status": "I can tell this is frustrating",
        "response": "That's legit annoying",
    },
    "overwhelmed": {
        "short": "Overwhelmed",
        "status": "That's a lot at once",
        "response": "Let's break this down",
    },
    "stuck": {
        "short": "Stuck",
        "status": "Feeling stuck",
        "response": "What's the smallest next step?",
    },
    "anxious": {
        "short": "Anxious",
        "status": "Some tension there",
        "response": "What's the worry?",
    },
}


# =============================================================================
# PROTECTION PHRASES - Dignity-first intervention messages
# =============================================================================

PROTECTION_PHRASES: Dict[str, Dict[str, str]] = {
    # Time-based gentle nudges
    "time_check_gentle": {
        "message": "It's been about {time}",
        "suggestion": "Just so you know",
    },
    "time_check_moderate": {
        "message": "You've been at this for {time}",
        "suggestion": "Quick break might help",
    },
    "time_check_firm": {
        "message": "It's been {time}. You've done a lot.",
        "suggestion": "Let's wrap this part up",
    },

    # Overuse detection
    "overuse_gentle": {
        "message": "You're pushing through",
        "suggestion": "That's okay, just checking in",
    },
    "overuse_moderate": {
        "message": "That's a lot of pushing through",
        "suggestion": "Want to wrap up soon?",
    },
    "overuse_firm": {
        "message": "You've been overriding a while now",
        "suggestion": "I think you need a break",
    },

    # Burnout warnings
    "burnout_yellow_nudge": {
        "message": "You've been going a while",
        "suggestion": "Break soon?",
    },
    "burnout_orange_warning": {
        "message": "You seem pretty tapped",
        "suggestion": "Want to find a stopping point?",
    },
    "burnout_red_stop": {
        "message": "Hey. Let's stop for today.",
        "suggestion": "You've done enough. Really.",
    },

    # Hyperfocus interventions
    "hyperfocus_notice": {
        "message": "You're deep in the zone",
        "suggestion": "Just a gentle tap - still with us?",
    },
    "hyperfocus_check": {
        "message": "You've been locked in for a while",
        "suggestion": "Body check: water? stretch?",
    },
    "hyperfocus_warning": {
        "message": "Deep focus is great, but it's been a while",
        "suggestion": "Set an exit point before you burn out",
    },

    # Break requests acknowledged
    "break_acknowledged": {
        "message": "Go for it",
        "suggestion": "I'll keep your place",
    },

    # Override acknowledged
    "override_acknowledged": {
        "message": "Got it, continuing",
        "note": "I'll check in again later",
    },
    "override_with_concern": {
        "message": "Okay, but I'm noting this",
        "note": "We can talk about what's driving this later",
    },
}


# =============================================================================
# CELEBRATION PHRASES - Dopamine hits for task completion
# =============================================================================

CELEBRATION_PHRASES: Dict[str, List[str]] = {
    "small_win": [
        "Nice.",
        "Got it.",
        "Done.",
        "Solid.",
    ],
    "medium_win": [
        "That's a win.",
        "Good progress.",
        "Knocked that out.",
        "Moving forward.",
    ],
    "big_win": [
        "Hell yeah.",
        "That was a big one.",
        "Major progress.",
        "You crushed that.",
    ],
    "milestone": [
        "That's a real milestone.",
        "Look at that. Actually done.",
        "This is worth celebrating.",
        "Remember this feeling.",
    ],
    "after_struggle": [
        "You got through it.",
        "That was hard. You did it anyway.",
        "The stuck part is behind you.",
        "Proof you can do hard things.",
    ],
}


# =============================================================================
# HANDOFF PHRASES - Session continuity messages
# =============================================================================

HANDOFF_PHRASES: Dict[str, str] = {
    "welcome_back": "Welcome back. Last time you were working on {task}.",
    "welcome_back_with_state": "Hey. Last session you were at {burnout} burnout, working on {task}.",
    "welcome_back_tired": "You left pretty tired last time. Feeling better?",
    "welcome_back_frustrated": "Last session got frustrating. Fresh start today?",
    "new_session": "Starting fresh. What are we working on?",
    "session_saved": "Session saved. Pick up anytime.",
    "session_saved_with_state": "Saved. You're at {burnout} energy, {progress}% through {task}.",
}


# =============================================================================
# OTTO ROLE PHRASES - Adjusted by otto_role preference
# =============================================================================

ROLE_ADJUSTED_PHRASES: Dict[str, Dict[str, str]] = {
    "guardian": {
        "break_suggestion": "Time for a break.",
        "override_response": "I hear you, but I think you need to stop.",
        "check_in": "How are you really doing?",
    },
    "companion": {
        "break_suggestion": "Break might be good?",
        "override_response": "Okay, your call. I'll note it.",
        "check_in": "Still good?",
    },
    "tool": {
        "break_suggestion": "FYI: {time} elapsed",
        "override_response": "Continuing.",
        "check_in": "",  # Tool mode doesn't check in
    },
}


# =============================================================================
# Validation
# =============================================================================

def contains_forbidden_word(text: str) -> bool:
    """Check if text contains any forbidden clinical terms."""
    text_lower = text.lower()
    for word in FORBIDDEN_WORDS:
        if word.lower() in text_lower:
            return True
    return False


def validate_phrase(text: str) -> tuple[bool, str]:
    """
    Validate that a phrase follows dignity-first guidelines.

    Returns:
        (is_valid, reason)
    """
    if contains_forbidden_word(text):
        return False, "Contains forbidden clinical language"
    return True, "OK"
