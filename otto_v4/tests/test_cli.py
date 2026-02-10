"""Tests for the OTTO CLI (Phase 5)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from otto.cli import main, _get_store, _get_state_store
from otto.models import Commitment
from otto.state import StateStore
from otto.store import CommitmentStore


@pytest.fixture()
def tmp_db(tmp_path):
    """Provide a temporary database path and monkeypatch _get_store."""
    db_path = str(tmp_path / "test.db")

    def _make_store():
        return CommitmentStore(db_path=db_path)

    with patch("otto.cli._get_store", side_effect=_make_store):
        yield _make_store


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def seeded_store(tmp_db):
    """Return a store pre-loaded with a few commitments."""
    store = tmp_db()
    now = datetime.now(timezone.utc)

    store.add(Commitment(
        raw_message="Send deck to Sarah",
        commitment_text="Send deck to Sarah",
        who_to="Sarah Chen",
        source_chat="WhatsApp/Sarah Chen",
        deadline=now + timedelta(days=2),
        deadline_source="explicit",
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(days=3),
        follow_up_count=1,
    ))
    store.add(Commitment(
        raw_message="Follow up with Frank about music collab",
        commitment_text="Follow up with Frank about music collab",
        who_to="Frank",
        source_chat="WhatsApp/Frank",
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(days=5),
    ))
    return store


# ------------------------------------------------------------------
# otto list
# ------------------------------------------------------------------

class TestList:
    def test_empty_store_shows_empty_message(self, runner, tmp_db):
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "No active commitments" in result.output
        assert "crushing it" in result.output

    def test_with_commitments_shows_formatted_output(self, runner, seeded_store):
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "Active Commitments (2)" in result.output
        assert "#1" in result.output
        assert "Send deck to Sarah" in result.output
        assert "#2" in result.output
        assert "Follow up with Frank" in result.output
        assert "otto done 1" in result.output
        assert "otto park 1" in result.output
        assert "Followed up: 1x" in result.output
        assert "WhatsApp/Sarah Chen" in result.output

    def test_due_filters_to_overdue_only(self, runner, tmp_db):
        store = tmp_db()
        now = datetime.now(timezone.utc)

        # Overdue commitment (deadline in the past)
        store.add(Commitment(
            raw_message="overdue task",
            commitment_text="overdue task",
            who_to="someone",
            deadline=now - timedelta(days=1),
            deadline_source="explicit",
        ))

        # Not overdue (deadline in the future)
        store.add(Commitment(
            raw_message="future task",
            commitment_text="future task",
            who_to="someone",
            deadline=now + timedelta(days=5),
            deadline_source="explicit",
        ))

        # No deadline at all
        store.add(Commitment(
            raw_message="no deadline task",
            commitment_text="no deadline task",
            who_to="someone",
        ))

        result = runner.invoke(main, ["list", "--due"])
        assert result.exit_code == 0
        assert "Overdue Commitments (1)" in result.output
        assert "overdue task" in result.output
        assert "future task" not in result.output
        assert "no deadline task" not in result.output

    def test_due_empty_shows_nice_message(self, runner, tmp_db):
        result = runner.invoke(main, ["list", "--due"])
        assert result.exit_code == 0
        assert "No overdue" in result.output

    def test_all_shows_done_and_parked(self, runner, tmp_db):
        store = tmp_db()
        now = datetime.now(timezone.utc)

        c1 = Commitment(
            raw_message="active one",
            commitment_text="active one",
            who_to="someone",
        )
        c2 = Commitment(
            raw_message="done one",
            commitment_text="done one",
            who_to="someone",
        )
        c3 = Commitment(
            raw_message="parked one",
            commitment_text="parked one",
            who_to="someone",
        )
        store.add(c1)
        store.add(c2)
        store.add(c3)
        store.mark_done(c2.id)
        store.mark_parked(c3.id)

        result = runner.invoke(main, ["list", "--all"])
        assert result.exit_code == 0
        assert "All Commitments (3)" in result.output
        assert "active one" in result.output
        assert "done one" in result.output
        assert "parked one" in result.output


# ------------------------------------------------------------------
# otto add
# ------------------------------------------------------------------

class TestAdd:
    def test_add_creates_commitment(self, runner, tmp_db):
        result = runner.invoke(main, ["add", "Buy groceries"])
        assert result.exit_code == 0
        assert "Added: Buy groceries" in result.output

        store = tmp_db()
        active = store.get_active()
        assert len(active) == 1
        assert active[0].commitment_text == "Buy groceries"
        assert active[0].source_chat == "manual"

    def test_add_with_who_and_deadline(self, runner, tmp_db):
        result = runner.invoke(main, [
            "add", "Send report",
            "--to", "Boss",
            "--by", "2026-03-15",
        ])
        assert result.exit_code == 0
        assert "Added: Send report" in result.output

        store = tmp_db()
        active = store.get_active()
        assert len(active) == 1
        assert active[0].who_to == "Boss"
        assert active[0].deadline is not None
        assert active[0].deadline.year == 2026
        assert active[0].deadline.month == 3
        assert active[0].deadline.day == 15

    def test_add_bad_date_shows_error(self, runner, tmp_db):
        result = runner.invoke(main, ["add", "foo", "--by", "not-a-date"])
        assert result.exit_code == 0
        assert "Bad date format" in result.output

        store = tmp_db()
        assert len(store.get_active()) == 0


# ------------------------------------------------------------------
# otto done
# ------------------------------------------------------------------

class TestDone:
    def test_done_marks_commitment(self, runner, seeded_store):
        result = runner.invoke(main, ["done", "1"])
        assert result.exit_code == 0
        assert "Done:" in result.output
        assert "Send deck to Sarah" in result.output

        # Verify it was actually marked done
        active = seeded_store.get_active()
        assert len(active) == 1
        assert active[0].commitment_text == "Follow up with Frank about music collab"

    def test_done_invalid_id(self, runner, seeded_store):
        result = runner.invoke(main, ["done", "99"])
        assert result.exit_code == 0
        assert "No commitment #99" in result.output

    def test_done_empty_store(self, runner, tmp_db):
        result = runner.invoke(main, ["done", "1"])
        assert result.exit_code == 0
        assert "No active commitments" in result.output


# ------------------------------------------------------------------
# otto park
# ------------------------------------------------------------------

class TestPark:
    def test_park_marks_commitment(self, runner, seeded_store):
        result = runner.invoke(main, ["park", "2"])
        assert result.exit_code == 0
        assert "Parked:" in result.output
        assert "Follow up with Frank" in result.output

        active = seeded_store.get_active()
        assert len(active) == 1
        assert active[0].commitment_text == "Send deck to Sarah"

    def test_park_invalid_id(self, runner, seeded_store):
        result = runner.invoke(main, ["park", "99"])
        assert result.exit_code == 0
        assert "No commitment #99" in result.output

    def test_park_empty_store(self, runner, tmp_db):
        result = runner.invoke(main, ["park", "1"])
        assert result.exit_code == 0
        assert "No active commitments" in result.output


# ------------------------------------------------------------------
# otto stats
# ------------------------------------------------------------------

class TestStats:
    def test_stats_shows_counts(self, runner, tmp_db):
        store = tmp_db()

        # Create some commitments in various states
        c1 = Commitment(
            raw_message="a", commitment_text="a", who_to="x",
        )
        c2 = Commitment(
            raw_message="b", commitment_text="b", who_to="x",
            follow_up_count=2,
        )
        c3 = Commitment(
            raw_message="c", commitment_text="c", who_to="x",
            follow_up_count=4,
        )
        c4 = Commitment(
            raw_message="d", commitment_text="d", who_to="x",
        )
        store.add(c1)
        store.add(c2)
        store.add(c3)
        store.add(c4)

        store.mark_done(c2.id)
        store.mark_done(c3.id)
        store.mark_parked(c4.id)

        result = runner.invoke(main, ["stats"])
        assert result.exit_code == 0
        assert "OTTO Stats" in result.output
        assert "Active: 1" in result.output
        assert "Done: 2" in result.output
        assert "Parked: 1" in result.output
        assert "Avg follow-ups before done: 3.0" in result.output

    def test_stats_empty_store(self, runner, tmp_db):
        result = runner.invoke(main, ["stats"])
        assert result.exit_code == 0
        assert "Active: 0" in result.output
        assert "Done: 0" in result.output
        assert "Parked: 0" in result.output
        assert "n/a" in result.output


# ------------------------------------------------------------------
# otto nuke
# ------------------------------------------------------------------

class TestNuke:
    def test_nuke_with_yes_clears_everything(self, runner, seeded_store):
        # Verify there are commitments first
        assert len(seeded_store.get_active()) == 2

        result = runner.invoke(main, ["nuke", "--yes"])
        assert result.exit_code == 0
        assert "All data deleted" in result.output

        assert len(seeded_store.get_active()) == 0

    def test_nuke_without_yes_aborts(self, runner, seeded_store):
        result = runner.invoke(main, ["nuke"], input="n\n")
        assert result.exit_code != 0 or "Aborted" in result.output

        # Data should still be there
        assert len(seeded_store.get_active()) == 2


# ------------------------------------------------------------------
# otto nudge
# ------------------------------------------------------------------

class TestNudge:
    def test_nudge_without_module_shows_message(self, runner, tmp_db):
        """If nudge module is missing, show a friendly message."""
        with patch("otto.cli.check_and_nudge", side_effect=ImportError, create=True):
            # Simulate ImportError by patching the import inside nudge()
            pass
        # Since nudge.py exists in this project, test the actual path:
        # with no nudgeable commitments, we get "Nothing to nudge about"
        result = runner.invoke(main, ["nudge"])
        assert result.exit_code == 0
        assert "Nothing to nudge" in result.output

    def test_nudge_import_error(self, runner, tmp_db):
        """If nudge module cannot be imported, show friendly message."""
        import sys
        # Temporarily make the import fail
        import otto.nudge as nudge_mod
        saved = sys.modules.get("otto.nudge")
        sys.modules["otto.nudge"] = None  # type: ignore[assignment]
        try:
            result = runner.invoke(main, ["nudge"])
            assert result.exit_code == 0
            assert "Nudge module not ready yet" in result.output
        finally:
            if saved is not None:
                sys.modules["otto.nudge"] = saved
            else:
                sys.modules.pop("otto.nudge", None)


# ------------------------------------------------------------------
# otto energy
# ------------------------------------------------------------------


@pytest.fixture()
def tmp_state(tmp_path):
    """Provide a patched _get_state_store for energy tests."""
    db_path = str(tmp_path / "test_energy.db")

    def _make_state_store():
        return StateStore(db_path=db_path)

    with patch("otto.cli._get_state_store", side_effect=_make_state_store):
        yield _make_state_store


class TestEnergy:
    def test_energy_shows_defaults(self, runner, tmp_state):
        result = runner.invoke(main, ["energy"])
        assert result.exit_code == 0
        assert "Energy:   medium" in result.output
        assert "Burnout:  GREEN" in result.output
        assert "Momentum: cold_start" in result.output

    def test_energy_set_low(self, runner, tmp_state):
        result = runner.invoke(main, ["energy", "low"])
        assert result.exit_code == 0
        assert "Energy set to low" in result.output
        assert "go easy" in result.output

    def test_energy_set_depleted(self, runner, tmp_state):
        result = runner.invoke(main, ["energy", "depleted"])
        assert result.exit_code == 0
        assert "Energy set to depleted" in result.output
        assert "give you space" in result.output

    def test_energy_set_high(self, runner, tmp_state):
        result = runner.invoke(main, ["energy", "high"])
        assert result.exit_code == 0
        assert "Energy set to high" in result.output

    def test_energy_invalid_level(self, runner, tmp_state):
        result = runner.invoke(main, ["energy", "exhausted"])
        assert result.exit_code == 0
        assert "Invalid level" in result.output

    def test_energy_persists(self, runner, tmp_state):
        runner.invoke(main, ["energy", "low"])
        result = runner.invoke(main, ["energy"])
        assert "Energy:   low" in result.output
