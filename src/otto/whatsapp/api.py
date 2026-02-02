"""
WhatsApp Cloud API client.

Provides async interface to WhatsApp Business Cloud API.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Union

import aiohttp

from .schemas import (
    OutgoingTextMessage,
    OutgoingAudioMessage,
    OutgoingReaction,
    MessageSendResponse,
    MediaUploadResponse,
)


logger = logging.getLogger(__name__)


class WhatsAppAPIError(Exception):
    """WhatsApp API error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


@dataclass
class WhatsAppConfig:
    """Configuration for WhatsApp API client."""

    phone_number_id: str = field(
        default_factory=lambda: os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    )
    """WhatsApp Business Phone Number ID."""

    access_token: str = field(
        default_factory=lambda: os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
    )
    """WhatsApp Business API access token."""

    api_version: str = "v18.0"
    """Graph API version."""

    base_url: str = "https://graph.facebook.com"
    """Graph API base URL."""

    timeout: float = 30.0
    """Request timeout in seconds."""

    max_retries: int = 3
    """Maximum retry attempts."""

    @property
    def messages_url(self) -> str:
        """URL for sending messages."""
        return f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"

    @property
    def media_url(self) -> str:
        """URL for media operations."""
        return f"{self.base_url}/{self.api_version}/{self.phone_number_id}/media"

    def validate(self) -> list[str]:
        """Validate configuration."""
        errors = []
        if not self.phone_number_id:
            errors.append("phone_number_id is required")
        if not self.access_token:
            errors.append("access_token is required")
        return errors


