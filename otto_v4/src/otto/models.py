"""Data models for OTTO v4.0 commitment tracking."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


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
    snoozed_until: datetime | None = None
    notes: str = ""
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
            "snoozed_until": self.snoozed_until.isoformat() if self.snoozed_until else None,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Commitment:
        """Deserialize from a plain dict. ISO strings become datetimes."""
        deadline_raw = data.get("deadline")
        deadline = (
            datetime.fromisoformat(deadline_raw) if deadline_raw else None
        )
        snoozed_raw = data.get("snoozed_until")
        snoozed_until = (
            datetime.fromisoformat(snoozed_raw) if snoozed_raw else None
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
            snoozed_until=snoozed_until,
            notes=data.get("notes", ""),
        )


# ---------------------------------------------------------------------------
# Shared helpers (used by both cli.py and otto_tools.py)
# ---------------------------------------------------------------------------


def _stable_short_id(uuid_str: str) -> int:
    """Derive a stable 4-digit short ID from a UUID.

    Uses SHA-256 to produce a deterministic integer in [1000, 9999].
    This is PYTHONHASHSEED-independent (deterministic by design).
    """
    digest = hashlib.sha256(uuid_str.encode()).hexdigest()  # noqa: S324
    return 1000 + (int(digest[:8], 16) % 9000)


def build_id_map(commitments: list[Commitment]) -> dict[int, str]:
    """Map stable short IDs to UUIDs.

    IDs are hash-derived from UUIDs so they don't shift when commitments
    are added or removed. Collisions are resolved by incrementing.
    """
    id_map: dict[int, str] = {}
    for c in commitments:
        short_id = _stable_short_id(c.id)
        attempts = 0
        while short_id in id_map:
            short_id += 1
            if short_id > 9999:
                short_id = 1000
            attempts += 1
            if attempts >= 9000:
                raise RuntimeError("ID space exhausted (9000 commitments)")
        id_map[short_id] = c.id
    return id_map


def parse_duration(duration: str) -> timedelta | None:
    """Parse a duration string like '4h', '30m', '2d' into a timedelta.

    Returns None if the format is invalid.
    """
    match = re.fullmatch(r"(\d+)(m|h|d)", duration.strip().lower())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    return None
