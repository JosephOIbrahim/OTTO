"""
Discord Adapter
===============

Adapter layer connecting Discord messages to OTTO's cognitive orchestrator.

Determinism:
- Fixed seed for any randomized operations
- Sorted key iteration in session management
- Deterministic state transitions
- Session state persistence per user_id

Design Principles:
1. Privacy-first: Store minimal user data
2. Deterministic: Same inputs produce same routing
3. Graceful degradation: Discord failures don't crash OTTO
4. Stateless where possible: State lives in cognitive orchestrator
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Union

from ..cognitive_orchestrator import (
    CognitiveOrchestrator,
    NexusResult,
    KnowledgeResult,
    create_orchestrator,
)
from ..cognitive_state import (
    BurnoutLevel,
    EnergyLevel,
    MomentumPhase,
    CognitiveMode,
)
from ..parameter_locker import ThinkDepth
from ..memory import get_memory, Episode, EpisodeQuery, Outcome, OTTOMemory
from ..substrate.protection import get_protection, SubstrateProtectionError

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

logger = logging.getLogger(__name__)


# Fixed constants
_DETERMINISM_SEED: Final[int] = 0xCAFEBABE
_SESSION_TIMEOUT_SECONDS: Final[int] = 7200  # 2 hours
_MAX_MESSAGE_LENGTH: Final[int] = 2000  # Discord limit


@dataclass
class DiscordSession:
    """
    Session state for a Discord user.

    Determinism:
    - All fields have fixed defaults
    - State transitions are deterministic
    - Session timeout is fixed (2 hours)
    """
    user_id: int
    channel_id: int
    guild_id: Optional[int] = None  # None for DMs
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    message_count: int = 0

    # Cognitive state links
    burnout_level: str = "GREEN"
    energy_level: str = "medium"
    momentum_phase: str = "cold_start"
    mode: str = "focused"

    # Session metadata
    username: Optional[str] = None
    display_name: Optional[str] = None

    @property
    def session_id(self) -> str:
        """
        Deterministic session ID from user_id and created_at.

        Uses fixed hash algorithm.
        """
        data = f"{self.user_id}:{self.created_at}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    @property
    def is_expired(self) -> bool:
        """Check if session has timed out (2 hours)."""
        return (time.time() - self.last_activity) > _SESSION_TIMEOUT_SECONDS

    @property
    def duration_seconds(self) -> float:
        """Session duration in seconds."""
        return time.time() - self.created_at

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()
        self.message_count += 1

    def update_cognitive_state(
        self,
        burnout: Optional[BurnoutLevel] = None,
        energy: Optional[EnergyLevel] = None,
        momentum: Optional[MomentumPhase] = None,
        mode: Optional[CognitiveMode] = None,
    ) -> None:
        """
        Update session with cognitive state.

        Only updates non-None values.
        """
        if burnout is not None:
            self.burnout_level = burnout.value
        if energy is not None:
            self.energy_level = energy.value
        if momentum is not None:
            self.momentum_phase = momentum.value
        if mode is not None:
            self.mode = mode.value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscordSession":
        """Deserialize session from dict."""
        return cls(**data)


@dataclass
class DiscordMessage:
    """
    Normalized Discord message for processing.

    Privacy-first: Only stores necessary metadata.
    """
    message_id: int
    user_id: int
    channel_id: int
    text: str
    timestamp: float
    guild_id: Optional[int] = None
    reply_to_message_id: Optional[int] = None
    is_dm: bool = False

    @property
    def is_command(self) -> bool:
        """Check if message is a bot command."""
        return self.text.startswith("/")

    @property
    def command(self) -> Optional[str]:
        """Extract command name if this is a command."""
        if not self.is_command:
            return None
        parts = self.text.split()
        return parts[0][1:].lower() if parts else None  # Remove leading /


@dataclass
class DiscordResponse:
    """
    Response to send back to Discord.
    """
    text: str
    channel_id: int
    reply_to_message_id: Optional[int] = None

    # Cognitive metadata for status display
    anchor: Optional[str] = None
    expert: Optional[str] = None
    processing_time_ms: float = 0.0

    # Discord-specific
    embed_data: Optional[Dict[str, Any]] = None
    ephemeral: bool = False

    def truncate(self) -> "DiscordResponse":
        """Truncate text to Discord's limit if needed."""
        if len(self.text) <= _MAX_MESSAGE_LENGTH:
            return self

        truncated = self.text[:_MAX_MESSAGE_LENGTH - 50]
        truncated += "\n\n...(message truncated)"
        return DiscordResponse(
            text=truncated,
            channel_id=self.channel_id,
            reply_to_message_id=self.reply_to_message_id,
            anchor=self.anchor,
            expert=self.expert,
            processing_time_ms=self.processing_time_ms,
            embed_data=self.embed_data,
            ephemeral=self.ephemeral,
        )


