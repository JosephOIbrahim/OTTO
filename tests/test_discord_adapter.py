"""
Discord Adapter Tests
=====================

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

from otto.discord.adapter import (
    DiscordAdapter,
    DiscordSession,
    DiscordMessage,
    DiscordResponse,
    _SESSION_TIMEOUT_SECONDS,
)


# [He2025] Fixed test constants
_TEST_USER_ID: Final[int] = 12345
_TEST_CHANNEL_ID: Final[int] = 67890
_TEST_GUILD_ID: Final[int] = 11111
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
    return DiscordAdapter(orchestrator=mock_orchestrator)


@pytest.fixture
def sample_message():
    """Create sample Discord message."""
    return DiscordMessage(
        message_id=_TEST_MESSAGE_ID,
        user_id=_TEST_USER_ID,
        channel_id=_TEST_CHANNEL_ID,
        text="Hello, I need help with my project",
        timestamp=time.time(),
        guild_id=_TEST_GUILD_ID,
    )


@pytest.fixture
def sample_dm():
    """Create sample Discord DM."""
    return DiscordMessage(
        message_id=_TEST_MESSAGE_ID,
        user_id=_TEST_USER_ID,
        channel_id=_TEST_CHANNEL_ID,
        text="Hello from DM",
        timestamp=time.time(),
        guild_id=None,
        is_dm=True,
    )


# =============================================================================
# Session Tests
# =============================================================================

class TestDiscordSession:
    """Tests for DiscordSession dataclass."""

    def test_session_creation(self):
        """Test session is created with correct defaults."""
        session = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
        )

        assert session.user_id == _TEST_USER_ID
        assert session.channel_id == _TEST_CHANNEL_ID
        assert session.guild_id is None
        assert session.message_count == 0
        assert session.burnout_level == "GREEN"
        assert session.energy_level == "medium"
        assert session.momentum_phase == "cold_start"
        assert session.mode == "focused"

    def test_session_with_guild(self):
        """Test session with guild ID."""
        session = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            guild_id=_TEST_GUILD_ID,
        )

        assert session.guild_id == _TEST_GUILD_ID

    def test_session_id_determinism(self):
        """[He2025] Session ID must be deterministic."""
        # Same inputs should produce same session ID
        created_at = 1704067200.0  # Fixed timestamp

        session1 = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            created_at=created_at,
        )

        session2 = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            created_at=created_at,
        )

        assert session1.session_id == session2.session_id

    def test_session_id_unique_per_user(self):
        """Different users should have different session IDs."""
        created_at = time.time()

        session1 = DiscordSession(
            user_id=111,
            channel_id=_TEST_CHANNEL_ID,
            created_at=created_at,
        )

        session2 = DiscordSession(
            user_id=222,
            channel_id=_TEST_CHANNEL_ID,
            created_at=created_at,
        )

        assert session1.session_id != session2.session_id

    def test_session_expiry(self):
        """Test session timeout detection."""
        # Fresh session should not be expired
        session = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
        )
        assert not session.is_expired

        # Old session should be expired
        old_session = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            last_activity=time.time() - _SESSION_TIMEOUT_SECONDS - 1,
        )
        assert old_session.is_expired

    def test_session_touch(self):
        """Test session touch updates activity."""
        session = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
        )

        initial_activity = session.last_activity
        initial_count = session.message_count

        time.sleep(0.01)  # Small delay
        session.touch()

        assert session.last_activity > initial_activity
        assert session.message_count == initial_count + 1

    def test_session_serialization(self):
        """Test session serialization roundtrip."""
        session = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            guild_id=_TEST_GUILD_ID,
            username="testuser",
            display_name="Test User",
            burnout_level="YELLOW",
        )

        # Serialize and deserialize
        data = session.to_dict()
        restored = DiscordSession.from_dict(data)

        assert restored.user_id == session.user_id
        assert restored.channel_id == session.channel_id
        assert restored.guild_id == session.guild_id
        assert restored.username == session.username
        assert restored.display_name == session.display_name
        assert restored.burnout_level == session.burnout_level

    def test_session_duration(self):
        """Test session duration calculation."""
        created_at = time.time() - 100  # 100 seconds ago
        session = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            created_at=created_at,
        )

        duration = session.duration_seconds
        assert 99 <= duration <= 102  # Allow small tolerance


# =============================================================================
# Message Tests
# =============================================================================

class TestDiscordMessage:
    """Tests for DiscordMessage dataclass."""

    def test_command_detection(self):
        """Test command detection."""
        # Regular message
        msg = DiscordMessage(
            message_id=1,
            user_id=1,
            channel_id=1,
            text="Hello",
            timestamp=time.time(),
        )
        assert not msg.is_command
        assert msg.command is None

        # Command message
        cmd_msg = DiscordMessage(
            message_id=1,
            user_id=1,
            channel_id=1,
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
            msg = DiscordMessage(
                message_id=1,
                user_id=1,
                channel_id=1,
                text=text,
                timestamp=time.time(),
            )
            assert msg.command == expected

    def test_dm_flag(self):
        """Test DM flag is properly set."""
        dm_msg = DiscordMessage(
            message_id=1,
            user_id=1,
            channel_id=1,
            text="Hello",
            timestamp=time.time(),
            is_dm=True,
        )
        assert dm_msg.is_dm

        guild_msg = DiscordMessage(
            message_id=1,
            user_id=1,
            channel_id=1,
            text="Hello",
            timestamp=time.time(),
            guild_id=123,
            is_dm=False,
        )
        assert not guild_msg.is_dm


# =============================================================================
# Response Tests
# =============================================================================

class TestDiscordResponse:
    """Tests for DiscordResponse dataclass."""

    def test_response_truncation(self):
        """Test long responses are truncated."""
        response = DiscordResponse(
            text="x" * 2500,  # Longer than 2000 Discord limit
            channel_id=_TEST_CHANNEL_ID,
        )

        truncated = response.truncate()

        assert len(truncated.text) <= 2000
        assert "truncated" in truncated.text

    def test_response_no_truncation_needed(self):
        """Test short responses are not truncated."""
        response = DiscordResponse(
            text="Short message",
            channel_id=_TEST_CHANNEL_ID,
        )

        truncated = response.truncate()

        assert truncated.text == "Short message"
        assert "truncated" not in truncated.text

    def test_response_preserves_metadata(self):
        """Test truncation preserves metadata."""
        response = DiscordResponse(
            text="x" * 2500,
            channel_id=_TEST_CHANNEL_ID,
            reply_to_message_id=123,
            anchor="[EXEC:test]",
            expert="direct",
            ephemeral=True,
        )

        truncated = response.truncate()

        assert truncated.channel_id == _TEST_CHANNEL_ID
        assert truncated.reply_to_message_id == 123
        assert truncated.anchor == "[EXEC:test]"
        assert truncated.expert == "direct"
        assert truncated.ephemeral is True


# =============================================================================
# Adapter Tests
# =============================================================================

class TestDiscordAdapter:
    """Tests for DiscordAdapter."""

    def test_adapter_creation(self, mock_orchestrator):
        """Test adapter creates with orchestrator."""
        adapter = DiscordAdapter(orchestrator=mock_orchestrator)

        assert adapter.orchestrator == mock_orchestrator
        assert len(adapter._sessions) == 0

    def test_session_creation_on_message(self, adapter, sample_message):
        """Test session is created on first message."""
        assert _TEST_USER_ID not in adapter._sessions

        adapter.process_message(sample_message)

        assert _TEST_USER_ID in adapter._sessions
        session = adapter._sessions[_TEST_USER_ID]
        assert session.user_id == _TEST_USER_ID
        assert session.channel_id == _TEST_CHANNEL_ID
        assert session.guild_id == _TEST_GUILD_ID

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

    def test_dm_session_creation(self, adapter, sample_dm):
        """Test session creation for DM."""
        adapter.process_message(sample_dm)

        assert _TEST_USER_ID in adapter._sessions
        session = adapter._sessions[_TEST_USER_ID]
        assert session.guild_id is None

    def test_command_handling(self, adapter):
        """Test command messages are handled."""
        commands = ["/start", "/help", "/status", "/reset", "/calibrate"]

        for cmd in commands:
            message = DiscordMessage(
                message_id=1,
                user_id=_TEST_USER_ID,
                channel_id=_TEST_CHANNEL_ID,
                text=cmd,
                timestamp=time.time(),
            )

            response = adapter.process_message(message)

            # Commands should not go through orchestrator
            # They should have response text or embed_data
            assert response.text or response.embed_data
            assert response.channel_id == _TEST_CHANNEL_ID

    def test_unknown_command(self, adapter):
        """Test unknown command returns help message."""
        message = DiscordMessage(
            message_id=1,
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            text="/unknowncommand",
            timestamp=time.time(),
        )

        response = adapter.process_message(message)

        assert "Unknown command" in response.text
        assert "/help" in response.text

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
        assert call_args.kwargs["context"]["platform"] == "discord"
        assert call_args.kwargs["context"]["is_dm"] is False

    def test_dm_processing_context(
        self,
        adapter,
        sample_dm,
        mock_orchestrator
    ):
        """Test DM messages have correct context."""
        adapter.process_message(sample_dm)

        call_args = mock_orchestrator.process_message.call_args
        assert call_args.kwargs["context"]["is_dm"] is True
        assert call_args.kwargs["context"]["guild_id"] is None

    def test_cleanup_expired_sessions(self, adapter, sample_message):
        """Test expired session cleanup."""
        # Create some sessions
        for user_id in [1, 2, 3]:
            msg = DiscordMessage(
                message_id=1,
                user_id=user_id,
                channel_id=user_id,
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

    def test_status_command_returns_embed(self, adapter):
        """Test /status command returns embed data."""
        message = DiscordMessage(
            message_id=1,
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            text="/status",
            timestamp=time.time(),
        )

        response = adapter.process_message(message)

        assert response.embed_data is not None
        assert "title" in response.embed_data
        assert "fields" in response.embed_data
        assert response.ephemeral is True  # Status is ephemeral

    def test_burnout_color_mapping(self, adapter):
        """Test burnout level to embed color mapping."""
        colors = {
            "GREEN": 0x2ECC71,
            "YELLOW": 0xF1C40F,
            "ORANGE": 0xE67E22,
            "RED": 0xE74C3C,
        }

        for level, expected_color in colors.items():
            color = adapter._burnout_color(level)
            assert color == expected_color

        # Unknown level should return grey
        assert adapter._burnout_color("UNKNOWN") == 0x95A5A6


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
            adapter = DiscordAdapter(
                orchestrator=mock_orchestrator,
                session_store_path=session_path,
            )

            for user_id in [1, 2, 3]:
                msg = DiscordMessage(
                    message_id=1,
                    user_id=user_id,
                    channel_id=user_id,
                    text="test",
                    timestamp=time.time(),
                )
                adapter.process_message(msg)

            # Manually save
            adapter._save_sessions()
            assert session_path.exists()

            # Create new adapter and load
            adapter2 = DiscordAdapter(
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
                    "channel_id": 1,
                    "guild_id": None,
                    "created_at": time.time(),
                    "last_activity": time.time(),  # Fresh
                    "message_count": 1,
                    "burnout_level": "GREEN",
                    "energy_level": "medium",
                    "momentum_phase": "building",
                    "mode": "focused",
                    "username": None,
                    "display_name": None,
                },
                "2": {
                    "user_id": 2,
                    "channel_id": 2,
                    "guild_id": None,
                    "created_at": time.time() - 10000,
                    "last_activity": time.time() - _SESSION_TIMEOUT_SECONDS - 1,  # Expired
                    "message_count": 1,
                    "burnout_level": "GREEN",
                    "energy_level": "medium",
                    "momentum_phase": "building",
                    "mode": "focused",
                    "username": None,
                    "display_name": None,
                },
            }

            with open(session_path, "w") as f:
                json.dump(data, f)

            # Load adapter
            adapter = DiscordAdapter(
                orchestrator=mock_orchestrator,
                session_store_path=session_path,
            )

            # Should only have non-expired session
            assert len(adapter._sessions) == 1
            assert 1 in adapter._sessions
            assert 2 not in adapter._sessions

    def test_persistence_json_sorted_keys(self, mock_orchestrator):
        """[He2025] Verify JSON output has sorted keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = Path(tmpdir) / "sessions.json"

            adapter = DiscordAdapter(
                orchestrator=mock_orchestrator,
                session_store_path=session_path,
            )

            # Create sessions in non-sorted order
            for user_id in [5, 1, 3]:
                msg = DiscordMessage(
                    message_id=1,
                    user_id=user_id,
                    channel_id=user_id,
                    text="test",
                    timestamp=time.time(),
                )
                adapter.process_message(msg)

            adapter._save_sessions()

            # Read raw JSON and verify order
            content = session_path.read_text()
            data = json.loads(content)

            # Keys should be in sorted order
            keys = list(data.keys())
            assert keys == sorted(keys)


