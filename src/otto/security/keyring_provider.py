"""
Keyring Provider Abstraction
============================

Provides platform-agnostic secure credential storage.

Supports:
- Desktop: System keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- Mobile: Secure enclave / app sandbox (future)
- Testing: In-memory mock provider

[He2025] Compliance:
- Fixed provider selection order
- Deterministic behavior
- No runtime variation in credential operations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, List
import logging
import os

logger = logging.getLogger(__name__)


class KeyringBackend(Enum):
    """Available keyring backends."""
    SYSTEM = "system"          # OS keyring (keyring library)
    ENCRYPTED_FILE = "file"    # Encrypted file fallback
    MEMORY = "memory"          # In-memory (testing only)
    NONE = "none"              # Disabled (no credential storage)


@dataclass
class Credential:
    """
    A stored credential.

    Attributes:
        service: Service/application identifier
        username: Account/key identifier
        password: The secret value
        metadata: Optional additional data
    """
    service: str
    username: str
    password: str
    metadata: Optional[Dict[str, str]] = None


class KeyringProvider(ABC):
    """
    Abstract base class for keyring providers.

    Implementations must provide secure storage for credentials.
    """

    @property
    @abstractmethod
    def backend(self) -> KeyringBackend:
        """Return the backend type."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current platform."""
        pass

    @abstractmethod
    def get_password(self, service: str, username: str) -> Optional[str]:
        """
        Retrieve a password from the keyring.

        Args:
            service: Service identifier (e.g., "otto", "otto-api")
            username: Account/key identifier

        Returns:
            The password/secret, or None if not found
        """
        pass

    @abstractmethod
    def set_password(self, service: str, username: str, password: str) -> bool:
        """
        Store a password in the keyring.

        Args:
            service: Service identifier
            username: Account/key identifier
            password: The secret value to store

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def delete_password(self, service: str, username: str) -> bool:
        """
        Delete a password from the keyring.

        Args:
            service: Service identifier
            username: Account/key identifier

        Returns:
            True if deleted, False if didn't exist
        """
        pass

    def get_credential(self, service: str, username: str) -> Optional[Credential]:
        """
        Get a full credential object.

        Default implementation wraps get_password.
        """
        password = self.get_password(service, username)
        if password is None:
            return None
        return Credential(service=service, username=username, password=password)

    def set_credential(self, credential: Credential) -> bool:
        """
        Store a full credential object.

        Default implementation wraps set_password.
        """
        return self.set_password(
            credential.service,
            credential.username,
            credential.password
        )


class SystemKeyringProvider(KeyringProvider):
    """
    System keyring provider using the 'keyring' library.

    Uses:
    - Windows: Windows Credential Manager
    - macOS: Keychain
    - Linux: Secret Service (GNOME Keyring, KWallet)
    """

    def __init__(self):
        self._keyring = None
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if keyring library is available and functional."""
        try:
            import keyring
            self._keyring = keyring
            # Try to get the active backend
            backend = keyring.get_keyring()
            # Check it's not the fail backend
            return not isinstance(backend, keyring.backends.fail.Keyring)
        except ImportError:
            logger.debug("keyring library not installed")
            return False
        except Exception as e:
            logger.debug(f"keyring not available: {e}")
            return False

    @property
    def backend(self) -> KeyringBackend:
        return KeyringBackend.SYSTEM

    @property
    def is_available(self) -> bool:
        return self._available

    def get_password(self, service: str, username: str) -> Optional[str]:
        """Get password from system keyring."""
        if not self._available:
            return None
        try:
            return self._keyring.get_password(service, username)
        except Exception as e:
            logger.warning(f"Failed to get password from keyring: {e}")
            return None

    def set_password(self, service: str, username: str, password: str) -> bool:
        """Store password in system keyring."""
        if not self._available:
            return False
        try:
            self._keyring.set_password(service, username, password)
            return True
        except Exception as e:
            logger.error(f"Failed to set password in keyring: {e}")
            return False

    def delete_password(self, service: str, username: str) -> bool:
        """Delete password from system keyring."""
        if not self._available:
            return False
        try:
            self._keyring.delete_password(service, username)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete password from keyring: {e}")
            return False


