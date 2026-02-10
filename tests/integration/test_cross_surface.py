"""
Cross-Surface State Integration Tests
=====================================

Tests that state flows correctly across surfaces.

This is THE core value proposition of OTTO's memory backbone:
Actions in one surface (CLI) are visible in another (Telegram).

Determinism:
- Tests use real memory instances
- Verify state consistency across surfaces
- Verify trail strength is shared
"""

import pytest
from otto.memory.interface import OTTOMemory, Episode, Outcome


class TestCrossSurfaceVisibility:
    """Test that episodes are visible across surfaces."""

    def test_episode_visible_across_surfaces(self, real_memory: OTTOMemory, mock_surface):
        """Episode recorded in one surface should be visible in another."""
        # CLI records an episode
        cli = mock_surface("cli", real_memory)
        cli.record_action("calendar.create", {"title": "Dentist", "time": "2pm"})

        # Telegram queries episodes
        telegram = mock_surface("telegram", real_memory)
        episodes = telegram.memory.query_episodes(
            event_type="surface.cli.calendar.create"
        )

        assert len(episodes) >= 1
        assert episodes[0].data["title"] == "Dentist"

    def test_multiple_surfaces_same_memory(self, real_memory: OTTOMemory, mock_surface):
        """Multiple surfaces should share the same memory instance."""
        cli = mock_surface("cli", real_memory)
        telegram = mock_surface("telegram", real_memory)
        discord = mock_surface("discord", real_memory)

        # All should share same memory
        assert cli.memory is telegram.memory
        assert telegram.memory is discord.memory

    def test_surface_isolation_by_type(self, real_memory: OTTOMemory, mock_surface):
        """Episodes should be filterable by surface."""
        cli = mock_surface("cli", real_memory)
        telegram = mock_surface("telegram", real_memory)

        # Record from both surfaces
        cli.record_action("task.create", {"title": "CLI Task"})
        telegram.record_action("task.create", {"title": "Telegram Task"})

        # Query by surface
        cli_episodes = real_memory.query_episodes(
            event_type="surface.cli.task.create"
        )
        telegram_episodes = real_memory.query_episodes(
            event_type="surface.telegram.task.create"
        )

        assert len(cli_episodes) == 1
        assert len(telegram_episodes) == 1
        assert cli_episodes[0].data["title"] == "CLI Task"
        assert telegram_episodes[0].data["title"] == "Telegram Task"


class TestCrossSurfaceTrails:
    """Test that trail strength is shared across surfaces."""

    def test_trail_strength_shared(self, real_memory: OTTOMemory, mock_surface):
        """Trail built in one surface should affect decisions in another."""
        cli = mock_surface("cli", real_memory)
        telegram = mock_surface("telegram", real_memory)

        action = "calendar.create"

        # Build trust via CLI (10 successful creates)
        for _ in range(10):
            cli.memory.deposit_trail(f"action.{action}", outcome=Outcome.SUCCESS)

        # Check trust from Telegram perspective
        trail = telegram.memory.follow_trail(f"action.{action}")

        # Should be significant (above auto-approve)
        assert trail.strength > 0.5

    def test_trust_building_across_surfaces(self, real_memory: OTTOMemory, mock_surface):
        """Trust should accumulate regardless of which surface deposits."""
        cli = mock_surface("cli", real_memory)
        telegram = mock_surface("telegram", real_memory)
        discord = mock_surface("discord", real_memory)

        action = "tasks.create"

        # Each surface contributes
        cli.memory.deposit_trail(f"action.{action}", outcome=Outcome.SUCCESS)
        telegram.memory.deposit_trail(f"action.{action}", outcome=Outcome.SUCCESS)
        discord.memory.deposit_trail(f"action.{action}", outcome=Outcome.SUCCESS)

        # Total should be sum of all
        trail = real_memory.follow_trail(f"action.{action}")
        assert trail.strength > 0

    def test_failure_in_one_surface_affects_others(self, real_memory: OTTOMemory, mock_surface):
        """Failure recorded in one surface should affect trust globally."""
        cli = mock_surface("cli", real_memory)
        telegram = mock_surface("telegram", real_memory)

        action = "email.send"

        # Build trust via CLI
        for _ in range(5):
            cli.memory.deposit_trail(f"action.{action}", outcome=Outcome.SUCCESS)

        trust_after_build = real_memory.follow_trail(f"action.{action}").strength

        # Failure in Telegram
        telegram.memory.deposit_trail(f"action.{action}", outcome=Outcome.FAILURE)

        # Global trust should decrease
        trust_after_failure = real_memory.follow_trail(f"action.{action}").strength
        assert trust_after_failure < trust_after_build


