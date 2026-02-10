"""PRISM Stage 1 detector — local regex-based signal detection.

This is the fast path (<50ms target). It evaluates all patterns against
the input text in a fixed order (sorted by signal_type.name)
and returns detected signals sorted by confidence descending.

When multiple patterns match the same signal type, the highest-confidence
match is kept (deduplication by signal type).

Determinism guarantees:
    - Pattern evaluation order: fixed (sorted by signal_type.name, regex)
    - Output order: fixed (sorted by -confidence, then signal_type.name)
    - Same text → same signals, every time
"""

from __future__ import annotations

import re
from typing import Optional

from otto_v3.core.prism.signals import CognitiveSignal, Signal
from otto_v3.core.prism.patterns import PATTERNS


class PRISMDetector:
    """Stage 1 cognitive signal detector.

    Evaluates regex patterns against input text and returns detected
    signals. Stateless — all state lives in the patterns tuple and
    the input text. No side effects.
    """

    def detect(self, text: str) -> list[Signal]:
        """Detect all cognitive signals in the input text.

        Evaluates every pattern in PATTERNS (fixed order). When multiple
        patterns match the same signal type, only the highest-confidence
        match is retained. Output is sorted by confidence descending,
        with signal_type.name as tiebreaker for determinism.

        Args:
            text: Raw input text to analyze.

        Returns:
            List of Signal objects, sorted by confidence descending.
            Empty list if no patterns match or text is empty.
        """
        if not text or not text.strip():
            return []

        # Collect matches, keyed by signal type for dedup.
        # When a signal type matches multiple patterns, keep highest confidence.
        best_by_type: dict[CognitiveSignal, float] = {}

        for pattern in PATTERNS:
            if re.search(pattern.regex, text):
                current_best = best_by_type.get(pattern.signal_type, -1.0)
                if pattern.base_confidence > current_best:
                    best_by_type[pattern.signal_type] = pattern.base_confidence

        # Build Signal objects — iterate in sorted order for
        signals: list[Signal] = []
        for signal_type in sorted(best_by_type.keys(), key=lambda s: s.name):
            signals.append(Signal(
                type=signal_type,
                confidence=best_by_type[signal_type],
                source="local_pattern",
            ))

        # Sort by confidence descending; tiebreak by signal name ascending
        signals.sort(key=lambda s: (-s.confidence, s.type.name))

        return signals

    def detect_primary(self, text: str) -> Optional[Signal]:
        """Return the highest-confidence signal, or None.

        Convenience method for routing code that only needs the
        dominant signal.

        Args:
            text: Raw input text to analyze.

        Returns:
            The highest-confidence Signal, or None if nothing detected.
        """
        signals = self.detect(text)
        return signals[0] if signals else None

    def detect_types(self, text: str) -> set[CognitiveSignal]:
        """Return just the signal types detected (no confidence/metadata).

        Useful for quick checks like "is the user frustrated?"
        without needing the full Signal objects.

        Args:
            text: Raw input text to analyze.

        Returns:
            Set of CognitiveSignal types found in the text.
        """
        return {signal.type for signal in self.detect(text)}
