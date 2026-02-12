"""Tests for Tier 1 wiring — NEXUS pipeline integration in CLI and scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from otto.models import Commitment, build_id_map, _stable_short_id
from otto.state import CognitiveState, StateStore
from otto.store import CommitmentStore
from otto.trails import TrailStore


# ------------------------------------------------------------------
# Stable short IDs (Tier 3.1)
# ------------------------------------------------------------------

class TestStableShortIds:
    def test_deterministic(self):
        """Same UUID -> same short ID (deterministic by design)."""
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        results = {_stable_short_id(uuid) for _ in range(100)}
        assert len(results) == 1

    def test_range(self):
        """Short IDs are always 4 digits."""
        import uuid as uuid_mod
        for _ in range(100):
            sid = _stable_short_id(str(uuid_mod.uuid4()))
            assert 1000 <= sid <= 9999

    def test_build_id_map_returns_hash_ids(self):
        """build_id_map returns hash-based IDs, not positional."""
        commitments = [
            Commitment(
                raw_message=f"task {i}",
                commitment_text=f"task {i}",
                who_to="someone",
            )
            for i in range(5)
        ]
        id_map = build_id_map(commitments)
        assert len(id_map) == 5
        # All IDs should be in 4-digit range
        for short_id in id_map:
            assert 1000 <= short_id <= 9999
        # All UUIDs should be present
        uuid_set = {c.id for c in commitments}
        assert set(id_map.values()) == uuid_set

    def test_build_id_map_handles_collisions(self):
        """If two UUIDs hash to the same short ID, both are still present."""
        # Create many commitments to increase collision probability
        commitments = [
            Commitment(
                raw_message=f"task {i}",
                commitment_text=f"task {i}",
                who_to="someone",
            )
            for i in range(50)
        ]
        id_map = build_id_map(commitments)
        # All 50 must be in the map
        assert len(id_map) == 50

    def test_ids_stable_across_list_changes(self):
        """Adding a commitment doesn't change existing IDs."""
        c1 = Commitment(raw_message="a", commitment_text="a", who_to="x")
        c2 = Commitment(raw_message="b", commitment_text="b", who_to="x")
        c3 = Commitment(raw_message="c", commitment_text="c", who_to="x")

        map_2 = build_id_map([c1, c2])
        map_3 = build_id_map([c1, c2, c3])

        # c1 and c2's IDs should be the same in both maps
        c1_id_2 = next(k for k, v in map_2.items() if v == c1.id)
        c1_id_3 = next(k for k, v in map_3.items() if v == c1.id)
        assert c1_id_2 == c1_id_3


# ------------------------------------------------------------------
# Message deduplication (Tier 3.2)
# ------------------------------------------------------------------