class WhatsAppAPI:
    """
    Async client for WhatsApp Business Cloud API.

    Provides methods for:
    - Sending text messages
    - Sending voice/audio messages
    - Uploading media
    - Downloading media
    - Sending reactions
    """

    def __init__(self, config: Optional[WhatsAppConfig] = None):
        """
        Initialize the API client.

        Args:
            config: API configuration (uses env vars if None)
        """
        self.config = config or WhatsAppConfig()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self.config.access_token}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        await self.close()

    async def _request(
        self,
        method: str,
        url: str,
        json: Optional[dict] = None,
        data: Optional[aiohttp.FormData] = None,
        headers: Optional[dict] = None,
    ) -> dict:
        """Make an API request with retry logic."""
        session = await self._get_session()

        # Merge headers
        request_headers = dict(session.headers)
        if headers:
            request_headers.update(headers)

        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                async with session.request(
                    method,
                    url,
                    json=json,
                    data=data,
                    headers=request_headers,
                ) as response:
                    response_data = await response.json()

                    if response.status >= 400:
                        error = response_data.get("error", {})
                        raise WhatsAppAPIError(
                            message=error.get("message", "Unknown error"),
                            status_code=response.status,
                            error_code=error.get("code"),
                            details=error,
                        )

                    return response_data

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    continue
                raise WhatsAppAPIError(
                    message=f"Request failed after {self.config.max_retries} attempts: {e}",
                    details={"original_error": str(e)},
                )

        raise last_error  # Should not reach here

    async def send_text(
        self,
        to: str,
        text: str,
        preview_url: bool = False,
    ) -> MessageSendResponse:
        """
        Send a text message.

        Args:
            to: Recipient phone number (with country code)
            text: Message text
            preview_url: Whether to show URL previews

        Returns:
            MessageSendResponse with message ID
        """
        message = OutgoingTextMessage.create(to, text, preview_url)
        response = await self._request(
            "POST",
            self.config.messages_url,
            json=message.model_dump()
        )
        return MessageSendResponse(**response)

    async def send_audio(
        self,
        to: str,
        media_id: Optional[str] = None,
        url: Optional[str] = None,
    ) -> MessageSendResponse:
        """
        Send an audio message.

        Args:
            to: Recipient phone number
            media_id: Media ID from upload (preferred)
            url: Public URL to audio file (alternative)

        Returns:
            MessageSendResponse with message ID
        """
        if media_id:
            message = OutgoingAudioMessage.create_from_id(to, media_id)
        elif url:
            message = OutgoingAudioMessage.create_from_url(to, url)
        else:
            raise ValueError("Either media_id or url must be provided")

        response = await self._request(
            "POST",
            self.config.messages_url,
            json=message.model_dump()
        )
        return MessageSendResponse(**response)

    async def send_reaction(
        self,
        to: str,
        message_id: str,
        emoji: str,
    ) -> MessageSendResponse:
        """
        Send a reaction to a message.

        Args:
            to: Recipient phone number
            message_id: ID of message to react to
            emoji: Emoji to use as reaction

        Returns:
            MessageSendResponse
        """
        message = OutgoingReaction.create(to, message_id, emoji)
        response = await self._request(
            "POST",
            self.config.messages_url,
            json=message.model_dump()
        )
        return MessageSendResponse(**response)

    async def upload_media(
        self,
        media_data: bytes,
        mime_type: str,
        filename: str = "audio.ogg",
    ) -> MediaUploadResponse:
        """
        Upload media to WhatsApp servers.

        Args:
            media_data: Raw media bytes
            mime_type: MIME type (e.g., "audio/ogg")
            filename: Filename for the media

        Returns:
            MediaUploadResponse with media ID
        """
        form = aiohttp.FormData()
        form.add_field(
            "file",
            media_data,
            filename=filename,
            content_type=mime_type,
        )
        form.add_field("messaging_product", "whatsapp")
        form.add_field("type", mime_type)

        session = await self._get_session()

        # Need different headers for multipart upload
        async with session.post(
            self.config.media_url,
            data=form,
            headers={"Authorization": f"Bearer {self.config.access_token}"},
        ) as response:
            response_data = await response.json()

            if response.status >= 400:
                error = response_data.get("error", {})
                raise WhatsAppAPIError(
                    message=error.get("message", "Upload failed"),
                    status_code=response.status,
                    error_code=error.get("code"),
                    details=error,
                )

            return MediaUploadResponse(**response_data)

    async def download_media(self, media_id: str) -> bytes:
        """
        Download media by ID.

        Args:
            media_id: Media ID from incoming message

        Returns:
            Raw media bytes
        """
        # First, get the media URL
        url = f"{self.config.base_url}/{self.config.api_version}/{media_id}"
        response = await self._request("GET", url)

        media_url = response.get("url")
        if not media_url:
            raise WhatsAppAPIError(
                message="No media URL in response",
                details=response,
            )

        # Download the actual media
        session = await self._get_session()
        async with session.get(
            media_url,
            headers={"Authorization": f"Bearer {self.config.access_token}"},
        ) as response:
            if response.status >= 400:
                raise WhatsAppAPIError(
                    message="Failed to download media",
                    status_code=response.status,
                )
            return await response.read()

    async def mark_as_read(self, message_id: str) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: ID of message to mark as read

        Returns:
            True if successful
        """
        try:
            await self._request(
                "POST",
                self.config.messages_url,
                json={
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message_id,
                }
            )
            return True
        except WhatsAppAPIError as e:
            logger.warning(f"Failed to mark message as read: {e}")
            return False


# Convenience function
def create_api(
    phone_number_id: Optional[str] = None,
    access_token: Optional[str] = None,
) -> WhatsAppAPI:
    """
    Create a WhatsApp API client.

    Args:
        phone_number_id: WhatsApp Business Phone Number ID
        access_token: API access token

    Returns:
        Configured WhatsAppAPI instance
    """
    config = WhatsAppConfig()
    if phone_number_id:
        config.phone_number_id = phone_number_id
    if access_token:
        config.access_token = access_token

    errors = config.validate()
    if errors:
        logger.warning(f"WhatsApp config validation warnings: {errors}")

    return WhatsAppAPI(config)
