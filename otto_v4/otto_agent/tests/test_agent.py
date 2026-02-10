"""Tests for otto_agent.py -- agent loop with mocked Anthropic client."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_otto_src = str(Path(__file__).resolve().parent.parent.parent / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

_agent_src = str(Path(__file__).resolve().parent.parent.parent)
if _agent_src not in sys.path:
    sys.path.insert(0, _agent_src)

from otto.state import StateStore
from otto.store import CommitmentStore
from otto_agent.otto_tools import init_stores


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_block(text: str):
    """Create a mock text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_tool_use_block(tool_id: str, name: str, input_data: dict):
    """Create a mock tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_data
    return block


def _make_response(content_blocks, stop_reason="end_turn"):
    """Create a mock Anthropic API response."""
    resp = MagicMock()
    resp.content = content_blocks
    resp.stop_reason = stop_reason
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_stores(tmp_path):
    """Wire up real stores with a temp database."""
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


# ---------------------------------------------------------------------------
# Agent loop tests
# ---------------------------------------------------------------------------


class TestAgentLoop:
    """Test the agentic loop with mocked API calls."""

    def test_text_only_response_completes(self, tmp_path):
        """Agent completes immediately if Claude returns text only."""
        mock_response = _make_response([
            _make_text_block("You have no active commitments.")
        ])

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch("otto_agent.otto_agent.Anthropic", return_value=mock_client):
            with patch("otto_agent.otto_agent._init_default_stores"):
                from otto_agent.otto_agent import run_agent
                messages = run_agent("Show my commitments")

        # Should have user message + assistant response
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_tool_use_then_response(self, store, tmp_path):
        """Agent calls a tool, gets result, then completes."""
        # Turn 1: Claude calls otto_list_commitments
        tool_response = _make_response(
            [
                _make_text_block("Let me check your commitments."),
                _make_tool_use_block(
                    "call_1", "otto_list_commitments", {}
                ),
            ],
            stop_reason="tool_use",
        )
        # Turn 2: Claude responds with text
        final_response = _make_response([
            _make_text_block("You have no active commitments right now.")
        ])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch("otto_agent.otto_agent.Anthropic", return_value=mock_client):
            with patch("otto_agent.otto_agent._init_default_stores"):
                from otto_agent.otto_agent import run_agent
                messages = run_agent("What's active?")

        # user -> assistant (tool_use) -> user (tool_result) -> assistant (text)
        assert len(messages) == 4
        assert messages[2]["role"] == "user"
        tool_result = messages[2]["content"][0]
        assert tool_result["type"] == "tool_result"

    def test_constitutional_gate_blocks_nudge_in_red(self, state_store):
        """When burnout is RED, otto_run_nudge is suppressed."""
        state_store.set_burnout("RED")

        # Turn 1: Claude calls otto_run_nudge
        tool_response = _make_response(
            [_make_tool_use_block("call_1", "otto_run_nudge", {})],
            stop_reason="tool_use",
        )
        # Turn 2: Claude explains the suppression
        final_response = _make_response([
            _make_text_block("I'll give you some space right now.")
        ])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch("otto_agent.otto_agent.Anthropic", return_value=mock_client):
            with patch("otto_agent.otto_agent._init_default_stores"):
                from otto_agent.otto_agent import run_agent
                messages = run_agent("Any nudges?")

        # The tool result should indicate suppression
        tool_result_msg = messages[2]["content"][0]
        result_data = json.loads(tool_result_msg["content"])
        assert result_data["suppressed"] is True

    def test_constitutional_gate_allows_nudge_in_green(self, state_store):
        """When burnout is GREEN, otto_run_nudge proceeds normally."""
        state_store.set_burnout("GREEN")

        tool_response = _make_response(
            [_make_tool_use_block("call_1", "otto_run_nudge", {})],
            stop_reason="tool_use",
        )
        final_response = _make_response([
            _make_text_block("Nothing to nudge about.")
        ])

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            tool_response,
            final_response,
        ]

        with patch("otto_agent.otto_agent.Anthropic", return_value=mock_client):
            with patch("otto_agent.otto_agent._init_default_stores"):
                from otto_agent.otto_agent import run_agent
                messages = run_agent("Check nudges")

        tool_result_msg = messages[2]["content"][0]
        result_data = json.loads(tool_result_msg["content"])
        assert "suppressed" not in result_data or not result_data["suppressed"]

    def test_max_turns_safety(self):
        """Agent stops after MAX_AGENT_TURNS even if Claude keeps calling tools."""
        # Every response calls a tool
        tool_response = _make_response(
            [_make_tool_use_block("call_n", "otto_get_energy", {})],
            stop_reason="tool_use",
        )

        mock_client = MagicMock()
        mock_client.messages.create.return_value = tool_response

        with patch("otto_agent.otto_agent.Anthropic", return_value=mock_client):
            with patch("otto_agent.otto_agent._init_default_stores"):
                with patch("otto_agent.otto_agent.MAX_AGENT_TURNS", 3):
                    from otto_agent.otto_agent import run_agent
                    messages = run_agent("Loop forever")

        # 3 turns * 2 messages per turn (assistant + tool_result) + 1 initial
        # = 7 messages
        assert mock_client.messages.create.call_count == 3
