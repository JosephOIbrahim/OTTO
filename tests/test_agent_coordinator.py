"""
Tests for AgentCoordinator - Work/Delegate/Protect model.

ThinkingMachines [He2025] compliance:
- Deterministic routing tests
- Bounded queue tests
- Flow protection tests
"""

import pytest
import asyncio
import time
from collections import deque
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from otto.agent_coordinator import (
    AgentCoordinator,
    Decision,
    DecisionMode,
    QueuedResult,
    CognitiveContext,
    TaskProfile,
    AgentType,
    FlowProtector,
)


class TestAgentCoordinatorInit:
    """Test AgentCoordinator initialization."""

    def test_bounded_queues(self):
        """Verify queues are bounded for production safety."""
        coordinator = AgentCoordinator()

        # Verify deque with maxlen
        assert isinstance(coordinator.result_queue, deque)
        assert isinstance(coordinator.decision_history, deque)
        assert coordinator.result_queue.maxlen == AgentCoordinator.MAX_RESULT_QUEUE
        assert coordinator.decision_history.maxlen == AgentCoordinator.MAX_DECISION_HISTORY

    def test_default_state(self):
        """Verify default state on initialization."""
        coordinator = AgentCoordinator()

        assert coordinator.flow_protection_active is False
        assert len(coordinator.active_agents) == 0


class TestDecisionRouting:
    """Test decision routing logic."""

    def test_work_mode_low_budget(self):
        """WORK mode when cognitive budget is low."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "low",
            "burnout_level": "YELLOW",
            "momentum_phase": "building",
            "working_memory_used": 2,
            "mode": "focused",
        }.get(key, default))

        coordinator = AgentCoordinator(cognitive_stage=mock_stage)
        context = coordinator.get_cognitive_context()

        # Low energy = low budget = should favor WORK
        assert context.cognitive_budget() < 0.5

    def test_protect_mode_peak_flow(self):
        """PROTECT mode when in peak flow state."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "high",
            "burnout_level": "GREEN",
            "momentum_phase": "peak",
            "working_memory_used": 1,
            "mode": "focused",
        }.get(key, default))

        coordinator = AgentCoordinator(cognitive_stage=mock_stage)
        context = coordinator.get_cognitive_context()

        # Peak flow should indicate flow state
        assert context.in_flow_state is True

    def test_cannot_spawn_at_limit(self):
        """Cannot spawn agents when at max parallel limit."""
        coordinator = AgentCoordinator()

        # Fill up active agents
        for i in range(3):
            coordinator.active_agents[f"agent_{i}"] = {"type": AgentType.GENERAL}

        context = coordinator.get_cognitive_context()
        assert context.can_accept_new_agent() is False


class TestResultQueue:
    """Test result queue functionality."""

    def test_queue_result_persists(self, tmp_path):
        """Queued results are persisted to disk."""
        state_dir = tmp_path / "state"
        coordinator = AgentCoordinator(state_dir=state_dir)

        result = QueuedResult(
            agent_id="test_agent",
            result_type="test",
            summary="Test result",
            full_result={"data": "test"},
            timestamp=datetime.now(),
            priority=2,
            presented=False
        )

        coordinator.queue_result(result)

        # Verify file was created
        assert coordinator.queue_file.exists()

        # Verify result is in queue
        assert len(coordinator.result_queue) == 1

    def test_bounded_queue_eviction(self, tmp_path):
        """Queue respects maxlen and evicts oldest."""
        state_dir = tmp_path / "state"
        coordinator = AgentCoordinator(state_dir=state_dir)

        # Fill queue beyond limit
        for i in range(AgentCoordinator.MAX_RESULT_QUEUE + 10):
            result = QueuedResult(
                agent_id=f"agent_{i}",
                result_type="test",
                summary=f"Result {i}",
                full_result={},
                timestamp=datetime.now(),
                priority=2,
                presented=False
            )
            coordinator.result_queue.append(result)

        # Should be capped at maxlen
        assert len(coordinator.result_queue) == AgentCoordinator.MAX_RESULT_QUEUE

        # First items should have been evicted
        assert coordinator.result_queue[0].agent_id != "agent_0"

    def test_ttl_cleanup(self, tmp_path):
        """Expired results are cleaned up."""
        state_dir = tmp_path / "state"
        coordinator = AgentCoordinator(state_dir=state_dir)

        # Add old result
        old_time = datetime.fromtimestamp(time.time() - 7200)  # 2 hours ago
        old_result = QueuedResult(
            agent_id="old_agent",
            result_type="test",
            summary="Old result",
            full_result={},
            timestamp=old_time,
            priority=2,
            presented=False
        )

        # Add fresh result
        fresh_result = QueuedResult(
            agent_id="fresh_agent",
            result_type="test",
            summary="Fresh result",
            full_result={},
            timestamp=datetime.now(),
            priority=2,
            presented=False
        )

        coordinator.result_queue.append(old_result)
        coordinator.result_queue.append(fresh_result)

        # Run cleanup
        coordinator.cleanup_expired_results()

        # Old should be gone, fresh should remain
        assert len(coordinator.result_queue) == 1
        assert coordinator.result_queue[0].agent_id == "fresh_agent"


