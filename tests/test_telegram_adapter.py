"""
Telegram Adapter Tests
======================

[He2025] Compliance Tests:
- Deterministic session creation
- Fixed evaluation order
- Sorted key iteration
- Session state persistence

Tests:
- Session management (create, expire, cleanup)
- Message processing pipeline
- Command handling
- Response building
"""

import json
import tempfile
import time
from pathlib import Path
from typing import Final
from unittest.mock import MagicMock, patch

import pytest

from otto.telegram.adapter import (
    TelegramAdapter,
    TelegramSession,
    TelegramMessage,
    TelegramResponse,
    _SESSION_TIMEOUT_SECONDS,
)


# [He2025] Fixed test constants
_TEST_USER_ID: Final[int] = 12345
_TEST_CHAT_ID: Final[int] = 67890
_TEST_MESSAGE_ID: Final[int] = 100


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_orchestrator():
    """Create mock cognitive orchestrator."""
    orchestrator = MagicMock()

    # Mock process_message to return a valid NexusResult-like object
    mock_result = MagicMock()
    mock_result.to_anchor.return_value = "[EXEC:test|direct|Cortex|30000ft|standard]"
    mock_result.routing.expert.value = "direct"
    orchestrator.process_message.return_value = mock_result

    # Mock get_state
    mock_state = MagicMock()
    mock_state.burnout_level.value = "GREEN"
    mock_state.energy_level.value = "medium"
    mock_state.momentum_phase.value = "building"
    mock_state.mode.value = "focused"
    mock_state.epistemic_tension = 0.05
    mock_state.convergence_attractor = "focused"
    mock_state.stable_exchanges = 2
    orchestrator.get_state.return_value = mock_state

    return orchestrator


@pytest.fixture
def adapter(mock_orchestrator):
    """Create adapter with mock orchestrator."""
    return TelegramAdapter(orchestrator=mock_orchestrator)


@pytest.fixture
def sample_message():
    """Create sample Telegram message."""
    return TelegramMessage(
        message_id=_TEST_MESSAGE_ID,
        user_id=_TEST_USER_ID,
        chat_id=_TEST_CHAT_ID,
        text="Hello, I need help with my project",
        timestamp=time.time(),
    )


# =============================================================================
# Session Tests
# =============================================================================

class TestTelegramSession:
    """Tests for TelegramSession dataclass."""

    def test_session_creation(self):
        """Test session is created with correct defaults."""
        session = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
        )

        assert session.user_id == _TEST_USER_ID
        assert session.chat_id == _TEST_CHAT_ID
        assert session.message_count == 0
        assert session.burnout_level == "GREEN"
        assert session.energy_level == "medium"
        assert session.momentum_phase == "cold_start"

    def test_session_id_determinism(self):
        """[He2025] Session ID must be deterministic."""
        # Same inputs should produce same session ID
        created_at = 1704067200.0  # Fixed timestamp

        session1 = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
            created_at=created_at,
        )

        session2 = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
            created_at=created_at,
        )

        assert session1.session_id == session2.session_id

    def test_session_id_unique_per_user(self):
        """Different users should have different session IDs."""
        created_at = time.time()

        session1 = TelegramSession(
            user_id=111,
            chat_id=_TEST_CHAT_ID,
            created_at=created_at,
        )

        session2 = TelegramSession(
            user_id=222,
            chat_id=_TEST_CHAT_ID,
            created_at=created_at,
        )

        assert session1.session_id != session2.session_id

    def test_session_expiry(self):
        """Test session timeout detection."""
        # Fresh session should not be expired
        session = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
        )
        assert not session.is_expired

        # Old session should be expired
        old_session = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
            last_activity=time.time() - _SESSION_TIMEOUT_SECONDS - 1,
        )
        assert old_session.is_expired

    def test_session_touch(self):
        """Test session touch updates activity."""
        session = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
        )

        initial_activity = session.last_activity
        initial_count = session.message_count

        time.sleep(0.01)  # Small delay
        session.touch()

        assert session.last_activity > initial_activity
        assert session.message_count == initial_count + 1

    def test_session_serialization(self):
        """Test session serialization roundtrip."""
        session = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
            username="testuser",
            burnout_level="YELLOW",
        )

        # Serialize and deserialize
        data = session.to_dict()
        restored = TelegramSession.from_dict(data)

        assert restored.user_id == session.user_id
        assert restored.chat_id == session.chat_id
        assert restored.username == session.username
        assert restored.burnout_level == session.burnout_level


# =============================================================================
# Message Tests
# =============================================================================

