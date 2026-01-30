"""
Tests for Encryption Manager
=============================

Tests for the high-level encryption orchestration.
"""

import pytest
import tempfile
from pathlib import Path

from otto.encryption import (
    EncryptionManager,
    EncryptionStatus,
    EncryptionManagerError,
    NotSetupError,
    NotUnlockedError,
    AlreadySetupError,
    InvalidPassphraseError,
    create_encryption_manager,
    CRYPTO_AVAILABLE,
    ARGON2_AVAILABLE,
)


ENCRYPTION_AVAILABLE = CRYPTO_AVAILABLE and ARGON2_AVAILABLE


@pytest.mark.skipif(not ENCRYPTION_AVAILABLE, reason="encryption deps not installed")
class TestEncryptionManagerSetup:
    """Tests for encryption setup."""

    def test_create_manager(self):
        """Manager can be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = create_encryption_manager(Path(tmpdir))
            assert manager is not None

    def test_not_setup_initially(self):
        """Manager is not set up initially."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            assert not manager.is_setup()

    def test_setup_returns_recovery_key(self):
        """Setup returns formatted recovery key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            recovery_key = manager.setup("strong-passphrase-12345")

            # Should be formatted with dashes
            assert '-' in recovery_key
            # Should be 64 hex chars + 15 dashes = 79 total
            assert len(recovery_key) == 79

    def test_setup_marks_as_setup(self):
        """Setup marks encryption as configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("strong-passphrase-12345")

            assert manager.is_setup()
            assert manager.is_unlocked()

    def test_setup_twice_raises(self):
        """Setup twice raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("strong-passphrase-12345")

            with pytest.raises(AlreadySetupError):
                manager.setup("another-passphrase-67890")

    def test_weak_passphrase_rejected(self):
        """Weak passphrase is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))

            with pytest.raises(InvalidPassphraseError):
                manager.setup("short")

            with pytest.raises(InvalidPassphraseError):
                manager.setup("password12345")


@pytest.mark.skipif(not ENCRYPTION_AVAILABLE, reason="encryption deps not installed")
class TestEncryptionManagerUnlock:
    """Tests for unlock/lock operations."""

    @pytest.fixture
    def setup_manager(self):
        """Create a set up manager."""
        tmpdir = tempfile.mkdtemp()
        manager = EncryptionManager(Path(tmpdir))
        manager.setup("test-passphrase-123")
        manager.lock()
        return manager, tmpdir

    def test_unlock_with_correct_passphrase(self, setup_manager):
        """Unlock works with correct passphrase."""
        manager, _ = setup_manager
        assert not manager.is_unlocked()

        result = manager.unlock("test-passphrase-123")

        assert result is True
        assert manager.is_unlocked()

    def test_unlock_with_wrong_passphrase(self, setup_manager):
        """Wrong passphrase fails unlock."""
        manager, _ = setup_manager

        with pytest.raises(InvalidPassphraseError):
            manager.unlock("wrong-passphrase-999")

    def test_lock_clears_state(self):
        """Lock clears encryption key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")

            assert manager.is_unlocked()

            manager.lock()

            assert not manager.is_unlocked()

    def test_unlock_not_setup_raises(self):
        """Unlock before setup raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))

            with pytest.raises(NotSetupError):
                manager.unlock("any-passphrase")


@pytest.mark.skipif(not ENCRYPTION_AVAILABLE, reason="encryption deps not installed")
class TestEncryptionManagerRecovery:
    """Tests for recovery key operations."""

    def test_unlock_with_recovery_key(self):
        """Recovery key can unlock encryption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            recovery_key = manager.setup("test-passphrase-123")
            manager.lock()

            result = manager.unlock_with_recovery_key(recovery_key)

            assert result is True
            assert manager.is_unlocked()

    def test_invalid_recovery_key_fails(self):
        """Invalid recovery key fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")
            manager.lock()

            with pytest.raises(InvalidPassphraseError):
                manager.unlock_with_recovery_key("invalid-recovery-key")


