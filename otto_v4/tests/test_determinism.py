"""Tests for determinism guarantees across OTTO modules."""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from otto.models import Commitment
from otto.nudge import format_nudge, _days_since


class TestFormatNudgeDeterminism:

    def test_format_nudge_deterministic_with_frozen_time(self):
        """Same commitment + same now = same output, every time."""
        frozen = datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        c = Commitment(
            raw_message="send the report",
            commitment_text="send the report",
            who_to="Sarah",
            created_at=datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
        )
        results = {format_nudge(c, "stale", now=frozen) for _ in range(100)}
        assert len(results) == 1, f"Non-deterministic: got {len(results)} unique outputs"

    def test_days_since_boundary(self):
        """Verify day calculation at exact midnight boundary."""
        # Commitment created at noon on March 10
        c = Commitment(
            raw_message="x",
            commitment_text="x",
            who_to="y",
            created_at=datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
        )
        # Exactly 23h59m later -> less than 1 day, should return 1 (minimum)
        almost_one_day = datetime(2025, 3, 11, 11, 59, 0, tzinfo=timezone.utc)
        assert _days_since(c, "stale", now=almost_one_day) == 1

        # Exactly 24h later -> 1 day
        one_day = datetime(2025, 3, 11, 12, 0, 0, tzinfo=timezone.utc)
        assert _days_since(c, "stale", now=one_day) == 1

        # 48h later -> 2 days
        two_days = datetime(2025, 3, 12, 12, 0, 0, tzinfo=timezone.utc)
        assert _days_since(c, "stale", now=two_days) == 2

    def test_days_since_overdue_uses_deadline(self):
        """Overdue reason uses deadline, not created_at."""
        c = Commitment(
            raw_message="x",
            commitment_text="x",
            who_to="y",
            deadline=datetime(2025, 3, 10, 12, 0, 0, tzinfo=timezone.utc),
            created_at=datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2025, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        now = datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        # 5 days since deadline, not 14 since created
        assert _days_since(c, "overdue", now=now) == 5


class TestAllLogicFunctionsAcceptNow:

    def test_nudge_functions_accept_now(self):
        """format_nudge and _days_since should accept now parameter."""
        sig_fn = inspect.signature(format_nudge)
        assert "now" in sig_fn.parameters, "format_nudge missing 'now' parameter"

        sig_ds = inspect.signature(_days_since)
        assert "now" in sig_ds.parameters, "_days_since missing 'now' parameter"

    def test_store_query_functions_accept_time_param(self):
        """get_due and get_stale should accept time override parameters."""
        from otto.store import CommitmentStore
        sig_due = inspect.signature(CommitmentStore.get_due)
        assert "as_of" in sig_due.parameters, "get_due missing 'as_of' parameter"

        sig_stale = inspect.signature(CommitmentStore.get_stale)
        assert "now" in sig_stale.parameters, "get_stale missing 'now' parameter"
