"""
Tests for Decision Engine (v4.3.0)

Verification tests for the work/delegate/protect refactoring per the plan:
1. Determinism Test - same input → same checksum
2. Batch Invariance Test - Task B routing identical whether preceded by Task A or not
3. Safety Gating Test - burnout=RED forces recovery
4. PROTECT Mode Test - peak flow queues results

ThinkingMachines [He2025] Compliance Testing
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from otto.decision_engine import (
    DecisionEngine, TaskRequest, TaskCategory, ExecutionPlan,
    ROUTING_TABLE, SignalCategory, ComplexityTier, BudgetTier, FlowState,
    StateSnapshot
)
from otto.agent_coordinator import (
    AgentCoordinator, DecisionMode, CognitiveContext, TaskProfile,
    QueuedResult, FlowProtector
)


class TestRoutingTable:
    """Tests for the pre-computed routing table."""

    def test_routing_table_has_default_entry(self):
        """Ensure routing table has a catch-all default entry."""
        # The last entry should be the wildcard default
        last_pattern, last_result = ROUTING_TABLE[-1]
        assert last_pattern == ("*", "*", "*", "*"), "Last entry should be wildcard default"

    def test_routing_table_emotional_first(self):
        """Emotional signals should be handled first (safety first)."""
        # Find emotional pattern
        emotional_patterns = [
            (p, r) for p, r in ROUTING_TABLE
            if p[0] == "emotional"
        ]
        assert len(emotional_patterns) > 0, "Should have emotional signal pattern"

        # Emotional should route to PROTECT
        pattern, result = emotional_patterns[0]
        mode, agents, rationale = result
        assert mode == DecisionMode.PROTECT, "Emotional signals should PROTECT"

    def test_routing_table_peak_flow_protected(self):
        """Peak flow state should be protected."""
        peak_patterns = [
            (p, r) for p, r in ROUTING_TABLE
            if p[3] == "peak"
        ]
        assert len(peak_patterns) > 0, "Should have peak flow pattern"

        pattern, result = peak_patterns[0]
        mode, agents, rationale = result
        assert mode == DecisionMode.PROTECT, "Peak flow should PROTECT"


class TestStateSnapshot:
    """Tests for state snapshot determinism."""

    def test_snapshot_checksum_deterministic(self):
        """Same state should produce same checksum."""
        snapshot1 = StateSnapshot(
            signal_category="task",
            complexity_tier="moderate",
            budget_tier="medium",
            flow_state="rolling",
            burnout_level="GREEN",
            energy_level="medium",
            can_spawn_agents=True
        )

        snapshot2 = StateSnapshot(
            signal_category="task",
            complexity_tier="moderate",
            budget_tier="medium",
            flow_state="rolling",
            burnout_level="GREEN",
            energy_level="medium",
            can_spawn_agents=True
        )

        assert snapshot1.checksum == snapshot2.checksum, "Same state should produce same checksum"

    def test_snapshot_checksum_varies_with_state(self):
        """Different states should produce different checksums."""
        snapshot1 = StateSnapshot(
            signal_category="task",
            complexity_tier="moderate",
            budget_tier="medium",
            flow_state="rolling",
            burnout_level="GREEN",
            energy_level="medium",
            can_spawn_agents=True
        )

        snapshot2 = StateSnapshot(
            signal_category="emotional",  # Different
            complexity_tier="moderate",
            budget_tier="medium",
            flow_state="rolling",
            burnout_level="GREEN",
            energy_level="medium",
            can_spawn_agents=True
        )

        assert snapshot1.checksum != snapshot2.checksum, "Different states should produce different checksums"

    def test_snapshot_to_routing_key(self):
        """Snapshot should convert to routing key tuple."""
        snapshot = StateSnapshot(
            signal_category="task",
            complexity_tier="moderate",
            budget_tier="medium",
            flow_state="rolling",
            burnout_level="GREEN",
            energy_level="medium",
            can_spawn_agents=True
        )

        key = snapshot.to_routing_key()
        assert key == ("task", "moderate", "medium", "rolling")


class TestDecisionEngineDeterminism:
    """Tests for ThinkingMachines [He2025] determinism requirements."""

    @pytest.fixture
    def engine(self):
        """Create a decision engine with mock cognitive stage."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "medium",
            "burnout_level": "GREEN",
            "momentum_phase": "rolling",
            "working_memory_used": 1,
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        return DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

    def test_routing_determinism(self, engine):
        """Same input should produce identical routing 100 times."""
        task = TaskRequest(
            description="Implement user authentication",
            category=TaskCategory.IMPLEMENTATION,
            files_involved=["auth.py", "users.py"],
            estimated_scope="medium"
        )

        results = [engine.process_task(task, {}) for _ in range(100)]
        checksums = set(r.checksum for r in results)

        assert len(checksums) == 1, f"Expected 1 unique checksum, got {len(checksums)}: {checksums}"

    def test_batch_invariance(self, engine):
        """Task B routing should be identical whether preceded by Task A or not."""
        task_a = TaskRequest(
            description="Search for patterns",
            category=TaskCategory.EXPLORATION,
            estimated_scope="small"
        )

        task_b = TaskRequest(
            description="Implement feature",
            category=TaskCategory.IMPLEMENTATION,
            estimated_scope="medium"
        )

        # Process Task A then Task B
        _ = engine.process_task(task_a, {})
        result_after_a = engine.process_task(task_b, {})

        # Create fresh engine for isolated test
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "medium",
            "burnout_level": "GREEN",
            "momentum_phase": "rolling",
            "working_memory_used": 1,
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))
        engine_fresh = DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

        # Process Task B alone
        result_alone = engine_fresh.process_task(task_b, {})

        assert result_after_a.decision.mode == result_alone.decision.mode, \
            "Task B routing should be identical regardless of Task A"


