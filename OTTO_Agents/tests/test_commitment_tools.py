"""Tests for OTTO_Agents MCP commitment tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Patch store factories before importing tools
_otto_src = str(Path(__file__).resolve().parent.parent.parent / "otto_v4" / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

from otto.models import Commitment
from otto.state import StateStore
from otto.store import CommitmentStore

from otto_agents.tools.commitment_tools import (
    ALL_COMMITMENT_TOOLS,
    otto_add,
    otto_done,
    otto_energy_get,
    otto_energy_set,
    otto_list,
    otto_nudge,
    otto_park,
    otto_snooze,
    otto_stats,
    otto_wip,
)


def _parse_result(result: dict) -> dict:
    """Extract JSON from tool result content."""
    text = result["content"][0]["text"]
    return json.loads(text)


class TestToolCount:
    def test_ten_tools_defined(self):
        assert len(ALL_COMMITMENT_TOOLS) == 10

    def test_all_tools_have_names(self):
        names = [t.name for t in ALL_COMMITMENT_TOOLS]
        assert "otto_list" in names
        assert "otto_add" in names
        assert "otto_done" in names
        assert "otto_nudge" in names
        assert "otto_energy_get" in names


class TestOttoList:
    @pytest.mark.asyncio
    async def test_list_empty(self, store):
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_list.handler({"filter": "active"})
        data = _parse_result(result)
        assert data["count"] == 0
        assert data["commitments"] == []

    @pytest.mark.asyncio
    async def test_list_with_commitment(self, store, sample):
        store.add(sample)
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_list.handler({"filter": "active"})
        data = _parse_result(result)
        assert data["count"] == 1
        assert data["commitments"][0]["text"] == "send the report to Sarah"

    @pytest.mark.asyncio
    async def test_list_default_filter_is_active(self, store, sample):
        store.add(sample)
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_list.handler({})
        data = _parse_result(result)
        assert data["filter"] == "active"


class TestOttoAdd:
    @pytest.mark.asyncio
    async def test_add_basic(self, store):
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_add.handler({"text": "call dentist"})
        data = _parse_result(result)
        assert data["added"] is True
        assert data["text"] == "call dentist"

    @pytest.mark.asyncio
    async def test_add_with_deadline(self, store):
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_add.handler({
                "text": "submit report",
                "who_to": "boss",
                "deadline": "2026-03-01",
            })
        data = _parse_result(result)
        assert data["added"] is True

    @pytest.mark.asyncio
    async def test_add_bad_date_returns_error(self, store):
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_add.handler({"text": "foo", "deadline": "not-a-date"})
        assert result.get("is_error") is True
        data = _parse_result(result)
        assert "error" in data


class TestOttoDone:
    @pytest.mark.asyncio
    async def test_done_marks_commitment(self, store, state_store, sample):
        store.add(sample)
        with (
            patch("otto_agents.tools.commitment_tools._get_store", return_value=store),
            patch("otto_agents.tools.commitment_tools._get_state_store", return_value=state_store),
        ):
            result = await otto_done.handler({"short_id": 1})
        data = _parse_result(result)
        assert data["done"] is True

    @pytest.mark.asyncio
    async def test_done_no_commitments(self, store):
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_done.handler({"short_id": 1})
        assert result.get("is_error") is True


class TestOttoPark:
    @pytest.mark.asyncio
    async def test_park_commitment(self, store, sample):
        store.add(sample)
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_park.handler({"short_id": 1})
        data = _parse_result(result)
        assert data["parked"] is True


class TestOttoSnooze:
    @pytest.mark.asyncio
    async def test_snooze_valid(self, store, sample):
        store.add(sample)
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_snooze.handler({"short_id": 1, "duration": "4h"})
        data = _parse_result(result)
        assert data["snoozed"] is True

    @pytest.mark.asyncio
    async def test_snooze_bad_duration(self, store, sample):
        store.add(sample)
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_snooze.handler({"short_id": 1, "duration": "xyz"})
        assert result.get("is_error") is True


class TestOttoWip:
    @pytest.mark.asyncio
    async def test_wip_adds_note(self, store, sample):
        store.add(sample)
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_wip.handler({"short_id": 1, "note": "started draft"})
        data = _parse_result(result)
        assert data["noted"] is True
        assert data["note"] == "started draft"


class TestOttoEnergy:
    @pytest.mark.asyncio
    async def test_get_energy_defaults(self, state_store):
        with patch("otto_agents.tools.commitment_tools._get_state_store", return_value=state_store):
            result = await otto_energy_get.handler({})
        data = _parse_result(result)
        assert data["energy"] == "medium"
        assert data["burnout"] == "GREEN"

    @pytest.mark.asyncio
    async def test_set_energy_depleted(self, state_store):
        with patch("otto_agents.tools.commitment_tools._get_state_store", return_value=state_store):
            result = await otto_energy_set.handler({"level": "depleted"})
        data = _parse_result(result)
        assert data["set"] is True
        assert "space" in data["message"]

    @pytest.mark.asyncio
    async def test_set_energy_invalid(self, state_store):
        with patch("otto_agents.tools.commitment_tools._get_state_store", return_value=state_store):
            result = await otto_energy_set.handler({"level": "turbo"})
        assert result.get("is_error") is True


class TestOttoNudge:
    @pytest.mark.asyncio
    async def test_nudge_suppressed_in_red(self, store, state_store):
        state_store.set_burnout("RED")
        with (
            patch("otto_agents.tools.commitment_tools._get_store", return_value=store),
            patch("otto_agents.tools.commitment_tools._get_state_store", return_value=state_store),
        ):
            result = await otto_nudge.handler({})
        data = _parse_result(result)
        assert data["suppressed"] is True

    @pytest.mark.asyncio
    async def test_nudge_allowed_in_green(self, store, state_store):
        with (
            patch("otto_agents.tools.commitment_tools._get_store", return_value=store),
            patch("otto_agents.tools.commitment_tools._get_state_store", return_value=state_store),
        ):
            result = await otto_nudge.handler({})
        data = _parse_result(result)
        assert "suppressed" not in data or data["suppressed"] is not True


class TestOttoStats:
    @pytest.mark.asyncio
    async def test_stats_empty(self, store):
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_stats.handler({})
        data = _parse_result(result)
        assert data["active"] == 0
        assert data["done"] == 0


class TestHe2025Compliance:
    """Verify all tool outputs use sort_keys=True for determinism."""

    @pytest.mark.asyncio
    async def test_list_output_is_sorted_json(self, store, sample):
        store.add(sample)
        with patch("otto_agents.tools.commitment_tools._get_store", return_value=store):
            result = await otto_list.handler({"filter": "active"})
        text = result["content"][0]["text"]
        # Re-serialize with sort_keys and compare
        data = json.loads(text)
        reserialized = json.dumps(data, indent=2, sort_keys=True)
        assert text == reserialized
