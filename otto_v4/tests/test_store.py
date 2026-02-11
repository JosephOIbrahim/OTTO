"""Tests for the SQLite commitment store."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from otto.models import Commitment
from otto.store import CommitmentStore


# ------------------------------------------------------------------
# Snooze
# ------------------------------------------------------------------

class TestSnooze:
    def test_snooze_commitment(self, store, sample):
        store.add(sample)
        snooze_until = datetime.now(timezone.utc) + timedelta(hours=4)
        store.snooze(sample.id, snooze_until)
        c = store.get(sample.id)
        assert c.snoozed_until is not None
        assert c.snoozed_until == snooze_until

    def test_snoozed_excluded_from_due(self, store):
        """Snoozed commitments don't appear in get_due()."""
        past = datetime.now(timezone.utc) - timedelta(days=2)
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        c = Commitment(
            raw_message="test", commitment_text="test",
            who_to="X", deadline=past, deadline_source="manual",
            created_at=past, updated_at=past,
        )
        store.add(c)
        store.snooze(c.id, future)
        assert store.get_due() == []

    def test_expired_snooze_appears_in_due(self, store):
        """Snooze that has expired should appear in get_due()."""
        past = datetime.now(timezone.utc) - timedelta(days=2)
        expired = datetime.now(timezone.utc) - timedelta(hours=1)
        c = Commitment(
            raw_message="test", commitment_text="test",
            who_to="X", deadline=past, deadline_source="manual",
            created_at=past, updated_at=past,
        )
        store.add(c)
        store.snooze(c.id, expired)
        assert len(store.get_due()) == 1

    def test_unsnooze(self, store, sample):
        store.add(sample)
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        store.snooze(sample.id, future)
        store.unsnooze(sample.id)
        c = store.get(sample.id)
        assert c.snoozed_until is None

    def test_snoozed_excluded_from_stale(self, store):
        """Snoozed commitments don't appear in get_stale()."""
        old = datetime.now(timezone.utc) - timedelta(days=5)
        future = datetime.now(timezone.utc) + timedelta(hours=4)
        c = Commitment(
            raw_message="test", commitment_text="test",
            who_to="X", created_at=old, updated_at=old,
        )
        store.add(c)
        store.snooze(c.id, future)
        assert store.get_stale(days=3) == []


# ------------------------------------------------------------------
# Notes
# ------------------------------------------------------------------

class TestNotes:
    def test_add_note(self, store, sample):
        store.add(sample)
        store.add_note(sample.id, "Working on it, 50% done")
        c = store.get(sample.id)
        assert c.notes == "Working on it, 50% done"

    def test_append_note(self, store, sample):
        store.add(sample)
        store.add_note(sample.id, "Started")
        store.add_note(sample.id, "50% done")
        c = store.get(sample.id)
        assert "Started" in c.notes
        assert "50% done" in c.notes

    def test_default_notes_empty(self, store, sample):
        store.add(sample)
        c = store.get(sample.id)
        assert c.notes == ""


_COMMITMENT_COUNTER = 0

def _make_commitment(**overrides) -> Commitment:
    """Helper: create a Commitment with sensible defaults.

    Each call produces a unique commitment_text to avoid deduplication.
    """
    global _COMMITMENT_COUNTER
    _COMMITMENT_COUNTER += 1
    defaults = {
        "raw_message": f"I'll send the report to Sarah by Friday (#{_COMMITMENT_COUNTER})",
        "commitment_text": f"send the report to Sarah (#{_COMMITMENT_COUNTER})",
        "who_to": "Sarah",
        "who_from": "me",
        "direction": "outbound",
        "source_chat": "slack",
    }
    defaults.update(overrides)
    return Commitment(**defaults)



# ------------------------------------------------------------------
# add + get round-trip
# ------------------------------------------------------------------

class TestAddAndGet:

    def test_round_trip(self, store: CommitmentStore) -> None:
        """add() then get() returns an equivalent commitment."""
        c = _make_commitment()
        returned_id = store.add(c)
        assert returned_id == c.id

        fetched = store.get(c.id)
        assert fetched is not None
        assert fetched.id == c.id
        assert fetched.raw_message == c.raw_message
        assert fetched.commitment_text == c.commitment_text
        assert fetched.who_to == c.who_to
        assert fetched.who_from == c.who_from
        assert fetched.direction == c.direction
        assert fetched.status == "active"
        assert fetched.follow_up_count == 0
        assert fetched.source_chat == "slack"

    def test_round_trip_with_deadline(self, store: CommitmentStore) -> None:
        """Deadline datetime survives the round-trip."""
        deadline = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        c = _make_commitment(deadline=deadline, deadline_source="explicit")
        store.add(c)

        fetched = store.get(c.id)
        assert fetched is not None
        assert fetched.deadline == deadline
        assert fetched.deadline_source == "explicit"

    def test_get_missing_returns_none(self, store: CommitmentStore) -> None:
        """get() with unknown ID returns None."""
        assert store.get("nonexistent-id") is None


