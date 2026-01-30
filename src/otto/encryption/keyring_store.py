"""
Keyring Store Module
====================

Integrates with OS-level secure key storage:
- Windows: Credential Manager
- macOS: Keychain
- Linux: Secret Service (libsecret/GNOME Keyring/KWallet)

This provides secure storage for:
- Encryption key salt
- Cached derived keys (optional, session-only)
- Recovery key hints

The actual encryption key is NEVER stored - only the salt needed
to re-derive it from the user's passphrase.
"""

import base64
import logging
from dataclasses import dataclass
from typing import Optional

try:
    import keyring
    from keyring.errors import KeyringError, PasswordDeleteError
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    KeyringError = Exception  # Fallback for type hints
    PasswordDeleteError = Exception

logger = logging.getLogger(__name__)


# Service name for keyring entries
SERVICE_NAME = "otto-os"

# Key names
KEY_SALT = "encryption-salt"
KEY_RECOVERY_HINT = "recovery-hint"
KEY_ENCRYPTION_ENABLED = "encryption-enabled"
KEY_LAST_UNLOCK = "last-unlock"


class KeyringStoreError(Exception):
    """Base exception for keyring operations."""
    pass


class KeyringUnavailableError(KeyringStoreError):
    """Raised when OS keyring is not available."""
    pass


@dataclass
class KeyringEntry:
    """
    A stored keyring entry.

    Attributes:
        key: The entry key name
        value: The stored value
        exists: Whether the entry exists in keyring
    """
    key: str
    value: Optional[str]
    exists: bool


