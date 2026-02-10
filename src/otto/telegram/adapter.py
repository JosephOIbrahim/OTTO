"""
Telegram Adapter
================

Adapter layer connecting Telegram messages to OTTO's cognitive orchestrator.

Determinism:
- Fixed seed for any randomized operations
- Sorted key iteration in session management
- Deterministic state transitions
- Session state persistence per user_id

Design Principles:
1. Privacy-first: Store minimal user data
2. Deterministic: Same inputs produce same routing
3. Graceful degradation: Telegram failures don't crash OTTO
4. Stateless where possible: State lives in cognitive orchestrator
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Final, Optional

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

# Memory integration (Stream A - Concurrent Rollout)
from ..memory import get_memory, Episode, Outcome, OTTOMemory
from ..substrate.protection import get_protection, SubstrateProtectionError

logger = logging.getLogger(__name__)


# Fixed constants
_DETERMINISM_SEED: Final[int] = 0xCAFEBABE
_SESSION_TIMEOUT_SECONDS: Final[int] = 7200  # 2 hours
_MAX_MESSAGE_LENGTH: Final[int] = 4096  # Telegram limit


@dataclass
class TelegramSession:
    """
    Session state for a Telegram user.

    Determinism:
    - All fields have fixed defaults
    - State transitions are deterministic
    - Session timeout is fixed (2 hours)
    """
    user_id: int
    chat_id: int
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
    first_name: Optional[str] = None
    language_code: str = "en"

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
    def from_dict(cls, data: Dict[str, Any]) -> "TelegramSession":
        """Deserialize session from dict."""
        return cls(**data)


@dataclass
class TelegramMessage:
    """
    Normalized Telegram message for processing.

    Privacy-first: Only stores necessary metadata.
    """
    message_id: int
    user_id: int
    chat_id: int
    text: str
    timestamp: float
    reply_to_message_id: Optional[int] = None

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
class TelegramResponse:
    """
    Response to send back to Telegram.
    """
    text: str
    chat_id: int
    reply_to_message_id: Optional[int] = None
    parse_mode: str = "Markdown"

    # Cognitive metadata for status display
    anchor: Optional[str] = None
    expert: Optional[str] = None
    processing_time_ms: float = 0.0

    def truncate(self) -> "TelegramResponse":
        """Truncate text to Telegram's limit if needed."""
        if len(self.text) <= _MAX_MESSAGE_LENGTH:
            return self

        truncated = self.text[:_MAX_MESSAGE_LENGTH - 50]
        truncated += "\n\n...(message truncated)"
        return TelegramResponse(
            text=truncated,
            chat_id=self.chat_id,
            reply_to_message_id=self.reply_to_message_id,
            parse_mode=self.parse_mode,
            anchor=self.anchor,
            expert=self.expert,
            processing_time_ms=self.processing_time_ms,
        )


