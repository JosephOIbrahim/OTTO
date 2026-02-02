"""
WhatsApp webhook handler.

FastAPI endpoints for receiving WhatsApp webhooks.
"""

import hashlib
import hmac
import logging
import os
from typing import Optional, Callable, Awaitable

from fastapi import APIRouter, Request, Response, HTTPException, Query

from .schemas import (
    WebhookPayload,
    IncomingMessage,
    WhatsAppContact,
    MessageType,
)


logger = logging.getLogger(__name__)


# Type for message handlers
MessageHandler = Callable[[WhatsAppContact, IncomingMessage], Awaitable[None]]


class WebhookConfig:
    """Webhook configuration."""

    def __init__(
        self,
        verify_token: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        """
        Initialize webhook config.

        Args:
            verify_token: Token for webhook verification
            app_secret: App secret for signature validation
        """
        self.verify_token = verify_token or os.environ.get(
            "WHATSAPP_VERIFY_TOKEN", "otto-voice-webhook"
        )
        self.app_secret = app_secret or os.environ.get(
            "WHATSAPP_APP_SECRET", ""
        )


class WhatsAppWebhook:
    """
    WhatsApp webhook handler.

    Provides:
    - Webhook verification endpoint
    - Message reception endpoint
    - Signature validation
    - Message type routing
    """

    def __init__(
        self,
        config: Optional[WebhookConfig] = None,
        on_text_message: Optional[MessageHandler] = None,
        on_voice_message: Optional[MessageHandler] = None,
        on_any_message: Optional[MessageHandler] = None,
    ):
        """
        Initialize webhook handler.

        Args:
            config: Webhook configuration
            on_text_message: Handler for text messages
            on_voice_message: Handler for voice messages
            on_any_message: Handler for all messages (fallback)
        """
        self.config = config or WebhookConfig()
        self._on_text_message = on_text_message
        self._on_voice_message = on_voice_message
        self._on_any_message = on_any_message
        self.router = self._create_router()

    def _create_router(self) -> APIRouter:
        """Create FastAPI router with webhook endpoints."""
        router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])

        @router.get("")
        async def verify_webhook(
            hub_mode: str = Query(..., alias="hub.mode"),
            hub_verify_token: str = Query(..., alias="hub.verify_token"),
            hub_challenge: str = Query(..., alias="hub.challenge"),
        ):
            """
            Webhook verification endpoint.

            WhatsApp sends a GET request to verify the webhook.
            """
            if hub_mode != "subscribe":
                raise HTTPException(status_code=400, detail="Invalid mode")

            if hub_verify_token != self.config.verify_token:
                logger.warning("Webhook verification failed: invalid token")
                raise HTTPException(status_code=403, detail="Invalid verify token")

            logger.info("Webhook verified successfully")
            return Response(content=hub_challenge, media_type="text/plain")

        @router.post("")
        async def receive_webhook(request: Request):
            """
            Webhook message reception endpoint.

            Receives and processes incoming WhatsApp messages.
            """
            # Validate signature if app secret is configured
            if self.config.app_secret:
                signature = request.headers.get("X-Hub-Signature-256", "")
                body = await request.body()

                if not self._verify_signature(body, signature):
                    logger.warning("Webhook signature validation failed")
                    raise HTTPException(status_code=403, detail="Invalid signature")
            else:
                body = await request.body()

            # Parse payload
            try:
                import json
                payload_data = json.loads(body)
                payload = WebhookPayload(**payload_data)
            except Exception as e:
                logger.error(f"Failed to parse webhook payload: {e}")
                raise HTTPException(status_code=400, detail="Invalid payload")

            # Process messages
            await self._process_payload(payload)

            # Always return 200 to acknowledge receipt
            return {"status": "ok"}

        return router

    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """
        Verify webhook signature.

        Args:
            body: Request body bytes
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid
        """
        if not signature.startswith("sha256="):
            return False

        expected_signature = signature[7:]  # Remove "sha256=" prefix

        computed = hmac.new(
            self.config.app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed, expected_signature)

    async def _process_payload(self, payload: WebhookPayload):
        """Process webhook payload and route messages."""
        messages = payload.get_messages()

        for contact, message in messages:
            logger.info(
                f"Received {message.type.value} message from {contact.phone_number}: "
                f"{message.content_summary}"
            )

            try:
                await self._route_message(contact, message)
            except Exception as e:
                logger.error(f"Error processing message {message.id}: {e}")

    async def _route_message(self, contact: WhatsAppContact, message: IncomingMessage):
        """Route message to appropriate handler."""
        # Voice messages get priority
        if message.is_voice_message and self._on_voice_message:
            await self._on_voice_message(contact, message)
            return

        # Text messages
        if message.type == MessageType.TEXT and self._on_text_message:
            await self._on_text_message(contact, message)
            return

        # Fallback to any message handler
        if self._on_any_message:
            await self._on_any_message(contact, message)
            return

        logger.debug(f"No handler for message type: {message.type}")

    def set_text_handler(self, handler: MessageHandler):
        """Set handler for text messages."""
        self._on_text_message = handler

    def set_voice_handler(self, handler: MessageHandler):
        """Set handler for voice messages."""
        self._on_voice_message = handler

    def set_any_handler(self, handler: MessageHandler):
        """Set handler for any message type."""
        self._on_any_message = handler


def create_webhook_router(
    on_text_message: Optional[MessageHandler] = None,
    on_voice_message: Optional[MessageHandler] = None,
    on_any_message: Optional[MessageHandler] = None,
    verify_token: Optional[str] = None,
) -> APIRouter:
    """
    Create a webhook router with handlers.

    Args:
        on_text_message: Handler for text messages
        on_voice_message: Handler for voice messages
        on_any_message: Fallback handler for all messages
        verify_token: Webhook verification token

    Returns:
        FastAPI APIRouter with webhook endpoints
    """
    config = WebhookConfig(verify_token=verify_token)
    webhook = WhatsAppWebhook(
        config=config,
        on_text_message=on_text_message,
        on_voice_message=on_voice_message,
        on_any_message=on_any_message,
    )
    return webhook.router