class KeyringStore:
    """
    Secure key storage using OS keyring.

    Stores encryption metadata (NOT the actual encryption key)
    in the OS secure credential store.

    Example:
        >>> store = KeyringStore()
        >>> store.store_salt(salt_bytes)
        >>> salt = store.get_salt()
    """

    def __init__(self, service_name: str = SERVICE_NAME):
        """
        Initialize keyring store.

        Args:
            service_name: Service identifier for keyring entries

        Raises:
            KeyringUnavailableError: If OS keyring is not available
        """
        if not KEYRING_AVAILABLE:
            raise ImportError(
                "keyring is required for secure key storage. "
                "Install with: pip install keyring"
            )

        self.service = service_name
        self._verify_keyring()

    def _verify_keyring(self) -> None:
        """Verify that keyring backend is available."""
        try:
            backend = keyring.get_keyring()
            logger.debug(f"Using keyring backend: {type(backend).__name__}")
        except Exception as e:
            logger.warning(f"Keyring verification failed: {e}")
            # Don't fail - keyring might still work

    def _store(self, key: str, value: str) -> None:
        """Store a value in keyring."""
        try:
            keyring.set_password(self.service, key, value)
            logger.debug(f"Stored keyring entry: {key}")
        except KeyringError as e:
            logger.error(f"Failed to store in keyring: {e}")
            raise KeyringStoreError(f"Failed to store {key}: {e}") from e

    def _get(self, key: str) -> Optional[str]:
        """Get a value from keyring."""
        try:
            value = keyring.get_password(self.service, key)
            logger.debug(f"Retrieved keyring entry: {key} (exists={value is not None})")
            return value
        except KeyringError as e:
            logger.error(f"Failed to get from keyring: {e}")
            raise KeyringStoreError(f"Failed to get {key}: {e}") from e

    def _delete(self, key: str) -> bool:
        """Delete a value from keyring."""
        try:
            keyring.delete_password(self.service, key)
            logger.debug(f"Deleted keyring entry: {key}")
            return True
        except PasswordDeleteError:
            logger.debug(f"Keyring entry not found: {key}")
            return False
        except KeyringError as e:
            logger.error(f"Failed to delete from keyring: {e}")
            raise KeyringStoreError(f"Failed to delete {key}: {e}") from e

    # =========================================================================
    # Salt Storage
    # =========================================================================

    def store_salt(self, salt: bytes) -> None:
        """
        Store the encryption key salt.

        The salt is needed to re-derive the encryption key from
        the user's passphrase.

        Args:
            salt: The salt bytes (typically 16 bytes)
        """
        # Encode as base64 for safe storage
        encoded = base64.b64encode(salt).decode('ascii')
        self._store(KEY_SALT, encoded)

    def get_salt(self) -> Optional[bytes]:
        """
        Retrieve the encryption key salt.

        Returns:
            Salt bytes, or None if not set
        """
        encoded = self._get(KEY_SALT)
        if encoded is None:
            return None
        return base64.b64decode(encoded)

    def has_salt(self) -> bool:
        """Check if salt is stored."""
        return self._get(KEY_SALT) is not None

    def delete_salt(self) -> bool:
        """Delete the stored salt."""
        return self._delete(KEY_SALT)

    # =========================================================================
    # Recovery Hint
    # =========================================================================

    def store_recovery_hint(self, hint: str) -> None:
        """
        Store a hint about where to find the recovery key.

        This is NOT the recovery key itself - just a reminder
        to the user about where they stored it.

        Args:
            hint: User's reminder text (e.g., "Printed and in safe")
        """
        self._store(KEY_RECOVERY_HINT, hint)

    def get_recovery_hint(self) -> Optional[str]:
        """Get the recovery hint."""
        return self._get(KEY_RECOVERY_HINT)

    # =========================================================================
    # Encryption State
    # =========================================================================

    def set_encryption_enabled(self, enabled: bool) -> None:
        """
        Store whether encryption is enabled.

        Args:
            enabled: True if encryption is configured
        """
        self._store(KEY_ENCRYPTION_ENABLED, "true" if enabled else "false")

    def is_encryption_enabled(self) -> bool:
        """Check if encryption is enabled."""
        value = self._get(KEY_ENCRYPTION_ENABLED)
        return value == "true"

    def mark_unlocked(self) -> None:
        """Mark that encryption was successfully unlocked."""
        import time
        self._store(KEY_LAST_UNLOCK, str(int(time.time())))

    def get_last_unlock_time(self) -> Optional[int]:
        """Get timestamp of last successful unlock."""
        value = self._get(KEY_LAST_UNLOCK)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    # =========================================================================
    # Cleanup
    # =========================================================================

    def clear_all(self) -> None:
        """
        Clear all OTTO keyring entries.

        WARNING: This will require re-setup of encryption.
        """
        keys = [KEY_SALT, KEY_RECOVERY_HINT, KEY_ENCRYPTION_ENABLED, KEY_LAST_UNLOCK]
        for key in keys:
            try:
                self._delete(key)
            except KeyringStoreError:
                pass  # Ignore errors during cleanup

        logger.info("Cleared all OTTO keyring entries")

    def get_status(self) -> dict:
        """
        Get status of keyring storage.

        Returns:
            Dict with storage status information
        """
        try:
            backend = keyring.get_keyring()
            backend_name = type(backend).__name__
        except Exception:
            backend_name = "unknown"

        return {
            "available": KEYRING_AVAILABLE,
            "backend": backend_name,
            "has_salt": self.has_salt(),
            "encryption_enabled": self.is_encryption_enabled(),
            "last_unlock": self.get_last_unlock_time(),
        }


def create_keyring_store(service_name: str = SERVICE_NAME) -> KeyringStore:
    """Factory function to create a KeyringStore."""
    return KeyringStore(service_name)


def is_keyring_available() -> bool:
    """Check if keyring is available without creating a store."""
    if not KEYRING_AVAILABLE:
        return False

    try:
        backend = keyring.get_keyring()
        # Check if it's a usable backend (not the fail backend)
        backend_name = type(backend).__name__
        if 'Fail' in backend_name or 'Null' in backend_name:
            return False
        return True
    except Exception:
        return False


__all__ = [
    'KeyringStore',
    'KeyringEntry',
    'KeyringStoreError',
    'KeyringUnavailableError',
    'create_keyring_store',
    'is_keyring_available',
    'SERVICE_NAME',
    'KEYRING_AVAILABLE',
]
