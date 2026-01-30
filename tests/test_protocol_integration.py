"""
Protocol Integration Tests
==========================

End-to-end tests for the protocol layer including agent operations
via JSON-RPC and binary protocol.
"""

import pytest
import asyncio

from otto.protocol.protocol_router import ProtocolRouter, ProtocolFormat
from otto.protocol.layer0_binary import BinaryProtocol
from otto.protocol.layer1_jsonrpc import JSONRPCHandler
from otto.protocol.message_types import Message, MessageType
from otto.protocol.agent_bridge import AgentProtocolBridge, SpawnStatus


class TestJSONRPCAgentIntegration:
    """Integration tests for JSON-RPC agent operations."""

    @pytest.fixture
    def router(self):
        """Create router with agent bridge."""
        return ProtocolRouter()

    @pytest.mark.asyncio
    async def test_agent_spawn_via_jsonrpc(self, router):
        """Spawn agent via JSON-RPC."""
        response = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.spawn",
            "params": {
                "task": "Explore authentication patterns",
                "agent_type": "explore"
            },
            "id": 1
        })

        assert "result" in response
        result = response["result"]
        assert result["status"] == "spawned"
        assert result["agent_id"].startswith("agent-")
        assert result["result"]["agent_type"] == "explore"

    @pytest.mark.asyncio
    async def test_agent_status_via_jsonrpc(self, router):
        """Get agent status via JSON-RPC."""
        # First spawn
        spawn_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.spawn",
            "params": {"task": "Test task"},
            "id": 1
        })
        agent_id = spawn_resp["result"]["agent_id"]

        # Get status
        status_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.status",
            "params": {"agent_id": agent_id},
            "id": 2
        })

        assert "result" in status_resp
        result = status_resp["result"]
        assert result["agent_id"] == agent_id
        assert result["status"] == "running"
        assert result["task"] == "Test task"

    @pytest.mark.asyncio
    async def test_agent_list_via_jsonrpc(self, router):
        """List agents via JSON-RPC."""
        # Spawn two agents
        for i in range(2):
            await router.route({
                "jsonrpc": "2.0",
                "method": "otto.agent.spawn",
                "params": {"task": f"Task {i}"},
                "id": i
            })

        # List all
        list_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.list",
            "id": 10
        })

        assert "result" in list_resp
        agents = list_resp["result"]
        assert len(agents) == 2

    @pytest.mark.asyncio
    async def test_agent_list_active_only(self, router):
        """List only active agents."""
        # Spawn and complete one agent
        spawn1 = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.spawn",
            "params": {"task": "Task 1"},
            "id": 1
        })
        agent1_id = spawn1["result"]["agent_id"]
        await router.agent_bridge._complete_agent(agent1_id, {})

        # Spawn another (still running)
        await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.spawn",
            "params": {"task": "Task 2"},
            "id": 2
        })

        # List active only
        list_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.list",
            "params": {"active_only": True},
            "id": 10
        })

        agents = list_resp["result"]
        assert len(agents) == 1
        assert agents[0]["task"] == "Task 2"

    @pytest.mark.asyncio
    async def test_agent_abort_via_jsonrpc(self, router):
        """Abort agent via JSON-RPC."""
        # Spawn
        spawn_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.spawn",
            "params": {"task": "Long task"},
            "id": 1
        })
        agent_id = spawn_resp["result"]["agent_id"]

        # Abort
        abort_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.abort",
            "params": {"agent_id": agent_id, "reason": "User cancelled"},
            "id": 2
        })

        assert "result" in abort_resp
        result = abort_resp["result"]
        assert result["status"] == "aborted"
        assert result["result"]["reason"] == "User cancelled"

    @pytest.mark.asyncio
    async def test_agent_status_unknown_returns_error(self, router):
        """Unknown agent status returns error."""
        response = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.status",
            "params": {"agent_id": "nonexistent-agent"},
            "id": 1
        })

        assert "error" in response
        assert response["error"]["code"] == -32003  # AGENT_ERROR
        assert "Unknown agent" in response["error"]["message"]