class TelegramAdapter:
    """
    Adapter connecting Telegram to OTTO's cognitive orchestrator.

    Determinism:
    - Sessions stored in sorted dict by user_id
    - Fixed evaluation order in process_message
    - Deterministic state transitions

    Usage:
        adapter = TelegramAdapter()
        response = adapter.process_message(telegram_message)
        # Send response.text back to Telegram
    """

    def __init__(
        self,
        orchestrator: Optional[CognitiveOrchestrator] = None,
        session_store_path: Optional[Path] = None,
        memory: Optional[OTTOMemory] = None,
    ):
        """
        Initialize adapter.

        Args:
            orchestrator: Cognitive orchestrator (creates default if None)
            session_store_path: Path to persist sessions (optional)
            memory: OTTOMemory instance (uses singleton if None)
        """
        self.orchestrator = orchestrator or create_orchestrator()
        self.session_store_path = session_store_path

        # Memory backbone integration (Stream A - Concurrent Rollout)
        self._memory = memory or get_memory()

        # Session dict - iterate in sorted order
        self._sessions: Dict[int, TelegramSession] = {}

        # Load persisted sessions if path provided
        if session_store_path and session_store_path.exists():
            self._load_sessions()

    def process_message(self, message: TelegramMessage) -> TelegramResponse:
        """
        Process a Telegram message through the cognitive pipeline.

        Fixed evaluation order:
        1. Get/create session
        2. Check for commands
        3. Route through orchestrator
        4. Build response
        5. Update session state

        Args:
            message: Normalized Telegram message

        Returns:
            Response to send back to Telegram
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
                "platform": "telegram",
                "user_id": message.user_id,
                "session_id": session.session_id,
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

        # Persist sessions if store configured
        if self.session_store_path:
            self._save_sessions()

        # Step 6: Record to memory backbone (Stream A - Concurrent Rollout)
        self._record_to_memory(message, response, result, session)

        logger.info(
            f"Processed message for user {message.user_id}: "
            f"{response.anchor} ({response.processing_time_ms:.1f}ms)"
        )

        return response

    def _record_to_memory(
        self,
        message: TelegramMessage,
        response: TelegramResponse,
        result: NexusResult | KnowledgeResult,
        session: TelegramSession,
    ) -> None:
        """
        Record interaction to memory backbone.

        Determinism:
        - Episode recording is deterministic
        - Trail deposits use sorted keys
        - Outcomes are binary (SUCCESS/FAILURE)

        This enables:
        - Cross-surface visibility (CLI can see Telegram actions)
        - Trail-based trust building
        - Episodic memory for context
        """
        try:
            # Record episode
            episode = Episode(
                type="surface.telegram.message",
                data={
                    "user_id": str(message.user_id),
                    "message_length": len(message.text),
                    "expert": response.expert,
                    "anchor": response.anchor,
                    "processing_time_ms": response.processing_time_ms,
                },
                outcome=Outcome.SUCCESS,
                actor="telegram_adapter",
                service="telegram",
                resource=f"user:{message.user_id}",
            )
            self._memory.record_episode(episode)

            # Deposit trail for this interaction
            # Trail strengthens with each successful interaction
            trail_action = f"telegram.{response.expert or 'direct'}"
            self._memory.deposit_trail(action=trail_action, outcome=Outcome.SUCCESS)

            logger.debug(f"Memory recorded: {episode.type}, trail: {trail_action}")

        except Exception as e:
            # Memory recording should not break the interaction
            logger.debug(f"Memory recording skipped: {e}")

    def _get_or_create_session(self, message: TelegramMessage) -> TelegramSession:
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
        session = TelegramSession(
            user_id=user_id,
            chat_id=message.chat_id,
        )
        self._sessions[user_id] = session

        # Reset orchestrator for new session
        self.orchestrator.reset_session()

        logger.info(f"Created new session for user {user_id}: {session.session_id}")
        return session

    def _handle_command(
        self,
        message: TelegramMessage,
        session: TelegramSession
    ) -> TelegramResponse:
        """
        Handle bot commands.

        Commands:
        - /start: Welcome message + calibration
        - /status: Current cognitive state
        - /reset: Reset session
        - /help: Available commands
        """
        command = message.command

        if command == "start":
            return self._cmd_start(message, session)
        elif command == "status":
            return self._cmd_status(message, session)
        elif command == "reset":
            return self._cmd_reset(message, session)
        elif command == "help":
            return self._cmd_help(message, session)
        elif command == "calibrate":
            return self._cmd_calibrate(message, session)
        else:
            return TelegramResponse(
                text=f"Unknown command: /{command}\nUse /help for available commands.",
                chat_id=message.chat_id,
                reply_to_message_id=message.message_id,
            )

    def _cmd_start(
        self,
        message: TelegramMessage,
        session: TelegramSession
    ) -> TelegramResponse:
        """Handle /start command."""
        text = """*Welcome to OTTO*

I'm your ADHD-native cognitive support system.

*Quick Start:*
- Just chat naturally about what you're working on
- I'll detect your state and adapt my responses
- Use /status to see current cognitive state
- Use /help for all commands

*What's your energy level right now?*
- Reply "high" - ready to dive in
- Reply "medium" - steady but not peak
- Reply "low" - need easy wins

Or just start chatting!"""

        return TelegramResponse(
            text=text,
            chat_id=message.chat_id,
            expert="welcome",
            anchor="[WELCOME]",
        )

    def _cmd_status(
        self,
        message: TelegramMessage,
        session: TelegramSession
    ) -> TelegramResponse:
        """Handle /status command."""
        state = self.orchestrator.get_state()
        last_result = self.orchestrator.get_last_result()

        text = f"""*OTTO Status*

*Session:* `{session.session_id}`
*Messages:* {session.message_count}
*Duration:* {session.duration_seconds/60:.1f} min

*Cognitive State:*
- Burnout: {state.burnout_level.value}
- Energy: {state.energy_level.value}
- Momentum: {state.momentum_phase.value}
- Mode: {state.mode.value}

*Convergence:*
- Tension: {state.epistemic_tension:.3f}
- Attractor: {state.convergence_attractor}
- Stable: {state.stable_exchanges}/3"""

        if last_result and isinstance(last_result, NexusResult):
            text += f"""

