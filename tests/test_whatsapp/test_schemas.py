"""
Tests for WhatsApp schemas.

Tests Pydantic models for WhatsApp Cloud API.
"""

import pytest
from datetime import datetime
from otto.whatsapp import (
    # Message types
    MessageType,
    MessageStatus,
    # Incoming messages
    IncomingMessage,
    WhatsAppContact,
    TextContent,
    AudioContent,
    ImageContent,
    LocationContent,
    # Webhook
    WebhookPayload,
    WebhookEntry,
    WebhookChange,
    WebhookValue,
    # Outgoing messages
    OutgoingTextMessage,
    OutgoingAudioMessage,
    OutgoingReaction,
    MessageSendResponse,
    MediaUploadResponse,
    # Session
    ConversationState,
)


class TestMessageType:
    """Test MessageType enum."""

    def test_text_type(self):
        """Should have TEXT type."""
        assert MessageType.TEXT == "text"

    def test_audio_type(self):
        """Should have AUDIO type."""
        assert MessageType.AUDIO == "audio"

    def test_image_type(self):
        """Should have IMAGE type."""
        assert MessageType.IMAGE == "image"

    def test_all_types_are_strings(self):
        """All types should be string values."""
        for msg_type in MessageType:
            assert isinstance(msg_type.value, str)


class TestWhatsAppContact:
    """Test WhatsAppContact model."""

    def test_creation(self):
        """Should create contact with required fields."""
        contact = WhatsAppContact(
            profile={"name": "John Doe"},
            wa_id="1234567890"
        )

        assert contact.wa_id == "1234567890"
        assert contact.name == "John Doe"
        assert contact.phone_number == "1234567890"

    def test_missing_name_defaults(self):
        """Should default name to 'Unknown' if missing."""
        contact = WhatsAppContact(
            profile={},
            wa_id="1234567890"
        )

        assert contact.name == "Unknown"


class TestTextContent:
    """Test TextContent model."""

    def test_creation(self):
        """Should create text content."""
        content = TextContent(body="Hello world")
        assert content.body == "Hello world"

    def test_empty_body_allowed(self):
        """Should allow empty body."""
        content = TextContent(body="")
        assert content.body == ""


class TestAudioContent:
    """Test AudioContent model."""

    def test_creation(self):
        """Should create audio content."""
        content = AudioContent(
            id="media123",
            mime_type="audio/ogg",
            voice=True
        )

        assert content.id == "media123"
        assert content.mime_type == "audio/ogg"
        assert content.voice is True

    def test_defaults(self):
        """Should have sensible defaults."""
        content = AudioContent(id="media123")

        assert content.mime_type == "audio/ogg"
        assert content.voice is False


class TestIncomingMessage:
    """Test IncomingMessage model."""

    def test_text_message(self):
        """Should create text message."""
        message = IncomingMessage(
            **{"from": "1234567890"},
            id="msg123",
            timestamp="1234567890",
            type=MessageType.TEXT,
            text=TextContent(body="Hello")
        )

        assert message.sender_phone == "1234567890"
        assert message.id == "msg123"
        assert message.type == MessageType.TEXT
        assert message.text.body == "Hello"

    def test_voice_message(self):
        """Should create voice message."""
        message = IncomingMessage(
            **{"from": "1234567890"},
            id="msg123",
            timestamp="1234567890",
            type=MessageType.AUDIO,
            audio=AudioContent(id="media123", voice=True)
        )

        assert message.is_voice_message is True
        assert message.audio.id == "media123"

    def test_is_voice_message_false_for_text(self):
        """is_voice_message should be False for text."""
        message = IncomingMessage(
            **{"from": "1234567890"},
            id="msg123",
            timestamp="1234567890",
            type=MessageType.TEXT,
            text=TextContent(body="Hello")
        )

        assert message.is_voice_message is False

    def test_message_timestamp(self):
        """Should parse timestamp to datetime."""
        message = IncomingMessage(
            **{"from": "1234567890"},
            id="msg123",
            timestamp="1704067200",  # 2024-01-01 00:00:00 UTC
            type=MessageType.TEXT,
            text=TextContent(body="Hello")
        )

        dt = message.message_timestamp
        assert isinstance(dt, datetime)
        assert dt.year == 2024

    def test_content_summary_text(self):
        """Should summarize text content."""
        message = IncomingMessage(
            **{"from": "1234567890"},
            id="msg123",
            timestamp="1234567890",
            type=MessageType.TEXT,
            text=TextContent(body="Hello world")
        )

        assert message.content_summary == "Hello world"

    def test_content_summary_voice(self):
        """Should summarize voice content."""
        message = IncomingMessage(
            **{"from": "1234567890"},
            id="msg123",
            timestamp="1234567890",
            type=MessageType.AUDIO,
            audio=AudioContent(id="media123")
        )

        assert message.content_summary == "[Voice message]"