class TestBinaryAgentIntegration:
    """Integration tests for binary protocol agent operations."""

    @pytest.fixture
    def router(self):
        return ProtocolRouter()

    @pytest.fixture
    def binary(self):
        return BinaryProtocol()

    @pytest.mark.asyncio
    async def test_agent_spawn_via_binary(self, router, binary):
        """Spawn agent via binary protocol."""
        msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={
                "agent_type": "explore",
                "task": "Find patterns"
            }
        )
        encoded = binary.encode(msg)

        response_bytes = await router.route(encoded)
        response = binary.decode(response_bytes)

        assert response.type == MessageType.AGENT_RESULT
        assert response.payload["status"] == "spawned"
        assert response.payload["agent_id"].startswith("agent-")

    @pytest.mark.asyncio
    async def test_agent_abort_via_binary(self, router, binary):
        """Abort agent via binary protocol."""
        # Spawn first
        spawn_msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={"task": "Test"}
        )
        spawn_resp_bytes = await router.route(binary.encode(spawn_msg))
        spawn_resp = binary.decode(spawn_resp_bytes)
        agent_id = spawn_resp.payload["agent_id"]

        # Abort
        abort_msg = Message(
            type=MessageType.AGENT_ABORT,
            payload={"agent_id": agent_id}
        )
        abort_resp_bytes = await router.route(binary.encode(abort_msg))
        abort_resp = binary.decode(abort_resp_bytes)

        assert abort_resp.payload["status"] == "aborted"


class TestFullAgentWorkflow:
    """Test complete agent lifecycle."""

    @pytest.fixture
    def router(self):
        return ProtocolRouter()

    @pytest.mark.asyncio
    async def test_spawn_execute_complete_workflow(self, router):
        """Full workflow: spawn → execute → complete."""
        execution_log = []

        # Register a custom executor
        async def test_executor(task, context):
            execution_log.append(task)
            return {"findings": ["pattern A", "pattern B"]}

        router.agent_bridge.register_executor("test", test_executor)

        # Spawn with custom executor type
        spawn_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.spawn",
            "params": {
                "task": "Find all patterns",
                "agent_type": "test"
            },
            "id": 1
        })

        agent_id = spawn_resp["result"]["agent_id"]

        # Wait for executor to run
        await asyncio.sleep(0.1)

        # Check status - should be completed
        status_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.status",
            "params": {"agent_id": agent_id},
            "id": 2
        })

        assert status_resp["result"]["status"] == "completed"
        assert "pattern A" in status_resp["result"]["result"]["findings"]
        assert "Find all patterns" in execution_log

    @pytest.mark.asyncio
    async def test_multiple_agents_workflow(self, router):
        """Multiple concurrent agents."""
        results = []

        # Spawn 3 agents
        for i in range(3):
            resp = await router.route({
                "jsonrpc": "2.0",
                "method": "otto.agent.spawn",
                "params": {"task": f"Task {i}"},
                "id": i
            })
            results.append(resp)

        # All should be spawned
        assert all(r["result"]["status"] == "spawned" for r in results)

        # List should show all 3
        list_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.list",
            "id": 100
        })
        assert len(list_resp["result"]) == 3

    @pytest.mark.asyncio
    async def test_concurrent_limit_workflow(self, router):
        """Concurrent agent limit is enforced in workflow."""
        # Spawn up to limit
        for i in range(3):
            await router.route({
                "jsonrpc": "2.0",
                "method": "otto.agent.spawn",
                "params": {"task": f"Task {i}"},
                "id": i
            })

        # Fourth should be rejected
        resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.spawn",
            "params": {"task": "Task 4"},
            "id": 4
        })

        assert resp["result"]["status"] == "rejected"
        assert resp["result"]["result"]["reason"] == "concurrent_limit"


class TestCrossProtocolConsistency:
    """Tests that binary and JSON-RPC produce consistent results."""

    @pytest.fixture
    def router(self):
        return ProtocolRouter()

    @pytest.fixture
    def binary(self):
        return BinaryProtocol()

    @pytest.mark.asyncio
    async def test_spawn_results_same_structure(self, router, binary):
        """Spawn via both protocols returns same structure."""
        # Via JSON-RPC
        jsonrpc_resp = await router.route({
            "jsonrpc": "2.0",
            "method": "otto.agent.spawn",
            "params": {"task": "Test A", "agent_type": "explore"},
            "id": 1
        })

        # Via binary
        binary_msg = Message(
            type=MessageType.AGENT_SPAWN,
            payload={"task": "Test B", "agent_type": "explore"}
        )
        binary_resp_bytes = await router.route(binary.encode(binary_msg))
        binary_resp = binary.decode(binary_resp_bytes)

        # Both should have same structure
        jsonrpc_result = jsonrpc_resp["result"]
        binary_result = binary_resp.payload

        assert jsonrpc_result["status"] == binary_result["status"]
        assert "agent_id" in jsonrpc_result
        assert "agent_id" in binary_result
        assert jsonrpc_result["result"]["agent_type"] == binary_result["result"]["agent_type"]


