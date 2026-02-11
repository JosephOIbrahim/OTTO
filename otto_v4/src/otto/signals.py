"""PRISM signal detection for OTTO v5.0.

Classifies input messages into cognitive signals. Wraps the existing
detector.py for commitment signals and adds pattern-based detection
for cognitive state signals (frustrated, depleted, stuck, etc.).

Two detection paths:
  1. Content signals: commitment, deadline, meeting (from message text)
  2. Behavioral signals: frustrated, depleted, burst (from patterns)

Usage:
    signals = detect_signals(message)
    # -> [Signal(type=COMMITMENT_DETECTED, confidence=0.9), ...]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal


class SignalType(Enum):
    """All signal types PRISM can detect."""

    # Action signals (content-based)
    COMMITMENT_DETECTED = "commitment_detected"
    ACTION_REQUIRED = "action_required"
    MEETING_PROPOSED = "meeting_proposed"
    DEADLINE_MENTIONED = "deadline_mentioned"

    # Cognitive state signals (pattern-based)
    FRUSTRATED = "frustrated"
    OVERWHELMED = "overwhelmed"
    DEPLETED = "depleted"
    STUCK = "stuck"
    EXPLORING = "exploring"
    FOCUSED = "focused"

    # Alert signals (behavioral)
    BURST_DETECTED = "burst_detected"
    CRASH_ZONE = "crash_zone"
    SPIRAL = "spiral"
    NUDGE_FATIGUE = "nudge_fatigue"


@dataclass(frozen=True)
class Signal:
    """A detected signal with type, confidence, and source evidence."""

    type: SignalType
    confidence: float  # 0.0 to 1.0
    source: Literal["content", "pattern", "behavioral"] = "content"
    evidence: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")


# ---------------------------------------------------------------------------
# Pattern-based detection (no API call needed)
# ---------------------------------------------------------------------------

# Frustrated: caps, negativity, repeated punctuation
_FRUSTRATED_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"[A-Z]{4,}"), 0.7, "extended caps"),
    (re.compile(r"[!?]{3,}"), 0.6, "repeated punctuation"),
    (re.compile(r"\b(ugh|argh|damn|fuck|shit|hate)\b", re.IGNORECASE), 0.8, "frustration keyword"),
    (re.compile(r"\b(can'?t|won'?t|impossible|give up|giving up)\b", re.IGNORECASE), 0.7, "defeat language"),
    (re.compile(r"\bthis (doesn'?t|isn'?t) work", re.IGNORECASE), 0.6, "broken statement"),
]

# Overwhelmed: too much, don't know where to start
_OVERWHELMED_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\btoo (much|many|overwhelm)", re.IGNORECASE), 0.8, "too much"),
    (re.compile(r"\bdon'?t know where to (start|begin)\b", re.IGNORECASE), 0.9, "no starting point"),
    (re.compile(r"\b(everything|all of it) at once\b", re.IGNORECASE), 0.7, "everything at once"),
    (re.compile(r"\b(drowning|swamped|buried)\b", re.IGNORECASE), 0.7, "overwhelm metaphor"),
]

# Depleted: short messages, tiredness
_DEPLETED_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\b(tired|exhausted|drained|burnt out|burned out)\b", re.IGNORECASE), 0.8, "fatigue keyword"),
    (re.compile(r"\b(can'?t think|brain fog|done for today)\b", re.IGNORECASE), 0.9, "cognitive fatigue"),
    (re.compile(r"\b(no energy|low energy|running on empty)\b", re.IGNORECASE), 0.8, "energy keyword"),
]

# Stuck: repetition, asking for help
_STUCK_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\b(stuck|blocked|stalled)\b", re.IGNORECASE), 0.8, "stuck keyword"),
    (re.compile(r"\b(don'?t (know|understand)|confused|lost)\b", re.IGNORECASE), 0.7, "confusion"),
    (re.compile(r"\bhelp\b", re.IGNORECASE), 0.5, "help request"),
    (re.compile(r"\bwhat (do I|should I|am I)\b", re.IGNORECASE), 0.6, "seeking direction"),
]

# Exploring: what-if, curiosity
_EXPLORING_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\bwhat if\b", re.IGNORECASE), 0.8, "what-if"),
    (re.compile(r"\bI wonder\b", re.IGNORECASE), 0.7, "wondering"),
    (re.compile(r"\bcould we\b", re.IGNORECASE), 0.6, "possibility"),
    (re.compile(r"\bwhat about\b", re.IGNORECASE), 0.6, "alternative"),
    (re.compile(r"\b(explore|brainstorm|think about)\b", re.IGNORECASE), 0.7, "exploration verb"),
]

# Focused: clear directives
_FOCUSED_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\b(let'?s|do it|go ahead|proceed|next)\b", re.IGNORECASE), 0.6, "action directive"),
    (re.compile(r"\bmark .+ (done|complete)\b", re.IGNORECASE), 0.8, "completion directive"),
    (re.compile(r"\badd .+ to\b", re.IGNORECASE), 0.6, "add directive"),
]

# Deadline: date mentions
_DEADLINE_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\bby (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE), 0.8, "day-of-week deadline"),
    (re.compile(r"\bby (tomorrow|tonight|end of (day|week|month))\b", re.IGNORECASE), 0.9, "relative deadline"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), 0.9, "ISO date"),
    (re.compile(r"\bdue (date|on|by)\b", re.IGNORECASE), 0.7, "due keyword"),
]

# Meeting: scheduling language
_MEETING_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\b(meet|meeting|call|sync|catch up)\b", re.IGNORECASE), 0.6, "meeting keyword"),
    (re.compile(r"\bschedule\b", re.IGNORECASE), 0.7, "schedule keyword"),
    (re.compile(r"\bat \d{1,2}(:\d{2})?\s*(am|pm)\b", re.IGNORECASE), 0.8, "time mention"),
]

# Commitment: promise language
_COMMITMENT_PATTERNS: list[tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\bI'?ll\b", re.IGNORECASE), 0.7, "I'll promise"),
    (re.compile(r"\bI will\b", re.IGNORECASE), 0.7, "I will promise"),
    (re.compile(r"\bI need to\b", re.IGNORECASE), 0.6, "I need to"),
    (re.compile(r"\bI (have to|gotta|must)\b", re.IGNORECASE), 0.6, "obligation"),
    (re.compile(r"\bpromise\b", re.IGNORECASE), 0.9, "promise keyword"),
    (re.compile(r"\bremind me to\b", re.IGNORECASE), 0.9, "remind request"),
]


_ALL_PATTERNS: list[tuple[SignalType, list[tuple[re.Pattern[str], float, str]]]] = [
    (SignalType.FRUSTRATED, _FRUSTRATED_PATTERNS),
    (SignalType.OVERWHELMED, _OVERWHELMED_PATTERNS),
    (SignalType.DEPLETED, _DEPLETED_PATTERNS),
    (SignalType.STUCK, _STUCK_PATTERNS),
    (SignalType.EXPLORING, _EXPLORING_PATTERNS),
    (SignalType.FOCUSED, _FOCUSED_PATTERNS),
    (SignalType.DEADLINE_MENTIONED, _DEADLINE_PATTERNS),
    (SignalType.MEETING_PROPOSED, _MEETING_PATTERNS),
    (SignalType.COMMITMENT_DETECTED, _COMMITMENT_PATTERNS),
]


def detect_signals(
    message: str,
    *,
    threshold: float = 0.5,
) -> list[Signal]:
    """Detect cognitive and action signals from a message.

    Scans the message against pattern banks and returns all signals
    whose confidence meets the threshold. Deterministic: same message
    always produces the same signals in the same order.

    Parameters
    ----------
    message:
        The user's message text.
    threshold:
        Minimum confidence to include a signal (default 0.5).

    Returns
    -------
    list[Signal]
        Signals sorted by confidence descending, then by SignalType
        name for deterministic ordering.
    """
    if not message or not message.strip():
        return []

    detected: list[Signal] = []

    for signal_type, patterns in _ALL_PATTERNS:
        best_confidence = 0.0
        best_evidence = ""

        for pattern, confidence, evidence in patterns:
            if pattern.search(message):
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_evidence = evidence

        if best_confidence >= threshold:
            detected.append(Signal(
                type=signal_type,
                confidence=best_confidence,
                source="pattern",
                evidence=best_evidence,
            ))

    # Short message heuristic: < 10 chars suggests depleted
    stripped = message.strip()
    if 0 < len(stripped) <= 10 and not any(
        s.type == SignalType.FOCUSED for s in detected
    ):
        detected.append(Signal(
            type=SignalType.DEPLETED,
            confidence=0.5,
            source="pattern",
            evidence="very short message",
        ))

    # Deterministic sort: confidence desc, then type name asc
    detected.sort(key=lambda s: (-s.confidence, s.type.name))

    return detected


def detect_action_signals(message: str) -> list[Signal]:
    """Detect only action signals (commitment, deadline, meeting).

    Convenience wrapper for routing decisions that only care about
    actionable signals, not cognitive state.
    """
    all_signals = detect_signals(message)
    action_types = {
        SignalType.COMMITMENT_DETECTED,
        SignalType.DEADLINE_MENTIONED,
        SignalType.MEETING_PROPOSED,
        SignalType.ACTION_REQUIRED,
    }
    return [s for s in all_signals if s.type in action_types]


def detect_cognitive_signals(message: str) -> list[Signal]:
    """Detect only cognitive state signals.

    Convenience wrapper for routing decisions about user wellbeing.
    """
    all_signals = detect_signals(message)
    cognitive_types = {
        SignalType.FRUSTRATED,
        SignalType.OVERWHELMED,
        SignalType.DEPLETED,
        SignalType.STUCK,
        SignalType.EXPLORING,
        SignalType.FOCUSED,
    }
    return [s for s in all_signals if s.type in cognitive_types]


# ---------------------------------------------------------------------------
# Behavioral pattern detection (Phase 2.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InteractionRecord:
    """A single interaction's metadata for behavioral analysis.

    Records are lightweight — just enough to detect patterns without
    storing message content (privacy by design).
    """

    timestamp: datetime
    message_length: int
    source: str = "cli"  # "cli", "whatsapp", "agent"


# Tuning constants for behavioral detection
_BURST_WINDOW_SECONDS: float = 120.0  # 2 minutes
_BURST_MIN_MESSAGES: int = 4
_CRASH_SILENCE_SECONDS: float = 600.0  # 10 minutes after burst
_DECLINING_LENGTH_WINDOW: int = 5  # last N messages
_DECLINING_LENGTH_RATIO: float = 0.4  # final must be < 40% of initial


class HistoryAnalyzer:
    """Detect behavioral signals from interaction history.

    Operates on a list of InteractionRecord — pure analysis with no
    I/O. The caller is responsible for loading/storing records.

    Behavioral signals detected:
      - DEPLETED: message lengths declining over recent window
      - BURST_DETECTED: many messages in a short window
      - CRASH_ZONE: burst followed by silence (current time well after last msg)

    Deterministic: same records + same now → same signals.
    """

    def analyze(
        self,
        records: list[InteractionRecord],
        *,
        now: datetime | None = None,
        threshold: float = 0.5,
    ) -> list[Signal]:
        """Analyze interaction history for behavioral patterns.

        Parameters
        ----------
        records:
            Interaction records sorted by timestamp ascending.
        now:
            Current time for silence detection. Defaults to utcnow.
        threshold:
            Minimum confidence to include a signal.

        Returns
        -------
        list[Signal]
            Behavioral signals sorted by confidence desc, type name asc.
        """
        if len(records) < 2:
            return []

        if now is None:
            now = datetime.now(timezone.utc)

        detected: list[Signal] = []

        # --- Declining message length → DEPLETED ---
        depleted_signal = self._check_declining_length(records)
        if depleted_signal is not None and depleted_signal.confidence >= threshold:
            detected.append(depleted_signal)

        # --- Burst detection → BURST_DETECTED ---
        burst_signal = self._check_burst(records)
        if burst_signal is not None and burst_signal.confidence >= threshold:
            detected.append(burst_signal)

            # --- Crash zone: burst then silence → CRASH_ZONE ---
            crash_signal = self._check_crash_zone(records, now)
            if crash_signal is not None and crash_signal.confidence >= threshold:
                detected.append(crash_signal)

        detected.sort(key=lambda s: (-s.confidence, s.type.name))
        return detected

    @staticmethod
    def _check_declining_length(
        records: list[InteractionRecord],
    ) -> Signal | None:
        """Detect declining message lengths over recent messages."""
        window = records[-_DECLINING_LENGTH_WINDOW:]
        if len(window) < 3:
            return None

        lengths = [r.message_length for r in window]
        first_avg = sum(lengths[:2]) / 2
        last_avg = sum(lengths[-2:]) / 2

        if first_avg <= 0:
            return None

        ratio = last_avg / first_avg
        if ratio < _DECLINING_LENGTH_RATIO:
            confidence = min(1.0, 1.0 - ratio)
            return Signal(
                type=SignalType.DEPLETED,
                confidence=round(confidence, 2),
                source="behavioral",
                evidence=f"message length declined to {ratio:.0%} of initial",
            )
        return None

    @staticmethod
    def _check_burst(records: list[InteractionRecord]) -> Signal | None:
        """Detect rapid-fire messaging (many messages in short window)."""
        if len(records) < _BURST_MIN_MESSAGES:
            return None

        recent = records[-_BURST_MIN_MESSAGES:]
        span = (recent[-1].timestamp - recent[0].timestamp).total_seconds()

        if span <= 0:
            # All same timestamp — treat as burst
            return Signal(
                type=SignalType.BURST_DETECTED,
                confidence=0.9,
                source="behavioral",
                evidence=f"{len(recent)} messages at same timestamp",
            )

        if span <= _BURST_WINDOW_SECONDS:
            # Scale confidence: shorter span = higher confidence
            confidence = min(0.95, 0.6 + 0.3 * (1 - span / _BURST_WINDOW_SECONDS))
            return Signal(
                type=SignalType.BURST_DETECTED,
                confidence=round(confidence, 2),
                source="behavioral",
                evidence=f"{len(recent)} messages in {span:.0f}s",
            )
        return None

    @staticmethod
    def _check_crash_zone(
        records: list[InteractionRecord],
        now: datetime,
    ) -> Signal | None:
        """Detect silence after a burst (crash zone)."""
        last = records[-1]
        silence = (now - last.timestamp).total_seconds()

        if silence >= _CRASH_SILENCE_SECONDS:
            confidence = min(0.95, 0.6 + 0.2 * (silence / _CRASH_SILENCE_SECONDS))
            return Signal(
                type=SignalType.CRASH_ZONE,
                confidence=round(confidence, 2),
                source="behavioral",
                evidence=f"{silence:.0f}s silence after burst",
            )
        return None
