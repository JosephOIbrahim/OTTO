"""
Agent Base Classes
==================

Foundation for all OTTO agents with progress tracking, error handling,
and cognitive state awareness.

ThinkingMachines [He2025] Compliance:
- Fixed execution phases
- State snapshot before execution
- Deterministic error classification
"""

import asyncio
import logging
import time
import uuid
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Callable

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent lifecycle states."""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class AgentError(Exception):
    """Base class for agent errors."""
    pass


class RetryableError(AgentError):
    """Error that can be retried."""
    def __init__(self, message: str, retry_after: float = 1.0):
        super().__init__(message)
        self.retry_after = retry_after


class NonRetryableError(AgentError):
    """Error that should not be retried."""
    pass


@dataclass
class AgentConfig:
    """Configuration for agent execution."""
    agent_type: str
    max_turns: int = 10
    timeout_seconds: float = 300.0
    max_retries: int = 3
    retry_delay: float = 1.0

    # Cognitive state propagated from parent
    parent_session_id: Optional[str] = None
    burnout_level: str = "GREEN"
    energy_level: str = "medium"
    depth: int = 0  # Agent chain depth

    # Safety limits
    max_depth: int = 3

    def should_reduce_scope(self) -> bool:
        """Check if we should reduce work scope due to cognitive state."""
        return (
            self.burnout_level in ("ORANGE", "RED") or
            self.energy_level in ("low", "depleted")
        )

    def effective_max_turns(self) -> int:
        """Get max turns adjusted for cognitive state."""
        if self.burnout_level == "RED":
            return min(3, self.max_turns)
        if self.burnout_level == "ORANGE" or self.energy_level == "depleted":
            return min(5, self.max_turns)
        if self.energy_level == "low":
            return min(self.max_turns, 7)
        return self.max_turns

    def can_spawn_child(self) -> bool:
        """Check if this agent can spawn child agents."""
        return (
            self.depth < self.max_depth and
            self.burnout_level not in ("ORANGE", "RED")
        )


@dataclass
class AgentProgress:
    """Progress update from agent."""
    agent_id: str
    current_step: int
    total_steps: int
    step_description: str
    percentage: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "step_description": self.step_description,
            "percentage": self.percentage,
            "timestamp": self.timestamp.isoformat(),
        }

    def format_display(self) -> str:
        """Format for terminal display."""
        bar_width = 20
        filled = int(bar_width * self.percentage / 100)
        bar = "#" * filled + "-" * (bar_width - filled)
        return f"[{bar}] {self.percentage:.0f}% - Step {self.current_step}/{self.total_steps}: {self.step_description}"


@dataclass
class AgentResult:
    """Result from agent execution."""
    agent_id: str
    agent_type: str
    success: bool
    result: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    turn_count: int = 0
    retries_used: int = 0
    checksum: str = ""

    def __post_init__(self):
        """Generate deterministic checksum."""
        data = f"{self.agent_id}|{self.success}|{len(self.errors)}|{self.duration_seconds}"
        self.checksum = hashlib.md5(data.encode()).hexdigest()[:8]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "success": self.success,
            "result": self.result,
            "errors": self.errors,
            "warnings": self.warnings,
            "files_read": self.files_read,
            "files_modified": self.files_modified,
            "duration_seconds": self.duration_seconds,
            "turn_count": self.turn_count,
            "retries_used": self.retries_used,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentResult":
        return cls(
            agent_id=data["agent_id"],
            agent_type=data["agent_type"],
            success=data["success"],
            result=data["result"],
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            files_read=data.get("files_read", []),
            files_modified=data.get("files_modified", []),
            duration_seconds=data.get("duration_seconds", 0.0),
            turn_count=data.get("turn_count", 0),
            retries_used=data.get("retries_used", 0),
        )


ResultT = TypeVar("ResultT")


class Agent(ABC, Generic[ResultT]):
    """
    Base class for all OTTO agents.

    Agents are specialized workers that:
    - Execute specific task types
    - Track and report progress
    - Handle errors with retry logic
    - Respect cognitive state limits

    Subclasses must implement:
    - _execute(): Main execution logic
    - _get_step_count(): Return total steps for progress
    - agent_type: Class attribute for agent type name

    Example:
        class MyAgent(Agent[Dict[str, Any]]):
            agent_type = "my_agent"

            async def _execute(self, task: str, context: Dict) -> Dict[str, Any]:
                await self.report_progress(1, "Starting task")
                result = await do_work()
                await self.report_progress(2, "Completed")
                return result

            def _get_step_count(self) -> int:
                return 2
    """

    agent_type: str = "base"  # Override in subclass

    def __init__(self, config: AgentConfig = None):
        self.config = config or AgentConfig(agent_type=self.agent_type)
        self.agent_id = f"{self.agent_type}-{uuid.uuid4().hex[:8]}"
        self.state = AgentState.CREATED
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.turn_count = 0
        self.retries_used = 0
        self.current_step = 0

        # Progress callbacks
        self._progress_callbacks: List[Callable[[AgentProgress], None]] = []

        # Files tracked during execution
        self._files_read: List[str] = []
        self._files_modified: List[str] = []
        self._errors: List[str] = []
        self._warnings: List[str] = []

    @abstractmethod
    async def _execute(self, task: str, context: Dict[str, Any]) -> ResultT:
        """
        Execute the agent's main task.

        Subclasses implement their specific logic here.
        Call report_progress() to update progress.

        Args:
            task: Task description
            context: Additional context (files, scope, etc.)

        Returns:
            Task-specific result
        """
        pass

    @abstractmethod
    def _get_step_count(self) -> int:
        """Return total number of steps for progress tracking."""
        pass

    async def run(self, task: str, context: Dict[str, Any] = None) -> AgentResult:
        """
        Run the agent with full lifecycle management.

        Handles:
        - State transitions
        - Progress tracking
        - Error handling with retries
        - Timeout enforcement
        - Result packaging

        Args:
            task: Task description
            context: Additional context

        Returns:
            AgentResult with success/failure and all collected data
        """
        context = context or {}
        self.state = AgentState.INITIALIZING
        self.start_time = time.time()

        # Log start
        logger.info(f"Agent {self.agent_id} starting: {task[:50]}...")

        # Report initial progress
        await self.report_progress(0, "Initializing")

        result = None
        try:
            self.state = AgentState.RUNNING

            # Execute with timeout and retry
            result = await self._execute_with_retry(task, context)

            self.state = AgentState.COMPLETED
            success = True

        except asyncio.CancelledError:
            self.state = AgentState.ABORTED
            self._errors.append("Agent execution cancelled")
            success = False
            result = {"aborted": True}

        except NonRetryableError as e:
            self.state = AgentState.FAILED
            self._errors.append(str(e))
            success = False
            result = {"error": str(e)}

        except Exception as e:
            self.state = AgentState.FAILED
            self._errors.append(f"Unexpected error: {e}")
            logger.exception(f"Agent {self.agent_id} failed: {e}")
            success = False
            result = {"error": str(e)}

        self.end_time = time.time()
        duration = self.end_time - self.start_time

        # Build result - convert to dict if result has to_dict method
        if isinstance(result, dict):
            result_dict = result
        elif hasattr(result, 'to_dict'):
            result_dict = result.to_dict()
        else:
            result_dict = {"value": result}

        return AgentResult(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            success=success,
            result=result_dict,
            errors=self._errors.copy(),
            warnings=self._warnings.copy(),
            files_read=self._files_read.copy(),
            files_modified=self._files_modified.copy(),
            duration_seconds=duration,
            turn_count=self.turn_count,
            retries_used=self.retries_used,
        )

    async def _execute_with_retry(
        self, task: str, context: Dict[str, Any]
    ) -> ResultT:
        """Execute with timeout and retry logic."""
        max_retries = self.config.max_retries
        timeout = self.config.timeout_seconds

        for attempt in range(max_retries + 1):
            try:
                # Enforce timeout
                result = await asyncio.wait_for(
                    self._execute(task, context),
                    timeout=timeout
                )
                return result

            except asyncio.TimeoutError:
                self._errors.append(f"Timeout after {timeout}s (attempt {attempt + 1})")
                if attempt < max_retries:
                    self.retries_used += 1
                    logger.warning(f"Agent {self.agent_id} timeout, retrying...")
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise NonRetryableError(f"Timeout after {max_retries + 1} attempts")

            except RetryableError as e:
                self._warnings.append(f"Retryable error: {e}")
                if attempt < max_retries:
                    self.retries_used += 1
                    logger.warning(f"Agent {self.agent_id} retryable error, waiting {e.retry_after}s...")
                    await asyncio.sleep(e.retry_after)
                else:
                    raise NonRetryableError(f"Failed after {max_retries + 1} attempts: {e}")

    async def report_progress(self, step: int, description: str):
        """
        Report progress update.

        Call this from _execute() to report progress.

        Args:
            step: Current step number (0-indexed)
            description: What's happening now
        """
        self.current_step = step
        total = self._get_step_count()
        percentage = (step / total * 100) if total > 0 else 0

        progress = AgentProgress(
            agent_id=self.agent_id,
            current_step=step,
            total_steps=total,
            step_description=description,
            percentage=percentage,
        )

        # Notify callbacks
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

        logger.debug(f"Agent {self.agent_id}: {progress.format_display()}")

    def on_progress(self, callback: Callable[[AgentProgress], None]):
        """Register a progress callback."""
        self._progress_callbacks.append(callback)

    def track_file_read(self, path: str):
        """Track a file that was read."""
        if path not in self._files_read:
            self._files_read.append(path)

    def track_file_modified(self, path: str):
        """Track a file that was modified."""
        if path not in self._files_modified:
            self._files_modified.append(path)

    def add_warning(self, warning: str):
        """Add a warning message."""
        self._warnings.append(warning)

    def increment_turn(self):
        """Increment turn counter, check limits."""
        self.turn_count += 1
        max_turns = self.config.effective_max_turns()

        if self.turn_count >= max_turns:
            raise NonRetryableError(f"Max turns ({max_turns}) reached")

    def abort(self):
        """Abort agent execution."""
        self.state = AgentState.ABORTED
        # The asyncio.CancelledError will be raised in run()


@dataclass
class AgentChain:
    """
    Chain of agents for complex multi-step tasks.

    Manages parent-child agent relationships and state propagation.
    """
    parent_agent_id: str
    chain_depth: int
    max_depth: int = 3
    agents: List[Agent] = field(default_factory=list)

    def can_add_agent(self) -> bool:
        """Check if we can add another agent to chain."""
        return self.chain_depth < self.max_depth

    def create_child_config(self, parent_config: AgentConfig, agent_type: str) -> AgentConfig:
        """Create config for child agent with propagated state."""
        return AgentConfig(
            agent_type=agent_type,
            max_turns=max(3, parent_config.max_turns // 2),
            timeout_seconds=parent_config.timeout_seconds / 2,
            parent_session_id=parent_config.parent_session_id,
            burnout_level=parent_config.burnout_level,
            energy_level=parent_config.energy_level,
            depth=parent_config.depth + 1,
            max_depth=parent_config.max_depth,
        )


__all__ = [
    "Agent",
    "AgentConfig",
    "AgentResult",
    "AgentProgress",
    "AgentState",
    "AgentError",
    "RetryableError",
    "NonRetryableError",
    "AgentChain",
]