@pytest.mark.skipif(not ENCRYPTION_AVAILABLE, reason="encryption deps not installed")
class TestEncryptionManagerFileOperations:
    """Tests for encrypted file operations."""

    def test_write_and_read_encrypted(self):
        """Can write and read encrypted files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")

            # Write encrypted
            content = b"secret data"
            manager.write_encrypted("test.dat", content)

            # Read encrypted
            result = manager.read_encrypted("test.dat")

            assert result == content

    def test_write_and_read_string(self):
        """Can write and read strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")

            content = "secret string with unicode: 世界"
            manager.write_encrypted_string("test.txt", content)

            result = manager.read_encrypted_string("test.txt")

            assert result == content

    def test_read_requires_unlock(self):
        """Reading requires unlocked state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")
            manager.write_encrypted("test.dat", b"data")
            manager.lock()

            with pytest.raises(NotUnlockedError):
                manager.read_encrypted("test.dat")

    def test_write_requires_unlock(self):
        """Writing requires unlocked state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")
            manager.lock()

            with pytest.raises(NotUnlockedError):
                manager.write_encrypted("test.dat", b"data")

    def test_file_persists_after_lock_unlock(self):
        """Encrypted files persist across lock/unlock."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")

            # Write
            content = b"persistent data"
            manager.write_encrypted("persistent.dat", content)

            # Lock and unlock
            manager.lock()
            manager.unlock("test-passphrase-123")

            # Read
            result = manager.read_encrypted("persistent.dat")
            assert result == content


@pytest.mark.skipif(not ENCRYPTION_AVAILABLE, reason="encryption deps not installed")
class TestEncryptionManagerStatus:
    """Tests for status reporting."""

    def test_status_not_setup(self):
        """Status when not set up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            status = manager.get_status()

            assert status.is_setup is False
            assert status.is_unlocked is False

    def test_status_setup_and_unlocked(self):
        """Status when set up and unlocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")

            status = manager.get_status()

            assert status.is_setup is True
            assert status.is_unlocked is True

    def test_status_to_dict(self):
        """Status can be serialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            status = manager.get_status()

            d = status.to_dict()

            assert "is_setup" in d
            assert "is_unlocked" in d
            assert "encrypted_file_count" in d


@pytest.mark.skipif(not ENCRYPTION_AVAILABLE, reason="encryption deps not installed")
class TestEncryptionManagerPassphraseChange:
    """Tests for passphrase change."""

    def test_change_passphrase(self):
        """Can change passphrase."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("old-passphrase-123")

            # Write some data
            manager.write_encrypted("data.dat", b"secret")
            manager.lock()

            # Change passphrase
            manager.unlock("old-passphrase-123")
            manager.change_passphrase("old-passphrase-123", "new-passphrase-456")
            manager.lock()

            # Old passphrase no longer works
            with pytest.raises(InvalidPassphraseError):
                manager.unlock("old-passphrase-123")

            # New passphrase works
            manager.unlock("new-passphrase-456")

            # Data still accessible
            result = manager.read_encrypted("data.dat")
            assert result == b"secret"


@pytest.mark.skipif(not ENCRYPTION_AVAILABLE, reason="encryption deps not installed")
class TestEncryptionManagerReset:
    """Tests for encryption reset."""

    def test_reset_requires_confirmation(self):
        """Reset requires explicit confirmation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")

            with pytest.raises(EncryptionManagerError):
                manager.reset()  # No confirm

            with pytest.raises(EncryptionManagerError):
                manager.reset(confirm=False)

    def test_reset_clears_state(self):
        """Reset clears all encryption state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = EncryptionManager(Path(tmpdir))
            manager.setup("test-passphrase-123")

            manager.reset(confirm=True)

            assert not manager.is_setup()
            assert not manager.is_unlocked()
