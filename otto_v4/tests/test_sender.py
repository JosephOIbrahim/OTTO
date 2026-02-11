"""Tests for outbound nudge sender (Phase 6.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from otto.models import Commitment
from otto.sender import NudgeSender
from otto.state import StateStore
from otto.transport.cli_transport import CliTransport


@pytest.fixture()
def state_store(tmp_path) -> StateStore:
    return StateStore(db_path=str(tmp_path / "state.db"))


@pytest.fixture()
def transport() -> CliTransport:
    return CliTransport(capture=True)


@pytest.fixture()
def sample_commitment() -> Commitment:
    return Commitment(
        raw_message="I'll send the report to Sarah",
        commitment_text="send the report to Sarah",
        who_to="Sarah",
        source_chat="test",
        deadline=datetime.now(timezone.utc) - timedelta(days=2),
        deadline_source="manual",
    )


@pytest.fixture()
def sender(transport, state_store) -> NudgeSender:
    return NudgeSender(transport=transport, state_store=state_store)


class TestSendNudgeInGreen:
    @pytest.mark.asyncio
    async def test_nudge_sent_successfully(self, sender, transport, sample_commitment):
        attempt = await sender.send_nudge(sample_commitment, "user")
        assert attempt.success is True
        assert attempt.suppressed is False
        assert attempt.reason == "sent"
        assert len(transport.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_nudge_text_contains_commitment(self, sender, transport, sample_commitment):
        await sender.send_nudge(sample_commitment, "user")
        _, text = transport.sent_messages[0]
        assert "send the report to Sarah" in text

    @pytest.mark.asyncio
    async def test_nudge_increments_sent_count(self, sender, state_store, sample_commitment):
        await sender.send_nudge(sample_commitment, "user")
        state = state_store.load()
        assert state.nudges_sent_today == 1


class TestSendSuppressedInRed:
    @pytest.mark.asyncio
    async def test_red_burnout_suppresses(self, sender, state_store, transport, sample_commitment):
        state_store.set_burnout("RED")
        attempt = await sender.send_nudge(sample_commitment, "user")
        assert attempt.success is False
        assert attempt.suppressed is True
        assert "RED" in attempt.reason
        # No message should have been sent
        assert len(transport.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_suppression_increments_counter(self, sender, state_store, sample_commitment):
        state_store.set_burnout("RED")
        await sender.send_nudge(sample_commitment, "user")
        state = state_store.load()
        assert state.suppressed_count == 1


class TestSendSuppressedLowEffectiveness:
    @pytest.mark.asyncio
    async def test_low_effectiveness_suppresses(self, sender, state_store, transport, sample_commitment):
        # Set up: 4 nudges sent, 0 completed -> effectiveness 0.0
        for _ in range(4):
            state_store.increment_nudges_sent()
        attempt = await sender.send_nudge(sample_commitment, "user")
        assert attempt.success is False
        assert attempt.suppressed is True
        assert len(transport.sent_messages) == 0


class TestSendSuppressedOrangeDepleted:
    @pytest.mark.asyncio
    async def test_orange_depleted_suppresses(self, sender, state_store, transport, sample_commitment):
        state_store.set_burnout("ORANGE")
        state_store.set_energy("depleted")
        attempt = await sender.send_nudge(sample_commitment, "user")
        assert attempt.success is False
        assert attempt.suppressed is True
        assert len(transport.sent_messages) == 0


class TestDeliveryTracking:
    @pytest.mark.asyncio
    async def test_attempts_tracked(self, sender, sample_commitment):
        await sender.send_nudge(sample_commitment, "user")
        assert len(sender.attempts) == 1
        assert sender.successful_count == 1
        assert sender.suppressed_count == 0

    @pytest.mark.asyncio
    async def test_suppressed_attempts_tracked(self, sender, state_store, sample_commitment):
        state_store.set_burnout("RED")
        await sender.send_nudge(sample_commitment, "user")
        assert len(sender.attempts) == 1
        assert sender.successful_count == 0
        assert sender.suppressed_count == 1

    @pytest.mark.asyncio
    async def test_multiple_attempts(self, sender, sample_commitment):
        for _ in range(3):
            await sender.send_nudge(sample_commitment, "user")
        assert len(sender.attempts) == 3
        assert sender.successful_count == 3

    @pytest.mark.asyncio
    async def test_mixed_attempts(self, sender, state_store, sample_commitment):
        # 2 successful sends
        await sender.send_nudge(sample_commitment, "user")
        await sender.send_nudge(sample_commitment, "user")
        # Then RED burnout
        state_store.set_burnout("RED")
        await sender.send_nudge(sample_commitment, "user")

        assert sender.successful_count == 2
        assert sender.suppressed_count == 1
        assert len(sender.attempts) == 3


class TestConstitutionalGateBeforeSend:
    @pytest.mark.asyncio
    async def test_transport_never_called_when_suppressed(self, state_store, sample_commitment):
        """The transport should NEVER be called when constitutional gate blocks."""
        transport = CliTransport(capture=True)
        sender = NudgeSender(transport=transport, state_store=state_store)

        state_store.set_burnout("RED")
        await sender.send_nudge(sample_commitment, "user")

        # Transport must not have been called
        assert transport.sent_messages == []
