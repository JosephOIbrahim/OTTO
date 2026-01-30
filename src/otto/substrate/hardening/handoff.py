"""
Session Handoff Detection and Management

Detects session end signals and creates handoff documents for cross-session continuity.
Part of USD Cognitive Substrate production hardening.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Session end detection patterns
END_SIGNALS = [
    r"\b(done|finished|stopping|leaving|goodbye|bye|later|signing off)\b",
    r"\b(that'?s? all|that'?s? it|all for now|call it a day)\b",
    r"\b(gotta go|have to go|need to go|heading out)\b",
    r"\b(thanks?,? that'?s? everything|thanks?,? we'?re? done)\b",
    r"\b(wrap up|wrapping up|let'?s? stop|stopping here)\b",
]

# Compiled patterns for efficiency
_END_PATTERNS = [re.compile(p, re.IGNORECASE) for p in END_SIGNALS]


@dataclass
class HandoffDocument:
    """Cross-session handoff document.

    Contains everything needed to resume context in a new session.

    Attributes:
        session_id: ID of the session being handed off
        created_at: When handoff was created
        goal: What we were working on
        progress: What was accomplished
        where_stopped: Where in the task we stopped
        next_steps: Suggested next actions
        substrate_state: Cognitive state at handoff
        open_threads: Unfinished discussions/ideas
        parked_ideas: Ideas saved for later
    """
    session_id: str
    created_at: datetime
    goal: str
    progress: str
    where_stopped: str
    next_steps: list[str] = field(default_factory=list)
    substrate_state: dict[str, Any] = field(default_factory=dict)
    open_threads: list[str] = field(default_factory=list)
    parked_ideas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'goal': self.goal,
            'progress': self.progress,
            'where_stopped': self.where_stopped,
            'next_steps': self.next_steps,
            'substrate_state': self.substrate_state,
            'open_threads': self.open_threads,
            'parked_ideas': self.parked_ideas,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandoffDocument:
        """Create from dictionary."""
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            session_id=data.get('session_id', ''),
            created_at=created_at,
            goal=data.get('goal', ''),
            progress=data.get('progress', ''),
            where_stopped=data.get('where_stopped', ''),
            next_steps=data.get('next_steps', []),
            substrate_state=data.get('substrate_state', {}),
            open_threads=data.get('open_threads', []),
            parked_ideas=data.get('parked_ideas', []),
        )

    def to_markdown(self) -> str:
        """Convert to markdown format for human readability."""
        lines = [
            f"# Session Handoff: {self.session_id}",
            f"*Created: {self.created_at.isoformat()}*",
            "",
            "## Goal",
            self.goal,
            "",
            "## Progress",
            self.progress,
            "",
            "## Where We Stopped",
            self.where_stopped,
            "",
        ]

        if self.next_steps:
            lines.extend([
                "## Next Steps",
                *[f"- {step}" for step in self.next_steps],
                "",
            ])

        if self.open_threads:
            lines.extend([
                "## Open Threads",
                *[f"- {thread}" for thread in self.open_threads],
                "",
            ])

        if self.parked_ideas:
            lines.extend([
                "## Parked Ideas",
                *[f"- {idea}" for idea in self.parked_ideas],
                "",
            ])

        if self.substrate_state:
            lines.extend([
                "## Substrate State",
                f"- Burnout: {self.substrate_state.get('burnout_level', 'unknown')}",
                f"- Momentum: {self.substrate_state.get('momentum_phase', 'unknown')}",
                f"- Energy: {self.substrate_state.get('energy_level', 'unknown')}",
                "",
            ])

        return '\n'.join(lines)


class HandoffManager:
    """Manages session handoff detection and document creation.

    Example:
        >>> manager = HandoffManager()
        >>> if manager.detect_end_signal("I'm done for today, thanks!"):
        ...     doc = manager.create_handoff(
        ...         session_id="session-abc123",
        ...         goal="Build EWM module",
        ...         progress="Completed schemas and manager",
        ...         where_stopped="Testing the manager",
        ...     )
        ...     manager.save_handoff(doc)
    """

    def __init__(self, handoff_dir: Path | str | None = None):
        """Initialize handoff manager.

        Args:
            handoff_dir: Directory for handoff files.
                        Defaults to ~/.claude/
        """
        if handoff_dir is None:
            handoff_dir = Path.home() / ".claude"
        self.handoff_dir = Path(handoff_dir)
        self.handoff_dir.mkdir(parents=True, exist_ok=True)

        self._last_session_file = self.handoff_dir / "last_session.md"
        self._last_session_json = self.handoff_dir / "last_session.json"

    def detect_end_signal(self, message: str) -> bool:
        """Detect if a message contains session end signals.

        Args:
            message: User message to check

        Returns:
            True if end signal detected
        """
        for pattern in _END_PATTERNS:
            if pattern.search(message):
                logger.debug(f"End signal detected: {pattern.pattern}")
                return True
        return False

    def create_handoff(
        self,
        session_id: str,
        goal: str,
        progress: str,
        where_stopped: str,
        next_steps: list[str] | None = None,
        substrate_state: dict[str, Any] | None = None,
        open_threads: list[str] | None = None,
        parked_ideas: list[str] | None = None,
    ) -> HandoffDocument:
        """Create a handoff document.

        Args:
            session_id: Current session ID
            goal: What we were working on
            progress: What was accomplished
            where_stopped: Where in the task we stopped
            next_steps: Suggested next actions
            substrate_state: Cognitive state at handoff
            open_threads: Unfinished discussions
            parked_ideas: Ideas saved for later

        Returns:
            HandoffDocument ready for saving
        """
        return HandoffDocument(
            session_id=session_id,
            created_at=datetime.now(),
            goal=goal,
            progress=progress,
            where_stopped=where_stopped,
            next_steps=next_steps or [],
            substrate_state=substrate_state or {},
            open_threads=open_threads or [],
            parked_ideas=parked_ideas or [],
        )

    def save_handoff(self, doc: HandoffDocument) -> tuple[Path, Path]:
        """Save handoff document in both markdown and JSON formats.

        Args:
            doc: HandoffDocument to save

        Returns:
            Tuple of (markdown_path, json_path)
        """
        # Save markdown for human readability
        self._last_session_file.write_text(
            doc.to_markdown(),
            encoding='utf-8'
        )

        # Save JSON for machine parsing
        self._last_session_json.write_text(
            json.dumps(doc.to_dict(), indent=2, sort_keys=True),
            encoding='utf-8'
        )

        logger.info(f"Saved handoff for session {doc.session_id}")
        return self._last_session_file, self._last_session_json

    def load_last_session(self) -> HandoffDocument | None:
        """Load the last session handoff document.

        Returns:
            HandoffDocument if found, None otherwise
        """
        # Prefer JSON for accuracy
        if self._last_session_json.exists():
            try:
                content = self._last_session_json.read_text(encoding='utf-8')
                data = json.loads(content)
                return HandoffDocument.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load last session JSON: {e}")

        # Fall back to parsing markdown (basic)
        if self._last_session_file.exists():
            try:
                content = self._last_session_file.read_text(encoding='utf-8')
                # Basic parsing - just extract goal from markdown
                goal_match = re.search(r'## Goal\n(.+?)(?:\n##|\Z)', content, re.DOTALL)
                goal = goal_match.group(1).strip() if goal_match else "Unknown"

                return HandoffDocument(
                    session_id="unknown",
                    created_at=datetime.now(),
                    goal=goal,
                    progress="(loaded from markdown)",
                    where_stopped="(loaded from markdown)",
                )
            except Exception as e:
                logger.warning(f"Failed to load last session markdown: {e}")

        return None

    def get_resume_prompt(self) -> str | None:
        """Get a resume prompt if last session exists.

        Returns:
            Resume prompt string or None
        """
        doc = self.load_last_session()
        if doc is None:
            return None

        goal_preview = doc.goal[:50] + "..." if len(doc.goal) > 50 else doc.goal
        return f"Last time: {goal_preview}. Continue or new direction?"

    @property
    def has_last_session(self) -> bool:
        """Check if there's a last session to resume."""
        return self._last_session_json.exists() or self._last_session_file.exists()


# Module-level singleton
_manager: HandoffManager | None = None


def get_handoff_manager() -> HandoffManager:
    """Get or create the singleton handoff manager."""
    global _manager
    if _manager is None:
        _manager = HandoffManager()
    return _manager
