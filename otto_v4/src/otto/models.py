"""Data models for OTTO v4.0 commitment tracking."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    """Generate a new commitment ID."""
    return str(uuid.uuid4())


@dataclass
class Commitment:
    """A single commitment extracted from conversation."""

    raw_message: str
    commitment_text: str
    who_to: str
    who_from: str = "me"
    deadline: datetime | None = None
    deadline_source: str = "none"
    status: str = "active"
    follow_up_count: int = 0
    source_chat: str = "unknown"
    direction: str = "outbound"
    id: str = field(default_factory=_new_id)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        """Serialize to a plain dict. Datetimes become ISO strings."""
        return {
            "id": self.id,
            "raw_message": self.raw_message,
            "commitment_text": self.commitment_text,
            "who_to": self.who_to,
            "who_from": self.who_from,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "deadline_source": self.deadline_source,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "follow_up_count": self.follow_up_count,
            "source_chat": self.source_chat,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Commitment:
        """Deserialize from a plain dict. ISO strings become datetimes."""
        deadline_raw = data.get("deadline")
        deadline = (
            datetime.fromisoformat(deadline_raw) if deadline_raw else None
        )
        return cls(
            id=data["id"],
            raw_message=data["raw_message"],
            commitment_text=data["commitment_text"],
            who_to=data["who_to"],
            who_from=data.get("who_from", "me"),
            deadline=deadline,
            deadline_source=data.get("deadline_source", "none"),
            status=data.get("status", "active"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            follow_up_count=data.get("follow_up_count", 0),
            source_chat=data.get("source_chat", "unknown"),
            direction=data.get("direction", "outbound"),
        )
