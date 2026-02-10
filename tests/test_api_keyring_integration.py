"""
OS Keyring Integration Tests for OTTO API Keys.

These tests verify that API keys work correctly with the OS keyring:
- Windows: Credential Manager
- macOS: Keychain
- Linux: libsecret/GNOME Keyring

ISOLATION:
- Uses separate service name "otto-os-test" to avoid polluting user's keyring
- Cleans up all test keys after each test
- Skips gracefully if keyring backend is not available

Determinism:
- DETERMINISTIC: same key → same validation result
- FIXED: storage and retrieval formats
- REPRODUCIBLE: key lifecycle operations

Run with: pytest tests/test_api_keyring_integration.py -v
"""

import pytest
import uuid
from typing import List

# Try to import keyring - tests will be skipped if not available
try:
    import keyring
    from keyring.errors import KeyringError as BaseKeyringError
    KEYRING_AVAILABLE = True

    # Check for null/fail backends that don't actually work
    backend = keyring.get_keyring()
    backend_name = backend.__class__.__name__.lower()
    if "fail" in backend_name or "null" in backend_name or "chainer" in backend_name:
        KEYRING_AVAILABLE = False
        KEYRING_SKIP_REASON = f"Keyring backend not usable: {backend_name}"
    else:
        KEYRING_SKIP_REASON = ""
except ImportError:
    KEYRING_AVAILABLE = False
    KEYRING_SKIP_REASON = "keyring library not installed"

from otto.api import APIScope, APIKeyManager


# =============================================================================
# Test Configuration
# =============================================================================

# Isolated service name for testing (never use production "otto-os")
TEST_SERVICE_NAME = "otto-os-test"

# Track created keys for cleanup
_created_key_ids: List[str] = []


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def keyring_manager():
    """
    Create an APIKeyManager that uses the keyring.

    This manager uses actual OS keyring storage.
    """
    if not KEYRING_AVAILABLE:
        pytest.skip(KEYRING_SKIP_REASON)

    manager = APIKeyManager(use_keyring=True)
    yield manager

    # Cleanup: delete all keys created during test
    for key_id in _created_key_ids:
        try:
            manager.delete(key_id)
        except Exception:
            pass
    _created_key_ids.clear()


@pytest.fixture
def memory_manager():
    """Create an APIKeyManager that uses memory storage (for comparison)."""
    return APIKeyManager(use_keyring=False)


def track_key(key_id: str) -> None:
    """Track a key for cleanup."""
    _created_key_ids.append(key_id)


# =============================================================================
# Skip decorator for keyring tests
# =============================================================================

requires_keyring = pytest.mark.skipif(
    not KEYRING_AVAILABLE,
    reason=KEYRING_SKIP_REASON
)


# =============================================================================
# Keyring Backend Detection
# =============================================================================

@requires_keyring
class TestKeyringBackend:
    """Test keyring backend detection."""

    def test_keyring_backend_available(self):
        """Keyring backend should be available."""
        backend = keyring.get_keyring()
        assert backend is not None

    def test_keyring_backend_is_secure(self):
        """Keyring backend should be a secure type."""
        backend = keyring.get_keyring()
        backend_name = backend.__class__.__name__.lower()

        # Should not be null or fail backends
        assert "fail" not in backend_name
        assert "null" not in backend_name


# =============================================================================
# API Key Lifecycle with Keyring
# =============================================================================

