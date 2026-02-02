"""
Voice processing queue with persistence.

Implements async queue for voice message processing with
guaranteed delivery (no message loss).
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Any
import logging

from .determinism import compute_checksum


logger = logging.getLogger(__name__)


class MessageStatus(str, Enum):
    """Status of a queued message."""

    PENDING = "pending"          # Waiting to be processed
    PROCESSING = "processing"    # Currently being processed
    COMPLETED = "completed"      # Successfully processed
    FAILED = "failed"           # Processing failed
    RETRYING = "retrying"       # Retrying after failure


@dataclass
class VoiceMessage:
    """A voice message in the processing queue."""

    id: str
    """Unique message identifier."""

    audio_data: bytes
    """Raw audio data."""

    source_id: str
    """Source identifier (e.g., WhatsApp phone number)."""

    timestamp: datetime
    """When the message was received."""

    status: MessageStatus = MessageStatus.PENDING
    """Current processing status."""

    retry_count: int = 0
    """Number of processing attempts."""

    checksum: str = ""
    """Audio data checksum."""

    metadata: dict = field(default_factory=dict)
    """Additional message metadata."""

    error: Optional[str] = None
    """Error message if failed."""

    def __post_init__(self):
        """Compute checksum after initialization."""
        if not self.checksum:
            self.checksum = compute_checksum(self.audio_data)

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence (excluding audio_data)."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "retry_count": self.retry_count,
            "checksum": self.checksum,
            "metadata": self.metadata,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict, audio_data: bytes) -> "VoiceMessage":
        """Create from dictionary and audio data."""
        return cls(
            id=data["id"],
            audio_data=audio_data,
            source_id=data["source_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=MessageStatus(data["status"]),
            retry_count=data.get("retry_count", 0),
            checksum=data.get("checksum", ""),
            metadata=data.get("metadata", {}),
            error=data.get("error"),
        )


@dataclass
class QueueConfig:
    """Configuration for voice processing queue."""

    max_retries: int = 3
    """Maximum retry attempts."""

    retry_delay: float = 1.0
    """Base delay between retries (seconds)."""

    max_queue_size: int = 1000
    """Maximum queue size."""

    persist_path: Optional[Path] = None
    """Path for queue persistence (None for in-memory only)."""

    processing_timeout: float = 30.0
    """Timeout for processing a single message (seconds)."""


class VoiceProcessingQueue:
    """
    Async queue for voice message processing.

    Features:
    - Guaranteed delivery (no message loss)
    - Optional persistence
    - Retry with exponential backoff
    - Concurrent processing with limit
    """

    def __init__(
        self,
        config: Optional[QueueConfig] = None,
        processor: Optional[Callable[[VoiceMessage], Any]] = None,
    ):
        """
        Initialize the queue.

        Args:
            config: Queue configuration
            processor: Async function to process messages
        """
        self.config = config or QueueConfig()
        self.processor = processor

        self._queue: asyncio.Queue[VoiceMessage] = asyncio.Queue(
            maxsize=self.config.max_queue_size
        )
        self._messages: dict[str, VoiceMessage] = {}
        self._processing_count = 0
        self._max_concurrent = 3
        self._running = False
        self._workers: list[asyncio.Task] = []

        # Load persisted messages on init
        if self.config.persist_path:
            self._load_persisted()

    async def enqueue(self, message: VoiceMessage) -> str:
        """
        Add a message to the queue.

        Args:
            message: Voice message to process

        Returns:
            Message ID
        """
        if message.id in self._messages:
            logger.warning(f"Message {message.id} already in queue, skipping")
            return message.id

        self._messages[message.id] = message
        await self._queue.put(message)

        # Persist immediately for durability
        if self.config.persist_path:
            self._persist_message(message)

        logger.info(f"Enqueued message {message.id} from {message.source_id}")
        return message.id

    async def enqueue_audio(
        self,
        audio_data: bytes,
        source_id: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Convenience method to enqueue raw audio.

        Args:
            audio_data: Raw audio bytes
            source_id: Source identifier
            metadata: Optional metadata

        Returns:
            Message ID
        """
        message = VoiceMessage(
            id=str(uuid.uuid4()),
            audio_data=audio_data,
            source_id=source_id,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
        )
        return await self.enqueue(message)

    def get_status(self, message_id: str) -> Optional[MessageStatus]:
        """Get status of a message."""
        message = self._messages.get(message_id)
        return message.status if message else None

    def get_message(self, message_id: str) -> Optional[VoiceMessage]:
        """Get a message by ID."""
        return self._messages.get(message_id)

    async def start(self, num_workers: int = 3):
        """
        Start queue processing.

        Args:
            num_workers: Number of concurrent workers
        """
        if self._running:
            return

        self._running = True
        self._max_concurrent = num_workers

        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        logger.info(f"Started {num_workers} voice processing workers")

    async def stop(self):
        """Stop queue processing gracefully."""
        self._running = False

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("Voice processing queue stopped")

    async def _worker(self, worker_id: int):
        """Worker coroutine that processes messages."""
        logger.info(f"Worker {worker_id} started")

        while self._running:
            try:
                # Get message with timeout
                try:
                    message = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Process the message
                await self._process_message(message)
                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

        logger.info(f"Worker {worker_id} stopped")

    async def _process_message(self, message: VoiceMessage):
        """Process a single message with retry logic."""
        message.status = MessageStatus.PROCESSING
        self._persist_message(message)

        try:
            if self.processor:
                await asyncio.wait_for(
                    self.processor(message),
                    timeout=self.config.processing_timeout
                )

            message.status = MessageStatus.COMPLETED
            logger.info(f"Processed message {message.id}")

        except asyncio.TimeoutError:
            message.error = "Processing timeout"
            await self._handle_failure(message)

        except Exception as e:
            message.error = str(e)
            await self._handle_failure(message)

        finally:
            self._persist_message(message)

    async def _handle_failure(self, message: VoiceMessage):
        """Handle message processing failure."""
        message.retry_count += 1

        if message.retry_count < self.config.max_retries:
            message.status = MessageStatus.RETRYING
            delay = self.config.retry_delay * (2 ** (message.retry_count - 1))

            logger.warning(
                f"Message {message.id} failed (attempt {message.retry_count}), "
                f"retrying in {delay}s: {message.error}"
            )

            await asyncio.sleep(delay)
            await self._queue.put(message)
        else:
            message.status = MessageStatus.FAILED
            logger.error(
                f"Message {message.id} permanently failed after "
                f"{message.retry_count} attempts: {message.error}"
            )

    def _persist_message(self, message: VoiceMessage):
        """Persist message state to disk."""
        if not self.config.persist_path:
            return

        try:
            persist_dir = self.config.persist_path
            persist_dir.mkdir(parents=True, exist_ok=True)

            # Save metadata
            meta_file = persist_dir / f"{message.id}.json"
            with open(meta_file, "w") as f:
                json.dump(message.to_dict(), f)

            # Save audio data
            audio_file = persist_dir / f"{message.id}.audio"
            with open(audio_file, "wb") as f:
                f.write(message.audio_data)

        except Exception as e:
            logger.error(f"Failed to persist message {message.id}: {e}")

    def _load_persisted(self):
        """Load persisted messages from disk."""
        if not self.config.persist_path or not self.config.persist_path.exists():
            return

        try:
            for meta_file in self.config.persist_path.glob("*.json"):
                message_id = meta_file.stem
                audio_file = self.config.persist_path / f"{message_id}.audio"

                if not audio_file.exists():
                    continue

                with open(meta_file) as f:
                    data = json.load(f)

                with open(audio_file, "rb") as f:
                    audio_data = f.read()

                message = VoiceMessage.from_dict(data, audio_data)

                # Re-queue pending/retrying messages
                if message.status in (MessageStatus.PENDING, MessageStatus.RETRYING):
                    self._messages[message.id] = message
                    asyncio.create_task(self._queue.put(message))
                    logger.info(f"Restored message {message.id} to queue")

        except Exception as e:
            logger.error(f"Failed to load persisted messages: {e}")

    @property
    def pending_count(self) -> int:
        """Number of pending messages."""
        return sum(
            1 for m in self._messages.values()
            if m.status == MessageStatus.PENDING
        )

    @property
    def processing_count(self) -> int:
        """Number of messages being processed."""
        return sum(
            1 for m in self._messages.values()
            if m.status == MessageStatus.PROCESSING
        )

    @property
    def completed_count(self) -> int:
        """Number of completed messages."""
        return sum(
            1 for m in self._messages.values()
            if m.status == MessageStatus.COMPLETED
        )

    @property
    def failed_count(self) -> int:
        """Number of failed messages."""
        return sum(
            1 for m in self._messages.values()
            if m.status == MessageStatus.FAILED
        )

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return {
            "total": len(self._messages),
            "pending": self.pending_count,
            "processing": self.processing_count,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "queue_size": self._queue.qsize(),
            "running": self._running,
            "workers": len(self._workers),
        }
