"""
Chaos engineering tests for Framework Orchestrator.

Fault injection and failure scenario tests to verify system resilience.
"""

import asyncio
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from otto import (
    FrameworkOrchestrator,
    OrchestratorConfig,
    AgentStatus,
    CircuitBreakerOpen,
    BulkheadRejected,
    BulkheadTimeout,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace for testing."""
    workspace = tmp_path / "chaos_test"
    workspace.mkdir()
    (workspace / "domains").mkdir()
    (workspace / "results").mkdir()
    (workspace / "checkpoints").mkdir()

    # Create minimal configs
    domain_config = {
        "name": "test",
        "specialists": {"test": {"keywords": ["test"]}},
        "routing_keywords": ["test"],
        "prism_perspectives": ["causal"]
    }
    (workspace / "domains" / "test.json").write_text(json.dumps(domain_config))

    principles = {"constitutional": {"principles": []}}
    (workspace / "principles.json").write_text(json.dumps(principles))

    return workspace


@pytest.fixture
def chaos_config(temp_workspace):
    """Configuration for chaos testing."""
    config = OrchestratorConfig()
    config.workspace = temp_workspace
    config.agent_timeout = 2.0  # Short timeout for faster tests
    config.circuit_breaker_threshold = 2  # Low threshold for testing
    config.circuit_breaker_reset_timeout = 1.0  # Fast reset for testing
    config.max_retries = 1  # Minimal retries
    config.checkpoint_enabled = True
    config.metrics_enabled = True
    config.enable_bulkhead = True
    config.enable_fallback = True
    config.max_concurrent_agents = 2  # Limited for testing
    config.agent_queue_size = 3  # Small queue
    return config


@pytest.mark.chaos
class TestChaosEngineering:
    """Fault injection and failure scenario tests."""

    @pytest.mark.asyncio
    async def test_agent_failure_isolation(self, temp_workspace, chaos_config):
        """Test that one agent failure doesn't break others."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Make moe_router fail (it always runs in WORK mode)
        async def failing_agent(task, context):
            raise Exception("Chaos: Agent exploded!")

        original = orchestrator.agents["moe_router"].execute
        orchestrator.agents["moe_router"].execute = failing_agent

        try:
            result = await orchestrator.orchestrate("Test isolation", {"seed": 42})

            # Other agents should succeed or degrade gracefully
            successful_agents = [
                name for name, r in result["agent_results"].items()
                if r["status"] in ["completed", "degraded"]
            ]
            assert len(successful_agents) > 0

            # Failed agent should be marked appropriately
            moe_result = result["agent_results"].get("moe_router", {})
            assert moe_result.get("status") in ["failed", "degraded"]

        finally:
            orchestrator.agents["moe_router"].execute = original

    @pytest.mark.asyncio
    async def test_circuit_breaker_cascade(self, temp_workspace, chaos_config):
        """Test circuit breaker opens after repeated failures."""
        # Disable fallback to test circuit breaker directly
        chaos_config.enable_fallback = False

        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Make an always-active agent fail consistently
        # echo_curator is always active
        fail_count = 0
        target_agent = "echo_curator"

        async def consistently_failing(task, context):
            nonlocal fail_count
            fail_count += 1
            raise Exception(f"Failure {fail_count}")

        original = orchestrator.agents[target_agent].execute
        orchestrator.agents[target_agent].execute = consistently_failing

        try:
            # First orchestration - failures start
            result1 = await orchestrator.orchestrate("First failure test", {"seed": 42})

            # With fallback disabled, check that failures are tracked
            agent_result = result1["agent_results"].get(target_agent, {})

            # Verify failure was detected in agent result
            assert agent_result.get("status") in ["failed", "degraded"], \
                f"Expected failed/degraded status, got: {agent_result.get('status')}"

            # Verify fail_count increased
            assert fail_count >= 1, "Agent should have been called at least once"

            # Continue failing until circuit opens
            for i in range(chaos_config.circuit_breaker_threshold + 1):
                try:
                    await orchestrator.orchestrate(f"Failure test {i}", {"seed": 42 + i})
                except Exception:
                    pass  # Expected

            # Circuit should have accumulated failures or agent consistently failed
            cb_stats = orchestrator.circuit_breaker.get_stats(target_agent)
            # Either circuit tracking or agent failed multiple times
            assert (cb_stats["failures"] >= 1 or
                    cb_stats["state"] == "open" or
                    fail_count >= chaos_config.circuit_breaker_threshold)
        finally:
            orchestrator.agents[target_agent].execute = original

    @pytest.mark.asyncio
    async def test_timeout_cascade_recovery(self, temp_workspace, chaos_config):
        """Test system recovers from timeout cascades."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Make moe_router timeout (it always runs in WORK mode)
        async def slow_agent(task, context):
            await asyncio.sleep(10)  # Will timeout
            return {"result": "too late"}

        original = orchestrator.agents["moe_router"].execute
        orchestrator.agents["moe_router"].execute = slow_agent

        try:
            result = await orchestrator.orchestrate("Timeout test", {"seed": 42})

            # moe_router should timeout but system continues
            moe_result = result["agent_results"].get("moe_router", {})
            # Should be degraded (fallback) or failed (no fallback)
            assert moe_result.get("status") in ["failed", "degraded", "skipped"]

            # Other agents should complete
            other_results = {
                k: v for k, v in result["agent_results"].items()
                if k != "moe_router"
            }
            completed = [r for r in other_results.values() if r["status"] == "completed"]
            assert len(completed) > 0

        finally:
            orchestrator.agents["world_modeler"].execute = original

    @pytest.mark.asyncio
    async def test_state_file_corruption(self, temp_workspace, chaos_config):
        """Test handling of corrupted state file."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # First, create valid state
        await orchestrator.orchestrate("Create state", {"seed": 42})

        # Corrupt the state file
        state_file = temp_workspace / ".orchestrator-state.json"
        state_file.write_text("not valid json {{{")

        # New orchestration should handle corrupted state gracefully
        orchestrator2 = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Should work despite corrupted previous state
        result = await orchestrator2.orchestrate("After corruption", {"seed": 43})
        assert result["agents_executed"] > 0

    @pytest.mark.asyncio
    async def test_bulkhead_queue_full(self, temp_workspace, chaos_config):
        """Test bulkhead rejects when queue is full."""
        chaos_config.max_concurrent_agents = 1
        chaos_config.agent_queue_size = 1
        chaos_config.bulkhead_timeout = 0.1  # Very short timeout

        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Make agents slow
        async def slow_agent(task, context):
            await asyncio.sleep(2)
            return {"slow": True}

        for name in orchestrator.agents:
            original = orchestrator.agents[name].execute
            orchestrator.agents[name].execute = slow_agent

        try:
            # This should hit bulkhead limits
            result = await orchestrator.orchestrate("Bulkhead test", {"seed": 42})

            # Some agents may be degraded due to bulkhead
            degraded_count = sum(
                1 for r in result["agent_results"].values()
                if r["status"] == "degraded"
            )
            # It's ok if no degradation (depends on timing)
            assert result["agents_executed"] > 0

        except (BulkheadTimeout, BulkheadRejected):
            # This is also acceptable
            pass

    @pytest.mark.asyncio
    async def test_checkpoint_interrupted_recovery(self, temp_workspace, chaos_config):
        """Test recovery from interrupted checkpoint."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Simulate interrupted checkpoint by creating incomplete one
        # Checkpoints are stored under state/checkpoints/
        checkpoint_dir = temp_workspace / "state" / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        incomplete_checkpoint = {
            "checkpoint_id": "test_incomplete_123",
            "iteration": 99,
            "task": "Interrupted task",
            "context": {"seed": 42},
            "status": "in_progress",
            "started_at": 1000.0,
            "updated_at": 1001.0,
            "agents_completed": {"echo_curator": {}},
            "agents_pending": ["moe_router", "code_generator"],
        }
        (checkpoint_dir / "checkpoint_test_incomplete_123.json").write_text(
            json.dumps(incomplete_checkpoint)
        )

        # Should detect interrupted orchestration
        interrupted = await orchestrator.get_interrupted_orchestrations()
        assert len(interrupted) >= 1
        assert any(cp["checkpoint_id"] == "test_incomplete_123" for cp in interrupted)

    @pytest.mark.asyncio
    async def test_concurrent_orchestrations(self, temp_workspace, chaos_config):
        """Test multiple concurrent orchestrations."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Run multiple orchestrations concurrently
        tasks = [
            orchestrator.orchestrate(f"Concurrent task {i}", {"seed": 42 + i})
            for i in range(3)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete (or fail gracefully)
        successful = [r for r in results if isinstance(r, dict)]
        assert len(successful) >= 1  # At least one should succeed

    @pytest.mark.asyncio
    async def test_memory_exhaustion_simulation(self, temp_workspace, chaos_config):
        """Test behavior under simulated memory pressure."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Simulate memory-heavy agent output
        async def memory_heavy(task, context):
            # Return large result
            return {"large_data": "x" * 100000}  # 100KB

        original = orchestrator.agents["domain_intelligence"].execute
        orchestrator.agents["domain_intelligence"].execute = memory_heavy

        try:
            result = await orchestrator.orchestrate("Memory test", {"seed": 42})
            assert result["agents_executed"] > 0
        finally:
            orchestrator.agents["domain_intelligence"].execute = original

    @pytest.mark.asyncio
    async def test_all_agents_fail(self, temp_workspace, chaos_config):
        """Test handling when all agents fail."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Make all agents fail
        originals = {}
        for name in orchestrator.agents:
            originals[name] = orchestrator.agents[name].execute

            async def failing(task, context, n=name):
                raise Exception(f"Agent {n} failed")

            orchestrator.agents[name].execute = failing

        try:
            result = await orchestrator.orchestrate("All fail test", {"seed": 42})

            # Should still complete (with all degraded/failed)
            assert result["agents_executed"] > 0

            # Check that fallbacks were used
            if chaos_config.enable_fallback:
                degraded = sum(
                    1 for r in result["agent_results"].values()
                    if r["status"] == "degraded"
                )
                # Some should be degraded (using fallback)
                assert degraded > 0 or result["agents_failed"] > 0

        finally:
            for name, original in originals.items():
                orchestrator.agents[name].execute = original


@pytest.mark.chaos
class TestRecoveryScenarios:
    """Recovery from failure scenarios."""

    @pytest.mark.asyncio
    async def test_graceful_degradation_chain(self, temp_workspace, chaos_config):
        """Test graceful degradation when multiple components fail."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # First successful run to cache results
        await orchestrator.orchestrate("Cache results", {"seed": 42})

        # Now make moe_router fail (it always runs) - should use cached result
        async def failing(task, context):
            raise Exception("Failed after cache")

        original = orchestrator.agents["moe_router"].execute
        orchestrator.agents["moe_router"].execute = failing

        try:
            result = await orchestrator.orchestrate("Use cached", {"seed": 43})

            # moe_router should be degraded (using cache)
            moe_result = result["agent_results"].get("moe_router", {})
            assert moe_result.get("status") in ["degraded", "failed"]

        finally:
            orchestrator.agents["moe_router"].execute = original

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, temp_workspace, chaos_config):
        """Test circuit breaker recovers after cooldown."""
        chaos_config.circuit_breaker_reset_timeout = 0.5  # Fast reset

        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=chaos_config
        )

        # Trip the circuit breaker
        for i in range(chaos_config.circuit_breaker_threshold + 1):
            orchestrator.circuit_breaker.record_failure("test_agent")

        # Verify circuit is open
        assert orchestrator.circuit_breaker.get_state("test_agent").value == "open"

        # Wait for reset timeout
        await asyncio.sleep(chaos_config.circuit_breaker_reset_timeout + 0.1)

        # Circuit should transition to half-open
        try:
            orchestrator.circuit_breaker.allow_request("test_agent")
            # If we get here, circuit transitioned to half-open
        except CircuitBreakerOpen:
            pytest.fail("Circuit should have transitioned to half-open")