# ------------------------------------------------------------------
# get_active
# ------------------------------------------------------------------

class TestGetActive:

    def test_returns_only_active(self, store: CommitmentStore) -> None:
        """get_active() excludes done/parked commitments."""
        active = _make_commitment(commitment_text="active one")
        done = _make_commitment(commitment_text="done one", status="done")
        parked = _make_commitment(commitment_text="parked one", status="parked")

        store.add(active)
        store.add(done)
        store.add(parked)

        results = store.get_active()
        assert len(results) == 1
        assert results[0].commitment_text == "active one"

    def test_ordered_by_deadline_nulls_last(self, store: CommitmentStore) -> None:
        """Active commitments with deadlines come before those without."""
        no_deadline = _make_commitment(commitment_text="no deadline")
        early = _make_commitment(
            commitment_text="early",
            deadline=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        late = _make_commitment(
            commitment_text="late",
            deadline=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )

        # Insert in non-sorted order
        store.add(no_deadline)
        store.add(late)
        store.add(early)

        results = store.get_active()
        assert len(results) == 3
        assert results[0].commitment_text == "early"
        assert results[1].commitment_text == "late"
        assert results[2].commitment_text == "no deadline"


# ------------------------------------------------------------------
# get_due
# ------------------------------------------------------------------

class TestGetDue:

    def test_returns_overdue(self, store: CommitmentStore) -> None:
        """get_due() returns active commitments past their deadline."""
        past = _make_commitment(
            commitment_text="overdue",
            deadline=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        future = _make_commitment(
            commitment_text="upcoming",
            deadline=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        no_dl = _make_commitment(commitment_text="no deadline")

        store.add(past)
        store.add(future)
        store.add(no_dl)

        results = store.get_due()
        assert len(results) == 1
        assert results[0].commitment_text == "overdue"

    def test_custom_as_of(self, store: CommitmentStore) -> None:
        """get_due(as_of=...) uses the supplied cutoff."""
        c = _make_commitment(
            commitment_text="borderline",
            deadline=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        store.add(c)

        # Before the deadline -- not due
        before = datetime(2026, 6, 1, tzinfo=timezone.utc)
        assert len(store.get_due(as_of=before)) == 0

        # After the deadline -- due
        after = datetime(2026, 7, 1, tzinfo=timezone.utc)
        assert len(store.get_due(as_of=after)) == 1

    def test_excludes_done(self, store: CommitmentStore) -> None:
        """get_due() ignores non-active commitments even if overdue."""
        c = _make_commitment(
            commitment_text="old done",
            deadline=datetime(2020, 1, 1, tzinfo=timezone.utc),
            status="done",
        )
        store.add(c)
        assert len(store.get_due()) == 0


# ------------------------------------------------------------------
# get_stale
# ------------------------------------------------------------------

class TestGetStale:

    def test_returns_old_no_deadline(self, store: CommitmentStore) -> None:
        """get_stale() returns active, no-deadline commitments older than N days."""
        old_time = datetime.now(timezone.utc) - timedelta(days=5)
        old = _make_commitment(
            commitment_text="stale",
            created_at=old_time,
            updated_at=old_time,
        )
        fresh = _make_commitment(commitment_text="fresh")

        store.add(old)
        store.add(fresh)

        results = store.get_stale(days=3)
        assert len(results) == 1
        assert results[0].commitment_text == "stale"

    def test_excludes_deadlined(self, store: CommitmentStore) -> None:
        """get_stale() ignores commitments that have a deadline."""
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        c = _make_commitment(
            commitment_text="has deadline",
            deadline=datetime(2099, 1, 1, tzinfo=timezone.utc),
            created_at=old_time,
            updated_at=old_time,
        )
        store.add(c)
        assert len(store.get_stale(days=3)) == 0


# ------------------------------------------------------------------
# mark_done
# ------------------------------------------------------------------

class TestMarkDone:

    def test_changes_status(self, store: CommitmentStore) -> None:
        c = _make_commitment()
        store.add(c)
        store.mark_done(c.id)

        fetched = store.get(c.id)
        assert fetched is not None
        assert fetched.status == "done"

    def test_updates_updated_at(self, store: CommitmentStore) -> None:
        c = _make_commitment()
        store.add(c)
        original_updated = store.get(c.id).updated_at

        store.mark_done(c.id)
        fetched = store.get(c.id)
        assert fetched.updated_at >= original_updated


# ------------------------------------------------------------------
# mark_parked
# ------------------------------------------------------------------

class TestMarkParked:

    def test_changes_status(self, store: CommitmentStore) -> None:
        c = _make_commitment()
        store.add(c)
        store.mark_parked(c.id)

        fetched = store.get(c.id)
        assert fetched is not None
        assert fetched.status == "parked"

    def test_updates_updated_at(self, store: CommitmentStore) -> None:
        c = _make_commitment()
        store.add(c)
        original_updated = store.get(c.id).updated_at

        store.mark_parked(c.id)
        fetched = store.get(c.id)
        assert fetched.updated_at >= original_updated


# ------------------------------------------------------------------
# increment_follow_up
# ------------------------------------------------------------------

class TestIncrementFollowUp:

    def test_bumps_count(self, store: CommitmentStore) -> None:
        c = _make_commitment()
        store.add(c)
        assert store.get(c.id).follow_up_count == 0

        store.increment_follow_up(c.id)
        assert store.get(c.id).follow_up_count == 1

        store.increment_follow_up(c.id)
        assert store.get(c.id).follow_up_count == 2

    def test_updates_updated_at(self, store: CommitmentStore) -> None:
        c = _make_commitment()
        store.add(c)
        original_updated = store.get(c.id).updated_at

        store.increment_follow_up(c.id)
        fetched = store.get(c.id)
        assert fetched.updated_at >= original_updated


# ------------------------------------------------------------------
# delete
# ------------------------------------------------------------------

class TestDelete:

    def test_removes_commitment(self, store: CommitmentStore) -> None:
        c = _make_commitment()
        store.add(c)
        assert store.get(c.id) is not None

        store.delete(c.id)
        assert store.get(c.id) is None

    def test_delete_nonexistent_is_noop(self, store: CommitmentStore) -> None:
        """Deleting a missing ID does not raise."""
        store.delete("does-not-exist")  # should not raise


# ------------------------------------------------------------------
# count
# ------------------------------------------------------------------

class TestCount:

    def test_counts_by_status(self, store: CommitmentStore) -> None:
        store.add(_make_commitment(status="active"))
        store.add(_make_commitment(status="active"))
        store.add(_make_commitment(status="done"))
        store.add(_make_commitment(status="parked"))

        counts = store.count()
        assert counts["active"] == 2
        assert counts["done"] == 1
        assert counts["parked"] == 1

    def test_empty_store(self, store: CommitmentStore) -> None:
        assert store.count() == {}


# ------------------------------------------------------------------
# get_all
# ------------------------------------------------------------------

class TestGetAll:

    def test_returns_all_statuses(self, store: CommitmentStore) -> None:
        store.add(_make_commitment(commitment_text="active"))
        store.add(_make_commitment(commitment_text="done", status="done"))
        store.add(_make_commitment(commitment_text="parked", status="parked"))

        results = store.get_all()
        assert len(results) == 3
        texts = {r.commitment_text for r in results}
        assert texts == {"active", "done", "parked"}

    def test_ordered_newest_first(self, store: CommitmentStore) -> None:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        store.add(_make_commitment(
            commitment_text="old",
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
        ))
        store.add(_make_commitment(
            commitment_text="new",
            created_at=now,
            updated_at=now,
        ))

        results = store.get_all()
        assert results[0].commitment_text == "new"
        assert results[1].commitment_text == "old"


# ------------------------------------------------------------------
# avg_follow_ups_done
# ------------------------------------------------------------------

class TestAvgFollowUpsDone:

    def test_returns_average(self, store: CommitmentStore) -> None:
        c1 = _make_commitment(follow_up_count=2, status="done")
        c2 = _make_commitment(follow_up_count=4, status="done")
        store.add(c1)
        store.add(c2)

        avg = store.avg_follow_ups_done()
        assert avg == 3.0

    def test_no_done_returns_none(self, store: CommitmentStore) -> None:
        store.add(_make_commitment())  # active, not done
        assert store.avg_follow_ups_done() is None

    def test_empty_store_returns_none(self, store: CommitmentStore) -> None:
        assert store.avg_follow_ups_done() is None


# ------------------------------------------------------------------
# nuke
# ------------------------------------------------------------------

class TestNuke:

    def test_clears_everything(self, store: CommitmentStore) -> None:
        store.add(_make_commitment())
        store.add(_make_commitment())
        assert store.count().get("active", 0) == 2

        store.nuke()
        assert store.count() == {}

    def test_table_still_works_after_nuke(self, store: CommitmentStore) -> None:
        """After nuke, the store is usable again."""
        store.nuke()
        c = _make_commitment()
        store.add(c)
        assert store.get(c.id) is not None


# ------------------------------------------------------------------
# directory creation
# ------------------------------------------------------------------

class TestDirectoryCreation:

    def test_creates_parent_directory(self, tmp_path) -> None:
        """Store creates the parent directory if it doesn't exist."""
        deep_path = str(tmp_path / "a" / "b" / "c" / "test.db")
        s = CommitmentStore(db_path=deep_path)
        s.add(_make_commitment())
        assert os.path.exists(deep_path)
