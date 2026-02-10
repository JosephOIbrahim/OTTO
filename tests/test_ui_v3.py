"""Tests for OTTO OS v3.0 — UI + MCP (Days 13-15).

Covers:
    - ChatMessage, ConversationHistory, ChatSession
    - DashboardState, CognitiveSummary
    - ThemeColors, style constants
    - TUI skeleton guard
    - MCP tools, handler, dispatch
    - Constitutional language checks
    - [He2025] determinism

Run: python -m pytest tests/test_ui_v3.py -v --noconftest --tb=short
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest


# ── Chat: ChatMessage ──────────────────────────────────────────


class TestChatMessage:
    def test_creation(self):
        from otto.ui.chat import ChatMessage

        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert isinstance(msg.timestamp, datetime)

    def test_frozen(self):
        from otto.ui.chat import ChatMessage

        msg = ChatMessage(role="user", content="hello")
        with pytest.raises(FrozenInstanceError):
            msg.role = "assistant"  # type: ignore[misc]

    def test_metadata_default_empty(self):
        from otto.ui.chat import ChatMessage

        msg = ChatMessage(role="user", content="hello")
        assert msg.metadata == {}

    def test_metadata_preserved(self):
        from otto.ui.chat import ChatMessage

        msg = ChatMessage(
            role="assistant",
            content="hi",
            metadata={"expert": "executor"},
        )
        assert msg.metadata["expert"] == "executor"

    def test_timestamp_utc(self):
        from otto.ui.chat import ChatMessage

        msg = ChatMessage(role="user", content="test")
        assert msg.timestamp.tzinfo is not None


# ── Chat: ConversationHistory ──────────────────────────────────


class TestConversationHistory:
    def test_empty(self):
        from otto.ui.chat import ConversationHistory

        h = ConversationHistory()
        assert h.count == 0
        assert h.last is None
        assert h.messages == []

    def test_add_and_count(self):
        from otto.ui.chat import ChatMessage, ConversationHistory

        h = ConversationHistory()
        h.add(ChatMessage(role="user", content="a"))
        h.add(ChatMessage(role="assistant", content="b"))
        assert h.count == 2

    def test_last_message(self):
        from otto.ui.chat import ChatMessage, ConversationHistory

        h = ConversationHistory()
        h.add(ChatMessage(role="user", content="first"))
        h.add(ChatMessage(role="user", content="second"))
        assert h.last is not None
        assert h.last.content == "second"

    def test_max_messages_fifo(self):
        from otto.ui.chat import ChatMessage, ConversationHistory

        h = ConversationHistory(max_messages=3)
        for i in range(5):
            h.add(ChatMessage(role="user", content=f"msg{i}"))
        assert h.count == 3
        assert h.messages[0].content == "msg2"
        assert h.messages[2].content == "msg4"

    def test_to_api_format_excludes_system(self):
        from otto.ui.chat import ChatMessage, ConversationHistory

        h = ConversationHistory()
        h.add(ChatMessage(role="system", content="system prompt"))
        h.add(ChatMessage(role="user", content="hello"))
        h.add(ChatMessage(role="assistant", content="hi"))
        api = h.to_api_format()
        assert len(api) == 2
        assert api[0] == {"role": "user", "content": "hello"}
        assert api[1] == {"role": "assistant", "content": "hi"}

    def test_estimate_tokens_empty(self):
        from otto.ui.chat import ConversationHistory

        h = ConversationHistory()
        assert h.estimate_tokens() == 0

    def test_estimate_tokens_rough(self):
        from otto.ui.chat import ChatMessage, ConversationHistory

        h = ConversationHistory()
        # 100 chars -> ~25 tokens
        h.add(ChatMessage(role="user", content="a" * 100))
        tokens = h.estimate_tokens()
        assert tokens == 25

    def test_estimate_tokens_minimum_one(self):
        from otto.ui.chat import ChatMessage, ConversationHistory

        h = ConversationHistory()
        h.add(ChatMessage(role="user", content="hi"))
        tokens = h.estimate_tokens()
        assert tokens >= 1

    def test_clear(self):
        from otto.ui.chat import ChatMessage, ConversationHistory

        h = ConversationHistory()
        h.add(ChatMessage(role="user", content="test"))
        h.clear()
        assert h.count == 0

    def test_messages_returns_copy(self):
        from otto.ui.chat import ChatMessage, ConversationHistory

        h = ConversationHistory()
        h.add(ChatMessage(role="user", content="test"))
        msgs = h.messages
        msgs.clear()
        assert h.count == 1  # Original unaffected


# ── Chat: ChatSession ─────────────────────────────────────────


def _make_mock_pipeline(content: str = "response", expert: str = "executor"):
    """Create a mock NEXUSPipeline for testing ChatSession."""
    mock = MagicMock()
    result = MagicMock()
    result.selection.primary.expert = expert
    result.selection.supporting = []
    result.effort.value = "low"
    result.signals = []
    result.response.content = content
    result.response.input_tokens = 100
    result.response.output_tokens = 50
    mock.process.return_value = result
    return mock


class TestChatSession:
    def test_initial_state(self):
        from otto.ui.chat import ChatSession

        session = ChatSession(pipeline=_make_mock_pipeline())
        assert session.exchange_count == 0
        assert session.history.count == 0

    def test_send_basic(self):
        from otto.ui.chat import ChatSession

        pipeline = _make_mock_pipeline(content="hello back")
        session = ChatSession(pipeline=pipeline)
        response = session.send("hello")

        assert response.role == "assistant"
        assert response.content == "hello back"
        assert session.exchange_count == 1
        assert session.history.count == 2  # user + assistant

    def test_send_metadata(self):
        from otto.ui.chat import ChatSession

        pipeline = _make_mock_pipeline(expert="protector")
        session = ChatSession(pipeline=pipeline)
        response = session.send("I'm frustrated")

        assert response.metadata["expert"] == "protector"
        assert "effort" in response.metadata
        assert "signal_count" in response.metadata

    def test_send_with_supporting_experts(self):
        from otto.ui.chat import ChatSession

        pipeline = _make_mock_pipeline()
        sup1 = MagicMock()
        sup1.expert = "decomposer"
        sup2 = MagicMock()
        sup2.expert = "restorer"
        pipeline.process.return_value.selection.supporting = [sup1, sup2]
        session = ChatSession(pipeline=pipeline)
        response = session.send("test")

        assert response.metadata["supporting"] == ["decomposer", "restorer"]

    def test_send_with_services(self):
        from otto.ui.chat import ChatSession

        pipeline = _make_mock_pipeline()
        registry = MagicMock()
        sig = MagicMock()
        sig.category = "time_period"
        sig.value = "morning"
        registry.get_all_signals.return_value = [sig]

        session = ChatSession(pipeline=pipeline, services=registry)
        session.send("hello")

        # Pipeline should have been called with state including time_period
        call_kwargs = pipeline.process.call_args
        assert "time_period" in call_kwargs.kwargs.get("state", call_kwargs[1].get("state", {}))

    def test_send_explicit_state_overrides_ambient(self):
        from otto.ui.chat import ChatSession

        pipeline = _make_mock_pipeline()
        registry = MagicMock()
        sig = MagicMock()
        sig.category = "time_period"
        sig.value = "morning"
        registry.get_all_signals.return_value = [sig]

        session = ChatSession(pipeline=pipeline, services=registry)
        session.send("hello", state={"time_period": "evening"})

        call_kwargs = pipeline.process.call_args
        state = call_kwargs.kwargs.get("state", call_kwargs[1].get("state", {}))
        assert state["time_period"] == "evening"

    def test_send_with_compaction(self):
        from otto.ui.chat import ChatSession

        pipeline = _make_mock_pipeline()
        compaction = MagicMock()
        session = ChatSession(pipeline=pipeline, compaction=compaction)
        session.send("test")

        compaction.record_exchange.assert_called_once_with(
            input_tokens=100, output_tokens=50,
        )

    def test_session_duration(self):
        from otto.ui.chat import ChatSession

        session = ChatSession(pipeline=_make_mock_pipeline())
        duration = session.session_duration_minutes()
        assert duration >= 0.0

    def test_services_accessor(self):
        from otto.ui.chat import ChatSession

        session = ChatSession(pipeline=_make_mock_pipeline())
        assert session.services is None

        registry = MagicMock()
        session2 = ChatSession(pipeline=_make_mock_pipeline(), services=registry)
        assert session2.services is registry


# ── Dashboard ──────────────────────────────────────────────────


class TestDashboardState:
    def test_frozen(self):
        from otto.services.base import CategoricalSignal
        from otto.ui.dashboard import DashboardState

        state = DashboardState(
            primary_expert="executor",
            supporting_experts=(),
            effort_level="low",
            active_signals=(),
            compaction_utilization=0.3,
            exchange_count=5,
            session_duration_minutes=10.0,
        )
        with pytest.raises(FrozenInstanceError):
            state.primary_expert = "protector"  # type: ignore[misc]

    def test_all_fields(self):
        from otto.ui.dashboard import DashboardState

        state = DashboardState(
            primary_expert="guide",
            supporting_experts=("decomposer",),
            effort_level="high",
            active_signals=(),
            compaction_utilization=0.75,
            exchange_count=12,
            session_duration_minutes=45.0,
        )
        assert state.primary_expert == "guide"
        assert state.supporting_experts == ("decomposer",)
        assert state.compaction_utilization == 0.75


class TestCognitiveSummary:
    def test_describe_known_expert(self):
        from otto.ui.dashboard import CognitiveSummary

        desc = CognitiveSummary.describe_expert("protector")
        assert "wellbeing" in desc.lower()

    def test_describe_unknown_expert(self):
        from otto.ui.dashboard import CognitiveSummary

        desc = CognitiveSummary.describe_expert("unknown_expert")
        assert desc == "Helping you out"

    def test_describe_known_effort(self):
        from otto.ui.dashboard import CognitiveSummary

        desc = CognitiveSummary.describe_effort("max")
        assert "deep" in desc.lower()

    def test_describe_unknown_effort(self):
        from otto.ui.dashboard import CognitiveSummary

        desc = CognitiveSummary.describe_effort("unknown")
        assert desc == "Thinking"

    def test_describe_state(self):
        from otto.ui.dashboard import CognitiveSummary, DashboardState

        state = DashboardState(
            primary_expert="executor",
            supporting_experts=(),
            effort_level="low",
            active_signals=(),
            compaction_utilization=0.3,
            exchange_count=5,
            session_duration_minutes=10.0,
        )
        summary = CognitiveSummary.describe_state(state)
        assert "5 exchanges" in summary
        assert "|" in summary

    def test_describe_compaction_low(self):
        from otto.ui.dashboard import CognitiveSummary

        desc = CognitiveSummary.describe_compaction(0.3)
        assert "plenty" in desc.lower()
        assert "30%" in desc

    def test_describe_compaction_medium(self):
        from otto.ui.dashboard import CognitiveSummary

        desc = CognitiveSummary.describe_compaction(0.65)
        assert "getting full" in desc.lower()

    def test_describe_compaction_high(self):
        from otto.ui.dashboard import CognitiveSummary

        desc = CognitiveSummary.describe_compaction(0.9)
        assert "almost full" in desc.lower()
        assert "compaction" in desc.lower()


class TestExpertDescriptions:
    def test_all_seven_experts(self):
        from otto.ui.dashboard import EXPERT_DESCRIPTIONS

        expected = {
            "acknowledger", "decomposer", "executor",
            "guide", "protector", "redirector", "restorer",
        }
        assert set(EXPERT_DESCRIPTIONS.keys()) == expected

    def test_sorted_keys(self):
        from otto.ui.dashboard import EXPERT_DESCRIPTIONS

        keys = list(EXPERT_DESCRIPTIONS.keys())
        assert keys == sorted(keys)


class TestEffortDescriptions:
    def test_all_four_levels(self):
        from otto.ui.dashboard import EFFORT_DESCRIPTIONS

        expected = {"high", "low", "max", "medium"}
        assert set(EFFORT_DESCRIPTIONS.keys()) == expected

    def test_sorted_keys(self):
        from otto.ui.dashboard import EFFORT_DESCRIPTIONS

        keys = list(EFFORT_DESCRIPTIONS.keys())
        assert keys == sorted(keys)


# ── Styles ─────────────────────────────────────────────────────


class TestThemeColors:
    def test_defaults(self):
        from otto.ui.styles import ThemeColors

        theme = ThemeColors()
        assert theme.primary == "#6C63FF"
        assert theme.background == "#1E1E2E"

    def test_frozen(self):
        from otto.ui.styles import ThemeColors

        theme = ThemeColors()
        with pytest.raises(FrozenInstanceError):
            theme.primary = "#000000"  # type: ignore[misc]

    def test_default_theme_instance(self):
        from otto.ui.styles import DEFAULT_THEME, ThemeColors

        assert isinstance(DEFAULT_THEME, ThemeColors)

    def test_all_colors_hex(self):
        from otto.ui.styles import DEFAULT_THEME

        for field_name in (
            "primary", "secondary", "success", "warning",
            "danger", "text", "text_dim", "background", "surface",
        ):
            color = getattr(DEFAULT_THEME, field_name)
            assert re.match(r"^#[0-9A-Fa-f]{6}$", color), f"{field_name}: {color}"


class TestExpertColors:
    def test_seven_experts(self):
        from otto.ui.styles import EXPERT_COLORS

        assert len(EXPERT_COLORS) == 7
        expected = {
            "acknowledger", "decomposer", "executor",
            "guide", "protector", "redirector", "restorer",
        }
        assert set(EXPERT_COLORS.keys()) == expected

    def test_sorted_keys(self):
        from otto.ui.styles import EXPERT_COLORS

        keys = list(EXPERT_COLORS.keys())
        assert keys == sorted(keys)

    def test_all_hex(self):
        from otto.ui.styles import EXPERT_COLORS

        for name, color in sorted(EXPERT_COLORS.items()):
            assert re.match(r"^#[0-9A-Fa-f]{6}$", color), f"{name}: {color}"


class TestEffortColors:
    def test_four_levels(self):
        from otto.ui.styles import EFFORT_COLORS

        expected = {"high", "low", "max", "medium"}
        assert set(EFFORT_COLORS.keys()) == expected

    def test_sorted_keys(self):
        from otto.ui.styles import EFFORT_COLORS

        keys = list(EFFORT_COLORS.keys())
        assert keys == sorted(keys)


class TestSignalLabels:
    def test_sorted_keys(self):
        from otto.ui.styles import SIGNAL_LABELS

        keys = list(SIGNAL_LABELS.keys())
        assert keys == sorted(keys)

    def test_no_clinical_language(self):
        from otto.ui.styles import SIGNAL_LABELS

        clinical = {"adhd", "executive dysfunction", "deficit", "disorder"}
        for key, label in sorted(SIGNAL_LABELS.items()):
            for term in clinical:
                assert term not in label.lower(), f"Clinical term '{term}' in label: {label}"


# ── TUI Skeleton ───────────────────────────────────────────────


class TestTUI:
    def test_run_raises_not_implemented(self):
        from otto.ui.tui import run

        # Even if textual is installed, should raise NotImplementedError
        try:
            import textual  # noqa: F401
            with pytest.raises(NotImplementedError, match="not yet implemented"):
                run()
        except ImportError:
            # textual not installed — should raise ImportError
            with pytest.raises(ImportError, match="textual"):
                run()


# ── MCP: Tool Definitions ─────────────────────────────────────


class TestMCPToolDefinition:
    def test_frozen(self):
        from otto.mcp.tools import MCPToolDefinition

        tool = MCPToolDefinition(name="test", description="a test tool")
        with pytest.raises(FrozenInstanceError):
            tool.name = "other"  # type: ignore[misc]

    def test_default_schema(self):
        from otto.mcp.tools import MCPToolDefinition

        tool = MCPToolDefinition(name="test", description="a test tool")
        assert tool.input_schema == {}


class TestGetToolDefinitions:
    def test_returns_three_tools(self):
        from otto.mcp.tools import get_tool_definitions

        tools = get_tool_definitions()
        assert len(tools) == 3

    def test_sorted_by_name(self):
        from otto.mcp.tools import get_tool_definitions

        tools = get_tool_definitions()
        names = [t.name for t in tools]
        assert names == sorted(names)

    def test_expected_names(self):
        from otto.mcp.tools import get_tool_definitions

        tools = get_tool_definitions()
        names = {t.name for t in tools}
        assert names == {"otto_chat", "otto_signals", "otto_status"}

    def test_all_have_descriptions(self):
        from otto.mcp.tools import get_tool_definitions

        for tool in get_tool_definitions():
            assert tool.description
            assert len(tool.description) > 10

    def test_chat_requires_message(self):
        from otto.mcp.tools import get_tool_definitions

        tools = {t.name: t for t in get_tool_definitions()}
        chat = tools["otto_chat"]
        assert "message" in chat.input_schema.get("properties", {})
        assert "message" in chat.input_schema.get("required", [])

    def test_deterministic(self):
        from otto.mcp.tools import get_tool_definitions

        results = [
            [t.name for t in get_tool_definitions()]
            for _ in range(50)
        ]
        assert all(r == results[0] for r in results)


# ── MCP: Tool Result ──────────────────────────────────────────


class TestMCPToolResult:
    def test_frozen(self):
        from otto.mcp.server import MCPToolResult

        result = MCPToolResult(content="hello")
        with pytest.raises(FrozenInstanceError):
            result.content = "other"  # type: ignore[misc]

    def test_defaults(self):
        from otto.mcp.server import MCPToolResult

        result = MCPToolResult(content="hello")
        assert result.is_error is False
        assert result.metadata == {}


# ── MCP: Handler ──────────────────────────────────────────────


class TestOTTOMCPHandler:
    def _make_handler(self, **kwargs):
        from otto.ui.chat import ChatSession
        from otto.mcp.server import OTTOMCPHandler

        pipeline = _make_mock_pipeline(**kwargs)
        session = ChatSession(pipeline=pipeline)
        return OTTOMCPHandler(session=session)

    def test_list_tools(self):
        from otto.mcp.server import OTTOMCPHandler

        tools = OTTOMCPHandler.list_tools()
        assert len(tools) == 3

    def test_handle_chat(self):
        handler = self._make_handler(content="hi there")
        result = handler.handle("otto_chat", {"message": "hello"})
        assert result.content == "hi there"
        assert result.is_error is False

    def test_handle_chat_empty_message(self):
        handler = self._make_handler()
        result = handler.handle("otto_chat", {"message": ""})
        assert result.is_error is True

    def test_handle_chat_whitespace_message(self):
        handler = self._make_handler()
        result = handler.handle("otto_chat", {"message": "   "})
        assert result.is_error is True

    def test_handle_chat_metadata(self):
        handler = self._make_handler(expert="protector")
        result = handler.handle("otto_chat", {"message": "help"})
        assert "expert" in result.metadata

    def test_handle_signals_no_services(self):
        handler = self._make_handler()
        result = handler.handle("otto_signals", {})
        assert "no services" in result.content.lower()

    def test_handle_signals_with_services(self):
        from otto.ui.chat import ChatSession
        from otto.mcp.server import OTTOMCPHandler

        pipeline = _make_mock_pipeline()
        registry = MagicMock()
        sig = MagicMock()
        sig.category = "time_period"
        sig.value = "morning"
        sig.confidence = 0.95
        registry.get_all_signals.return_value = [sig]

        session = ChatSession(pipeline=pipeline, services=registry)
        handler = OTTOMCPHandler(session=session)
        result = handler.handle("otto_signals", {})

        assert "time_period" in result.content
        assert "morning" in result.content
        assert result.metadata["signal_count"] == 1

    def test_handle_signals_empty(self):
        from otto.ui.chat import ChatSession
        from otto.mcp.server import OTTOMCPHandler

        pipeline = _make_mock_pipeline()
        registry = MagicMock()
        registry.get_all_signals.return_value = []

        session = ChatSession(pipeline=pipeline, services=registry)
        handler = OTTOMCPHandler(session=session)
        result = handler.handle("otto_signals", {})

        assert "no signals" in result.content.lower()

    def test_handle_status(self):
        handler = self._make_handler()
        result = handler.handle("otto_status", {})
        assert "0 exchanges" in result.content
        assert "exchange_count" in result.metadata

    def test_handle_unknown_tool(self):
        handler = self._make_handler()
        result = handler.handle("nonexistent_tool", {})
        assert result.is_error is True
        assert "unknown" in result.content.lower()


# ── Constitutional Language Check ──────────────────────────────


CLINICAL_TERMS = {
    "adhd", "executive dysfunction", "deficit", "disorder",
    "neurodivergent deficit", "diagnosis", "symptom",
}

MINIMIZING_TERMS = {"just", "simply", "easy"}


class TestConstitutionalLanguage:
    """Verify ALL user-facing strings are constitutional."""

    def _get_all_descriptions(self) -> list[tuple[str, str]]:
        """Collect all user-facing strings with their source."""
        from otto.ui.dashboard import EXPERT_DESCRIPTIONS, EFFORT_DESCRIPTIONS
        from otto.ui.styles import SIGNAL_LABELS

        items = []
        for k, v in sorted(EXPERT_DESCRIPTIONS.items()):
            items.append((f"EXPERT_DESCRIPTIONS[{k}]", v))
        for k, v in sorted(EFFORT_DESCRIPTIONS.items()):
            items.append((f"EFFORT_DESCRIPTIONS[{k}]", v))
        for k, v in sorted(SIGNAL_LABELS.items()):
            items.append((f"SIGNAL_LABELS[{k}]", v))
        return items

    def test_no_clinical_language(self):
        for source, text in self._get_all_descriptions():
            text_lower = text.lower()
            for term in CLINICAL_TERMS:
                assert term not in text_lower, (
                    f"Clinical term '{term}' found in {source}: {text}"
                )

    def test_no_minimizing_language(self):
        for source, text in self._get_all_descriptions():
            words = set(text.lower().split())
            for term in MINIMIZING_TERMS:
                assert term not in words, (
                    f"Minimizing term '{term}' found in {source}: {text}"
                )

    def test_mcp_tool_descriptions_constitutional(self):
        from otto.mcp.tools import get_tool_definitions

        for tool in get_tool_definitions():
            text_lower = tool.description.lower()
            for term in CLINICAL_TERMS:
                assert term not in text_lower, (
                    f"Clinical term '{term}' in MCP tool {tool.name}: {tool.description}"
                )

    def test_mcp_error_messages_constitutional(self):
        """Verify MCP error messages don't use clinical language."""
        from otto.ui.chat import ChatSession
        from otto.mcp.server import OTTOMCPHandler

        pipeline = _make_mock_pipeline()
        session = ChatSession(pipeline=pipeline)
        handler = OTTOMCPHandler(session=session)

        # Test all error paths
        errors = [
            handler.handle("unknown", {}),
            handler.handle("otto_chat", {"message": ""}),
            handler.handle("otto_signals", {}),  # no services
        ]
        for result in errors:
            text_lower = result.content.lower()
            for term in CLINICAL_TERMS:
                assert term not in text_lower

    def test_compaction_descriptions_constitutional(self):
        from otto.ui.dashboard import CognitiveSummary

        for util in [0.1, 0.3, 0.5, 0.65, 0.8, 0.95]:
            desc = CognitiveSummary.describe_compaction(util)
            desc_lower = desc.lower()
            for term in CLINICAL_TERMS:
                assert term not in desc_lower


