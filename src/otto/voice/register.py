"""
Register Detection for OTTO Voice System.

Detects communication style: casual, formal, venting, terse.

[He2025] ThinkingMachines Compliance:
- Pattern lists are sorted for deterministic iteration
- Classification uses fixed priority order
- Same input always produces same output
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


class Register(Enum):
    """Communication register levels."""
    CASUAL = "casual"       # bro, lol, lowercase, informal
    NEUTRAL = "neutral"     # Standard communication
    FORMAL = "formal"       # Professional, structured
    TERSE = "terse"         # Minimal words, flow state
    VENTING = "venting"     # Frustrated, caps, emotional


@dataclass
class RegisterSignals:
    """Signals extracted from user message."""
    casual_markers: int = 0
    formal_markers: int = 0
    venting_markers: int = 0
    message_length: int = 0
    word_count: int = 0
    has_punctuation: bool = False
    caps_ratio: float = 0.0
    has_emoji: bool = False
    has_exclamation_burst: bool = False  # !!! or similar


# [He2025] Sorted pattern lists for deterministic iteration
CASUAL_MARKERS = sorted([
    r'\bbro\b', r'\bbruh\b', r'\bdude\b',
    r'\blol\b', r'\blmao\b', r'\bhaha\b', r'\bheh\b',
    r'\bngl\b', r'\btbh\b', r'\bidk\b', r'\bimo\b', r'\brn\b',
    r'\bu\b', r'\bur\b', r'\br\b',  # u, ur, r
    r'\bpls\b', r'\bthx\b', r'\bty\b',
    r'\byeah\b', r'\byep\b', r'\bnope\b', r'\bnah\b',
    r'\bkinda\b', r'\bsorta\b', r'\bgonna\b', r'\bwanna\b',
    r'\bgotta\b', r'\blemme\b', r'\bdunno\b',
    r'\byo\b', r'\bsup\b', r'\bchill\b', r'\bcool\b',
    r'\blow key\b', r'\blowkey\b',
    r'\.{3,}',  # ...
    r'^[a-z]',  # Starts lowercase
])

FORMAL_MARKERS = sorted([
    r'\bplease\b', r'\bkindly\b',
    r'\bwould you\b', r'\bcould you\b', r'\bmay I\b',
    r'\bI would like\b', r'\bI am\b',
    r'\bregarding\b', r'\bpertaining\b', r'\bconcerning\b',
    r'\bassistance\b', r'\bfurthermore\b', r'\bhowever\b',
    r'\btherefore\b', r'\baccordingly\b',
    r'^[A-Z].*[.!?]$',  # Proper sentence with ending punctuation
])

VENTING_MARKERS = sorted([
    r'[A-Z]{3,}',        # CAPS
    r'!{2,}',            # !!
    r'\?{2,}',           # ??
    r'\bugh\b', r'\bargh\b',
    r'\bfuck\b', r'\bshit\b', r'\bdamn\b', r'\bcrap\b',
    r'\bhate\b', r'\bsucks\b', r'\bstupid\b',
    r'why (won\'?t|doesn\'?t|can\'?t|isn\'?t)',
    r'\bgive up\b', r'\bso frustrated\b',
    r'\bnothing works\b', r'\bbroken\b',
])


def detect_register(message: str) -> Tuple[Register, RegisterSignals]:
    """
    Detect register from message.

    [He2025] Deterministic: same input always produces same output.

    Args:
        message: User message to analyze

    Returns:
        Tuple of (Register, RegisterSignals)
    """
    signals = RegisterSignals()
    signals.message_length = len(message)
    words = message.split()
    signals.word_count = len(words)

    # Punctuation check
    signals.has_punctuation = bool(re.search(r'[.!?]$', message.strip()))

    # Caps ratio
    alpha = [c for c in message if c.isalpha()]
    if alpha:
        signals.caps_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)

    # Emoji detection
    signals.has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF]', message))

    # Exclamation burst detection (!! or more)
    signals.has_exclamation_burst = bool(re.search(r'!{2,}', message))

    # Count markers (deterministic iteration over sorted lists)
    for pattern in CASUAL_MARKERS:
        if re.search(pattern, message, re.IGNORECASE):
            signals.casual_markers += 1

    for pattern in FORMAL_MARKERS:
        if re.search(pattern, message, re.IGNORECASE):
            signals.formal_markers += 1

    for pattern in VENTING_MARKERS:
        if re.search(pattern, message):  # Case-sensitive for CAPS
            signals.venting_markers += 1

    # Classification (fixed priority order for determinism)
    register = _classify(signals)

    return register, signals


def _classify(signals: RegisterSignals) -> Register:
    """
    Classify register from signals.

    [He2025] Fixed priority order (first match wins):
    1. Venting (emotional override)
    2. Casual with strong markers (casual markers win over terse)
    3. Terse (structural override, only if no casual markers)
    4. Highest marker score
    5. Default based on length
    """
    # Priority 1: Strong venting signals (exclamation burst, high caps, or multiple markers)
    if signals.has_exclamation_burst or signals.caps_ratio > 0.5 or signals.venting_markers >= 2:
        return Register.VENTING

    # Priority 2: Casual markers can soften mild venting
    # "lol this is broken" = CASUAL (lol softens "broken")
    if signals.casual_markers >= 2:
        return Register.CASUAL

    # Priority 3: Single venting marker without casual softening = venting
    if signals.venting_markers >= 1:
        return Register.VENTING

    # Priority 3: Terse (very short, no casual markers)
    if signals.word_count <= 3 and signals.message_length < 20:
        return Register.TERSE

    # Priority 4: Highest marker count
    if signals.formal_markers > signals.casual_markers:
        return Register.FORMAL

    # Priority 5: Short without punctuation = casual
    if signals.word_count <= 8 and not signals.has_punctuation:
        return Register.CASUAL

    return Register.NEUTRAL


def get_register(message: str) -> Register:
    """Convenience function to get just the register."""
    register, _ = detect_register(message)
    return register


__all__ = [
    'Register',
    'RegisterSignals',
    'detect_register',
    'get_register',
    'CASUAL_MARKERS',
    'FORMAL_MARKERS',
    'VENTING_MARKERS',
]
