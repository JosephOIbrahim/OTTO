"""
External Working Memory Manager

Manages EWM state: session anchor, time beacon, and project friction.
Part of USD Cognitive Substrate production hardening.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid

from .schemas import (
    EWMState,
    Project,
    ProjectFriction,
    SessionAnchor,
    TimeBeacon,
)

logger = logging.getLogger(__name__)


class EWMManager:
    """Manages External Working Memory state.

    Provides ADHD-supportive session tracking with:
    - Session anchor: prevents losing the thread
    - Time beacon: prevents time blindness
    - Project friction: prevents project proliferation

    Example:
        >>> manager = EWMManager()
        >>> manager.start_session(goal="Build EWM module")
        >>> manager.tick()  # Increment exchange count
        >>> if manager.should_show_beacon():
        ...     print(manager.get_status_line())
    """

    def __init__(self, state_dir: Path | str | None = None):
        """Initialize EWM manager.

        Args:
            state_dir: Directory for state files.
                      Defaults to ~/.claude/substrate/ewm/
        """
        if state_dir is None:
            state_dir = Path.home() / ".claude" / "substrate" / "ewm"
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self._state = EWMState()
        self._state_file = self.state_dir / "ewm_state.json"
        self._projects_file = self.state_dir / "projects.json"

        self._load_state()

    def _load_state(self) -> None:
        """Load state from disk with graceful degradation."""
        # Load EWM state
        if self._state_file.exists():
            try:
                content = self._state_file.read_text(encoding='utf-8')
                data = json.loads(content)
                self._state = EWMState.from_dict(data)
                logger.debug("Loaded EWM state from disk")
            except Exception as e:
                logger.warning(f"Failed to load EWM state: {e}, using defaults")
                self._state = EWMState()
        else:
            self._state = EWMState()

        # Load projects
        if self._projects_file.exists():
            try:
                content = self._projects_file.read_text(encoding='utf-8')
                data = json.loads(content)
                self._state.friction = ProjectFriction.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load projects: {e}")

    def _save_state(self) -> None:
        """Save state to disk with backup."""
        try:
            # Backup existing state
            if self._state_file.exists():
                backup_dir = self.state_dir / "backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"ewm_state_{timestamp}.json"
                backup_path.write_text(
                    self._state_file.read_text(encoding='utf-8'),
                    encoding='utf-8'
                )

            # Write new state
            content = json.dumps(self._state.to_dict(), indent=2, sort_keys=True)
            self._state_file.write_text(content, encoding='utf-8')
            logger.debug("Saved EWM state to disk")
        except Exception as e:
            logger.error(f"Failed to save EWM state: {e}")

    def _save_projects(self) -> None:
        """Save projects to disk."""
        if self._state.friction:
            try:
                content = json.dumps(self._state.friction.to_dict(), indent=2, sort_keys=True)
                self._projects_file.write_text(content, encoding='utf-8')
            except Exception as e:
                logger.error(f"Failed to save projects: {e}")

    # =========================================================================
    # Session Anchor
    # =========================================================================

    def start_session(
        self,
        goal: str,
        success_criteria: str | None = None,
        session_id: str | None = None,
    ) -> SessionAnchor:
        """Start a new session with a goal.

        Args:
            goal: What we're trying to accomplish
            success_criteria: How we'll know we're done
            session_id: Optional session ID (auto-generated if not provided)

        Returns:
            The created SessionAnchor
        """
        if session_id is None:
            session_id = f"session-{uuid.uuid4().hex[:8]}"

        anchor = SessionAnchor(
            session_id=session_id,
            goal=goal,
            started_at=datetime.now(),
            success_criteria=success_criteria,
        )
        self._state.anchor = anchor

        # Initialize beacon for this session
        self._state.beacon = TimeBeacon(session_start=datetime.now())

        self._save_state()
        return anchor

    def update_milestone(self, milestone: str) -> None:
        """Update the last completed milestone."""
        if self._state.anchor:
            self._state.anchor.last_milestone = milestone
            self._save_state()

    def get_session_goal(self) -> str | None:
        """Get the current session goal."""
        if self._state.anchor:
            return self._state.anchor.goal
        return None

    @property
    def has_active_session(self) -> bool:
        """Check if there's an active session."""
        return self._state.anchor is not None

    # =========================================================================
    # Time Beacon
    # =========================================================================

    def tick(self) -> None:
        """Increment exchange count."""
        if self._state.anchor:
            self._state.anchor.exchange_count += 1
            self._save_state()

    def should_show_beacon(self) -> bool:
        """Check if a time beacon should be shown."""
        if self._state.beacon and self._state.anchor:
            return self._state.beacon.should_beacon(
                self._state.anchor.exchange_count
            )
        return False

    def mark_beacon_shown(self) -> None:
        """Mark that a beacon was shown."""
        if self._state.beacon and self._state.anchor:
            self._state.beacon.last_beacon_at = self._state.anchor.exchange_count
            self._save_state()

    def get_elapsed_estimate(self) -> str:
        """Get estimated elapsed time."""
        if self._state.beacon and self._state.anchor:
            return self._state.beacon.get_elapsed_estimate(
                self._state.anchor.exchange_count
            )
        return "~0m"

    # =========================================================================
    # Project Friction
    # =========================================================================

    def add_project(
        self,
        name: str,
        path: str,
        status: str = 'active',
        notes: str | None = None,
    ) -> Project:
        """Add a project to the registry.

        Args:
            name: Project name
            path: File system path
            status: 'active', 'parked', 'completed', or 'abandoned'
            notes: Optional notes

        Returns:
            The created Project
        """
        if self._state.friction is None:
            self._state.friction = ProjectFriction()

        project = Project(
            name=name,
            path=path,
            status=status,
            last_touched=datetime.now(),
            notes=notes,
        )
        self._state.friction.projects.append(project)
        self._save_projects()
        return project

    def update_project_status(
        self,
        name: str,
        status: str,
    ) -> bool:
        """Update a project's status.

        Args:
            name: Project name
            status: New status

        Returns:
            True if project was found and updated
        """
        if self._state.friction is None:
            return False

        for project in self._state.friction.projects:
            if project.name == name:
                project.status = status
                project.last_touched = datetime.now()
                self._save_projects()
                return True
        return False

    def get_active_projects(self) -> list[Project]:
        """Get list of active projects."""
        if self._state.friction:
            return self._state.friction.active_projects
        return []

    def get_friction_warning(self) -> str | None:
        """Get friction warning if too many active projects."""
        if self._state.friction:
            return self._state.friction.get_friction_message()
        return None

    # =========================================================================
    # Status Line
    # =========================================================================

    def get_status_line(
        self,
        expert: str = "Direct",
        altitude: str = "30000ft",
        burnout: str = "GREEN",
        momentum: str = "building",
    ) -> str:
        """Generate status line for visibility.

        Format: [~time | Goal: X | expert | altitude | burnout | momentum]

        Args:
            expert: Current expert (Validator/Scaffolder/Direct/etc)
            altitude: Current altitude (30000ft/15000ft/5000ft/Ground)
            burnout: Current burnout level (GREEN/YELLOW/ORANGE/RED)
            momentum: Current momentum phase

        Returns:
            Formatted status line
        """
        elapsed = self.get_elapsed_estimate()
        goal = self._state.anchor.goal if self._state.anchor else "No goal set"

        # Truncate goal if too long
        if len(goal) > 30:
            goal = goal[:27] + "..."

        return f"[{elapsed} | Goal: {goal} | {expert} | {altitude} | {burnout} | {momentum}]"

    # =========================================================================
    # State Access
    # =========================================================================

    @property
    def state(self) -> EWMState:
        """Get current EWM state."""
        return self._state

    def set_intervention_style(
        self,
        style: str,
    ) -> None:
        """Set intervention style.

        Args:
            style: 'gentle', 'moderate', or 'firm'
        """
        if style in ('gentle', 'moderate', 'firm'):
            self._state.intervention_style = style
            self._save_state()


# Module-level singleton
_manager: EWMManager | None = None


def get_manager() -> EWMManager:
    """Get or create the singleton EWM manager."""
    global _manager
    if _manager is None:
        _manager = EWMManager()
    return _manager
