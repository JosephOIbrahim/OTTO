"""Chat interface — core conversation management.

Manages the conversation loop between the user and OTTO:

1. Accept user input
2. Collect ambient signals from services
3. Route through NEXUS pipeline
4. Track conversation history + compaction
5. Return response

The chat module is platform-agnostic — it's the logic layer.
TUI (Textual) and MCP wrap this for their respective surfaces.

[He2025]: Message ordering is deterministic.  Conversation
history is a time-ordered list.  Token estimation uses fixed
heuristics (no randomness).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from otto.api.effort import EffortLevel
from otto.api.nexus import NEXUSPipeline
from otto.api.compaction import CompactionManager
from otto.services.base import ServiceRegistry


# Rough token estimation: ~4 chars per token (English average)
_CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class ChatMessage:
    """A single message in a conversation.

    Frozen — messages are immutable facts once created.

    Attributes:
        role: Message role (``"user"``, ``"assistant"``, ``"system"``).
        content: Message text.
        timestamp: When the message was created (UTC).
        metadata: Optional routing/pipeline metadata for introspection.
            May include: expert, effort, signal_count, supporting.
    """

    role: str
    content: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationHistory:
    """Manages ordered message history with token estimation.

    Maintains a list of ChatMessages with a configurable maximum.
    When the limit is reached, oldest messages are dropped (FIFO).

    Token estimation uses a character-based heuristic (~4 chars/token)
    for compaction threshold tracking.

    Args:
        max_messages: Maximum messages to retain (default 200).
    """

    def __init__(self, max_messages: int = 200) -> None:
        self._messages: list[ChatMessage] = []
        self._max_messages = max_messages

    def add(self, message: ChatMessage) -> None:
        """Add a message to history.  Drops oldest if at limit."""
        self._messages.append(message)
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages :]

    def to_api_format(self) -> list[dict[str, str]]:
        """Convert history to Anthropic Messages API format.

        Excludes system messages (those are handled separately
        by the pipeline as system prompts).

        Returns:
            List of ``{"role": "...", "content": "..."}`` dicts.
        """
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self._messages
            if msg.role in ("user", "assistant")
        ]

    def estimate_tokens(self) -> int:
        """Estimate total tokens in conversation history.

        Uses a rough heuristic of ~4 characters per token.
        Sufficient for compaction threshold tracking.

        Returns:
            Estimated token count (minimum 1 if non-empty).
        """
        total_chars = sum(len(msg.content) for msg in self._messages)
        if total_chars == 0:
            return 0
        return max(1, total_chars // _CHARS_PER_TOKEN)

    @property
    def messages(self) -> list[ChatMessage]:
        """All messages in order (copy)."""
        return list(self._messages)

    @property
    def count(self) -> int:
        """Number of messages."""
        return len(self._messages)

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()

    @property
    def last(self) -> ChatMessage | None:
        """Most recent message, or None if empty."""
        return self._messages[-1] if self._messages else None


class ChatSession:
    """Core chat session — orchestrates the conversation loop.

    Connects the NEXUS pipeline, service registry, and compaction
    manager into a coherent conversation experience.

    Args:
        pipeline: NEXUSPipeline for routing and API calls.
        services: Optional ServiceRegistry for ambient signals.
        compaction: Optional CompactionManager for token tracking.
        history: Optional ConversationHistory (creates default).
    """

    def __init__(
        self,
        pipeline: NEXUSPipeline,
        services: ServiceRegistry | None = None,
        compaction: CompactionManager | None = None,
        history: ConversationHistory | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._services = services
        self._compaction = compaction
        self._history = history or ConversationHistory()
        self._exchange_count = 0
        self._start_time = datetime.now(timezone.utc)

    @property
    def history(self) -> ConversationHistory:
        """The conversation history."""
        return self._history

    @property
    def services(self) -> ServiceRegistry | None:
        """The active service registry (if any)."""
        return self._services

    @property
    def exchange_count(self) -> int:
        """Number of completed exchanges (user -> assistant)."""
        return self._exchange_count

    def send(
        self,
        text: str,
        state: dict[str, Any] | None = None,
        effort_override: EffortLevel | None = None,
    ) -> ChatMessage:
        """Send a user message and get a response.

        Steps:

        1. Collect service signals (if registry active)
        2. Build state from signals + explicit overrides
        3. Add user message to history
        4. Process through NEXUS pipeline
        5. Track compaction tokens
        6. Add response to history
        7. Return response as ChatMessage

        Args:
            text: User's input text.
            state: Optional explicit state overrides.
            effort_override: Force a specific effort level.

        Returns:
            The assistant's response as a ChatMessage.
        """
        now = datetime.now(timezone.utc)

        # Step 1: Collect service signals
        ambient_state: dict[str, Any] = dict(state or {})
        if self._services is not None:
            signals = self._services.get_all_signals()
            for sig in signals:
                # Don't overwrite explicit state with ambient
                if sig.category not in ambient_state:
                    ambient_state[sig.category] = sig.value

        # Step 2: Add user message to history
        user_msg = ChatMessage(role="user", content=text, timestamp=now)
        self._history.add(user_msg)

        # Step 3: Process through pipeline
        # Exclude current user msg — pipeline adds it internally
        conversation = self._history.to_api_format()[:-1]
        result = self._pipeline.process(
            user_message=text,
            conversation=conversation,
            state=ambient_state,
            effort_override=effort_override,
        )

        # Step 4: Build response metadata
        metadata: dict[str, Any] = {
            "expert": result.selection.primary.expert,
            "effort": result.effort.value,
            "signal_count": len(result.signals),
        }
        if result.selection.supporting:
            metadata["supporting"] = [
                s.expert for s in result.selection.supporting
            ]

        # Step 5: Track compaction
        if self._compaction is not None and result.response is not None:
            self._compaction.record_exchange(
                input_tokens=result.response.input_tokens,
                output_tokens=result.response.output_tokens,
            )

        # Step 6: Build response message
        content = result.response.content if result.response else ""
        response_msg = ChatMessage(
            role="assistant",
            content=content,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata,
        )
        self._history.add(response_msg)
        self._exchange_count += 1

        return response_msg

    def session_duration_minutes(self) -> float:
        """Minutes since session started."""
        elapsed = datetime.now(timezone.utc) - self._start_time
        return elapsed.total_seconds() / 60.0
