"""WhatsApp outbound transport for OTTO v5.1.

Sends messages via Meta's WhatsApp Cloud API (Graph API v21.0).
Requires a phone number ID and access token from Meta Business.
"""

from __future__ import annotations

import re

import httpx

from .base import DeliveryResult
from ..log import get_logger

_log = get_logger(__name__)

_GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class WhatsAppTransport:
    """Transport that sends messages via WhatsApp Cloud API.

    Parameters
    ----------
    phone_number_id:
        The WhatsApp Business phone number ID from Meta.
    access_token:
        The access token for the WhatsApp Cloud API.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        phone_number_id: str,
        access_token: str,
        *,
        timeout: float = 10.0,
    ) -> None:
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._client = httpx.AsyncClient(timeout=timeout)
        self._url = f"{_GRAPH_API_BASE}/{phone_number_id}/messages"

    @property
    def name(self) -> str:
        return "whatsapp"

    @staticmethod
    def _normalize_phone(recipient: str) -> str:
        """Strip non-digit characters from a phone number.

        Parameters
        ----------
        recipient:
            Raw phone number string (e.g. "+1 (555) 123-4567").

        Returns
        -------
        str
            Digits only (e.g. "15551234567").
        """
        return re.sub(r"\D", "", recipient)

    async def send(self, recipient: str, text: str) -> DeliveryResult:
        """Send a text message via WhatsApp Cloud API.

        Parameters
        ----------
        recipient:
            Phone number to send to (will be normalized).
        text:
            The message content.

        Returns
        -------
        DeliveryResult
            Whether delivery succeeded. Never raises.
        """
        phone = self._normalize_phone(recipient)
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"body": text},
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            response = await self._client.post(
                self._url,
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            _log.warning("WhatsApp send failed (network): %s", exc)
            return DeliveryResult(
                success=False,
                transport="whatsapp",
                error=f"network error: {exc}",
            )

        if response.status_code == 200:
            _log.debug("WhatsApp send to %s: OK", phone)
            return DeliveryResult(success=True, transport="whatsapp")

        _log.warning(
            "WhatsApp send to %s failed: HTTP %d",
            phone,
            response.status_code,
        )
        return DeliveryResult(
            success=False,
            transport="whatsapp",
            error=f"HTTP {response.status_code}: {response.text}",
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
