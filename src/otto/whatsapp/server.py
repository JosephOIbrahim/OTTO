"""
WhatsApp Voice Server Integration
=================================

Integrates WhatsApp voice adapter with OTTO's cognitive orchestrator.

Usage:
    # Start standalone server
    python -m otto.whatsapp.server --port 8000

    # Or import and mount to existing FastAPI app
    from otto.whatsapp.server import create_app, get_whatsapp_router
    app.include_router(get_whatsapp_router())

Environment Variables:
    OPENAI_API_KEY          - OpenAI API key (for Whisper STT and TTS)
    WHATSAPP_TOKEN          - WhatsApp Cloud API access token
    WHATSAPP_PHONE_NUMBER_ID - WhatsApp Business phone number ID
    WHATSAPP_VERIFY_TOKEN   - Webhook verification token

[He2025] Compliance:
    - Fixed seed for session management
    - Deterministic cognitive routing
    - State snapshot before processing
"""

import argparse
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Check FastAPI availability
try:
    from fastapi import FastAPI, APIRouter
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("FastAPI not installed. Install with: pip install fastapi uvicorn")

from .adapter import WhatsAppVoiceAdapter, VoiceAdapterConfig, create_adapter
from .api import WhatsAppConfig

from ..cognitive_orchestrator import CognitiveOrchestrator, create_orchestrator

# Optional LLM imports
try:
    from ..llm import ResponseGenerator, GenerationContext, create_response_generator
    from ..llm.response_generator import ConversationTurn
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    ResponseGenerator = None
    GenerationContext = None
    create_response_generator = None
    ConversationTurn = None


# =============================================================================
# OTTO Processor Callback
# =============================================================================

async def otto_processor(
    text: str,
    context: dict,
    orchestrator: CognitiveOrchestrator,
    response_generator: Optional["ResponseGenerator"] = None,
) -> str:
    """
    Process text through OTTO's cognitive orchestrator and generate response.

    This is the callback wired to WhatsAppVoiceAdapter.

    Args:
        text: User message text (transcribed from voice or text input)
        context: Message context (phone_number, voice_message flag,
                 conversation_history, etc.)
        orchestrator: Cognitive orchestrator instance
        response_generator: LLM response generator (optional)

    Returns:
        OTTO's response text
    """
    # Process through NEXUS pipeline
    result = orchestrator.process_message(text, context)

    # Extract routing info
    if hasattr(result, 'routing'):
        expert = result.routing.expert.value
        anchor = result.to_anchor()

        # Generate response via LLM if available
        if response_generator and LLM_AVAILABLE:
            try:
                # Extract conversation history from context
                conversation_history = context.get("conversation_history", [])

                gen_context = GenerationContext(
                    expert=expert,
                    platform="whatsapp",
                    user_id=context.get("phone_number"),
                    conversation_history=conversation_history,
                )

                response = await response_generator.generate(text, gen_context)
                return response.text
            except Exception as e:
                logger.error(f"LLM generation failed, using fallback: {e}")

        # Fallback: routing info (no LLM available)
        return f"[{expert}] Message received. {anchor}"
    else:
        # KnowledgeResult (fast path)
        if result.found:
            prim = result.top_prim
            return f"From knowledge: {prim.summary}" if prim else "Knowledge found."
        return "I understand. How can I help?"


# =============================================================================
# Global State
# =============================================================================

_adapter: Optional[WhatsAppVoiceAdapter] = None
_orchestrator: Optional[CognitiveOrchestrator] = None
_response_generator: Optional["ResponseGenerator"] = None


def get_adapter() -> WhatsAppVoiceAdapter:
    """Get or create the WhatsApp adapter singleton."""
    global _adapter, _orchestrator, _response_generator

    if _adapter is None:
        _orchestrator = create_orchestrator()
        _response_generator = _create_response_generator()
        _adapter = create_whatsapp_adapter(_orchestrator, _response_generator)

    return _adapter


def get_orchestrator() -> CognitiveOrchestrator:
    """Get the cognitive orchestrator instance."""
    global _orchestrator

    if _orchestrator is None:
        _orchestrator = create_orchestrator()

    return _orchestrator


