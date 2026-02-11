"""Tests for transport protocol and CLI transport (Phase 6.1)."""

from __future__ import annotations

import pytest

from otto.transport.base import DeliveryResult, Message, Transport
from otto.transport.cli_transport import CliTransport


class TestTransportProtocol:
    def test_cli_transport_is_transport(self):
        assert isinstance(CliTransport(), Transport)

    def test_transport_protocol_is_runtime_checkable(self):
        """Protocol should be checkable with isinstance()."""

        class FakeTransport:
            @property
            def name(self) -> str:
                return "fake"

            async def send(self, recipient: str, text: str) -> DeliveryResult:
                return DeliveryResult(success=True, transport="fake")

        assert isinstance(FakeTransport(), Transport)

    def test_non_transport_fails_check(self):
        class NotATransport:
            pass

        assert not isinstance(NotATransport(), Transport)


class TestMessage:
    def test_message_creation(self):
        msg = Message(text="hello", sender="user", source="cli")
        assert msg.text == "hello"
        assert msg.sender == "user"
        assert msg.source == "cli"

    def test_message_frozen(self):
        msg = Message(text="hello")
        with pytest.raises(AttributeError):
            msg.text = "changed"  # type: ignore[misc]

    def test_message_defaults(self):
        msg = Message(text="hi")
        assert msg.sender == "user"
        assert msg.source == "unknown"
        assert msg.timestamp is not None


class TestDeliveryResult:
    def test_success_result(self):
        result = DeliveryResult(success=True, transport="cli")
        assert result.success is True
        assert result.error == ""

    def test_failure_result(self):
        result = DeliveryResult(success=False, transport="whatsapp", error="API timeout")
        assert result.success is False
        assert result.error == "API timeout"


class TestCliTransport:
    def test_name(self):
        assert CliTransport().name == "cli"

    @pytest.mark.asyncio
    async def test_send_returns_success(self):
        transport = CliTransport(capture=True)
        result = await transport.send("stdout", "Hello OTTO")
        assert result.success is True
        assert result.transport == "cli"

    @pytest.mark.asyncio
    async def test_send_captures_messages(self):
        transport = CliTransport(capture=True)
        await transport.send("user1", "Message one")
        await transport.send("user2", "Message two")
        assert len(transport.sent_messages) == 2
        assert transport.sent_messages[0] == ("user1", "Message one")
        assert transport.sent_messages[1] == ("user2", "Message two")

    @pytest.mark.asyncio
    async def test_send_to_stdout(self, capsys):
        transport = CliTransport(capture=False)
        await transport.send("stdout", "Visible message")
        captured = capsys.readouterr()
        assert "Visible message" in captured.out

    @pytest.mark.asyncio
    async def test_multiple_sends(self):
        transport = CliTransport(capture=True)
        for i in range(5):
            await transport.send("user", f"msg {i}")
        assert len(transport.sent_messages) == 5
