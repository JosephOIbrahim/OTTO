"""Day 7 tests: Kahan accumulator, named seeds, pheromone trails, decay.

Test requirements from CLAUDE.md:
  - Deposit increases strength
  - Multiple deposits accumulate correctly
  - Decay reduces strength over time
  - Kahan vs naive sum shows precision difference (10,000 iterations)
  - Trails below threshold pruned
  - follow() returns sorted by strength desc
  - Deterministic decay
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from otto.core.determinism.kahan import KahanAccumulator, kahan_sum
from otto.core.determinism.seeds import (
    ALL_SEEDS,
    BATCH_SEED,
    DECAY_SEED,
    DETERMINISM_SEED,
    ROUTING_SEED,
    TEST_SEED,
    TRAIL_SEED,
)
from otto.core.pheromones.decay import DecayEngine
from otto.core.pheromones.trails import Trail, TrailManager


# ============================================================
# Helpers
# ============================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hours_ago(hours: float) -> datetime:
    return _now() - timedelta(hours=hours)


# ============================================================
# KahanAccumulator
# ============================================================

class TestKahanAccumulator:
    """Kahan summation for numerically stable float addition."""

    def test_empty_total_is_zero(self) -> None:
        acc = KahanAccumulator()
        assert acc.total() == 0.0

    def test_single_add(self) -> None:
        acc = KahanAccumulator()
        acc.add(42.0)
        assert acc.total() == 42.0

    def test_multiple_adds(self) -> None:
        acc = KahanAccumulator()
        acc.add(1.0)
        acc.add(2.0)
        acc.add(3.0)
        assert acc.total() == 6.0

    def test_negative_values(self) -> None:
        acc = KahanAccumulator()
        acc.add(10.0)
        acc.add(-3.0)
        acc.add(-2.0)
        assert acc.total() == 5.0

    def test_mixed_positive_negative(self) -> None:
        acc = KahanAccumulator()
        acc.add(1e15)
        acc.add(-1e15)
        acc.add(1.0)
        assert acc.total() == 1.0

    def test_kahan_vs_naive_10000_iterations(self) -> None:
        """CLAUDE.md requirement: precision difference at 10,000 iterations.

        Pattern: start with 1e15, then add 10,000 tiny values (0.001).
        The ULP of 1e15 is 0.125, so 0.001 < ULP/2 = 0.0625.
        Each naive += 0.001 is silently rounded away.  Kahan tracks the
        lost bits in its compensation term and folds them back when they
        accumulate above ULP.

        Expected: 1e15 + 10 = 1000000000000010.0
        Naive:    1e15       (all 0.001 additions lost)
        Kahan:    ~1e15 + 10 (compensation recovers the tiny values)
        """
        big = 1e15
        tiny = 0.001
        n = 10_000
        expected = big + n * tiny  # 1e15 + 10.0

        # Naive summation: tiny values lost below ULP
        naive = big
        for _ in range(n):
            naive += tiny

        # Kahan summation: compensation recovers tiny values
        acc = KahanAccumulator()
        acc.add(big)
        for _ in range(n):
            acc.add(tiny)

        kahan_error = abs(acc.total() - expected)
        naive_error = abs(naive - expected)

        # Kahan MUST be more precise than naive
        assert kahan_error < naive_error, (
            f"Kahan error ({kahan_error}) should be less than "
            f"naive error ({naive_error})"
        )

    def test_kahan_vs_naive_small_values(self) -> None:
        """Additional precision test: 10,000 additions of 0.1."""
        expected = 1000.0
        n = 10_000

        naive = 0.0
        acc = KahanAccumulator()
        for _ in range(n):
            naive += 0.1
            acc.add(0.1)

        kahan_error = abs(acc.total() - expected)
        naive_error = abs(naive - expected)

        # Kahan should be at least as good as naive
        assert kahan_error <= naive_error

    def test_reset(self) -> None:
        acc = KahanAccumulator()
        acc.add(100.0)
        acc.reset()
        assert acc.total() == 0.0

    def test_kahan_sum_function(self) -> None:
        values = [0.1, 0.2, 0.3, 0.4]
        result = kahan_sum(values)
        assert abs(result - 1.0) < 1e-15

    def test_kahan_sum_empty(self) -> None:
        assert kahan_sum([]) == 0.0


# ============================================================
# Named Seeds
# ============================================================

class TestNamedSeeds:
    """[He2025] named seed constants."""

    def test_seeds_are_ints(self) -> None:
        for name, value in ALL_SEEDS:
            assert isinstance(value, int), f"{name} is not int"

    def test_seeds_are_positive(self) -> None:
        for name, value in ALL_SEEDS:
            assert value > 0, f"{name} is not positive"

    def test_seeds_are_unique(self) -> None:
        values = [v for _, v in ALL_SEEDS]
        assert len(values) == len(set(values)), "Seed values must be unique"

    def test_all_seeds_tuple_sorted(self) -> None:
        """ALL_SEEDS is sorted by name [He2025]."""
        names = [name for name, _ in ALL_SEEDS]
        assert names == sorted(names)

    def test_expected_seeds_present(self) -> None:
        seed_names = {name for name, _ in ALL_SEEDS}
        expected = {
            "DETERMINISM_SEED", "ROUTING_SEED", "TRAIL_SEED",
            "DECAY_SEED", "BATCH_SEED", "TEST_SEED",
        }
        assert expected == seed_names

    def test_specific_values_stable(self) -> None:
        """Seed values must never change (reproducibility contract)."""
        assert DETERMINISM_SEED == 42
        assert ROUTING_SEED == 137
        assert TRAIL_SEED == 271
        assert DECAY_SEED == 314
        assert BATCH_SEED == 577
        assert TEST_SEED == 12345


# ============================================================
# Trail dataclass
# ============================================================

class TestTrail:
    """Frozen Trail dataclass."""

    def test_is_frozen(self) -> None:
        trail = Trail(action="test", context="ctx", strength=1.0)
        with pytest.raises(AttributeError):
            trail.strength = 2.0  # type: ignore[misc]

    def test_required_fields(self) -> None:
        trail = Trail(action="a", context="c", strength=0.5)
        assert trail.action == "a"
        assert trail.context == "c"
        assert trail.strength == 0.5

    def test_default_deposit_count(self) -> None:
        trail = Trail(action="a", context="c", strength=1.0)
        assert trail.deposit_count == 1

    def test_has_timestamp(self) -> None:
        trail = Trail(action="a", context="c", strength=1.0)
        assert isinstance(trail.last_deposited, datetime)


# ============================================================
# TrailManager — Deposit
# ============================================================

class TestTrailManagerDeposit:
    """CLAUDE.md: Deposit increases strength."""

    def test_single_deposit(self) -> None:
        """Single deposit creates trail with given strength."""
        tm = TrailManager()
        trail = tm.deposit("route:protector", 0.5, "frustrated")
        assert trail.strength == 0.5
        assert trail.deposit_count == 1
        assert trail.action == "route:protector"
        assert trail.context == "frustrated"

    def test_multiple_deposits_accumulate(self) -> None:
        """CLAUDE.md: Multiple deposits accumulate correctly."""
        tm = TrailManager()
        tm.deposit("route:protector", 0.3, "frustrated")
        tm.deposit("route:protector", 0.4, "frustrated")
        trail = tm.deposit("route:protector", 0.2, "frustrated")
        assert abs(trail.strength - 0.9) < 1e-15
        assert trail.deposit_count == 3

    def test_deposit_increments_count(self) -> None:
        tm = TrailManager()
        for i in range(5):
            trail = tm.deposit("action", 0.1, "ctx")
        assert trail.deposit_count == 5

    def test_deposit_updates_timestamp(self) -> None:
        tm = TrailManager()
        t1 = _hours_ago(2)
        t2 = _now()
        tm.deposit("a", 0.5, "c", now=t1)
        trail = tm.deposit("a", 0.3, "c", now=t2)
        assert trail.last_deposited == t2

    def test_different_contexts_independent(self) -> None:
        """Same action in different contexts are separate trails."""
        tm = TrailManager()
        tm.deposit("route:protector", 0.5, "frustrated")
        tm.deposit("route:protector", 0.3, "crashed")
        assert tm.get_strength("route:protector", "frustrated") == 0.5
        assert tm.get_strength("route:protector", "crashed") == 0.3

    def test_deposit_negative_raises(self) -> None:
        tm = TrailManager()
        with pytest.raises(ValueError, match="positive"):
            tm.deposit("a", -0.1, "c")

    def test_deposit_zero_raises(self) -> None:
        tm = TrailManager()
        with pytest.raises(ValueError, match="positive"):
            tm.deposit("a", 0.0, "c")


# ============================================================
# TrailManager — Follow
# ============================================================

class TestTrailManagerFollow:
    """CLAUDE.md: follow() returns sorted by strength desc."""

    def test_follow_returns_matching_context(self) -> None:
        tm = TrailManager()
        tm.deposit("a", 0.5, "target")
        tm.deposit("b", 0.3, "target")
        tm.deposit("c", 0.8, "other")
        trails = tm.follow("target")
        assert len(trails) == 2
        assert all(t.context == "target" for t in trails)

    def test_follow_sorted_by_strength_desc(self) -> None:
        tm = TrailManager()
        tm.deposit("weak", 0.1, "ctx")
        tm.deposit("strong", 0.9, "ctx")
        tm.deposit("medium", 0.5, "ctx")
        trails = tm.follow("ctx")
        strengths = [t.strength for t in trails]
        assert strengths == sorted(strengths, reverse=True)

    def test_follow_tiebreaker_by_action(self) -> None:
        """Equal strength → sorted by action name [He2025]."""
        tm = TrailManager()
        tm.deposit("beta", 0.5, "ctx")
        tm.deposit("alpha", 0.5, "ctx")
        tm.deposit("gamma", 0.5, "ctx")
        trails = tm.follow("ctx")
        actions = [t.action for t in trails]
        assert actions == ["alpha", "beta", "gamma"]

    def test_follow_empty_context(self) -> None:
        tm = TrailManager()
        tm.deposit("a", 0.5, "other")
        assert tm.follow("missing") == []

    def test_follow_empty_manager(self) -> None:
        tm = TrailManager()
        assert tm.follow("anything") == []


# ============================================================
# TrailManager — Get Strength
# ============================================================

class TestTrailManagerGetStrength:
    """Query individual trail strengths."""

    def test_get_strength_existing(self) -> None:
        tm = TrailManager()
        tm.deposit("a", 0.7, "ctx")
        assert tm.get_strength("a", "ctx") == 0.7

    def test_get_strength_missing(self) -> None:
        tm = TrailManager()
        assert tm.get_strength("nonexistent", "ctx") == 0.0

    def test_get_strength_no_context_returns_max(self) -> None:
        """Without context, returns max across all contexts."""
        tm = TrailManager()
        tm.deposit("a", 0.3, "ctx1")
        tm.deposit("a", 0.8, "ctx2")
        tm.deposit("a", 0.5, "ctx3")
        assert tm.get_strength("a") == 0.8

    def test_get_strength_no_context_missing(self) -> None:
        tm = TrailManager()
        assert tm.get_strength("nonexistent") == 0.0


# ============================================================
# TrailManager — Total Strength (Kahan)
# ============================================================

class TestTrailManagerTotalStrength:
    """Aggregate strength using Kahan summation."""

    def test_total_strength_all(self) -> None:
        tm = TrailManager()
        tm.deposit("a", 0.3, "ctx1")
        tm.deposit("b", 0.4, "ctx2")
        tm.deposit("c", 0.3, "ctx1")
        total = tm.total_strength()
        assert abs(total - 1.0) < 1e-15

    def test_total_strength_filtered(self) -> None:
        tm = TrailManager()
        tm.deposit("a", 0.3, "target")
        tm.deposit("b", 0.4, "target")
        tm.deposit("c", 0.5, "other")
        assert abs(tm.total_strength("target") - 0.7) < 1e-15

    def test_total_strength_empty(self) -> None:
        tm = TrailManager()
        assert tm.total_strength() == 0.0

    def test_total_strength_uses_kahan(self) -> None:
        """Total strength of many small values is Kahan-accurate."""
        tm = TrailManager()
        n = 1000
        for i in range(n):
            tm.deposit(f"action_{i:04d}", 0.001, "ctx")
        expected = 1.0
        assert abs(tm.total_strength("ctx") - expected) < 1e-12


# ============================================================
# TrailManager — Introspection
# ============================================================

class TestTrailManagerIntrospection:
    """all_trails() and count()."""

    def test_all_trails_sorted_by_key(self) -> None:
        tm = TrailManager()
        tm.deposit("beta", 0.5, "ctx")
        tm.deposit("alpha", 0.3, "ctx")
        tm.deposit("gamma", 0.7, "ctx")
        trails = tm.all_trails()
        keys = [(t.action, t.context) for t in trails]
        assert keys == sorted(keys)

    def test_count(self) -> None:
        tm = TrailManager()
        assert tm.count() == 0
        tm.deposit("a", 0.5, "c1")
        tm.deposit("b", 0.3, "c1")
        assert tm.count() == 2
        # Same key — doesn't create new trail
        tm.deposit("a", 0.2, "c1")
        assert tm.count() == 2


# ============================================================
# DecayEngine
# ============================================================

class TestDecayEngine:
    """CLAUDE.md: Decay reduces strength over time."""

    def test_decay_reduces_strength(self) -> None:
        """After elapsed time, strength is lower."""
        tm = TrailManager()
        t_old = _hours_ago(48)
        tm.deposit("a", 1.0, "ctx", now=t_old)

        engine = DecayEngine(half_life_hours=168.0)
        pruned = engine.decay_all(tm._store)

        trail = tm._store[("a", "ctx")]
        assert trail.strength < 1.0
        assert trail.strength > 0.0
        assert pruned == 0

    def test_no_decay_for_fresh_trails(self) -> None:
        """Just-deposited trails don't decay."""
        tm = TrailManager()
        now = _now()
        tm.deposit("a", 1.0, "ctx", now=now)

        engine = DecayEngine(half_life_hours=168.0)
        engine.decay_all(tm._store, now=now)

        assert tm._store[("a", "ctx")].strength == 1.0

    def test_half_life_correct(self) -> None:
        """After exactly one half-life, strength is ~50%."""
        half_life = 168.0
        tm = TrailManager()
        t_old = _hours_ago(half_life)
        tm.deposit("a", 1.0, "ctx", now=t_old)

        engine = DecayEngine(half_life_hours=half_life)
        engine.decay_all(tm._store)

        trail = tm._store[("a", "ctx")]
        assert abs(trail.strength - 0.5) < 0.01

    def test_double_half_life_quarter(self) -> None:
        """After two half-lives, strength is ~25%."""
        half_life = 100.0
        tm = TrailManager()
        t_old = _hours_ago(2 * half_life)
        tm.deposit("a", 1.0, "ctx", now=t_old)

        engine = DecayEngine(half_life_hours=half_life)
        engine.decay_all(tm._store)

        trail = tm._store[("a", "ctx")]
        assert abs(trail.strength - 0.25) < 0.01

    def test_prune_below_threshold(self) -> None:
        """CLAUDE.md: Trails below threshold pruned."""
        tm = TrailManager()
        # Very old trail — should decay below 0.001
        t_very_old = _hours_ago(168.0 * 15)  # 15 half-lives
        tm.deposit("old", 1.0, "ctx", now=t_very_old)
        # Recent trail — should survive
        tm.deposit("recent", 1.0, "ctx", now=_now())

        engine = DecayEngine(half_life_hours=168.0, prune_threshold=0.001)
        pruned = engine.decay_all(tm._store)

        assert pruned == 1
        assert ("old", "ctx") not in tm._store
        assert ("recent", "ctx") in tm._store

    def test_prune_count_correct(self) -> None:
        """Prune count matches number of removed trails."""
        tm = TrailManager()
        t_ancient = _hours_ago(168.0 * 20)
        for i in range(5):
            tm.deposit(f"dead_{i}", 0.1, "ctx", now=t_ancient)
        tm.deposit("alive", 1.0, "ctx", now=_now())

        engine = DecayEngine(half_life_hours=168.0)
        pruned = engine.decay_all(tm._store)
        assert pruned == 5
        assert tm.count() == 1

    def test_decay_preserves_action_context(self) -> None:
        """Decay creates new Trail instances with same action/context."""
        tm = TrailManager()
        t_old = _hours_ago(24)
        tm.deposit("a", 1.0, "ctx", now=t_old)

        engine = DecayEngine(half_life_hours=168.0)
        engine.decay_all(tm._store)

        trail = tm._store[("a", "ctx")]
        assert trail.action == "a"
        assert trail.context == "ctx"
        assert trail.deposit_count == 1

    def test_decay_preserves_deposit_count(self) -> None:
        """Decay doesn't change deposit count."""
        tm = TrailManager()
        t_old = _hours_ago(24)
        tm.deposit("a", 0.5, "c", now=t_old)
        tm.deposit("a", 0.3, "c", now=t_old)

        engine = DecayEngine(half_life_hours=168.0)
        engine.decay_all(tm._store)

        assert tm._store[("a", "c")].deposit_count == 2


