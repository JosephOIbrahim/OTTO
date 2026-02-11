"""Tests for behavioral pattern detection (Phase 2.2).

Tests the HistoryAnalyzer which detects:
  - DEPLETED from declining message lengths
  - BURST_DETECTED from rapid-fire messaging
  - CRASH_ZONE from silence after a burst
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from otto.signals import (
    HistoryAnalyzer,
    InteractionRecord,
    Signal,
    SignalType,
)


def _ts(offset_seconds: float = 0) -> datetime:
    """Helper: create a UTC timestamp offset from a fixed base."""
    base = datetime(2026, 2, 11, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(seconds=offset_seconds)


def _record(offset_seconds: float, length: int) -> InteractionRecord:
    """Helper: create an interaction record at a given offset."""
    return InteractionRecord(
        timestamp=_ts(offset_seconds),
        message_length=length,
    )


@pytest.fixture()
def analyzer() -> HistoryAnalyzer:
    return HistoryAnalyzer()


class TestDecliningLength:
    def test_declining_signals_depleted(self, analyzer):
        """Steadily shrinking messages should signal depletion."""
        records = [
            _record(0, 200),
            _record(60, 180),
            _record(120, 100),
            _record(180, 50),
            _record(240, 30),
        ]
        signals = analyzer.analyze(records, now=_ts(300))
        types = {s.type for s in signals}
        assert SignalType.DEPLETED in types

    def test_stable_length_no_depleted(self, analyzer):
        """Consistent message lengths should not trigger depleted."""
        records = [
            _record(0, 100),
            _record(60, 105),
            _record(120, 98),
            _record(180, 102),
            _record(240, 100),
        ]
        signals = analyzer.analyze(records, now=_ts(300))
        types = {s.type for s in signals}
        assert SignalType.DEPLETED not in types

    def test_increasing_length_no_depleted(self, analyzer):
        """Growing messages should not trigger depleted."""
        records = [
            _record(0, 30),
            _record(60, 50),
            _record(120, 100),
            _record(180, 150),
            _record(240, 200),
        ]
        signals = analyzer.analyze(records, now=_ts(300))
        types = {s.type for s in signals}
        assert SignalType.DEPLETED not in types

    def test_needs_minimum_records(self, analyzer):
        """Fewer than 3 records in the window should not trigger."""
        records = [
            _record(0, 200),
            _record(60, 10),
        ]
        signals = analyzer.analyze(records, now=_ts(120))
        assert signals == []


class TestBurstDetection:
    def test_rapid_messages_signal_burst(self, analyzer):
        """4+ messages within 2 minutes should signal burst."""
        records = [
            _record(0, 50),
            _record(10, 60),
            _record(25, 45),
            _record(40, 55),
        ]
        signals = analyzer.analyze(records, now=_ts(50))
        types = {s.type for s in signals}
        assert SignalType.BURST_DETECTED in types

    def test_spaced_messages_no_burst(self, analyzer):
        """Messages spread over 10 minutes should not trigger burst."""
        records = [
            _record(0, 50),
            _record(180, 60),
            _record(360, 45),
            _record(540, 55),
        ]
        signals = analyzer.analyze(records, now=_ts(600))
        types = {s.type for s in signals}
        assert SignalType.BURST_DETECTED not in types

    def test_same_timestamp_burst(self, analyzer):
        """All messages at same timestamp should count as burst."""
        records = [
            _record(0, 50),
            _record(0, 60),
            _record(0, 45),
            _record(0, 55),
        ]
        signals = analyzer.analyze(records, now=_ts(0))
        types = {s.type for s in signals}
        assert SignalType.BURST_DETECTED in types

    def test_three_messages_no_burst(self, analyzer):
        """Only 3 messages (below threshold) should not trigger burst."""
        records = [
            _record(0, 50),
            _record(10, 60),
            _record(20, 45),
        ]
        signals = analyzer.analyze(records, now=_ts(30))
        types = {s.type for s in signals}
        assert SignalType.BURST_DETECTED not in types


class TestCrashZone:
    def test_burst_then_silence_signals_crash(self, analyzer):
        """Burst followed by 10+ minutes of silence should signal crash zone."""
        records = [
            _record(0, 50),
            _record(10, 60),
            _record(25, 45),
            _record(40, 55),
        ]
        # 15 minutes later
        now = _ts(40 + 900)
        signals = analyzer.analyze(records, now=now)
        types = {s.type for s in signals}
        assert SignalType.BURST_DETECTED in types
        assert SignalType.CRASH_ZONE in types

    def test_burst_no_silence_no_crash(self, analyzer):
        """Burst with immediate follow-up should not signal crash zone."""
        records = [
            _record(0, 50),
            _record(10, 60),
            _record(25, 45),
            _record(40, 55),
        ]
        # Only 1 minute later — no crash
        now = _ts(100)
        signals = analyzer.analyze(records, now=now)
        types = {s.type for s in signals}
        assert SignalType.BURST_DETECTED in types
        assert SignalType.CRASH_ZONE not in types

    def test_no_burst_no_crash(self, analyzer):
        """Crash zone requires a burst first."""
        records = [
            _record(0, 50),
            _record(180, 60),
            _record(360, 45),
            _record(540, 55),
        ]
        # Long silence but no burst
        now = _ts(540 + 1200)
        signals = analyzer.analyze(records, now=now)
        types = {s.type for s in signals}
        assert SignalType.CRASH_ZONE not in types


class TestDeterminism:
    def test_same_input_same_output(self, analyzer):
        """Same records + same now must produce identical results."""
        records = [
            _record(0, 200),
            _record(10, 180),
            _record(20, 100),
            _record(30, 50),
            _record(40, 20),
        ]
        now = _ts(700)
        baseline = analyzer.analyze(records, now=now)
        for _ in range(50):
            result = analyzer.analyze(records, now=now)
            assert result == baseline

    def test_sorted_by_confidence_then_type(self, analyzer):
        """Signals should be sorted confidence desc, then type name asc."""
        records = [
            _record(0, 200),
            _record(10, 180),
            _record(20, 100),
            _record(30, 50),
            _record(40, 20),
        ]
        now = _ts(700)
        signals = analyzer.analyze(records, now=now)
        for i in range(len(signals) - 1):
            a, b = signals[i], signals[i + 1]
            assert (a.confidence > b.confidence) or (
                a.confidence == b.confidence and a.type.name <= b.type.name
            )


class TestEdgeCases:
    def test_empty_records(self, analyzer):
        assert analyzer.analyze([]) == []

    def test_single_record(self, analyzer):
        assert analyzer.analyze([_record(0, 100)]) == []

    def test_all_signals_have_behavioral_source(self, analyzer):
        """All HistoryAnalyzer signals should have source='behavioral'."""
        records = [
            _record(0, 200),
            _record(10, 180),
            _record(20, 100),
            _record(30, 50),
            _record(40, 20),
        ]
        now = _ts(700)
        signals = analyzer.analyze(records, now=now)
        for s in signals:
            assert s.source == "behavioral"

    def test_threshold_filtering(self, analyzer):
        """High threshold should filter out lower-confidence signals."""
        records = [
            _record(0, 200),
            _record(10, 180),
            _record(20, 100),
            _record(30, 50),
            _record(40, 20),
        ]
        now = _ts(700)
        low_threshold = analyzer.analyze(records, now=now, threshold=0.3)
        high_threshold = analyzer.analyze(records, now=now, threshold=0.9)
        assert len(high_threshold) <= len(low_threshold)


class TestInteractionLog:
    """Test the StateStore interaction log methods."""

    def test_log_and_retrieve(self, tmp_path):
        from otto.state import StateStore
        store = StateStore(db_path=str(tmp_path / "test.db"))
        store.log_interaction(100, "cli", _ts(0))
        store.log_interaction(50, "whatsapp", _ts(60))

        rows = store.get_recent_interactions(limit=10)
        assert len(rows) == 2
        assert rows[0][1] == 100  # first message length
        assert rows[1][1] == 50   # second message length

    def test_recent_interactions_order(self, tmp_path):
        """Interactions should come back oldest-first."""
        from otto.state import StateStore
        store = StateStore(db_path=str(tmp_path / "test.db"))
        for i in range(5):
            store.log_interaction(i * 10, "cli", _ts(i * 60))

        rows = store.get_recent_interactions(limit=5)
        lengths = [r[1] for r in rows]
        assert lengths == [0, 10, 20, 30, 40]

    def test_recent_interactions_limit(self, tmp_path):
        """Limit parameter should cap the number returned."""
        from otto.state import StateStore
        store = StateStore(db_path=str(tmp_path / "test.db"))
        for i in range(10):
            store.log_interaction(i * 10, "cli", _ts(i * 60))

        rows = store.get_recent_interactions(limit=3)
        assert len(rows) == 3
        # Should be the 3 most recent, oldest first
        lengths = [r[1] for r in rows]
        assert lengths == [70, 80, 90]
