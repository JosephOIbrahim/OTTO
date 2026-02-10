"""Tests for commitment detector -- mocked unit tests + real integration tests."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from otto.detector import detect_commitment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(text: str):
    """Build a fake Anthropic messages response."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


# ---------------------------------------------------------------------------
# Unit tests (mocked -- no API calls)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_commitment_detected():
    payload = json.dumps({
        "found": True,
        "commitment_text": "send the deck",
        "who_to": "Alice",
        "deadline": None,
        "deadline_source": "none",
        "confidence": 0.92,
    })
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_response(payload)
        )
        result = await detect_commitment("I'll send you the deck tomorrow", "Work")

    assert result is not None
    assert result.commitment_text == "send the deck"
    assert result.who_to == "Alice"
    assert result.source_chat == "Work"
    assert result.status == "active"


@pytest.mark.asyncio
async def test_no_commitment():
    payload = json.dumps({"found": False})
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_response(payload)
        )
        result = await detect_commitment("Sounds good!", "Friends")

    assert result is None


@pytest.mark.asyncio
async def test_api_error_returns_none():
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            side_effect=Exception("API down")
        )
        result = await detect_commitment("I'll do it", "Chat")

    assert result is None


@pytest.mark.asyncio
async def test_low_confidence_returns_none():
    payload = json.dumps({
        "found": True,
        "commitment_text": "maybe do something",
        "who_to": "unknown",
        "deadline": None,
        "deadline_source": "none",
        "confidence": 0.4,
    })
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_response(payload)
        )
        result = await detect_commitment("Maybe I'll look into it", "Chat")

    assert result is None


@pytest.mark.asyncio
async def test_deadline_parsed():
    payload = json.dumps({
        "found": True,
        "commitment_text": "send the report",
        "who_to": "Alice",
        "deadline": "2026-03-15T00:00:00",
        "deadline_source": "explicit",
        "confidence": 0.9,
    })
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_response(payload)
        )
        result = await detect_commitment("I'll send the report by March 15", "Work")

    assert result is not None
    assert result.deadline is not None
    assert result.deadline.year == 2026
    assert result.deadline.month == 3
    assert result.deadline.day == 15
    assert result.deadline_source == "explicit"


@pytest.mark.asyncio
async def test_null_deadline_stays_none():
    payload = json.dumps({
        "found": True,
        "commitment_text": "handle it",
        "who_to": "Bob",
        "deadline": None,
        "deadline_source": "none",
        "confidence": 0.85,
    })
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_response(payload)
        )
        result = await detect_commitment("I'll handle it", "Chat")

    assert result is not None
    assert result.deadline is None


@pytest.mark.asyncio
async def test_markdown_fenced_json_stripped():
    """Claude sometimes wraps JSON in ```json ... ``` code fences."""
    inner = json.dumps({
        "found": True,
        "commitment_text": "send the deck",
        "who_to": "Alice",
        "deadline": None,
        "deadline_source": "none",
        "confidence": 0.92,
    })
    fenced = f"```json\n{inner}\n```"
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_response(fenced)
        )
        result = await detect_commitment("I'll send the deck", "Work")

    assert result is not None
    assert result.commitment_text == "send the deck"


@pytest.mark.asyncio
async def test_invalid_json_returns_none():
    with patch("otto.detector.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(
            return_value=_mock_response("this is not json at all")
        )
        result = await detect_commitment("I'll do it", "Chat")

    assert result is None


# ---------------------------------------------------------------------------
# Integration tests (real API -- skip in CI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_commitment_deck():
    result = await detect_commitment("I'll send you the deck tomorrow", "Work Chat")
    assert result is not None
    assert result.commitment_text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_no_commitment():
    result = await detect_commitment("Sounds good!", "Work Chat")
    assert result is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_follow_up():
    result = await detect_commitment(
        "Let me follow up with Sandra about that", "Project Chat"
    )
    assert result is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_no_commitment_funny():
    result = await detect_commitment("Ha that's hilarious", "Friends")
    assert result is None