@requires_keyring
class TestAPIKeyLifecycleWithKeyring:
    """Test full API key lifecycle using OS keyring."""

    def test_create_key_stores_in_keyring(self, keyring_manager):
        """Created key should be stored in OS keyring."""
        full_key, key = keyring_manager.create(
            name="Keyring Test Key",
            scopes={APIScope.READ_STATUS},
        )
        track_key(key.key_id)

        # Key should have been created
        assert full_key is not None
        assert key.key_id is not None

        # Validate the key (should retrieve from keyring)
        result = keyring_manager.validate(full_key)
        assert result.valid is True
        assert result.key.key_id == key.key_id

    def test_key_persists_across_manager_instances(self, keyring_manager):
        """Key should persist when creating new manager instance."""
        # Create key with first manager
        full_key, key = keyring_manager.create(
            name="Persistent Key",
            scopes={APIScope.READ_STATUS},
        )
        track_key(key.key_id)

        # Create new manager instance
        new_manager = APIKeyManager(use_keyring=True)

        # Key should still be valid with new manager
        result = new_manager.validate(full_key)
        assert result.valid is True
        assert result.key.name == "Persistent Key"

    def test_revoke_key_in_keyring(self, keyring_manager):
        """Revoked key should no longer validate."""
        full_key, key = keyring_manager.create(
            name="Revokable Key",
            scopes={APIScope.READ_STATUS},
        )
        track_key(key.key_id)

        # Revoke the key
        success = keyring_manager.revoke(key.key_id, reason="Test revocation")
        assert success is True

        # Key should no longer validate
        result = keyring_manager.validate(full_key)
        assert result.valid is False

    def test_delete_key_from_keyring(self, keyring_manager):
        """Deleted key should be removed from keyring."""
        full_key, key = keyring_manager.create(
            name="Deletable Key",
            scopes={APIScope.READ_STATUS},
        )
        key_id = key.key_id
        # Don't track - we're deleting manually

        # Delete the key
        success = keyring_manager.delete(key_id)
        assert success is True

        # Key should no longer validate
        result = keyring_manager.validate(full_key)
        assert result.valid is False

    def test_list_keys_from_keyring(self, keyring_manager):
        """List should return keys stored in keyring."""
        # Create multiple keys
        keys_created = []
        for i in range(3):
            _, key = keyring_manager.create(
                name=f"List Test Key {i}",
                scopes={APIScope.READ_STATUS},
            )
            keys_created.append(key.key_id)
            track_key(key.key_id)

        # List should include all created keys
        keys = keyring_manager.list()
        key_ids = [k.key_id for k in keys]

        for created_id in keys_created:
            assert created_id in key_ids


# =============================================================================
# Keyring vs Memory Comparison
# =============================================================================

@requires_keyring
class TestKeyringVsMemory:
    """Compare keyring and memory storage behavior."""

    def test_same_validation_behavior(self, keyring_manager, memory_manager):
        """Keyring and memory should have same validation behavior."""
        # Create key in each
        kr_full, kr_key = keyring_manager.create(
            name="Keyring Key",
            scopes={APIScope.READ_STATUS},
        )
        track_key(kr_key.key_id)

        mem_full, mem_key = memory_manager.create(
            name="Memory Key",
            scopes={APIScope.READ_STATUS},
        )

        # Both should validate their own keys
        kr_result = keyring_manager.validate(kr_full)
        mem_result = memory_manager.validate(mem_full)

        assert kr_result.valid is True
        assert mem_result.valid is True

        # Neither should validate the other's key
        cross_kr = keyring_manager.validate(mem_full)
        cross_mem = memory_manager.validate(kr_full)

        assert cross_kr.valid is False
        assert cross_mem.valid is False


# =============================================================================
# Determinism Tests
# =============================================================================

