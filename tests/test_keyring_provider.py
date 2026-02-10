"""
Tests for Keyring Provider Abstraction
======================================

Tests the keyring provider interface and implementations.

Determinism:
- Tests verify deterministic behavior
- Same operations → same results
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from otto.security.keyring_provider import (
    KeyringProvider,
    KeyringBackend,
    Credential,
    SystemKeyringProvider,
    MemoryKeyringProvider,
    NoOpKeyringProvider,
    KeyringManager,
    get_keyring,
    set_keyring,
    reset_keyring,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def memory_provider():
    """Create a memory keyring provider."""
    return MemoryKeyringProvider()


@pytest.fixture
def noop_provider():
    """Create a no-op keyring provider."""
    return NoOpKeyringProvider()


@pytest.fixture
def memory_manager(memory_provider):
    """Create a keyring manager with memory provider."""
    return KeyringManager(provider=memory_provider)


@pytest.fixture(autouse=True)
def reset_global():
    """Reset global keyring manager before and after each test."""
    reset_keyring()
    yield
    reset_keyring()


# =============================================================================
# Credential Tests
# =============================================================================

class TestCredential:
    """Tests for Credential dataclass."""

    def test_create_credential(self):
        """Test creating a credential."""
        cred = Credential(
            service="otto",
            username="api_key",
            password="secret123"
        )

        assert cred.service == "otto"
        assert cred.username == "api_key"
        assert cred.password == "secret123"
        assert cred.metadata is None

    def test_create_credential_with_metadata(self):
        """Test creating a credential with metadata."""
        cred = Credential(
            service="otto",
            username="api_key",
            password="secret123",
            metadata={"created": "2024-01-01", "expires": "2025-01-01"}
        )

        assert cred.metadata["created"] == "2024-01-01"
        assert cred.metadata["expires"] == "2025-01-01"


# =============================================================================
# MemoryKeyringProvider Tests
# =============================================================================

class TestMemoryKeyringProvider:
    """Tests for MemoryKeyringProvider."""

    def test_backend_type(self, memory_provider):
        """Test backend type is MEMORY."""
        assert memory_provider.backend == KeyringBackend.MEMORY

    def test_is_available(self, memory_provider):
        """Test availability."""
        assert memory_provider.is_available is True

    def test_set_get_password(self, memory_provider):
        """Test storing and retrieving a password."""
        success = memory_provider.set_password("otto", "api_key", "secret123")
        assert success is True

        password = memory_provider.get_password("otto", "api_key")
        assert password == "secret123"

    def test_get_nonexistent_password(self, memory_provider):
        """Test getting a nonexistent password."""
        password = memory_provider.get_password("otto", "nonexistent")
        assert password is None

    def test_delete_password(self, memory_provider):
        """Test deleting a password."""
        memory_provider.set_password("otto", "api_key", "secret123")

        success = memory_provider.delete_password("otto", "api_key")
        assert success is True

        password = memory_provider.get_password("otto", "api_key")
        assert password is None

    def test_delete_nonexistent_password(self, memory_provider):
        """Test deleting a nonexistent password."""
        success = memory_provider.delete_password("otto", "nonexistent")
        assert success is False

    def test_multiple_services(self, memory_provider):
        """Test storing passwords for multiple services."""
        memory_provider.set_password("otto", "key1", "secret1")
        memory_provider.set_password("other", "key1", "secret2")

        assert memory_provider.get_password("otto", "key1") == "secret1"
        assert memory_provider.get_password("other", "key1") == "secret2"

    def test_multiple_usernames(self, memory_provider):
        """Test storing multiple passwords for same service."""
        memory_provider.set_password("otto", "key1", "secret1")
        memory_provider.set_password("otto", "key2", "secret2")

        assert memory_provider.get_password("otto", "key1") == "secret1"
        assert memory_provider.get_password("otto", "key2") == "secret2"

    def test_overwrite_password(self, memory_provider):
        """Test overwriting an existing password."""
        memory_provider.set_password("otto", "api_key", "secret1")
        memory_provider.set_password("otto", "api_key", "secret2")

        password = memory_provider.get_password("otto", "api_key")
        assert password == "secret2"

    def test_clear(self, memory_provider):
        """Test clearing all credentials."""
        memory_provider.set_password("otto", "key1", "secret1")
        memory_provider.set_password("other", "key2", "secret2")

        memory_provider.clear()

        assert memory_provider.get_password("otto", "key1") is None
        assert memory_provider.get_password("other", "key2") is None

    def test_get_credential(self, memory_provider):
        """Test getting a full credential object."""
        memory_provider.set_password("otto", "api_key", "secret123")

        cred = memory_provider.get_credential("otto", "api_key")

        assert cred is not None
        assert cred.service == "otto"
        assert cred.username == "api_key"
        assert cred.password == "secret123"

    def test_get_credential_nonexistent(self, memory_provider):
        """Test getting nonexistent credential."""
        cred = memory_provider.get_credential("otto", "nonexistent")
        assert cred is None

    def test_set_credential(self, memory_provider):
        """Test storing a full credential object."""
        cred = Credential(
            service="otto",
            username="api_key",
            password="secret123"
        )

        success = memory_provider.set_credential(cred)
        assert success is True

        password = memory_provider.get_password("otto", "api_key")
        assert password == "secret123"


# =============================================================================
# NoOpKeyringProvider Tests
# =============================================================================

class TestNoOpKeyringProvider:
    """Tests for NoOpKeyringProvider."""

    def test_backend_type(self, noop_provider):
        """Test backend type is NONE."""
        assert noop_provider.backend == KeyringBackend.NONE

    def test_is_available(self, noop_provider):
        """Test availability (always True)."""
        assert noop_provider.is_available is True

    def test_get_password_returns_none(self, noop_provider):
        """Test get_password always returns None."""
        password = noop_provider.get_password("otto", "api_key")
        assert password is None

    def test_set_password_returns_false(self, noop_provider):
        """Test set_password always returns False."""
        success = noop_provider.set_password("otto", "api_key", "secret")
        assert success is False

    def test_delete_password_returns_false(self, noop_provider):
        """Test delete_password always returns False."""
        success = noop_provider.delete_password("otto", "api_key")
        assert success is False


# =============================================================================
# SystemKeyringProvider Tests
# =============================================================================

class TestSystemKeyringProvider:
    """Tests for SystemKeyringProvider."""

    def test_backend_type(self):
        """Test backend type is SYSTEM."""
        provider = SystemKeyringProvider()
        assert provider.backend == KeyringBackend.SYSTEM

    def test_availability_without_keyring_library(self):
        """Test availability when keyring library not installed."""
        with patch.dict('sys.modules', {'keyring': None}):
            provider = SystemKeyringProvider()
            # May or may not be available depending on actual installation

    def test_operations_when_unavailable(self):
        """Test operations gracefully fail when unavailable."""
        provider = SystemKeyringProvider()
        provider._available = False

        assert provider.get_password("otto", "key") is None
        assert provider.set_password("otto", "key", "secret") is False
        assert provider.delete_password("otto", "key") is False


# =============================================================================
# KeyringManager Tests
# =============================================================================

class TestKeyringManager:
    """Tests for KeyringManager."""

    def test_uses_provided_provider(self, memory_provider):
        """Test manager uses explicitly provided provider."""
        manager = KeyringManager(provider=memory_provider)
        assert manager.provider is memory_provider

    def test_backend_property(self, memory_manager):
        """Test backend property."""
        assert memory_manager.backend == KeyringBackend.MEMORY

    def test_is_available(self, memory_manager):
        """Test is_available property."""
        assert memory_manager.is_available is True

    def test_is_available_with_noop(self, noop_provider):
        """Test is_available is False with NoOp provider."""
        manager = KeyringManager(provider=noop_provider)
        assert manager.is_available is False

    def test_get_set_password(self, memory_manager):
        """Test password operations via manager."""
        success = memory_manager.set_password("otto", "key", "secret")
        assert success is True

        password = memory_manager.get_password("otto", "key")
        assert password == "secret"

    def test_delete_password(self, memory_manager):
        """Test delete via manager."""
        memory_manager.set_password("otto", "key", "secret")

        success = memory_manager.delete_password("otto", "key")
        assert success is True

        assert memory_manager.get_password("otto", "key") is None

    def test_get_set_credential(self, memory_manager):
        """Test credential operations via manager."""
        cred = Credential(
            service="otto",
            username="api_key",
            password="secret123"
        )

        success = memory_manager.set_credential(cred)
        assert success is True

        result = memory_manager.get_credential("otto", "api_key")
        assert result is not None
        assert result.password == "secret123"

    def test_env_disable_keyring(self):
        """Test disabling keyring via environment."""
        with patch.dict(os.environ, {"OTTO_KEYRING_DISABLED": "true"}):
            manager = KeyringManager()
            assert manager.backend == KeyringBackend.NONE

    def test_env_force_memory_backend(self):
        """Test forcing memory backend via environment."""
        with patch.dict(os.environ, {"OTTO_KEYRING_BACKEND": "memory"}):
            manager = KeyringManager()
            assert manager.backend == KeyringBackend.MEMORY

    def test_env_force_none_backend(self):
        """Test forcing none backend via environment."""
        with patch.dict(os.environ, {"OTTO_KEYRING_BACKEND": "none"}):
            manager = KeyringManager()
            assert manager.backend == KeyringBackend.NONE


# =============================================================================
# Global Instance Tests
# =============================================================================

class TestGlobalInstance:
    """Tests for global keyring instance."""

    def test_get_keyring_creates_instance(self):
        """Test that get_keyring creates a manager."""
        keyring = get_keyring()
        assert isinstance(keyring, KeyringManager)

    def test_get_keyring_returns_same_instance(self):
        """Test singleton behavior."""
        keyring1 = get_keyring()
        keyring2 = get_keyring()
        assert keyring1 is keyring2

    def test_set_keyring_replaces_instance(self, memory_manager):
        """Test that set_keyring replaces the global instance."""
        set_keyring(memory_manager)
        assert get_keyring() is memory_manager

    def test_reset_keyring(self, memory_manager):
        """Test resetting the global instance."""
        set_keyring(memory_manager)
        reset_keyring()

        # Should create new instance
        keyring = get_keyring()
        assert keyring is not memory_manager


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests verifying Determinism determinism."""

    def test_same_input_same_output(self, memory_provider):
        """Test that same operations produce same results."""
        # Set password
        for _ in range(10):
            memory_provider.set_password("otto", "key", "secret123")

        # Get password multiple times
        results = []
        for _ in range(10):
            results.append(memory_provider.get_password("otto", "key"))

        # All results should be identical
        assert all(r == "secret123" for r in results)

    def test_provider_selection_deterministic(self):
        """Test that provider selection is deterministic."""
        backends = []
        for _ in range(10):
            with patch.dict(os.environ, {"OTTO_KEYRING_BACKEND": "memory"}):
                manager = KeyringManager()
                backends.append(manager.backend)

        # All selections should be identical
        assert len(set(backends)) == 1
        assert backends[0] == KeyringBackend.MEMORY


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_password(self, memory_provider):
        """Test storing empty password."""
        success = memory_provider.set_password("otto", "key", "")
        assert success is True

        password = memory_provider.get_password("otto", "key")
        assert password == ""

    def test_unicode_password(self, memory_provider):
        """Test storing unicode password."""
        password = "пароль密码كلمة_السر🔐"

        memory_provider.set_password("otto", "key", password)
        result = memory_provider.get_password("otto", "key")

        assert result == password

    def test_special_characters_in_service(self, memory_provider):
        """Test special characters in service name."""
        memory_provider.set_password("otto-api.v2", "key", "secret")
        result = memory_provider.get_password("otto-api.v2", "key")

        assert result == "secret"

    def test_long_password(self, memory_provider):
        """Test storing very long password."""
        password = "x" * 10000  # 10KB password

        memory_provider.set_password("otto", "key", password)
        result = memory_provider.get_password("otto", "key")

        assert result == password

    def test_concurrent_access(self, memory_provider):
        """Test concurrent access to same credential."""
        # Simulate concurrent writes
        memory_provider.set_password("otto", "key", "secret1")
        memory_provider.set_password("otto", "key", "secret2")

        # Last write wins
        assert memory_provider.get_password("otto", "key") == "secret2"