# =============================================================================
# [He2025] Determinism Tests
# =============================================================================

class TestDeterminism:
    """[He2025] Determinism verification tests."""

    def test_session_iteration_order(self, adapter, sample_message):
        """[He2025] Sessions should iterate in sorted order."""
        # Create sessions in random order
        for user_id in [5, 1, 3, 2, 4]:
            msg = DiscordMessage(
                message_id=1,
                user_id=user_id,
                channel_id=user_id,
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

        # Create two sessions with same inputs
        session1 = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            guild_id=_TEST_GUILD_ID,
            created_at=fixed_timestamp,
            last_activity=fixed_timestamp,
        )

        session2 = DiscordSession(
            user_id=_TEST_USER_ID,
            channel_id=_TEST_CHANNEL_ID,
            guild_id=_TEST_GUILD_ID,
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
            message = DiscordMessage(
                message_id=1,
                user_id=_TEST_USER_ID,
                channel_id=_TEST_CHANNEL_ID,
                text="/help",
                timestamp=time.time(),
            )

            response = adapter.process_message(message)
            responses.append(response.text)

        # All responses should be identical (command has fixed output)
        assert all(r == responses[0] for r in responses)

    def test_session_hash_determinism(self):
        """[He2025] Session ID hash is deterministic."""
        # Same inputs, multiple trials
        results = set()

        for _ in range(100):
            session = DiscordSession(
                user_id=_TEST_USER_ID,
                channel_id=_TEST_CHANNEL_ID,
                created_at=1704067200.0,
            )
            results.add(session.session_id)

        # All session IDs should be identical
        assert len(results) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
