"""
Tests for Agent Base Classes
============================

Tests for the foundation agent infrastructure.
"""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path

from otto.agents import (
    Agent,
    AgentConfig,
    AgentResult,
    AgentProgress,
    AgentState,
    AgentError,
    RetryableError,
    NonRetryableError,
)


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_config(self):
        """Default configuration values."""
        config = AgentConfig(agent_type="test")
        assert config.agent_type == "test"
        assert config.max_turns == 10
        assert config.timeout_seconds == 300.0
        assert config.max_retries == 3
        assert config.burnout_level == "GREEN"
        assert config.energy_level == "medium"

    def test_should_reduce_scope_orange_burnout(self):
        """Reduce scope on ORANGE burnout."""
        config = AgentConfig(agent_type="test", burnout_level="ORANGE")
        assert config.should_reduce_scope()

    def test_should_reduce_scope_red_burnout(self):
        """Reduce scope on RED burnout."""
        config = AgentConfig(agent_type="test", burnout_level="RED")
        assert config.should_reduce_scope()

    def test_should_reduce_scope_depleted(self):
        """Reduce scope when depleted."""
        config = AgentConfig(agent_type="test", energy_level="depleted")
        assert config.should_reduce_scope()

    def test_should_not_reduce_scope_healthy(self):
        """Don't reduce scope when healthy."""
        config = AgentConfig(agent_type="test", burnout_level="GREEN", energy_level="high")
        assert not config.should_reduce_scope()

    def test_effective_max_turns_red(self):
        """Max turns reduced on RED burnout."""
        config = AgentConfig(agent_type="test", max_turns=10, burnout_level="RED")
        assert config.effective_max_turns() == 3

    def test_effective_max_turns_orange(self):
        """Max turns reduced on ORANGE burnout."""
        config = AgentConfig(agent_type="test", max_turns=10, burnout_level="ORANGE")
        assert config.effective_max_turns() == 5

    def test_effective_max_turns_depleted(self):
        """Max turns reduced when depleted."""
        config = AgentConfig(agent_type="test", max_turns=10, energy_level="depleted")
        assert config.effective_max_turns() == 5

    def test_effective_max_turns_normal(self):
        """Normal max turns when healthy."""
        config = AgentConfig(agent_type="test", max_turns=10)
        assert config.effective_max_turns() == 10

    def test_can_spawn_child(self):
        """Can spawn child when not at max depth."""
        config = AgentConfig(agent_type="test", depth=1, max_depth=3)
        assert config.can_spawn_child()

    def test_cannot_spawn_child_max_depth(self):
        """Cannot spawn child at max depth."""
        config = AgentConfig(agent_type="test", depth=3, max_depth=3)
        assert not config.can_spawn_child()

    def test_cannot_spawn_child_burnout(self):
        """Cannot spawn child on burnout."""
        config = AgentConfig(agent_type="test", depth=1, burnout_level="ORANGE")
        assert not config.can_spawn_child()


class TestAgentProgress:
    """Tests for AgentProgress."""

    def test_create_progress(self):
        """Create progress update."""
        progress = AgentProgress(
            agent_id="test-123",
            current_step=2,
            total_steps=5,
            step_description="Processing",
            percentage=40.0,
        )
        assert progress.agent_id == "test-123"
        assert progress.percentage == 40.0

    def test_to_dict(self):
        """Progress can be serialized."""
        progress = AgentProgress(
            agent_id="test-123",
            current_step=2,
            total_steps=5,
            step_description="Processing",
            percentage=40.0,
        )
        data = progress.to_dict()
        assert "agent_id" in data
        assert "percentage" in data
        assert "timestamp" in data

    def test_format_display(self):
        """Progress can be formatted for display."""
        progress = AgentProgress(
            agent_id="test-123",
            current_step=2,
            total_steps=5,
            step_description="Processing",
            percentage=40.0,
        )
        display = progress.format_display()
        assert "40%" in display
        assert "Step 2/5" in display
        assert "Processing" in display


class TestAgentResult:
    """Tests for AgentResult."""

    def test_create_success_result(self):
        """Create successful result."""
        result = AgentResult(
            agent_id="test-123",
            agent_type="test",
            success=True,
            result={"value": 42},
        )
        assert result.success
        assert result.result["value"] == 42
        assert len(result.checksum) == 8

    def test_create_failure_result(self):
        """Create failure result."""
        result = AgentResult(
            agent_id="test-123",
            agent_type="test",
            success=False,
            result={},
            errors=["Something went wrong"],
        )
        assert not result.success
        assert len(result.errors) == 1

    def test_to_dict_roundtrip(self):
        """Result serialization roundtrip."""
        original = AgentResult(
            agent_id="test-123",
            agent_type="test",
            success=True,
            result={"key": "value"},
            files_read=["file1.py"],
            duration_seconds=1.5,
        )
        data = original.to_dict()
        restored = AgentResult.from_dict(data)

        assert restored.agent_id == original.agent_id
        assert restored.success == original.success
        assert restored.result == original.result
        assert restored.files_read == original.files_read