class TestDecayEngineParams:
    """DecayEngine parameter validation."""

    def test_negative_half_life_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            DecayEngine(half_life_hours=-1.0)

    def test_zero_half_life_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            DecayEngine(half_life_hours=0.0)

    def test_negative_threshold_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            DecayEngine(prune_threshold=-0.1)

    def test_compute_decay_factor_no_elapsed(self) -> None:
        engine = DecayEngine()
        assert engine.compute_decay_factor(0.0) == 1.0

    def test_compute_decay_factor_negative_elapsed(self) -> None:
        engine = DecayEngine()
        assert engine.compute_decay_factor(-5.0) == 1.0

    def test_compute_decay_factor_one_half_life(self) -> None:
        engine = DecayEngine(half_life_hours=168.0)
        assert abs(engine.compute_decay_factor(168.0) - 0.5) < 1e-15


class TestDecayTotalDecayedAmount:
    """DecayEngine.total_decayed_amount (uses Kahan)."""

    def test_total_decayed_amount(self) -> None:
        tm = TrailManager()
        t_old = _hours_ago(168.0)
        tm.deposit("a", 1.0, "ctx", now=t_old)
        tm.deposit("b", 1.0, "ctx", now=t_old)

        engine = DecayEngine(half_life_hours=168.0)
        loss = engine.total_decayed_amount(tm._store)
        # After one half-life, each loses ~0.5 → total ~1.0
        assert abs(loss - 1.0) < 0.05

    def test_total_decayed_no_modification(self) -> None:
        """total_decayed_amount doesn't modify trails."""
        tm = TrailManager()
        t_old = _hours_ago(48)
        tm.deposit("a", 1.0, "ctx", now=t_old)

        engine = DecayEngine()
        engine.total_decayed_amount(tm._store)

        # Trail strength unchanged
        assert tm._store[("a", "ctx")].strength == 1.0


