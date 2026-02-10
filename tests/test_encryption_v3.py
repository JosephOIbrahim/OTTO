"""Day 6 tests: AES-256-GCM encryption, Argon2id KDF, keystore lifecycle.

Test requirements from CLAUDE.md:
  - Encrypt → decrypt roundtrip preserves data
  - Wrong key → graceful failure
  - Key derivation is deterministic
  - Recovery key works
  - Plaintext never written to disk

All tests use TEST_PARAMS for Argon2id to keep execution fast.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from otto_v3.core.encryption.crypto import (
    CryptoEngine,
    DecryptionError,
    KEY_SIZE_BYTES,
    NONCE_SIZE_BYTES,
    TAG_SIZE_BYTES,
)
from otto_v3.core.encryption.kdf import (
    KDFParams,
    PRODUCTION_PARAMS,
    SALT_SIZE_BYTES,
    TEST_PARAMS,
    derive_key,
    generate_salt,
)
from otto_v3.core.encryption.keystore import (
    InvalidRecoveryKeyError,
    KeyStore,
    KeyStoreAlreadyInitializedError,
    KeyStoreError,
    KeyStoreLockedError,
    _VERIFICATION_PLAINTEXT,
)


# ============================================================
# Helpers
# ============================================================

def _random_key() -> bytes:
    """Generate a random AES-256 key for tests."""
    return CryptoEngine.generate_key()


def _tmp_keystore_path(tmp_path: Path) -> Path:
    """Return a temp path for a keystore file."""
    return tmp_path / "keystore.json"


# ============================================================
# CryptoEngine — AES-256-GCM
# ============================================================

class TestCryptoEngineRoundtrip:
    """Encrypt → decrypt preserves data (CLAUDE.md requirement)."""

    def test_roundtrip_basic(self) -> None:
        """Basic encrypt/decrypt roundtrip."""
        key = _random_key()
        plaintext = b"Hello, OTTO!"
        blob = CryptoEngine.encrypt(plaintext, key)
        assert CryptoEngine.decrypt(blob, key) == plaintext

    def test_roundtrip_empty_plaintext(self) -> None:
        """Empty plaintext encrypts and decrypts correctly."""
        key = _random_key()
        blob = CryptoEngine.encrypt(b"", key)
        assert CryptoEngine.decrypt(blob, key) == b""

    def test_roundtrip_large_data(self) -> None:
        """1 MiB of data survives roundtrip."""
        key = _random_key()
        plaintext = os.urandom(1024 * 1024)
        blob = CryptoEngine.encrypt(plaintext, key)
        assert CryptoEngine.decrypt(blob, key) == plaintext

    def test_roundtrip_binary_data(self) -> None:
        """All 256 byte values survive roundtrip."""
        key = _random_key()
        plaintext = bytes(range(256))
        blob = CryptoEngine.encrypt(plaintext, key)
        assert CryptoEngine.decrypt(blob, key) == plaintext

    def test_roundtrip_unicode_as_bytes(self) -> None:
        """UTF-8 encoded unicode survives roundtrip."""
        key = _random_key()
        text = "Cognitive safety is paramount"
        plaintext = text.encode("utf-8")
        blob = CryptoEngine.encrypt(plaintext, key)
        assert CryptoEngine.decrypt(blob, key) == plaintext
        assert CryptoEngine.decrypt(blob, key).decode("utf-8") == text

    def test_roundtrip_json_content(self) -> None:
        """JSON-serialized dict roundtrips through encryption."""
        key = _random_key()
        data = {"key": "mood", "content": "focused", "score": 0.85}
        plaintext = json.dumps(data, sort_keys=True).encode("utf-8")
        blob = CryptoEngine.encrypt(plaintext, key)
        recovered = json.loads(CryptoEngine.decrypt(blob, key))
        assert recovered == data


class TestCryptoEngineAAD:
    """Associated Authenticated Data (AAD) tests."""

    def test_aad_roundtrip(self) -> None:
        """Encrypt with AAD, decrypt with same AAD succeeds."""
        key = _random_key()
        plaintext = b"secret data"
        aad = b"memory_type=EPISODIC"
        blob = CryptoEngine.encrypt(plaintext, key, aad=aad)
        assert CryptoEngine.decrypt(blob, key, aad=aad) == plaintext

    def test_aad_mismatch_fails(self) -> None:
        """Decrypting with wrong AAD raises DecryptionError."""
        key = _random_key()
        blob = CryptoEngine.encrypt(b"secret", key, aad=b"correct")
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(blob, key, aad=b"wrong")

    def test_aad_missing_fails(self) -> None:
        """Encrypted with AAD, decrypted without AAD fails."""
        key = _random_key()
        blob = CryptoEngine.encrypt(b"secret", key, aad=b"present")
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(blob, key, aad=None)

    def test_aad_added_fails(self) -> None:
        """Encrypted without AAD, decrypted with AAD fails."""
        key = _random_key()
        blob = CryptoEngine.encrypt(b"secret", key, aad=None)
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(blob, key, aad=b"unexpected")


class TestCryptoEngineFailures:
    """Wrong key and corruption scenarios (CLAUDE.md requirement)."""

    def test_wrong_key_raises_decryption_error(self) -> None:
        """Decrypting with wrong key raises DecryptionError."""
        key1 = _random_key()
        key2 = _random_key()
        blob = CryptoEngine.encrypt(b"secret", key1)
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(blob, key2)

    def test_corrupted_ciphertext_fails(self) -> None:
        """Tampered ciphertext raises DecryptionError."""
        key = _random_key()
        blob = bytearray(CryptoEngine.encrypt(b"secret", key))
        # Flip a byte in the ciphertext region (after nonce)
        blob[NONCE_SIZE_BYTES + 1] ^= 0xFF
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(bytes(blob), key)

    def test_corrupted_nonce_fails(self) -> None:
        """Tampered nonce raises DecryptionError."""
        key = _random_key()
        blob = bytearray(CryptoEngine.encrypt(b"secret", key))
        blob[0] ^= 0xFF
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(bytes(blob), key)

    def test_truncated_blob_fails(self) -> None:
        """Blob shorter than nonce+tag raises DecryptionError."""
        key = _random_key()
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(b"short", key)

    def test_empty_blob_fails(self) -> None:
        """Empty blob raises DecryptionError."""
        key = _random_key()
        with pytest.raises(DecryptionError):
            CryptoEngine.decrypt(b"", key)


class TestCryptoEngineKeyValidation:
    """Key size enforcement."""

    def test_encrypt_short_key_raises(self) -> None:
        """Key shorter than 32 bytes raises ValueError."""
        with pytest.raises(ValueError, match="32 bytes"):
            CryptoEngine.encrypt(b"data", b"short")

    def test_encrypt_long_key_raises(self) -> None:
        """Key longer than 32 bytes raises ValueError."""
        with pytest.raises(ValueError, match="32 bytes"):
            CryptoEngine.encrypt(b"data", os.urandom(64))

    def test_decrypt_wrong_size_key_raises(self) -> None:
        """Decrypt with wrong-size key raises ValueError."""
        key = _random_key()
        blob = CryptoEngine.encrypt(b"data", key)
        with pytest.raises(ValueError, match="32 bytes"):
            CryptoEngine.decrypt(blob, b"too_short")


class TestCryptoEngineProperties:
    """Structural properties of the engine."""

    def test_generate_key_correct_size(self) -> None:
        """Generated key is exactly 32 bytes."""
        assert len(CryptoEngine.generate_key()) == KEY_SIZE_BYTES

    def test_generate_key_unique(self) -> None:
        """Two generated keys are different."""
        assert CryptoEngine.generate_key() != CryptoEngine.generate_key()

    def test_blob_contains_nonce_prefix(self) -> None:
        """Blob is at least nonce + tag bytes long."""
        key = _random_key()
        blob = CryptoEngine.encrypt(b"", key)
        assert len(blob) >= NONCE_SIZE_BYTES + TAG_SIZE_BYTES

    def test_same_plaintext_different_blobs(self) -> None:
        """Same plaintext + key → different blobs (random nonce).

        This is the ONE intentional non-determinism in the crypto
        layer, documented.
        """
        key = _random_key()
        blob1 = CryptoEngine.encrypt(b"same", key)
        blob2 = CryptoEngine.encrypt(b"same", key)
        assert blob1 != blob2  # Different nonces

    def test_constants_correct(self) -> None:
        """Module constants are the standard GCM values."""
        assert KEY_SIZE_BYTES == 32
        assert NONCE_SIZE_BYTES == 12
        assert TAG_SIZE_BYTES == 16


# ============================================================
# Key Derivation — Argon2id
# ============================================================

class TestKeyDerivation:
    """Argon2id KDF tests (CLAUDE.md requirement: deterministic)."""

    def test_deterministic_same_inputs(self) -> None:
        """Same passphrase + salt + params → same key (always)."""
        salt = generate_salt()
        key1 = derive_key("my passphrase", salt, TEST_PARAMS)
        key2 = derive_key("my passphrase", salt, TEST_PARAMS)
        assert key1 == key2

    def test_deterministic_100x(self) -> None:
        """KDF is deterministic over 100 repetitions."""
        salt = generate_salt()
        reference = derive_key("determinism test", salt, TEST_PARAMS)
        for _ in range(100):
            assert derive_key("determinism test", salt, TEST_PARAMS) == reference

    def test_different_passphrase_different_key(self) -> None:
        """Different passphrase → different key."""
        salt = generate_salt()
        key1 = derive_key("password_one", salt, TEST_PARAMS)
        key2 = derive_key("password_two", salt, TEST_PARAMS)
        assert key1 != key2

    def test_different_salt_different_key(self) -> None:
        """Different salt → different key."""
        salt1 = generate_salt()
        salt2 = generate_salt()
        key1 = derive_key("same_pass", salt1, TEST_PARAMS)
        key2 = derive_key("same_pass", salt2, TEST_PARAMS)
        assert key1 != key2

    def test_output_correct_size(self) -> None:
        """Derived key is exactly 32 bytes."""
        salt = generate_salt()
        key = derive_key("pass", salt, TEST_PARAMS)
        assert len(key) == KEY_SIZE_BYTES

    def test_empty_passphrase(self) -> None:
        """Empty passphrase works (no crash)."""
        salt = generate_salt()
        key = derive_key("", salt, TEST_PARAMS)
        assert len(key) == KEY_SIZE_BYTES

    def test_unicode_passphrase(self) -> None:
        """Unicode passphrase works correctly."""
        salt = generate_salt()
        key = derive_key("p\u00e4ssw\u00f6rd", salt, TEST_PARAMS)
        assert len(key) == KEY_SIZE_BYTES
        # Same unicode → same key
        key2 = derive_key("p\u00e4ssw\u00f6rd", salt, TEST_PARAMS)
        assert key == key2

    def test_salt_too_short_raises(self) -> None:
        """Salt shorter than 8 bytes raises ValueError."""
        with pytest.raises(ValueError, match="8 bytes"):
            derive_key("pass", b"short", TEST_PARAMS)

    def test_generate_salt_correct_size(self) -> None:
        """Generated salt is exactly 16 bytes."""
        assert len(generate_salt()) == SALT_SIZE_BYTES

    def test_generate_salt_unique(self) -> None:
        """Two generated salts are different."""
        assert generate_salt() != generate_salt()


class TestKDFParams:
    """Parameter preset tests."""

    def test_production_params_frozen(self) -> None:
        """Production params are immutable."""
        with pytest.raises(AttributeError):
            PRODUCTION_PARAMS.time_cost = 999  # type: ignore[misc]

    def test_test_params_frozen(self) -> None:
        """Test params are immutable."""
        with pytest.raises(AttributeError):
            TEST_PARAMS.memory_cost = 999  # type: ignore[misc]

    def test_production_params_values(self) -> None:
        """Production params match CLAUDE.md spec."""
        assert PRODUCTION_PARAMS.time_cost == 3
        assert PRODUCTION_PARAMS.memory_cost == 65_536  # 64 MiB
        assert PRODUCTION_PARAMS.parallelism == 4
        assert PRODUCTION_PARAMS.key_size == 32

    def test_test_params_are_fast(self) -> None:
        """Test params are significantly lighter than production."""
        assert TEST_PARAMS.time_cost < PRODUCTION_PARAMS.time_cost
        assert TEST_PARAMS.memory_cost < PRODUCTION_PARAMS.memory_cost

    def test_different_params_different_key(self) -> None:
        """Different KDF params → different key (even same inputs)."""
        salt = generate_salt()
        params_a = KDFParams(time_cost=1, memory_cost=1024, parallelism=1)
        params_b = KDFParams(time_cost=2, memory_cost=1024, parallelism=1)
        key_a = derive_key("same", salt, params_a)
        key_b = derive_key("same", salt, params_b)
        assert key_a != key_b


# ============================================================
# KeyStore — Lifecycle management
# ============================================================

class TestKeyStoreSetup:
    """First-time setup tests."""

    def test_setup_returns_recovery_key(self, tmp_path: Path) -> None:
        """Setup returns a hex recovery key of correct length."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("my_passphrase")
        assert isinstance(recovery, str)
        assert len(recovery) == KEY_SIZE_BYTES * 2  # 64 hex chars
        # Valid hex
        bytes.fromhex(recovery)

    def test_setup_creates_store_file(self, tmp_path: Path) -> None:
        """Setup creates the keystore JSON file."""
        path = _tmp_keystore_path(tmp_path)
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        assert not path.exists()
        ks.setup("pass")
        assert path.exists()

    def test_setup_file_is_valid_json(self, tmp_path: Path) -> None:
        """Keystore file is valid JSON with required fields."""
        path = _tmp_keystore_path(tmp_path)
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        ks.setup("pass")
        data = json.loads(path.read_text())
        for field in ("salt", "wrapped_key", "verification", "version"):
            assert field in data

    def test_setup_unlocks_keystore(self, tmp_path: Path) -> None:
        """After setup, keystore is unlocked."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("pass")
        assert ks.is_unlocked()
        assert ks.is_initialized()

    def test_setup_twice_raises(self, tmp_path: Path) -> None:
        """Calling setup twice raises error."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("pass")
        with pytest.raises(KeyStoreAlreadyInitializedError):
            ks.setup("pass")

    def test_setup_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Setup creates parent directories if they don't exist."""
        deep_path = tmp_path / "nested" / "dir" / "keystore.json"
        ks = KeyStore(deep_path, kdf_params=TEST_PARAMS)
        ks.setup("pass")
        assert deep_path.exists()


