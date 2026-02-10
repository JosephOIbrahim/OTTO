"""Tests for the follow-up nudge system (Phase 4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from otto.models import Commitment
from otto.nudge import (
    MAX_NUDGES,
    _OVERDUE_TEMPLATES,
    _REPEATED_TEMPLATE,
    _STALE_TEMPLATES,
    check_and_nudge,
    format_nudge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)



def _overdue_commitment(**overrides) -> Commitment:
    """A commitment whose deadline is 5 days in the past."""
    defaults = dict(
        raw_message="I'll send the report to Alice by Monday",
        commitment_text="send the report",
        who_to="Alice",
        deadline=_utcnow() - timedelta(days=5),
        deadline_source="explicit",
        status="active",
        follow_up_count=0,
        # updated_at well past the 24-hour cooldown
        updated_at=_utcnow() - timedelta(days=5),
        created_at=_utcnow() - timedelta(days=7),
    )
    defaults.update(overrides)
    return Commitment(**defaults)


def _stale_commitment(**overrides) -> Commitment:
    """A commitment with no deadline, created 5 days ago."""
    defaults = dict(
        raw_message="I should probably organise the shared drive",
        commitment_text="organise the shared drive",
        who_to="team",
        deadline=None,
        deadline_source="none",
        status="active",
        follow_up_count=0,
        updated_at=_utcnow() - timedelta(days=5),
        created_at=_utcnow() - timedelta(days=5),
    )
    defaults.update(overrides)
    return Commitment(**defaults)


def _future_commitment(**overrides) -> Commitment:
    """An active commitment whose deadline is still in the future."""
    defaults = dict(
        raw_message="I'll review the PR by next Friday",
        commitment_text="review the PR",
        who_to="Bob",
        deadline=_utcnow() + timedelta(days=3),
        deadline_source="explicit",
        status="active",
        follow_up_count=0,
        updated_at=_utcnow() - timedelta(days=2),
        created_at=_utcnow() - timedelta(days=2),
    )
    defaults.update(overrides)
    return Commitment(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOverdueNudge:
    """Overdue commitments produce nudge messages."""

    def test_overdue_produces_nudge(self, store):

        store.add(_overdue_commitment())

        nudges = check_and_nudge(store, now=_utcnow())

        assert len(nudges) == 1
        assert isinstance(nudges[0], str)
        assert len(nudges[0]) > 0

    def test_overdue_nudge_contains_commitment_text(self, store):

        c = _overdue_commitment(commitment_text="email the slides")
        store.add(c)

        nudges = check_and_nudge(store, now=_utcnow())

        assert "email the slides" in nudges[0]


class TestStaleNudge:
    """Stale commitments (no deadline, 3+ days old) produce nudge messages."""

    def test_stale_produces_nudge(self, store):

        store.add(_stale_commitment())

        nudges = check_and_nudge(store, now=_utcnow())

        assert len(nudges) == 1
        assert isinstance(nudges[0], str)
        assert len(nudges[0]) > 0

    def test_stale_nudge_contains_commitment_text(self, store):

        c = _stale_commitment(commitment_text="clean up the repo")
        store.add(c)

        nudges = check_and_nudge(store, now=_utcnow())

        assert "clean up the repo" in nudges[0]


class TestNonOverdueSkipped:
    """Commitments that are not yet due should NOT produce nudges."""

    def test_future_deadline_no_nudge(self, store):

        store.add(_future_commitment())

        nudges = check_and_nudge(store, now=_utcnow())

        assert nudges == []

    def test_recent_stale_no_nudge(self, store):
        """A commitment without deadline, created only 1 day ago, is not stale."""

        c = _stale_commitment(
            created_at=_utcnow() - timedelta(days=1),
            updated_at=_utcnow() - timedelta(days=1),
        )
        store.add(c)

        nudges = check_and_nudge(store, now=_utcnow())

        assert nudges == []


class TestMaxNudges:
    """At most MAX_NUDGES (5) nudges per check."""

    def test_max_five_nudges(self, store):

        for i in range(8):
            store.add(_overdue_commitment(
                commitment_text=f"task {i}",
                deadline=_utcnow() - timedelta(days=5 + i),
                updated_at=_utcnow() - timedelta(days=5 + i),
                created_at=_utcnow() - timedelta(days=10 + i),
            ))

        nudges = check_and_nudge(store, now=_utcnow())

        assert len(nudges) == MAX_NUDGES


class TestCooldown:
    """Commitments followed up < 24 hours ago are skipped."""

    def test_recently_followed_up_skipped(self, store):

        # updated_at is only 1 hour ago -- within cooldown
        c = _overdue_commitment(updated_at=_utcnow() - timedelta(hours=1))
        store.add(c)

        nudges = check_and_nudge(store, now=_utcnow())

        assert nudges == []

    def test_exactly_24h_ago_is_nudged(self, store):

        # updated_at is exactly 24 hours ago -- on the boundary (<=)
        c = _overdue_commitment(updated_at=_utcnow() - timedelta(hours=24))
        store.add(c)

        nudges = check_and_nudge(store, now=_utcnow())

        assert len(nudges) == 1

    def test_past_cooldown_is_nudged(self, store):

        c = _overdue_commitment(updated_at=_utcnow() - timedelta(hours=48))
        store.add(c)

        nudges = check_and_nudge(store, now=_utcnow())

        assert len(nudges) == 1


class TestRepeatedFollowUp:
    """Commitments with follow_up_count > 2 use the escalation template."""

    def test_escalation_template_used(self, store):

        c = _overdue_commitment(follow_up_count=3)
        store.add(c)

        nudges = check_and_nudge(store, now=_utcnow())

        assert len(nudges) == 1
        assert "third time" in nudges[0]

    def test_escalation_template_mentions_park(self, store):

        c = _overdue_commitment(follow_up_count=4)
        store.add(c)

        nudges = check_and_nudge(store, now=_utcnow())

        assert "park it guilt-free" in nudges[0]


class TestTemplateRotation:
    """Same commitment gets different messages on different follow_up_counts."""

    def test_different_counts_different_templates(self):
        """At least 2 of 3 follow_up_counts produce distinct messages
        (the hash selects from the template list)."""
        c0 = _overdue_commitment(follow_up_count=0)
        c1 = _overdue_commitment(follow_up_count=1)
        c2 = _overdue_commitment(follow_up_count=2)
        # Use same ID so only the count differs
        c1.id = c0.id
        c2.id = c0.id

        msg0 = format_nudge(c0, "overdue")
        msg1 = format_nudge(c1, "overdue")
        msg2 = format_nudge(c2, "overdue")

        messages = {msg0, msg1, msg2}
        # With 3 templates, at least 2 distinct messages are expected
        assert len(messages) >= 2

    def test_deterministic_for_same_input(self):
        """Same id + same count = same message, every time."""
        c = _overdue_commitment()
        msg1 = format_nudge(c, "overdue")
        msg2 = format_nudge(c, "overdue")
        assert msg1 == msg2


class TestFormatNudge:
    """format_nudge includes commitment_text and who_to."""

    def test_overdue_includes_fields(self):
        c = _overdue_commitment(
            commitment_text="file the taxes",
            who_to="Sarah",
            follow_up_count=0,
        )
        msg = format_nudge(c, "overdue")

        assert "file the taxes" in msg
        # who_to may not appear in every template (template 3 omits it)
        # but commitment_text always appears
        assert isinstance(msg, str)

    def test_stale_includes_commitment_text(self):
        c = _stale_commitment(commitment_text="tidy up docs")
        msg = format_nudge(c, "stale")

        assert "tidy up docs" in msg

    def test_overdue_who_to_in_at_least_some_templates(self):
        """who_to appears in at least some overdue templates."""
        c = _overdue_commitment(who_to="Dana")
        found = False
        for count in range(10):
            c.follow_up_count = count
            msg = format_nudge(c, "overdue")
            if "Dana" in msg:
                found = True
                break
        assert found, "who_to never appeared in any overdue template"


class TestIncrementFollowUp:
    """check_and_nudge increments follow_up_count via the store."""

    def test_follow_up_count_incremented(self, store):

        c = _overdue_commitment()
        store.add(c)

        check_and_nudge(store, now=_utcnow())

        refreshed = store.get(c.id)
        assert refreshed is not None
        assert refreshed.follow_up_count == 1

    def test_multiple_nudges_increment_each(self, store):

        c1 = _overdue_commitment(commitment_text="task A")
        c2 = _stale_commitment(commitment_text="task B")
        store.add(c1)
        store.add(c2)

        check_and_nudge(store, now=_utcnow())

        assert store.get(c1.id).follow_up_count == 1
        assert store.get(c2.id).follow_up_count == 1