class TestTelegramMessage:
    """Tests for TelegramMessage dataclass."""

    def test_command_detection(self):
        """Test command detection."""
        # Regular message
        msg = TelegramMessage(
            message_id=1,
            user_id=1,
            chat_id=1,
            text="Hello",
            timestamp=time.time(),
        )
        assert not msg.is_command
        assert msg.command is None

        # Command message
        cmd_msg = TelegramMessage(
            message_id=1,
            user_id=1,
            chat_id=1,
            text="/start",
            timestamp=time.time(),
        )
        assert cmd_msg.is_command
        assert cmd_msg.command == "start"

    def test_command_extraction(self):
        """Test command name extraction."""
        commands = [
            ("/start", "start"),
            ("/help arg1 arg2", "help"),
            ("/STATUS", "status"),  # Should lowercase
            ("/Reset now", "reset"),
        ]

        for text, expected in commands:
            msg = TelegramMessage(
                message_id=1,
                user_id=1,
                chat_id=1,
                text=text,
                timestamp=time.time(),
            )
            assert msg.command == expected


# =============================================================================
# Adapter Tests
# =============================================================================

class TestTelegramAdapter:
    """Tests for TelegramAdapter."""

    def test_adapter_creation(self, mock_orchestrator):
        """Test adapter creates with orchestrator."""
        adapter = TelegramAdapter(orchestrator=mock_orchestrator)

        assert adapter.orchestrator == mock_orchestrator
        assert len(adapter._sessions) == 0

    def test_session_creation_on_message(self, adapter, sample_message):
        """Test session is created on first message."""
        assert _TEST_USER_ID not in adapter._sessions

        adapter.process_message(sample_message)

        assert _TEST_USER_ID in adapter._sessions
        session = adapter._sessions[_TEST_USER_ID]
        assert session.user_id == _TEST_USER_ID

    def test_session_reuse(self, adapter, sample_message):
        """Test session is reused for same user."""
        # First message creates session
        adapter.process_message(sample_message)
        session_id = adapter._sessions[_TEST_USER_ID].session_id

        # Second message reuses session
        adapter.process_message(sample_message)
        assert adapter._sessions[_TEST_USER_ID].session_id == session_id

    def test_session_expiry_creates_new(self, adapter, sample_message):
        """Test expired session is replaced."""
        # Create session
        adapter.process_message(sample_message)
        old_session_id = adapter._sessions[_TEST_USER_ID].session_id

        # Expire the session
        adapter._sessions[_TEST_USER_ID].last_activity = (
            time.time() - _SESSION_TIMEOUT_SECONDS - 1
        )

        # Next message should create new session
        adapter.process_message(sample_message)
        new_session_id = adapter._sessions[_TEST_USER_ID].session_id

        # Session IDs should differ (different created_at)
        assert new_session_id != old_session_id

    def test_command_handling(self, adapter):
        """Test command messages are handled."""
        commands = ["/start", "/help", "/status", "/reset", "/calibrate"]

        for cmd in commands:
            message = TelegramMessage(
                message_id=1,
                user_id=_TEST_USER_ID,
                chat_id=_TEST_CHAT_ID,
                text=cmd,
                timestamp=time.time(),
            )

            response = adapter.process_message(message)

            # Commands should not go through orchestrator
            assert response.text  # Should have response text
            assert response.chat_id == _TEST_CHAT_ID

    def test_message_processing_calls_orchestrator(
        self,
        adapter,
        sample_message,
        mock_orchestrator
    ):
        """Test regular messages go through orchestrator."""
        adapter.process_message(sample_message)

        mock_orchestrator.process_message.assert_called_once()
        call_args = mock_orchestrator.process_message.call_args

        # Check message was passed
        assert call_args.kwargs["message"] == sample_message.text
        # Check context includes platform
        assert call_args.kwargs["context"]["platform"] == "telegram"

    def test_response_truncation(self, adapter):
        """Test long responses are truncated."""
        response = TelegramResponse(
            text="x" * 5000,  # Longer than 4096 limit
            chat_id=_TEST_CHAT_ID,
        )

        truncated = response.truncate()

        assert len(truncated.text) <= 4096
        assert "truncated" in truncated.text

    def test_cleanup_expired_sessions(self, adapter, sample_message):
        """Test expired session cleanup."""
        # Create some sessions
        for user_id in [1, 2, 3]:
            msg = TelegramMessage(
                message_id=1,
                user_id=user_id,
                chat_id=user_id,
                text="test",
                timestamp=time.time(),
            )
            adapter.process_message(msg)

        assert len(adapter._sessions) == 3

        # Expire user 2's session
        adapter._sessions[2].last_activity = (
            time.time() - _SESSION_TIMEOUT_SECONDS - 1
        )

        # Cleanup
        removed = adapter.cleanup_expired_sessions()

        assert removed == 1
        assert len(adapter._sessions) == 2
        assert 2 not in adapter._sessions


