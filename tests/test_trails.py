"""
Tests for the Pheromone Trail System
=====================================

Tests Trail, TrailQuery, and TrailStore with focus on:
- [He2025] determinism (same inputs → same outputs)
- Decay and reinforcement mechanics
- CRUD operations
- Query ordering guarantees
"""

import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from otto.trails import (
    Trail,
    TrailType,
    TrailQuery,
    TrailStore,
)


# =============================================================================
# Trail Model Tests
# =============================================================================

class TestTrail:
    """Tests for the Trail dataclass."""

    def test_trail_creation_defaults(self):
        """Trail should have sensible defaults."""
        trail = Trail(path="src/test.py", signal="test_signal")

        assert trail.id is None
        assert trail.trail_type == TrailType.QUALITY
        assert trail.path == "src/test.py"
        assert trail.signal == "test_signal"
        assert trail.strength == 1.0
        assert trail.deposited_by == "unknown"
        assert trail.reinforced_count == 0
        assert trail.half_life_days == 7.0

    def test_trail_validation_empty_path(self):
        """Trail should reject empty path."""
        with pytest.raises(ValueError, match="path cannot be empty"):
            Trail(path="", signal="test")

    def test_trail_validation_empty_signal(self):
        """Trail should reject empty signal."""
        with pytest.raises(ValueError, match="signal cannot be empty"):
            Trail(path="test.py", signal="")

    def test_trail_validation_invalid_strength(self):
        """Trail should reject strength outside [0, 1]."""
        with pytest.raises(ValueError, match="strength must be in"):
            Trail(path="test.py", signal="test", strength=1.5)

        with pytest.raises(ValueError, match="strength must be in"):
            Trail(path="test.py", signal="test", strength=-0.1)

    def test_trail_validation_invalid_half_life(self):
        """Trail should reject non-positive half_life_days."""
        with pytest.raises(ValueError, match="half_life_days must be positive"):
            Trail(path="test.py", signal="test", half_life_days=0)

    def test_current_strength_no_decay(self):
        """Current strength should equal initial strength if no time passed."""
        now = datetime.now()
        trail = Trail(
            path="test.py",
            signal="test",
            strength=1.0,
            deposited_at=now,
        )
        assert trail.current_strength(now) == 1.0

    def test_current_strength_half_life_decay(self):
        """Strength should halve after one half-life period."""
        now = datetime.now()
        deposited_at = now - timedelta(days=7)  # Default half-life is 7 days

        trail = Trail(
            path="test.py",
            signal="test",
            strength=1.0,
            deposited_at=deposited_at,
            half_life_days=7.0,
        )

        current = trail.current_strength(now)
        assert abs(current - 0.5) < 0.001  # Should be ~0.5

    def test_current_strength_two_half_lives(self):
        """Strength should quarter after two half-life periods."""
        now = datetime.now()
        deposited_at = now - timedelta(days=14)

        trail = Trail(
            path="test.py",
            signal="test",
            strength=1.0,
            deposited_at=deposited_at,
            half_life_days=7.0,
        )

        current = trail.current_strength(now)
        assert abs(current - 0.25) < 0.001

    def test_is_alive_fresh_trail(self):
        """Fresh trail should be alive."""
        trail = Trail(path="test.py", signal="test", strength=1.0)
        assert trail.is_alive()

    def test_is_alive_decayed_trail(self):
        """Heavily decayed trail should be dead."""
        now = datetime.now()
        # After 28 days (4 half-lives), strength is 1.0 * 0.5^4 = 0.0625 < 0.1
        deposited_at = now - timedelta(days=28)

        trail = Trail(
            path="test.py",
            signal="test",
            strength=1.0,
            deposited_at=deposited_at,
            half_life_days=7.0,
        )

        assert not trail.is_alive(threshold=0.1, now=now)

    def test_trail_to_dict_round_trip(self):
        """Trail should serialize and deserialize correctly."""
        original = Trail(
            id=42,
            trail_type=TrailType.CONTEXT,
            path="src/test.py",
            signal="depends_on:utils.py",
            strength=0.8,
            deposited_by="test_agent",
            deposited_at=datetime(2025, 1, 15, 10, 30, 0),
            reinforced_count=3,
            metadata={"key": "value"},
            half_life_days=14.0,
        )

        data = original.to_dict()
        restored = Trail.from_dict(data)

        assert restored.id == original.id
        assert restored.trail_type == original.trail_type
        assert restored.path == original.path
        assert restored.signal == original.signal
        assert restored.strength == original.strength
        assert restored.deposited_by == original.deposited_by
        assert restored.deposited_at == original.deposited_at
        assert restored.reinforced_count == original.reinforced_count
        assert restored.metadata == original.metadata
        assert restored.half_life_days == original.half_life_days


