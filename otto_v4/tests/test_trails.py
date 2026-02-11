"""Tests for pheromone trail system (Phase 5.1)."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from otto.trails import TrailStore, _kahan_decay


def _ts(offset_hours: float = 0) -> datetime:
    base = datetime(2026, 2, 11, 12, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(hours=offset_hours)


@pytest.fixture()
def store(tmp_path) -> TrailStore:
    return TrailStore(db_path=str(tmp_path / "trails.db"))


class TestDeposit:
    def test_deposit_creates_trail(self, store):
        store.deposit("executor:nudge", "commitment_detected", 1.0, now=_ts())
        trails = store.follow("commitment_detected")
        assert len(trails) == 1
        assert trails[0].action == "executor:nudge"
        assert trails[0].strength == 1.0
        assert trails[0].deposit_count == 1

    def test_deposit_accumulates_strength(self, store):
        store.deposit("executor:nudge", "commitment_detected", 1.0, now=_ts())
        store.deposit("executor:nudge", "commitment_detected", 0.5, now=_ts(1))
        trails = store.follow("commitment_detected")
        assert len(trails) == 1
        assert trails[0].strength == 1.5
        assert trails[0].deposit_count == 2

    def test_deposit_different_actions_separate(self, store):
        store.deposit("executor:nudge", "commitment_detected", 1.0, now=_ts())
        store.deposit("protector:validate", "commitment_detected", 0.5, now=_ts())
        trails = store.follow("commitment_detected")
        assert len(trails) == 2

    def test_deposit_different_contexts_separate(self, store):
        store.deposit("executor:nudge", "commitment_detected", 1.0, now=_ts())
        store.deposit("executor:nudge", "frustrated", 0.5, now=_ts())
        assert store.count() == 2


class TestFollow:
    def test_follow_sorted_by_strength_desc(self, store):
        store.deposit("weak_action", "ctx", 0.3, now=_ts())
        store.deposit("strong_action", "ctx", 0.9, now=_ts())
        store.deposit("mid_action", "ctx", 0.6, now=_ts())
        trails = store.follow("ctx")
        strengths = [t.strength for t in trails]
        assert strengths == sorted(strengths, reverse=True)

    def test_follow_deterministic_tiebreaker(self, store):
        """Same strength -> sorted by action name ascending."""
        store.deposit("beta", "ctx", 1.0, now=_ts())
        store.deposit("alpha", "ctx", 1.0, now=_ts())
        trails = store.follow("ctx")
        actions = [t.action for t in trails]
        assert actions == ["alpha", "beta"]

    def test_follow_empty_context(self, store):
        assert store.follow("nonexistent") == []

    def test_follow_only_matching_context(self, store):
        store.deposit("action_a", "ctx1", 1.0, now=_ts())
        store.deposit("action_b", "ctx2", 1.0, now=_ts())
        trails = store.follow("ctx1")
        assert len(trails) == 1
        assert trails[0].action == "action_a"


class TestGetStrength:
    def test_existing_trail(self, store):
        store.deposit("action", "ctx", 0.75, now=_ts())
        assert store.get_strength("action", "ctx") == 0.75

    def test_nonexistent_trail(self, store):
        assert store.get_strength("no_action", "no_ctx") == 0.0


class TestDecay:
    def test_decay_reduces_strength(self, store):
        store.deposit("action", "ctx", 1.0, now=_ts(0))
        # 168 hours later (one half-life)
        pruned = store.decay(half_life_hours=168, now=_ts(168))
        strength = store.get_strength("action", "ctx")
        assert strength == pytest.approx(0.5, rel=1e-6)
        assert pruned == 0

    def test_two_half_lives_quarter_strength(self, store):
        store.deposit("action", "ctx", 1.0, now=_ts(0))
        pruned = store.decay(half_life_hours=168, now=_ts(336))
        strength = store.get_strength("action", "ctx")
        assert strength == pytest.approx(0.25, rel=1e-6)
        assert pruned == 0

    def test_decay_prunes_below_threshold(self, store):
        store.deposit("action", "ctx", 0.001, now=_ts(0))
        # After one half-life, 0.001 * 0.5 = 0.0005 < threshold
        pruned = store.decay(half_life_hours=168, now=_ts(168))
        assert pruned == 1
        assert store.count() == 0

    def test_decay_no_effect_at_zero_elapsed(self, store):
        store.deposit("action", "ctx", 1.0, now=_ts(0))
        store.decay(half_life_hours=168, now=_ts(0))
        assert store.get_strength("action", "ctx") == 1.0

    def test_successful_nudge_strengthens_trail(self, store):
        """Simulating: nudge sent, user completed -> deposit strength."""
        store.deposit("executor:nudge", "commitment", 1.0, now=_ts(0))
        # User completed the task -> deposit more
        store.deposit("executor:nudge", "commitment", 1.0, now=_ts(2))
        assert store.get_strength("executor:nudge", "commitment") == 2.0

    def test_ignored_nudge_weakens_trail(self, store):
        """Simulating: nudge sent, user ignored -> deposit negative."""
        store.deposit("executor:nudge", "meeting", 1.0, now=_ts(0))
        # Nudge ignored -> deposit negative strength
        store.deposit("executor:nudge", "meeting", -0.3, now=_ts(2))
        assert store.get_strength("executor:nudge", "meeting") == 0.7


class TestKahanDecay:
    def test_half_life_at_half_life(self):
        """At exactly one half-life, factor should be 0.5."""
        assert _kahan_decay(168, 168) == pytest.approx(0.5)

    def test_zero_elapsed(self):
        """Zero elapsed -> factor is 1.0."""
        assert _kahan_decay(0, 168) == 1.0

    def test_large_elapsed(self):
        """Very large elapsed -> factor approaches 0."""
        factor = _kahan_decay(10000, 168)
        assert factor < 0.001

    def test_zero_half_life_returns_zero(self):
        assert _kahan_decay(100, 0) == 0.0

    def test_numerical_stability(self):
        """Kahan decay should produce consistent results across magnitudes."""
        # Compare result of 10 half-lives
        result = _kahan_decay(1680, 168)
        expected = 0.5 ** 10
        assert result == pytest.approx(expected, rel=1e-10)


class TestAllTrails:
    def test_all_trails_sorted(self, store):
        store.deposit("b_action", "b_ctx", 1.0, now=_ts())
        store.deposit("a_action", "a_ctx", 1.0, now=_ts())
        trails = store.all_trails()
        contexts = [(t.context, t.action) for t in trails]
        assert contexts == sorted(contexts)


class TestDeterminism:
    def test_follow_is_deterministic(self, store):
        store.deposit("alpha", "ctx", 0.5, now=_ts())
        store.deposit("beta", "ctx", 0.5, now=_ts())
        store.deposit("gamma", "ctx", 0.8, now=_ts())
        baseline = store.follow("ctx")
        for _ in range(20):
            result = store.follow("ctx")
            assert [(t.action, t.strength) for t in result] == [
                (t.action, t.strength) for t in baseline
            ]