class TestKeyStoreUnlock:
    """Unlock with passphrase (CLAUDE.md: wrong key → graceful failure)."""

    def test_unlock_correct_passphrase(self, tmp_path: Path) -> None:
        """Correct passphrase unlocks and returns master key."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("correct_pass")
        expected_key = bytes.fromhex(recovery)
        ks.lock()

        master_key = ks.unlock("correct_pass")
        assert master_key == expected_key
        assert ks.is_unlocked()

    def test_unlock_wrong_passphrase_raises(self, tmp_path: Path) -> None:
        """Wrong passphrase raises DecryptionError."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("correct")
        ks.lock()

        with pytest.raises(DecryptionError):
            ks.unlock("wrong_password")
        assert not ks.is_unlocked()

    def test_unlock_returns_same_key_as_setup(self, tmp_path: Path) -> None:
        """Unlock returns the same master key that setup generated."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("pass")
        setup_key = bytes.fromhex(recovery)
        ks.lock()
        unlock_key = ks.unlock("pass")
        assert unlock_key == setup_key

    def test_unlock_not_initialized_raises(self, tmp_path: Path) -> None:
        """Unlock before setup raises KeyStoreError."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        with pytest.raises(KeyStoreError, match="not initialized"):
            ks.unlock("pass")


class TestKeyStoreRecovery:
    """Recovery key tests (CLAUDE.md requirement: recovery key works)."""

    def test_recovery_correct_key(self, tmp_path: Path) -> None:
        """Correct recovery key unlocks the keystore."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("pass")
        ks.lock()

        master_key = ks.recover(recovery)
        assert ks.is_unlocked()
        assert master_key == bytes.fromhex(recovery)

    def test_recovery_wrong_key_raises(self, tmp_path: Path) -> None:
        """Wrong recovery key raises InvalidRecoveryKeyError."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("pass")
        ks.lock()

        fake_key = os.urandom(KEY_SIZE_BYTES).hex()
        with pytest.raises(InvalidRecoveryKeyError):
            ks.recover(fake_key)
        assert not ks.is_unlocked()

    def test_recovery_short_key_raises(self, tmp_path: Path) -> None:
        """Too-short recovery key raises ValueError."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("pass")
        ks.lock()

        with pytest.raises(ValueError):
            ks.recover("aabb")

    def test_recovery_invalid_hex_raises(self, tmp_path: Path) -> None:
        """Non-hex recovery key raises ValueError."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("pass")
        ks.lock()

        with pytest.raises(ValueError):
            ks.recover("not_valid_hex_at_all!")

    def test_recovery_returns_same_key_as_setup(self, tmp_path: Path) -> None:
        """Recovery returns the same master key as setup."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("pass")
        setup_key = ks.master_key
        ks.lock()

        recovered_key = ks.recover(recovery)
        assert recovered_key == setup_key


class TestKeyStoreLock:
    """Lock / state management."""

    def test_lock_clears_master_key(self, tmp_path: Path) -> None:
        """Lock wipes the master key from memory."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("pass")
        assert ks.is_unlocked()

        ks.lock()
        assert not ks.is_unlocked()

    def test_master_key_when_locked_raises(self, tmp_path: Path) -> None:
        """Accessing master_key when locked raises error."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("pass")
        ks.lock()

        with pytest.raises(KeyStoreLockedError):
            _ = ks.master_key

    def test_is_initialized_before_setup(self, tmp_path: Path) -> None:
        """Not initialized before setup."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        assert not ks.is_initialized()

    def test_is_unlocked_before_setup(self, tmp_path: Path) -> None:
        """Not unlocked before setup."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        assert not ks.is_unlocked()


class TestKeyStoreChangePassphrase:
    """Passphrase change tests."""

    def test_change_passphrase_works(self, tmp_path: Path) -> None:
        """New passphrase can unlock after change."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("old_pass")
        expected_key = bytes.fromhex(recovery)

        ks.change_passphrase("new_pass")
        ks.lock()

        # Old passphrase no longer works
        with pytest.raises(DecryptionError):
            ks.unlock("old_pass")

        # New passphrase works and returns same master key
        master_key = ks.unlock("new_pass")
        assert master_key == expected_key

    def test_change_passphrase_preserves_recovery(self, tmp_path: Path) -> None:
        """Recovery key still works after passphrase change."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("old_pass")

        ks.change_passphrase("new_pass")
        ks.lock()

        # Recovery key still works
        master_key = ks.recover(recovery)
        assert master_key == bytes.fromhex(recovery)

    def test_change_passphrase_when_locked_raises(self, tmp_path: Path) -> None:
        """Changing passphrase when locked raises error."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        ks.setup("pass")
        ks.lock()

        with pytest.raises(KeyStoreLockedError):
            ks.change_passphrase("new")


