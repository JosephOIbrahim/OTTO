"""
OTTO WhatsApp Integration Module.

Provides WhatsApp Cloud API integration for voice and text messaging:
- Webhook handling for incoming messages
- Voice message processing pipeline
- Text message handling
- Media upload/download
- Session management

Usage (Standalone Server):
    python -m otto.whatsapp.server --port 8000

Usage (Mount to Existing App):
    from otto.whatsapp import get_whatsapp_router
    app.include_router(get_whatsapp_router(), prefix="/webhook")

Usage (Custom Adapter):
    from otto.whatsapp import create_whatsapp_adapter

    # Automatically wired to OTTO cognitive orchestrator
    adapter = create_whatsapp_adapter()
    await adapter.start()

Environment Variables:
    OPENAI_API_KEY          - OpenAI API key (for Whisper STT and TTS)
    WHATSAPP_TOKEN          - WhatsApp Cloud API access token
    WHATSAPP_PHONE_NUMBER_ID - WhatsApp Business phone number ID
    WHATSAPP_VERIFY_TOKEN   - Webhook verification token

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

# Server integration (imports lazily to avoid FastAPI dependency)
def get_whatsapp_router():
    """Get FastAPI router for WhatsApp webhooks."""
    from .server import get_whatsapp_router as _get_router
    return _get_router()

def create_app():
    """Create FastAPI app with WhatsApp integration."""
    from .server import create_app as _create_app
    return _create_app()

def create_whatsapp_adapter(orchestrator=None):
    """Create WhatsApp adapter wired to OTTO."""
    from .server import create_whatsapp_adapter as _create_adapter
    return _create_adapter(orchestrator)


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
    # Server integration
    "get_whatsapp_router",
    "create_app",
    "create_whatsapp_adapter",
]

__version__ = "1.0.0"