class DiscordAdapter:
    """
    Adapter connecting Discord to OTTO's cognitive orchestrator.

    Determinism:
    - Sessions stored in sorted dict by user_id
    - Fixed evaluation order in process_message
    - Deterministic state transitions

    Usage:
        adapter = DiscordAdapter()
        response = adapter.process_message(discord_message)
        # Send response.text back to Discord
    """

    def __init__(
        self,
        orchestrator: Optional[CognitiveOrchestrator] = None,
        session_store_path: Optional[Path] = None,
        response_generator: Optional["ResponseGenerator"] = None,
        memory: Optional[OTTOMemory] = None,
    ):
        """
        Initialize adapter.

        Args:
            orchestrator: Cognitive orchestrator (creates default if None)
            session_store_path: Path to persist sessions (optional)
            response_generator: LLM response generator (optional, for async generation)
            memory: OTTOMemory instance (uses singleton if None)
        """
        self.orchestrator = orchestrator or create_orchestrator()
        self.session_store_path = session_store_path
        self.response_generator = response_generator

        # Memory backbone integration
        self._memory = memory or get_memory()

        # Session dict - iterate in sorted order
        self._sessions: Dict[int, DiscordSession] = {}

        # Load persisted sessions if path provided
        if session_store_path and session_store_path.exists():
            self._load_sessions()

    def process_message(self, message: DiscordMessage) -> DiscordResponse:
        """
        Process a Discord message through the cognitive pipeline.

        Fixed evaluation order:
        1. Get/create session
        2. Check for commands
        3. Route through orchestrator
        4. Build response
        5. Update session state

        Args:
            message: Normalized Discord message

        Returns:
            Response to send back to Discord
        """
        start_time = time.time()

        # Step 1: Get or create session
        session = self._get_or_create_session(message)
        session.touch()

        # Step 2: Handle commands
        if message.is_command:
            response = self._handle_command(message, session)
            response.processing_time_ms = (time.time() - start_time) * 1000
            return response

        # Step 3: Route through cognitive orchestrator
        result = self.orchestrator.process_message(
            message=message.text,
            context={
                "platform": "discord",
                "user_id": message.user_id,
                "session_id": session.session_id,
                "guild_id": message.guild_id,
                "is_dm": message.is_dm,
            }
        )

        # Step 4: Build response
        response = self._build_response(result, message, session)
        response.processing_time_ms = (time.time() - start_time) * 1000

        # Step 5: Update session with cognitive state
        state = self.orchestrator.get_state()
        session.update_cognitive_state(
            burnout=state.burnout_level,
            energy=state.energy_level,
            momentum=state.momentum_phase,
            mode=state.mode,
        )

        # Step 6: Record episode to memory backbone
        self._record_episode(message, response, session)

        # Step 7: Deposit trail for trust tracking
        self._deposit_trail(response.expert or "direct", success=True)

        # Persist sessions if store configured
        if self.session_store_path:
            self._save_sessions()

        logger.info(
            f"Processed message for user {message.user_id}: "
            f"{response.anchor} ({response.processing_time_ms:.1f}ms)"
        )

        return response

    async def process_message_async(self, message: DiscordMessage) -> DiscordResponse:
        """
        Process a Discord message with async LLM generation.

        Same as process_message but uses ResponseGenerator for actual LLM responses.

        Fixed evaluation order:
        1. Get/create session
        2. Check for commands
        3. Route through orchestrator
        4. Generate response via LLM
        5. Update session state

        Args:
            message: Normalized Discord message

        Returns:
            Response with LLM-generated text
        """
        start_time = time.time()

        # Step 1: Get or create session
        session = self._get_or_create_session(message)
        session.touch()

        # Step 2: Handle commands (sync - no LLM needed)
        if message.is_command:
            response = self._handle_command(message, session)
            response.processing_time_ms = (time.time() - start_time) * 1000
            return response

        # Step 3: Route through cognitive orchestrator
        result = self.orchestrator.process_message(
            message=message.text,
            context={
                "platform": "discord",
                "user_id": message.user_id,
                "session_id": session.session_id,
                "guild_id": message.guild_id,
                "is_dm": message.is_dm,
            }
        )

        # Step 4: Build response with LLM generation
        response = await self._build_response_async(result, message, session)
        response.processing_time_ms = (time.time() - start_time) * 1000

        # Step 5: Update session with cognitive state
        state = self.orchestrator.get_state()
        session.update_cognitive_state(
            burnout=state.burnout_level,
            energy=state.energy_level,
            momentum=state.momentum_phase,
            mode=state.mode,
        )

        # Step 6: Record episode to memory backbone
        self._record_episode(message, response, session)

        # Step 7: Deposit trail for trust tracking
        self._deposit_trail(response.expert or "direct", success=True)

        # Persist sessions if store configured
        if self.session_store_path:
            self._save_sessions()

        logger.info(
            f"Processed message for user {message.user_id}: "
            f"{response.anchor} ({response.processing_time_ms:.1f}ms)"
        )

        return response

    def _get_or_create_session(self, message: DiscordMessage) -> DiscordSession:
        """
        Get existing session or create new one.

        Deterministic session creation.
        """
        user_id = message.user_id

        # Check for existing session
        if user_id in self._sessions:
            session = self._sessions[user_id]

            # Reset if expired
            if session.is_expired:
                logger.info(f"Session expired for user {user_id}, creating new")
                del self._sessions[user_id]
            else:
                return session

        # Create new session
        session = DiscordSession(
            user_id=user_id,
            channel_id=message.channel_id,
            guild_id=message.guild_id,
        )
        self._sessions[user_id] = session

        # Reset orchestrator for new session
        self.orchestrator.reset_session()

        logger.info(f"Created new session for user {user_id}: {session.session_id}")
        return session

    def _handle_command(
        self,
        message: DiscordMessage,
        session: DiscordSession
    ) -> DiscordResponse:
        """
        Handle bot commands.

        Commands:
        - /start: Welcome message
        - /status: Current cognitive state
        - /reset: Reset session
        - /help: Available commands
        - /calibrate: Start calibration
        """
        command = message.command

        if command == "start":
            return self._cmd_start(message, session)
        elif command == "status":
            return self._cmd_status(message, session)
        elif command == "reset":
            return self._cmd_reset(message, session)
        elif command == "calibrate":
            return self._cmd_calibrate(message, session)
        elif command == "help":
            return self._cmd_help(message, session)
        else:
            return DiscordResponse(
                text=f"Unknown command: /{command}\nUse /help to see available commands.",
                channel_id=message.channel_id,
                reply_to_message_id=message.message_id,
            )

    def _cmd_start(
        self,
        message: DiscordMessage,
        session: DiscordSession
    ) -> DiscordResponse:
        """Handle /start command."""
        text = (
            "**Welcome to OTTO**\n\n"
            "I'm an adaptive assistant that learns how you work best.\n\n"
            "Just chat with me naturally. I'll pick up on your patterns and "
            "adapt my responses to match your energy and focus.\n\n"
            "**Quick commands:**\n"
            "- `/status` - See how I think you're doing\n"
            "- `/calibrate` - Set your current state\n"
            "- `/reset` - Start fresh\n"
            "- `/help` - More info\n\n"
            "What can I help you with?"
        )

        return DiscordResponse(
            text=text,
            channel_id=message.channel_id,
            reply_to_message_id=message.message_id,
        )

    def _cmd_status(
        self,
        message: DiscordMessage,
        session: DiscordSession
    ) -> DiscordResponse:
        """Handle /status command."""
        state = self.orchestrator.get_state()

        # Build status embed data
        embed_data = {
            "title": "Your Current State",
            "color": self._burnout_color(session.burnout_level),
            "fields": [
                {"name": "Energy", "value": session.energy_level, "inline": True},
                {"name": "Burnout", "value": session.burnout_level, "inline": True},
                {"name": "Momentum", "value": session.momentum_phase, "inline": True},
                {"name": "Mode", "value": session.mode, "inline": True},
                {"name": "Messages", "value": str(session.message_count), "inline": True},
            ],
        }

        # Add guidance based on state
        guidance = self._get_guidance(session)
        if guidance:
            embed_data["footer"] = {"text": guidance}

        return DiscordResponse(
            text="",
            channel_id=message.channel_id,
            embed_data=embed_data,
            ephemeral=True,  # Only visible to user
        )

    def _cmd_reset(
        self,
        message: DiscordMessage,
        session: DiscordSession
    ) -> DiscordResponse:
        """Handle /reset command."""
        # Remove session
        if message.user_id in self._sessions:
            del self._sessions[message.user_id]

        # Reset orchestrator
        self.orchestrator.reset_session()

        return DiscordResponse(
            text="Session reset. Fresh start.",
            channel_id=message.channel_id,
            reply_to_message_id=message.message_id,
        )

    def _cmd_calibrate(
        self,
        message: DiscordMessage,
        session: DiscordSession
    ) -> DiscordResponse:
        """Handle /calibrate command."""
        text = (
            "**Quick Calibration**\n\n"
            "How scattered or focused are you right now?\n"
            "1. Scattered - thoughts all over\n"
            "2. Moderate - somewhat focused\n"
            "3. Locked in - deep focus\n\n"
            "Just reply with a number (1-3), or describe how you're feeling."
        )

        return DiscordResponse(
            text=text,
            channel_id=message.channel_id,
            reply_to_message_id=message.message_id,
        )

    def _cmd_help(
        self,
        message: DiscordMessage,
        session: DiscordSession
    ) -> DiscordResponse:
        """Handle /help command."""
        text = (
            "**OTTO Commands**\n\n"
            "`/start` - Introduction and setup\n"
            "`/status` - See your current cognitive state\n"
            "`/calibrate` - Calibrate your current state\n"
            "`/reset` - Clear session and start fresh\n"
            "`/help` - This message\n\n"
            "**Tips:**\n"
            "- Mention me or DM me to chat\n"
            "- I adapt to your energy and focus\n"
            "- If you're frustrated, I'll notice and adjust\n"
            "- Use /status to see how I'm reading you"
        )

        return DiscordResponse(
            text=text,
            channel_id=message.channel_id,
            reply_to_message_id=message.message_id,
        )

    def _build_response(
        self,
        result: Union[NexusResult, KnowledgeResult],
        message: DiscordMessage,
        session: DiscordSession,
    ) -> DiscordResponse:
        """
        Build Discord response from orchestrator result.

        Fixed response building order.
        """
        # Get anchor and expert from result
        anchor = result.to_anchor()

        if isinstance(result, NexusResult):
            expert = result.routing.expert.value
            # Build response text based on expert and state
            response_text = self._render_response(result, session)
        else:
            # KnowledgeResult - direct knowledge response
            expert = "knowledge"
            prim = result.top_prim
            if prim:
                response_text = f"**{prim.summary}**\n\n{prim.content}"
            else:
                response_text = "I couldn't find specific information on that."

        return DiscordResponse(
            text=response_text,
            channel_id=message.channel_id,
            reply_to_message_id=message.message_id,
            anchor=anchor,
            expert=expert,
        )

    async def _build_response_async(
        self,
        result: Union[NexusResult, KnowledgeResult],
        message: DiscordMessage,
        session: DiscordSession,
    ) -> DiscordResponse:
        """
        Build Discord response with async LLM generation.

        Fixed response building order.
        """
        # Get anchor and expert from result
        anchor = result.to_anchor()

        if isinstance(result, NexusResult):
            expert = result.routing.expert.value
            # Generate response via LLM
            response_text = await self._render_response_async(
                result, session, message.text
            )
        else:
            # KnowledgeResult - direct knowledge response (no LLM needed)
            expert = "knowledge"
            prim = result.top_prim
            if prim:
                response_text = f"**{prim.summary}**\n\n{prim.content}"
            else:
                response_text = "I couldn't find specific information on that."

        return DiscordResponse(
            text=response_text,
            channel_id=message.channel_id,
            reply_to_message_id=message.message_id,
            anchor=anchor,
            expert=expert,
        )

    async def _render_response_async(
        self,
        result: NexusResult,
        session: DiscordSession,
        user_message: str,
    ) -> str:
        """
        Generate response text using LLM.

        Uses ResponseGenerator if available, falls back to sync render.

        Determinism:
        - Retrieves conversation history in fixed order (oldest to newest)
        - Deterministic context building
        """
        if not self.response_generator or not LLM_AVAILABLE:
            # Fall back to sync version
            return self._render_response(result, session)

        expert = result.routing.expert.value

        # Retrieve conversation history from memory backbone
        conversation_history = self._get_conversation_history(
            user_id=session.user_id,
            limit=10,  # Last 10 exchanges provides good context
        )

        # Build generation context from session state
        from ..llm.response_generator import GenerationContext
        context = GenerationContext(
            expert=expert,
            burnout_level=session.burnout_level,
            energy_level=session.energy_level,
            momentum_phase=session.momentum_phase,
            mode=session.mode,
            platform="discord",
            user_id=session.user_id,
            session_id=session.session_id,
            conversation_history=conversation_history,
        )

        try:
            # Generate response via LLM
            response = await self.response_generator.generate(
                message=user_message,
                context=context,
            )
            return response
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fall back to sync version on error
            return self._render_response(result, session)

    def _render_response(
        self,
        result: NexusResult,
        session: DiscordSession,
    ) -> str:
        """
        Render response text based on NEXUS result and session state.

        This is where expert-specific responses are built.
        """
        expert = result.routing.expert.value

        # Base acknowledgment based on expert
        if expert == "Validator":
            # User is frustrated - empathy first
            prefix = "I hear you. "
        elif expert == "Scaffolder":
            # User is stuck/overwhelmed - break it down
            prefix = "Let's break this down. "
        elif expert == "Restorer":
            # User is depleted - easy mode
            prefix = "Take it easy. "
        elif expert == "Celebrator":
            # Task completed - acknowledge
            prefix = "Nice work! "
        elif expert == "Socratic":
            # Exploring mode - guide discovery
            prefix = ""
        else:
            # Direct mode - minimal friction
            prefix = ""

        # Build response (in real implementation, this would generate content)
        response = f"{prefix}How can I help you with this?"

        return response

    def _burnout_color(self, level: str) -> int:
        """Map burnout level to Discord embed color (int)."""
        colors = {
            "GREEN": 0x2ECC71,   # Green
            "YELLOW": 0xF1C40F,  # Gold
            "ORANGE": 0xE67E22,  # Orange
            "RED": 0xE74C3C,     # Red
        }
        return colors.get(level, 0x95A5A6)  # Grey default

    def _get_guidance(self, session: DiscordSession) -> Optional[str]:
        """Get gentle guidance based on current state."""
        burnout = session.burnout_level
        energy = session.energy_level

        if burnout == "RED":
            return "You've been pushing hard. It's okay to stop."
        elif burnout == "ORANGE":
            return "Noticing some strain. What's the blocker?"
        elif energy == "depleted":
            return "Running low. Easy wins or rest?"
        elif energy == "high":
            return "Good energy. Let's use it."

        return None

    def _load_sessions(self) -> None:
        """
        Load persisted sessions from disk.

        Uses encrypted storage if protection is set up, otherwise falls
        back to plaintext with a warning.

        Determinism: Fixed evaluation order, sorted iteration.
        """
        # Try encrypted storage first (preferred)
        try:
            protection = get_protection()
            if protection.is_setup() and protection.is_unlocked():
                data = protection.read_protected_json("sessions/discord.json")
                for user_id_str, session_data in sorted(data.items()):
                    session = DiscordSession.from_dict(session_data)
                    if not session.is_expired:
                        self._sessions[int(user_id_str)] = session
                logger.info(f"Loaded {len(self._sessions)} encrypted sessions")
                return
        except SubstrateProtectionError:
            pass  # Protection not set up, fall through to plaintext
        except FileNotFoundError:
            return  # No sessions file yet
        except Exception as e:
            logger.debug(f"Encrypted load failed, trying plaintext: {e}")

        # Fall back to plaintext (legacy or protection not set up)
        if not self.session_store_path or not self.session_store_path.exists():
            return

        try:
            data = json.loads(self.session_store_path.read_text())

            for user_id_str, session_data in sorted(data.items()):
                session = DiscordSession.from_dict(session_data)

                # Skip expired sessions
                if not session.is_expired:
                    self._sessions[int(user_id_str)] = session

            logger.info(f"Loaded {len(self._sessions)} sessions from disk")
            logger.warning(
                "Sessions loaded from PLAINTEXT storage. "
                "Run 'otto protection setup' to enable encryption."
            )

        except Exception as e:
            logger.warning(f"Failed to load sessions: {e}")

    def _save_sessions(self) -> None:
        """
        Save sessions to disk.

        Uses encrypted storage if protection is set up, otherwise falls
        back to plaintext with a warning.

        Determinism: Sorted keys for deterministic output.
        """
        # Sort by user_id for deterministic output
        data = {
            str(user_id): session.to_dict()
            for user_id, session in sorted(self._sessions.items())
        }

        # Try encrypted storage first (preferred)
        try:
            protection = get_protection()
            if protection.is_setup() and protection.is_unlocked():
                protection.write_protected_json("sessions/discord.json", data)
                logger.debug("Sessions saved with encryption")
                return
        except SubstrateProtectionError as e:
            logger.debug(f"Encrypted save unavailable: {e}")
        except Exception as e:
            logger.warning(f"Failed to save encrypted sessions: {e}")

        # Fall back to plaintext (legacy or protection not set up)
        if not self.session_store_path:
            return

        try:
            # Ensure parent directory exists
            self.session_store_path.parent.mkdir(parents=True, exist_ok=True)

            self.session_store_path.write_text(
                json.dumps(data, indent=2, sort_keys=True)
            )
            logger.debug(
                "Sessions saved in PLAINTEXT. "
                "Run 'otto protection setup' to enable encryption."
            )

        except Exception as e:
            logger.warning(f"Failed to save sessions: {e}")

    def _record_episode(
        self,
        message: DiscordMessage,
        response: DiscordResponse,
        session: DiscordSession,
    ) -> None:
        """
        Record message processing episode to memory backbone.

        This enables cross-surface visibility - actions in Discord
        are visible to other surfaces (Telegram, CLI, etc.)

        Fixed data structure for deterministic recording.
        """
        # Generate unique episode type including timestamp for uniqueness
        # This ensures each message gets its own trail entry (not reinforced)
        from datetime import datetime
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        unique_episode_type = f"surface.discord.message.{message.user_id}.{timestamp_ms}"

        logger.info(
            f"[MEMORY DEBUG] Recording episode: user_id={message.user_id}, "
            f"type={unique_episode_type}, "
            f"user_msg='{message.text[:50]}...', "
            f"asst_response='{response.text[:50]}...'"
        )
        try:
            episode = Episode(
                type=unique_episode_type,
                data={
                    "user_id": message.user_id,
                    "guild_id": message.guild_id,
                    "is_dm": message.is_dm,
                    "expert": response.expert or "direct",
                    "anchor": response.anchor,
                    "processing_time_ms": response.processing_time_ms,
                    "burnout_level": session.burnout_level,
                    "energy_level": session.energy_level,
                    "momentum_phase": session.momentum_phase,
                    # Store conversation content for history retrieval
                    "user_message": message.text,
                    "assistant_response": response.text,
                },
                outcome=Outcome.SUCCESS,
                actor="discord_adapter",
                service="discord",
            )
            self._memory.record_episode(episode)
        except Exception as e:
            logger.warning(f"Failed to record episode: {e}")

    def _deposit_trail(self, expert: str, success: bool) -> None:
        """
        Deposit trail for trust tracking.

        Trails enable auto-approval when trust is established.

        Fixed action format for deterministic trail matching.
        """
        try:
            action = f"discord.{expert.lower()}"
            outcome = Outcome.SUCCESS if success else Outcome.FAILURE
            self._memory.deposit_trail(action=action, outcome=outcome)
        except Exception as e:
            logger.warning(f"Failed to deposit trail: {e}")

    def _get_conversation_history(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List["ConversationTurn"]:
        """
        Retrieve recent conversation history for a user.

        Queries memory backbone for recent episodes and builds
        ConversationTurn list for multi-turn context.

        Determinism:
        - Fixed order: oldest to newest for proper conversation flow
        - Deterministic filtering and sorting
        - No random selection of history

        Args:
            user_id: Discord user ID to retrieve history for
            limit: Maximum number of conversation exchanges to return

        Returns:
            List of ConversationTurn objects, oldest first
        """
        if not self._memory or not LLM_AVAILABLE or ConversationTurn is None:
            return []

        try:
            # Query recent Discord message episodes
            # Note: EpisodeQuery doesn't filter by user_id directly,
            # so we query more and filter post-hoc
            # Use prefix "surface.discord.message" to match all unique episode types
            query = EpisodeQuery(
                type="surface.discord.message",  # Prefix match in query_mock
                service="discord",
                limit=limit * 3,  # Over-fetch to account for other users
                min_strength=0.0,  # Include all episodes
            )
            episodes = self._memory.query_episodes(query)

            logger.info(
                f"[MEMORY DEBUG] query_episodes returned {len(episodes)} episodes"
            )
            for ep in episodes:
                logger.info(
                    f"[MEMORY DEBUG] Episode: type={ep.type}, "
                    f"user_id={ep.data.get('user_id')}, "
                    f"has_user_msg={bool(ep.data.get('user_message'))}, "
                    f"has_asst_msg={bool(ep.data.get('assistant_response'))}"
                )

            # Filter by user_id (stored in episode.data)
            user_episodes = [
                ep for ep in episodes
                if ep.data.get("user_id") == user_id
            ]
            logger.info(
                f"[MEMORY DEBUG] After user_id filter ({user_id}): {len(user_episodes)} episodes"
            )

            # Sort by timestamp ascending (oldest first)
            # This ensures conversation flows naturally to the LLM
            user_episodes = sorted(
                user_episodes,
                key=lambda e: e.timestamp,
            )

            # Take only the most recent N episodes
            user_episodes = user_episodes[-limit:]

            # Build conversation turns
            turns: List[ConversationTurn] = []
            for ep in user_episodes:
                # Add user message if stored
                user_msg = ep.data.get("user_message")
                if user_msg:
                    turns.append(ConversationTurn(
                        role="user",
                        content=user_msg,
                    ))

                # Add assistant response if stored
                assistant_msg = ep.data.get("assistant_response")
                if assistant_msg:
                    turns.append(ConversationTurn(
                        role="assistant",
                        content=assistant_msg,
                    ))

            logger.debug(
                f"Retrieved {len(turns)} conversation turns for user {user_id}"
            )
            return turns

        except Exception as e:
            logger.warning(f"Failed to retrieve conversation history: {e}")
            return []

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.

        Returns:
            Number of sessions removed
        """
        # Iterate in sorted order
        expired = [
            user_id for user_id in sorted(self._sessions.keys())
            if self._sessions[user_id].is_expired
        ]

        for user_id in expired:
            del self._sessions[user_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)


# Export session timeout for tests
__all__ = [
    "DiscordAdapter",
    "DiscordSession",
    "DiscordMessage",
    "DiscordResponse",
    "_SESSION_TIMEOUT_SECONDS",
]
