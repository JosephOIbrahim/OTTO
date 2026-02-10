"""
Agent Type Framework
====================

Defines the 4-tier agent autonomy hierarchy for OTTO.

Agent Types (increasing autonomy):
1. SYNCHRONOUS: Simple request-response, no autonomy
2. SUPERVISED: Actions require explicit approval
3. BOUNDED: Autonomous within defined limits
4. AUTONOMOUS: Full autonomy (requires highest trust)

Determinism:
- Fixed autonomy levels (no runtime variation)
- Deterministic approval routing
- Fixed limit enforcement
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any, Callable, Dict, Final, List, Optional, Set

from .base import (
    Agent,
    AgentConfig,
    AgentResult,
    AgentProgress,
    AgentState,
    NonRetryableError,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Constants - Determinism
# ============================================================================

AGENT_SEED: Final[int] = 0xA6E77F00
FRAMEWORK_SEED: Final[int] = AGENT_SEED  # Alias for backward compatibility
MAX_PARALLEL_AGENTS: Final[int] = 3
MAX_CHAIN_DEPTH: Final[int] = 3


class AgentAutonomy(IntEnum):
    """Agent autonomy levels (increasing autonomy)."""
    SYNCHRONOUS = 0   # Request-response only
    SUPERVISED = 1    # Requires approval for actions
    BOUNDED = 2       # Autonomous within limits
    AUTONOMOUS = 3    # Full autonomy


class ActionType(IntEnum):
    """Types of actions agents can perform."""
    READ = 0          # Read-only operations (safe)
    WRITE = 1         # Create/modify data
    DELETE = 2        # Delete data
    EXTERNAL = 3      # External API calls
    SPAWN = 4         # Spawn child agents


# ============================================================================
# Limits & Boundaries
# ============================================================================

@dataclass
class AgentLimits:
    """Defines boundaries for agent operation.

    Attributes:
        max_actions: Maximum actions per task
        max_files_read: Maximum files to read
        max_files_write: Maximum files to write
        max_api_calls: Maximum external API calls
        max_spawn_agents: Maximum child agents to spawn
        allowed_paths: File paths agent can access (glob patterns)
        allowed_actions: Set of allowed ActionType values
        timeout_seconds: Maximum execution time
    """
    max_actions: int = 50
    max_files_read: int = 20
    max_files_write: int = 5
    max_api_calls: int = 10
    max_spawn_agents: int = MAX_PARALLEL_AGENTS
    allowed_paths: List[str] = field(default_factory=lambda: ["**/*"])
    allowed_actions: Set[ActionType] = field(default_factory=lambda: {ActionType.READ})
    timeout_seconds: float = 300.0

    def can_perform(self, action: ActionType) -> bool:
        """Check if action is allowed by limits."""
        return action in self.allowed_actions

    def is_path_allowed(self, path: str) -> bool:
        """Check if path is allowed (simple check, not full glob)."""
        if not self.allowed_paths:
            return False
        if "**/*" in self.allowed_paths:
            return True
        # Simple prefix matching
        for pattern in self.allowed_paths:
            if pattern.endswith("/**/*"):
                prefix = pattern[:-5]
                if path.startswith(prefix):
                    return True
            elif path == pattern:
                return True
        return False


# Default limits per autonomy level
DEFAULT_LIMITS: Final[Dict[AgentAutonomy, AgentLimits]] = {
    AgentAutonomy.SYNCHRONOUS: AgentLimits(
        max_actions=10,
        max_files_read=5,
        max_files_write=0,
        max_api_calls=0,
        max_spawn_agents=0,
        allowed_actions={ActionType.READ},
        timeout_seconds=30.0,
    ),
    AgentAutonomy.SUPERVISED: AgentLimits(
        max_actions=30,
        max_files_read=15,
        max_files_write=3,
        max_api_calls=5,
        max_spawn_agents=0,
        allowed_actions={ActionType.READ, ActionType.WRITE},
        timeout_seconds=120.0,
    ),
    AgentAutonomy.BOUNDED: AgentLimits(
        max_actions=100,
        max_files_read=50,
        max_files_write=10,
        max_api_calls=20,
        max_spawn_agents=2,
        allowed_actions={ActionType.READ, ActionType.WRITE, ActionType.EXTERNAL},
        timeout_seconds=300.0,
    ),
    AgentAutonomy.AUTONOMOUS: AgentLimits(
        max_actions=500,
        max_files_read=200,
        max_files_write=50,
        max_api_calls=100,
        max_spawn_agents=MAX_PARALLEL_AGENTS,
        allowed_actions=set(ActionType),  # All actions
        timeout_seconds=600.0,
    ),
}


# ============================================================================
# Action Tracking
# ============================================================================

@dataclass
class AgentAction:
    """Record of an action taken by an agent.

    Attributes:
        action_type: Type of action
        description: What was done
        target: Target of action (file path, API endpoint, etc.)
        approved: Whether action was approved (for SUPERVISED)
        timestamp: When action was taken
        success: Whether action succeeded
        result_summary: Brief result description
    """
    action_type: ActionType
    description: str
    target: str = ""
    approved: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    result_summary: str = ""


@dataclass
class ActionCounter:
    """Tracks action counts against limits.

    Attributes:
        actions: Total actions taken
        files_read: Files read
        files_written: Files written
        api_calls: External API calls
        agents_spawned: Child agents spawned
    """
    actions: int = 0
    files_read: int = 0
    files_written: int = 0
    api_calls: int = 0
    agents_spawned: int = 0

    def check_limit(self, limits: AgentLimits, action: ActionType) -> Optional[str]:
        """Check if action would exceed limits.

        Returns:
            Error message if limit exceeded, None if OK
        """
        if self.actions >= limits.max_actions:
            return f"Max actions ({limits.max_actions}) reached"

        if action == ActionType.READ and self.files_read >= limits.max_files_read:
            return f"Max files read ({limits.max_files_read}) reached"

        if action == ActionType.WRITE and self.files_written >= limits.max_files_write:
            return f"Max files write ({limits.max_files_write}) reached"

        if action == ActionType.EXTERNAL and self.api_calls >= limits.max_api_calls:
            return f"Max API calls ({limits.max_api_calls}) reached"

        if action == ActionType.SPAWN and self.agents_spawned >= limits.max_spawn_agents:
            return f"Max spawn agents ({limits.max_spawn_agents}) reached"

        return None

    def increment(self, action: ActionType) -> None:
        """Increment counter for action."""
        self.actions += 1

        if action == ActionType.READ:
            self.files_read += 1
        elif action == ActionType.WRITE:
            self.files_written += 1
        elif action == ActionType.EXTERNAL:
            self.api_calls += 1
        elif action == ActionType.SPAWN:
            self.agents_spawned += 1


# ============================================================================
# Typed Agents
# ============================================================================

class TypedAgent(Agent[Dict[str, Any]], ABC):
    """Base class for typed agents with autonomy levels.

    Extends the base Agent class with:
    - Autonomy level enforcement
    - Action limits
    - Approval integration

    Subclasses must implement:
    - autonomy_level: Class attribute for autonomy
    - _execute_typed(): Main execution logic
    """

    autonomy_level: AgentAutonomy = AgentAutonomy.SYNCHRONOUS
    agent_type: str = "typed"

    def __init__(
        self,
        config: AgentConfig = None,
        limits: AgentLimits = None,
        approval_callback: Optional[Callable[[str, ActionType], bool]] = None,
    ):
        """Initialize typed agent.

        Args:
            config: Agent configuration
            limits: Override default limits for this autonomy level
            approval_callback: Callback for action approval (SUPERVISED agents)
        """
        super().__init__(config)

        # Get limits for autonomy level, allow override
        self.limits = limits or DEFAULT_LIMITS.get(
            self.autonomy_level,
            DEFAULT_LIMITS[AgentAutonomy.SYNCHRONOUS]
        )

        self.approval_callback = approval_callback
        self.counter = ActionCounter()
        self.action_history: List[AgentAction] = []

    @abstractmethod
    async def _execute_typed(
        self,
        task: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the typed agent's main task.

        Subclasses implement their specific logic here.

        Args:
            task: Task description
            context: Additional context

        Returns:
            Task result dictionary
        """
        pass

    async def _execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with limit enforcement."""
        # Log autonomy level
        logger.info(
            f"Agent {self.agent_id} executing at autonomy level {self.autonomy_level.name}"
        )

        # Execute subclass implementation
        result = await self._execute_typed(task, context)

        # Add action summary to result
        result["_agent_meta"] = {
            "autonomy": self.autonomy_level.name,
            "actions_taken": self.counter.actions,
            "action_history": [
                {
                    "type": a.action_type.name,
                    "target": a.target,
                    "success": a.success,
                }
                for a in self.action_history[-10:]  # Last 10 actions
            ],
        }

        return result

    async def perform_action(
        self,
        action_type: ActionType,
        description: str,
        target: str = "",
        action_fn: Optional[Callable[[], Any]] = None,
    ) -> Optional[Any]:
        """Perform an action with limit and approval checking.

        Args:
            action_type: Type of action to perform
            description: What the action does
            target: Target of action (file path, API, etc.)
            action_fn: Function to execute if approved

        Returns:
            Result of action_fn if performed, None if blocked

        Raises:
            NonRetryableError: If limits exceeded
        """
        # Check if action type is allowed
        if not self.limits.can_perform(action_type):
            logger.warning(
                f"Agent {self.agent_id}: Action {action_type.name} not allowed at autonomy level {self.autonomy_level.name}"
            )
            return None

        # Check limits
        error = self.counter.check_limit(self.limits, action_type)
        if error:
            raise NonRetryableError(error)

        # Check approval for SUPERVISED agents
        approved = True
        if self.autonomy_level == AgentAutonomy.SUPERVISED:
            if self.approval_callback:
                approved = self.approval_callback(description, action_type)
            else:
                # No callback = deny by default for supervised
                logger.warning(
                    f"Agent {self.agent_id}: No approval callback for SUPERVISED agent"
                )
                approved = False

        # Record action
        action = AgentAction(
            action_type=action_type,
            description=description,
            target=target,
            approved=approved,
        )

        if not approved:
            action.success = False
            action.result_summary = "Approval denied"
            self.action_history.append(action)
            logger.info(f"Agent {self.agent_id}: Action denied - {description}")
            return None

        # Execute action
        result = None
        try:
            if action_fn:
                result = action_fn()
            action.success = True
            action.result_summary = "Success"
            self.counter.increment(action_type)
        except Exception as e:
            action.success = False
            action.result_summary = str(e)
            logger.error(f"Agent {self.agent_id}: Action failed - {e}")

        self.action_history.append(action)
        return result

    async def read_file(self, path: str) -> Optional[str]:
        """Read a file with limit checking.

        Args:
            path: File path to read

        Returns:
            File contents if allowed, None otherwise
        """
        if not self.limits.is_path_allowed(path):
            logger.warning(f"Agent {self.agent_id}: Path not allowed: {path}")
            return None

        def do_read():
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

        result = await self.perform_action(
            ActionType.READ,
            f"Read file: {path}",
            target=path,
            action_fn=do_read,
        )

        if result is not None:
            self.track_file_read(path)

        return result

    async def write_file(self, path: str, content: str) -> bool:
        """Write a file with limit checking.

        Args:
            path: File path to write
            content: Content to write

        Returns:
            True if written, False otherwise
        """
        if not self.limits.is_path_allowed(path):
            logger.warning(f"Agent {self.agent_id}: Path not allowed: {path}")
            return False

        def do_write():
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        result = await self.perform_action(
            ActionType.WRITE,
            f"Write file: {path}",
            target=path,
            action_fn=do_write,
        )

        if result:
            self.track_file_modified(path)

        return result is True


# ============================================================================
# Concrete Agent Types
# ============================================================================

class SynchronousAgent(TypedAgent):
    """Synchronous agent - simple request-response.

    No autonomy. Executes single tasks and returns results.
    Cannot spawn child agents or perform write operations.

    Use for:
    - Simple queries
    - Read-only exploration
    - Quick lookups
    """

    autonomy_level = AgentAutonomy.SYNCHRONOUS
    agent_type = "synchronous"

    async def _execute_typed(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Default synchronous execution - override in subclass."""
        await self.report_progress(1, "Processing request")
        return {"task": task, "status": "completed"}

    def _get_step_count(self) -> int:
        return 2


