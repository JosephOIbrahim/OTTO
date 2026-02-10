"""
Progress Tracking System
========================

Real-time progress visibility for agent execution.

ADHD-Critical: Progress must ALWAYS be visible. No silent background work.

Determinism:
- Fixed progress levels
- Deterministic state transitions
- Bounded history size
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProgressLevel(Enum):
    """Granularity of progress updates."""
    MINIMAL = "minimal"      # Just start/complete
    STANDARD = "standard"    # Key milestones
    DETAILED = "detailed"    # Every step
    VERBOSE = "verbose"      # Sub-step level


@dataclass
class ProgressEvent:
    """A single progress event."""
    agent_id: str
    agent_type: str
    event_type: str  # "start", "step", "milestone", "complete", "error", "warning"
    message: str
    current_step: int = 0
    total_steps: int = 0
    percentage: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "event_type": self.event_type,
            "message": self.message,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "percentage": self.percentage,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def format_terminal(self) -> str:
        """Format for terminal display."""
        if self.event_type == "start":
            return f"[{self.agent_type}] Starting: {self.message}"
        elif self.event_type == "complete":
            return f"[{self.agent_type}] Completed: {self.message}"
        elif self.event_type == "error":
            return f"[{self.agent_type}] ERROR: {self.message}"
        elif self.event_type == "warning":
            return f"[{self.agent_type}] Warning: {self.message}"
        else:
            bar = self._progress_bar()
            return f"[{self.agent_type}] {bar} {self.message}"

    def _progress_bar(self, width: int = 20) -> str:
        """Generate ASCII progress bar."""
        filled = int(width * self.percentage / 100)
        bar = "#" * filled + "-" * (width - filled)
        return f"[{bar}] {self.percentage:.0f}%"


@dataclass
class AgentTracker:
    """Tracks a single agent's progress."""
    agent_id: str
    agent_type: str
    task: str
    start_time: datetime
    total_steps: int
    current_step: int = 0
    status: str = "running"  # running, completed, failed, aborted
    end_time: Optional[datetime] = None
    events: Deque[ProgressEvent] = field(default_factory=lambda: deque(maxlen=100))

    def get_duration(self) -> float:
        """Get duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    def get_eta_seconds(self) -> Optional[float]:
        """Estimate time remaining based on progress."""
        if self.current_step == 0:
            return None

        elapsed = self.get_duration()
        rate = self.current_step / elapsed if elapsed > 0 else 0
        remaining_steps = self.total_steps - self.current_step

        if rate > 0:
            return remaining_steps / rate
        return None


class ProgressTracker:
    """
    Central progress tracking for all agents.

    Features:
    - Real-time progress events
    - Aggregated view of all running agents
    - History with bounded size
    - Callbacks for progress updates
    - Terminal-friendly formatting

    Usage:
        tracker = ProgressTracker()

        # Register callback
        tracker.on_progress(lambda e: print(e.format_terminal()))

        # Track agents
        tracker.start_agent("agent-123", "planner", "Plan implementation", 5)
        tracker.update_progress("agent-123", 1, "Analyzing requirements")
        tracker.complete_agent("agent-123", success=True)
    """

    MAX_HISTORY = 1000
    MAX_ACTIVE_AGENTS = 10

    def __init__(self, level: ProgressLevel = ProgressLevel.STANDARD):
        self.level = level
        self._agents: Dict[str, AgentTracker] = {}
        self._history: Deque[ProgressEvent] = deque(maxlen=self.MAX_HISTORY)
        self._callbacks: List[Callable[[ProgressEvent], None]] = []
        self._lock = asyncio.Lock()

    def start_agent(
        self,
        agent_id: str,
        agent_type: str,
        task: str,
        total_steps: int,
    ) -> AgentTracker:
        """Start tracking a new agent."""
        if len(self._agents) >= self.MAX_ACTIVE_AGENTS:
            # Remove oldest completed agent
            completed = [aid for aid, a in self._agents.items() if a.status != "running"]
            if completed:
                del self._agents[completed[0]]
            else:
                logger.warning("Max active agents reached")

        tracker = AgentTracker(
            agent_id=agent_id,
            agent_type=agent_type,
            task=task,
            start_time=datetime.now(),
            total_steps=total_steps,
        )
        self._agents[agent_id] = tracker

        # Emit start event
        event = ProgressEvent(
            agent_id=agent_id,
            agent_type=agent_type,
            event_type="start",
            message=task,
            total_steps=total_steps,
        )
        self._emit(event)
        tracker.events.append(event)

        return tracker

    def update_progress(
        self,
        agent_id: str,
        step: int,
        message: str,
        metadata: Dict[str, Any] = None,
    ):
        """Update agent progress."""
        tracker = self._agents.get(agent_id)
        if not tracker:
            logger.warning(f"Unknown agent: {agent_id}")
            return

        tracker.current_step = step
        percentage = (step / tracker.total_steps * 100) if tracker.total_steps > 0 else 0

        event = ProgressEvent(
            agent_id=agent_id,
            agent_type=tracker.agent_type,
            event_type="step",
            message=message,
            current_step=step,
            total_steps=tracker.total_steps,
            percentage=percentage,
            metadata=metadata or {},
        )

        # Only emit based on level
        if self._should_emit(event):
            self._emit(event)

        tracker.events.append(event)

    def milestone(
        self,
        agent_id: str,
        message: str,
        metadata: Dict[str, Any] = None,
    ):
        """Report a milestone (always emitted)."""
        tracker = self._agents.get(agent_id)
        if not tracker:
            return

        percentage = (tracker.current_step / tracker.total_steps * 100) if tracker.total_steps > 0 else 0

        event = ProgressEvent(
            agent_id=agent_id,
            agent_type=tracker.agent_type,
            event_type="milestone",
            message=message,
            current_step=tracker.current_step,
            total_steps=tracker.total_steps,
            percentage=percentage,
            metadata=metadata or {},
        )
        self._emit(event)
        tracker.events.append(event)

    def warning(self, agent_id: str, message: str):
        """Report a warning."""
        tracker = self._agents.get(agent_id)
        if not tracker:
            return

        event = ProgressEvent(
            agent_id=agent_id,
            agent_type=tracker.agent_type,
            event_type="warning",
            message=message,
            current_step=tracker.current_step,
            total_steps=tracker.total_steps,
        )
        self._emit(event)
        tracker.events.append(event)

    def complete_agent(
        self,
        agent_id: str,
        success: bool,
        message: str = None,
        result_summary: Dict[str, Any] = None,
    ):
        """Mark agent as completed."""
        tracker = self._agents.get(agent_id)
        if not tracker:
            return

        tracker.status = "completed" if success else "failed"
        tracker.end_time = datetime.now()
        tracker.current_step = tracker.total_steps

        event_type = "complete" if success else "error"
        default_msg = "Completed successfully" if success else "Failed"

        event = ProgressEvent(
            agent_id=agent_id,
            agent_type=tracker.agent_type,
            event_type=event_type,
            message=message or default_msg,
            current_step=tracker.total_steps,
            total_steps=tracker.total_steps,
            percentage=100.0 if success else tracker.current_step / tracker.total_steps * 100,
            metadata=result_summary or {},
        )
        self._emit(event)
        tracker.events.append(event)

    def abort_agent(self, agent_id: str, reason: str):
        """Mark agent as aborted."""
        tracker = self._agents.get(agent_id)
        if not tracker:
            return

        tracker.status = "aborted"
        tracker.end_time = datetime.now()

        event = ProgressEvent(
            agent_id=agent_id,
            agent_type=tracker.agent_type,
            event_type="error",
            message=f"Aborted: {reason}",
            current_step=tracker.current_step,
            total_steps=tracker.total_steps,
        )
        self._emit(event)
        tracker.events.append(event)

    def _should_emit(self, event: ProgressEvent) -> bool:
        """Check if event should be emitted based on level."""
        if self.level == ProgressLevel.VERBOSE:
            return True
        if self.level == ProgressLevel.DETAILED:
            return True
        if self.level == ProgressLevel.STANDARD:
            # Emit every ~25% or milestones
            tracker = self._agents.get(event.agent_id)
            if tracker:
                prev_quarter = int((tracker.current_step - 1) / tracker.total_steps * 4) if tracker.total_steps > 0 else 0
                curr_quarter = int(event.current_step / tracker.total_steps * 4) if tracker.total_steps > 0 else 0
                return curr_quarter > prev_quarter
            return False
        # MINIMAL - only start/complete (handled separately)
        return False

    def _emit(self, event: ProgressEvent):
        """Emit event to callbacks and history."""
        self._history.append(event)

        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def on_progress(self, callback: Callable[[ProgressEvent], None]):
        """Register a progress callback."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[ProgressEvent], None]):
        """Remove a progress callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_agent(self, agent_id: str) -> Optional[AgentTracker]:
        """Get tracker for specific agent."""
        return self._agents.get(agent_id)

    def get_running_agents(self) -> List[AgentTracker]:
        """Get all running agents."""
        return [a for a in self._agents.values() if a.status == "running"]

    def get_all_agents(self) -> List[AgentTracker]:
        """Get all tracked agents."""
        return list(self._agents.values())

    def get_recent_events(self, count: int = 10) -> List[ProgressEvent]:
        """Get most recent events."""
        return list(self._history)[-count:]

    # =========================================================================
    # Display Methods
    # =========================================================================

    def format_status(self) -> str:
        """Format current status for terminal display."""
        running = self.get_running_agents()
        if not running:
            return "No agents running"

        lines = [f"Active agents: {len(running)}"]
        for agent in running:
            percentage = (agent.current_step / agent.total_steps * 100) if agent.total_steps > 0 else 0
            bar = self._progress_bar(percentage)
            eta = agent.get_eta_seconds()
            eta_str = f" (ETA: {eta:.0f}s)" if eta else ""
            lines.append(f"  [{agent.agent_type}] {bar} {agent.task[:30]}...{eta_str}")

        return "\n".join(lines)

    def format_summary(self) -> str:
        """Format summary of all agents."""
        all_agents = self.get_all_agents()
        if not all_agents:
            return "No agents tracked"

        running = [a for a in all_agents if a.status == "running"]
        completed = [a for a in all_agents if a.status == "completed"]
        failed = [a for a in all_agents if a.status == "failed"]

        lines = [
            f"Agents: {len(running)} running, {len(completed)} completed, {len(failed)} failed"
        ]

        for agent in running:
            lines.append(f"  [running] {agent.agent_type}: {agent.task[:40]}...")

        return "\n".join(lines)

    @staticmethod
    def _progress_bar(percentage: float, width: int = 15) -> str:
        """Generate ASCII progress bar."""
        filled = int(width * percentage / 100)
        bar = "#" * filled + "-" * (width - filled)
        return f"[{bar}] {percentage:.0f}%"

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup_completed(self, max_age_seconds: float = 3600.0):
        """Remove old completed agents."""
        now = datetime.now()
        to_remove = []

        for agent_id, tracker in self._agents.items():
            if tracker.status in ("completed", "failed", "aborted"):
                if tracker.end_time:
                    age = (now - tracker.end_time).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(agent_id)

        for agent_id in to_remove:
            del self._agents[agent_id]


# Global tracker instance (optional singleton pattern)
_global_tracker: Optional[ProgressTracker] = None


def get_progress_tracker() -> ProgressTracker:
    """Get global progress tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ProgressTracker()
    return _global_tracker


__all__ = [
    "ProgressTracker",
    "ProgressEvent",
    "ProgressLevel",
    "AgentTracker",
    "get_progress_tracker",
]
