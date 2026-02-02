"""
WhatsApp media handling utilities.

Provides media download, upload, and format conversion.
"""

import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .api import WhatsAppAPI, WhatsAppAPIError
from ..voice_core.determinism import compute_checksum


logger = logging.getLogger(__name__)


# Supported audio formats for WhatsApp
SUPPORTED_AUDIO_FORMATS = {
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/amr": ".amr",
}

# Default format for TTS output (WhatsApp prefers opus in ogg container)
DEFAULT_AUDIO_FORMAT = "audio/ogg"
DEFAULT_AUDIO_EXTENSION = ".ogg"


@dataclass
class MediaInfo:
    """Information about downloaded media."""

    media_id: str
    """WhatsApp media ID."""

    data: bytes
    """Raw media data."""

    mime_type: str
    """MIME type of the media."""

    checksum: str
    """SHA-256 checksum of the data."""

    size_bytes: int
    """Size in bytes."""

    @property
    def extension(self) -> str:
        """Get file extension for mime type."""
        return SUPPORTED_AUDIO_FORMATS.get(self.mime_type, ".bin")


class MediaHandler:
    """
    Handle WhatsApp media operations.

    Provides:
    - Media download with caching
    - Media upload
    - Format validation
    """

    def __init__(
        self,
        api: WhatsAppAPI,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize media handler.

        Args:
            api: WhatsApp API client
            cache_dir: Optional directory for caching downloaded media
        """
        self.api = api
        self.cache_dir = cache_dir
        self._cache: dict[str, MediaInfo] = {}

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    async def download_voice_message(
        self,
        media_id: str,
        mime_type: str = "audio/ogg",
    ) -> MediaInfo:
        """
        Download a voice message.

        Args:
            media_id: WhatsApp media ID
            mime_type: Expected MIME type

        Returns:
            MediaInfo with downloaded data
        """
        # Check memory cache
        if media_id in self._cache:
            logger.debug(f"Media {media_id} found in cache")
            return self._cache[media_id]

        # Check disk cache
        if self.cache_dir:
            cached_path = self._get_cache_path(media_id, mime_type)
            if cached_path.exists():
                logger.debug(f"Media {media_id} found on disk")
                data = cached_path.read_bytes()
                info = MediaInfo(
                    media_id=media_id,
                    data=data,
                    mime_type=mime_type,
                    checksum=compute_checksum(data),
                    size_bytes=len(data),
                )
                self._cache[media_id] = info
                return info

        # Download from WhatsApp
        logger.info(f"Downloading media {media_id}")
        try:
            data = await self.api.download_media(media_id)
        except WhatsAppAPIError as e:
            logger.error(f"Failed to download media {media_id}: {e}")
            raise

        info = MediaInfo(
            media_id=media_id,
            data=data,
            mime_type=mime_type,
            checksum=compute_checksum(data),
            size_bytes=len(data),
        )

        # Cache to memory
        self._cache[media_id] = info

        # Cache to disk
        if self.cache_dir:
            cache_path = self._get_cache_path(media_id, mime_type)
            cache_path.write_bytes(data)
            logger.debug(f"Cached media {media_id} to {cache_path}")

        return info

    async def upload_audio(
        self,
        audio_data: bytes,
        mime_type: str = DEFAULT_AUDIO_FORMAT,
        filename: Optional[str] = None,
    ) -> str:
        """
        Upload audio to WhatsApp.

        Args:
            audio_data: Raw audio bytes
            mime_type: MIME type of the audio
            filename: Optional filename

        Returns:
            Media ID for use in messages
        """
        if mime_type not in SUPPORTED_AUDIO_FORMATS:
            logger.warning(f"Audio format {mime_type} may not be supported")

        if filename is None:
            ext = SUPPORTED_AUDIO_FORMATS.get(mime_type, ".bin")
            filename = f"otto_voice{ext}"

        logger.info(f"Uploading audio ({len(audio_data)} bytes, {mime_type})")

        try:
            response = await self.api.upload_media(
                media_data=audio_data,
                mime_type=mime_type,
                filename=filename,
            )
            logger.info(f"Uploaded audio, media ID: {response.id}")
            return response.id
        except WhatsAppAPIError as e:
            logger.error(f"Failed to upload audio: {e}")
            raise

    def _get_cache_path(self, media_id: str, mime_type: str) -> Path:
        """Get cache file path for a media ID."""
        ext = SUPPORTED_AUDIO_FORMATS.get(mime_type, ".bin")
        # Sanitize media_id for filename
        safe_id = "".join(c if c.isalnum() else "_" for c in media_id)
        return self.cache_dir / f"{safe_id}{ext}"

    def clear_cache(self):
        """Clear the memory cache."""
        self._cache.clear()

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        memory_size = sum(info.size_bytes for info in self._cache.values())

        disk_files = 0
        disk_size = 0
        if self.cache_dir and self.cache_dir.exists():
            for f in self.cache_dir.iterdir():
                if f.is_file():
                    disk_files += 1
                    disk_size += f.stat().st_size

        return {
            "memory_items": len(self._cache),
            "memory_size_bytes": memory_size,
            "disk_files": disk_files,
            "disk_size_bytes": disk_size,
        }


async def download_and_validate(
    api: WhatsAppAPI,
    media_id: str,
    expected_mime: str = "audio/ogg",
    max_size_mb: float = 16.0,
) -> MediaInfo:
    """
    Download media with validation.

    Args:
        api: WhatsApp API client
        media_id: Media ID to download
        expected_mime: Expected MIME type
        max_size_mb: Maximum allowed size in MB

    Returns:
        MediaInfo if valid

    Raises:
        ValueError: If media fails validation
    """
    handler = MediaHandler(api)
    info = await handler.download_voice_message(media_id, expected_mime)

    # Validate size
    max_bytes = int(max_size_mb * 1024 * 1024)
    if info.size_bytes > max_bytes:
        raise ValueError(
            f"Media too large: {info.size_bytes / 1024 / 1024:.1f}MB > {max_size_mb}MB"
        )

    # Basic format validation (check for common audio headers)
    if not _validate_audio_header(info.data, expected_mime):
        logger.warning(f"Audio header validation failed for {media_id}")
        # Don't fail, just warn (WhatsApp guarantees the format)

    return info


def _validate_audio_header(data: bytes, mime_type: str) -> bool:
    """
    Validate audio file header.

    Args:
        data: Raw audio data
        mime_type: Expected MIME type

    Returns:
        True if header looks valid
    """
    if len(data) < 4:
        return False

    # OGG (Opus container)
    if mime_type in ("audio/ogg", "audio/opus"):
        return data[:4] == b"OggS"

    # MP3
    if mime_type == "audio/mpeg":
        # ID3 header or MP3 frame sync
        return data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)

    # M4A/AAC (MP4 container)
    if mime_type in ("audio/mp4", "audio/aac"):
        return data[4:8] == b"ftyp"

    # AMR
    if mime_type == "audio/amr":
        return data[:6] == b"#!AMR\n"

    return True  # Unknown format, assume valid
