"""
Pydantic schemas for WhatsApp Cloud API.

Defines request/response models for WhatsApp Business API.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


class MessageType(str, Enum):
    """WhatsApp message types."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"
    REACTION = "reaction"
    UNKNOWN = "unknown"


class MessageStatus(str, Enum):
    """WhatsApp message status."""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


# === Incoming Message Schemas ===

class WhatsAppContact(BaseModel):
    """Contact information from webhook."""

    profile: dict = Field(default_factory=dict)
    wa_id: str = Field(..., description="WhatsApp ID (phone number)")

    @property
    def name(self) -> str:
        """Get contact name."""
        return self.profile.get("name", "Unknown")

    @property
    def phone_number(self) -> str:
        """Get phone number."""
        return self.wa_id


class TextContent(BaseModel):
    """Text message content."""

    body: str = Field(..., description="Message text")


class AudioContent(BaseModel):
    """Audio message content."""

    id: str = Field(..., description="Media ID")
    mime_type: str = Field(default="audio/ogg")
    sha256: Optional[str] = None
    voice: bool = Field(default=False, description="True if voice message")


class ImageContent(BaseModel):
    """Image message content."""

    id: str = Field(..., description="Media ID")
    mime_type: str = Field(default="image/jpeg")
    sha256: Optional[str] = None
    caption: Optional[str] = None


class DocumentContent(BaseModel):
    """Document message content."""

    id: str = Field(..., description="Media ID")
    mime_type: str
    sha256: Optional[str] = None
    filename: Optional[str] = None
    caption: Optional[str] = None


class LocationContent(BaseModel):
    """Location message content."""

    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None


class IncomingMessage(BaseModel):
    """Incoming WhatsApp message."""

    from_: str = Field(..., alias="from", description="Sender phone number")
    id: str = Field(..., description="Message ID")
    timestamp: str = Field(..., description="Unix timestamp")
    type: MessageType = Field(default=MessageType.TEXT)

    # Content fields (mutually exclusive based on type)
    text: Optional[TextContent] = None
    audio: Optional[AudioContent] = None
    image: Optional[ImageContent] = None
    document: Optional[DocumentContent] = None
    location: Optional[LocationContent] = None

    # Context for replies
    context: Optional[dict] = None

    class Config:
        populate_by_name = True

    @property
    def sender_phone(self) -> str:
        """Get sender phone number."""
        return self.from_

    @property
    def message_timestamp(self) -> datetime:
        """Get message timestamp as datetime (UTC)."""
        return datetime.fromtimestamp(int(self.timestamp), tz=timezone.utc)

    @property
    def is_voice_message(self) -> bool:
        """Check if this is a voice message."""
        return self.type == MessageType.AUDIO and self.audio is not None

    @property
    def content_summary(self) -> str:
        """Get a summary of message content."""
        if self.type == MessageType.TEXT and self.text:
            return self.text.body[:100]
        if self.type == MessageType.AUDIO:
            return "[Voice message]"
        if self.type == MessageType.IMAGE:
            return f"[Image{': ' + self.image.caption if self.image and self.image.caption else ''}]"
        if self.type == MessageType.DOCUMENT:
            return f"[Document: {self.document.filename if self.document else 'unknown'}]"
        if self.type == MessageType.LOCATION:
            return f"[Location: {self.location.name if self.location else 'unknown'}]"
        return f"[{self.type.value} message]"


class WebhookValue(BaseModel):
    """Value object in webhook payload."""

    messaging_product: str = "whatsapp"
    metadata: dict = Field(default_factory=dict)
    contacts: list[WhatsAppContact] = Field(default_factory=list)
    messages: list[IncomingMessage] = Field(default_factory=list)
    statuses: list[dict] = Field(default_factory=list)


class WebhookChange(BaseModel):
    """Change object in webhook payload."""

    value: WebhookValue
    field: str = "messages"


class WebhookEntry(BaseModel):
    """Entry in webhook payload."""

    id: str = Field(..., description="Business Account ID")
    changes: list[WebhookChange] = Field(default_factory=list)


class WebhookPayload(BaseModel):
    """Complete webhook payload from WhatsApp."""

    object: str = "whatsapp_business_account"
    entry: list[WebhookEntry] = Field(default_factory=list)

    def get_messages(self) -> list[tuple[WhatsAppContact, IncomingMessage]]:
        """Extract all messages with their contacts."""
        results = []
        for entry in self.entry:
            for change in entry.changes:
                contacts_map = {c.wa_id: c for c in change.value.contacts}
                for message in change.value.messages:
                    contact = contacts_map.get(message.from_)
                    if contact:
                        results.append((contact, message))
        return results


# === Outgoing Message Schemas ===

class OutgoingTextMessage(BaseModel):
    """Outgoing text message."""

    messaging_product: str = "whatsapp"
    recipient_type: str = "individual"
    to: str = Field(..., description="Recipient phone number")
    type: str = "text"
    text: dict = Field(..., description="Text content")

    @classmethod
    def create(cls, to: str, body: str, preview_url: bool = False) -> "OutgoingTextMessage":
        """Create a text message."""
        return cls(
            to=to,
            text={"body": body, "preview_url": preview_url}
        )


class OutgoingAudioMessage(BaseModel):
    """Outgoing audio message."""

    messaging_product: str = "whatsapp"
    recipient_type: str = "individual"
    to: str = Field(..., description="Recipient phone number")
    type: str = "audio"
    audio: dict = Field(..., description="Audio content")

    @classmethod
    def create_from_id(cls, to: str, media_id: str) -> "OutgoingAudioMessage":
        """Create an audio message from media ID."""
        return cls(
            to=to,
            audio={"id": media_id}
        )

    @classmethod
    def create_from_url(cls, to: str, url: str) -> "OutgoingAudioMessage":
        """Create an audio message from URL."""
        return cls(
            to=to,
            audio={"link": url}
        )


class OutgoingReaction(BaseModel):
    """Outgoing reaction message."""

    messaging_product: str = "whatsapp"
    recipient_type: str = "individual"
    to: str = Field(..., description="Recipient phone number")
    type: str = "reaction"
    reaction: dict = Field(..., description="Reaction content")

    @classmethod
    def create(cls, to: str, message_id: str, emoji: str) -> "OutgoingReaction":
        """Create a reaction to a message."""
        return cls(
            to=to,
            reaction={"message_id": message_id, "emoji": emoji}
        )


class MediaUploadResponse(BaseModel):
    """Response from media upload."""

    id: str = Field(..., description="Media ID")


class MessageSendResponse(BaseModel):
    """Response from sending a message."""

    messaging_product: str = "whatsapp"
    contacts: list[dict] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)

    @property
    def message_id(self) -> Optional[str]:
        """Get the sent message ID."""
        if self.messages:
            return self.messages[0].get("id")
        return None


# === Session State Schemas ===

class ConversationState(BaseModel):
    """State of a conversation with a user."""

    phone_number: str = Field(..., description="User's phone number")
    last_message_id: Optional[str] = None
    last_message_time: Optional[datetime] = None
    message_count: int = 0
    voice_message_count: int = 0
    context: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def update_on_message(self, message_id: str):
        """Update state when a message is received."""
        self.last_message_id = message_id
        self.last_message_time = datetime.utcnow()
        self.message_count += 1
        self.updated_at = datetime.utcnow()

    def update_on_voice(self, message_id: str):
        """Update state when a voice message is received."""
        self.update_on_message(message_id)
        self.voice_message_count += 1
