"""Tests for PRISM signal detection — Day 3 of OTTO OS v3.0.

These tests verify:
1. Known text → correct signal type detection
2. Confidence ordering (highest first)
3. Caps/punctuation detection for FRUSTRATED
4. Multiple signals from complex text
5. Empty/whitespace text → empty list
6. Determinism (same text → same signals, 100x)
7. Deduplication (best confidence per signal type)
8. Pattern list is properly sorted for [He2025]
9. Action signal detection (commitments, meetings, etc.)
"""

from __future__ import annotations

import pytest

from otto.core.prism.signals import CognitiveSignal, Signal
from otto.core.prism.patterns import DetectionPattern, PATTERNS
from otto.core.prism.detector import PRISMDetector


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def detector() -> PRISMDetector:
    return PRISMDetector()


# ===================================================================
# Test: CognitiveSignal enum
# ===================================================================

class TestCognitiveSignal:
    """Signal enum must have all expected values."""

    def test_has_primary_states(self) -> None:
        primary = {
            CognitiveSignal.FRUSTRATED,
            CognitiveSignal.OVERWHELMED,
            CognitiveSignal.DEPLETED,
            CognitiveSignal.STUCK,
            CognitiveSignal.EXPLORING,
            CognitiveSignal.FOCUSED,
            CognitiveSignal.HYPERFOCUS,
            CognitiveSignal.CRASHED,
        }
        assert primary.issubset(set(CognitiveSignal))

    def test_has_action_signals(self) -> None:
        actions = {
            CognitiveSignal.COMMITMENT_OUTBOUND,
            CognitiveSignal.COMMITMENT_INBOUND,
            CognitiveSignal.MEETING_REQUEST,
            CognitiveSignal.TASK_IMPLIED,
            CognitiveSignal.FOLLOW_UP_NEEDED,
            CognitiveSignal.DECISION_MADE,
        }
        assert actions.issubset(set(CognitiveSignal))

    def test_has_ambient_signals(self) -> None:
        ambient = {
            CognitiveSignal.LOW_ENERGY,
            CognitiveSignal.HIGH_ENERGY,
            CognitiveSignal.CONTEXT_SWITCH,
            CognitiveSignal.EXTENDED_MEETINGS,
            CognitiveSignal.CRASH_ZONE_APPROACHING,
        }
        assert ambient.issubset(set(CognitiveSignal))

    def test_total_signal_count(self) -> None:
        """8 primary + 6 action + 5 ambient = 19 signals."""
        assert len(CognitiveSignal) == 19


# ===================================================================
# Test: Signal dataclass
# ===================================================================

