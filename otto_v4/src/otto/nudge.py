"""Follow-up nudge system for OTTO v4.0.

Checks for overdue and stale commitments, produces warm nudge messages.
No LLM calls — template-only for speed and zero cost.

Usage:
    python -m otto.nudge
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from otto.models import Commitment
from otto.store import CommitmentStore

# ---------------------------------------------------------------------------
# Nudge templates
# ---------------------------------------------------------------------------

_OVERDUE_TEMPLATES: list[str] = [
    (
        "Hey -- you said you'd {commitment_text} for {who_to}. "
        "That was {days} days ago. Did you handle it, need help "
        "drafting something, or should we park it?"
    ),
    (
        "Quick check: {commitment_text} (for {who_to}) -- still on "
        "your radar? Done / Help drafting / Park it"
    ),
    (
        "Nudge on: {commitment_text}. No judgment, just checking. "
        "What's the status?"
    ),
]

_STALE_TEMPLATES: list[str] = [
    (
        "You mentioned wanting to {commitment_text}. That was {days} "
        "days ago. Still want to? Or was it more of a 'nice to have'?"
    ),
    (
        "Gentle ping: {commitment_text}. Want to commit to a day for "
        "this, or let it go?"
    ),
]

_REPEATED_TEMPLATE: str = (
    "This is the third time I'm checking on {commitment_text}. "
    "If this keeps slipping, it might mean it's not actually important "
    "right now. Want to park it guilt-free?"
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_NUDGES = 5
COOLDOWN_HOURS = 24


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_nudge(commitment: Commitment, reason: str) -> str:
    """Build a human-friendly nudge message for *commitment*.

    Parameters
    ----------
    commitment:
        The commitment to nudge about.
    reason:
        One of ``"overdue"`` or ``"stale"``.

    Returns
    -------
    str
        A warm, non-judgmental nudge message.
    """
    days = _days_since(commitment, reason)

    # Repeated follow-ups (count > 2) always use the escalation template.
    if commitment.follow_up_count > 2:
        return _REPEATED_TEMPLATE.format(
            commitment_text=commitment.commitment_text,
            who_to=commitment.who_to,
            days=days,
        )

    # Pick template deterministically based on id + follow_up_count.
    if reason == "overdue":
        templates = _OVERDUE_TEMPLATES
    else:
        templates = _STALE_TEMPLATES

    idx = hash(commitment.id + str(commitment.follow_up_count)) % len(templates)
    template = templates[idx]

    return template.format(
        commitment_text=commitment.commitment_text,
        who_to=commitment.who_to,
        days=days,
    )


def check_and_nudge(
    store: CommitmentStore,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Check for due/stale commitments and return nudge messages.

    Parameters
    ----------
    store:
        The commitment store to query.
    now:
        Override for "current time" (useful for testing).

    Returns
    -------
    list[str]
        Up to :data:`MAX_NUDGES` nudge messages, most-overdue first.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    cooldown_cutoff = now - timedelta(hours=COOLDOWN_HOURS)

    # 1. Overdue commitments (past deadline).
    overdue = [
        c for c in store.get_due(as_of=now)
        if _past_cooldown(c, cooldown_cutoff)
    ]

    # 2. Stale commitments (no deadline, 3+ days old).
    stale = [
        c for c in store.get_stale(days=3)
        if _past_cooldown(c, cooldown_cutoff)
    ]

    # Merge: overdue first (sorted by deadline ascending — already from
    # store), then stale (sorted by created_at ascending — already from
    # store).  Cap at MAX_NUDGES.
    candidates = overdue + stale
    candidates = candidates[:MAX_NUDGES]

    nudges: list[str] = []
    for c in candidates:
        reason = "overdue" if c.deadline is not None else "stale"
        nudges.append(format_nudge(c, reason))
        store.increment_follow_up(c.id)

    return nudges


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _past_cooldown(commitment: Commitment, cutoff: datetime) -> bool:
    """Return True if the commitment was last updated before *cutoff*."""
    return commitment.updated_at <= cutoff


def _days_since(commitment: Commitment, reason: str) -> int:
    """Return the number of days since the relevant anchor date."""
    now = datetime.now(timezone.utc)
    if reason == "overdue" and commitment.deadline is not None:
        delta = now - commitment.deadline
    else:
        delta = now - commitment.created_at
    return max(1, math.floor(delta.total_seconds() / 86400))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    store = CommitmentStore()
    nudges = check_and_nudge(store)
    for nudge in nudges:
        print(nudge)
