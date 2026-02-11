"""Tests for OTTO_Agents constitutional hooks."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_agent_sdk import HookContext

_otto_src = str(Path(__file__).resolve().parent.parent.parent / "otto_v4" / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

from otto.state import StateStore

from otto_agents.hooks.constitutional import (
    _NUDGE_TOOLS,
    _UNSUPPRESSABLE_TOOLS,
    constitutional_gate,
    red_burnout_gate,
)


@pytest.fixture()
def state_store(tmp_path) -> StateStore:
    return StateStore(db_path=str(tmp_path / "test.db"))


@pytest.fixture()
def ctx() -> HookContext:
    return HookContext()


class TestConstitutionalGate:
    @pytest.mark.asyncio
    async def test_non_otto_tool_passes(self, ctx):
        result = await constitutional_gate(
            {"tool_name": "Bash"}, None, ctx,
        )
        assert result == {}

    @pytest.mark.asyncio
    async def test_list_tool_never_suppressed(self, state_store, ctx):
        state_store.set_burnout("RED")
        with patch("otto_agents.hooks.constitutional._get_state_store", return_value=state_store):
            result = await constitutional_gate(
                {"tool_name": "mcp__otto__otto_list"}, None, ctx,
            )
        assert result == {}

    @pytest.mark.asyncio
    async def test_nudge_suppressed_in_red(self, state_store, ctx):
        state_store.set_burnout("RED")
        with patch("otto_agents.hooks.constitutional._get_state_store", return_value=state_store):
            result = await constitutional_gate(
                {"tool_name": "mcp__otto__otto_nudge"}, None, ctx,
            )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    @pytest.mark.asyncio
    async def test_nudge_allowed_in_green(self, state_store, ctx):
        with patch("otto_agents.hooks.constitutional._get_state_store", return_value=state_store):
            result = await constitutional_gate(
                {"tool_name": "mcp__otto__otto_nudge"}, None, ctx,
            )
        assert result == {}


class TestRedBurnoutGate:
    @pytest.mark.asyncio
    async def test_red_blocks_nudge(self, state_store, ctx):
        state_store.set_burnout("RED")
        with patch("otto_agents.hooks.constitutional._get_state_store", return_value=state_store):
            result = await red_burnout_gate(
                {"tool_name": "mcp__otto__otto_nudge"}, None, ctx,
            )
        output = result.get("hookSpecificOutput", {})
        assert output.get("permissionDecision") == "deny"

    @pytest.mark.asyncio
    async def test_green_allows_nudge(self, state_store, ctx):
        with patch("otto_agents.hooks.constitutional._get_state_store", return_value=state_store):
            result = await red_burnout_gate(
                {"tool_name": "mcp__otto__otto_nudge"}, None, ctx,
            )
        assert result == {}

    @pytest.mark.asyncio
    async def test_list_never_blocked_even_in_red(self, state_store, ctx):
        state_store.set_burnout("RED")
        with patch("otto_agents.hooks.constitutional._get_state_store", return_value=state_store):
            result = await red_burnout_gate(
                {"tool_name": "mcp__otto__otto_list"}, None, ctx,
            )
        assert result == {}


class TestToolCategories:
    def test_nudge_tools_are_gated(self):
        assert "mcp__otto__otto_nudge" in _NUDGE_TOOLS

    def test_passive_tools_are_unsuppressable(self):
        assert "mcp__otto__otto_list" in _UNSUPPRESSABLE_TOOLS
        assert "mcp__otto__otto_energy_get" in _UNSUPPRESSABLE_TOOLS
        assert "mcp__otto__otto_done" in _UNSUPPRESSABLE_TOOLS
        assert "mcp__otto__otto_park" in _UNSUPPRESSABLE_TOOLS
