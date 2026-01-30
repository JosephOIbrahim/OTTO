"""
External Working Memory Schemas

Data models for session anchoring, time beacons, and project friction.
Part of USD Cognitive Substrate production hardening.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass
class SessionAnchor:
    """Session goal anchor for context preservation.

    Prevents losing the thread by tracking what we're working on.

    Attributes:
        session_id: Unique session identifier
        goal: Current session goal (what success looks like)
        started_at: When session started
        exchange_count: Number of exchanges in session
        last_milestone: Last completed milestone
        success_criteria: How we'll know we're done
    """
    session_id: str
    goal: str
    started_at: datetime
    exchange_count: int = 0
    last_milestone: str | None = None
    success_criteria: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'goal': self.goal,
            'started_at': self.started_at.isoformat(),
            'exchange_count': self.exchange_count,
            'last_milestone': self.last_milestone,
            'success_criteria': self.success_criteria,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionAnchor:
        """Create from dictionary."""
        started_at = data.get('started_at')
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        elif started_at is None:
            started_at = datetime.now()

        return cls(
            session_id=data.get('session_id', ''),
            goal=data.get('goal', ''),
            started_at=started_at,
            exchange_count=data.get('exchange_count', 0),
            last_milestone=data.get('last_milestone'),
            success_criteria=data.get('success_criteria'),
        )


@dataclass
class TimeBeacon:
    """Time beacon for combating time blindness.

    Surfaces elapsed time periodically to maintain awareness.

    Attributes:
        session_start: When tracking started
        last_beacon_at: Exchange count of last beacon
        beacon_interval: Exchanges between beacons
        time_heuristic: Minutes per 10 exchanges (estimated)
    """
    session_start: datetime
    last_beacon_at: int = 0
    beacon_interval: int = 10
    time_heuristic: int = 45  # ~45 min per 10 exchanges

    def should_beacon(self, exchange_count: int) -> bool:
        """Check if a beacon should be shown."""
        return (exchange_count - self.last_beacon_at) >= self.beacon_interval

    def get_elapsed_estimate(self, exchange_count: int) -> str:
        """Get estimated elapsed time as human-readable string."""
        # Use heuristic: ~45 min per 10 exchanges
        estimated_minutes = (exchange_count * self.time_heuristic) // 10

        if estimated_minutes < 60:
            return f"~{estimated_minutes}m"
        else:
            hours = estimated_minutes // 60
            mins = estimated_minutes % 60
            if mins == 0:
                return f"~{hours}h"
            return f"~{hours}h{mins}m"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'session_start': self.session_start.isoformat(),
            'last_beacon_at': self.last_beacon_at,
            'beacon_interval': self.beacon_interval,
            'time_heuristic': self.time_heuristic,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimeBeacon:
        """Create from dictionary."""
        session_start = data.get('session_start')
        if isinstance(session_start, str):
            session_start = datetime.fromisoformat(session_start)
        elif session_start is None:
            session_start = datetime.now()

        return cls(
            session_start=session_start,
            last_beacon_at=data.get('last_beacon_at', 0),
            beacon_interval=data.get('beacon_interval', 10),
            time_heuristic=data.get('time_heuristic', 45),
        )


@dataclass
class Project:
    """Project entry for the project registry.

    Attributes:
        name: Project name
        path: File system path
        status: Current status
        last_touched: When last worked on
        notes: Optional notes
    """
    name: str
    path: str
    status: Literal['active', 'parked', 'completed', 'abandoned'] = 'active'
    last_touched: datetime | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'path': self.path,
            'status': self.status,
            'last_touched': self.last_touched.isoformat() if self.last_touched else None,
            'notes': self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        """Create from dictionary."""
        last_touched = data.get('last_touched')
        if isinstance(last_touched, str):
            last_touched = datetime.fromisoformat(last_touched)

        return cls(
            name=data.get('name', ''),
            path=data.get('path', ''),
            status=data.get('status', 'active'),
            last_touched=last_touched,
            notes=data.get('notes'),
        )


@dataclass
class ProjectFriction:
    """Project friction system for preventing proliferation.

    Surfaces existing open projects when starting something new.

    Attributes:
        projects: List of tracked projects
        friction_threshold: Number of active projects before warning
    """
    projects: list[Project] = field(default_factory=list)
    friction_threshold: int = 3

    @property
    def active_projects(self) -> list[Project]:
        """Get only active projects."""
        return [p for p in self.projects if p.status == 'active']

    @property
    def should_warn(self) -> bool:
        """Check if we should warn about too many active projects."""
        return len(self.active_projects) >= self.friction_threshold

    def get_friction_message(self) -> str | None:
        """Get friction message if threshold exceeded."""
        active = self.active_projects
        if len(active) < self.friction_threshold:
            return None

        project_list = ', '.join(p.name for p in active[:5])
        if len(active) > 5:
            project_list += f' (+{len(active) - 5} more)'

        return f"You have {len(active)} active projects: {project_list}. Consider completing one before starting new work."

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'projects': [p.to_dict() for p in self.projects],
            'friction_threshold': self.friction_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectFriction:
        """Create from dictionary."""
        projects = [
            Project.from_dict(p) for p in data.get('projects', [])
        ]
        return cls(
            projects=projects,
            friction_threshold=data.get('friction_threshold', 3),
        )


@dataclass
class EWMState:
    """Complete External Working Memory state.

    Combines anchor, beacon, and friction into unified state.

    Attributes:
        anchor: Session anchor state
        beacon: Time beacon state
        friction: Project friction state
        intervention_style: How interventions are delivered
    """
    anchor: SessionAnchor | None = None
    beacon: TimeBeacon | None = None
    friction: ProjectFriction | None = None
    intervention_style: Literal['gentle', 'moderate', 'firm'] = 'gentle'

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'anchor': self.anchor.to_dict() if self.anchor else None,
            'beacon': self.beacon.to_dict() if self.beacon else None,
            'friction': self.friction.to_dict() if self.friction else None,
            'intervention_style': self.intervention_style,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EWMState:
        """Create from dictionary."""
        anchor_data = data.get('anchor')
        beacon_data = data.get('beacon')
        friction_data = data.get('friction')

        return cls(
            anchor=SessionAnchor.from_dict(anchor_data) if anchor_data else None,
            beacon=TimeBeacon.from_dict(beacon_data) if beacon_data else None,
            friction=ProjectFriction.from_dict(friction_data) if friction_data else None,
            intervention_style=data.get('intervention_style', 'gentle'),
        )