class TestSignal:
    """Signal must be frozen with correct fields."""

    def test_is_frozen(self) -> None:
        import dataclasses
        sig = Signal(
            type=CognitiveSignal.FOCUSED,
            confidence=0.8,
            source="test",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            sig.confidence = 0.5  # type: ignore[misc]

    def test_has_timestamp(self) -> None:
        sig = Signal(
            type=CognitiveSignal.FOCUSED,
            confidence=0.8,
            source="test",
        )
        assert sig.timestamp is not None


# ===================================================================
# Test: Patterns [He2025] compliance
# ===================================================================

class TestPatterns:
    """Pattern list must be sorted and well-formed."""

    def test_patterns_sorted_by_signal_name(self) -> None:
        """[He2025]: Patterns MUST be sorted by signal_type.name."""
        names = [(p.signal_type.name, p.regex) for p in PATTERNS]
        assert names == sorted(names)

    def test_patterns_is_tuple(self) -> None:
        """Tuple, not list — immutable at runtime."""
        assert isinstance(PATTERNS, tuple)

    def test_all_patterns_are_frozen(self) -> None:
        for p in PATTERNS:
            assert isinstance(p, DetectionPattern)

    def test_all_confidences_in_range(self) -> None:
        for p in PATTERNS:
            assert 0.0 < p.base_confidence <= 1.0, (
                f"Pattern {p.regex} has out-of-range confidence {p.base_confidence}"
            )

    def test_all_regexes_compile(self) -> None:
        """Every regex must be valid."""
        import re
        for p in PATTERNS:
            try:
                re.compile(p.regex)
            except re.error as e:
                pytest.fail(f"Pattern {p.regex!r} fails to compile: {e}")

    def test_no_empty_regexes(self) -> None:
        for p in PATTERNS:
            assert p.regex.strip(), "Empty regex found in PATTERNS"


# ===================================================================
# Test: Detector — primary cognitive states
# ===================================================================

class TestDetectPrimaryStates:
    """Specific text must trigger the expected cognitive signals."""

    def test_frustrated_from_expletive(self, detector: PRISMDetector) -> None:
        signals = detector.detect("ugh this is so annoying")
        types = {s.type for s in signals}
        assert CognitiveSignal.FRUSTRATED in types

    def test_frustrated_from_caps(self, detector: PRISMDetector) -> None:
        signals = detector.detect("WHY DOES THIS KEEP HAPPENING")
        types = {s.type for s in signals}
        assert CognitiveSignal.FRUSTRATED in types

    def test_frustrated_from_broken(self, detector: PRISMDetector) -> None:
        result = detector.detect("this is broken and nothing works")
        types = {s.type for s in result}
        assert CognitiveSignal.FRUSTRATED in types

    def test_frustrated_from_punctuation(self, detector: PRISMDetector) -> None:
        result = detector.detect("what is going on?!?!")
        types = {s.type for s in result}
        assert CognitiveSignal.FRUSTRATED in types

    def test_stuck_from_keyword(self, detector: PRISMDetector) -> None:
        result = detector.detect("I'm stuck on this problem")
        types = {s.type for s in result}
        assert CognitiveSignal.STUCK in types

    def test_stuck_from_blocked(self, detector: PRISMDetector) -> None:
        result = detector.detect("completely blocked, don't know how to proceed")
        types = {s.type for s in result}
        assert CognitiveSignal.STUCK in types

    def test_overwhelmed(self, detector: PRISMDetector) -> None:
        result = detector.detect("there's too much to do, I can't handle all of this")
        types = {s.type for s in result}
        assert CognitiveSignal.OVERWHELMED in types

    def test_depleted(self, detector: PRISMDetector) -> None:
        result = detector.detect("I'm exhausted, need a break")
        types = {s.type for s in result}
        assert CognitiveSignal.DEPLETED in types

    def test_exploring(self, detector: PRISMDetector) -> None:
        result = detector.detect("what if we tried a different approach?")
        types = {s.type for s in result}
        assert CognitiveSignal.EXPLORING in types

    def test_focused(self, detector: PRISMDetector) -> None:
        result = detector.detect("ready to go, let's do this")
        types = {s.type for s in result}
        assert CognitiveSignal.FOCUSED in types

    def test_hyperfocus(self, detector: PRISMDetector) -> None:
        result = detector.detect("one more thing, I can't stop now")
        types = {s.type for s in result}
        assert CognitiveSignal.HYPERFOCUS in types

    def test_crashed(self, detector: PRISMDetector) -> None:
        result = detector.detect("I give up, I can't do this anymore")
        types = {s.type for s in result}
        assert CognitiveSignal.CRASHED in types


# ===================================================================
# Test: Detector — action signals
# ===================================================================

class TestDetectActionSignals:
    """Action signals detect commitments, meetings, tasks, decisions."""

    def test_commitment_outbound(self, detector: PRISMDetector) -> None:
        result = detector.detect("I'll send the report by Friday")
        types = {s.type for s in result}
        assert CognitiveSignal.COMMITMENT_OUTBOUND in types

    def test_commitment_inbound(self, detector: PRISMDetector) -> None:
        result = detector.detect("can you finish the review by Monday")
        types = {s.type for s in result}
        assert CognitiveSignal.COMMITMENT_INBOUND in types

    def test_meeting_request(self, detector: PRISMDetector) -> None:
        result = detector.detect("let's meet to discuss the architecture")
        types = {s.type for s in result}
        assert CognitiveSignal.MEETING_REQUEST in types

    def test_task_implied(self, detector: PRISMDetector) -> None:
        result = detector.detect("I need to update the documentation")
        types = {s.type for s in result}
        assert CognitiveSignal.TASK_IMPLIED in types

    def test_follow_up_needed(self, detector: PRISMDetector) -> None:
        result = detector.detect("let me get back to you on that")
        types = {s.type for s in result}
        assert CognitiveSignal.FOLLOW_UP_NEEDED in types

    def test_decision_made(self, detector: PRISMDetector) -> None:
        result = detector.detect("let's go with option B, decided on that")
        types = {s.type for s in result}
        assert CognitiveSignal.DECISION_MADE in types


# ===================================================================
# Test: Detector — ambient signals
# ===================================================================

class TestDetectAmbientSignals:
    """Ambient signals detect energy levels and context changes."""

    def test_low_energy(self, detector: PRISMDetector) -> None:
        result = detector.detect("feeling really sluggish today")
        types = {s.type for s in result}
        assert CognitiveSignal.LOW_ENERGY in types

    def test_high_energy(self, detector: PRISMDetector) -> None:
        result = detector.detect("I'm so pumped, let's go")
        types = {s.type for s in result}
        assert CognitiveSignal.HIGH_ENERGY in types

    def test_context_switch(self, detector: PRISMDetector) -> None:
        result = detector.detect("actually, hold on, different topic")
        types = {s.type for s in result}
        assert CognitiveSignal.CONTEXT_SWITCH in types

    def test_crash_zone_approaching(self, detector: PRISMDetector) -> None:
        result = detector.detect("I'm starting to fade, losing focus")
        types = {s.type for s in result}
        assert CognitiveSignal.CRASH_ZONE_APPROACHING in types


# ===================================================================
# Test: Detector — edge cases
# ===================================================================

class TestDetectEdgeCases:
    """Edge cases: empty input, no matches, whitespace."""

    def test_empty_string(self, detector: PRISMDetector) -> None:
        assert detector.detect("") == []

    def test_whitespace_only(self, detector: PRISMDetector) -> None:
        assert detector.detect("   \n\t  ") == []

    def test_no_matches(self, detector: PRISMDetector) -> None:
        result = detector.detect("the weather is nice today")
        # May or may not match — but should not crash
        assert isinstance(result, list)

    def test_detect_primary_empty(self, detector: PRISMDetector) -> None:
        assert detector.detect_primary("") is None

    def test_detect_primary_returns_highest(self, detector: PRISMDetector) -> None:
        # "I give up" → CRASHED at 0.85 confidence
        result = detector.detect_primary("I give up")
        assert result is not None
        assert result.type == CognitiveSignal.CRASHED

    def test_detect_types_returns_set(self, detector: PRISMDetector) -> None:
        result = detector.detect_types("I'm stuck and exhausted")
        assert isinstance(result, set)
        assert CognitiveSignal.STUCK in result
        assert CognitiveSignal.DEPLETED in result


# ===================================================================
# Test: Detector — confidence ordering
# ===================================================================

class TestDetectConfidenceOrdering:
    """Signals must be sorted by confidence descending."""

    def test_sorted_by_confidence_desc(self, detector: PRISMDetector) -> None:
        result = detector.detect("I'm stuck and tired, what if we try something new")
        if len(result) >= 2:
            for i in range(len(result) - 1):
                assert result[i].confidence >= result[i + 1].confidence, (
                    f"Signal {result[i].type.name} ({result[i].confidence}) "
                    f"should be >= {result[i+1].type.name} ({result[i+1].confidence})"
                )

    def test_tiebreaker_is_signal_name(self, detector: PRISMDetector) -> None:
        """When confidence ties, earlier alphabetical signal name wins."""
        result = detector.detect("I'm stuck and tired, what if we try something new")
        # Check adjacent pairs with equal confidence
        for i in range(len(result) - 1):
            if result[i].confidence == result[i + 1].confidence:
                assert result[i].type.name <= result[i + 1].type.name, (
                    f"Tiebreaker failed: {result[i].type.name} should come "
                    f"before {result[i+1].type.name} at confidence "
                    f"{result[i].confidence}"
                )


# ===================================================================
# Test: Detector — deduplication
# ===================================================================

class TestDetectDedup:
    """When multiple patterns match the same signal type, keep the best."""

    def test_frustrated_deduped(self, detector: PRISMDetector) -> None:
        """Text matching multiple FRUSTRATED patterns should yield one signal."""
        # "UGH NOTHING WORKS!!" matches: expletive, caps, broken, punctuation
        result = detector.detect("UGH NOTHING WORKS!!")
        frustrated = [s for s in result if s.type == CognitiveSignal.FRUSTRATED]
        assert len(frustrated) == 1, (
            f"Expected 1 FRUSTRATED signal, got {len(frustrated)}"
        )

    def test_frustrated_keeps_highest_confidence(self, detector: PRISMDetector) -> None:
        """Dedup should keep the highest-confidence match."""
        result = detector.detect("UGH this is broken and nothing works!!")
        frustrated = [s for s in result if s.type == CognitiveSignal.FRUSTRATED]
        assert len(frustrated) == 1
        # "this is broken|nothing works" pattern has confidence 0.80
        assert frustrated[0].confidence == 0.80

    def test_stuck_deduped(self, detector: PRISMDetector) -> None:
        """Text matching multiple STUCK patterns yields one signal."""
        result = detector.detect("I'm stuck, tried everything, going in circles")
        stuck = [s for s in result if s.type == CognitiveSignal.STUCK]
        assert len(stuck) == 1
        # "tried everything|going in circles" = 0.75 > "stuck" = 0.70
        assert stuck[0].confidence == 0.75


# ===================================================================
# Test: Detector — multiple signal types
# ===================================================================

class TestDetectMultipleTypes:
    """Complex text should produce multiple distinct signal types."""

    def test_frustrated_and_stuck(self, detector: PRISMDetector) -> None:
        result = detector.detect("UGH I'm stuck, this keeps failing")
        types = {s.type for s in result}
        assert CognitiveSignal.FRUSTRATED in types
        assert CognitiveSignal.STUCK in types

    def test_depleted_and_crash_zone(self, detector: PRISMDetector) -> None:
        result = detector.detect("getting tired, starting to fade")
        types = {s.type for s in result}
        assert CognitiveSignal.DEPLETED in types
        assert CognitiveSignal.CRASH_ZONE_APPROACHING in types

    def test_exploring_and_high_energy(self, detector: PRISMDetector) -> None:
        result = detector.detect("I'm pumped, what if we brainstorm this?")
        types = {s.type for s in result}
        assert CognitiveSignal.EXPLORING in types
        assert CognitiveSignal.HIGH_ENERGY in types


# ===================================================================
# Test: Determinism — [He2025] compliance
# ===================================================================

class TestDeterminism:
    """Same text must produce the exact same signals every time."""

    SAMPLE_TEXTS = [
        "I'm stuck and overwhelmed, too much to handle",
        "UGH THIS IS BROKEN, nothing works!!",
        "what if we tried something different?",
        "I give up, I can't do this, I'm exhausted",
        "ready to go, let's do this, I'll finish by Friday",
        "",
        "the weather is mild",
    ]

    def test_deterministic_100x(self, detector: PRISMDetector) -> None:
        """Run detection 100 times on each text — results must be identical."""
        for text in self.SAMPLE_TEXTS:
            first = [
                (s.type.name, s.confidence, s.source)
                for s in detector.detect(text)
            ]
            for i in range(99):
                current = [
                    (s.type.name, s.confidence, s.source)
                    for s in detector.detect(text)
                ]
                assert current == first, (
                    f"Divergence on iteration {i + 2} for text: {text!r}"
                )

    def test_two_detectors_same_result(self, detector: PRISMDetector) -> None:
        """Two independent detector instances must produce identical results."""
        other = PRISMDetector()
        for text in self.SAMPLE_TEXTS:
            r1 = [(s.type.name, s.confidence) for s in detector.detect(text)]
            r2 = [(s.type.name, s.confidence) for s in other.detect(text)]
            assert r1 == r2

    def test_all_sources_are_local_pattern(self, detector: PRISMDetector) -> None:
        """Stage 1 detector always reports source as 'local_pattern'."""
        for text in self.SAMPLE_TEXTS:
            for signal in detector.detect(text):
                assert signal.source == "local_pattern"


# ===================================================================
# Test: Package imports
# ===================================================================

class TestPackageImports:
    """Verify the __init__.py re-exports work correctly."""

    def test_import_from_package(self) -> None:
        from otto.core.prism import (
            CognitiveSignal,
            DetectionPattern,
            PATTERNS,
            PRISMDetector,
            Signal,
        )
        assert CognitiveSignal.FRUSTRATED is not None
        assert len(PATTERNS) > 0
        assert PRISMDetector is not None
