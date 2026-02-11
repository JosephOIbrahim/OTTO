"""Tests for otto_tools.py -- tool definitions and execution."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure otto source is importable
_otto_src = str(Path(__file__).resolve().parent.parent.parent / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

# Ensure otto_agent is importable
_agent_src = str(Path(__file__).resolve().parent.parent.parent)
if _agent_src not in sys.path:
    sys.path.insert(0, _agent_src)

from otto.models import Commitment, build_id_map
from otto.state import CognitiveState, StateStore
from otto.store import CommitmentStore
from otto_agent.otto_tools import (
    TOOL_DEFINITIONS,
    execute_tool,
    init_stores,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_stores(tmp_path):
    """Create real stores backed by a temp database for each test."""
    db_path = str(tmp_path / "test.db")
    store = CommitmentStore(db_path=db_path)
    state_store = StateStore(db_path=db_path)
    init_stores(store=store, state_store=state_store)
    yield store, state_store


@pytest.fixture
def store(_setup_stores):
    return _setup_stores[0]


@pytest.fixture
def state_store(_setup_stores):
    return _setup_stores[1]


@pytest.fixture
def sample_commitment():
    return Commitment(
        raw_message="I'll send the report to Sarah by Friday",
        commitment_text="send the report to Sarah",
        who_to="Sarah",
        source_chat="test",
    )


@pytest.fixture
def overdue_commitment():
    past = datetime.now(timezone.utc) - timedelta(days=5)
    return Commitment(
        raw_message="I'll send the report by Monday",
        commitment_text="send the report",
        who_to="Sarah",
        source_chat="test",
        deadline=past,
        deadline_source="manual",
        created_at=past,
        updated_at=past,
    )


# ---------------------------------------------------------------------------
# Tool schema validation
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    def test_all_tools_have_required_fields(self):
        for tool in TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_tool_count(self):
        assert len(TOOL_DEFINITIONS) == 10

    def test_tool_names(self):
        names = {t["name"] for t in TOOL_DEFINITIONS}
        expected = {
            "otto_list_commitments",
            "otto_add_commitment",
            "otto_mark_done",
            "otto_park_commitment",
            "otto_run_nudge",
            "otto_get_stats",
            "otto_get_energy",
            "otto_set_energy",
            "otto_snooze_commitment",
            "otto_add_wip_note",
        }
        assert names == expected


# ---------------------------------------------------------------------------
# List commitments
# ---------------------------------------------------------------------------


class TestListCommitments:
    def test_empty_list(self):
        result = json.loads(execute_tool("otto_list_commitments", {}))
        assert result["count"] == 0
        assert result["commitments"] == []

    def test_list_active(self, store, sample_commitment):
        store.add(sample_commitment)
        result = json.loads(execute_tool("otto_list_commitments", {}))
        assert result["count"] == 1
        assert result["commitments"][0]["text"] == "send the report to Sarah"

    def test_list_due(self, store, overdue_commitment):
        store.add(overdue_commitment)
        result = json.loads(
            execute_tool("otto_list_commitments", {"filter": "due"})
        )
        assert result["count"] == 1
        assert result["label"] == "overdue"

    def test_list_all_includes_done(self, store, sample_commitment):
        store.add(sample_commitment)
        store.mark_done(sample_commitment.id)
        result = json.loads(
            execute_tool("otto_list_commitments", {"filter": "all"})
        )
        assert result["count"] == 1
        assert result["commitments"][0]["status"] == "done"


# ---------------------------------------------------------------------------
# Add commitment
# ---------------------------------------------------------------------------


class TestAddCommitment:
    def test_add_basic(self, store):
        result = json.loads(
            execute_tool("otto_add_commitment", {"text": "Call the dentist"})
        )
        assert result["added"] is True
        assert result["text"] == "Call the dentist"
        assert store.get_active()[0].commitment_text == "Call the dentist"

    def test_add_with_deadline(self, store):
        result = json.loads(
            execute_tool(
                "otto_add_commitment",
                {"text": "Submit taxes", "deadline": "2026-04-15"},
            )
        )
        assert result["added"] is True
        c = store.get_active()[0]
        assert c.deadline is not None
        assert c.deadline.year == 2026

    def test_add_with_who(self, store):
        result = json.loads(
            execute_tool(
                "otto_add_commitment",
                {"text": "Send proposal", "who_to": "Sarah"},
            )
        )
        assert result["added"] is True
        assert store.get_active()[0].who_to == "Sarah"

    def test_add_bad_date(self):
        result = json.loads(
            execute_tool(
                "otto_add_commitment",
                {"text": "Something", "deadline": "not-a-date"},
            )
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Mark done
# ---------------------------------------------------------------------------


class TestMarkDone:
    def test_mark_done(self, store, sample_commitment):
        store.add(sample_commitment)
        id_map = build_id_map(store.get_active())
        short_id = next(k for k, v in id_map.items() if v == sample_commitment.id)
        result = json.loads(execute_tool("otto_mark_done", {"short_id": short_id}))
        assert result["done"] is True
        assert store.get(sample_commitment.id).status == "done"

    def test_mark_done_no_commitments(self):
        result = json.loads(execute_tool("otto_mark_done", {"short_id": 9999}))
        assert "error" in result

    def test_mark_done_bad_id(self, store, sample_commitment):
        store.add(sample_commitment)
        result = json.loads(execute_tool("otto_mark_done", {"short_id": 99}))
        assert "error" in result


# ---------------------------------------------------------------------------
# Park commitment
# ---------------------------------------------------------------------------


class TestParkCommitment:
    def test_park(self, store, sample_commitment):
        store.add(sample_commitment)
        id_map = build_id_map(store.get_active())
        short_id = next(k for k, v in id_map.items() if v == sample_commitment.id)
        result = json.loads(
            execute_tool("otto_park_commitment", {"short_id": short_id})
        )
        assert result["parked"] is True
        assert store.get(sample_commitment.id).status == "parked"

    def test_park_no_commitments(self):
        result = json.loads(
            execute_tool("otto_park_commitment", {"short_id": 9999})
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Run nudge
# ---------------------------------------------------------------------------


class TestRunNudge:
    def test_no_nudges(self):
        result = json.loads(execute_tool("otto_run_nudge", {}))
        assert result["nudges"] == []

    def test_nudges_for_overdue(self, store, overdue_commitment):
        store.add(overdue_commitment)
        result = json.loads(execute_tool("otto_run_nudge", {}))
        assert result["count"] >= 1
        assert len(result["nudges"]) >= 1


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        result = json.loads(execute_tool("otto_get_stats", {}))
        assert result["active"] == 0
        assert result["done"] == 0
        assert result["parked"] == 0

    def test_stats_with_data(self, store, sample_commitment):
        store.add(sample_commitment)
        result = json.loads(execute_tool("otto_get_stats", {}))
        assert result["active"] == 1


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------


class TestGetEnergy:
    def test_default_energy(self):
        result = json.loads(execute_tool("otto_get_energy", {}))
        assert result["energy"] == "medium"
        assert result["burnout"] == "GREEN"

    def test_energy_after_set(self, state_store):
        state_store.set_energy("low")
        result = json.loads(execute_tool("otto_get_energy", {}))
        assert result["energy"] == "low"


class TestSetEnergy:
    def test_set_depleted(self, state_store):
        result = json.loads(
            execute_tool("otto_set_energy", {"level": "depleted"})
        )
        assert result["set"] is True
        assert result["energy"] == "depleted"
        assert "space" in result["message"]

    def test_set_high(self, state_store):
        result = json.loads(
            execute_tool("otto_set_energy", {"level": "high"})
        )
        assert result["set"] is True
        assert result["energy"] == "high"


# ---------------------------------------------------------------------------
# Snooze commitment
# ---------------------------------------------------------------------------


class TestSnoozeCommitment:
    def test_snooze(self, store, sample_commitment):
        store.add(sample_commitment)
        id_map = build_id_map(store.get_active())
        short_id = next(k for k, v in id_map.items() if v == sample_commitment.id)
        result = json.loads(
            execute_tool("otto_snooze_commitment", {"short_id": short_id, "duration": "4h"})
        )
        assert result["snoozed"] is True
        assert result["text"] == "send the report to Sarah"

    def test_snooze_no_commitments(self):
        result = json.loads(
            execute_tool("otto_snooze_commitment", {"short_id": 9999, "duration": "4h"})
        )
        assert "error" in result

    def test_snooze_bad_id(self, store, sample_commitment):
        store.add(sample_commitment)
        result = json.loads(
            execute_tool("otto_snooze_commitment", {"short_id": 99, "duration": "4h"})
        )
        assert "error" in result

    def test_snooze_bad_duration(self, store, sample_commitment):
        store.add(sample_commitment)
        id_map = build_id_map(store.get_active())
        short_id = next(k for k, v in id_map.items() if v == sample_commitment.id)
        result = json.loads(
            execute_tool("otto_snooze_commitment", {"short_id": short_id, "duration": "xyz"})
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# WIP note
# ---------------------------------------------------------------------------


class TestWipNote:
    def test_wip(self, store, sample_commitment):
        store.add(sample_commitment)
        id_map = build_id_map(store.get_active())
        short_id = next(k for k, v in id_map.items() if v == sample_commitment.id)
        result = json.loads(
            execute_tool("otto_add_wip_note", {"short_id": short_id, "note": "50% done"})
        )
        assert result["noted"] is True
        assert result["note"] == "50% done"

    def test_wip_no_commitments(self):
        result = json.loads(
            execute_tool("otto_add_wip_note", {"short_id": 9999, "note": "test"})
        )
        assert "error" in result

    def test_wip_bad_id(self, store, sample_commitment):
        store.add(sample_commitment)
        result = json.loads(
            execute_tool("otto_add_wip_note", {"short_id": 99, "note": "test"})
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


class TestUnknownTool:
    def test_unknown_tool(self):
        result = json.loads(execute_tool("nonexistent_tool", {}))
        assert "error" in result