*Last Route:*
- Expert: {last_result.routing.expert.value}
- Anchor: `{last_result.to_anchor()}`"""

        return TelegramResponse(
            text=text,
            chat_id=message.chat_id,
            expert="status",
            anchor="[STATUS]",
        )

    def _cmd_reset(
        self,
        message: TelegramMessage,
        session: TelegramSession
    ) -> TelegramResponse:
        """Handle /reset command."""
        # Reset orchestrator
        self.orchestrator.reset_session()

        # Create fresh session
        new_session = TelegramSession(
            user_id=message.user_id,
            chat_id=message.chat_id,
        )
        self._sessions[message.user_id] = new_session

        return TelegramResponse(
            text="*Session Reset*\n\nFresh start. How can I help?",
            chat_id=message.chat_id,
            expert="reset",
            anchor="[RESET]",
        )

    def _cmd_help(
        self,
        message: TelegramMessage,
        session: TelegramSession
    ) -> TelegramResponse:
        """Handle /help command."""
        text = """*OTTO Commands*

*Session:*
- /start - Welcome message
- /status - Current cognitive state
- /reset - Start fresh session
- /calibrate - Calibrate energy/focus
- /approve - View approval status
- /services - List available services

*Services (MCP):*
- /calendar today - Today's events
- /calendar week - This week's events
- /tasks list - List tasks
- /tasks add [title] - Add task
- /email inbox - Check inbox
- /notion pages - List pages

*Cognitive Support:*
Just chat naturally! OTTO detects:
- Frustration (ALL CAPS, negative words)
- Overwhelm (too many options)
- Depletion (short responses, "tired")
- Exploration ("what if", curiosity)

*Experts:*
I route to different experts based on your state:
- Validator: Frustration first aid
- Scaffolder: Break down overwhelm
- Restorer: Easy wins when depleted
- Socratic: Guide exploration
- Direct: Stay out of your way

*Approvals:*
When OTTO needs permission for actions:
- Inline buttons appear [Approve] [Deny]
- Approved actions build trust over time
- Trusted actions auto-approve later"""

        return TelegramResponse(
            text=text,
            chat_id=message.chat_id,
            expert="help",
            anchor="[HELP]",
        )

    def _cmd_calibrate(
        self,
        message: TelegramMessage,
        session: TelegramSession
    ) -> TelegramResponse:
        """Handle /calibrate command."""
        text = """*Quick Calibration*

*Energy right now:*
Reply with: `high`, `medium`, `low`, or `depleted`

*Focus level:*
Reply with: `scattered`, `moderate`, or `locked_in`