# =============================================================================
# TrailQuery Tests
# =============================================================================

class TestTrailQuery:
    """Tests for the TrailQuery dataclass."""

    def test_query_matches_trail_type(self):
        """Query should filter by trail type."""
        trail = Trail(
            path="test.py",
            signal="test",
            trail_type=TrailType.QUALITY,
        )

        assert TrailQuery(trail_type=TrailType.QUALITY).matches(trail)
        assert not TrailQuery(trail_type=TrailType.CONTEXT).matches(trail)

    def test_query_matches_path(self):
        """Query should filter by exact path."""
        trail = Trail(path="src/test.py", signal="test")

        assert TrailQuery(path="src/test.py").matches(trail)
        assert not TrailQuery(path="src/other.py").matches(trail)

    def test_query_matches_path_prefix(self):
        """Query should filter by path prefix."""
        trail = Trail(path="src/otto/test.py", signal="test")

        assert TrailQuery(path_prefix="src/").matches(trail)
        assert TrailQuery(path_prefix="src/otto/").matches(trail)
        assert not TrailQuery(path_prefix="tests/").matches(trail)

    def test_query_matches_signal_contains(self):
        """Query should filter by signal substring."""
        trail = Trail(path="test.py", signal="he2025_compliant")

        assert TrailQuery(signal_contains="he2025").matches(trail)
        assert TrailQuery(signal_contains="compliant").matches(trail)
        assert not TrailQuery(signal_contains="violation").matches(trail)

    def test_query_matches_min_strength(self):
        """Query should filter by minimum strength."""
        now = datetime.now()
        trail = Trail(path="test.py", signal="test", strength=0.5, deposited_at=now)

        assert TrailQuery(min_strength=0.3).matches(trail, now)
        assert TrailQuery(min_strength=0.5).matches(trail, now)
        assert not TrailQuery(min_strength=0.6).matches(trail, now)

    def test_query_matches_max_age(self):
        """Query should filter by maximum age."""
        now = datetime.now()
        old_trail = Trail(
            path="test.py",
            signal="test",
            deposited_at=now - timedelta(days=10),
        )

        assert TrailQuery(max_age_days=15).matches(old_trail, now)
        assert not TrailQuery(max_age_days=5).matches(old_trail, now)


# =============================================================================
# TrailStore Tests
# =============================================================================

