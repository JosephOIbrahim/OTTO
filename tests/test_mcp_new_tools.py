"""
Tests for New MCP Tools
========================

Tests the MCP tools added for:
- [He2025] verification (otto_verify_determinism)
- Trail operations (otto-trails-mcp)

Note: These tests verify the handler functions directly without
requiring a running MCP server.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path

from otto.hooks.auto_validate import validate_file, check_he2025_compliance
from otto.trails import Trail, TrailStore, TrailType


# =============================================================================
# otto_verify_determinism Tests
# =============================================================================

class TestVerifyDeterminism:
    """Tests for [He2025] verification via MCP."""

    @pytest.fixture
    def compliant_code(self):
        """Python code that is [He2025] compliant."""
        return '''
from otto.determinism import sorted_max, kahan_sum, DETERMINISM_SEED
import random

random.seed(DETERMINISM_SEED)

def get_best_score(scores: dict) -> tuple:
    """Get highest scoring item deterministically."""
    return sorted_max(scores)

def total_score(values: list) -> float:
    """Sum values with batch invariance."""
    return kahan_sum(values)

def process_items(items: set) -> list:
    """Process items in deterministic order."""
    return [process(x) for x in sorted(items)]
'''

    @pytest.fixture
    def non_compliant_code(self):
        """Python code with [He2025] violations."""
        return '''
import random

def get_best_score(scores: dict) -> tuple:
    """Get highest scoring item - VIOLATION: uses max on dict."""
    return max(scores.items(), key=lambda x: x[1])

def pick_random(items: list) -> any:
    """Pick random item - VIOLATION: unseeded random."""
    return random.choice(items)

def process_items(items: set) -> list:
    """Process items - VIOLATION: iterating over set."""
    for item in set(items):
        process(item)
'''

    def test_compliant_code_passes(self, compliant_code):
        """Compliant code should have no violations."""
        violations, compliances = check_he2025_compliance(compliant_code)

        assert len(violations) == 0
        assert len(compliances) > 0

        types = [c["type"] for c in compliances]
        assert "uses_sorted_max" in types
        assert "uses_kahan_sum" in types

    def test_non_compliant_code_fails(self, non_compliant_code):
        """Non-compliant code should have violations."""
        violations, compliances = check_he2025_compliance(non_compliant_code)

        assert len(violations) >= 2

        types = [v["type"] for v in violations]
        assert "max_on_dict_items" in types
        assert "unseeded_random" in types

    def test_validate_file_function(self, compliant_code):
        """validate_file should work on actual files."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(compliant_code)
            path = f.name

        try:
            result = validate_file(path)

            assert result["is_compliant"]
            assert len(result["violations"]) == 0
            assert len(result["compliances"]) > 0
        finally:
            Path(path).unlink()

    def test_validate_file_returns_line_numbers(self, non_compliant_code):
        """Violations should include line numbers."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(non_compliant_code)
            path = f.name

        try:
            result = validate_file(path)

            assert not result["is_compliant"]
            for violation in result["violations"]:
                assert "line" in violation
                assert isinstance(violation["line"], int)
                assert violation["line"] > 0
        finally:
            Path(path).unlink()


# =============================================================================
# Trail MCP Handler Tests
# =============================================================================

class TestTrailMCPHandlers:
    """Tests for trail MCP handler functions."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create a TrailStore with temporary database."""
        return TrailStore(db_path=temp_db)

    def test_read_trails_empty(self, store):
        """Reading trails for path with no trails returns empty."""
        trails = store.read_trails("nonexistent.py")
        assert len(trails) == 0

    def test_deposit_and_read_trail(self, store):
        """Should deposit and read back a trail."""
        trail = Trail(
            path="src/otto/test.py",
            signal="he2025_compliant",
            trail_type=TrailType.QUALITY,
            deposited_by="test",
        )

        result = store.deposit(trail)

        assert result.id is not None
        assert result.signal == "he2025_compliant"

        trails = store.read_trails("src/otto/test.py")
        assert len(trails) == 1
        assert trails[0].signal == "he2025_compliant"

    def test_reinforce_trail(self, store):
        """Should reinforce an existing trail."""
        trail = Trail(
            path="src/otto/test.py",
            signal="good_pattern",
            trail_type=TrailType.PATTERN,
            strength=0.5,
            deposited_by="test",
        )
        store.deposit(trail)

        result = store.reinforce(
            path="src/otto/test.py",
            signal="good_pattern",
            trail_type=TrailType.PATTERN,
            boost=0.2,
        )

        assert result is not None
        assert result.strength == pytest.approx(0.7, abs=0.01)
        assert result.reinforced_count == 1

    def test_query_trails_by_type(self, store):
        """Should query trails filtered by type."""
        store.deposit(Trail(
            path="src/test.py",
            signal="quality_signal",
            trail_type=TrailType.QUALITY,
            deposited_by="test",
        ))
        store.deposit(Trail(
            path="src/test.py",
            signal="context_signal",
            trail_type=TrailType.CONTEXT,
            deposited_by="test",
        ))

        from otto.trails import TrailQuery

        quality_trails = store.query(TrailQuery(trail_type=TrailType.QUALITY))
        context_trails = store.query(TrailQuery(trail_type=TrailType.CONTEXT))

        assert len(quality_trails) == 1
        assert quality_trails[0].signal == "quality_signal"

        assert len(context_trails) == 1
        assert context_trails[0].signal == "context_signal"

    def test_get_related_paths(self, store):
        """Should follow CONTEXT trails to find related files."""
        store.deposit(Trail(
            path="src/router.py",
            signal="depends_on:src/utils.py",
            trail_type=TrailType.CONTEXT,
            deposited_by="test",
        ))
        store.deposit(Trail(
            path="src/router.py",
            signal="used_by:src/main.py",
            trail_type=TrailType.CONTEXT,
            deposited_by="test",
        ))

        related = store.get_related_paths("src/router.py")

        assert "src/utils.py" in related
        assert "src/main.py" in related

    def test_decay_prunes_old_trails(self, store):
        """Should prune trails below threshold after decay."""
        from datetime import datetime, timedelta

        # Insert a very weak, old trail directly
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
                    "dead_signal",
                    0.05,  # Below threshold
                    "test",
                    (datetime.now() - timedelta(days=30)).isoformat(),
                    0,
                    7.0,
                    "{}",
                ),
            )

        # Also add a fresh trail
        store.deposit(Trail(
            path="src/fresh.py",
            signal="alive",
            deposited_by="test",
        ))

        initial_count = store.count_trails()
        assert initial_count == 2

        pruned = store.decay_all()

        assert pruned >= 1
        final_count = store.count_trails()
        assert final_count == 1