class SupervisedAgent(TypedAgent):
    """Supervised agent - requires approval for actions.

    Actions are gated by approval callback. Good for:
    - File modifications with human oversight
    - API calls requiring confirmation
    - Learning agent preferences

    Each write action triggers approval check.
    """

    autonomy_level = AgentAutonomy.SUPERVISED
    agent_type = "supervised"

    async def _execute_typed(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Default supervised execution - override in subclass."""
        await self.report_progress(1, "Awaiting approval")
        return {"task": task, "status": "awaiting_approval"}

    def _get_step_count(self) -> int:
        return 3


class BoundedAgent(TypedAgent):
    """Bounded agent - autonomous within defined limits.

    Operates autonomously but respects hard limits on:
    - Number of files read/written
    - API calls made
    - Child agents spawned

    Good for:
    - Code exploration tasks
    - Automated testing
    - Batch processing within scope
    """

    autonomy_level = AgentAutonomy.BOUNDED
    agent_type = "bounded"

    async def _execute_typed(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Default bounded execution - override in subclass."""
        await self.report_progress(1, "Executing within bounds")
        return {"task": task, "status": "bounded_execution"}

    def _get_step_count(self) -> int:
        return 5


class AutonomousAgent(TypedAgent):
    """Autonomous agent - full autonomy with highest trust.

    Can perform any action within generous limits.
    Requires highest trust level to deploy.

    Good for:
    - Complex multi-step tasks
    - Full project refactoring
    - Automated deployments (with caution)

    WARNING: Only deploy with full user consent and trust.
    """

    autonomy_level = AgentAutonomy.AUTONOMOUS
    agent_type = "autonomous"

    async def _execute_typed(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Default autonomous execution - override in subclass."""
        await self.report_progress(1, "Executing autonomously")
        return {"task": task, "status": "autonomous_execution"}

    def _get_step_count(self) -> int:
        return 10


# ============================================================================
# Agent Factory
# ============================================================================

class AgentFactory:
    """Factory for creating typed agents.

    Centralizes agent creation with proper configuration.

    Example:
        >>> factory = AgentFactory()
        >>> agent = factory.create(
        ...     AgentAutonomy.SUPERVISED,
        ...     approval_callback=lambda d, a: input(f"Approve {d}? ") == "y"
        ... )
    """

    def __init__(
        self,
        default_approval_callback: Optional[Callable[[str, ActionType], bool]] = None,
    ):
        """Initialize factory.

        Args:
            default_approval_callback: Default approval callback for supervised agents
        """
        self.default_approval_callback = default_approval_callback

        # Registry of agent classes
        self._registry: Dict[AgentAutonomy, type] = {
            AgentAutonomy.SYNCHRONOUS: SynchronousAgent,
            AgentAutonomy.SUPERVISED: SupervisedAgent,
            AgentAutonomy.BOUNDED: BoundedAgent,
            AgentAutonomy.AUTONOMOUS: AutonomousAgent,
        }

    def register(self, autonomy: AgentAutonomy, agent_class: type) -> None:
        """Register a custom agent class for an autonomy level.

        Args:
            autonomy: Autonomy level
            agent_class: Agent class (must extend TypedAgent)
        """
        if not issubclass(agent_class, TypedAgent):
            raise ValueError(f"Agent class must extend TypedAgent")
        self._registry[autonomy] = agent_class

    def create(
        self,
        autonomy: AgentAutonomy,
        config: AgentConfig = None,
        limits: AgentLimits = None,
        approval_callback: Optional[Callable[[str, ActionType], bool]] = None,
    ) -> TypedAgent:
        """Create an agent with specified autonomy level.

        Args:
            autonomy: Desired autonomy level
            config: Optional config override
            limits: Optional limits override
            approval_callback: Optional approval callback (uses default if not provided)

        Returns:
            Configured TypedAgent instance
        """
        agent_class = self._registry.get(autonomy)
        if agent_class is None:
            raise ValueError(f"No agent registered for autonomy level {autonomy}")

        # Use provided or default approval callback
        callback = approval_callback or self.default_approval_callback

        return agent_class(
            config=config,
            limits=limits,
            approval_callback=callback,
        )

    def create_for_burnout(
        self,
        burnout_level: str,
        base_autonomy: AgentAutonomy = AgentAutonomy.BOUNDED,
    ) -> TypedAgent:
        """Create an agent with autonomy adjusted for burnout level.

        ORANGE/RED burnout reduces maximum autonomy.

        Args:
            burnout_level: Current burnout level
            base_autonomy: Requested autonomy level

        Returns:
            Agent with appropriate autonomy
        """
        if burnout_level == "RED":
            # RED = only synchronous allowed
            return self.create(AgentAutonomy.SYNCHRONOUS)
        elif burnout_level == "ORANGE":
            # ORANGE = max supervised
            effective = min(base_autonomy, AgentAutonomy.SUPERVISED)
            return self.create(AgentAutonomy(effective))
        else:
            return self.create(base_autonomy)


# Module-level factory
_factory: Optional[AgentFactory] = None


def get_factory() -> AgentFactory:
    """Get or create the singleton agent factory."""
    global _factory
    if _factory is None:
        _factory = AgentFactory()
    return _factory


__all__ = [
    # Enums
    "AgentAutonomy",
    "ActionType",
    # Data classes
    "AgentLimits",
    "AgentAction",
    "ActionCounter",
    # Agents
    "TypedAgent",
    "SynchronousAgent",
    "SupervisedAgent",
    "BoundedAgent",
    "AutonomousAgent",
    # Factory
    "AgentFactory",
    "get_factory",
    # Constants
    "DEFAULT_LIMITS",
    "MAX_PARALLEL_AGENTS",
    "MAX_CHAIN_DEPTH",
]