class TestCrossSurfaceScenarios:
    """End-to-end scenarios involving multiple surfaces."""

    def test_task_lifecycle_across_surfaces(self, real_memory: OTTOMemory, mock_surface):
        """
        Scenario: Create task in CLI, check in Telegram, complete in Discord.

        This tests the core cross-surface workflow.
        """
        cli = mock_surface("cli", real_memory)
        telegram = mock_surface("telegram", real_memory)
        discord = mock_surface("discord", real_memory)

        task_id = "task_123"

        # CLI: Create task
        cli.record_action("task.create", {"task_id": task_id, "title": "Write report"})

        # Telegram: Query to see task exists
        all_tasks = telegram.memory.query_episodes(
            event_type_prefix="surface.cli.task"
        )
        assert len(all_tasks) >= 1
        assert any(e.data.get("title") == "Write report" for e in all_tasks)

        # Discord: Complete task
        discord.record_action("task.complete", {"task_id": task_id})

        # Verify full history
        all_task_events = real_memory.query_episodes()
        surfaces = {e.type.split(".")[1] for e in all_task_events if e.type.startswith("surface.")}
        assert "cli" in surfaces
        assert "discord" in surfaces

    def test_approval_trust_builds_globally(self, real_memory: OTTOMemory, mock_surface):
        """
        Scenario: User approves actions across different surfaces,
        trust builds globally until auto-approval kicks in.
        """
        cli = mock_surface("cli", real_memory)
        telegram = mock_surface("telegram", real_memory)

        action = "calendar.delete"

        # Start with no trust
        initial = real_memory.follow_trail(f"action.{action}")
        initial_strength = initial.strength if initial else 0.0

        # Approve in CLI (simulated)
        for _ in range(3):
            cli.memory.deposit_trail(f"action.{action}", outcome=Outcome.SUCCESS)
            cli.record_action("approval.granted", {"action": action})

        # Approve in Telegram (simulated)
        for _ in range(3):
            telegram.memory.deposit_trail(f"action.{action}", outcome=Outcome.SUCCESS)
            telegram.record_action("approval.granted", {"action": action})

        # Trust should be significantly higher
        final = real_memory.follow_trail(f"action.{action}")
        assert final.strength > initial_strength

    def test_session_continuity_across_surfaces(self, temp_data_dir, mock_surface):
        """
        Scenario: User works in CLI session, then continues in Telegram.
        State should persist and be visible.
        """
        # Session 1: CLI work
        memory1 = OTTOMemory(data_dir=temp_data_dir)
        cli = mock_surface("cli", memory1)

        cli.record_action("session.start", {"goal": "Write report"})
        cli.record_action("document.edit", {"changes": 10})
        memory1.deposit_trail("action.document.edit", outcome=Outcome.SUCCESS)

        # Close session
        del memory1, cli

        # Session 2: Continue in Telegram
        memory2 = OTTOMemory(data_dir=temp_data_dir)
        telegram = mock_surface("telegram", memory2)

        # Should see CLI history
        history = telegram.memory.query_episodes(event_type="surface.cli.document.edit")
        assert len(history) >= 1

        # Trail strength should persist
        trail = telegram.memory.follow_trail("action.document.edit")
        assert trail.strength > 0


class TestCrossSurfaceDeterminism:
    """Test determinism across surfaces."""

    def test_same_actions_same_trust(self, temp_data_dir, mock_surface):
        """Same sequence of actions should produce same trust level."""
        trust_levels = []

        for run in range(3):
            memory = OTTOMemory(data_dir=temp_data_dir / f"run_{run}")
            cli = mock_surface("cli", memory)
            telegram = mock_surface("telegram", memory)

            # Same sequence
            for i in range(5):
                cli.memory.deposit_trail("action.test", outcome=Outcome.SUCCESS)
                telegram.memory.deposit_trail("action.test", outcome=Outcome.SUCCESS)

            trust_levels.append(memory.follow_trail("action.test").strength)

        # All should be identical
        assert len(set(trust_levels)) == 1, f"Trust varied: {trust_levels}"

    def test_episode_ordering_deterministic(self, real_memory: OTTOMemory, mock_surface):
        """Episode ordering should be deterministic across queries."""
        cli = mock_surface("cli", real_memory)
        telegram = mock_surface("telegram", real_memory)

        # Create interleaved episodes
        cli.record_action("action1", {})
        telegram.record_action("action2", {})
        cli.record_action("action3", {})

        # Query multiple times
        results1 = real_memory.query_episodes()
        results2 = real_memory.query_episodes()

        types1 = [e.type for e in results1]
        types2 = [e.type for e in results2]

        assert types1 == types2