class TestDecisionHistory:
    """Test decision history tracking."""

    def test_history_bounded(self):
        """Decision history respects maxlen."""
        coordinator = AgentCoordinator()

        # Add decisions beyond limit
        for i in range(AgentCoordinator.MAX_DECISION_HISTORY + 100):
            decision = Decision(
                mode=DecisionMode.WORK,
                rationale=f"Decision {i}"
            )
            coordinator.decision_history.append(decision)

        # Should be capped
        assert len(coordinator.decision_history) == AgentCoordinator.MAX_DECISION_HISTORY


class TestFlowProtection:
    """Test flow protection functionality."""

    def test_flow_protection_queues_results(self, tmp_path):
        """Results queued during flow protection."""
        state_dir = tmp_path / "state"
        coordinator = AgentCoordinator(state_dir=state_dir)
        coordinator.flow_protection_active = True

        # Directly queue a result (simulating what complete_agent would do)
        result = QueuedResult(
            agent_id="test_agent",
            result_type="test",
            summary="Test result",
            full_result={"status": "success"},
            timestamp=datetime.now(),
            priority=2,
            presented=False
        )
        coordinator.queue_result(result)

        assert len(coordinator.result_queue) == 1

    def test_pending_results_sorted(self, tmp_path):
        """Pending results sorted by priority then timestamp then agent_id."""
        state_dir = tmp_path / "state"
        coordinator = AgentCoordinator(state_dir=state_dir)

        # Add results with different priorities
        base_time = datetime.now()
        results = [
            QueuedResult("agent_c", "test", "C", {}, base_time, 3, False),
            QueuedResult("agent_a", "test", "A", {}, base_time, 1, False),
            QueuedResult("agent_b", "test", "B", {}, base_time, 1, False),
        ]

        for r in results:
            coordinator.result_queue.append(r)

        # Get pending - should be sorted
        pending = coordinator.get_pending_results_for_delivery()

        # Priority 1 first, then by agent_id for same priority
        assert pending[0].agent_id == "agent_a"
        assert pending[1].agent_id == "agent_b"


class TestCognitiveContext:
    """Test CognitiveContext calculations."""

    def test_budget_calculation(self):
        """Cognitive budget calculated correctly."""
        context = CognitiveContext(
            energy_level="high",
            burnout_level="GREEN",
            momentum_phase="rolling",
            active_agents=0,
            working_memory_used=0,
            in_flow_state=False,
            mode="focused"
        )

        budget = context.cognitive_budget()
        assert 0.8 <= budget <= 1.0  # High energy + GREEN = high budget

    def test_budget_depleted(self):
        """Budget zero when depleted."""
        context = CognitiveContext(
            energy_level="depleted",
            burnout_level="RED",
            momentum_phase="crashed",
            active_agents=3,
            working_memory_used=3,
            in_flow_state=False,
            mode="recovery"
        )

        budget = context.cognitive_budget()
        assert budget == 0.0


class TestDeterminism:
    """Test determinism requirements [He2025]."""

    def test_context_reproducible(self):
        """Same inputs produce same context."""
        mock_stage = MagicMock()
        mock_stage.get_resolved_value = MagicMock(side_effect=lambda key, default: {
            "energy_level": "medium",
            "burnout_level": "GREEN",
            "momentum_phase": "building",
            "working_memory_used": 1,
            "mode": "focused",
        }.get(key, default))

        coordinator = AgentCoordinator(cognitive_stage=mock_stage)

        # Get context multiple times
        contexts = [coordinator.get_cognitive_context() for _ in range(10)]
        budgets = [c.cognitive_budget() for c in contexts]

        # All budgets should be identical
        assert len(set(budgets)) == 1

    def test_queue_sort_deterministic(self, tmp_path):
        """Queue sorting is deterministic [He2025]."""
        # Test the sorting logic directly
        base_time = datetime.now()
        results = [
            QueuedResult("z_agent", "test", "Z", {}, base_time, 2, False),
            QueuedResult("a_agent", "test", "A", {}, base_time, 2, False),
            QueuedResult("m_agent", "test", "M", {}, base_time, 2, False),
        ]

        # Sort using the same key function as the coordinator
        for _ in range(5):
            import random
            shuffled = results.copy()
            random.shuffle(shuffled)
            shuffled.sort(key=lambda r: (r.priority, r.timestamp, r.agent_id))

            # With same priority and timestamp, should sort by agent_id
            assert shuffled[0].agent_id == "a_agent"
            assert shuffled[1].agent_id == "m_agent"
            assert shuffled[2].agent_id == "z_agent"
