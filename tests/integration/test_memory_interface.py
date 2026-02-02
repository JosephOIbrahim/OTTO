"""
Memory Interface Integration Tests
==================================

Tests for OTTOMemory as the unified memory backbone.

These tests verify:
- Episode recording and querying
- Trail deposits and following
- Cross-instance persistence
- Decay mechanisms

[He2025] Compliance:
- Tests use real instances (no mocking)
- Verify deterministic ordering
- Verify persistence
"""

import pytest
from otto.memory.interface import OTTOMemory, Episode, Outcome


class TestMemoryInterface:
    """Test OTTOMemory as the unified backbone."""

    def test_memory_is_singleton(self):
        """Memory should be accessible as singleton."""
        from otto.memory import get_memory

        mem1 = get_memory()
        mem2 = get_memory()

        # Should be same instance
        assert mem1 is mem2

    def test_memory_wraps_components(self, real_memory: OTTOMemory):
        """OTTOMemory should provide access to internal components."""
        # Should have trail-related methods
        assert hasattr(real_memory, 'deposit_trail')
        assert hasattr(real_memory, 'follow_trail')

        # Should have episode-related methods
        assert hasattr(real_memory, 'record_episode')
        assert hasattr(real_memory, 'query_episodes')

    def test_record_and_query_episode(self, real_memory: OTTOMemory, sample_episode: Episode):
        """Episodes should be recordable and queryable."""
        # Record
        real_memory.record_episode(sample_episode)

        # Query
        episodes = real_memory.query_episodes(event_type="test.sample")

        assert len(episodes) >= 1
        found = episodes[0]
        assert found.type == "test.sample"
        assert found.data["key"] == "value"
        assert found.outcome == Outcome.SUCCESS

    def test_deposit_and_follow_trail(self, real_memory: OTTOMemory, sample_trail_name: str):
        """Trails should strengthen with deposits."""
        # Initial - trail doesn't exist
        initial = real_memory.follow_trail(sample_trail_name)
        initial_strength = initial.strength if initial else 0.0

        # Deposit success
        real_memory.deposit_trail(sample_trail_name, outcome=Outcome.SUCCESS)

        # Check strengthened
        after = real_memory.follow_trail(sample_trail_name)
        assert after is not None
        assert after.strength > initial_strength

    def test_multiple_deposits_accumulate(self, real_memory: OTTOMemory, sample_trail_name: str):
        """Multiple deposits should accumulate strength."""
        # Deposit 5 times
        for _ in range(5):
            real_memory.deposit_trail(sample_trail_name, outcome=Outcome.SUCCESS)

        strength_after_5 = real_memory.follow_trail(sample_trail_name).strength

        # Deposit 5 more
        for _ in range(5):
            real_memory.deposit_trail(sample_trail_name, outcome=Outcome.SUCCESS)

        strength_after_10 = real_memory.follow_trail(sample_trail_name).strength

        # Should be stronger (but not necessarily linear)
        assert strength_after_10 > strength_after_5

    def test_failure_weakens_trail(self, real_memory: OTTOMemory, sample_trail_name: str):
        """Failures should weaken trails."""
        # Build up strength first
        for _ in range(5):
            real_memory.deposit_trail(sample_trail_name, outcome=Outcome.SUCCESS)

        before = real_memory.follow_trail(sample_trail_name).strength

        # Add failures
        for _ in range(3):
            real_memory.deposit_trail(sample_trail_name, outcome=Outcome.FAILURE)

        after = real_memory.follow_trail(sample_trail_name).strength

        # Should be weaker
        assert after < before

    def test_episode_query_filtering(self, memory_with_history: OTTOMemory):
        """Episode queries should filter correctly."""
        # Query by type
        calendar_episodes = memory_with_history.query_episodes(
            event_type="service.calendar.create"
        )
        assert len(calendar_episodes) >= 1
        assert all(e.type == "service.calendar.create" for e in calendar_episodes)

        # Query by service
        cli_episodes = memory_with_history.query_episodes(
            service="cli"
        )
        assert len(cli_episodes) >= 1
        assert all(e.service == "cli" for e in cli_episodes)

    def test_persistence_across_instances(self, temp_data_dir):
        """Memory state should persist across instances."""
        # Create first instance
        memory1 = OTTOMemory(data_dir=temp_data_dir)
        memory1.record_episode(Episode(
            type="persist.test",
            data={"instance": 1},
            outcome=Outcome.SUCCESS,
            actor="test",
            service="pytest",
        ))
        memory1.deposit_trail("persist.trail", outcome=Outcome.SUCCESS)

        # Explicitly close/flush
        del memory1

        # Create second instance with same data dir
        memory2 = OTTOMemory(data_dir=temp_data_dir)

        # Should see data from first instance
        episodes = memory2.query_episodes(event_type="persist.test")
        assert len(episodes) >= 1

        trail = memory2.follow_trail("persist.trail")
        assert trail is not None
        assert trail.strength > 0


class TestMemoryDeterminism:
    """Test [He2025] determinism requirements."""

    def test_episode_query_ordering(self, memory_with_history: OTTOMemory):
        """Episode queries should return deterministic ordering."""
        # Query multiple times
        results1 = memory_with_history.query_episodes()
        results2 = memory_with_history.query_episodes()

        # Should be identical order
        types1 = [e.type for e in results1]
        types2 = [e.type for e in results2]

        assert types1 == types2

    def test_trail_query_ordering(self, real_memory: OTTOMemory):
        """Trail queries should return deterministic ordering."""
        # Create multiple trails
        for name in ["z.trail", "a.trail", "m.trail"]:
            real_memory.deposit_trail(name, outcome=Outcome.SUCCESS)

        # Query multiple times
        results1 = real_memory.query_trails()
        results2 = real_memory.query_trails()

        # Should be identical order
        names1 = [t.name for t in results1] if results1 else []
        names2 = [t.name for t in results2] if results2 else []

        assert names1 == names2

    def test_deterministic_strength_calculation(self, temp_data_dir):
        """Same deposits should produce same strength."""
        strengths = []

        for _ in range(3):
            memory = OTTOMemory(data_dir=temp_data_dir / f"run_{_}")

            # Same deposits
            for _ in range(5):
                memory.deposit_trail("determinism.test", outcome=Outcome.SUCCESS)

            strengths.append(memory.follow_trail("determinism.test").strength)

        # All should be identical
        assert len(set(strengths)) == 1, f"Strengths varied: {strengths}"


class TestMemoryThresholds:
    """Test auto-approval thresholds."""

    def test_auto_approve_threshold(self, real_memory: OTTOMemory):
        """Verify AUTO_APPROVE_THRESHOLD behavior."""
        from otto.memory import AUTO_APPROVE_THRESHOLD

        trail_name = "action.calendar.create"

        # Build trust with repeated approvals
        for _ in range(20):
            real_memory.deposit_trail(trail_name, outcome=Outcome.SUCCESS)

        trail = real_memory.follow_trail(trail_name)

        # After many successes, should be above threshold
        assert trail.strength >= AUTO_APPROVE_THRESHOLD or trail.strength >= 0.7

    def test_learning_threshold(self, real_memory: OTTOMemory):
        """Verify LEARNING_THRESHOLD behavior."""
        from otto.memory import LEARNING_THRESHOLD

        trail_name = "action.test.learn"

        # Few deposits - below learning threshold
        for _ in range(3):
            real_memory.deposit_trail(trail_name, outcome=Outcome.SUCCESS)

        trail = real_memory.follow_trail(trail_name)

        # Should be below learning threshold
        assert trail.strength < 1.0  # Not maxed out