class TestSafetyGating:
    """Tests for cognitive safety constraints."""

    def test_burnout_red_forces_protect(self):
        """RED burnout should force PROTECT mode."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "low",
            "burnout_level": "RED",  # Critical burnout
            "momentum_phase": "crashed",
            "working_memory_used": 3,
            "mode": "recovery",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        engine = DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

        task = TaskRequest(
            description="Complex implementation task",
            category=TaskCategory.IMPLEMENTATION,
            estimated_scope="large"
        )

        result = engine.process_task(task, {})

        assert result.decision.mode == DecisionMode.PROTECT, \
            "RED burnout should force PROTECT mode"
        assert "recovery" in result.decision.rationale.lower() or "red" in result.decision.rationale.lower(), \
            "Rationale should mention recovery or RED"

    def test_cannot_spawn_forces_work(self):
        """When can't spawn agents, should force WORK mode."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "low",
            "burnout_level": "ORANGE",
            "momentum_phase": "building",
            "working_memory_used": 3,  # At limit
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        engine = DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

        # This would normally delegate (complex + parallelizable)
        task = TaskRequest(
            description="Complex implementation task",
            category=TaskCategory.IMPLEMENTATION,
            files_involved=["a.py", "b.py", "c.py", "d.py", "e.py"],
            estimated_scope="large"
        )

        result = engine.process_task(task, {})

        # Should be WORK because can't spawn (ORANGE burnout + full memory)
        assert result.decision.mode in (DecisionMode.WORK, DecisionMode.PROTECT), \
            "Should be WORK or PROTECT when can't spawn agents"


class TestProtectMode:
    """Tests for PROTECT mode (flow protection)."""

    def test_peak_flow_queues_results(self):
        """Peak flow state should trigger PROTECT mode."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "high",
            "burnout_level": "GREEN",
            "momentum_phase": "peak",  # Peak flow
            "working_memory_used": 1,
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        engine = DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

        task = TaskRequest(
            description="New task during flow",
            category=TaskCategory.SIMPLE,
            estimated_scope="small"
        )

        result = engine.process_task(task, {})

        assert result.decision.mode == DecisionMode.PROTECT, \
            "Peak flow should trigger PROTECT mode"
        assert result.flow_protection_enabled, \
            "Flow protection should be enabled"

    def test_protect_mode_sets_resume_condition(self):
        """PROTECT mode should specify when to resume."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "high",
            "burnout_level": "GREEN",
            "momentum_phase": "peak",
            "working_memory_used": 1,
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        engine = DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

        task = TaskRequest(
            description="Task to protect",
            category=TaskCategory.SIMPLE
        )

        result = engine.process_task(task, {})

        assert result.decision.protect_until is not None, \
            "PROTECT mode should specify resume condition"


class TestTableLookup:
    """Tests for table lookup mechanics."""

    def test_pattern_matching_with_wildcards(self):
        """Wildcards should match any value."""
        engine = DecisionEngine(use_table_routing=True)

        # Test wildcard matching
        assert engine._pattern_matches(("*", "*", "*", "*"), ("task", "simple", "high", "rolling"))
        assert engine._pattern_matches(("emotional", "*", "*", "*"), ("emotional", "complex", "low", "peak"))
        assert not engine._pattern_matches(("emotional", "*", "*", "*"), ("task", "simple", "high", "rolling"))

    def test_table_lookup_returns_tuple(self):
        """Table lookup should return (mode, agents, rationale)."""
        engine = DecisionEngine(use_table_routing=True)

        snapshot = StateSnapshot(
            signal_category="task",
            complexity_tier="simple",
            budget_tier="high",
            flow_state="rolling",
            burnout_level="GREEN",
            energy_level="high",
            can_spawn_agents=True
        )

        mode, agents, rationale = engine._table_lookup(snapshot)

        assert isinstance(mode, DecisionMode)
        assert isinstance(agents, list)
        assert isinstance(rationale, str)