# ============================================================
# Integration
# ============================================================

class TestDepositDecayFollowCycle:
    """Full lifecycle: deposit → decay → follow."""

    def test_deposit_decay_follow(self) -> None:
        tm = TrailManager()
        now = _now()
        t_old = now - timedelta(hours=168.0)

        # Deposit trails at different times
        tm.deposit("strong_recent", 0.8, "ctx", now=now)
        tm.deposit("strong_old", 0.8, "ctx", now=t_old)
        tm.deposit("weak_recent", 0.2, "ctx", now=now)

        # Decay at the exact same `now` — recent trails have 0 elapsed
        engine = DecayEngine(half_life_hours=168.0)
        engine.decay_all(tm._store, now=now)

        # Follow — recent trails should dominate
        trails = tm.follow("ctx")
        assert trails[0].action == "strong_recent"
        assert trails[0].strength == 0.8  # No decay (0 elapsed)
        assert trails[1].action == "strong_old"
        assert trails[1].strength < 0.5  # Decayed ~half-life
        assert trails[2].action == "weak_recent"
        assert trails[2].strength == 0.2  # No decay (0 elapsed)

    def test_multiple_decay_cycles(self) -> None:
        """Multiple decay cycles reduce strength progressively."""
        tm = TrailManager()
        base_time = _hours_ago(0)
        tm.deposit("a", 1.0, "ctx", now=base_time)

        engine = DecayEngine(half_life_hours=100.0)

        strengths = [1.0]
        for i in range(1, 5):
            future = base_time + timedelta(hours=100 * i)
            engine.decay_all(tm._store, now=future)
            strengths.append(tm._store[("a", "ctx")].strength)

        # Each cycle halves the strength
        for i in range(1, len(strengths)):
            ratio = strengths[i] / strengths[i - 1]
            assert abs(ratio - 0.5) < 0.01


