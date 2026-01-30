"""Tests for Framework Orchestrator."""

import asyncio
import json
import pytest
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from otto import (
    BaseAgent,
    ECHOCuratorAgent,
    DomainIntelligenceAgent,
    MoERouterAgent,
    DeterminismGuardAgent,
    FrameworkOrchestrator,
    Mycelium,
)


class TestBaseAgent:
    """Tests for BaseAgent interface."""

    def test_agent_has_required_attributes(self):
        """All agents should have name, framework, ces_alignment."""

        class TestAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    name="test",
                    framework="Test Framework",
                    ces_alignment="Test alignment",
                )

            async def execute(self, task, context):
                return {"test": True}

        agent = TestAgent()
        assert agent.name == "test"
        assert agent.framework == "Test Framework"
        assert agent.ces_alignment == "Test alignment"


class TestECHOCurator:
    """Tests for ECHO Curator agent."""

    @pytest.fixture
    def agent(self):
        return ECHOCuratorAgent()

    def test_memory_layers_initialized(self, agent):
        """Memory layers should be initialized."""
        assert "local" in agent.memory_layers
        assert "inherits" in agent.memory_layers
        assert "variantsets" in agent.memory_layers
        assert "references" in agent.memory_layers
        assert "payloads" in agent.memory_layers
        assert "specializes" in agent.memory_layers

    def test_compression_order(self, agent):
        """Compression order should be defined."""
        assert agent.COMPRESSION_ORDER["local"] == 1
        assert agent.COMPRESSION_ORDER["inherits"] == 2
        assert agent.COMPRESSION_ORDER["specializes"] is None  # Never compress

    @pytest.mark.asyncio
    async def test_execute_returns_livrps_structure(self, agent):
        """Execute should return LIVRPS memory structure."""
        result = await agent.execute("test query", {})
        assert result["memory_architecture"] == "LIVRPS"
        assert "active_mode" in result
        assert "compression_state" in result
        assert "principles_layer" in result

    def test_detect_memory_mode_focused(self, agent):
        """Should detect focused mode for normal tasks."""
        # Note: "error" triggers recovery_recall, so use a task without recovery signals
        mode = agent._detect_memory_mode("implement this feature", {})
        assert mode == "focused_recall"

    def test_detect_memory_mode_exploratory(self, agent):
        """Should detect exploratory mode for brainstorming."""
        mode = agent._detect_memory_mode("what if we tried", {})
        assert mode == "exploratory_recall"


class TestDomainIntelligence:
    """Tests for Domain Intelligence agent."""

    @pytest.fixture
    def agent(self, tmp_path):
        # Create a test domain
        domains_dir = tmp_path / "domains"
        domains_dir.mkdir()

        test_domain = {
            "name": "Test Domain",
            "specialists": {
                "test_specialist": {
                    "keywords": ["test", "example"],
                    "analysis_focus": ["metric1"],
                }
            },
            "routing_keywords": ["test", "example"],
            "prism_perspectives": ["causal"],
        }

        (domains_dir / "test.json").write_text(json.dumps(test_domain))
        return DomainIntelligenceAgent(domains_path=domains_dir)

    def test_domains_loaded(self, agent):
        """Domains should be loaded from path."""
        assert len(agent.domains) > 0
        assert "test domain" in agent.domains

    def test_get_routing_keywords(self, agent):
        """Should return routing keywords from all domains."""
        keywords = agent.get_routing_keywords()
        assert "test" in keywords
        assert "example" in keywords

    @pytest.mark.asyncio
    async def test_execute_detects_domain(self, agent):
        """Execute should detect matching domain."""
        result = await agent.execute("test this feature", {})
        assert "detected_domains" in result
        assert "test domain" in result["detected_domains"]


