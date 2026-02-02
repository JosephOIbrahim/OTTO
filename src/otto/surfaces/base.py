"""
Interaction Surface Base
========================

Abstract base for interaction surfaces with OTTO.

A surface is the interface between a user and the system.
Different surfaces (CLI, desktop, voice, API) have different
interaction patterns but share the same core interface.

ThinkingMachines [He2025] Compliance:
- Fixed message normalization
- Deterministic rendering order
- Sorted metadata iteration
"""

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Final, List, Optional, TypeVar

logger = logging.getLogger(__name__)

# ============================================================================
# Constants - [He2025] Compliance
# ============================================================================

SURFACE_SEED: Final[int] = 0x50BFAC3
MESSAGE_HASH_LENGTH: Final[int] = 8


class SurfaceType(str, Enum):
    """Types of interaction surfaces."""
    CLI = "cli"
    DESKTOP = "desktop"
    VOICE = "voice"
    API = "api"
    WEB = "web"


class MessageRole(str, Enum):
    """Role of message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class RenderFormat(str, Enum):
    """Output rendering formats."""
    PLAIN = "plain"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    VOICE = "voice"  # Speech-optimized


# ============================================================================
# Message Types
# ============================================================================

@dataclass
class SurfaceMessage:
    """A message in the conversation.

    Attributes:
        role: Who sent this message
        content: Message content
        timestamp: When message was created
        metadata: Additional metadata (e.g., files, attachments)
        message_id: Unique message identifier
        checksum: Content checksum for integrity
    """
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    message_id: str = ""
    checksum: str = ""

    def __post_init__(self):
        """Generate ID and checksum."""
        if not self.message_id:
            self.message_id = self._generate_id()
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _generate_id(self) -> str:
        """Generate unique message ID."""
        data = f"{self.role.value}|{self.content[:50]}|{self.timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:MESSAGE_HASH_LENGTH]

    def _compute_checksum(self) -> str:
        """Compute content checksum."""
        return hashlib.md5(self.content.encode()).hexdigest()[:MESSAGE_HASH_LENGTH]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(sorted(self.metadata.items())),
            "message_id": self.message_id,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SurfaceMessage":
        """Create from dictionary."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
            message_id=data.get("message_id", ""),
            checksum=data.get("checksum", ""),
        )


@dataclass
class SurfaceResponse:
    """Response from the assistant.

    Attributes:
        content: Response content
        format: Rendering format used
        thinking: Optional thinking process (for transparency)
        tool_calls: Tools invoked during generation
        metadata: Response metadata
        duration_ms: Generation duration
        checksum: Content checksum
    """
    content: str
    format: RenderFormat = RenderFormat.MARKDOWN
    thinking: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            self.checksum = hashlib.md5(self.content.encode()).hexdigest()[:MESSAGE_HASH_LENGTH]

    def to_message(self) -> SurfaceMessage:
        """Convert to SurfaceMessage."""
        return SurfaceMessage(
            role=MessageRole.ASSISTANT,
            content=self.content,
            metadata={
                "format": self.format.value,
                "tool_calls": self.tool_calls,
                "duration_ms": self.duration_ms,
            },
        )


# ============================================================================
# Input Processing
# ============================================================================

@dataclass
class InputContext:
    """Context for input processing.

    Attributes:
        raw_input: Original user input
        normalized_input: Cleaned input
        detected_intent: Detected user intent
        extracted_entities: Entities extracted from input
        attachments: Files or other attachments
    """
    raw_input: str
    normalized_input: str = ""
    detected_intent: str = ""
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.normalized_input:
            self.normalized_input = self._normalize(self.raw_input)

    def _normalize(self, text: str) -> str:
        """Normalize input text (deterministic)."""
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        # Strip
        text = text.strip()
        return text


# ============================================================================
# Surface Base Class
# ============================================================================