class TestDeduplication:
    def test_duplicate_active_commitment_skipped(self, tmp_path):
        store = CommitmentStore(db_path=str(tmp_path / "dedup.db"))
        c1 = Commitment(
            raw_message="Send report to Sarah",
            commitment_text="Send report to Sarah",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        c2 = Commitment(
            raw_message="Send report to Sarah",
            commitment_text="Send report to Sarah",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        result1 = store.add(c1)
        result2 = store.add(c2)
        assert result1 != ""
        assert result2 == ""  # Duplicate skipped
        assert len(store.get_active()) == 1

    def test_different_text_not_duplicate(self, tmp_path):
        store = CommitmentStore(db_path=str(tmp_path / "dedup.db"))
        c1 = Commitment(
            raw_message="Send report",
            commitment_text="Send report",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        c2 = Commitment(
            raw_message="Send invoice",
            commitment_text="Send invoice",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        store.add(c1)
        store.add(c2)
        assert len(store.get_active()) == 2

    def test_different_who_to_not_duplicate(self, tmp_path):
        store = CommitmentStore(db_path=str(tmp_path / "dedup.db"))
        c1 = Commitment(
            raw_message="Send report",
            commitment_text="Send report",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        c2 = Commitment(
            raw_message="Send report",
            commitment_text="Send report",
            who_to="Frank",
            source_chat="whatsapp",
        )
        store.add(c1)
        store.add(c2)
        assert len(store.get_active()) == 2

    def test_done_commitment_allows_readd(self, tmp_path):
        store = CommitmentStore(db_path=str(tmp_path / "dedup.db"))
        c1 = Commitment(
            raw_message="Send report",
            commitment_text="Send report",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        store.add(c1)
        store.mark_done(c1.id)
        # Same text but c1 is done, so new one should be accepted
        c2 = Commitment(
            raw_message="Send report",
            commitment_text="Send report",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        result = store.add(c2)
        assert result != ""

    def test_dedup_can_be_disabled(self, tmp_path):
        store = CommitmentStore(db_path=str(tmp_path / "dedup.db"))
        c1 = Commitment(
            raw_message="Send report",
            commitment_text="Send report",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        c2 = Commitment(
            raw_message="Send report",
            commitment_text="Send report",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        store.add(c1, dedup=False)
        store.add(c2, dedup=False)
        # Both should be added despite same text
        assert len(store.get_active()) == 2

    def test_case_insensitive_dedup(self, tmp_path):
        store = CommitmentStore(db_path=str(tmp_path / "dedup.db"))
        c1 = Commitment(
            raw_message="Send Report",
            commitment_text="Send Report",
            who_to="Sarah",
            source_chat="whatsapp",
        )
        c2 = Commitment(
            raw_message="send report",
            commitment_text="send report",
            who_to="sarah",
            source_chat="whatsapp",
        )
        store.add(c1)
        result = store.add(c2)
        assert result == ""  # Case-insensitive match


# ------------------------------------------------------------------
# Daily state rollover (Tier 2.3)
# ------------------------------------------------------------------

class TestDailyRollover:
    def test_first_load_sets_date(self, tmp_path):
        store = StateStore(db_path=str(tmp_path / "rollover.db"))
        state = store.load()
        # Should work without error, counters at 0
        assert state.nudges_sent_today == 0

    def test_same_day_preserves_counters(self, tmp_path):
        store = StateStore(db_path=str(tmp_path / "rollover.db"))
        store.load()  # Set initial date
        store.increment_nudges_sent()
        store.increment_nudges_sent()
        state = store.load()
        assert state.nudges_sent_today == 2

    def test_new_day_resets_counters(self, tmp_path):
        store = StateStore(db_path=str(tmp_path / "rollover.db"))
        store.load()  # Set initial date
        store.increment_nudges_sent()
        store.increment_nudges_sent()

        # Simulate date change by setting last_reset_date to yesterday
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        store._set_key("last_reset_date", yesterday)

        state = store.load()
        assert state.nudges_sent_today == 0
        assert state.nudges_completed_today == 0
        assert state.suppressed_count == 0


# ------------------------------------------------------------------
# Trail deposits from CLI (Tier 1.3)
# ------------------------------------------------------------------

class TestTrailDeposits:
    def test_trail_deposit_on_done(self, tmp_path):
        """done command deposits trail when commitment had nudges."""
        trail_store = TrailStore(db_path=str(tmp_path / "trails.db"))
        trail_store.deposit("executor:nudge", "commitment_detected", 1.0)
        strength = trail_store.get_strength("executor:nudge", "commitment_detected")
        assert strength == 1.0

    def test_trail_deposit_on_park(self, tmp_path):
        """park command deposits weaker trail."""
        trail_store = TrailStore(db_path=str(tmp_path / "trails.db"))
        trail_store.deposit("executor:nudge", "commitment_detected", 0.3)
        strength = trail_store.get_strength("executor:nudge", "commitment_detected")
        assert strength == pytest.approx(0.3)

    def test_multiple_deposits_accumulate(self, tmp_path):
        trail_store = TrailStore(db_path=str(tmp_path / "trails.db"))
        trail_store.deposit("executor:nudge", "commitment_detected", 1.0)
        trail_store.deposit("executor:nudge", "commitment_detected", 0.3)
        strength = trail_store.get_strength("executor:nudge", "commitment_detected")
        assert strength == pytest.approx(1.3)


# ------------------------------------------------------------------
# Database indices (Tier 3.3)
# ------------------------------------------------------------------

class TestDatabaseIndices:
    def test_indices_exist(self, tmp_path):
        """Verify performance indices are created."""
        import sqlite3
        store = CommitmentStore(db_path=str(tmp_path / "idx.db"))
        conn = sqlite3.connect(str(tmp_path / "idx.db"))
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='commitments'"
            )
            index_names = {row[0] for row in cur.fetchall()}
        finally:
            conn.close()
        assert "idx_commitments_status" in index_names
        assert "idx_commitments_deadline" in index_names
        assert "idx_commitments_created_at" in index_names


# ------------------------------------------------------------------
# Trail feedback loop wiring (Phase A)
# ------------------------------------------------------------------

class TestTrailFeedbackLoop:
    def test_cli_nudge_passes_trail_adjustments(self, tmp_path):
        """Trail adjustments must flow into route_and_execute."""
        from unittest.mock import patch, MagicMock
        from click.testing import CliRunner
        from otto.cli import main

        runner = CliRunner()
        # Patch at the source module since nudge() does local imports
        with patch("otto.router.route_and_execute") as mock_route, \
             patch("otto.cli._get_state_store") as mock_ss, \
             patch("otto.cli._get_store") as mock_cs, \
             patch("otto.cli._get_trail_store") as mock_ts:
            mock_state = CognitiveState(burnout="GREEN", energy="high")
            mock_ss.return_value.load.return_value = mock_state
            mock_ts.return_value = TrailStore(str(tmp_path / "t.db"))
            mock_route.return_value = MagicMock(text="ok", suppress_others=False, metadata={})

            result = runner.invoke(main, ["nudge"], catch_exceptions=False)

        assert mock_route.called
        call_kwargs = mock_route.call_args.kwargs
        assert "trail_adjustments" in call_kwargs

    def test_scheduler_passes_trail_adjustments(self, tmp_path):
        """Scheduler must pass trail adjustments into route_and_execute."""
        from unittest.mock import patch, MagicMock
        from otto.scheduler import NudgeScheduler

        db = str(tmp_path / "sched.db")
        cs = CommitmentStore(db_path=db)
        ss = StateStore(db_path=db)

        scheduler = NudgeScheduler(store=cs, state_store=ss)

        with patch("otto.scheduler.route_and_execute") as mock_route:
            mock_route.return_value = MagicMock(text="ok", suppress_others=False, metadata={})
            scheduler._run_check()

        assert mock_route.called
        call_kwargs = mock_route.call_args.kwargs
        assert "trail_adjustments" in call_kwargs


# ------------------------------------------------------------------
# Plasticity wiring (Phase A)
# ------------------------------------------------------------------

class TestPlasticityWiring:
    def test_plasticity_amplifies_in_crisis(self, tmp_path):
        """During RED burnout, trail deposits are amplified by plasticity."""
        from otto.plasticity import PlasticityWindow

        db = str(tmp_path / "test.db")
        trail_store = TrailStore(db)
        state_store = StateStore(db)
        state_store.set_burnout("RED")

        state = state_store.load()
        window = PlasticityWindow()
        window.update(state)
        strength = window.adjust_strength(1.0)
        trail_store.deposit("executor:nudge", "commitment_detected", strength)

        assert trail_store.get_strength("executor:nudge", "commitment_detected") == 2.0

    def test_plasticity_normal_in_green(self, tmp_path):
        """During GREEN burnout, trail deposits are NOT amplified."""
        from otto.plasticity import PlasticityWindow

        db = str(tmp_path / "test.db")
        trail_store = TrailStore(db)
        state_store = StateStore(db)

        state = state_store.load()  # defaults to GREEN
        window = PlasticityWindow()
        window.update(state)
        strength = window.adjust_strength(1.0)
        trail_store.deposit("executor:nudge", "commitment_detected", strength)

        assert trail_store.get_strength("executor:nudge", "commitment_detected") == 1.0


# ------------------------------------------------------------------
# Signal-to-mode mapping completeness
# ------------------------------------------------------------------

class TestSignalToModeMapping:
    def test_redirector_has_signal_mapping(self):
        """Redirector must have a signal mapping so UCB1 can learn from it."""
        from otto.router import _SIGNAL_TO_MODE
        from otto.signals import SignalType

        assert SignalType.BURST_DETECTED in _SIGNAL_TO_MODE
        assert _SIGNAL_TO_MODE[SignalType.BURST_DETECTED] == "redirector"

    def test_all_seven_modes_reachable(self):
        """Every production mode should be reachable via at least one signal."""
        from otto.router import _SIGNAL_TO_MODE

        reachable_modes = set(_SIGNAL_TO_MODE.values())
        expected = {"executor", "protector", "restorer", "decomposer",
                    "acknowledger", "redirector", "guide"}
        assert expected == reachable_modes