def _create_response_generator() -> Optional["ResponseGenerator"]:
    """Create LLM response generator if available."""
    if not LLM_AVAILABLE:
        logger.warning("LLM not available for WhatsApp. Responses will be placeholder.")
        return None

    try:
        gen = create_response_generator()
        logger.info("Created WhatsApp response generator")
        return gen
    except Exception as e:
        logger.warning(f"Failed to create response generator: {e}")
        return None


# =============================================================================
# Factory Functions
# =============================================================================

def create_whatsapp_adapter(
    orchestrator: Optional[CognitiveOrchestrator] = None,
    response_gen: Optional["ResponseGenerator"] = None,
) -> WhatsAppVoiceAdapter:
    """
    Create a WhatsApp voice adapter wired to OTTO.

    Args:
        orchestrator: Cognitive orchestrator instance (creates default if None)
        response_gen: LLM response generator (creates default if None)

    Returns:
        Configured WhatsAppVoiceAdapter
    """
    if orchestrator is None:
        orchestrator = create_orchestrator()

    if response_gen is None and LLM_AVAILABLE:
        response_gen = _create_response_generator()

    # Read configuration from environment
    whatsapp_config = WhatsAppConfig(
        access_token=os.environ.get("WHATSAPP_TOKEN", ""),
        phone_number_id=os.environ.get("WHATSAPP_PHONE_NUMBER_ID", ""),
        verify_token=os.environ.get("WHATSAPP_VERIFY_TOKEN", "otto_verify"),
    )

    adapter_config = VoiceAdapterConfig(
        whatsapp_config=whatsapp_config,
        enable_voice_response=True,
        send_typing_indicator=True,
    )

    # Create processor closure that captures orchestrator and response generator
    async def processor(text: str, context: dict) -> str:
        return await otto_processor(text, context, orchestrator, response_gen)

    adapter = WhatsAppVoiceAdapter(adapter_config, processor)

    logger.info("WhatsApp adapter created and wired to OTTO orchestrator")
    return adapter


def get_whatsapp_router() -> "APIRouter":
    """
    Get the FastAPI router for WhatsApp webhooks.

    Returns:
        APIRouter with WhatsApp webhook endpoints
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI required. Install with: pip install fastapi")

    adapter = get_adapter()
    webhook = adapter.get_webhook()
    return webhook.router


# =============================================================================
# FastAPI Application
# =============================================================================

def create_app() -> "FastAPI":
    """
    Create the FastAPI application with WhatsApp webhook routes.

    Returns:
        Configured FastAPI app
    """
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI required. Install with: pip install fastapi uvicorn")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage adapter lifecycle."""
        adapter = get_adapter()
        await adapter.start()
        logger.info("WhatsApp voice adapter started")

        yield

        await adapter.stop()
        logger.info("WhatsApp voice adapter stopped")

    app = FastAPI(
        title="OTTO WhatsApp Voice",
        description="WhatsApp voice integration for OTTO OS",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Mount webhook router
    app.include_router(get_whatsapp_router(), prefix="/webhook", tags=["WhatsApp"])

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        adapter = get_adapter()
        return {
            "status": "healthy",
            "adapter_stats": adapter.get_stats(),
        }

    # Status endpoint
    @app.get("/status")
    async def status():
        orchestrator = get_orchestrator()
        state = orchestrator.get_state()
        return {
            "cognitive_state": {
                "burnout": state.burnout_level.value,
                "energy": state.energy_level.value,
                "momentum": state.momentum_phase.value,
                "mode": state.mode.value,
            },
            "adapter_stats": get_adapter().get_stats(),
        }

    return app


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """Run the WhatsApp voice server."""
    parser = argparse.ArgumentParser(description="OTTO WhatsApp Voice Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    # Check required environment variables
    required_vars = ["OPENAI_API_KEY", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"]
    missing = [v for v in required_vars if not os.environ.get(v)]

    if missing:
        logger.warning(f"Missing environment variables: {missing}")
        logger.warning("WhatsApp integration will not work without these.")

    # Import uvicorn here to make it optional
    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn required. Install with: pip install uvicorn")
        return 1

    logger.info(f"Starting WhatsApp voice server on {args.host}:{args.port}")
    uvicorn.run(
        "otto.whatsapp.server:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