class MemoryKeyringProvider(KeyringProvider):
    """
    In-memory keyring provider for testing.

    NOT SECURE - only use for testing!
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, str]] = {}

    @property
    def backend(self) -> KeyringBackend:
        return KeyringBackend.MEMORY

    @property
    def is_available(self) -> bool:
        return True

    def get_password(self, service: str, username: str) -> Optional[str]:
        """Get password from memory."""
        service_store = self._store.get(service, {})
        return service_store.get(username)

    def set_password(self, service: str, username: str, password: str) -> bool:
        """Store password in memory."""
        if service not in self._store:
            self._store[service] = {}
        self._store[service][username] = password
        return True

    def delete_password(self, service: str, username: str) -> bool:
        """Delete password from memory."""
        if service in self._store and username in self._store[service]:
            del self._store[service][username]
            return True
        return False

    def clear(self) -> None:
        """Clear all stored credentials."""
        self._store.clear()


class NoOpKeyringProvider(KeyringProvider):
    """
    No-op keyring provider when credential storage is disabled.

    All operations return None/False but don't error.
    """

    @property
    def backend(self) -> KeyringBackend:
        return KeyringBackend.NONE

    @property
    def is_available(self) -> bool:
        return True  # Always "available" but does nothing

    def get_password(self, service: str, username: str) -> Optional[str]:
        return None

    def set_password(self, service: str, username: str, password: str) -> bool:
        logger.warning("Keyring disabled - credential not stored")
        return False

    def delete_password(self, service: str, username: str) -> bool:
        return False


# =============================================================================
# Keyring Manager
# =============================================================================

class KeyringManager:
    """
    Manages keyring provider selection and access.

    Automatically selects the best available provider:
    1. System keyring (if available)
    2. Encrypted file fallback (if enabled)
    3. Memory (if testing)
    4. No-op (if disabled)

    Environment Variables:
        OTTO_KEYRING_BACKEND: Force a specific backend ('system', 'file', 'memory', 'none')
        OTTO_KEYRING_DISABLED: Set to 'true' to disable all credential storage
    """

    def __init__(self, provider: Optional[KeyringProvider] = None):
        """
        Initialize keyring manager.

        Args:
            provider: Explicit provider to use (auto-selects if None)
        """
        self._provider = provider or self._select_provider()

    def _select_provider(self) -> KeyringProvider:
        """
        Select the best available keyring provider.

        [He2025] Fixed selection order: env override → system → file → none
        """
        # Check for explicit disable
        if os.environ.get("OTTO_KEYRING_DISABLED", "").lower() == "true":
            logger.info("Keyring disabled via environment")
            return NoOpKeyringProvider()

        # Check for explicit backend selection
        backend_env = os.environ.get("OTTO_KEYRING_BACKEND", "").lower()
        if backend_env:
            if backend_env == "system":
                provider = SystemKeyringProvider()
                if provider.is_available:
                    return provider
                logger.warning("System keyring requested but not available")
            elif backend_env == "memory":
                return MemoryKeyringProvider()
            elif backend_env == "none":
                return NoOpKeyringProvider()

        # Auto-select: try system keyring first
        system_provider = SystemKeyringProvider()
        if system_provider.is_available:
            logger.debug("Using system keyring")
            return system_provider

        # Fallback to no-op with warning
        logger.warning("No keyring backend available - credentials will not be stored securely")
        return NoOpKeyringProvider()

    @property
    def provider(self) -> KeyringProvider:
        """Get the active keyring provider."""
        return self._provider

    @property
    def backend(self) -> KeyringBackend:
        """Get the active backend type."""
        return self._provider.backend

    @property
    def is_available(self) -> bool:
        """Check if secure credential storage is available."""
        return self._provider.is_available and self._provider.backend != KeyringBackend.NONE

    # Delegate to provider
    def get_password(self, service: str, username: str) -> Optional[str]:
        """Get a password from the keyring."""
        return self._provider.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> bool:
        """Store a password in the keyring."""
        return self._provider.set_password(service, username, password)

    def delete_password(self, service: str, username: str) -> bool:
        """Delete a password from the keyring."""
        return self._provider.delete_password(service, username)

    def get_credential(self, service: str, username: str) -> Optional[Credential]:
        """Get a full credential."""
        return self._provider.get_credential(service, username)

    def set_credential(self, credential: Credential) -> bool:
        """Store a full credential."""
        return self._provider.set_credential(credential)


# =============================================================================
# Global Instance
# =============================================================================

_keyring_manager: Optional[KeyringManager] = None


def get_keyring() -> KeyringManager:
    """
    Get the global keyring manager instance.

    Creates and auto-selects provider on first call.
    """
    global _keyring_manager
    if _keyring_manager is None:
        _keyring_manager = KeyringManager()
    return _keyring_manager


def set_keyring(manager: KeyringManager) -> None:
    """
    Set the global keyring manager.

    Useful for testing or custom deployments.
    """
    global _keyring_manager
    _keyring_manager = manager


def reset_keyring() -> None:
    """Reset global keyring manager (for testing)."""
    global _keyring_manager
    _keyring_manager = None