class TestExecutionPlan:
    """Tests for ExecutionPlan structure."""

    def test_execution_plan_checksum(self):
        """ExecutionPlan should have deterministic checksum."""
        from otto.agent_coordinator import Decision

        decision = Decision(
            mode=DecisionMode.WORK,
            rationale="Test rationale"
        )

        task = TaskRequest(
            description="Test task",
            category=TaskCategory.SIMPLE
        )

        plan1 = ExecutionPlan(
            decision=decision,
            task=task,
            steps=["Step 1", "Step 2"]
        )

        plan2 = ExecutionPlan(
            decision=decision,
            task=task,
            steps=["Step 1", "Step 2"]
        )

        assert plan1.checksum == plan2.checksum

    def test_get_routed_agents(self):
        """ExecutionPlan should return routed agents."""
        from otto.agent_coordinator import Decision

        decision = Decision(
            mode=DecisionMode.DELEGATE,
            rationale="Test"
        )
        decision._routing_agents = ["echo_curator", "moe_router"]

        task = TaskRequest(
            description="Test",
            category=TaskCategory.IMPLEMENTATION
        )

        plan = ExecutionPlan(
            decision=decision,
            task=task,
            steps=[]
        )

        agents = plan.get_routed_agents()
        assert agents == ["echo_curator", "moe_router"]


class TestAgentCoordinatorQueue:
    """Tests for result queue persistence."""

    def test_queue_result_persistence(self, tmp_path):
        """Queued results should be persisted."""
        coordinator = AgentCoordinator(state_dir=tmp_path)

        result = QueuedResult(
            agent_id="test-agent-1",
            result_type="explore",
            summary="Found 5 files",
            full_result={"files": ["a.py", "b.py"]},
            timestamp=datetime.now(),
            priority=2
        )

        coordinator.queue_result(result)

        # Create new coordinator to test persistence
        coordinator2 = AgentCoordinator(state_dir=tmp_path)

        assert len(coordinator2.result_queue) == 1
        assert coordinator2.result_queue[0].agent_id == "test-agent-1"

    def test_get_pending_results_respects_flow(self, tmp_path):
        """Pending results should not be delivered during peak flow."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "high",
            "burnout_level": "GREEN",
            "momentum_phase": "peak",
            "working_memory_used": 1,
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        coordinator = AgentCoordinator(cognitive_stage=mock_stage, state_dir=tmp_path)
        coordinator.flow_protection_active = True

        result = QueuedResult(
            agent_id="test-agent",
            result_type="explore",
            summary="Test",
            full_result={},
            timestamp=datetime.now(),
            priority=2
        )
        coordinator.queue_result(result)

        # Should not deliver during peak flow
        pending = coordinator.get_pending_results_for_delivery()
        assert len(pending) == 0, "Should not deliver during peak flow"


class TestIntegration:
    """Integration tests for the full flow."""

    def test_full_work_flow(self):
        """Test complete WORK mode flow."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "high",
            "burnout_level": "GREEN",
            "momentum_phase": "rolling",
            "working_memory_used": 1,
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        engine = DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

        task = TaskRequest(
            description="Simple task",
            category=TaskCategory.SIMPLE,
            estimated_scope="small"
        )

        plan = engine.process_task(task, {})

        assert plan.decision.mode == DecisionMode.WORK
        assert len(plan.steps) > 0
        assert plan.checksum != ""

    def test_full_delegate_flow(self):
        """Test complete DELEGATE mode flow."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "high",
            "burnout_level": "GREEN",
            "momentum_phase": "rolling",
            "working_memory_used": 0,
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        engine = DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

        task = TaskRequest(
            description="Complex multi-file implementation",
            category=TaskCategory.IMPLEMENTATION,
            files_involved=["a.py", "b.py", "c.py", "d.py", "e.py",
                           "f.py", "g.py", "h.py", "i.py", "j.py", "k.py"],
            estimated_scope="large"
        )

        plan = engine.process_task(task, {})

        assert plan.decision.mode == DecisionMode.DELEGATE
        assert len(plan.get_routed_agents()) > 0

    def test_full_protect_flow(self):
        """Test complete PROTECT mode flow."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "high",
            "burnout_level": "GREEN",
            "momentum_phase": "peak",  # Peak flow
            "working_memory_used": 1,
            "mode": "focused",
            "max_parallel_agents": 3,
            "max_agent_depth": 3,
            "working_memory_limit": 3
        }.get(key, default))

        engine = DecisionEngine(cognitive_stage=mock_stage, use_table_routing=True)

        task = TaskRequest(
            description="Any task during peak",
            category=TaskCategory.SIMPLE
        )

        plan = engine.process_task(task, {})

        assert plan.decision.mode == DecisionMode.PROTECT
        assert plan.flow_protection_enabled
        assert plan.decision.protect_until is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