Example: `medium locked_in`"""

        return TelegramResponse(
            text=text,
            chat_id=message.chat_id,
            expert="calibrate",
            anchor="[CALIBRATE]",
        )

    def _build_response(
        self,
        result: NexusResult | KnowledgeResult,
        message: TelegramMessage,
        session: TelegramSession
    ) -> TelegramResponse:
        """
        Build Telegram response from NEXUS result.

        Response format is deterministic based on result type.
        """
        if isinstance(result, KnowledgeResult):
            return self._build_knowledge_response(result, message)
        else:
            return self._build_nexus_response(result, message, session)

    def _build_knowledge_response(
        self,
        result: KnowledgeResult,
        message: TelegramMessage
    ) -> TelegramResponse:
        """Build response for knowledge fast path."""
        prim = result.top_prim

        if prim:
            text = f"*{prim.name}*\n\n{prim.summary}"
            if prim.content:
                text += f"\n\n{prim.content[:500]}..."
        else:
            text = "I found something but couldn't parse it. Can you rephrase?"

        return TelegramResponse(
            text=text,
            chat_id=message.chat_id,
            reply_to_message_id=message.message_id,
            expert="knowledge",
            anchor=result.to_anchor(),
        )

    def _build_nexus_response(
        self,
        result: NexusResult,
        message: TelegramMessage,
        session: TelegramSession
    ) -> TelegramResponse:
        """
        Build response from NEXUS pipeline result.

        Response varies by expert:
        - Validator: Empathy-first, validation
        - Scaffolder: Break down, reduce scope
        - Restorer: Easy wins, permission to rest
        - Socratic: Guide discovery
        - Direct: Minimal, stay out of way
        """
        expert = result.routing.expert.value

        # Get expert-specific response template
        response_text = self._get_expert_response(result, message)

        return TelegramResponse(
            text=response_text,
            chat_id=message.chat_id,
            reply_to_message_id=message.message_id,
            expert=expert,
            anchor=result.to_anchor(),
        )

    def _get_expert_response(
        self,
        result: NexusResult,
        message: TelegramMessage
    ) -> str:
        """
        Get expert-appropriate response.

        Each expert has a different communication style.
        """
        expert = result.routing.expert.value

        # Map expert to response style
        if expert == "validator":
            return self._validator_response(result, message)
        elif expert == "scaffolder":
            return self._scaffolder_response(result, message)
        elif expert == "restorer":
            return self._restorer_response(result, message)
        elif expert == "celebrator":
            return self._celebrator_response(result, message)
        elif expert == "socratic":
            return self._socratic_response(result, message)
        elif expert == "refocuser":
            return self._refocuser_response(result, message)
        else:  # direct
            return self._direct_response(result, message)

    def _validator_response(
        self,
        result: NexusResult,
        message: TelegramMessage
    ) -> str:
        """Validator: Empathy first, normalize frustration."""
        return (
            "I hear you. That sounds frustrating.\n\n"
            "Take a breath. This feeling is valid.\n\n"
            "When you're ready: what's the core blocker?"
        )

    def _scaffolder_response(
        self,
        result: NexusResult,
        message: TelegramMessage
    ) -> str:
        """Scaffolder: Break down, reduce scope."""
        return (
            "Let's simplify this.\n\n"
            "What's ONE thing that would make progress?\n\n"
            "We can tackle the rest after."
        )

    def _restorer_response(
        self,
        result: NexusResult,
        message: TelegramMessage
    ) -> str:
        """Restorer: Easy wins, permission to rest."""
        return (
            "You're running low. That's OK.\n\n"
            "Options:\n"
            "- One small win?\n"
            "- Save state and rest?\n"
            "- Talk it out?\n\n"
            "No wrong answer."
        )

    def _celebrator_response(
        self,
        result: NexusResult,
        message: TelegramMessage
    ) -> str:
        """Celebrator: Acknowledge wins."""
        return (
            "Nice work!\n\n"
            "Take a moment to appreciate that.\n\n"
            "What's next when you're ready?"
        )

    def _socratic_response(
        self,
        result: NexusResult,
        message: TelegramMessage
    ) -> str:
        """Socratic: Guide discovery."""
        return (
            "Interesting direction...\n\n"
            "What possibilities do you see?\n\n"
            "I'm curious where this leads."
        )

    def _refocuser_response(
        self,
        result: NexusResult,
        message: TelegramMessage
    ) -> str:
        """Refocuser: Gentle redirect."""
        return (
            "Noted.\n\n"
            "I've parked that thought.\n\n"
            "Back to the current task?"
        )

    def _direct_response(
        self,
        result: NexusResult,
        message: TelegramMessage
    ) -> str:
        """Direct: Minimal, stay out of way."""
        return "Got it. Proceeding."

    def _load_sessions(self) -> None:
        """
        Load sessions from disk.

        Uses encrypted storage if protection is set up, otherwise falls
        back to plaintext with a warning.

        Determinism: Fixed evaluation order, sorted iteration.
        """
        # Try encrypted storage first (preferred)
        try:
            protection = get_protection()
            if protection.is_setup() and protection.is_unlocked():
                data = protection.read_protected_json("sessions/telegram.json")
                for user_id in sorted(data.keys()):
                    session_data = data[user_id]
                    session = TelegramSession.from_dict(session_data)
                    if not session.is_expired:
                        self._sessions[int(user_id)] = session
                logger.info(f"Loaded {len(self._sessions)} encrypted sessions")
                return
        except SubstrateProtectionError:
            pass  # Protection not set up, fall through to plaintext
        except FileNotFoundError:
            return  # No sessions file yet
        except Exception as e:
            logger.debug(f"Encrypted load failed, trying plaintext: {e}")

        # Fall back to plaintext (legacy or protection not set up)
        if not self.session_store_path:
            return

        try:
            with open(self.session_store_path) as f:
                data = json.load(f)

            # Load in sorted order by user_id
            for user_id in sorted(data.keys()):
                session_data = data[user_id]
                session = TelegramSession.from_dict(session_data)

                # Skip expired sessions
                if not session.is_expired:
                    self._sessions[int(user_id)] = session

            logger.info(f"Loaded {len(self._sessions)} sessions")
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
        # Save in sorted order by user_id
        data = {}
        for user_id in sorted(self._sessions.keys()):
            session = self._sessions[user_id]
            if not session.is_expired:
                data[str(user_id)] = session.to_dict()

        # Try encrypted storage first (preferred)
        try:
            protection = get_protection()
            if protection.is_setup() and protection.is_unlocked():
                protection.write_protected_json("sessions/telegram.json", data)
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
            # Atomic write
            temp_path = self.session_store_path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            temp_path.replace(self.session_store_path)
            logger.debug(
                "Sessions saved in PLAINTEXT. "
                "Run 'otto protection setup' to enable encryption."
            )

        except Exception as e:
            logger.warning(f"Failed to save sessions: {e}")

    def get_session(self, user_id: int) -> Optional[TelegramSession]:
        """Get session by user ID."""
        return self._sessions.get(user_id)

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.

        Iterate in sorted order.

        Returns:
            Number of sessions removed
        """
        expired = []

        for user_id in sorted(self._sessions.keys()):
            if self._sessions[user_id].is_expired:
                expired.append(user_id)

        for user_id in expired:
            del self._sessions[user_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)


__all__ = [
    "TelegramAdapter",
    "TelegramSession",
    "TelegramMessage",
    "TelegramResponse",
]
