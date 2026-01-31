"""
Tests for OTTO Messaging Module
===============================

Tests for Matrix bot and secure channel functionality.
"""

import pytest
import asyncio
import time
from pathlib import Path
from datetime import datetime, timezone

from otto.messaging import (
    # Matrix Bot
    OTTOMatrixBot,
    create_bot,
    BotConfig,
    MatrixMessage,
    MessageType,
    MockMatrixClient,
    # Secure Channel
    SecureChannel,
    ThresholdSecureChannel,
    create_secure_channel,
    SecurePayload,
    KeyExchangeMessage,
    ChannelState,
    # Commands
    OTTOCommands,
    register_otto_commands,
    # Exceptions
    SecureChannelError,
    KeyExchangeError,
    ReplayError,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def bot_config(tmp_path):
    """Create a test bot configuration."""
    return BotConfig(
        homeserver="https://matrix.test.org",
        user_id="@otto:test.org",
        device_id="TEST_DEVICE",
        state_dir=tmp_path / "matrix_state",
        allowed_users=["@user:test.org"],
        enable_e2e=True,
        enable_pq_layer=True,
    )


@pytest.fixture
def mock_bot(tmp_path):
    """Create a mock Matrix bot."""
    return create_bot(
        homeserver="https://matrix.test.org",
        user_id="@otto:test.org",
        device_id="TEST_DEVICE",
        state_dir=tmp_path / "matrix_state",
        use_mock=True,
    )


@pytest.fixture
def secure_channel():
    """Create a secure channel."""
    return SecureChannel(device_id="test_device_1")


@pytest.fixture
def peer_channel():
    """Create a peer secure channel."""
    return SecureChannel(device_id="test_device_2")


# =============================================================================
# Bot Configuration Tests
# =============================================================================

class TestBotConfig:
    """Tests for bot configuration."""

    def test_config_creation(self, tmp_path):
        """Test creating a bot config."""
        config = BotConfig(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            device_id="BOT_1",
            state_dir=tmp_path / "state",
        )

        assert config.homeserver == "https://matrix.org"
        assert config.user_id == "@bot:matrix.org"
        assert config.enable_e2e is True

    def test_config_creates_state_dir(self, tmp_path):
        """Test config creates state directory."""
        state_dir = tmp_path / "matrix_state"
        config = BotConfig(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            state_dir=state_dir,
        )

        assert state_dir.exists()

    def test_config_defaults(self, tmp_path):
        """Test config default values."""
        config = BotConfig(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            state_dir=tmp_path,
        )

        assert config.device_id == "OTTO_BOT"
        assert config.enable_e2e is True
        assert config.auto_join is False
        assert config.command_prefix == "!"


# =============================================================================
# Matrix Message Tests
# =============================================================================

class TestMatrixMessage:
    """Tests for Matrix message parsing."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = MatrixMessage(
            room_id="!room:test.org",
            sender="@user:test.org",
            body="Hello, World!",
            message_type=MessageType.TEXT,
            event_id="$event123",
            timestamp=datetime.now(timezone.utc),
        )

        assert msg.room_id == "!room:test.org"
        assert msg.body == "Hello, World!"
        assert not msg.is_command

    def test_command_detection(self):
        """Test command detection."""
        msg = MatrixMessage(
            room_id="!room:test.org",
            sender="@user:test.org",
            body="!help",
            message_type=MessageType.TEXT,
            event_id="$event123",
            timestamp=datetime.now(timezone.utc),
        )

        assert msg.is_command
        assert msg.command_name == "help"
        assert msg.command_args == []

    def test_command_with_args(self):
        """Test command with arguments."""
        msg = MatrixMessage(
            room_id="!room:test.org",
            sender="@user:test.org",
            body="!threshold sign operation1",
            message_type=MessageType.TEXT,
            event_id="$event123",
            timestamp=datetime.now(timezone.utc),
        )

        assert msg.is_command
        assert msg.command_name == "threshold"
        assert msg.command_args == ["sign", "operation1"]

    def test_non_command_message(self):
        """Test non-command message."""
        msg = MatrixMessage(
            room_id="!room:test.org",
            sender="@user:test.org",
            body="Hello, not a command",
            message_type=MessageType.TEXT,
            event_id="$event123",
            timestamp=datetime.now(timezone.utc),
        )

        assert not msg.is_command
        assert msg.command_name is None
        assert msg.command_args == []


# =============================================================================
# Mock Bot Tests
# =============================================================================

class TestMockBot:
    """Tests for mock Matrix bot."""

    @pytest.mark.asyncio
    async def test_bot_creation(self, mock_bot):
        """Test creating a mock bot."""
        assert mock_bot is not None
        assert isinstance(mock_bot._client, MockMatrixClient)

    @pytest.mark.asyncio
    async def test_bot_login(self, mock_bot):
        """Test bot login."""
        success = await mock_bot.login(password="test_password")
        assert success

    @pytest.mark.asyncio
    async def test_bot_send_message(self, mock_bot):
        """Test sending a message."""
        await mock_bot.login(password="test")

        event_id = await mock_bot.send("!room:test.org", "Hello, World!")

        assert event_id.startswith("$mock_event_")

    @pytest.mark.asyncio
    async def test_bot_reply(self, mock_bot):
        """Test replying to a message."""
        await mock_bot.login(password="test")

        original = MatrixMessage(
            room_id="!room:test.org",
            sender="@user:test.org",
            body="Original message",
            message_type=MessageType.TEXT,
            event_id="$orig",
            timestamp=datetime.now(timezone.utc),
        )

        event_id = await mock_bot.reply(original, "Reply message")

        assert event_id.startswith("$mock_event_")

    @pytest.mark.asyncio
    async def test_bot_command_registration(self, mock_bot):
        """Test registering commands."""
        async def test_handler(msg, args):
            return "Test response"

        mock_bot.register_command(
            name="test",
            handler=test_handler,
            description="A test command",
        )

        assert "test" in mock_bot._commands

    @pytest.mark.asyncio
    async def test_default_commands_registered(self, mock_bot):
        """Test default commands are registered."""
        assert "help" in mock_bot._commands
        assert "ping" in mock_bot._commands
        assert "status" in mock_bot._commands
        assert "version" in mock_bot._commands


# =============================================================================
# Command Tests
# =============================================================================

class TestOTTOCommands:
    """Tests for OTTO command handlers."""

    @pytest.mark.asyncio
    async def test_commands_registration(self, mock_bot):
        """Test registering OTTO commands."""
        commands = register_otto_commands(mock_bot)

        assert "health" in mock_bot._commands
        assert "info" in mock_bot._commands
        assert "secure" in mock_bot._commands
        assert "threshold" in mock_bot._commands

    @pytest.mark.asyncio
    async def test_health_command(self, mock_bot):
        """Test health command."""
        commands = register_otto_commands(mock_bot)

        msg = MatrixMessage(
            room_id="!room:test.org",
            sender="@user:test.org",
            body="!health",
            message_type=MessageType.TEXT,
            event_id="$event",
            timestamp=datetime.now(timezone.utc),
        )

        response = await commands.cmd_health(msg, [])

        assert "OTTO Health Status" in response
        assert "OK" in response

    @pytest.mark.asyncio
    async def test_info_command(self, mock_bot):
        """Test info command."""
        commands = register_otto_commands(mock_bot)

        msg = MatrixMessage(
            room_id="!room:test.org",
            sender="@user:test.org",
            body="!info",
            message_type=MessageType.TEXT,
            event_id="$event",
            timestamp=datetime.now(timezone.utc),
        )

        response = await commands.cmd_info(msg, [])

        assert "OTTO OS Information" in response
        assert "Version" in response


# =============================================================================
# Secure Channel Tests
# =============================================================================

class TestSecureChannel:
    """Tests for secure channel functionality."""

    def test_channel_creation(self, secure_channel):
        """Test creating a secure channel."""
        assert secure_channel is not None
        assert secure_channel.key_id is not None
        assert len(secure_channel.key_id) == 16

    def test_channel_has_public_key(self, secure_channel):
        """Test channel has public key."""
        pk = secure_channel.public_key
        assert pk is not None
        assert pk.classical is not None

    def test_security_status(self, secure_channel):
        """Test security status."""
        status = secure_channel.security_status

        assert 'pq_enabled' in status
        assert 'algorithm' in status
        assert 'key_id' in status
        assert 'active_channels' in status

    def test_create_key_exchange(self, secure_channel):
        """Test creating key exchange message."""
        kex = secure_channel.create_key_exchange()

        assert kex.version == "1.0.0"
        assert kex.sender_id == "test_device_1"
        assert len(kex.public_key) > 0
        assert kex.key_id == secure_channel.key_id

    def test_key_exchange_serialization(self, secure_channel):
        """Test key exchange message serialization."""
        kex = secure_channel.create_key_exchange()

        as_dict = kex.to_dict()
        restored = KeyExchangeMessage.from_dict(as_dict)

        assert restored.sender_id == kex.sender_id
        assert restored.key_id == kex.key_id


class TestSecureChannelKeyExchange:
    """Tests for secure channel key exchange."""

    def test_full_key_exchange(self, secure_channel, peer_channel):
        """Test complete key exchange flow."""
        # Device 1 initiates
        kex1 = secure_channel.create_key_exchange()

        # Device 2 processes and responds
        ciphertext, shared_secret_2 = peer_channel.process_key_exchange(kex1)

        # Device 1 completes
        shared_secret_1 = secure_channel.complete_key_exchange(
            peer_id="test_device_2",
            ciphertext=ciphertext,
        )

        # Both should have the same shared secret
        assert shared_secret_1 == shared_secret_2

    def test_expired_key_exchange_rejected(self, secure_channel, peer_channel):
        """Test that expired key exchange is rejected."""
        kex = KeyExchangeMessage(
            version="1.0.0",
            sender_id="test",
            public_key=secure_channel.public_key.to_bytes(),
            timestamp=time.time() - 600,  # 10 minutes ago
            key_id="old_key",
        )

        with pytest.raises(KeyExchangeError, match="too old"):
            peer_channel.process_key_exchange(kex)


class TestSecureChannelEncryption:
    """Tests for secure channel encryption."""

    def test_encrypt_decrypt(self, secure_channel, peer_channel):
        """Test encrypting and decrypting messages."""
        # Establish channel
        kex1 = secure_channel.create_key_exchange()
        ciphertext, _ = peer_channel.process_key_exchange(kex1)
        secure_channel.complete_key_exchange("test_device_2", ciphertext)

        # Encrypt message
        plaintext = "Hello, secure world!"
        payload = secure_channel.encrypt("test_device_2", plaintext)

        assert payload.message_type == "otto.pq.encrypted"
        assert len(payload.ciphertext) > 0

        # Decrypt message
        decrypted = peer_channel.decrypt("test_device_1", payload)

        assert decrypted == plaintext

    def test_replay_detection(self, secure_channel, peer_channel):
        """Test replay attack detection."""
        # Establish channel
        kex1 = secure_channel.create_key_exchange()
        ciphertext, _ = peer_channel.process_key_exchange(kex1)
        secure_channel.complete_key_exchange("test_device_2", ciphertext)

        # Encrypt message
        payload = secure_channel.encrypt("test_device_2", "Test message")

        # First decrypt should succeed
        peer_channel.decrypt("test_device_1", payload)

        # Second decrypt should fail (replay)
        with pytest.raises(ReplayError, match="replay"):
            peer_channel.decrypt("test_device_1", payload)

    def test_channel_info_updated(self, secure_channel, peer_channel):
        """Test channel info is updated on messages."""
        # Establish channel
        kex1 = secure_channel.create_key_exchange()
        ciphertext, _ = peer_channel.process_key_exchange(kex1)
        secure_channel.complete_key_exchange("test_device_2", ciphertext)

        # Send message
        secure_channel.encrypt("test_device_2", "Test")

        info = secure_channel.get_channel_info("test_device_2")
        assert info is not None
        assert info.messages_sent == 1


class TestSecurePayload:
    """Tests for secure payload serialization."""

    def test_payload_to_json(self):
        """Test payload JSON serialization."""
        payload = SecurePayload(
            version="1.0.0",
            message_type="otto.pq.encrypted",
            ciphertext=b"encrypted_data",
            nonce=b"random_nonce_123",
            timestamp=time.time(),
            sender_key_id="sender123",
            recipient_key_id="recipient456",
        )

        json_str = payload.to_json()
        restored = SecurePayload.from_json(json_str)

        assert restored.version == payload.version
        assert restored.ciphertext == payload.ciphertext
        assert restored.sender_key_id == payload.sender_key_id

    def test_payload_to_dict(self):
        """Test payload dict conversion."""
        payload = SecurePayload(
            version="1.0.0",
            message_type="otto.pq.encrypted",
            ciphertext=b"data",
            nonce=b"nonce",
            timestamp=12345.0,
            sender_key_id="s",
            recipient_key_id="r",
        )

        as_dict = payload.to_dict()

        assert as_dict['version'] == "1.0.0"
        assert 'ciphertext' in as_dict
        assert 'nonce' in as_dict


# =============================================================================
# Threshold Secure Channel Tests
# =============================================================================

class TestThresholdSecureChannel:
    """Tests for threshold-protected secure channel."""

    def test_threshold_channel_creation(self):
        """Test creating a threshold channel."""
        channel = ThresholdSecureChannel(
            device_id="test_device",
            threshold=2,
            total_devices=3,
        )

        assert channel._threshold == 2
        assert channel._total_devices == 3

    def test_create_signature_request(self):
        """Test creating a signature request."""
        channel = ThresholdSecureChannel(
            device_id="test",
            threshold=2,
            total_devices=3,
        )

        request = channel.create_signature_request(
            operation="transfer",
            data=b"transfer $100 to account",
        )

        assert request['type'] == "otto.pq.sig_req"
        assert request['operation'] == "transfer"
        assert request['threshold'] == 2
        assert 'request_id' in request


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_bot(self, tmp_path):
        """Test create_bot function."""
        bot = create_bot(
            homeserver="https://matrix.org",
            user_id="@bot:matrix.org",
            state_dir=tmp_path,
            use_mock=True,
        )

        assert isinstance(bot, OTTOMatrixBot)
        assert isinstance(bot._client, MockMatrixClient)

    def test_create_secure_channel(self):
        """Test create_secure_channel function."""
        channel = create_secure_channel(device_id="test")

        assert isinstance(channel, SecureChannel)

    def test_create_threshold_channel(self):
        """Test creating threshold channel via factory."""
        channel = create_secure_channel(
            device_id="test",
            threshold=2,
            total_devices=3,
        )

        assert isinstance(channel, ThresholdSecureChannel)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the messaging module."""

    @pytest.mark.asyncio
    async def test_full_bot_flow(self, tmp_path):
        """Test full bot workflow."""
        # Create bot
        bot = create_bot(
            homeserver="https://matrix.test.org",
            user_id="@otto:test.org",
            state_dir=tmp_path,
            use_mock=True,
        )

        # Register commands
        register_otto_commands(bot)

        # Login
        await bot.login(password="test")

        # Send message
        event_id = await bot.send("!room:test.org", "Bot is online!")
        assert event_id is not None

        # Verify commands are available
        assert len(bot._commands) > 5

    def test_secure_messaging_flow(self):
        """Test secure messaging between two devices."""
        # Two devices
        device1 = create_secure_channel(device_id="device_1")
        device2 = create_secure_channel(device_id="device_2")

        # Key exchange
        kex = device1.create_key_exchange()
        ct, _ = device2.process_key_exchange(kex)
        device1.complete_key_exchange("device_2", ct)

        # Exchange messages
        messages = [
            "Hello from device 1",
            "Secret information",
            "End of conversation",
        ]

        for msg in messages:
            # Device 1 sends
            payload = device1.encrypt("device_2", msg)

            # Device 2 decrypts
            decrypted = device2.decrypt("device_1", payload)
            assert decrypted == msg

        # Verify stats
        info = device1.get_channel_info("device_2")
        assert info.messages_sent == 3
