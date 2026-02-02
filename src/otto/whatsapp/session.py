"""
WhatsApp session management.

Manages conversation state across messages.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from .schemas import ConversationState


logger = logging.getLogger(__name__)


@dataclass
class SessionConfig:
    """Session management configuration."""

    session_timeout_minutes: int = 30
    """Minutes of inactivity before session expires."""

    max_sessions: int = 10000
    """Maximum concurrent sessions."""

    persist_path: Optional[Path] = None
    """Path for session persistence."""

    cleanup_interval_minutes: int = 5
    """How often to run cleanup."""


class SessionManager:
    """
    Manage WhatsApp conversation sessions.

    Provides:
    - Session creation and retrieval
    - Session expiration
    - Context persistence
    """

    def __init__(self, config: Optional[SessionConfig] = None):
        """
        Initialize session manager.

        Args:
            config: Session configuration
        """
        self.config = config or SessionConfig()
        self._sessions: dict[str, ConversationState] = {}
        self._last_cleanup = datetime.utcnow()

        # Load persisted sessions
        if self.config.persist_path:
            self._load_sessions()

    def get_or_create(self, phone_number: str) -> ConversationState:
        """
        Get existing session or create new one.

        Args:
            phone_number: User's phone number

        Returns:
            ConversationState for the user
        """
        self._maybe_cleanup()

        if phone_number in self._sessions:
            session = self._sessions[phone_number]
            # Check if session is still valid
            if self._is_expired(session):
                logger.info(f"Session expired for {phone_number}, creating new")
                session = self._create_session(phone_number)
            return session

        return self._create_session(phone_number)

    def get(self, phone_number: str) -> Optional[ConversationState]:
        """
        Get existing session if valid.

        Args:
            phone_number: User's phone number

        Returns:
            ConversationState if exists and valid, None otherwise
        """
        session = self._sessions.get(phone_number)
        if session and not self._is_expired(session):
            return session
        return None

    def update(self, session: ConversationState):
        """
        Update a session.

        Args:
            session: Session to update
        """
        session.updated_at = datetime.utcnow()
        self._sessions[session.phone_number] = session

        if self.config.persist_path:
            self._persist_session(session)

    def delete(self, phone_number: str):
        """
        Delete a session.

        Args:
            phone_number: Phone number of session to delete
        """
        if phone_number in self._sessions:
            del self._sessions[phone_number]
            if self.config.persist_path:
                self._delete_persisted_session(phone_number)

    def set_context(self, phone_number: str, key: str, value: any):
        """
        Set a context value for a session.

        Args:
            phone_number: User's phone number
            key: Context key
            value: Context value
        """
        session = self.get_or_create(phone_number)
        session.context[key] = value
        self.update(session)

    def get_context(self, phone_number: str, key: str, default: any = None) -> any:
        """
        Get a context value from a session.

        Args:
            phone_number: User's phone number
            key: Context key
            default: Default value if not found

        Returns:
            Context value or default
        """
        session = self.get(phone_number)
        if session:
            return session.context.get(key, default)
        return default

    def _create_session(self, phone_number: str) -> ConversationState:
        """Create a new session."""
        session = ConversationState(
            phone_number=phone_number,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._sessions[phone_number] = session

        # Enforce max sessions limit
        if len(self._sessions) > self.config.max_sessions:
            self._evict_oldest()

        if self.config.persist_path:
            self._persist_session(session)

        logger.info(f"Created new session for {phone_number}")
        return session

    def _is_expired(self, session: ConversationState) -> bool:
        """Check if a session is expired."""
        timeout = timedelta(minutes=self.config.session_timeout_minutes)
        return datetime.utcnow() - session.updated_at > timeout

    def _maybe_cleanup(self):
        """Run cleanup if interval has passed."""
        cleanup_interval = timedelta(minutes=self.config.cleanup_interval_minutes)
        if datetime.utcnow() - self._last_cleanup > cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = datetime.utcnow()

    def _cleanup_expired(self):
        """Remove expired sessions."""
        expired = [
            phone for phone, session in self._sessions.items()
            if self._is_expired(session)
        ]
        for phone in expired:
            self.delete(phone)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def _evict_oldest(self):
        """Evict oldest sessions when at capacity."""
        # Sort by updated_at and remove oldest
        sorted_sessions = sorted(
            self._sessions.items(),
            key=lambda x: x[1].updated_at
        )
        to_remove = len(self._sessions) - self.config.max_sessions + 1
        for phone, _ in sorted_sessions[:to_remove]:
            self.delete(phone)

        logger.info(f"Evicted {to_remove} oldest sessions")

    def _persist_session(self, session: ConversationState):
        """Persist session to disk."""
        if not self.config.persist_path:
            return

        try:
            self.config.persist_path.mkdir(parents=True, exist_ok=True)
            path = self._get_session_path(session.phone_number)

            data = {
                "phone_number": session.phone_number,
                "last_message_id": session.last_message_id,
                "last_message_time": session.last_message_time.isoformat() if session.last_message_time else None,
                "message_count": session.message_count,
                "voice_message_count": session.voice_message_count,
                "context": session.context,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            }

            with open(path, "w") as f:
                json.dump(data, f)

        except Exception as e:
            logger.error(f"Failed to persist session: {e}")

    def _load_sessions(self):
        """Load sessions from disk."""
        if not self.config.persist_path or not self.config.persist_path.exists():
            return

        try:
            for path in self.config.persist_path.glob("*.json"):
                try:
                    with open(path) as f:
                        data = json.load(f)

                    session = ConversationState(
                        phone_number=data["phone_number"],
                        last_message_id=data.get("last_message_id"),
                        last_message_time=datetime.fromisoformat(data["last_message_time"]) if data.get("last_message_time") else None,
                        message_count=data.get("message_count", 0),
                        voice_message_count=data.get("voice_message_count", 0),
                        context=data.get("context", {}),
                        created_at=datetime.fromisoformat(data["created_at"]),
                        updated_at=datetime.fromisoformat(data["updated_at"]),
                    )

                    # Only load if not expired
                    if not self._is_expired(session):
                        self._sessions[session.phone_number] = session

                except Exception as e:
                    logger.warning(f"Failed to load session from {path}: {e}")

            logger.info(f"Loaded {len(self._sessions)} sessions from disk")

        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")

    def _delete_persisted_session(self, phone_number: str):
        """Delete persisted session file."""
        if not self.config.persist_path:
            return

        path = self._get_session_path(phone_number)
        if path.exists():
            path.unlink()

    def _get_session_path(self, phone_number: str) -> Path:
        """Get path for session file."""
        # Sanitize phone number for filename
        safe_phone = "".join(c if c.isdigit() else "_" for c in phone_number)
        return self.config.persist_path / f"session_{safe_phone}.json"

    def get_stats(self) -> dict:
        """Get session statistics."""
        now = datetime.utcnow()
        active_count = sum(
            1 for s in self._sessions.values()
            if not self._is_expired(s)
        )

        total_messages = sum(s.message_count for s in self._sessions.values())
        total_voice = sum(s.voice_message_count for s in self._sessions.values())

        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active_count,
            "total_messages": total_messages,
            "total_voice_messages": total_voice,
            "timeout_minutes": self.config.session_timeout_minutes,
        }


# Global session manager
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager (lazy init)."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def configure_sessions(config: SessionConfig):
    """Configure the global session manager."""
    global _session_manager
    _session_manager = SessionManager(config)
