"""
OS Keyring Adapter
==================

Secure storage of encryption keys in the operating system's keychain.

Backends:
- Windows: Credential Manager
- macOS: Keychain
- Linux: libsecret/GNOME Keyring

Determinism:
- FIXED service name: "otto-os"
- FIXED key format: base64-encoded bytes
- DETERMINISTIC: same identifier → same key retrieval

Security Properties:
- Keys protected by OS-level security
- Automatic locking/unlocking with user session
- No plaintext keys on disk

Usage:
    from otto.crypto import store_key, retrieve_key, delete_key

    # Store encryption key
    store_key("master", key_bytes)

    # Retrieve later
    key = retrieve_key("master")

    # Clean up
    delete_key("master")
"""

import logging
import base64
from typing import Optional

import keyring
from keyring.errors import KeyringError as BaseKeyringError, PasswordDeleteError

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED)
# =============================================================================

SERVICE_NAME = "otto-os"
KEY_PREFIX = "key:"  # Prefix for key identifiers


# =============================================================================
# Exceptions
# =============================================================================

class KeyringError(Exception):
    """Raised when keyring operations fail."""
    pass


class KeyNotFoundError(KeyringError):
    """Raised when key is not found in keyring."""
    pass


# =============================================================================
# KeyringAdapter Class
# =============================================================================

class KeyringAdapter:
    """
    Adapter for OS keyring operations.

    Provides a consistent interface across platforms:
    - Windows: Credential Manager
    - macOS: Keychain
    - Linux: libsecret/GNOME Keyring

    Example:
        adapter = KeyringAdapter()
        adapter.store("master", key_bytes)
        key = adapter.retrieve("master")
    """

    def __init__(self, service_name: str = SERVICE_NAME):
        """
        Initialize keyring adapter.

        Args:
            service_name: Service identifier in keyring
        """
        self.service_name = service_name
        self._verify_backend()

    def _verify_backend(self) -> None:
        """Verify keyring backend is available."""
        backend = keyring.get_keyring()
        logger.debug(f"Using keyring backend: {backend.__class__.__name__}")

        # Check for null/fail backends
        backend_name = backend.__class__.__name__.lower()
        if "fail" in backend_name or "null" in backend_name:
            logger.warning(f"Keyring backend may not be secure: {backend_name}")

    def store(self, identifier: str, key: bytes) -> None:
        """
        Store key in OS keyring.

        Args:
            identifier: Key identifier (e.g., "master", "recovery")
            key: Key bytes to store

        Raises:
            KeyringError: If storage fails
        """
        username = f"{KEY_PREFIX}{identifier}"
        password = base64.b64encode(key).decode("ascii")

        try:
            keyring.set_password(self.service_name, username, password)
            logger.info(f"Key stored in keyring: {identifier}")
        except BaseKeyringError as e:
            raise KeyringError(f"Failed to store key '{identifier}': {e}")
        except Exception as e:
            raise KeyringError(f"Unexpected error storing key: {e}")

    def retrieve(self, identifier: str) -> bytes:
        """
        Retrieve key from OS keyring.

        Args:
            identifier: Key identifier

        Returns:
            Key bytes

        Raises:
            KeyNotFoundError: If key not found
            KeyringError: If retrieval fails
        """
        username = f"{KEY_PREFIX}{identifier}"

        try:
            password = keyring.get_password(self.service_name, username)

            if password is None:
                raise KeyNotFoundError(f"Key not found: {identifier}")

            key = base64.b64decode(password)
            logger.debug(f"Key retrieved from keyring: {identifier}")
            return key

        except KeyNotFoundError:
            raise
        except BaseKeyringError as e:
            raise KeyringError(f"Failed to retrieve key '{identifier}': {e}")
        except Exception as e:
            raise KeyringError(f"Unexpected error retrieving key: {e}")

    def delete(self, identifier: str) -> None:
        """
        Delete key from OS keyring.

        Args:
            identifier: Key identifier

        Raises:
            KeyNotFoundError: If key not found
            KeyringError: If deletion fails
        """
        username = f"{KEY_PREFIX}{identifier}"

        try:
            keyring.delete_password(self.service_name, username)
            logger.info(f"Key deleted from keyring: {identifier}")
        except PasswordDeleteError:
            raise KeyNotFoundError(f"Key not found: {identifier}")
        except BaseKeyringError as e:
            raise KeyringError(f"Failed to delete key '{identifier}': {e}")
        except Exception as e:
            raise KeyringError(f"Unexpected error deleting key: {e}")

    def exists(self, identifier: str) -> bool:
        """
        Check if key exists in keyring.

        Args:
            identifier: Key identifier

        Returns:
            True if key exists
        """
        try:
            username = f"{KEY_PREFIX}{identifier}"
            password = keyring.get_password(self.service_name, username)
            return password is not None
        except Exception:
            return False

    def list_keys(self) -> list[str]:
        """
        List all stored key identifiers.

        Note: Not all backends support enumeration.
        This is a best-effort implementation.

        Returns:
            List of key identifiers
        """
        # Most keyring backends don't support enumeration
        # This would need backend-specific implementation
        logger.warning("Key enumeration not supported by all backends")
        return []


# =============================================================================
# Global Adapter Instance
# =============================================================================

_adapter: Optional[KeyringAdapter] = None


def get_adapter() -> KeyringAdapter:
    """Get or create global keyring adapter."""
    global _adapter
    if _adapter is None:
        _adapter = KeyringAdapter()
    return _adapter


# =============================================================================
# Convenience Functions
# =============================================================================

def store_key(identifier: str, key: bytes) -> None:
    """
    Store key in OS keyring.

    Args:
        identifier: Key identifier
        key: Key bytes to store

    Raises:
        KeyringError: If storage fails
    """
    get_adapter().store(identifier, key)


def retrieve_key(identifier: str) -> bytes:
    """
    Retrieve key from OS keyring.

    Args:
        identifier: Key identifier

    Returns:
        Key bytes

    Raises:
        KeyNotFoundError: If key not found
        KeyringError: If retrieval fails
    """
    return get_adapter().retrieve(identifier)


def delete_key(identifier: str) -> None:
    """
    Delete key from OS keyring.

    Args:
        identifier: Key identifier

    Raises:
        KeyNotFoundError: If key not found
        KeyringError: If deletion fails
    """
    get_adapter().delete(identifier)


def key_exists(identifier: str) -> bool:
    """
    Check if key exists in keyring.

    Args:
        identifier: Key identifier

    Returns:
        True if key exists
    """
    return get_adapter().exists(identifier)


__all__ = [
    "KeyringAdapter",
    "KeyringError",
    "KeyNotFoundError",
    "store_key",
    "retrieve_key",
    "delete_key",
    "key_exists",
    "get_adapter",
    "SERVICE_NAME",
]
