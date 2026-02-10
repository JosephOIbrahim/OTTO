"""
Memory Integration Tests
========================

Tests for unified memory interface integration with services.

Determinism:
- Fixed seeds for reproducibility
- Deterministic test order
- Sorted assertions
"""

import hashlib
import pytest
from datetime import datetime
from typing import Final
from unittest.mock import MagicMock, patch

# Constants
TEST_SEED: Final[int] = 0x7E57CAFE
DETERMINISM_ROUNDS: Final[int] = 10


# ============================================================================
# Memory Interface Tests
# ============================================================================

class TestOTTOMemory:
    """Tests for unified memory interface."""

    def test_singleton_pattern(self):
        """Memory interface should be singleton."""
        from otto.memory import OTTOMemory

        # Reset singleton for test
        OTTOMemory._instance = None

        m1 = OTTOMemory()
        m2 = OTTOMemory()

        assert m1 is m2, "OTTOMemory should be singleton"

    def test_episode_recording(self):
        """Episodes should be recorded to trails."""
        from otto.memory import OTTOMemory, Episode, Outcome

        OTTOMemory._instance = None
        memory = OTTOMemory()

        episode = Episode(
            type="test.action",
            data={"key": "value"},
            outcome=Outcome.SUCCESS,
            actor="test",
        )

        # Should not raise
        memory.record_episode(episode)

    def test_trail_deposit_and_follow(self):
        """Trail deposits should be followable."""
        from otto.memory import OTTOMemory, Outcome

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Deposit trail
        memory.deposit_trail("test.action", Outcome.SUCCESS)

        # Follow trail
        strength = memory.follow_trail("test.action")

        assert strength.action == "test.action"
        assert strength.strength >= 0.0

    def test_context_operations(self):
        """Context should be retrievable and updatable."""
        from otto.memory import OTTOMemory, Context, ContextDelta

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Get context (should return default)
        context = memory.get_context()

        assert context is not None
        assert hasattr(context, 'session_goal')
        assert hasattr(context, 'burnout_level')

    def test_session_lifecycle(self):
        """Session start/end should persist correctly."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Start session
        context = memory.start_session("Test goal")
        assert context is not None

        # End session
        memory.end_session(
            progress=["Task 1", "Task 2"],
            position="Completed",
            next_steps=["Task 3"],
        )

    def test_determinism_episode_hash(self):
        """Episode recording should be deterministic."""
        from otto.memory import Episode, Outcome

        # Create same episode multiple times
        hashes = set()
        for _ in range(DETERMINISM_ROUNDS):
            episode = Episode(
                type="determinism.test",
                data={"key": "value"},
                outcome=Outcome.SUCCESS,
                actor="test",
                timestamp=datetime(2025, 1, 1, 12, 0, 0),  # Fixed timestamp
            )
            trail_signal = episode.to_trail_signal()
            trail_metadata = episode.to_trail_metadata()

            # Create hash of output
            h = hashlib.sha256(
                f"{trail_signal}|{sorted(trail_metadata.items())}".encode()
            ).hexdigest()
            hashes.add(h)

        assert len(hashes) == 1, "Episode conversion should be deterministic"


# ============================================================================
# MCP Integration Tests
# ============================================================================

class TestMCPMemoryIntegration:
    """Tests for MCP server memory integration."""

    def test_tool_invocation_records_episode(self):
        """Tool invocations should record episodes to memory."""
        from otto.services.mcp.base_mcp import MCPServer, MCPTool

        # Create minimal test server
        class TestMCPServer(MCPServer):
            server_name = "test_server"

            async def _read_resource_content(self, uri: str):
                return {}

        server = TestMCPServer()

        # Mock memory
        mock_memory = MagicMock()
        server._memory = mock_memory

        tool = MCPTool(
            name="test_tool",
            description="Test tool",
            parameters={},
        )

        # Log tool invocation (this should record to memory)
        server._log_tool_invocation(tool, {"arg": "value"}, True, None)

        # Check that memory methods were called
        assert mock_memory.record_episode.called or mock_memory.deposit_trail.called


# ============================================================================
# Approval Memory Integration Tests
# ============================================================================

class TestApprovalMemoryIntegration:
    """Tests for approval system memory integration."""

    def test_approval_deposits_trail(self):
        """Approvals should deposit trails for trust tracking."""
        from otto.services.approval import ApprovalGate

        gate = ApprovalGate()

        # Mock memory - the inline import inside _record_approval_to_memory
        # uses 'from ..memory import get_memory' which resolves to 'otto.memory'
        mock_memory = MagicMock()

        # Patch at the otto.memory module level since that's where imports come from
        with patch('otto.memory.get_memory', return_value=mock_memory):
            # This is internal method that records to memory
            gate._record_approval_to_memory("test.action", "test.actor", approved=True)

        # Verify trail was deposited (or episode recorded)
        assert mock_memory.deposit_trail.called or mock_memory.record_episode.called

    def test_trust_uses_trail_strength(self):
        """Trust check should use trail strength from memory."""
        from otto.services.approval import ApprovalGate

        gate = ApprovalGate()

        # Register a trust-eligible policy
        from otto.services.approval import ApprovalPolicy, ApprovalCategory
        gate.register_policy(ApprovalPolicy(
            action="test.read",
            category=ApprovalCategory.TRUST,
            description="Test read action",
            trust_eligible=True,
        ))

        # Get trust (should query memory)
        trust = gate.get_trust("test.read", "test.actor")

        # Should return a value (0.0 if no trails)
        assert isinstance(trust, float)


# ============================================================================
# Observer Memory Integration Tests
# ============================================================================

class TestObserverMemoryIntegration:
    """Tests for substrate observer memory integration."""

    def test_change_recording_to_memory(self):
        """Belief changes should be recorded to memory."""
        from otto.substrate.observer import SubstrateObserver, BeliefChange, ChangeType
        from otto.substrate.interface import CognitiveSubstrate, SubstrateTier

        # Create mock substrate
        mock_substrate = MagicMock(spec=CognitiveSubstrate)
        mock_substrate.get.return_value = None
        mock_substrate.keys.return_value = []
        mock_substrate.verify_constitutional_integrity.return_value = []

        observer = SubstrateObserver(mock_substrate)

        # Record a change
        change = BeliefChange(
            timestamp=datetime.now(),
            key="test.key",
            tier=SubstrateTier.LEARNED,
            change_type=ChangeType.MODIFIED,
            old_value="old",
            new_value="new",
            source="test",
        )

        observer.record_change(change)

        # Change should be in history
        assert len(observer._history) == 1

    def test_learning_proposal(self):
        """Observer should be able to propose learnings."""
        from otto.substrate.observer import SubstrateObserver
        from otto.substrate.interface import CognitiveSubstrate

        mock_substrate = MagicMock(spec=CognitiveSubstrate)
        mock_substrate.get.return_value = None
        mock_substrate.keys.return_value = []
        mock_substrate.verify_constitutional_integrity.return_value = []

        observer = SubstrateObserver(mock_substrate)

        # Mock memory
        mock_memory = MagicMock()
        mock_memory.propose_learning.return_value = True
        observer._memory = mock_memory

        # Propose learning
        result = observer.propose_learning(
            key="test.key",
            proposed_value="new_value",
            reason="Test reason",
        )

        # Should succeed with mock
        assert result is True
        mock_memory.propose_learning.assert_called_once()


# ============================================================================
# Surface Memory Integration Tests
# ============================================================================

class TestSurfaceMemoryIntegration:
    """Tests for surface memory integration."""

    def test_session_start_end(self):
        """Surface session should use memory."""
        from otto.surfaces.base import Surface, SurfaceType, RenderFormat, SurfaceResponse

        # Create minimal test surface
        class TestSurface(Surface):
            surface_type = SurfaceType.CLI

            def render(self, response: SurfaceResponse) -> str:
                return response.content

            def process_input(self, raw_input: str):
                from otto.surfaces.base import InputContext
                return InputContext(raw_input=raw_input)

            def display(self, content: str) -> None:
                pass

            def prompt(self, message: str = "") -> str:
                return ""

        surface = TestSurface()

        # Start session
        surface.start_session("Test goal")
        assert surface._session_goal == "Test goal"

        # End session
        surface.end_session(
            progress=["Did thing"],
            position="Done",
        )
        assert surface._session_goal is None

    def test_get_session_context(self):
        """Surface should return session context."""
        from otto.surfaces.base import Surface, SurfaceType, RenderFormat, SurfaceResponse

        class TestSurface(Surface):
            surface_type = SurfaceType.CLI

            def render(self, response: SurfaceResponse) -> str:
                return response.content

            def process_input(self, raw_input: str):
                from otto.surfaces.base import InputContext
                return InputContext(raw_input=raw_input)

            def display(self, content: str) -> None:
                pass

            def prompt(self, message: str = "") -> str:
                return ""

        surface = TestSurface()
        surface.start_session("My goal")

        context = surface.get_session_context()

        assert "goal" in context
        assert context["goal"] == "My goal"


# ============================================================================
# Determinism Tests
# ============================================================================

class TestMemoryDeterminism:
    """Tests for Determinism."""

    def test_outcome_enum_determinism(self):
        """Outcome enum values should be deterministic."""
        from otto.memory import Outcome

        # Run multiple times
        for _ in range(DETERMINISM_ROUNDS):
            assert Outcome.SUCCESS.value == "success"
            assert Outcome.FAILURE.value == "failure"
            assert Outcome.PARTIAL.value == "partial"

    def test_trail_strength_calculation_determinism(self):
        """Trail strength calculation should be deterministic."""
        from otto.memory import TrailStrength
        from datetime import datetime

        # Create same trail strength multiple times
        results = []
        for _ in range(DETERMINISM_ROUNDS):
            ts = TrailStrength(
                action="test.action",
                signal="success",
                strength=0.85,
                reinforced_count=5,
                last_deposit=datetime(2025, 1, 1, 12, 0, 0),
            )
            results.append(ts.auto_approvable)

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_context_fresh_determinism(self):
        """Fresh context creation should be deterministic (except timestamp)."""
        from otto.memory import Context

        # Create multiple fresh contexts
        contexts = []
        for _ in range(DETERMINISM_ROUNDS):
            ctx = Context.fresh()
            contexts.append({
                "expert": ctx.current_expert,
                "altitude": ctx.current_altitude,
                "burnout": ctx.burnout_level,
                "momentum": ctx.momentum_phase,
            })

        # All should have same default values
        for ctx in contexts:
            assert ctx == contexts[0]


# ============================================================================
# Auto-Approval Integration Tests
# ============================================================================

class TestAutoApprovalIntegration:
    """Tests for auto-approval based on trail strength."""

    def test_auto_approval_threshold(self):
        """Actions with high trail strength should auto-approve."""
        from otto.memory import TrailStrength, AUTO_APPROVE_THRESHOLD

        # High strength -> auto-approvable
        high_strength = TrailStrength(
            action="test.action",
            signal="success",
            strength=AUTO_APPROVE_THRESHOLD + 0.1,
            reinforced_count=10,
            last_deposit=datetime.now(),
        )
        assert high_strength.auto_approvable is True

        # Low strength -> not auto-approvable
        low_strength = TrailStrength(
            action="test.action",
            signal="success",
            strength=AUTO_APPROVE_THRESHOLD - 0.1,
            reinforced_count=2,
            last_deposit=datetime.now(),
        )
        assert low_strength.auto_approvable is False

    def test_threshold_is_fixed(self):
        """Auto-approval threshold should be fixed."""
        from otto.memory import AUTO_APPROVE_THRESHOLD

        # Threshold should always be 0.8
        assert AUTO_APPROVE_THRESHOLD == 0.8


# ============================================================================
# Knowledge Graph Integration Tests
# ============================================================================

class TestKnowledgeGraphIntegration:
    """Tests for Knowledge Graph integration."""

    def test_knowledge_graph_bootstrap(self):
        """Knowledge graph should have bootstrap prims."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Check bootstrap knowledge exists
        prim = memory.get_knowledge("/Knowledge/OTTO/Memory")
        assert prim is not None
        assert prim.confidence >= 0.85

    def test_knowledge_query_by_trigger(self):
        """Knowledge should be queryable by trigger."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Query by trigger
        results = memory.query_knowledge("livrps")
        assert len(results) > 0
        assert any("LIVRPS" in p.path for p in results)

    def test_knowledge_deterministic_query(self):
        """Query results should be deterministic."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Run query multiple times
        results_hashes = set()
        for _ in range(DETERMINISM_ROUNDS):
            results = memory.query_knowledge("otto")
            # Hash the paths for comparison
            paths_str = "|".join(sorted(p.path for p in results))
            results_hashes.add(hashlib.sha256(paths_str.encode()).hexdigest())

        assert len(results_hashes) == 1, "Query results should be deterministic"

    def test_has_knowledge(self):
        """has_knowledge should check path existence."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        assert memory.has_knowledge("/Knowledge/OTTO/Memory") is True
        assert memory.has_knowledge("/Knowledge/NonExistent") is False

    def test_list_knowledge(self):
        """list_knowledge should return sorted paths."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        paths = memory.list_knowledge("/Knowledge/OTTO")
        assert len(paths) > 0
        # Verify sorted
        assert paths == sorted(paths)