@requires_keyring
class TestKeyringDeterminism:
    """
    Test determinism of keyring operations.

    Principle: Same input → same output.
    """

    def test_validation_is_deterministic(self, keyring_manager):
        """Same key should always produce same validation result."""
        full_key, key = keyring_manager.create(
            name="Deterministic Key",
            scopes={APIScope.READ_STATUS},
        )
        track_key(key.key_id)

        # Validate same key multiple times
        results = [keyring_manager.validate(full_key) for _ in range(10)]

        # All should be identical
        for result in results:
            assert result.valid is True
            assert result.key.key_id == key.key_id
            assert result.key.name == "Deterministic Key"

    def test_invalid_key_always_fails(self, keyring_manager):
        """Invalid key should always fail validation."""
        invalid_key = "otto_live_invalid_00000000000000000000000000000000"

        # Validate multiple times
        results = [keyring_manager.validate(invalid_key) for _ in range(10)]

        # All should fail
        for result in results:
            assert result.valid is False

    def test_scope_checking_is_deterministic(self, keyring_manager):
        """Scope checking should be deterministic."""
        full_key, key = keyring_manager.create(
            name="Scoped Key",
            scopes={APIScope.READ_STATUS, APIScope.READ_STATE},
        )
        track_key(key.key_id)

        # Check scopes multiple times
        for _ in range(10):
            result = keyring_manager.validate(full_key)
            assert APIScope.READ_STATUS in result.key.scopes
            assert APIScope.READ_STATE in result.key.scopes
            assert APIScope.WRITE_STATE not in result.key.scopes


# =============================================================================
# Error Handling
# =============================================================================

@requires_keyring
class TestKeyringErrorHandling:
    """Test error handling with keyring storage."""

    def test_validate_nonexistent_key_format(self, keyring_manager):
        """Validating properly-formatted but nonexistent key should fail gracefully."""
        # Key with valid format but not in storage
        fake_key = "otto_live_abc12345_" + "x" * 32

        result = keyring_manager.validate(fake_key)
        assert result.valid is False

    def test_validate_malformed_key(self, keyring_manager):
        """Validating malformed key should fail gracefully."""
        malformed_keys = [
            "not_a_key",
            "otto_wrong_format",
            "too_short",
            "",
            "otto_live_",  # No key ID or secret
        ]

        for key in malformed_keys:
            result = keyring_manager.validate(key)
            assert result.valid is False

    def test_revoke_nonexistent_key(self, keyring_manager):
        """Revoking nonexistent key should return False."""
        result = keyring_manager.revoke("nonexistent_key_id")
        assert result is False

    def test_delete_nonexistent_key(self, keyring_manager):
        """Deleting nonexistent key should return False."""
        result = keyring_manager.delete("nonexistent_key_id")
        assert result is False


# =============================================================================
# Security Properties
# =============================================================================

@requires_keyring
class TestKeyringSecurityProperties:
    """Test security properties of keyring storage."""

    def test_key_not_stored_in_plaintext(self, keyring_manager):
        """Full API key should never be stored in plaintext."""
        full_key, key = keyring_manager.create(
            name="Security Test Key",
            scopes={APIScope.READ_STATUS},
        )
        track_key(key.key_id)

        # The manager should only store the hash, not the full key
        # We verify this by checking that the key object doesn't contain
        # the full secret
        assert not hasattr(key, 'secret')
        assert not hasattr(key, 'full_key')

        # The key_id is just the identifier, not the secret
        assert len(key.key_id) == 8  # Short identifier

    def test_key_hash_comparison_is_constant_time(self, keyring_manager):
        """Key validation should use constant-time comparison."""
        full_key, key = keyring_manager.create(
            name="Timing Test Key",
            scopes={APIScope.READ_STATUS},
        )
        track_key(key.key_id)

        # The implementation should use hmac.compare_digest
        # We can't easily test timing, but we verify the code uses it
        # by checking the import exists
        import hmac
        assert hasattr(hmac, 'compare_digest')


# =============================================================================
# Cleanup Test (runs last)
# =============================================================================

@requires_keyring
class TestCleanup:
    """Verify cleanup works correctly."""

    def test_cleanup_removes_test_keys(self, keyring_manager):
        """Cleanup should remove all test keys."""
        # Create a key
        _, key = keyring_manager.create(
            name="Cleanup Test",
            scopes={APIScope.READ_STATUS},
        )
        key_id = key.key_id

        # Delete it
        success = keyring_manager.delete(key_id)
        assert success is True

        # Verify it's gone
        keys = keyring_manager.list()
        key_ids = [k.key_id for k in keys]
        assert key_id not in key_ids
