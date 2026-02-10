"""Detection patterns — regex-to-signal mappings for Stage 1.

Each pattern maps a compiled regex to a CognitiveSignal with a base
confidence score. The PATTERNS list is sorted by signal_type.name
for determinism — evaluation order is fixed and reproducible.

Pattern design principles:
    - Case-insensitive matching ((?i) flag in regex)
    - Patterns should be specific enough to avoid false positives
    - Base confidence reflects pattern reliability (0.0–1.0)
    - Multiple patterns can map to the same signal type
"""

from __future__ import annotations

from dataclasses import dataclass

from otto_v3.core.prism.signals import CognitiveSignal


@dataclass(frozen=True)
class DetectionPattern:
    """A single regex → signal mapping.

    Frozen because patterns are static configuration — they define
    the detection vocabulary and must not change at runtime.

    Attributes:
        regex: Regular expression pattern string.
        signal_type: Which cognitive signal this pattern detects.
        base_confidence: How reliable this pattern is (0.0–1.0).
    """

    regex: str
    signal_type: CognitiveSignal
    base_confidence: float


# ---------------------------------------------------------------------------
# Master pattern list — SORTED by signal_type.name for
# ---------------------------------------------------------------------------
# This list is built unsorted for readability, then sorted at module
# level. The sorted() call ensures deterministic evaluation order
# regardless of how patterns are added or reordered in source.

_UNSORTED_PATTERNS: list[DetectionPattern] = [
    # --- FRUSTRATED ---
    DetectionPattern(
        r"(?i)\b(ugh|argh|damn|dammit|crap)\b",
        CognitiveSignal.FRUSTRATED,
        0.75,
    ),
    DetectionPattern(
        r"[A-Z]{3,}",
        CognitiveSignal.FRUSTRATED,
        0.60,
    ),
    DetectionPattern(
        r"(?i)(this is broken|nothing works|keeps failing)",
        CognitiveSignal.FRUSTRATED,
        0.80,
    ),
    DetectionPattern(
        r"[!?]{2,}",
        CognitiveSignal.FRUSTRATED,
        0.55,
    ),

    # --- OVERWHELMED ---
    DetectionPattern(
        r"(?i)(too much|overwhelm|can't handle|drowning in)",
        CognitiveSignal.OVERWHELMED,
        0.80,
    ),
    DetectionPattern(
        r"(?i)(where do I (even )?start|so many things)",
        CognitiveSignal.OVERWHELMED,
        0.70,
    ),

    # --- DEPLETED ---
    DetectionPattern(
        r"(?i)\b(tired|exhausted|done for today|burned out|wiped)\b",
        CognitiveSignal.DEPLETED,
        0.75,
    ),
    DetectionPattern(
        r"(?i)(can't think|brain fog|need a break)",
        CognitiveSignal.DEPLETED,
        0.80,
    ),

    # --- STUCK ---
    DetectionPattern(
        r"(?i)\b(stuck|blocked|don't know how|no idea)\b",
        CognitiveSignal.STUCK,
        0.70,
    ),
    DetectionPattern(
        r"(?i)(tried everything|nothing works|going in circles)",
        CognitiveSignal.STUCK,
        0.75,
    ),

    # --- EXPLORING ---
    DetectionPattern(
        r"(?i)(what if|I wonder|could we|what about|how about)",
        CognitiveSignal.EXPLORING,
        0.65,
    ),
    DetectionPattern(
        r"(?i)(brainstorm|explore|experiment|play with)",
        CognitiveSignal.EXPLORING,
        0.70,
    ),

    # --- FOCUSED ---
    DetectionPattern(
        r"(?i)(let's do this|ready to go|focused on|working on)",
        CognitiveSignal.FOCUSED,
        0.65,
    ),

    # --- HYPERFOCUS ---
    DetectionPattern(
        r"(?i)(one more thing|can't stop|in the zone|keep going)",
        CognitiveSignal.HYPERFOCUS,
        0.60,
    ),

    # --- CRASHED ---
    DetectionPattern(
        r"(?i)(I give up|can't do this|shutting down|I quit)",
        CognitiveSignal.CRASHED,
        0.85,
    ),

    # --- COMMITMENT_OUTBOUND ---
    DetectionPattern(
        r"(?i)(I'll|I will|I can)\b.*\bby\s+\w+day",
        CognitiveSignal.COMMITMENT_OUTBOUND,
        0.70,
    ),
    DetectionPattern(
        r"(?i)(I'll|I will)\b.*\b(send|deliver|finish|complete)",
        CognitiveSignal.COMMITMENT_OUTBOUND,
        0.65,
    ),

    # --- COMMITMENT_INBOUND ---
    DetectionPattern(
        r"(?i)(can you|could you|please)\b.*\bby\s+\w+day",
        CognitiveSignal.COMMITMENT_INBOUND,
        0.65,
    ),

    # --- MEETING_REQUEST ---
    DetectionPattern(
        r"(?i)(let's meet|we should meet|schedule a|set up a call)",
        CognitiveSignal.MEETING_REQUEST,
        0.70,
    ),

    # --- TASK_IMPLIED ---
    DetectionPattern(
        r"(?i)(I need to|I have to|I should|I gotta|must)\b.*\b\w+",
        CognitiveSignal.TASK_IMPLIED,
        0.60,
    ),

    # --- FOLLOW_UP_NEEDED ---
    DetectionPattern(
        r"(?i)(get back to you|follow up|circle back|let me check)",
        CognitiveSignal.FOLLOW_UP_NEEDED,
        0.65,
    ),

    # --- DECISION_MADE ---
    DetectionPattern(
        r"(?i)(let's go with|decided on|going with|I choose|we'll use)",
        CognitiveSignal.DECISION_MADE,
        0.70,
    ),

    # --- LOW_ENERGY ---
    DetectionPattern(
        r"(?i)\b(slow|sluggish|low energy|dragging)\b",
        CognitiveSignal.LOW_ENERGY,
        0.60,
    ),

    # --- HIGH_ENERGY ---
    DetectionPattern(
        r"(?i)\b(pumped|energized|fired up|let's go|hyped)\b",
        CognitiveSignal.HIGH_ENERGY,
        0.65,
    ),

    # --- CONTEXT_SWITCH ---
    DetectionPattern(
        r"(?i)(actually|wait|hold on|switching to|different topic)",
        CognitiveSignal.CONTEXT_SWITCH,
        0.55,
    ),

    # --- CRASH_ZONE_APPROACHING ---
    DetectionPattern(
        r"(?i)(losing focus|starting to fade|getting tired|winding down)",
        CognitiveSignal.CRASH_ZONE_APPROACHING,
        0.65,
    ),
]

# CRITICAL: Sort by signal_type.name for deterministic evaluation order.
# This sort is performed ONCE at module load time.
PATTERNS: tuple[DetectionPattern, ...] = tuple(
    sorted(_UNSORTED_PATTERNS, key=lambda p: (p.signal_type.name, p.regex))
)
