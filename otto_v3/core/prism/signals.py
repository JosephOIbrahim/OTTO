"""Cognitive signal types — the vocabulary of PRISM detection.

Every detectable cognitive state, action, and ambient signal is
enumerated here. The enum uses auto() for values since the integer
values are opaque — only the names matter for routing.

Signals are grouped logically but the enum is flat. Grouping is
documented in comments; the NEXUS router uses signal identity
(not grouping) for expert selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto


class CognitiveSignal(Enum):
    """All detectable cognitive signals.

    Grouped by category but stored in a single flat enum so that
    pattern matching and routing remain simple.
    """

    # --- Primary cognitive states ---
    FRUSTRATED = auto()
    OVERWHELMED = auto()
    DEPLETED = auto()
    STUCK = auto()
    EXPLORING = auto()
    FOCUSED = auto()
    HYPERFOCUS = auto()
    CRASHED = auto()

    # --- Action signals (commitment tracking) ---
    COMMITMENT_OUTBOUND = auto()   # "I'll send that by Friday"
    COMMITMENT_INBOUND = auto()    # "Can you get me X by Tuesday?"
    MEETING_REQUEST = auto()       # "We should meet about this"
    TASK_IMPLIED = auto()          # "I need to update the docs"
    FOLLOW_UP_NEEDED = auto()      # "Let me get back to you"
    DECISION_MADE = auto()         # "Let's go with option B"

    # --- Ambient signals ---
    LOW_ENERGY = auto()
    HIGH_ENERGY = auto()
    CONTEXT_SWITCH = auto()
    EXTENDED_MEETINGS = auto()
    CRASH_ZONE_APPROACHING = auto()


@dataclass(frozen=True)
class Signal:
    """A detected cognitive signal with confidence and provenance.

    Frozen because detected signals are facts about the input — they
    should not be mutated after detection. Downstream routing reads
    signals; it never writes them.

    Attributes:
        type: Which cognitive signal was detected.
        confidence: Detection confidence (0.0–1.0).
        source: Where this detection came from ("local_pattern",
            "server_llm", "ambient_sensor", etc.).
        timestamp: When detection occurred (UTC).
    """

    type: CognitiveSignal
    confidence: float
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