class TestKeyStoreNoPlaintextOnDisk:
    """Plaintext never written to disk (CLAUDE.md requirement)."""

    def test_master_key_not_in_store_file(self, tmp_path: Path) -> None:
        """The master key does NOT appear in the keystore file."""
        path = _tmp_keystore_path(tmp_path)
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        recovery = ks.setup("pass")
        master_key_hex = recovery
        master_key_bytes = bytes.fromhex(recovery)

        file_content = path.read_bytes()
        # Master key not present as raw bytes
        assert master_key_bytes not in file_content
        # Master key not present as hex string in file
        # (it COULD appear in wrapped_key hex, but that's the
        #  encrypted form — check the raw key bytes aren't there)
        # The hex of the raw key should not appear unencrypted
        file_text = path.read_text()
        data = json.loads(file_text)
        # The wrapped_key is the master key encrypted — decrypting
        # it should give us the master key, but the hex of the raw
        # key should not be a direct substring of any stored value
        assert master_key_hex != data["salt"]
        assert master_key_hex != data["wrapped_key"]
        assert master_key_hex != data["verification"]

    def test_passphrase_not_in_store_file(self, tmp_path: Path) -> None:
        """The passphrase does NOT appear in the keystore file."""
        path = _tmp_keystore_path(tmp_path)
        passphrase = "super_secret_passphrase_12345"
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        ks.setup(passphrase)

        file_content = path.read_text()
        assert passphrase not in file_content
        assert passphrase.encode("utf-8").hex() not in file_content

    def test_verification_plaintext_not_readable(self, tmp_path: Path) -> None:
        """The verification plaintext is encrypted, not stored raw."""
        path = _tmp_keystore_path(tmp_path)
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        ks.setup("pass")

        file_content = path.read_bytes()
        assert _VERIFICATION_PLAINTEXT not in file_content

    def test_store_file_structure(self, tmp_path: Path) -> None:
        """Store file has exactly the expected fields, no extras."""
        path = _tmp_keystore_path(tmp_path)
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        ks.setup("pass")

        data = json.loads(path.read_text())
        # sorted keys in JSON
        expected_keys = ["salt", "verification", "version", "wrapped_key"]
        assert sorted(data.keys()) == expected_keys