class TestProtocolRouterWithMockedComponents:
    """Test router with mocked state manager and protection engine."""

    class MockState:
        """Mock cognitive state."""
        class BurnoutLevel:
            value = "green"
        class MomentumPhase:
            value = "rolling"
        class EnergyLevel:
            value = "high"
        class Mode:
            value = "focused"

        burnout_level = BurnoutLevel()
        momentum_phase = MomentumPhase()
        energy_level = EnergyLevel()
        mode = Mode()
        session_start = 0
        exchange_count = 5

        def to_dict(self):
            return {
                "burnout_level": "green",
                "momentum_phase": "rolling",
                "energy_level": "high",
                "mode": "focused",
                "exchange_count": 5
            }

    class MockStateManager:
        def __init__(self):
            self.state = TestProtocolRouterWithMockedComponents.MockState()

        def get_state(self):
            return self.state

        def batch_update(self, updates):
            pass

        def save(self):
            pass

    class MockProtectionDecision:
        def to_dict(self):
            return {
                "action": "allow",
                "message": "",
                "can_override": True
            }

    class MockProtectionEngine:
        def check(self, state):
            return TestProtocolRouterWithMockedComponents.MockProtectionDecision()

    @pytest.fixture
    def router_with_mocks(self):
        return ProtocolRouter(
            state_manager=self.MockStateManager(),
            protection_engine=self.MockProtectionEngine()
        )

    @pytest.mark.asyncio
    async def test_status_includes_cognitive_state(self, router_with_mocks):
        """Status includes cognitive state when manager configured."""
        response = await router_with_mocks.route({
            "jsonrpc": "2.0",
            "method": "otto.status",
            "id": 1
        })

        assert "cognitive_state" in response["result"]
        state = response["result"]["cognitive_state"]
        assert state["burnout_level"] == "green"
        assert state["mode"] == "focused"

    @pytest.mark.asyncio
    async def test_state_get_returns_full_state(self, router_with_mocks):
        """State get returns full state dict."""
        response = await router_with_mocks.route({
            "jsonrpc": "2.0",
            "method": "otto.state.get",
            "id": 1
        })

        result = response["result"]
        assert result["burnout_level"] == "green"
        assert result["momentum_phase"] == "rolling"

    @pytest.mark.asyncio
    async def test_protection_check_returns_decision(self, router_with_mocks):
        """Protection check returns decision dict."""
        response = await router_with_mocks.route({
            "jsonrpc": "2.0",
            "method": "otto.protect.check",
            "params": {"action": "spawn_agent"},
            "id": 1
        })

        result = response["result"]
        assert result["action"] == "allow"
        assert result["can_override"] is True


class TestBinaryStateOperations:
    """Test binary protocol state operations."""

    class MockState:
        def to_dict(self):
            return {"burnout_level": "yellow", "mode": "exploring"}

    class MockStateManager:
        def get_state(self):
            return TestBinaryStateOperations.MockState()

        def batch_update(self, updates):
            pass

    @pytest.fixture
    def router(self):
        return ProtocolRouter(state_manager=self.MockStateManager())

    @pytest.fixture
    def binary(self):
        return BinaryProtocol()

    @pytest.mark.asyncio
    async def test_state_query_via_binary(self, router, binary):
        """STATE_QUERY via binary returns STATE_SYNC."""
        msg = Message(type=MessageType.STATE_QUERY, payload={})
        response_bytes = await router.route(binary.encode(msg))
        response = binary.decode(response_bytes)

        assert response.type == MessageType.STATE_SYNC
        assert response.payload["state"]["burnout_level"] == "yellow"

    @pytest.mark.asyncio
    async def test_state_query_with_fields_filter(self, router, binary):
        """STATE_QUERY with fields filter returns subset."""
        msg = Message(
            type=MessageType.STATE_QUERY,
            payload={"fields": ["burnout_level"]}
        )
        response_bytes = await router.route(binary.encode(msg))
        response = binary.decode(response_bytes)

        assert "burnout_level" in response.payload["state"]
        assert "mode" not in response.payload["state"]