# ============================================================================
# Trail Decay Tests
# ============================================================================

class TestTrailDecayIntegration:
    """Tests for trail decay integration."""

    def test_decay_factor_calculation(self):
        """Decay factor should follow formula."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # At 0 hours, no decay
        assert memory.get_decay_factor(0) == 1.0

        # At half-life (168 hours = 7 days), factor should be 0.5
        factor = memory.get_decay_factor(168)
        assert abs(factor - 0.5) < 0.001

        # At double half-life, factor should be 0.25
        factor = memory.get_decay_factor(336)
        assert abs(factor - 0.25) < 0.001

    def test_decay_factor_determinism(self):
        """Decay factor should be deterministic."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Same input should always give same output
        results = set()
        for _ in range(DETERMINISM_ROUNDS):
            factor = memory.get_decay_factor(100)
            results.add(round(factor, 10))

        assert len(results) == 1

    def test_run_decay(self):
        """run_decay should not error with mock trail store."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Should not raise
        decayed = memory.run_decay(force=True)
        assert isinstance(decayed, int)


# ============================================================================
# Memory Metrics Tests
# ============================================================================

class TestMemoryMetricsIntegration:
    """Tests for memory metrics integration."""

    def test_get_metrics(self):
        """get_metrics should return dictionary."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        metrics = memory.get_metrics()

        assert isinstance(metrics, dict)
        assert "memory" in metrics
        assert "knowledge" in metrics
        assert "decay" in metrics

    def test_metrics_tracking(self):
        """Operations should increment metrics."""
        from otto.memory import OTTOMemory, Episode, Outcome

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Get initial metrics
        initial = memory.get_metrics()
        initial_episodes = initial["memory"]["episodes_recorded"]

        # Record an episode
        episode = Episode(
            type="metrics.test",
            data={"key": "value"},
            outcome=Outcome.SUCCESS,
            actor="test",
        )
        memory.record_episode(episode)

        # Check metrics increased
        updated = memory.get_metrics()
        assert updated["memory"]["episodes_recorded"] == initial_episodes + 1

    def test_auto_approval_tracking(self):
        """Auto-approval should track in metrics."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Get initial
        initial = memory.get_metrics()["memory"]["auto_approvals"]

        # Record auto-approval
        memory.record_auto_approval(approved=True)
        memory.record_auto_approval(approved=False)

        # Check tracking
        updated = memory.get_metrics()["memory"]
        assert updated["auto_approvals"] == initial + 1
        assert updated["manual_approvals"] >= 1

    def test_metrics_determinism(self):
        """Metrics structure should be deterministic."""
        from otto.memory import OTTOMemory

        OTTOMemory._instance = None
        memory = OTTOMemory()

        # Get metrics multiple times
        keys_sets = set()
        for _ in range(DETERMINISM_ROUNDS):
            metrics = memory.get_metrics()
            # Hash the keys structure
            all_keys = []
            for section, values in sorted(metrics.items()):
                if isinstance(values, dict):
                    all_keys.extend(f"{section}.{k}" for k in sorted(values.keys()))
            keys_sets.add("|".join(all_keys))

        assert len(keys_sets) == 1, "Metrics structure should be deterministic"


# ============================================================================
# Constants Tests
# ============================================================================

class TestMemoryConstants:
    """Tests for memory constants."""

    def test_cognitive_tile_size_fixed(self):
        """COGNITIVE_TILE_SIZE should be fixed at 32."""
        from otto.memory import COGNITIVE_TILE_SIZE

        assert COGNITIVE_TILE_SIZE == 32

    def test_memory_seed_fixed(self):
        """MEMORY_SEED should be fixed."""
        from otto.memory import MEMORY_SEED

        assert MEMORY_SEED == 0xAE0717E5


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
