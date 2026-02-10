"""
Agent Protocol Bridge
=====================

Bridges the protocol layer to the agent coordination infrastructure.

Connects:
- AGENT_SPAWN messages → DecisionEngine.process_task() → AgentCoordinator
- AGENT_RESULT messages → AgentCoordinator.agent_completed()
- AGENT_ABORT messages → AgentCoordinator abort handling

This is the translation layer between structured protocol messages and
the existing orchestration logic.

Determinism:
- Fixed message → method mapping
- State snapshot via DecisionEngine (already compliant)
- Deterministic result formatting
"""

import asyncio
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

from .message_types import Message, MessageType, create_error

logger = logging.getLogger(__name__)


class AgentBridgeError(Exception):
    """Error in agent protocol bridge."""
    pass


class SpawnStatus(Enum):
    """Status of agent spawn operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class SpawnedAgent:
    """Tracks a spawned agent."""
    agent_id: str
    agent_type: str
    task: str
    spawned_at: datetime
    status: SpawnStatus = SpawnStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class AgentBridgeConfig:
    """Configuration for agent bridge."""
    max_concurrent_agents: int = 3
    default_timeout_seconds: float = 300.0
    enable_flow_protection: bool = True


class AgentProtocolBridge:
    """
    Bridges protocol messages to agent coordination.

    This class connects the protocol layer's structured messages to the
    existing AgentCoordinator and DecisionEngine infrastructure.

    Example:
        >>> bridge = AgentProtocolBridge(decision_engine, coordinator)
        >>> spawn_msg = Message(
        ...     type=MessageType.AGENT_SPAWN,
        ...     payload={"agent_type": "explore", "task": "Find auth patterns"}
        ... )
        >>> response = await bridge.handle_message(spawn_msg)
    """

    def __init__(
        self,
        decision_engine=None,
        coordinator=None,
        state_manager=None,
        config: AgentBridgeConfig = None,
    ):
        """
        Initialize agent bridge.

        Args:
            decision_engine: DecisionEngine instance for task processing
            coordinator: AgentCoordinator instance for agent management
            state_manager: CognitiveStateManager for state access
            config: Bridge configuration
        """
        self.decision_engine = decision_engine
        self.coordinator = coordinator
        self.state_manager = state_manager
        self.config = config or AgentBridgeConfig()

        # Track spawned agents
        self._agents: Dict[str, SpawnedAgent] = {}

        # Agent executors (registered by type)
        self._executors: Dict[str, Callable] = {}

        # Message handlers
        self._handlers = {
            MessageType.AGENT_SPAWN: self._handle_spawn,
            MessageType.AGENT_RESULT: self._handle_result,
            MessageType.AGENT_ABORT: self._handle_abort,
        }

    async def handle_message(self, message: Message) -> Message:
        """
        Handle an agent-related protocol message.

        Args:
            message: Incoming Message

        Returns:
            Response Message
        """
        handler = self._handlers.get(message.type)
        if not handler:
            return message.reply(
                MessageType.ERROR,
                {
                    "code": -1,
                    "message": f"Unknown message type for agent bridge: {message.type}",
                }
            )

        try:
            return await handler(message)
        except Exception as e:
            logger.exception(f"Error handling {message.type}: {e}")
            return message.reply(
                MessageType.ERROR,
                {
                    "code": -2,
                    "message": str(e),
                }
            )

    async def _handle_spawn(self, message: Message) -> Message:
        """
        Handle AGENT_SPAWN message.

        Validates the request, makes a decision via DecisionEngine,
        and either spawns agents or explains why not.
        """
        payload = message.payload
        agent_type = payload.get("agent_type", "general")
        task = payload.get("task", "")
        context = payload.get("context", {})
        timeout = payload.get("timeout", self.config.default_timeout_seconds)

        if not task:
            return message.reply(
                MessageType.ERROR,
                {"code": -3, "message": "Task is required for AGENT_SPAWN"}
            )

        # Check concurrent agent limit
        active_count = len([a for a in self._agents.values()
                           if a.status == SpawnStatus.RUNNING])
        if active_count >= self.config.max_concurrent_agents:
            return message.reply(
                MessageType.AGENT_RESULT,
                {
                    "agent_id": None,
                    "status": "rejected",
                    "result": {
                        "reason": "concurrent_limit",
                        "message": f"Max {self.config.max_concurrent_agents} concurrent agents",
                        "active": active_count,
                    }
                }
            )

        # If decision engine available, use it for work/delegate/protect decision
        if self.decision_engine:
            from ..decision_engine import TaskRequest, TaskCategory

            # Map agent_type to task category
            type_to_category = {
                "explore": TaskCategory.EXPLORATION,
                "implement": TaskCategory.IMPLEMENTATION,
                "review": TaskCategory.REVIEW,
                "test": TaskCategory.DEBUGGING,
                "research": TaskCategory.RESEARCH,
                "general": TaskCategory.SIMPLE,
            }
            category = type_to_category.get(agent_type, TaskCategory.SIMPLE)

            request = TaskRequest(
                description=task,
                category=category,
                files_involved=context.get("files", []),
                estimated_scope=context.get("scope", "small"),
            )

            plan = self.decision_engine.process_task(request, context)

            # Check decision
            from ..agent_coordinator import DecisionMode

            if plan.decision.mode == DecisionMode.PROTECT:
                # Flow protection active - queue instead of spawn
                return message.reply(
                    MessageType.AGENT_RESULT,
                    {
                        "agent_id": None,
                        "status": "queued",
                        "result": {
                            "reason": "flow_protection",
                            "message": plan.decision.rationale,
                            "protect_until": plan.decision.protect_until,
                        }
                    }
                )

            if plan.decision.mode == DecisionMode.WORK:
                # Decision is to work directly, not spawn agent
                return message.reply(
                    MessageType.AGENT_RESULT,
                    {
                        "agent_id": None,
                        "status": "direct_work",
                        "result": {
                            "reason": "work_preferred",
                            "message": plan.decision.rationale,
                            "steps": plan.steps,
                        }
                    }
                )

        # Generate agent ID and register
        agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        spawned = SpawnedAgent(
            agent_id=agent_id,
            agent_type=agent_type,
            task=task,
            spawned_at=datetime.now(),
            status=SpawnStatus.RUNNING,
        )
        self._agents[agent_id] = spawned

        # Register with coordinator if available
        if self.coordinator:
            from ..agent_coordinator import AgentType
            agent_type_enum = AgentType[agent_type.upper()] if agent_type.upper() in AgentType.__members__ else AgentType.GENERAL
            self.coordinator.register_agent(agent_id, agent_type_enum, task)

        logger.info(f"Spawned agent {agent_id} ({agent_type}) for: {task[:50]}...")

        # If we have an executor for this type, run it
        executor = self._executors.get(agent_type)
        if executor:
            # Start agent execution in background
            asyncio.create_task(
                self._execute_agent(agent_id, executor, task, context, timeout)
            )

        return message.reply(
            MessageType.AGENT_RESULT,
            {
                "agent_id": agent_id,
                "status": "spawned",
                "result": {
                    "agent_type": agent_type,
                    "task": task,
                    "spawned_at": spawned.spawned_at.isoformat(),
                }
            }
        )

    async def _execute_agent(
        self,
        agent_id: str,
        executor: Callable,
        task: str,
        context: Dict[str, Any],
        timeout: float
    ):
        """Execute an agent with timeout handling."""
        try:
            result = await asyncio.wait_for(
                executor(task, context),
                timeout=timeout
            )
            await self._complete_agent(agent_id, result)
        except asyncio.TimeoutError:
            await self._fail_agent(agent_id, "Execution timeout")
        except Exception as e:
            await self._fail_agent(agent_id, str(e))

    async def _complete_agent(self, agent_id: str, result: Any):
        """Mark agent as completed with result."""
        if agent_id not in self._agents:
            return

        agent = self._agents[agent_id]
        agent.status = SpawnStatus.COMPLETED
        agent.result = result if isinstance(result, dict) else {"value": result}

        # Notify coordinator
        if self.coordinator:
            self.coordinator.agent_completed(agent_id, result)

        logger.info(f"Agent {agent_id} completed")

    async def _fail_agent(self, agent_id: str, error: str):
        """Mark agent as failed."""
        if agent_id not in self._agents:
            return

        agent = self._agents[agent_id]
        agent.status = SpawnStatus.FAILED
        agent.error = error

        logger.error(f"Agent {agent_id} failed: {error}")

    async def _handle_result(self, message: Message) -> Message:
        """
        Handle AGENT_RESULT message.

        This is typically sent by an external agent reporting its result.
        """
        payload = message.payload
        agent_id = payload.get("agent_id")
        status = payload.get("status", "unknown")
        result = payload.get("result", {})
        errors = payload.get("errors", [])

        if not agent_id:
            return message.reply(
                MessageType.ERROR,
                {"code": -3, "message": "agent_id required"}
            )

        if agent_id not in self._agents:
            # Unknown agent - might be from external source
            logger.warning(f"Result for unknown agent: {agent_id}")

        if status == "success":
            await self._complete_agent(agent_id, result)
        elif status == "failure":
            await self._fail_agent(agent_id, "; ".join(errors) or "Unknown failure")

        # Acknowledge
        return message.reply(
            MessageType.AGENT_RESULT,
            {
                "agent_id": agent_id,
                "status": "acknowledged",
                "result": {"processed": True}
            }
        )

    async def _handle_abort(self, message: Message) -> Message:
        """Handle AGENT_ABORT message."""
        payload = message.payload
        agent_id = payload.get("agent_id")
        reason = payload.get("reason", "User requested abort")

        if not agent_id:
            return message.reply(
                MessageType.ERROR,
                {"code": -3, "message": "agent_id required"}
            )

        if agent_id not in self._agents:
            return message.reply(
                MessageType.ERROR,
                {"code": -4, "message": f"Unknown agent: {agent_id}"}
            )

        agent = self._agents[agent_id]
        if agent.status != SpawnStatus.RUNNING:
            return message.reply(
                MessageType.AGENT_RESULT,
                {
                    "agent_id": agent_id,
                    "status": "not_running",
                    "result": {"current_status": agent.status.value}
                }
            )

        # Mark as aborted
        agent.status = SpawnStatus.ABORTED
        agent.error = reason

        logger.info(f"Agent {agent_id} aborted: {reason}")

        return message.reply(
            MessageType.AGENT_RESULT,
            {
                "agent_id": agent_id,
                "status": "aborted",
                "result": {"reason": reason}
            }
        )

    def register_executor(self, agent_type: str, executor: Callable):
        """
        Register an executor function for an agent type.

        The executor should be an async function that takes (task, context)
        and returns a result dict.

        Args:
            agent_type: Type of agent (e.g., "explore", "implement")
            executor: Async callable(task: str, context: dict) -> dict
        """
        self._executors[agent_type] = executor
        logger.info(f"Registered executor for agent type: {agent_type}")

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        return {
            "agent_id": agent.agent_id,
            "agent_type": agent.agent_type,
            "task": agent.task,
            "status": agent.status.value,
            "spawned_at": agent.spawned_at.isoformat(),
            "result": agent.result,
            "error": agent.error,
        }

    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Get status of all tracked agents."""
        return [self.get_agent_status(aid) for aid in self._agents]

    def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get only running agents."""
        return [
            self.get_agent_status(aid)
            for aid, agent in self._agents.items()
            if agent.status == SpawnStatus.RUNNING
        ]

    def cleanup_completed(self, max_age_seconds: float = 3600.0):
        """Remove completed/failed agents older than max_age."""
        now = datetime.now()
        to_remove = []

        for agent_id, agent in self._agents.items():
            if agent.status in (SpawnStatus.COMPLETED, SpawnStatus.FAILED, SpawnStatus.ABORTED):
                age = (now - agent.spawned_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(agent_id)

        for agent_id in to_remove:
            del self._agents[agent_id]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old agents")


def create_agent_bridge(
    decision_engine=None,
    coordinator=None,
    state_manager=None,
) -> AgentProtocolBridge:
    """
    Factory function to create an agent bridge.

    If components are not provided, creates standalone bridge.
    """
    return AgentProtocolBridge(
        decision_engine=decision_engine,
        coordinator=coordinator,
        state_manager=state_manager,
    )


__all__ = [
    "AgentProtocolBridge",
    "AgentBridgeConfig",
    "AgentBridgeError",
    "SpawnStatus",
    "SpawnedAgent",
    "create_agent_bridge",
]