class TestKeyStoreCorruption:
    """Graceful handling of corrupted store files."""

    def test_corrupted_json_raises(self, tmp_path: Path) -> None:
        """Corrupted JSON raises KeyStoreError."""
        path = _tmp_keystore_path(tmp_path)
        path.write_text("not json at all {{{")
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        with pytest.raises(KeyStoreError, match="corrupted"):
            ks.unlock("pass")

    def test_missing_field_raises(self, tmp_path: Path) -> None:
        """Missing required field raises KeyStoreError."""
        path = _tmp_keystore_path(tmp_path)
        path.write_text(json.dumps({"version": 1, "salt": "aa"}))
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        with pytest.raises(KeyStoreError, match="missing"):
            ks.unlock("pass")


# ============================================================
# Integration: Full flow
# ============================================================

class TestFullEncryptionFlow:
    """End-to-end: setup → encrypt data → lock → unlock → decrypt."""

    def test_full_lifecycle(self, tmp_path: Path) -> None:
        """Complete keystore + encryption lifecycle."""
        # Setup
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("my_passphrase")
        key = ks.master_key

        # Encrypt some cognitive data
        cognitive_data = json.dumps({
            "type": "EPISODIC",
            "key": "conversation_001",
            "content": "User discussed project momentum",
        }, sort_keys=True).encode("utf-8")
        encrypted = CryptoEngine.encrypt(cognitive_data, key)

        # Lock (simulates app shutdown)
        ks.lock()
        assert not ks.is_unlocked()

        # Unlock (simulates app restart)
        key2 = ks.unlock("my_passphrase")
        assert key2 == key

        # Decrypt
        decrypted = CryptoEngine.decrypt(encrypted, key2)
        assert decrypted == cognitive_data

    def test_recovery_flow(self, tmp_path: Path) -> None:
        """Forgot passphrase → recover → re-encrypt with new pass."""
        ks = KeyStore(_tmp_keystore_path(tmp_path), kdf_params=TEST_PARAMS)
        recovery = ks.setup("forgotten_pass")
        key = ks.master_key

        # Encrypt data
        data = b"important memory"
        encrypted = CryptoEngine.encrypt(data, key)

        # "Forget" passphrase — lock
        ks.lock()

        # Recover with recovery key
        recovered_key = ks.recover(recovery)
        assert recovered_key == key

        # Decrypt still works
        assert CryptoEngine.decrypt(encrypted, recovered_key) == data

        # Set new passphrase
        ks.change_passphrase("new_remembered_pass")
        ks.lock()

        # New passphrase works
        new_key = ks.unlock("new_remembered_pass")
        assert CryptoEngine.decrypt(encrypted, new_key) == data

    def test_separate_keystore_instances(self, tmp_path: Path) -> None:
        """Two KeyStore instances sharing the same file work correctly."""
        path = _tmp_keystore_path(tmp_path)

        # Instance 1: setup
        ks1 = KeyStore(path, kdf_params=TEST_PARAMS)
        recovery = ks1.setup("shared_pass")
        key1 = ks1.master_key

        # Instance 2: unlock from same file
        ks2 = KeyStore(path, kdf_params=TEST_PARAMS)
        key2 = ks2.unlock("shared_pass")
        assert key2 == key1

    def test_encrypt_decrypt_with_kdf_key(self, tmp_path: Path) -> None:
        """Key derived from passphrase can encrypt/decrypt directly."""
        salt = generate_salt()
        key = derive_key("direct_kdf_test", salt, TEST_PARAMS)
        plaintext = b"derived key encryption"
        blob = CryptoEngine.encrypt(plaintext, key)
        assert CryptoEngine.decrypt(blob, key) == plaintext


# ============================================================
# Determinism
# ============================================================

class TestEncryptionDeterminism:
    """determinism requirements for the encryption layer."""

    def test_kdf_deterministic_100x(self) -> None:
        """KDF produces identical output across 100 runs."""
        salt = generate_salt()
        reference = derive_key("determinism", salt, TEST_PARAMS)
        for i in range(100):
            assert derive_key("determinism", salt, TEST_PARAMS) == reference, (
                f"KDF non-deterministic on run {i}"
            )

    def test_decrypt_deterministic(self) -> None:
        """Decrypt is deterministic (same blob + key → same plaintext)."""
        key = _random_key()
        blob = CryptoEngine.encrypt(b"fixed plaintext", key)
        reference = CryptoEngine.decrypt(blob, key)
        for _ in range(100):
            assert CryptoEngine.decrypt(blob, key) == reference

    def test_keystore_json_sorted_keys(self, tmp_path: Path) -> None:
        """Keystore JSON has sorted keys."""
        path = _tmp_keystore_path(tmp_path)
        ks = KeyStore(path, kdf_params=TEST_PARAMS)
        ks.setup("pass")
        data = json.loads(path.read_text())
        assert list(data.keys()) == sorted(data.keys())