class TestMoERouter:
    """Tests for MoE Router agent (V5 Intervention Experts)."""

    @pytest.fixture
    def agent(self):
        return MoERouterAgent()

    def test_v5_experts_defined(self, agent):
        """V5 experts should be defined with correct archetypes."""
        assert len(agent.EXPERTS) == 7
        assert "protector" in agent.EXPERTS
        assert "decomposer" in agent.EXPERTS
        assert "restorer" in agent.EXPERTS
        assert "redirector" in agent.EXPERTS
        assert "acknowledger" in agent.EXPERTS
        assert "guide" in agent.EXPERTS
        assert "executor" in agent.EXPERTS

    def test_safety_floors_defined(self, agent):
        """Safety floors should be defined for all experts."""
        assert len(agent.SAFETY_FLOORS) == 7
        assert agent.SAFETY_FLOORS["protector"] == 0.10
        assert agent.SAFETY_FLOORS["decomposer"] == 0.05
        assert agent.SAFETY_FLOORS["restorer"] == 0.05

    @pytest.mark.asyncio
    async def test_5phase_routing_deterministic(self, agent):
        """Same task should always route to same expert via 5-phase routing."""
        task = "implement the feature"
        result1 = await agent.execute(task, {})
        result2 = await agent.execute(task, {})
        assert result1["selected_expert"] == result2["selected_expert"]
        assert result1["expert_hash"] == result2["expert_hash"]

    @pytest.mark.asyncio
    async def test_execute_returns_v5_structure(self, agent):
        """Execute should return V5 routing structure."""
        result = await agent.execute("test task", {})
        assert result["routing_version"] == "v5"
        assert result["routing_type"] == "v5_5phase"
        assert "routing_phases" in result
        assert result["routing_phases"] == ["activate", "weight", "bound", "select", "update"]

    @pytest.mark.asyncio
    async def test_execute_returns_gating_weights(self, agent):
        """Execute should return gating weights (bounded scores)."""
        result = await agent.execute("test task", {})
        assert "gating_weights" in result
        assert "bounded_scores" in result

    @pytest.mark.asyncio
    async def test_safety_floor_enforcement(self, agent):
        """Protector should never drop below 10% after bounding."""
        # Use a task with no safety-related triggers
        result = await agent.execute("implement code build create", {})
        bounded = result["bounded_scores"]

        # Verify safety floors are enforced
        assert bounded["protector"] >= 0.10, "Protector floor violated"
        assert bounded["decomposer"] >= 0.05, "Decomposer floor violated"
        assert bounded["restorer"] >= 0.05, "Restorer floor violated"

    @pytest.mark.asyncio
    async def test_protector_activates_on_safety_triggers(self, agent):
        """Protector should activate strongly on safety-related triggers."""
        result = await agent.execute("I'm frustrated and overwhelmed, help!", {})
        activation = result["activation_vector"]
        assert activation["protector"] > 0, "Protector should activate on safety triggers"

    @pytest.mark.asyncio
    async def test_executor_activates_on_implementation_triggers(self, agent):
        """Executor should activate on implementation triggers."""
        result = await agent.execute("implement and build this code", {})
        activation = result["activation_vector"]
        assert activation["executor"] > 0, "Executor should activate on implementation triggers"

    @pytest.mark.asyncio
    async def test_homeostatic_normalization(self, agent):
        """Bounded scores should sum to 1.0 (homeostatic regulation)."""
        result = await agent.execute("test task", {})
        bounded = result["bounded_scores"]
        total = sum(bounded.values())
        assert abs(total - 1.0) < 0.001, f"Bounded scores should sum to 1.0, got {total}"

    @pytest.mark.asyncio
    async def test_priority_tiebreaker(self, agent):
        """Lower priority number should win ties."""
        # When no triggers match, all activations are 0, so safety floors determine winner
        # After normalization, protector (floor 0.10) should win over lower-floor experts
        result = await agent.execute("neutral task with no triggers", {})
        # Protector has highest floor, so should win when no triggers match
        assert result["selected_expert"] == "protector"


