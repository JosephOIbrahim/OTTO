"""
OTTO WhatsApp Integration Module.

Provides WhatsApp Cloud API integration for voice and text messaging:
- Webhook handling for incoming messages
- Voice message processing pipeline
- Text message handling
- Media upload/download
- Session management

Usage:
    from otto.whatsapp import create_adapter

    adapter = create_adapter(
        otto_processor=my_processor_function,
        enable_voice_response=True,
    )

    # Add webhook router to FastAPI app
    app.include_router(adapter.get_webhook().router)

    # Start processing
    await adapter.start()

Target Metrics:
- Latency: <10 seconds end-to-end
- Cost: ~$0.22/user/day (20 voice interactions)
- Reliability: No message loss (async queue with persistence)
"""

from .schemas import (
    # Message types
    MessageType,
    MessageStatus,
    # Incoming messages
    IncomingMessage,
    WhatsAppContact,
    TextContent,
    AudioContent,
    ImageContent,
    DocumentContent,
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

from .api import (
    WhatsAppAPI,
    WhatsAppConfig,
    WhatsAppAPIError,
    create_api,
)

from .webhook import (
    WhatsAppWebhook,
    WebhookConfig,
    create_webhook_router,
    MessageHandler,
)

from .media import (
    MediaHandler,
    MediaInfo,
    download_and_validate,
    SUPPORTED_AUDIO_FORMATS,
    DEFAULT_AUDIO_FORMAT,
)

from .session import (
    SessionManager,
    SessionConfig,
    get_session_manager,
    configure_sessions,
)

from .adapter import (
    WhatsAppVoiceAdapter,
    VoiceAdapterConfig,
    create_adapter,
    OTTOProcessor,
)


__all__ = [
    # Schemas - Message types
    "MessageType",
    "MessageStatus",
    # Schemas - Incoming
    "IncomingMessage",
    "WhatsAppContact",
    "TextContent",
    "AudioContent",
    "ImageContent",
    "DocumentContent",
    "LocationContent",
    # Schemas - Webhook
    "WebhookPayload",
    "WebhookEntry",
    "WebhookChange",
    "WebhookValue",
    # Schemas - Outgoing
    "OutgoingTextMessage",
    "OutgoingAudioMessage",
    "OutgoingReaction",
    "MessageSendResponse",
    "MediaUploadResponse",
    # Schemas - Session
    "ConversationState",
    # API
    "WhatsAppAPI",
    "WhatsAppConfig",
    "WhatsAppAPIError",
    "create_api",
    # Webhook
    "WhatsAppWebhook",
    "WebhookConfig",
    "create_webhook_router",
    "MessageHandler",
    # Media
    "MediaHandler",
    "MediaInfo",
    "download_and_validate",
    "SUPPORTED_AUDIO_FORMATS",
    "DEFAULT_AUDIO_FORMAT",
    # Session
    "SessionManager",
    "SessionConfig",
    "get_session_manager",
    "configure_sessions",
    # Adapter
    "WhatsAppVoiceAdapter",
    "VoiceAdapterConfig",
    "create_adapter",
    "OTTOProcessor",
]

__version__ = "1.0.0"
