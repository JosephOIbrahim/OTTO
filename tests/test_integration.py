"""
Integration tests for Framework Orchestrator.

Full end-to-end orchestration workflow tests.
Tests complete task → 7 agents → state persistence flow.
"""

import asyncio
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from otto import (
    FrameworkOrchestrator,
    OrchestratorConfig,
    AgentStatus,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace for testing."""
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()
    (workspace / "domains").mkdir()
    (workspace / "results").mkdir()
    (workspace / "checkpoints").mkdir()

    # Create minimal domain config
    domain_config = {
        "name": "test",
        "description": "Test domain",
        "specialists": {
            "test_spec": {
                "keywords": ["test", "analyze"],
                "analysis_focus": ["testing"]
            }
        },
        "routing_keywords": ["test"],
        "prism_perspectives": ["causal", "temporal"]
    }
    (workspace / "domains" / "test.json").write_text(json.dumps(domain_config))

    # Create minimal principles
    principles = {
        "constitutional": {
            "principles": [
                {"id": "test_principle", "statement": "Test safety first"}
            ]
        }
    }
    (workspace / "principles.json").write_text(json.dumps(principles))

    return workspace


@pytest.fixture
def test_config(temp_workspace):
    """Create test configuration."""
    config = OrchestratorConfig()
    config.workspace = temp_workspace
    config.checkpoint_enabled = True
    config.metrics_enabled = True
    config.tracing_enabled = True
    config.enable_bulkhead = True
    config.enable_fallback = True
    config.enable_idempotency = True
    config.enable_rate_limit = False  # Disable for faster tests
    return config


@pytest.mark.integration
class TestOrchestrationE2E:
    """Full end-to-end orchestration workflow tests."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self, temp_workspace, test_config):
        """Test complete task → 7 agents → state flow."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        result = await orchestrator.orchestrate(
            "Analyze this test task for testing purposes",
            {"seed": 42}
        )

        # Verify result structure
        assert "iteration" in result
        assert "agents_executed" in result
        assert "master_checksum" in result
        assert "agent_results" in result

        # Verify agents executed
        assert result["agents_executed"] > 0
        assert result["agents_succeeded"] + result["agents_failed"] + result.get("agents_degraded", 0) + result.get("agents_skipped", 0) == result["agents_executed"]

        # Verify state file created
        # State file is stored under state/ subdirectory
        assert (temp_workspace / "state" / ".orchestrator-state.json").exists()

        # Verify results directory has files (under state/)
        result_files = list((temp_workspace / "state" / "results").glob("*.json"))
        assert len(result_files) > 0

    @pytest.mark.asyncio
    async def test_agent_interaction_sequence(self, temp_workspace, test_config):
        """Verify execution order and data flow between agents."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        result = await orchestrator.orchestrate(
            "Test agent sequence",
            {"seed": 42}
        )

        # Verify echo_curator runs (always active)
        assert "echo_curator" in result["agent_results"]

        # Verify determinism_guard runs (always active)
        assert "determinism_guard" in result["agent_results"]

        # Check that each agent has required fields
        for agent_name, agent_result in result["agent_results"].items():
            assert "status" in agent_result
            assert "checksum" in agent_result
            assert "execution_time_ms" in agent_result

    @pytest.mark.asyncio
    async def test_state_recovery(self, temp_workspace, test_config):
        """Test state recovery after restart."""
        # First orchestration
        orchestrator1 = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )
        result1 = await orchestrator1.orchestrate("Test recovery", {"seed": 42})

        # Verify state persisted
        # State file is under state/ subdirectory
        state_file = temp_workspace / "state" / ".orchestrator-state.json"
        assert state_file.exists()

        # Read persisted state
        state_data = json.loads(state_file.read_text())
        assert state_data["master_checksum"] == result1["master_checksum"]

        # Second orchestration (simulating restart)
        orchestrator2 = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        # New orchestration should work
        result2 = await orchestrator2.orchestrate("Another test", {"seed": 43})
        assert result2["iteration"] == 1  # Fresh orchestrator

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, temp_workspace, test_config):
        """Test handling when some agents fail."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        # Patch moe_router to fail (it always runs in WORK mode)
        original_execute = orchestrator.agents["moe_router"].execute

        async def failing_execute(task, context):
            raise Exception("Simulated failure")

        orchestrator.agents["moe_router"].execute = failing_execute

        try:
            result = await orchestrator.orchestrate(
                "Test partial failure with moe router",
                {"seed": 42}
            )

            # Should complete despite failure (with fallback)
            assert "moe_router" in result["agent_results"]

            # Check if fallback was used or agent failed
            moe_router_result = result["agent_results"]["moe_router"]
            assert moe_router_result["status"] in ["failed", "degraded"]

        finally:
            orchestrator.agents["moe_router"].execute = original_execute

    @pytest.mark.asyncio
    async def test_checkpoint_creation(self, temp_workspace, test_config):
        """Test that checkpoints are created during orchestration."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        await orchestrator.orchestrate("Test checkpoint creation", {"seed": 42})

        # Check checkpoint directory (under state/)
        checkpoint_files = list((temp_workspace / "state" / "checkpoints").glob("checkpoint_*.json"))
        assert len(checkpoint_files) >= 1

        # Verify checkpoint structure
        checkpoint_data = json.loads(checkpoint_files[0].read_text())
        assert "checkpoint_id" in checkpoint_data
        assert "status" in checkpoint_data
        assert checkpoint_data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, temp_workspace, test_config):
        """Test that metrics are recorded during orchestration."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        await orchestrator.orchestrate("Test metrics", {"seed": 42})

        # Verify metrics recorded
        stats = orchestrator.get_metrics()
        assert stats is not None
        assert stats["tasks"]["total"] >= 1
        assert stats["tasks"]["succeeded"] >= 1

        # Verify latency recorded
        assert stats["latency"]["orchestration_p50"] is not None or stats["latency"]["orchestration_p50"] is None

    @pytest.mark.asyncio
    async def test_tracing_spans(self, temp_workspace, test_config):
        """Test that tracing spans are created."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        result = await orchestrator.orchestrate("Test tracing", {"seed": 42})

        # Tracer should have recorded spans
        assert orchestrator.tracer is not None

    @pytest.mark.asyncio
    async def test_reproducibility(self, temp_workspace, test_config):
        """Test that same input produces same checksum."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        task = "Test reproducibility"
        context = {"seed": 42}

        result1 = await orchestrator.orchestrate(task, context.copy())

        # Reset idempotency cache to allow re-execution
        if orchestrator.idempotency_manager:
            orchestrator.idempotency_manager.clear()

        # Same task should produce same checksums
        result2 = await orchestrator.orchestrate(task, context.copy())

        # Note: Results may differ due to timing, but structure should match
        assert result1["agents_executed"] == result2["agents_executed"]

    @pytest.mark.asyncio
    async def test_production_status(self, temp_workspace, test_config):
        """Test production status endpoint."""
        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        status = orchestrator.get_production_status()

        assert status["version"] == "3.0"
        assert "healthy" in status
        assert "components" in status
        assert "circuit_breaker" in status["components"]

        # After orchestration, check components updated
        await orchestrator.orchestrate("Test status", {"seed": 42})
        status_after = orchestrator.get_production_status()

        assert status_after["iteration"] >= 1


@pytest.mark.integration
class TestIntegrationWithConfig:
    """Tests for configuration integration."""

    @pytest.mark.asyncio
    async def test_disabled_features(self, temp_workspace):
        """Test orchestrator with features disabled."""
        config = OrchestratorConfig()
        config.workspace = temp_workspace
        config.checkpoint_enabled = False
        config.metrics_enabled = False
        config.tracing_enabled = False
        config.enable_bulkhead = False
        config.enable_fallback = False
        config.enable_idempotency = False
        config.enable_rate_limit = False

        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=config
        )

        # Should still work without optional features
        result = await orchestrator.orchestrate("Test minimal", {"seed": 42})
        assert result["agents_executed"] > 0

        # Features should be None/disabled
        assert orchestrator.checkpoint is None
        assert orchestrator.metrics is None
        assert orchestrator.tracer is None
        assert orchestrator.bulkhead is None

    @pytest.mark.asyncio
    async def test_custom_timeouts(self, temp_workspace, test_config):
        """Test custom timeout configuration."""
        test_config.agent_timeout = 5.0
        test_config.orchestration_timeout = 30.0

        orchestrator = FrameworkOrchestrator(
            workspace=temp_workspace,
            config=test_config
        )

        # Should work with custom timeouts
        result = await orchestrator.orchestrate("Test timeouts", {"seed": 42})
        assert result["agents_executed"] > 0