class TestMycelium:
    """Tests for Mycelium neuroplasticity mechanism."""

    @pytest.fixture
    def mycelium(self):
        return Mycelium()

    def test_initial_weights_equal(self, mycelium):
        """Initial weights should be equal across all experts."""
        weights = mycelium.get_weights()
        assert len(weights) == 7
        expected = 1/7
        for expert, weight in weights.items():
            assert abs(weight - expected) < 0.001

    def test_record_outcome(self, mycelium):
        """Should record outcomes for Hebbian learning."""
        mycelium.record_outcome("protector", 1.0, "abc123")
        state = mycelium.get_state()
        assert state["outcomes_recorded"] == 1
        assert state["recent_outcomes"][0]["expert"] == "protector"
        assert state["recent_outcomes"][0]["outcome"] == 1.0

    def test_get_state(self, mycelium):
        """Should return current state for inspection."""
        state = mycelium.get_state()
        assert "weights" in state
        assert "learning_rate" in state
        assert "outcomes_recorded" in state
        assert state["learning_rate"] == 0.1


class TestDeterminismGuard:
    """Tests for Determinism Guard agent."""

    @pytest.fixture
    def agent(self):
        return DeterminismGuardAgent()

    @pytest.mark.asyncio
    async def test_batch_size_check(self, agent):
        """Should check batch size in determinism config."""
        result = await agent.execute("check determinism", {})
        assert "determinism_config" in result
        assert result["determinism_config"]["batch_size"] == 1

    @pytest.mark.asyncio
    async def test_cudnn_settings_check(self, agent):
        """Should check cuDNN settings."""
        result = await agent.execute("verify reproducibility", {})
        assert "determinism_config" in result
        assert result["determinism_config"]["cudnn_deterministic"] is True
        assert result["determinism_config"]["cudnn_benchmark"] is False

    @pytest.mark.asyncio
    async def test_batch_invariance_enforced(self, agent):
        """Should report batch invariance enforcement."""
        result = await agent.execute("test", {})
        assert result["batch_invariance_enforced"] is True
        assert result["reproducibility_guaranteed"] is True


class TestFrameworkOrchestrator:
    """Tests for the main orchestrator."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        return FrameworkOrchestrator(workspace=workspace)

    def test_agents_registered(self, orchestrator):
        """All 7 agents should be registered."""
        assert len(orchestrator.agents) == 7
        assert "echo_curator" in orchestrator.agents
        assert "domain_intelligence" in orchestrator.agents
        assert "moe_router" in orchestrator.agents
        assert "world_modeler" in orchestrator.agents
        assert "code_generator" in orchestrator.agents
        assert "determinism_guard" in orchestrator.agents
        assert "self_reflector" in orchestrator.agents

    def test_route_task_always_includes_core(self, orchestrator):
        """echo_curator and determinism_guard should always be active."""
        active = orchestrator._route_task("any task", {})
        assert "echo_curator" in active
        assert "determinism_guard" in active

    @pytest.mark.asyncio
    async def test_orchestrate_returns_results(self, orchestrator):
        """Orchestrate should return results from active agents."""
        result = await orchestrator.orchestrate("test task", {})
        assert "task" in result
        assert "agents_executed" in result
        assert "agent_results" in result
        assert "echo_curator" in result["agent_results"]

    @pytest.mark.asyncio
    async def test_orchestrate_execution_time(self, orchestrator):
        """Orchestrate should include execution time."""
        result = await orchestrator.orchestrate("test", {})
        assert "total_execution_time_ms" in result


class TestChecksums:
    """Tests for checksum generation."""

    @pytest.mark.asyncio
    async def test_agent_output_has_checksum(self):
        """Agent outputs should include checksums."""
        agent = ECHOCuratorAgent()
        result = await agent.execute("test", {})
        # Checksum is added by orchestrator, but we can verify structure
        assert "provenance" in result
        assert "content_hash" in result["provenance"]

    @pytest.mark.asyncio
    async def test_checksums_reproducible(self):
        """Same input should produce same checksum."""
        agent = MoERouterAgent()
        result1 = await agent.execute("exact same task", {})
        result2 = await agent.execute("exact same task", {})
        assert result1["expert_hash"] == result2["expert_hash"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
