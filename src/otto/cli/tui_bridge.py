"""
TUI Bridge
==========

Connects the agent progress tracking system to the TUI dashboard.

This module provides real-time updates from agent execution to the
enhanced TUI dashboard via state files.

Determinism:
- Fixed update frequency (max 10 Hz)
- Deterministic state serialization
- Bounded history size

Usage:
    from otto.cli.tui_bridge import TUIBridge, get_tui_bridge

    bridge = get_tui_bridge()
    bridge.register_with_tracker(progress_tracker)

    # Progress will automatically flow to TUI
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

# State file paths
STATE_DIR = Path.home() / ".orchestra" / "state"
AGENT_STATE_FILE = STATE_DIR / "agent_state.json"
COGNITIVE_STATE_FILE = STATE_DIR / "cognitive_state.json"

# Update rate limiting (ThinkingMachines compliant - bounded frequency)
MIN_UPDATE_INTERVAL_MS = 100  # Max 10 Hz


@dataclass
class AgentStateEntry:
    """State entry for a single agent."""
    agent_id: str
    agent_type: str
    task: str
    status: str  # running, completed, failed, aborted
    current_step: int = 0
    total_steps: int = 1
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_seconds: float = 0.0
    last_message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "task": self.task,
            "status": self.status,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "last_message": self.last_message,
            "error": self.error,
        }


@dataclass
class TUIState:
    """Complete TUI state for serialization."""
    agents: List[AgentStateEntry] = field(default_factory=list)
    last_update: float = field(default_factory=time.time)
    total_agents_run: int = 0
    total_completed: int = 0
    total_failed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agents": [a.to_dict() for a in self.agents],
            "last_update": self.last_update,
            "total_agents_run": self.total_agents_run,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
        }


class TUIBridge:
    """
    Bridge between agent progress tracking and TUI dashboard.

    Provides:
    - Automatic state file updates from ProgressTracker events
    - Rate-limited file writes (max 10 Hz)
    - Agent state aggregation
    - History management (bounded size)

    ThinkingMachines Compliance:
    - FIXED update frequency bounds
    - DETERMINISTIC serialization
    - BOUNDED history (max 50 agents)
    """

    MAX_HISTORY_SIZE = 50
    MAX_ACTIVE_DISPLAY = 10

    def __init__(self, state_dir: Path = None):
        """
        Initialize TUI bridge.

        Args:
            state_dir: Directory for state files
        """
        self.state_dir = state_dir or STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.state = TUIState()
        self._agent_map: Dict[str, AgentStateEntry] = {}
        self._last_write_time: float = 0.0
        self._pending_write: bool = False

    def register_with_tracker(self, tracker) -> None:
        """
        Register with a ProgressTracker to receive events.

        Args:
            tracker: ProgressTracker instance from otto.agents.progress
        """
        tracker.on_progress(self._handle_progress_event)
        logger.info("TUIBridge registered with ProgressTracker")

    def _handle_progress_event(self, event) -> None:
        """
        Handle progress event from tracker.

        Args:
            event: ProgressEvent from otto.agents.progress
        """
        agent_id = event.agent_id

        if event.event_type == "start":
            # New agent started
            entry = AgentStateEntry(
                agent_id=agent_id,
                agent_type=event.agent_type,
                task=event.message[:100],
                status="running",
                total_steps=event.total_steps or 1,
                start_time=time.time(),
            )
            self._agent_map[agent_id] = entry
            self.state.total_agents_run += 1

        elif agent_id in self._agent_map:
            entry = self._agent_map[agent_id]

            if event.event_type == "step":
                entry.current_step = event.current_step
                entry.last_message = event.message
                entry.duration_seconds = time.time() - entry.start_time

            elif event.event_type == "milestone":
                entry.last_message = f"[MILESTONE] {event.message}"

            elif event.event_type == "complete":
                entry.status = "completed"
                entry.end_time = time.time()
                entry.duration_seconds = entry.end_time - entry.start_time
                entry.current_step = entry.total_steps
                self.state.total_completed += 1

            elif event.event_type == "error":
                entry.status = "failed"
                entry.error = event.message
                entry.end_time = time.time()
                entry.duration_seconds = entry.end_time - entry.start_time
                self.state.total_failed += 1

            elif event.event_type == "warning":
                entry.last_message = f"[WARNING] {event.message}"

        # Update state and write
        self._update_state()
        self._write_state_throttled()

    def _update_state(self) -> None:
        """Update state from agent map."""
        # Sort agents: running first, then by start time
        all_agents = list(self._agent_map.values())
        running = [a for a in all_agents if a.status == "running"]
        completed = [a for a in all_agents if a.status != "running"]

        # Sort running by start time (newest first)
        running.sort(key=lambda a: a.start_time, reverse=True)

        # Sort completed by end time (newest first)
        completed.sort(key=lambda a: a.end_time or 0, reverse=True)

        # Combine with running first, limit to max display
        self.state.agents = (running + completed)[:self.MAX_ACTIVE_DISPLAY]
        self.state.last_update = time.time()

        # Cleanup old completed agents from map
        if len(self._agent_map) > self.MAX_HISTORY_SIZE:
            old_completed = [
                a for a in completed
                if a.agent_id not in [r.agent_id for r in running]
            ]
            for agent in old_completed[self.MAX_HISTORY_SIZE // 2:]:
                self._agent_map.pop(agent.agent_id, None)

    def _write_state_throttled(self) -> None:
        """Write state to file with rate limiting."""
        now = time.time()
        elapsed_ms = (now - self._last_write_time) * 1000

        if elapsed_ms >= MIN_UPDATE_INTERVAL_MS:
            self._write_state()
            self._last_write_time = now
            self._pending_write = False
        else:
            self._pending_write = True

    def _write_state(self) -> None:
        """Write state to file (atomic write)."""
        try:
            state_file = self.state_dir / "agent_state.json"
            temp_file = state_file.with_suffix(".tmp")

            with open(temp_file, "w") as f:
                json.dump(self.state.to_dict(), f, indent=2)

            temp_file.replace(state_file)
            logger.debug(f"TUI state written: {len(self.state.agents)} agents")

        except Exception as e:
            logger.error(f"Failed to write TUI state: {e}")

    def flush(self) -> None:
        """Force write any pending state."""
        if self._pending_write:
            self._write_state()
            self._pending_write = False

    def add_agent(
        self,
        agent_id: str,
        agent_type: str,
        task: str,
        total_steps: int = 1,
    ) -> None:
        """
        Manually add an agent (for non-tracker usage).

        Args:
            agent_id: Unique agent identifier
            agent_type: Type of agent
            task: Task description
            total_steps: Total number of steps
        """
        entry = AgentStateEntry(
            agent_id=agent_id,
            agent_type=agent_type,
            task=task,
            status="running",
            total_steps=total_steps,
        )
        self._agent_map[agent_id] = entry
        self.state.total_agents_run += 1
        self._update_state()
        self._write_state_throttled()

    def update_agent(
        self,
        agent_id: str,
        current_step: int = None,
        message: str = None,
        status: str = None,
    ) -> None:
        """
        Manually update an agent (for non-tracker usage).

        Args:
            agent_id: Agent identifier
            current_step: Current step number
            message: Status message
            status: New status
        """
        if agent_id not in self._agent_map:
            return

        entry = self._agent_map[agent_id]

        if current_step is not None:
            entry.current_step = current_step
        if message is not None:
            entry.last_message = message
        if status is not None:
            entry.status = status
            if status in ("completed", "failed", "aborted"):
                entry.end_time = time.time()

        entry.duration_seconds = time.time() - entry.start_time
        self._update_state()
        self._write_state_throttled()

    def complete_agent(
        self,
        agent_id: str,
        success: bool = True,
        message: str = None,
    ) -> None:
        """
        Mark an agent as complete.

        Args:
            agent_id: Agent identifier
            success: Whether completed successfully
            message: Completion message
        """
        status = "completed" if success else "failed"
        self.update_agent(agent_id, status=status, message=message)

        if success:
            self.state.total_completed += 1
        else:
            self.state.total_failed += 1

    def get_active_count(self) -> int:
        """Get count of currently running agents."""
        return sum(1 for a in self._agent_map.values() if a.status == "running")

    def get_state(self) -> TUIState:
        """Get current TUI state."""
        return self.state

    def clear(self) -> None:
        """Clear all agent state."""
        self._agent_map.clear()
        self.state = TUIState()
        self._write_state()


# =============================================================================
# Global Singleton
# =============================================================================

_tui_bridge: Optional[TUIBridge] = None


def get_tui_bridge() -> TUIBridge:
    """Get or create global TUI bridge singleton."""
    global _tui_bridge
    if _tui_bridge is None:
        _tui_bridge = TUIBridge()
    return _tui_bridge


def reset_tui_bridge() -> None:
    """Reset global TUI bridge (for testing)."""
    global _tui_bridge
    _tui_bridge = None


__all__ = [
    "TUIBridge",
    "TUIState",
    "AgentStateEntry",
    "get_tui_bridge",
    "reset_tui_bridge",
]