class TestWebhookPayload:
    """Test WebhookPayload model."""

    def test_parse_basic_payload(self):
        """Should parse basic webhook payload."""
        data = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "business123",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {},
                        "contacts": [{
                            "profile": {"name": "John"},
                            "wa_id": "1234567890"
                        }],
                        "messages": [{
                            "from": "1234567890",
                            "id": "msg123",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "Hello"}
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        payload = WebhookPayload(**data)

        assert payload.object == "whatsapp_business_account"
        assert len(payload.entry) == 1

    def test_get_messages(self):
        """Should extract messages with contacts."""
        data = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "business123",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {},
                        "contacts": [{
                            "profile": {"name": "John"},
                            "wa_id": "1234567890"
                        }],
                        "messages": [{
                            "from": "1234567890",
                            "id": "msg123",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {"body": "Hello"}
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        payload = WebhookPayload(**data)
        messages = payload.get_messages()

        assert len(messages) == 1
        contact, message = messages[0]
        assert contact.name == "John"
        assert message.text.body == "Hello"


class TestOutgoingTextMessage:
    """Test OutgoingTextMessage model."""

    def test_create(self):
        """Should create text message."""
        message = OutgoingTextMessage.create(
            to="1234567890",
            body="Hello world"
        )

        assert message.to == "1234567890"
        assert message.type == "text"
        assert message.text["body"] == "Hello world"

    def test_preview_url(self):
        """Should set preview_url flag."""
        message = OutgoingTextMessage.create(
            to="1234567890",
            body="Check https://example.com",
            preview_url=True
        )

        assert message.text["preview_url"] is True


class TestOutgoingAudioMessage:
    """Test OutgoingAudioMessage model."""

    def test_create_from_id(self):
        """Should create audio message from media ID."""
        message = OutgoingAudioMessage.create_from_id(
            to="1234567890",
            media_id="media123"
        )

        assert message.to == "1234567890"
        assert message.type == "audio"
        assert message.audio["id"] == "media123"

    def test_create_from_url(self):
        """Should create audio message from URL."""
        message = OutgoingAudioMessage.create_from_url(
            to="1234567890",
            url="https://example.com/audio.ogg"
        )

        assert message.audio["link"] == "https://example.com/audio.ogg"


class TestOutgoingReaction:
    """Test OutgoingReaction model."""

    def test_create(self):
        """Should create reaction message."""
        reaction = OutgoingReaction.create(
            to="1234567890",
            message_id="msg123",
            emoji="👍"
        )

        assert reaction.to == "1234567890"
        assert reaction.type == "reaction"
        assert reaction.reaction["message_id"] == "msg123"
        assert reaction.reaction["emoji"] == "👍"


class TestMessageSendResponse:
    """Test MessageSendResponse model."""

    def test_message_id_property(self):
        """Should extract message ID from response."""
        response = MessageSendResponse(
            messaging_product="whatsapp",
            contacts=[{"wa_id": "1234567890"}],
            messages=[{"id": "wamid.123"}]
        )

        assert response.message_id == "wamid.123"

    def test_message_id_none_if_empty(self):
        """Should return None if no messages."""
        response = MessageSendResponse(
            messaging_product="whatsapp",
            contacts=[],
            messages=[]
        )

        assert response.message_id is None


class TestConversationState:
    """Test ConversationState model."""

    def test_creation(self):
        """Should create conversation state."""
        state = ConversationState(phone_number="1234567890")

        assert state.phone_number == "1234567890"
        assert state.message_count == 0
        assert state.voice_message_count == 0

    def test_update_on_message(self):
        """Should update state on message."""
        state = ConversationState(phone_number="1234567890")
        state.update_on_message("msg123")

        assert state.last_message_id == "msg123"
        assert state.message_count == 1
        assert state.last_message_time is not None

    def test_update_on_voice(self):
        """Should update state on voice message."""
        state = ConversationState(phone_number="1234567890")
        state.update_on_voice("msg123")

        assert state.message_count == 1
        assert state.voice_message_count == 1
