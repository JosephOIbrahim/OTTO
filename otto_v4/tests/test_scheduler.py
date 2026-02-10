"""Tests for the nudge scheduler (Phase 1.3)."""

from __future__ import annotations

import time
import threading
from datetime import datetime, timedelta, timezone

import pytest

from otto.models import Commitment
from otto.scheduler import NudgeScheduler
from otto.state import StateStore
from otto.store import CommitmentStore


@pytest.fixture()
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    store = CommitmentStore(db_path=db_path)
    state_store = StateStore(db_path=db_path)
    return store, state_store


@pytest.fixture()
def overdue_commitment():
    past = datetime.now(timezone.utc) - timedelta(days=5)
    return Commitment(
        raw_message="Send the report",
        commitment_text="send the report",
        who_to="Sarah",
        source_chat="test",
        deadline=past,
        deadline_source="manual",
        created_at=past,
        updated_at=past,
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestSchedulerLifecycle:
    def test_start_and_stop(self, db):
        store, state_store = db
        scheduler = NudgeScheduler(store, state_store, interval_seconds=1)
        assert not scheduler.running
        scheduler.start()
        assert scheduler.running
        scheduler.stop()
        assert not scheduler.running

    def test_double_start_is_safe(self, db):
        store, state_store = db
        scheduler = NudgeScheduler(store, state_store, interval_seconds=1)
        scheduler.start()
        scheduler.start()  # should not raise or double-schedule
        assert scheduler.running
        scheduler.stop()

    def test_double_stop_is_safe(self, db):
        store, state_store = db
        scheduler = NudgeScheduler(store, state_store, interval_seconds=1)
        scheduler.start()
        scheduler.stop()
        scheduler.stop()  # should not raise
        assert not scheduler.running

    def test_daemon_thread(self, db):
        """Timer thread is daemon so it won't block process exit."""
        store, state_store = db
        scheduler = NudgeScheduler(store, state_store, interval_seconds=60)
        scheduler.start()
        assert scheduler._timer is not None
        assert scheduler._timer.daemon is True
        scheduler.stop()


# ---------------------------------------------------------------------------
# Nudge execution
# ---------------------------------------------------------------------------


class TestSchedulerExecution:
    def test_runs_nudge_check(self, db, overdue_commitment):
        """Scheduler actually runs check_and_nudge."""
        store, state_store = db
        store.add(overdue_commitment)

        scheduler = NudgeScheduler(store, state_store, interval_seconds=60)
        # Manually trigger the check (don't wait for timer)
        scheduler._run_check()

        # Follow-up count should have been incremented by check_and_nudge
        updated = store.get(overdue_commitment.id)
        assert updated.follow_up_count > 0

    def test_constitutional_gate_blocks_in_red(self, db, overdue_commitment):
        """Scheduler respects constitutional layer — no nudges in RED."""
        store, state_store = db
        store.add(overdue_commitment)
        state_store.set_burnout("RED")

        scheduler = NudgeScheduler(store, state_store, interval_seconds=60)
        scheduler._run_check()

        # Follow-up count should NOT have been incremented
        updated = store.get(overdue_commitment.id)
        assert updated.follow_up_count == 0

        # Suppressed count should have been incremented
        state = state_store.load()
        assert state.suppressed_count == 1

    def test_constitutional_gate_allows_in_green(self, db, overdue_commitment):
        """Scheduler runs nudges when burnout is GREEN."""
        store, state_store = db
        store.add(overdue_commitment)
        state_store.set_burnout("GREEN")
        state_store.set_energy("high")

        scheduler = NudgeScheduler(store, state_store, interval_seconds=60)
        scheduler._run_check()

        updated = store.get(overdue_commitment.id)
        assert updated.follow_up_count > 0

    def test_error_in_check_does_not_crash(self, db):
        """If check_and_nudge raises, scheduler logs and continues."""
        store, state_store = db
        scheduler = NudgeScheduler(store, state_store, interval_seconds=60)

        # Corrupt the store to cause an error
        import os
        os.remove(store._db_path)

        # Should not raise
        scheduler._run_check()


# ---------------------------------------------------------------------------
# Timer behavior
# ---------------------------------------------------------------------------


class TestSchedulerTimer:
    def test_timer_fires(self, db):
        """Verify the timer actually fires within the interval."""
        store, state_store = db
        fired = threading.Event()

        scheduler = NudgeScheduler(store, state_store, interval_seconds=1)
        original_run = scheduler._run_check

        def _run_and_signal():
            original_run()
            fired.set()

        scheduler._run_check = _run_and_signal
        scheduler.start()

        assert fired.wait(timeout=3), "Timer did not fire within 3 seconds"
        scheduler.stop()
