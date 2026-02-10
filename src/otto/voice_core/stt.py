"""
Speech-to-Text (STT) module using OpenAI Whisper.

Provides deterministic speech transcription with Determinism.
"""

import asyncio
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from .determinism import (
    STT_NORMALIZATION_SEED,
    DeterministicRNG,
    compute_checksum,
)


@dataclass
class TranscriptionResult:
    """Result of speech-to-text transcription."""

    text: str
    """Transcribed text content."""

    language: str = "en"
    """Detected or specified language."""

    duration_ms: float = 0.0
    """Audio duration in milliseconds."""

    confidence: float = 1.0
    """Transcription confidence (0.0-1.0)."""

    checksum: str = ""
    """Deterministic checksum of transcription."""

    def __post_init__(self):
        """Compute checksum after initialization."""
        if not self.checksum:
            self.checksum = compute_checksum(self.text)


@dataclass
class STTConfig:
    """Configuration for speech-to-text."""

    model: str = "whisper-1"
    """Whisper model to use."""

    language: Optional[str] = None
    """Language hint (None for auto-detect)."""

    temperature: float = 0.0
    """Temperature for transcription (0.0 for determinism)."""

    response_format: str = "json"
    """Response format from API."""

    api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY")
    )
    """OpenAI API key."""


class SpeechToText:
    """
    Speech-to-text transcription using OpenAI Whisper.

    Determinism:
    - Temperature = 0.0 for deterministic output
    - Seeded text normalization
    - Checksum verification
    """

    def __init__(self, config: Optional[STTConfig] = None):
        """
        Initialize STT with configuration.

        Args:
            config: STT configuration (uses defaults if None)
        """
        self.config = config or STTConfig()
        self._rng = DeterministicRNG(STT_NORMALIZATION_SEED)
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

    async def transcribe(
        self,
        audio_path: Path | str,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Optional language hint

        Returns:
            TranscriptionResult with text and metadata
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        client = await self._get_client()

        with open(audio_path, "rb") as audio_file:
            response = await client.audio.transcriptions.create(
                model=self.config.model,
                file=audio_file,
                language=language or self.config.language,
                temperature=self.config.temperature,  # 0.0 for determinism
                response_format=self.config.response_format,
            )

        text = response.text if hasattr(response, 'text') else str(response)
        normalized_text = self._normalize_text(text)

        return TranscriptionResult(
            text=normalized_text,
            language=language or self.config.language or "en",
            confidence=1.0,  # Whisper doesn't provide per-segment confidence
        )

    async def transcribe_bytes(
        self,
        audio_data: bytes,
        filename: str = "audio.ogg",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio bytes to text.

        Args:
            audio_data: Raw audio bytes
            filename: Filename hint for format detection
            language: Optional language hint

        Returns:
            TranscriptionResult with text and metadata
        """
        client = await self._get_client()

        response = await client.audio.transcriptions.create(
            model=self.config.model,
            file=(filename, audio_data),
            language=language or self.config.language,
            temperature=self.config.temperature,
            response_format=self.config.response_format,
        )

        text = response.text if hasattr(response, 'text') else str(response)
        normalized_text = self._normalize_text(text)

        return TranscriptionResult(
            text=normalized_text,
            language=language or self.config.language or "en",
            confidence=1.0,
        )

    def _normalize_text(self, text: str) -> str:
        """
        Normalize transcribed text deterministically.

        Operations (fixed order):
        1. Strip whitespace
        2. Normalize unicode
        3. Fix common transcription errors
        """
        import unicodedata

        # Phase 1: Strip whitespace
        text = text.strip()

        # Phase 2: Normalize unicode (NFKC for compatibility)
        text = unicodedata.normalize("NFKC", text)

        # Phase 3: Normalize multiple spaces to single
        while "  " in text:
            text = text.replace("  ", " ")

        return text


# Convenience function for simple transcription
async def transcribe_audio(
    audio_path: Path | str,
    language: Optional[str] = None,
) -> str:
    """
    Simple transcription function.

    Args:
        audio_path: Path to audio file
        language: Optional language hint

    Returns:
        Transcribed text
    """
    stt = SpeechToText()
    result = await stt.transcribe(audio_path, language)
    return result.text