class TestTrailStore:
    """Tests for the SQLite TrailStore."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        # Cleanup
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create a TrailStore with temporary database."""
        return TrailStore(db_path=temp_db)

    def test_deposit_creates_trail(self, store):
        """Deposit should create a new trail."""
        trail = Trail(
            path="src/test.py",
            signal="test_signal",
            trail_type=TrailType.QUALITY,
            deposited_by="test_agent",
        )

        result = store.deposit(trail)

        assert result.id is not None
        assert result.path == "src/test.py"
        assert result.signal == "test_signal"
        assert result.reinforced_count == 0

    def test_deposit_reinforces_existing(self, store):
        """Depositing same trail should reinforce it."""
        trail = Trail(
            path="src/test.py",
            signal="test_signal",
            trail_type=TrailType.QUALITY,
            deposited_by="test_agent",
        )

        first = store.deposit(trail)
        second = store.deposit(trail)

        assert second.id == first.id
        assert second.reinforced_count == 1

    def test_reinforce_increases_strength(self, store):
        """Reinforce should increase trail strength."""
        trail = Trail(
            path="src/test.py",
            signal="test_signal",
            strength=0.5,
            deposited_by="test_agent",
        )
        store.deposit(trail)

        result = store.reinforce(
            path="src/test.py",
            signal="test_signal",
            trail_type=TrailType.QUALITY,
            boost=0.2,
        )

        assert result is not None
        assert result.strength == pytest.approx(0.7, abs=0.01)
        assert result.reinforced_count == 1

    def test_reinforce_caps_at_one(self, store):
        """Reinforce should not exceed strength of 1.0."""
        trail = Trail(
            path="src/test.py",
            signal="test_signal",
            strength=0.9,
            deposited_by="test_agent",
        )
        store.deposit(trail)

        result = store.reinforce(
            path="src/test.py",
            signal="test_signal",
            trail_type=TrailType.QUALITY,
            boost=0.5,
        )

        assert result.strength == 1.0

    def test_weaken_decreases_strength(self, store):
        """Weaken should decrease trail strength."""
        trail = Trail(
            path="src/test.py",
            signal="test_signal",
            strength=0.5,
            deposited_by="test_agent",
        )
        store.deposit(trail)

        result = store.weaken(
            path="src/test.py",
            signal="test_signal",
            trail_type=TrailType.QUALITY,
            reduction=0.2,
        )

        assert result is not None
        assert result.strength == pytest.approx(0.3, abs=0.01)

    def test_weaken_floors_at_zero(self, store):
        """Weaken should not go below 0.0."""
        trail = Trail(
            path="src/test.py",
            signal="test_signal",
            strength=0.1,
            deposited_by="test_agent",
        )
        store.deposit(trail)

        result = store.weaken(
            path="src/test.py",
            signal="test_signal",
            trail_type=TrailType.QUALITY,
            reduction=0.5,
        )

        assert result.strength == 0.0

    def test_read_trails_returns_all_for_path(self, store):
        """Read trails should return all trails for a path."""
        for signal in ["signal_a", "signal_b", "signal_c"]:
            store.deposit(Trail(
                path="src/test.py",
                signal=signal,
                deposited_by="test_agent",
            ))

        # Different path
        store.deposit(Trail(
            path="src/other.py",
            signal="other_signal",
            deposited_by="test_agent",
        ))

        trails = store.read_trails("src/test.py")

        assert len(trails) == 3
        signals = [t.signal for t in trails]
        assert "signal_a" in signals
        assert "signal_b" in signals
        assert "signal_c" in signals

    def test_read_trails_deterministic_order(self, store):
        """Read trails should return results in deterministic order."""
        # Deposit in reverse order
        for signal in ["z_signal", "m_signal", "a_signal"]:
            store.deposit(Trail(
                path="src/test.py",
                signal=signal,
                deposited_by="test_agent",
            ))

        trails = store.read_trails("src/test.py")

        # Should be sorted by (trail_type, signal) ASC
        assert trails[0].signal == "a_signal"
        assert trails[1].signal == "m_signal"
        assert trails[2].signal == "z_signal"

    def test_follow_strongest_returns_best(self, store):
        """Follow strongest should return highest strength trail."""
        store.deposit(Trail(
            path="src/test.py",
            signal="weak",
            strength=0.3,
            trail_type=TrailType.QUALITY,
            deposited_by="test_agent",
        ))
        store.deposit(Trail(
            path="src/test.py",
            signal="strong",
            strength=0.9,
            trail_type=TrailType.QUALITY,
            deposited_by="test_agent",
        ))
        store.deposit(Trail(
            path="src/test.py",
            signal="medium",
            strength=0.6,
            trail_type=TrailType.QUALITY,
            deposited_by="test_agent",
        ))

        best = store.follow_strongest("src/test.py", TrailType.QUALITY)

        assert best is not None
        assert best.signal == "strong"

    def test_follow_strongest_deterministic_tiebreaker(self, store):
        """Follow strongest should use deterministic tie-breaking."""
        # Same strength, different signals
        for signal in ["zebra", "alpha", "beta"]:
            store.deposit(Trail(
                path="src/test.py",
                signal=signal,
                strength=0.5,
                trail_type=TrailType.QUALITY,
                deposited_by="test_agent",
            ))

        best = store.follow_strongest("src/test.py", TrailType.QUALITY)

        # Should return lexicographically first signal on tie
        assert best is not None
        assert best.signal == "alpha"

    def test_query_filters_correctly(self, store):
        """Query should apply all filters."""
        store.deposit(Trail(
            path="src/otto/router.py",
            signal="he2025_compliant",
            trail_type=TrailType.QUALITY,
            deposited_by="validation_agent",
        ))
        store.deposit(Trail(
            path="src/otto/detector.py",
            signal="he2025_violation:line45",
            trail_type=TrailType.QUALITY,
            deposited_by="validation_agent",
        ))
        store.deposit(Trail(
            path="src/otto/router.py",
            signal="depends_on:utils.py",
            trail_type=TrailType.CONTEXT,
            deposited_by="context_agent",
        ))

        # Query for QUALITY trails with violations
        results = store.query(TrailQuery(
            trail_type=TrailType.QUALITY,
            signal_contains="violation",
        ))

        assert len(results) == 1
        assert results[0].signal == "he2025_violation:line45"

    def test_query_deterministic_order(self, store):
        """Query results should always be in deterministic order."""
        paths = ["src/z.py", "src/a.py", "src/m.py"]
        for path in paths:
            store.deposit(Trail(
                path=path,
                signal="test",
                deposited_by="test_agent",
            ))

        results = store.query(TrailQuery())

        # Should be sorted by path ASC
        assert results[0].path == "src/a.py"
        assert results[1].path == "src/m.py"
        assert results[2].path == "src/z.py"

    def test_get_related_paths(self, store):
        """Get related paths should follow CONTEXT trails."""
        # router.py depends on utils.py
        store.deposit(Trail(
            path="src/router.py",
            signal="depends_on:src/utils.py",
            trail_type=TrailType.CONTEXT,
            deposited_by="test_agent",
        ))
        # router.py is used by main.py
        store.deposit(Trail(
            path="src/router.py",
            signal="used_by:src/main.py",
            trail_type=TrailType.CONTEXT,
            deposited_by="test_agent",
        ))

        related = store.get_related_paths("src/router.py")

        assert "src/utils.py" in related
        assert "src/main.py" in related

    def test_decay_all_prunes_dead_trails(self, store):
        """Decay all should remove trails below threshold."""
        now = datetime.now()

        # Fresh trail - should survive
        store.deposit(Trail(
            path="src/fresh.py",
            signal="alive",
            strength=1.0,
            deposited_by="test_agent",
        ))

        # Old trail - should be pruned after decay
        # We need to manually insert an old trail
        with store._connection() as conn:
            conn.execute(
                """
                INSERT INTO trails
                (trail_type, path, signal, strength, deposited_by,
                 deposited_at, reinforced_count, half_life_days, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    TrailType.QUALITY.value,
                    "src/old.py",
                    "dead",
                    0.05,  # Below threshold
                    "test_agent",
                    (now - timedelta(days=30)).isoformat(),
                    0,
                    7.0,
                    "{}",
                ),
            )

        initial_count = store.count_trails()
        assert initial_count == 2

        pruned = store.decay_all()

        assert pruned >= 1
        final_count = store.count_trails()
        assert final_count == 1

        # Fresh trail should still exist
        trails = store.read_trails("src/fresh.py")
        assert len(trails) == 1

    def test_delete_trail(self, store):
        """Delete trail should remove specific trail."""
        trail = store.deposit(Trail(
            path="src/test.py",
            signal="to_delete",
            deposited_by="test_agent",
        ))

        result = store.delete_trail(trail.id)

        assert result is True
        assert store.count_trails() == 0

    def test_clear_path(self, store):
        """Clear path should remove all trails for a path."""
        for signal in ["a", "b", "c"]:
            store.deposit(Trail(
                path="src/test.py",
                signal=signal,
                deposited_by="test_agent",
            ))

        store.deposit(Trail(
            path="src/other.py",
            signal="keep",
            deposited_by="test_agent",
        ))

        deleted = store.clear_path("src/test.py")

        assert deleted == 3
        assert store.count_trails() == 1


# =============================================================================
# Determinism Tests - [He2025] Compliance
# =============================================================================

class TestDeterminism:
    """Tests verifying [He2025] deterministic behavior."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    def test_deposit_order_independence(self, temp_db):
        """Trail reads should be independent of deposit order."""
        signals_order_1 = ["zebra", "alpha", "mike"]
        signals_order_2 = ["alpha", "mike", "zebra"]

        # First store with order 1
        store1 = TrailStore(db_path=temp_db)
        for signal in signals_order_1:
            store1.deposit(Trail(
                path="test.py",
                signal=signal,
                deposited_by="test",
            ))
        result1 = [t.signal for t in store1.read_trails("test.py")]

        # Clear and recreate with order 2
        store1.clear_path("test.py")
        for signal in signals_order_2:
            store1.deposit(Trail(
                path="test.py",
                signal=signal,
                deposited_by="test",
            ))
        result2 = [t.signal for t in store1.read_trails("test.py")]

        # Both should return same ordered list
        assert result1 == result2
        assert result1 == ["alpha", "mike", "zebra"]

    def test_query_results_reproducible(self, temp_db):
        """Same query should always produce same results."""
        store = TrailStore(db_path=temp_db)

        # Create trails
        for i in range(10):
            store.deposit(Trail(
                path=f"src/file{i}.py",
                signal=f"signal{9-i}",  # Reverse order
                deposited_by="test",
            ))

        query = TrailQuery(path_prefix="src/")

        # Run query 100 times
        results = []
        for _ in range(100):
            result = store.query(query)
            result_tuple = tuple((t.path, t.signal) for t in result)
            results.append(result_tuple)

        # All results should be identical
        assert len(set(results)) == 1

    def test_follow_strongest_reproducible(self, temp_db):
        """Follow strongest should always return same trail for ties."""
        store = TrailStore(db_path=temp_db)

        # Create multiple trails with same strength
        for signal in ["zebra", "alpha", "mike", "bravo"]:
            store.deposit(Trail(
                path="test.py",
                signal=signal,
                strength=0.5,
                trail_type=TrailType.QUALITY,
                deposited_by="test",
            ))

        # Run 100 times
        results = []
        for _ in range(100):
            best = store.follow_strongest("test.py", TrailType.QUALITY)
            results.append(best.signal)

        # Should always return "alpha" (lexicographically first)
        assert all(r == "alpha" for r in results)