class SimpleTestAgent(Agent[dict]):
    """Simple agent for testing."""

    agent_type = "simple_test"

    def __init__(self, config=None, steps=3, should_fail=False, should_retry=False):
        super().__init__(config)
        self._steps = steps
        self._should_fail = should_fail
        self._should_retry = should_retry
        self._retry_count = 0

    def _get_step_count(self) -> int:
        return self._steps

    async def _execute(self, task: str, context: dict) -> dict:
        for i in range(1, self._steps + 1):
            await self.report_progress(i, f"Step {i}")
            self.increment_turn()

            if self._should_retry and self._retry_count == 0:
                self._retry_count += 1
                raise RetryableError("Retry me")

            if self._should_fail and i == self._steps:
                raise NonRetryableError("Intentional failure")

        return {"completed": True, "task": task}


class TestAgent:
    """Tests for Agent base class."""

    @pytest.mark.asyncio
    async def test_run_success(self):
        """Successful agent execution."""
        agent = SimpleTestAgent()
        result = await agent.run("test task", {})

        assert result.success
        assert result.result["completed"]
        assert result.turn_count == 3
        assert agent.state == AgentState.COMPLETED

    @pytest.mark.asyncio
    async def test_run_with_progress(self):
        """Agent reports progress."""
        agent = SimpleTestAgent()
        progress_updates = []
        agent.on_progress(lambda p: progress_updates.append(p))

        await agent.run("test task", {})

        # Should have progress updates (plus initial)
        assert len(progress_updates) >= 3

    @pytest.mark.asyncio
    async def test_run_failure(self):
        """Agent handles failure."""
        agent = SimpleTestAgent(should_fail=True)
        result = await agent.run("test task", {})

        assert not result.success
        assert len(result.errors) > 0
        assert agent.state == AgentState.FAILED

    @pytest.mark.asyncio
    async def test_run_with_retry(self):
        """Agent retries on retryable error."""
        config = AgentConfig(agent_type="simple_test", retry_delay=0.01)
        agent = SimpleTestAgent(config=config, should_retry=True)
        result = await agent.run("test task", {})

        assert result.success
        assert result.retries_used == 1

    @pytest.mark.asyncio
    async def test_agent_id_unique(self):
        """Each agent has unique ID."""
        agent1 = SimpleTestAgent()
        agent2 = SimpleTestAgent()
        assert agent1.agent_id != agent2.agent_id

    @pytest.mark.asyncio
    async def test_agent_tracks_files(self):
        """Agent tracks file access."""
        agent = SimpleTestAgent()
        agent.track_file_read("file1.py")
        agent.track_file_modified("file2.py")

        result = await agent.run("test", {})

        assert "file1.py" in result.files_read
        assert "file2.py" in result.files_modified

    @pytest.mark.asyncio
    async def test_agent_max_turns(self):
        """Agent respects max turns."""
        config = AgentConfig(agent_type="simple_test", max_turns=2)
        agent = SimpleTestAgent(config=config, steps=5)
        result = await agent.run("test", {})

        assert not result.success
        assert "Max turns" in result.errors[0]

    @pytest.mark.asyncio
    async def test_agent_timeout(self):
        """Agent respects timeout."""
        class SlowAgent(Agent[dict]):
            agent_type = "slow"

            def _get_step_count(self) -> int:
                return 1

            async def _execute(self, task: str, context: dict) -> dict:
                await asyncio.sleep(10)  # Too slow
                return {}

        config = AgentConfig(agent_type="slow", timeout_seconds=0.1, max_retries=0)
        agent = SlowAgent(config)
        result = await agent.run("test", {})

        assert not result.success
        assert "Timeout" in result.errors[0]


class TestAgentErrors:
    """Tests for agent error types."""

    def test_retryable_error(self):
        """RetryableError has retry_after."""
        error = RetryableError("Try again", retry_after=5.0)
        assert error.retry_after == 5.0
        assert "Try again" in str(error)

    def test_non_retryable_error(self):
        """NonRetryableError is final."""
        error = NonRetryableError("Fatal error")
        assert "Fatal error" in str(error)
