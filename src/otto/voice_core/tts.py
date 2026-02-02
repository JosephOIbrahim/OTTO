"""
Text-to-Speech (TTS) module using OpenAI TTS.

Provides deterministic speech synthesis with [He2025] compliance.
"""

import asyncio
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path

from .determinism import (
    TTS_VOICE_SEED,
    DeterministicRNG,
    compute_checksum,
)


class TTSVoice(str, Enum):
    """Available TTS voices."""

    ALLOY = "alloy"      # Neutral, balanced
    ECHO = "echo"        # Warm, conversational
    FABLE = "fable"      # British, storytelling
    ONYX = "onyx"        # Deep, authoritative
    NOVA = "nova"        # Friendly, approachable
    SHIMMER = "shimmer"  # Soft, gentle

    @classmethod
    def default(cls) -> "TTSVoice":
        """Return default voice for OTTO."""
        return cls.NOVA  # Friendly and approachable


class TTSModel(str, Enum):
    """Available TTS models."""

    TTS_1 = "tts-1"           # Standard quality, lower latency
    TTS_1_HD = "tts-1-hd"     # Higher quality, higher latency

    @classmethod
    def default(cls) -> "TTSModel":
        """Return default model balancing quality/latency."""
        return cls.TTS_1  # Lower latency for voice responses


class AudioFormat(str, Enum):
    """Output audio formats."""

    MP3 = "mp3"
    OPUS = "opus"    # Good for voice, smaller files
    AAC = "aac"
    FLAC = "flac"
    WAV = "wav"
    PCM = "pcm"

    @classmethod
    def default(cls) -> "AudioFormat":
        """Return default format for WhatsApp compatibility."""
        return cls.OPUS  # WhatsApp prefers opus


@dataclass
class TTSResult:
    """Result of text-to-speech synthesis."""

    audio_data: bytes
    """Raw audio data."""

    format: AudioFormat
    """Audio format."""

    duration_ms: float = 0.0
    """Estimated audio duration in milliseconds."""

    text_checksum: str = ""
    """Checksum of input text."""

    audio_checksum: str = ""
    """Checksum of output audio."""

    def __post_init__(self):
        """Compute audio checksum after initialization."""
        if not self.audio_checksum:
            self.audio_checksum = compute_checksum(self.audio_data)


@dataclass
class TTSConfig:
    """Configuration for text-to-speech."""

    model: TTSModel = field(default_factory=TTSModel.default)
    """TTS model to use."""

    voice: TTSVoice = field(default_factory=TTSVoice.default)
    """Voice for synthesis."""

    format: AudioFormat = field(default_factory=AudioFormat.default)
    """Output audio format."""

    speed: float = 1.0
    """Speech speed (0.25 to 4.0)."""

    api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY")
    )
    """OpenAI API key."""

    max_text_length: int = 4096
    """Maximum text length for single synthesis."""


class TextToSpeech:
    """
    Text-to-speech synthesis using OpenAI TTS.

    [He2025] Compliance:
    - Fixed voice selection (no dynamic switching)
    - Deterministic text preprocessing
    - Checksum verification
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        """
        Initialize TTS with configuration.

        Args:
            config: TTS configuration (uses defaults if None)
        """
        self.config = config or TTSConfig()
        self._rng = DeterministicRNG(TTS_VOICE_SEED)
        self._client: Optional[object] = None

    async def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.config.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai>=1.0.0")
        return self._client

    async def synthesize(
        self,
        text: str,
        voice: Optional[TTSVoice] = None,
        speed: Optional[float] = None,
    ) -> TTSResult:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice: Optional voice override
            speed: Optional speed override

        Returns:
            TTSResult with audio data and metadata
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")

        if len(text) > self.config.max_text_length:
            raise ValueError(
                f"Text exceeds maximum length: {len(text)} > {self.config.max_text_length}"
            )

        text_checksum = compute_checksum(text)
        client = await self._get_client()

        response = await client.audio.speech.create(
            model=self.config.model.value,
            voice=(voice or self.config.voice).value,
            input=text,
            response_format=self.config.format.value,
            speed=speed or self.config.speed,
        )

        audio_data = response.content

        # Estimate duration (rough: ~150 words per minute at speed 1.0)
        word_count = len(text.split())
        speed_factor = speed or self.config.speed
        estimated_duration_ms = (word_count / 150) * 60 * 1000 / speed_factor

        return TTSResult(
            audio_data=audio_data,
            format=self.config.format,
            duration_ms=estimated_duration_ms,
            text_checksum=text_checksum,
        )

    async def synthesize_to_file(
        self,
        text: str,
        output_path: Path | str,
        voice: Optional[TTSVoice] = None,
        speed: Optional[float] = None,
    ) -> TTSResult:
        """
        Synthesize text to speech and save to file.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            voice: Optional voice override
            speed: Optional speed override

        Returns:
            TTSResult with audio data and metadata
        """
        result = await self.synthesize(text, voice, speed)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(result.audio_data)

        return result

    async def synthesize_chunks(
        self,
        chunks: list[str],
        voice: Optional[TTSVoice] = None,
        speed: Optional[float] = None,
    ) -> list[TTSResult]:
        """
        Synthesize multiple text chunks.

        Useful for long texts that need to be split.

        Args:
            chunks: List of text chunks
            voice: Optional voice override
            speed: Optional speed override

        Returns:
            List of TTSResults
        """
        results = []
        for chunk in chunks:
            if chunk.strip():
                result = await self.synthesize(chunk, voice, speed)
                results.append(result)
        return results


# Voice characteristics for selection
VOICE_CHARACTERISTICS: dict[TTSVoice, dict] = {
    TTSVoice.ALLOY: {
        "gender": "neutral",
        "tone": "balanced",
        "energy": "medium",
        "best_for": ["general", "neutral"],
    },
    TTSVoice.ECHO: {
        "gender": "male",
        "tone": "warm",
        "energy": "medium",
        "best_for": ["conversational", "friendly"],
    },
    TTSVoice.FABLE: {
        "gender": "female",
        "tone": "expressive",
        "energy": "medium",
        "best_for": ["storytelling", "narrative"],
    },
    TTSVoice.ONYX: {
        "gender": "male",
        "tone": "deep",
        "energy": "low",
        "best_for": ["authoritative", "formal"],
    },
    TTSVoice.NOVA: {
        "gender": "female",
        "tone": "friendly",
        "energy": "high",
        "best_for": ["approachable", "casual"],
    },
    TTSVoice.SHIMMER: {
        "gender": "female",
        "tone": "soft",
        "energy": "low",
        "best_for": ["gentle", "calming"],
    },
}


# Convenience function for simple synthesis
async def synthesize_speech(
    text: str,
    voice: TTSVoice = TTSVoice.NOVA,
) -> bytes:
    """
    Simple speech synthesis function.

    Args:
        text: Text to synthesize
        voice: Voice to use

    Returns:
        Audio data as bytes
    """
    tts = TextToSpeech()
    result = await tts.synthesize(text, voice)
    return result.audio_data