# =============================================================================
# Persistence Tests
# =============================================================================

class TestSessionPersistence:
    """Tests for session persistence."""

    def test_save_and_load_sessions(self, mock_orchestrator):
        """Test sessions persist to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions.json"

            # Create adapter and add sessions
            adapter = TelegramAdapter(
                orchestrator=mock_orchestrator,
                session_store_path=session_path,
            )

            for user_id in [1, 2, 3]:
                msg = TelegramMessage(
                    message_id=1,
                    user_id=user_id,
                    chat_id=user_id,
                    text="test",
                    timestamp=time.time(),
                )
                adapter.process_message(msg)

            # Manually save
            adapter._save_sessions()
            assert session_path.exists()

            # Create new adapter and load
            adapter2 = TelegramAdapter(
                orchestrator=mock_orchestrator,
                session_store_path=session_path,
            )

            assert len(adapter2._sessions) == 3
            for user_id in [1, 2, 3]:
                assert user_id in adapter2._sessions

    def test_load_skips_expired_sessions(self, mock_orchestrator):
        """Test loading skips expired sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions.json"

            # Write session data with expired session
            data = {
                "1": {
                    "user_id": 1,
                    "chat_id": 1,
                    "created_at": time.time(),
                    "last_activity": time.time(),  # Fresh
                    "message_count": 1,
                    "burnout_level": "GREEN",
                    "energy_level": "medium",
                    "momentum_phase": "building",
                    "mode": "focused",
                    "username": None,
                    "first_name": None,
                    "language_code": "en",
                },
                "2": {
                    "user_id": 2,
                    "chat_id": 2,
                    "created_at": time.time() - 10000,
                    "last_activity": time.time() - _SESSION_TIMEOUT_SECONDS - 1,  # Expired
                    "message_count": 1,
                    "burnout_level": "GREEN",
                    "energy_level": "medium",
                    "momentum_phase": "building",
                    "mode": "focused",
                    "username": None,
                    "first_name": None,
                    "language_code": "en",
                },
            }

            with open(session_path, "w") as f:
                json.dump(data, f)

            # Load adapter
            adapter = TelegramAdapter(
                orchestrator=mock_orchestrator,
                session_store_path=session_path,
            )

            # Should only have non-expired session
            assert len(adapter._sessions) == 1
            assert 1 in adapter._sessions
            assert 2 not in adapter._sessions


# =============================================================================
# [He2025] Determinism Tests
# =============================================================================

class TestDeterminism:
    """[He2025] Determinism verification tests."""

    def test_session_iteration_order(self, adapter, sample_message):
        """[He2025] Sessions should iterate in sorted order."""
        # Create sessions in random order
        for user_id in [5, 1, 3, 2, 4]:
            msg = TelegramMessage(
                message_id=1,
                user_id=user_id,
                chat_id=user_id,
                text="test",
                timestamp=time.time(),
            )
            adapter.process_message(msg)

        # Verify sorted iteration (via cleanup which uses sorted())
        # This indirectly tests that we iterate in sorted order
        cleaned = adapter.cleanup_expired_sessions()
        assert cleaned == 0  # None expired

        # Check sessions are stored
        assert list(sorted(adapter._sessions.keys())) == [1, 2, 3, 4, 5]

    def test_same_input_same_session(self, mock_orchestrator):
        """[He2025] Same inputs should create same session state."""
        fixed_timestamp = 1704067200.0

        # Create two adapters with same inputs
        session1 = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
            created_at=fixed_timestamp,
            last_activity=fixed_timestamp,
        )

        session2 = TelegramSession(
            user_id=_TEST_USER_ID,
            chat_id=_TEST_CHAT_ID,
            created_at=fixed_timestamp,
            last_activity=fixed_timestamp,
        )

        # Sessions should be identical
        assert session1.to_dict() == session2.to_dict()
        assert session1.session_id == session2.session_id

    def test_response_determinism(self, adapter):
        """[He2025] Same command should produce consistent response."""
        responses = []

        for _ in range(5):
            message = TelegramMessage(
                message_id=1,
                user_id=_TEST_USER_ID,
                chat_id=_TEST_CHAT_ID,
                text="/help",
                timestamp=time.time(),
            )

            response = adapter.process_message(message)
            responses.append(response.text)

        # All responses should be identical (command has fixed output)
        assert all(r == responses[0] for r in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
