"""Tests for WhatsApp outbound transport (v5.1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from otto.transport.base import DeliveryResult, Transport
from otto.transport.whatsapp_transport import WhatsAppTransport


def _make_transport() -> WhatsAppTransport:
    return WhatsAppTransport(
        phone_number_id="123456",
        access_token="test-token",
    )


class TestWhatsAppTransport:
    def test_name(self):
        transport = _make_transport()
        assert transport.name == "whatsapp"

    def test_is_transport(self):
        assert isinstance(_make_transport(), Transport)

    @pytest.mark.asyncio
    async def test_send_success(self):
        transport = _make_transport()
        mock_response = httpx.Response(
            status_code=200,
            json={"messages": [{"id": "wamid.abc123"}]},
            request=httpx.Request("POST", "https://example.com"),
        )
        with patch.object(
            transport._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await transport.send("+1 555 123 4567", "Hello")
        assert result.success is True
        assert result.transport == "whatsapp"
        assert result.error == ""

    @pytest.mark.asyncio
    async def test_send_failure_returns_error(self):
        transport = _make_transport()
        mock_response = httpx.Response(
            status_code=401,
            text="Unauthorized",
            request=httpx.Request("POST", "https://example.com"),
        )
        with patch.object(
            transport._client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await transport.send("15551234567", "Hello")
        assert result.success is False
        assert result.transport == "whatsapp"
        assert "401" in result.error

    @pytest.mark.asyncio
    async def test_send_network_error(self):
        transport = _make_transport()
        with patch.object(
            transport._client,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await transport.send("15551234567", "Hello")
        assert result.success is False
        assert result.transport == "whatsapp"
        assert "network error" in result.error.lower()

    def test_formats_phone_number(self):
        assert WhatsAppTransport._normalize_phone("+1 (555) 123-4567") == "15551234567"
        assert WhatsAppTransport._normalize_phone("15551234567") == "15551234567"
        assert WhatsAppTransport._normalize_phone("+44 20 7946 0958") == "442079460958"
        assert WhatsAppTransport._normalize_phone("") == ""

    @pytest.mark.asyncio
    async def test_determinism(self):
        """Same input produces same output across iterations."""
        results: list[DeliveryResult] = []
        for _ in range(10):
            transport = _make_transport()
            mock_response = httpx.Response(
                status_code=200,
                json={"messages": [{"id": "wamid.abc123"}]},
                request=httpx.Request("POST", "https://example.com"),
            )
            with patch.object(
                transport._client, "post", new_callable=AsyncMock, return_value=mock_response
            ):
                result = await transport.send("+1 555 123 4567", "Same message")
            results.append(result)

        for result in results:
            assert result == results[0]

    @pytest.mark.asyncio
    async def test_close(self):
        transport = _make_transport()
        with patch.object(transport._client, "aclose", new_callable=AsyncMock) as mock_close:
            await transport.close()
            mock_close.assert_called_once()