# =============================================================================
# Determinism Tests
# =============================================================================

class TestMCPDeterminism:
    """Tests for [He2025] determinism in MCP handlers."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def store(self, temp_db):
        """Create a TrailStore with temporary database."""
        return TrailStore(db_path=temp_db)

    def test_query_order_deterministic(self, store):
        """Query results should always be in the same order."""
        # Deposit trails in random order
        signals = ["zebra", "alpha", "mike", "bravo", "charlie"]
        for signal in signals:
            store.deposit(Trail(
                path="src/test.py",
                signal=signal,
                trail_type=TrailType.QUALITY,
                deposited_by="test",
            ))

        # Query multiple times
        from otto.trails import TrailQuery

        results = []
        for _ in range(10):
            trails = store.query(TrailQuery(path="src/test.py"))
            result_signals = tuple(t.signal for t in trails)
            results.append(result_signals)

        # All results should be identical
        assert len(set(results)) == 1

        # Should be sorted alphabetically
        expected = tuple(sorted(signals))
        assert results[0] == expected

    def test_read_trails_order_deterministic(self, store):
        """read_trails should always return same order."""
        # Deposit with different types in mixed order
        store.deposit(Trail(
            path="src/test.py",
            signal="z_signal",
            trail_type=TrailType.CONTEXT,
            deposited_by="test",
        ))
        store.deposit(Trail(
            path="src/test.py",
            signal="a_signal",
            trail_type=TrailType.QUALITY,
            deposited_by="test",
        ))
        store.deposit(Trail(
            path="src/test.py",
            signal="m_signal",
            trail_type=TrailType.QUALITY,
            deposited_by="test",
        ))

        # Read multiple times
        results = []
        for _ in range(10):
            trails = store.read_trails("src/test.py")
            result_tuple = tuple((t.trail_type.value, t.signal) for t in trails)
            results.append(result_tuple)

        # All should be identical
        assert len(set(results)) == 1