# ── Determinism ────────────────────────────────────────────────


class TestDeterminism:
    def test_expert_descriptions_sorted(self):
        from otto.ui.dashboard import EXPERT_DESCRIPTIONS

        keys = list(EXPERT_DESCRIPTIONS.keys())
        assert keys == sorted(keys)

    def test_effort_descriptions_sorted(self):
        from otto.ui.dashboard import EFFORT_DESCRIPTIONS

        keys = list(EFFORT_DESCRIPTIONS.keys())
        assert keys == sorted(keys)

    def test_expert_colors_sorted(self):
        from otto.ui.styles import EXPERT_COLORS

        keys = list(EXPERT_COLORS.keys())
        assert keys == sorted(keys)

    def test_effort_colors_sorted(self):
        from otto.ui.styles import EFFORT_COLORS

        keys = list(EFFORT_COLORS.keys())
        assert keys == sorted(keys)

    def test_signal_labels_sorted(self):
        from otto.ui.styles import SIGNAL_LABELS

        keys = list(SIGNAL_LABELS.keys())
        assert keys == sorted(keys)

    def test_mcp_tools_deterministic_100x(self):
        from otto.mcp.tools import get_tool_definitions

        baseline = [(t.name, t.description) for t in get_tool_definitions()]
        for _ in range(100):
            current = [(t.name, t.description) for t in get_tool_definitions()]
            assert current == baseline

    def test_cognitive_summary_deterministic(self):
        from otto.ui.dashboard import CognitiveSummary, DashboardState

        state = DashboardState(
            primary_expert="executor",
            supporting_experts=("decomposer",),
            effort_level="medium",
            active_signals=(),
            compaction_utilization=0.5,
            exchange_count=10,
            session_duration_minutes=30.0,
        )
        baseline = CognitiveSummary.describe_state(state)
        for _ in range(100):
            assert CognitiveSummary.describe_state(state) == baseline


# ── Package Exports ────────────────────────────────────────────


class TestUIExports:
    def test_ui_package_exports(self):
        from otto.ui import (
            ChatMessage,
            ChatSession,
            CognitiveSummary,
            ConversationHistory,
            DashboardState,
            DEFAULT_THEME,
            EFFORT_COLORS,
            EFFORT_DESCRIPTIONS,
            EXPERT_COLORS,
            EXPERT_DESCRIPTIONS,
            SIGNAL_LABELS,
            ThemeColors,
        )
        assert ChatMessage is not None
        assert ChatSession is not None

    def test_mcp_package_exports(self):
        from otto.mcp import (
            MCPToolDefinition,
            MCPToolResult,
            OTTOMCPHandler,
            get_tool_definitions,
        )
        assert MCPToolDefinition is not None
        assert OTTOMCPHandler is not None