class Surface(ABC):
    """Abstract base class for interaction surfaces.

    Surfaces provide:
    - Input processing (normalization, intent detection)
    - Output rendering (format adaptation)
    - Context management (conversation history)
    - Event hooks (for extensions)

    Subclasses implement surface-specific behavior.

    Example:
        class MyCLI(Surface):
            surface_type = SurfaceType.CLI

            def render(self, response: SurfaceResponse) -> str:
                return response.content

            def process_input(self, raw: str) -> InputContext:
                return InputContext(raw_input=raw)
    """

    surface_type: SurfaceType = SurfaceType.CLI

    def __init__(
        self,
        render_format: RenderFormat = RenderFormat.MARKDOWN,
        max_history: int = 100,
    ):
        """Initialize surface.

        Args:
            render_format: Default output format
            max_history: Maximum messages to retain in history
        """
        self.render_format = render_format
        self.max_history = max_history

        # Conversation history
        self._history: List[SurfaceMessage] = []

        # Event callbacks
        self._on_input: List[Callable[[InputContext], None]] = []
        self._on_output: List[Callable[[SurfaceResponse], None]] = []
        self._on_error: List[Callable[[Exception], None]] = []

        # Memory interface (lazy-loaded)
        self._memory = None

        # Session info
        self._session_goal: Optional[str] = None

        logger.info(f"Surface initialized: {self.surface_type.value}")

    def _get_memory(self):
        """Get unified memory interface (lazy load)."""
        if self._memory is None:
            try:
                from ..memory import get_memory
                self._memory = get_memory()
            except ImportError:
                logger.debug("Memory interface not available")
        return self._memory

    # =========================================================================
    # Abstract Methods
    # =========================================================================

    @abstractmethod
    def render(self, response: SurfaceResponse) -> str:
        """Render response for this surface.

        Args:
            response: Response to render

        Returns:
            Rendered string for display
        """
        pass

    @abstractmethod
    def process_input(self, raw_input: str) -> InputContext:
        """Process raw user input.

        Args:
            raw_input: Raw input string

        Returns:
            Processed InputContext
        """
        pass

    @abstractmethod
    def display(self, content: str) -> None:
        """Display content to user.

        Args:
            content: Content to display
        """
        pass

    @abstractmethod
    def prompt(self, message: str = "") -> str:
        """Prompt user for input.

        Args:
            message: Optional prompt message

        Returns:
            User input string
        """
        pass

    # =========================================================================
    # History Management
    # =========================================================================

    def add_to_history(self, message: SurfaceMessage) -> None:
        """Add message to conversation history.

        Args:
            message: Message to add
        """
        self._history.append(message)

        # Trim if over limit
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

    def get_history(self, limit: Optional[int] = None) -> List[SurfaceMessage]:
        """Get conversation history.

        Args:
            limit: Maximum messages to return (newest first)

        Returns:
            List of messages
        """
        if limit:
            return self._history[-limit:]
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    def get_history_for_api(self) -> List[Dict[str, str]]:
        """Get history formatted for API calls.

        Returns:
            List of {role, content} dictionaries
        """
        return [
            {"role": m.role.value, "content": m.content}
            for m in self._history
        ]

    # =========================================================================
    # Event Hooks
    # =========================================================================

    def on_input(self, callback: Callable[[InputContext], None]) -> None:
        """Register input event callback."""
        self._on_input.append(callback)

    def on_output(self, callback: Callable[[SurfaceResponse], None]) -> None:
        """Register output event callback."""
        self._on_output.append(callback)

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """Register error event callback."""
        self._on_error.append(callback)

    def _fire_input(self, context: InputContext) -> None:
        """Fire input event."""
        for callback in self._on_input:
            try:
                callback(context)
            except Exception as e:
                logger.warning(f"Input callback error: {e}")

    def _fire_output(self, response: SurfaceResponse) -> None:
        """Fire output event."""
        for callback in self._on_output:
            try:
                callback(response)
            except Exception as e:
                logger.warning(f"Output callback error: {e}")

    def _fire_error(self, error: Exception) -> None:
        """Fire error event."""
        for callback in self._on_error:
            try:
                callback(error)
            except Exception as e:
                logger.warning(f"Error callback error: {e}")

    # =========================================================================
    # High-Level Operations
    # =========================================================================

    def receive_input(self, raw_input: str) -> InputContext:
        """Receive and process user input.

        Per [He2025]: Deterministic input processing.

        Args:
            raw_input: Raw input from user

        Returns:
            Processed InputContext
        """
        context = self.process_input(raw_input)
        self._fire_input(context)

        # Add to history
        message = SurfaceMessage(
            role=MessageRole.USER,
            content=context.normalized_input,
            metadata={"raw": raw_input},
        )
        self.add_to_history(message)

        # Tick session exchange count
        self.tick_session()

        return context

    def send_response(self, response: SurfaceResponse) -> None:
        """Send response to user.

        Per [He2025]: Deterministic response handling.

        Args:
            response: Response to send
        """
        self._fire_output(response)

        # Render and display
        rendered = self.render(response)
        self.display(rendered)

        # Add to history
        self.add_to_history(response.to_message())

        # Record interaction to memory
        if self._history and len(self._history) >= 2:
            last_user_msg = next(
                (m for m in reversed(self._history[:-1]) if m.role == MessageRole.USER),
                None
            )
            if last_user_msg:
                self.record_interaction(
                    input_text=last_user_msg.content,
                    output_text=response.content,
                    success=True,
                )

    def handle_error(self, error: Exception) -> None:
        """Handle and display error.

        Args:
            error: Error to handle
        """
        self._fire_error(error)
        self.display(f"Error: {error}")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def format_status_line(
        self,
        time_estimate: str,
        goal: str,
        expert: str,
        altitude: str,
        burnout: str,
        momentum: str,
    ) -> str:
        """Format cognitive status line.

        Args:
            time_estimate: Estimated session time
            goal: Current goal
            expert: Active expert
            altitude: Current altitude
            burnout: Burnout level
            momentum: Momentum phase

        Returns:
            Formatted status line
        """
        return f"[{time_estimate} | Goal: {goal} | {expert} | {altitude} | {burnout} | {momentum}]"

    def get_capabilities(self) -> Dict[str, bool]:
        """Get surface capabilities.

        Returns:
            Dictionary of capability -> supported
        """
        return {
            "markdown": self.render_format == RenderFormat.MARKDOWN,
            "html": self.render_format == RenderFormat.HTML,
            "voice": self.render_format == RenderFormat.VOICE,
            "attachments": True,
            "streaming": False,  # Override in subclass
            "rich_text": True,
        }

    # =========================================================================
    # Session Management (Memory Integration)
    # =========================================================================

    def start_session(self, goal: str) -> None:
        """Start a new session with goal.

        Uses unified memory interface for cross-session persistence.
        Per [He2025]: Deterministic session initialization.

        Args:
            goal: Session goal
        """
        self._session_goal = goal
        memory = self._get_memory()

        if memory:
            try:
                memory.start_session(goal)
                logger.info(f"Session started with goal: {goal[:50]}...")
            except Exception as e:
                logger.warning(f"Memory session start failed: {e}")

    def end_session(
        self,
        progress: Optional[List[str]] = None,
        position: str = "",
        next_steps: Optional[List[str]] = None,
    ) -> None:
        """End current session with handoff data.

        Persists session state to memory for cross-session continuity.
        Per [He2025]: Deterministic session termination.

        Args:
            progress: List of completed items
            position: Where we stopped
            next_steps: Suggested next steps
        """
        memory = self._get_memory()

        if memory:
            try:
                memory.end_session(
                    progress=progress or [],
                    position=position or "Session ended",
                    next_steps=next_steps or [],
                )
                logger.info("Session ended and persisted to memory")
            except Exception as e:
                logger.warning(f"Memory session end failed: {e}")

        self._session_goal = None

    def tick_session(self) -> None:
        """Increment session exchange count.

        Called after each exchange for time tracking.
        Per [He2025]: Deterministic exchange counting.
        """
        memory = self._get_memory()

        if memory:
            try:
                memory.tick()
            except Exception as e:
                logger.debug(f"Memory tick failed: {e}")

    def get_session_context(self) -> Dict[str, Any]:
        """Get current session context from memory.

        Returns:
            Session context including goal, state, and history
        """
        memory = self._get_memory()

        if memory:
            try:
                context = memory.get_context()
                return {
                    "goal": context.session_goal or self._session_goal,
                    "exchange_count": context.exchange_count,
                    "expert": context.current_expert,
                    "altitude": context.current_altitude,
                    "burnout": context.burnout_level,
                    "momentum": context.momentum_phase,
                    "mode": context.active_mode,
                    "paradigm": context.active_paradigm,
                    "last_session": context.last_session,
                }
            except Exception as e:
                logger.debug(f"Memory context failed: {e}")

        return {
            "goal": self._session_goal,
            "exchange_count": len(self._history),
        }

    def record_interaction(
        self,
        input_text: str,
        output_text: str,
        success: bool = True,
    ) -> None:
        """Record an interaction to memory as episode.

        Per [He2025]: Deterministic episode recording.

        Args:
            input_text: User input
            output_text: Assistant output
            success: Whether interaction succeeded
        """
        memory = self._get_memory()

        if memory:
            try:
                from ..memory import Episode, Outcome

                episode = Episode(
                    type=f"surface.{self.surface_type.value}.interaction",
                    data={
                        "input_length": len(input_text),
                        "output_length": len(output_text),
                        "had_tool_calls": False,
                    },
                    outcome=Outcome.SUCCESS if success else Outcome.FAILURE,
                    actor="user",
                    service=f"surface.{self.surface_type.value}",
                )
                memory.record_episode(episode)

            except Exception as e:
                logger.debug(f"Memory episode recording failed: {e}")


# ============================================================================
# Surface Factory
# ============================================================================

_surfaces: Dict[SurfaceType, Surface] = {}


def register_surface(surface: Surface) -> None:
    """Register a surface instance.

    Args:
        surface: Surface to register
    """
    _surfaces[surface.surface_type] = surface


def get_surface(surface_type: SurfaceType = SurfaceType.CLI) -> Optional[Surface]:
    """Get registered surface by type.

    Args:
        surface_type: Type of surface to get

    Returns:
        Surface instance if registered, None otherwise
    """
    return _surfaces.get(surface_type)


__all__ = [
    # Enums
    "SurfaceType",
    "MessageRole",
    "RenderFormat",
    # Data classes
    "SurfaceMessage",
    "SurfaceResponse",
    "InputContext",
    # Base class
    "Surface",
    # Factory
    "register_surface",
    "get_surface",
    # Constants
    "SURFACE_SEED",
]
