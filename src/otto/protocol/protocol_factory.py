"""
Protocol Factory
================

Factory functions for creating fully-wired protocol components.

This is the integration layer that connects the protocol router to
all real OTTO OS components:
- CognitiveStateManager (state persistence)
- ProtectionEngine (safety gating)
- DecisionEngine (work/delegate/protect decisions)
- AgentCoordinator (agent lifecycle)
- HumanRender (dignity-first output)

Usage:
    >>> from otto.protocol import create_protocol_router
    >>> router = create_protocol_router()
    >>> response = await router.route({"jsonrpc": "2.0", "method": "otto.status", "id": 1})

Determinism:
- Fixed initialization order
- Deterministic component wiring
- All dependencies explicitly declared
"""

import logging
from pathlib import Path
from typing import Optional

from .protocol_router import ProtocolRouter
from .agent_bridge import AgentBridgeConfig

logger = logging.getLogger(__name__)


def create_protocol_router(
    otto_dir: Path = None,
    state_manager=None,
    protection_engine=None,
    decision_engine=None,
    coordinator=None,
    render=None,
    agent_config: AgentBridgeConfig = None,
    register_default_executors: bool = True,
) -> ProtocolRouter:
    """
    Create a fully-wired ProtocolRouter with all real components.

    This factory function handles the complex wiring of all OTTO OS
    components into a single protocol router that can handle:
    - Binary protocol messages (MessagePack)
    - JSON-RPC 2.0 requests
    - Human-readable text

    Args:
        otto_dir: Base directory for OTTO state (default: ~/.otto)
        state_manager: Optional CognitiveStateManager (created if None)
        protection_engine: Optional ProtectionEngine (created if None)
        decision_engine: Optional DecisionEngine (created if None)
        coordinator: Optional AgentCoordinator (created if None)
        render: Optional HumanRender (created if None)
        agent_config: Optional AgentBridgeConfig
        register_default_executors: Register default agent executors

    Returns:
        Fully-wired ProtocolRouter instance

    Example:
        >>> router = create_protocol_router()
        >>> # JSON-RPC request
        >>> response = await router.route({
        ...     "jsonrpc": "2.0",
        ...     "method": "otto.status",
        ...     "id": 1
        ... })
        >>> # Binary protocol
        >>> response = await router.route(binary_message)
    """
    otto_dir = otto_dir or Path.home() / ".otto"

    # Create state manager if not provided
    if state_manager is None:
        try:
            from ..cognitive_state import CognitiveStateManager
            state_manager = CognitiveStateManager(otto_dir / "state")
            logger.debug("Created CognitiveStateManager")
        except ImportError:
            logger.warning("CognitiveStateManager not available")

    # Create protection engine if not provided
    if protection_engine is None and state_manager is not None:
        try:
            from ..protection.protection_engine import ProtectionEngine
            from ..profile_loader import ProfileLoader

            # Load profile for protection engine
            profile_loader = ProfileLoader(otto_dir)
            profile = profile_loader.load()

            protection_engine = ProtectionEngine(profile)
            logger.debug("Created ProtectionEngine")
        except ImportError:
            logger.warning("ProtectionEngine not available")
        except Exception as e:
            logger.warning(f"Could not create ProtectionEngine: {e}")

    # Create decision engine if not provided
    # Pass False to explicitly disable (None = auto-create)
    if decision_engine is None:
        try:
            from ..decision_engine import DecisionEngine
            decision_engine = DecisionEngine()
            logger.debug("Created DecisionEngine")
        except ImportError:
            logger.warning("DecisionEngine not available")
    elif decision_engine is False:
        decision_engine = None  # Explicitly disabled

    # Create agent coordinator if not provided
    if coordinator is None:
        try:
            from ..agent_coordinator import AgentCoordinator
            coordinator = AgentCoordinator()
            logger.debug("Created AgentCoordinator")
        except ImportError:
            logger.warning("AgentCoordinator not available")

    # Create render if not provided
    if render is None:
        try:
            from ..render.human_render import HumanRender
            render = HumanRender()
            logger.debug("Created HumanRender")
        except ImportError:
            logger.warning("HumanRender not available")

    # Create the router with all components
    router = ProtocolRouter(
        state_manager=state_manager,
        protection_engine=protection_engine,
        render=render,
        decision_engine=decision_engine,
        coordinator=coordinator,
        agent_bridge_config=agent_config,
    )

    # Register default executors if requested
    if register_default_executors:
        _register_default_executors(router)

    logger.info("Created fully-wired ProtocolRouter")
    return router


def _register_default_executors(router: ProtocolRouter) -> None:
    """
    Register default agent executors with the router's agent bridge.

    Default executors:
    - explore: Codebase exploration
    - implement: Code implementation
    - review: Code review
    - research: Research and analysis
    - general: General-purpose tasks
    """
    try:
        from .agent_executors import (
            explore_executor,
            implement_executor,
            review_executor,
            research_executor,
            general_executor,
        )

        router.agent_bridge.register_executor("explore", explore_executor)
        router.agent_bridge.register_executor("implement", implement_executor)
        router.agent_bridge.register_executor("review", review_executor)
        router.agent_bridge.register_executor("research", research_executor)
        router.agent_bridge.register_executor("general", general_executor)

        logger.debug("Registered 5 default agent executors")
    except ImportError as e:
        logger.warning(f"Could not register default executors: {e}")


def create_minimal_router() -> ProtocolRouter:
    """
    Create a minimal ProtocolRouter without external dependencies.

    Useful for testing or when full wiring is not needed.
    Only provides basic protocol functionality.

    Returns:
        Minimal ProtocolRouter instance
    """
    return ProtocolRouter()


def create_router_with_state(
    otto_dir: Path = None,
) -> ProtocolRouter:
    """
    Create a ProtocolRouter with only state management.

    Useful when you need state tracking but not the full
    protection/coordination infrastructure.

    Args:
        otto_dir: Base directory for OTTO state

    Returns:
        ProtocolRouter with CognitiveStateManager
    """
    otto_dir = otto_dir or Path.home() / ".otto"

    try:
        from ..cognitive_state import CognitiveStateManager
        state_manager = CognitiveStateManager(otto_dir / "state")
    except ImportError:
        state_manager = None

    return ProtocolRouter(state_manager=state_manager)


__all__ = [
    "create_protocol_router",
    "create_minimal_router",
    "create_router_with_state",
]
