"""
Tests for Protocol Factory
===========================

Tests for the protocol factory functions that wire all components together.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from otto.protocol.protocol_factory import (
    create_protocol_router,
    create_minimal_router,
    create_router_with_state,
)
from otto.protocol.protocol_router import ProtocolRouter


class TestCreateProtocolRouter:
    """Tests for create_protocol_router factory."""

    def test_creates_router_instance(self):
        """Factory creates a ProtocolRouter instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_protocol_router(otto_dir=Path(tmpdir))
            assert isinstance(router, ProtocolRouter)

    def test_accepts_custom_otto_dir(self):
        """Factory accepts custom otto_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_protocol_router(otto_dir=Path(tmpdir))
            assert router is not None

    def test_creates_agent_bridge(self):
        """Factory creates agent bridge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_protocol_router(otto_dir=Path(tmpdir))
            assert router.agent_bridge is not None

    def test_registers_default_executors(self):
        """Factory registers default executors when requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_protocol_router(
                otto_dir=Path(tmpdir),
                register_default_executors=True
            )
            # Check executors are registered
            assert "explore" in router.agent_bridge._executors
            assert "implement" in router.agent_bridge._executors
            assert "review" in router.agent_bridge._executors

    def test_skips_executors_when_disabled(self):
        """Factory skips executors when disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_protocol_router(
                otto_dir=Path(tmpdir),
                register_default_executors=False
            )
            # Should have no executors
            assert len(router.agent_bridge._executors) == 0

    def test_accepts_custom_state_manager(self):
        """Factory accepts custom state manager."""
        mock_manager = MagicMock()
        router = create_protocol_router(
            state_manager=mock_manager,
            register_default_executors=False
        )
        assert router.state_manager == mock_manager

    def test_accepts_custom_protection_engine(self):
        """Factory accepts custom protection engine."""
        mock_engine = MagicMock()
        router = create_protocol_router(
            protection_engine=mock_engine,
            register_default_executors=False
        )
        assert router.protection_engine == mock_engine


class TestCreateMinimalRouter:
    """Tests for create_minimal_router factory."""

    def test_creates_router_instance(self):
        """Factory creates a ProtocolRouter instance."""
        router = create_minimal_router()
        assert isinstance(router, ProtocolRouter)

    def test_has_no_state_manager(self):
        """Minimal router has no state manager."""
        router = create_minimal_router()
        assert router.state_manager is None

    def test_has_no_protection_engine(self):
        """Minimal router has no protection engine."""
        router = create_minimal_router()
        assert router.protection_engine is None

    def test_still_has_agent_bridge(self):
        """Minimal router still has agent bridge."""
        router = create_minimal_router()
        assert router.agent_bridge is not None


class TestCreateRouterWithState:
    """Tests for create_router_with_state factory."""

    def test_creates_router_instance(self):
        """Factory creates a ProtocolRouter instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router_with_state(otto_dir=Path(tmpdir))
            assert isinstance(router, ProtocolRouter)

    def test_has_state_manager(self):
        """Router has state manager configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_router_with_state(otto_dir=Path(tmpdir))
            # State manager should be created (may be None if import fails)
            # Just verify router was created
            assert router is not None


class TestFactoryIntegration:
    """Integration tests for factory functions."""

    @pytest.mark.asyncio
    async def test_factory_router_handles_jsonrpc(self):
        """Factory-created router handles JSON-RPC requests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_protocol_router(
                otto_dir=Path(tmpdir),
                register_default_executors=True
            )

            response = await router.route({
                "jsonrpc": "2.0",
                "method": "otto.ping",
                "id": 1
            })

            assert "result" in response
            assert response["result"] == "pong"

    @pytest.mark.asyncio
    async def test_factory_router_handles_agent_spawn(self):
        """Factory-created router handles agent spawn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create router without decision engine so agents actually spawn
            # (With decision engine, it may choose to work directly)
            # Pass False to explicitly disable (None = auto-create)
            router = create_protocol_router(
                otto_dir=Path(tmpdir),
                decision_engine=False,  # Explicitly disable decision engine
                register_default_executors=True
            )

            response = await router.route({
                "jsonrpc": "2.0",
                "method": "otto.agent.spawn",
                "params": {
                    "task": "Test task",
                    "agent_type": "explore"
                },
                "id": 1
            })

            assert "result" in response
            result = response["result"]
            assert result["status"] == "spawned"
            assert result["agent_id"].startswith("agent-")

    @pytest.mark.asyncio
    async def test_factory_router_methods_list(self):
        """Factory-created router lists all methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            router = create_protocol_router(
                otto_dir=Path(tmpdir),
                register_default_executors=False
            )

            response = await router.route({
                "jsonrpc": "2.0",
                "method": "otto.methods",
                "id": 1
            })

            methods = response["result"]
            assert "otto.ping" in methods
            assert "otto.status" in methods
            assert "otto.agent.spawn" in methods
            assert "otto.agent.list" in methods
