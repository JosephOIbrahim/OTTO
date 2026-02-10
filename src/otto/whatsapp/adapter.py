"""
WhatsApp Voice Integration Adapter.

Main integration point connecting WhatsApp to OTTO voice processing.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable, Awaitable

from .api import WhatsAppAPI, WhatsAppConfig
from .webhook import WhatsAppWebhook, WebhookConfig
from .media import MediaHandler, MediaInfo
from .session import SessionManager, SessionConfig, get_session_manager
from .schemas import WhatsAppContact, IncomingMessage, MessageType

from ..voice_core import (
    SpeechToText,
    TextToSpeech,
    prepare_for_speech,
    VoiceProcessingQueue,
    QueueConfig,
    VoiceMessage,
    LatencyMetrics,
    CostMetrics,
    LatencyTimer,
    record_voice_interaction,
    DEFAULT_IDENTITY,
)

from ..memory import get_memory, Episode, EpisodeQuery, Outcome, OTTOMemory

# Optional LLM imports (for conversation history)
try:
    from ..llm.response_generator import ConversationTurn
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    ConversationTurn = None


logger = logging.getLogger(__name__)


# Type for OTTO core processor
OTTOProcessor = Callable[[str, dict], Awaitable[str]]


@dataclass
class VoiceAdapterConfig:
    """Configuration for voice adapter."""

    # WhatsApp config
    whatsapp_config: WhatsAppConfig = field(default_factory=WhatsAppConfig)

    # Session config
    session_config: SessionConfig = field(default_factory=SessionConfig)

    # Queue config
    queue_config: QueueConfig = field(default_factory=QueueConfig)

    # Media cache directory
    media_cache_dir: Optional[Path] = None

    # Voice response settings
    enable_voice_response: bool = True
    """Send voice responses (if False, send text)."""

    send_typing_indicator: bool = True
    """Send typing indicator while processing."""

    max_response_length: int = 4000
    """Maximum response text length."""


class WhatsAppVoiceAdapter:
    """
    WhatsApp Voice Integration Adapter.

    Provides full voice pipeline:
    1. Receive voice message via webhook
    2. Download audio from WhatsApp
    3. Transcribe with Whisper (STT)
    4. Process with OTTO core
    5. Prepare response for speech
    6. Synthesize response (TTS)
    7. Upload and send voice response

    Target metrics:
    - Latency: <10 seconds end-to-end
    - Cost: ~$0.22/user/day (20 interactions)
    """

    def __init__(
        self,
        config: Optional[VoiceAdapterConfig] = None,
        otto_processor: Optional[OTTOProcessor] = None,
    ):
        """
        Initialize the adapter.

        Args:
            config: Adapter configuration
            otto_processor: Function to process text through OTTO
        """
        self.config = config or VoiceAdapterConfig()
        self._otto_processor = otto_processor

        # Initialize components
        self.api = WhatsAppAPI(self.config.whatsapp_config)
        self.media = MediaHandler(self.api, self.config.media_cache_dir)
        self.sessions = get_session_manager()
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.queue = VoiceProcessingQueue(
            config=self.config.queue_config,
            processor=self._process_voice_message,
        )

        # Memory backbone for conversation history
        self._memory: OTTOMemory = get_memory()

        # Webhook (created on demand)
        self._webhook: Optional[WhatsAppWebhook] = None

    def set_otto_processor(self, processor: OTTOProcessor):
        """Set the OTTO processor function."""
        self._otto_processor = processor

    async def start(self):
        """Start the adapter (queue workers)."""
        await self.queue.start()
        logger.info("WhatsApp voice adapter started")

    async def stop(self):
        """Stop the adapter."""
        await self.queue.stop()
        await self.api.close()
        logger.info("WhatsApp voice adapter stopped")

    def get_webhook(self) -> WhatsAppWebhook:
        """Get or create webhook handler."""
        if self._webhook is None:
            self._webhook = WhatsAppWebhook(
                on_voice_message=self._on_voice_message,
                on_text_message=self._on_text_message,
            )
        return self._webhook

    async def _on_voice_message(
        self,
        contact: WhatsAppContact,
        message: IncomingMessage,
    ):
        """Handle incoming voice message."""
        logger.info(f"Voice message from {contact.phone_number}")

        # Update session
        session = self.sessions.get_or_create(contact.phone_number)
        session.update_on_voice(message.id)
        self.sessions.update(session)

        # Mark as read
        await self.api.mark_as_read(message.id)

        # React to show we received it
        await self.api.send_reaction(contact.phone_number, message.id, "🎤")

        # Download the audio
        audio_info = await self.media.download_voice_message(
            media_id=message.audio.id,
            mime_type=message.audio.mime_type,
        )

        # Enqueue for processing
        await self.queue.enqueue_audio(
            audio_data=audio_info.data,
            source_id=contact.phone_number,
            metadata={
                "message_id": message.id,
                "contact_name": contact.name,
                "audio_checksum": audio_info.checksum,
            }
        )

    async def _on_text_message(
        self,
        contact: WhatsAppContact,
        message: IncomingMessage,
    ):
        """Handle incoming text message."""
        logger.info(f"Text message from {contact.phone_number}")

        # Update session
        session = self.sessions.get_or_create(contact.phone_number)
        session.update_on_message(message.id)
        self.sessions.update(session)

        # Mark as read
        await self.api.mark_as_read(message.id)

        # Process text directly (no STT needed)
        if self._otto_processor and message.text:
            user_text = message.text.body

            # Retrieve conversation history before processing
            conversation_history = self._get_conversation_history(
                phone_number=contact.phone_number,
                limit=10,
            )

            response = await self._otto_processor(
                user_text,
                {
                    "phone_number": contact.phone_number,
                    "conversation_history": conversation_history,
                }
            )
            await self._send_response(contact.phone_number, response)

            # Record episode for future retrieval
            self._record_episode(
                phone_number=contact.phone_number,
                user_message=user_text,
                assistant_response=response,
            )

    async def _process_voice_message(self, voice_message: VoiceMessage):
        """
        Process a voice message through the full pipeline.

        Pipeline:
        1. STT (Whisper)
        2. OTTO processing
        3. Prepare for speech
        4. TTS
        5. Upload and send
        """
        latency = LatencyMetrics()
        source_id = voice_message.source_id

        try:
            # === Phase 1: STT ===
            with LatencyTimer() as stt_timer:
                transcription = await self.stt.transcribe_bytes(
                    audio_data=voice_message.audio_data,
                    filename="voice_message.ogg",
                )
            latency.stt_ms = stt_timer.elapsed_ms
            logger.info(f"STT: '{transcription.text[:50]}...' ({latency.stt_ms:.0f}ms)")

            # === Phase 2: OTTO Processing ===
            # Retrieve conversation history before processing
            conversation_history = self._get_conversation_history(
                phone_number=source_id,
                limit=10,
            )

            with LatencyTimer() as proc_timer:
                if self._otto_processor:
                    response_text = await self._otto_processor(
                        transcription.text,
                        {
                            "phone_number": source_id,
                            "voice_message": True,
                            "message_id": voice_message.metadata.get("message_id"),
                            "conversation_history": conversation_history,
                        }
                    )
                else:
                    # Fallback response
                    response_text = f"I heard: {transcription.text}"
            latency.processing_ms = proc_timer.elapsed_ms
            logger.info(f"Processing: {latency.processing_ms:.0f}ms")

            # Record episode for future retrieval
            self._record_episode(
                phone_number=source_id,
                user_message=transcription.text,
                assistant_response=response_text,
            )

            # === Phase 3: Prepare for Speech ===
            with LatencyTimer() as prep_timer:
                speech_text = prepare_for_speech(response_text)
            latency.prepare_speech_ms = prep_timer.elapsed_ms

            # === Phase 4: TTS ===
            with LatencyTimer() as tts_timer:
                audio_result = await self.tts.synthesize(speech_text.text)
            latency.tts_ms = tts_timer.elapsed_ms
            logger.info(f"TTS: {latency.tts_ms:.0f}ms")

            # === Phase 5: Upload and Send ===
            with LatencyTimer() as upload_timer:
                if self.config.enable_voice_response:
                    media_id = await self.media.upload_audio(
                        audio_data=audio_result.audio_data,
                        mime_type="audio/ogg",
                    )
                    await self.api.send_audio(source_id, media_id=media_id)
                else:
                    # Fall back to text
                    await self.api.send_text(source_id, response_text)
            latency.upload_ms = upload_timer.elapsed_ms

            # Calculate total latency
            latency.total_ms = (
                latency.stt_ms +
                latency.processing_ms +
                latency.prepare_speech_ms +
                latency.tts_ms +
                latency.upload_ms
            )

            # Calculate costs
            audio_duration = len(voice_message.audio_data) / 16000  # Rough estimate
            cost = CostMetrics.calculate(
                audio_duration_seconds=audio_duration,
                output_characters=len(speech_text.text),
            )

            # Record metrics
            record_voice_interaction(
                latency=latency,
                cost=cost,
                success=True,
                source_id=source_id,
            )

            logger.info(
                f"Voice pipeline complete: {latency.total_ms:.0f}ms "
                f"(target: 10000ms, within: {latency.within_target})"
            )

        except Exception as e:
            logger.error(f"Voice processing failed: {e}")

            # Send error message
            identity = DEFAULT_IDENTITY
            await self.api.send_text(
                source_id,
                identity.get_error_response()
            )

            # Record failure
            record_voice_interaction(
                latency=latency,
                cost=CostMetrics(),
                success=False,
                error=str(e),
                source_id=source_id,
            )

            raise

    async def _send_response(self, phone_number: str, response: str):
        """Send a response (voice or text based on config)."""
        if len(response) > self.config.max_response_length:
            response = response[:self.config.max_response_length] + "..."

        if self.config.enable_voice_response:
            # Prepare and synthesize
            speech_text = prepare_for_speech(response)
            audio_result = await self.tts.synthesize(speech_text.text)
            media_id = await self.media.upload_audio(
                audio_data=audio_result.audio_data,
                mime_type="audio/ogg",
            )
            await self.api.send_audio(phone_number, media_id=media_id)
        else:
            await self.api.send_text(phone_number, response)

    def _record_episode(
        self,
        phone_number: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """
        Record a conversation episode to memory backbone.

        Fixed data structure for deterministic recording.
        """
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        unique_episode_type = f"surface.whatsapp.message.{phone_number}.{timestamp_ms}"

        try:
            episode = Episode(
                type=unique_episode_type,
                data={
                    "phone_number": phone_number,
                    "user_message": user_message,
                    "assistant_response": assistant_response,
                },
                outcome=Outcome.SUCCESS,
                actor="whatsapp_adapter",
                service="whatsapp",
            )
            self._memory.record_episode(episode)
            logger.debug(f"Recorded WhatsApp episode: {unique_episode_type}")
        except Exception as e:
            logger.warning(f"Failed to record WhatsApp episode: {e}")

    def _get_conversation_history(
        self,
        phone_number: str,
        limit: int = 10,
    ) -> List["ConversationTurn"]:
        """
        Retrieve recent conversation history for a WhatsApp user.

        Determinism:
        - Fixed order: oldest to newest
        - Deterministic filtering and sorting

        Args:
            phone_number: WhatsApp phone number
            limit: Maximum number of conversation exchanges

        Returns:
            List of ConversationTurn objects, oldest first
        """
        if not self._memory or not LLM_AVAILABLE or ConversationTurn is None:
            return []

        try:
            query = EpisodeQuery(
                type="surface.whatsapp.message",
                service="whatsapp",
                limit=limit * 3,
                min_strength=0.0,
            )
            episodes = self._memory.query_episodes(query)

            # Filter by phone_number
            user_episodes = [
                ep for ep in episodes
                if ep.data.get("phone_number") == phone_number
            ]

            # Sort oldest first
            user_episodes = sorted(
                user_episodes,
                key=lambda e: e.timestamp,
            )[-limit:]

            # Build conversation turns
            turns: List[ConversationTurn] = []
            for ep in user_episodes:
                user_msg = ep.data.get("user_message")
                if user_msg:
                    turns.append(ConversationTurn(role="user", content=user_msg))

                assistant_msg = ep.data.get("assistant_response")
                if assistant_msg:
                    turns.append(ConversationTurn(role="assistant", content=assistant_msg))

            logger.debug(
                f"Retrieved {len(turns)} WhatsApp conversation turns for {phone_number}"
            )
            return turns

        except Exception as e:
            logger.warning(f"Failed to retrieve WhatsApp conversation history: {e}")
            return []

    def get_stats(self) -> dict:
        """Get adapter statistics."""
        from ..voice_core.metrics import get_metrics_collector

        metrics = get_metrics_collector()

        return {
            "queue": self.queue.get_stats(),
            "sessions": self.sessions.get_stats(),
            "media_cache": self.media.get_cache_stats(),
            "voice_metrics": metrics.get_summary(),
            "cost_projection": metrics.get_cost_projection(),
        }


def create_adapter(
    otto_processor: Optional[OTTOProcessor] = None,
    enable_voice_response: bool = True,
) -> WhatsAppVoiceAdapter:
    """
    Create a WhatsApp voice adapter.

    Args:
        otto_processor: Function to process text through OTTO
        enable_voice_response: Whether to respond with voice

    Returns:
        Configured adapter
    """
    config = VoiceAdapterConfig(
        enable_voice_response=enable_voice_response,
    )
    return WhatsAppVoiceAdapter(config, otto_processor)