class TestContextIsolation:
    """Decay and follow respect context boundaries."""

    def test_decay_affects_all_contexts(self) -> None:
        tm = TrailManager()
        t_old = _hours_ago(168.0)
        tm.deposit("a", 1.0, "ctx1", now=t_old)
        tm.deposit("a", 1.0, "ctx2", now=t_old)

        engine = DecayEngine(half_life_hours=168.0)
        engine.decay_all(tm._store)

        # Both contexts decayed
        for ctx in ("ctx1", "ctx2"):
            assert tm._store[("a", ctx)].strength < 1.0


# ============================================================
# Determinism [He2025]
# ============================================================

class TestDeterminism:
    """[He2025] determinism for the pheromone trail system."""

    def test_follow_deterministic_100x(self) -> None:
        """follow() is deterministic over 100 repetitions."""
        tm = TrailManager()
        tm.deposit("a", 0.5, "ctx")
        tm.deposit("b", 0.3, "ctx")
        tm.deposit("c", 0.8, "ctx")

        reference = [(t.action, t.strength) for t in tm.follow("ctx")]
        for _ in range(100):
            result = [(t.action, t.strength) for t in tm.follow("ctx")]
            assert result == reference

    def test_decay_deterministic_100x(self) -> None:
        """CLAUDE.md: Deterministic decay over 100 repetitions."""

        def _build_and_decay() -> list[tuple[str, float]]:
            tm = TrailManager()
            base = datetime(2026, 1, 1, tzinfo=timezone.utc)
            tm.deposit("a", 1.0, "ctx", now=base)
            tm.deposit("b", 0.5, "ctx", now=base)
            tm.deposit("c", 0.3, "ctx", now=base)

            engine = DecayEngine(half_life_hours=168.0)
            future = base + timedelta(hours=100)
            engine.decay_all(tm._store, now=future)

            return [
                (t.action, t.strength)
                for t in sorted(
                    tm._store.values(),
                    key=lambda t: t.action,
                )
            ]

        reference = _build_and_decay()
        for _ in range(100):
            assert _build_and_decay() == reference

    def test_all_trails_sorted_deterministic(self) -> None:
        """all_trails() returns deterministic sorted order."""
        tm = TrailManager()
        tm.deposit("z", 0.1, "ctx")
        tm.deposit("a", 0.9, "ctx")
        tm.deposit("m", 0.5, "ctx")
        reference = [(t.action, t.context) for t in tm.all_trails()]
        for _ in range(100):
            result = [(t.action, t.context) for t in tm.all_trails()]
            assert result == reference


# ============================================================
# Package imports
# ============================================================

class TestPackageImports:
    """Verify public API is importable from package."""

    def test_import_pheromones(self) -> None:
        from otto.core.pheromones import (
            DecayEngine,
            Trail,
            TrailKey,
            TrailManager,
        )
        assert Trail is not None
        assert TrailManager is not None
        assert DecayEngine is not None

    def test_import_determinism(self) -> None:
        from otto.core.determinism import (
            DETERMINISM_SEED,
            KahanAccumulator,
            TRAIL_SEED,
            kahan_sum,
        )
        assert KahanAccumulator is not None
        assert kahan_sum is not None
        assert DETERMINISM_SEED == 42
        assert TRAIL_SEED == 271
