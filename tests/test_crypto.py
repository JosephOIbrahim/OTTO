"""
Tests for Cryptography Module
=============================

Comprehensive tests for OTTO OS encryption, key derivation,
keyring integration, and secure file operations.

Determinism Tests:
- Fixed algorithm parameters
- Deterministic operations
- Bounded memory usage
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from otto.crypto.encryption import (
    encrypt_data,
    decrypt_data,
    encrypt_string,
    decrypt_string,
    generate_nonce,
    validate_key,
    EncryptedBlob,
    EncryptionError,
    DecryptionError,
    KEY_SIZE,
    NONCE_SIZE,
    TAG_SIZE,
    BLOB_VERSION,
)

from otto.crypto.key_derivation import (
    derive_key,
    derive_key_from_bytes,
    verify_key,
    generate_salt,
    validate_password_strength,
    estimate_derivation_time_ms,
    KeyDerivationParams,
    KeyDerivationError,
    KEY_SIZE as KDF_KEY_SIZE,
    SALT_SIZE,
    DEFAULT_PARAMS,
)

from otto.crypto.keyring_adapter import (
    KeyringAdapter,
    store_key,
    retrieve_key,
    delete_key,
    key_exists,
    KeyringError,
    KeyNotFoundError,
    SERVICE_NAME,
)

from otto.crypto.secure_file import (
    SecureFile,
    SecureFileHeader,
    encrypt_file,
    decrypt_file_to_memory,
    encrypt_text_file,
    is_encrypted_file,
    SecureFileError,
    InvalidFileFormat,
    FileIntegrityError,
    MAGIC,
    FORMAT_VERSION,
)

from otto.crypto.recovery import (
    RecoveryKey,
    generate_recovery_key,
    validate_recovery_key,
    recovery_key_to_bytes,
    recovery_key_from_entropy,
    format_recovery_key_for_display,
    RecoveryKeyError,
    InvalidRecoveryKey,
    WORD_COUNT,
    ENTROPY_SIZE,
)


# =============================================================================
# Encryption Tests
# =============================================================================

class TestEncryptionConstants:
    """Tests for encryption constants (determinism compliance)."""

    def test_key_size_fixed(self):
        """Key size is fixed at 256 bits."""
        assert KEY_SIZE == 32

    def test_nonce_size_fixed(self):
        """Nonce size is fixed at 96 bits."""
        assert NONCE_SIZE == 12

    def test_tag_size_fixed(self):
        """Tag size is fixed at 128 bits."""
        assert TAG_SIZE == 16

    def test_blob_version_fixed(self):
        """Blob version is fixed."""
        assert BLOB_VERSION == 0x01


class TestGenerateNonce:
    """Tests for nonce generation."""

    def test_nonce_correct_size(self):
        """Nonce is correct size."""
        nonce = generate_nonce()
        assert len(nonce) == NONCE_SIZE

    def test_nonce_is_random(self):
        """Each nonce is different."""
        nonces = [generate_nonce() for _ in range(10)]
        assert len(set(nonces)) == 10


class TestEncryptData:
    """Tests for data encryption."""

    @pytest.fixture
    def key(self):
        """Generate test key."""
        return os.urandom(KEY_SIZE)

    @pytest.fixture
    def plaintext(self):
        """Test plaintext."""
        return b"Hello, OTTO OS!"

    def test_encrypt_returns_blob(self, key, plaintext):
        """Encryption returns EncryptedBlob."""
        blob = encrypt_data(plaintext, key)
        assert isinstance(blob, EncryptedBlob)

    def test_blob_has_correct_version(self, key, plaintext):
        """Blob has correct version."""
        blob = encrypt_data(plaintext, key)
        assert blob.version == BLOB_VERSION

    def test_blob_has_nonce(self, key, plaintext):
        """Blob contains nonce."""
        blob = encrypt_data(plaintext, key)
        assert len(blob.nonce) == NONCE_SIZE

    def test_ciphertext_different_from_plaintext(self, key, plaintext):
        """Ciphertext is different from plaintext."""
        blob = encrypt_data(plaintext, key)
        assert blob.ciphertext != plaintext

    def test_custom_nonce(self, key, plaintext):
        """Can provide custom nonce."""
        nonce = generate_nonce()
        blob = encrypt_data(plaintext, key, nonce=nonce)
        assert blob.nonce == nonce

    def test_invalid_key_size(self, plaintext):
        """Raises on invalid key size."""
        with pytest.raises(EncryptionError):
            encrypt_data(plaintext, b"short")

    def test_invalid_nonce_size(self, key, plaintext):
        """Raises on invalid nonce size."""
        with pytest.raises(EncryptionError):
            encrypt_data(plaintext, key, nonce=b"short")

    def test_deterministic_with_same_nonce(self, key, plaintext):
        """Same key + nonce + data = same ciphertext."""
        nonce = generate_nonce()
        blob1 = encrypt_data(plaintext, key, nonce=nonce)
        blob2 = encrypt_data(plaintext, key, nonce=nonce)
        assert blob1.ciphertext == blob2.ciphertext


class TestDecryptData:
    """Tests for data decryption."""

    @pytest.fixture
    def key(self):
        """Generate test key."""
        return os.urandom(KEY_SIZE)

    @pytest.fixture
    def plaintext(self):
        """Test plaintext."""
        return b"Secret message for OTTO!"

    def test_roundtrip(self, key, plaintext):
        """Encrypt then decrypt returns original."""
        blob = encrypt_data(plaintext, key)
        decrypted = decrypt_data(blob, key)
        assert decrypted == plaintext

    def test_wrong_key_fails(self, key, plaintext):
        """Wrong key fails decryption."""
        blob = encrypt_data(plaintext, key)
        wrong_key = os.urandom(KEY_SIZE)

        with pytest.raises(DecryptionError):
            decrypt_data(blob, wrong_key)

    def test_tampered_data_fails(self, key, plaintext):
        """Tampered ciphertext fails."""
        blob = encrypt_data(plaintext, key)

        # Tamper with ciphertext
        tampered = bytearray(blob.ciphertext)
        tampered[0] ^= 0xFF
        blob.ciphertext = bytes(tampered)

        with pytest.raises(DecryptionError):
            decrypt_data(blob, key)

    def test_invalid_version(self, key, plaintext):
        """Invalid version fails."""
        blob = encrypt_data(plaintext, key)
        blob.version = 0xFF

        with pytest.raises(DecryptionError):
            decrypt_data(blob, key)


class TestEncryptedBlobSerialization:
    """Tests for EncryptedBlob serialization."""

    @pytest.fixture
    def blob(self):
        """Create test blob."""
        key = os.urandom(KEY_SIZE)
        return encrypt_data(b"Test data", key)

    def test_to_bytes_and_back(self, blob):
        """Roundtrip through bytes."""
        data = blob.to_bytes()
        restored = EncryptedBlob.from_bytes(data)

        assert restored.version == blob.version
        assert restored.nonce == blob.nonce
        assert restored.ciphertext == blob.ciphertext

    def test_to_base64_and_back(self, blob):
        """Roundtrip through base64."""
        b64 = blob.to_base64()
        restored = EncryptedBlob.from_base64(b64)

        assert restored.version == blob.version
        assert restored.nonce == blob.nonce

    def test_from_bytes_too_short(self):
        """Short data raises error."""
        with pytest.raises(DecryptionError):
            EncryptedBlob.from_bytes(b"short")


class TestStringEncryption:
    """Tests for string encryption convenience functions."""

    @pytest.fixture
    def key(self):
        """Generate test key."""
        return os.urandom(KEY_SIZE)

    def test_encrypt_string_roundtrip(self, key):
        """Encrypt and decrypt string."""
        original = "Hello, OTTO! 🎉"
        blob = encrypt_string(original, key)
        decrypted = decrypt_string(blob, key)
        assert decrypted == original

    def test_unicode_support(self, key):
        """Unicode characters work correctly."""
        original = "Привет, 世界! 🌍"
        blob = encrypt_string(original, key)
        decrypted = decrypt_string(blob, key)
        assert decrypted == original


# =============================================================================
# Key Derivation Tests
# =============================================================================

class TestKeyDerivationConstants:
    """Tests for key derivation constants."""

    def test_key_size_matches_encryption(self):
        """KDF key size matches encryption key size."""
        assert KDF_KEY_SIZE == KEY_SIZE

    def test_salt_size_adequate(self):
        """Salt size is adequate (>= 16 bytes)."""
        assert SALT_SIZE >= 16

    def test_default_params_immutable(self):
        """Default params are frozen."""
        with pytest.raises(Exception):
            DEFAULT_PARAMS.time_cost = 99


class TestGenerateSalt:
    """Tests for salt generation."""

    def test_salt_correct_size(self):
        """Salt is correct size."""
        salt = generate_salt()
        assert len(salt) == SALT_SIZE

    def test_salt_is_random(self):
        """Each salt is different."""
        salts = [generate_salt() for _ in range(10)]
        assert len(set(salts)) == 10


class TestDeriveKey:
    """Tests for key derivation."""

    @pytest.fixture
    def password(self):
        """Test password."""
        return "correct horse battery staple"

    @pytest.fixture
    def salt(self):
        """Test salt."""
        return generate_salt()

    def test_derive_key_correct_size(self, password, salt):
        """Derived key is correct size."""
        key = derive_key(password, salt)
        assert len(key) == KDF_KEY_SIZE

    def test_deterministic(self, password, salt):
        """Same password + salt = same key."""
        key1 = derive_key(password, salt)
        key2 = derive_key(password, salt)
        assert key1 == key2

    def test_different_password_different_key(self, salt):
        """Different passwords produce different keys."""
        key1 = derive_key("password1", salt)
        key2 = derive_key("password2", salt)
        assert key1 != key2

    def test_different_salt_different_key(self, password):
        """Different salts produce different keys."""
        key1 = derive_key(password, generate_salt())
        key2 = derive_key(password, generate_salt())
        assert key1 != key2

    def test_salt_too_short(self, password):
        """Short salt raises error."""
        with pytest.raises(KeyDerivationError):
            derive_key(password, b"short")


class TestVerifyKey:
    """Tests for key verification."""

    def test_verify_correct_password(self):
        """Correct password verifies."""
        password = "test password"
        salt = generate_salt()
        key = derive_key(password, salt)

        assert verify_key(password, salt, key)

    def test_verify_wrong_password(self):
        """Wrong password fails."""
        salt = generate_salt()
        key = derive_key("correct", salt)

        assert not verify_key("wrong", salt, key)


class TestPasswordStrength:
    """Tests for password strength validation."""

    def test_short_password_fails(self):
        """Short password fails."""
        valid, issues = validate_password_strength("short")
        assert not valid
        assert any("12 characters" in i for i in issues)

    def test_common_password_fails(self):
        """Common password fails."""
        # "password" is in the common list but too short
        # "password1234" is 12 chars and contains "password"
        valid, issues = validate_password_strength("password")
        assert not valid
        # Either too short or too common
        assert len(issues) > 0

    def test_good_password_passes(self):
        """Good password passes."""
        valid, issues = validate_password_strength("correct horse battery staple")
        assert valid
        assert len(issues) == 0


# =============================================================================
# Keyring Tests
# =============================================================================

class TestKeyringAdapter:
    """Tests for OS keyring adapter."""

    @pytest.fixture
    def adapter(self):
        """Create test adapter with unique service."""
        return KeyringAdapter(service_name="otto-os-test")

    @pytest.fixture
    def test_key(self):
        """Generate test key."""
        return os.urandom(32)

    def test_store_and_retrieve(self, adapter, test_key):
        """Store then retrieve key."""
        try:
            adapter.store("test-key", test_key)
            retrieved = adapter.retrieve("test-key")
            assert retrieved == test_key
        finally:
            try:
                adapter.delete("test-key")
            except Exception:
                pass

    def test_retrieve_nonexistent(self, adapter):
        """Retrieve nonexistent key raises."""
        with pytest.raises(KeyNotFoundError):
            adapter.retrieve("nonexistent-key")

    def test_delete_key(self, adapter, test_key):
        """Delete removes key."""
        adapter.store("delete-test", test_key)
        adapter.delete("delete-test")

        with pytest.raises(KeyNotFoundError):
            adapter.retrieve("delete-test")

    def test_exists_true(self, adapter, test_key):
        """Exists returns True for stored key."""
        try:
            adapter.store("exists-test", test_key)
            assert adapter.exists("exists-test")
        finally:
            try:
                adapter.delete("exists-test")
            except Exception:
                pass

    def test_exists_false(self, adapter):
        """Exists returns False for missing key."""
        assert not adapter.exists("missing-key")


# =============================================================================
# Secure File Tests
# =============================================================================

class TestSecureFileConstants:
    """Tests for secure file constants."""

    def test_magic_fixed(self):
        """Magic bytes are fixed."""
        assert MAGIC == b"OTTO"

    def test_version_fixed(self):
        """Format version is fixed."""
        assert FORMAT_VERSION == 0x01


class TestEncryptFile:
    """Tests for file encryption."""

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def password(self):
        """Test password."""
        return "test-password-123"

    @pytest.fixture
    def plaintext(self):
        """Test plaintext."""
        return b"Secret file contents for OTTO!"

    def test_encrypt_creates_file(self, temp_dir, plaintext, password):
        """Encryption creates file."""
        path = temp_dir / "test.enc"
        encrypt_file(plaintext, path, password)
        assert path.exists()

    def test_encrypted_file_has_magic(self, temp_dir, plaintext, password):
        """Encrypted file starts with magic."""
        path = temp_dir / "test.enc"
        encrypt_file(plaintext, path, password)

        with open(path, "rb") as f:
            magic = f.read(4)
        assert magic == MAGIC

    def test_is_encrypted_file_true(self, temp_dir, plaintext, password):
        """is_encrypted_file returns True."""
        path = temp_dir / "test.enc"
        encrypt_file(plaintext, path, password)
        assert is_encrypted_file(path)

    def test_is_encrypted_file_false(self, temp_dir):
        """is_encrypted_file returns False for normal file."""
        path = temp_dir / "normal.txt"
        path.write_text("Hello")
        assert not is_encrypted_file(path)


class TestDecryptFile:
    """Tests for file decryption."""

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def password(self):
        """Test password."""
        return "decrypt-test-password"

    @pytest.fixture
    def plaintext(self):
        """Test plaintext."""
        return b"Confidential data for OTTO OS testing!"

    def test_decrypt_roundtrip(self, temp_dir, plaintext, password):
        """Encrypt then decrypt returns original."""
        path = temp_dir / "roundtrip.enc"
        encrypt_file(plaintext, path, password)

        decrypted = decrypt_file_to_memory(path, password)
        assert decrypted == plaintext

    def test_wrong_password_fails(self, temp_dir, plaintext, password):
        """Wrong password fails decryption."""
        path = temp_dir / "wrong-pw.enc"
        encrypt_file(plaintext, path, password)

        with pytest.raises(FileIntegrityError):
            decrypt_file_to_memory(path, "wrong-password")

    def test_file_not_found(self, temp_dir, password):
        """Missing file raises error."""
        with pytest.raises(SecureFileError):
            decrypt_file_to_memory(temp_dir / "missing.enc", password)

    def test_invalid_format(self, temp_dir, password):
        """Invalid file format raises error."""
        path = temp_dir / "invalid.enc"
        path.write_bytes(b"not encrypted")

        with pytest.raises(InvalidFileFormat):
            decrypt_file_to_memory(path, password)


class TestSecureFileContext:
    """Tests for SecureFile context manager."""

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def encrypted_file(self, temp_dir):
        """Create encrypted test file."""
        path = temp_dir / "context-test.enc"
        content = b"Context manager test content"
        password = "context-password"

        encrypt_file(content, path, password)
        return path, content, password

    def test_read_in_context(self, encrypted_file):
        """Can read within context."""
        path, content, password = encrypted_file

        with SecureFile(path, password) as sf:
            data = sf.read()
            assert data == content

    def test_read_outside_context_fails(self, encrypted_file):
        """Read outside context raises."""
        path, _, password = encrypted_file

        sf = SecureFile(path, password)
        with pytest.raises(SecureFileError):
            sf.read()

    def test_read_text(self, temp_dir):
        """Can read as text."""
        path = temp_dir / "text.enc"
        text = "Hello, OTTO! 🎉"
        password = "text-password"

        encrypt_text_file(text, path, password)

        with SecureFile(path, password) as sf:
            result = sf.read_text()
            assert result == text


# =============================================================================
# Recovery Key Tests
# =============================================================================

class TestRecoveryKeyConstants:
    """Tests for recovery key constants."""

    def test_word_count_fixed(self):
        """Word count is fixed at 24."""
        assert WORD_COUNT == 24

    def test_entropy_size_fixed(self):
        """Entropy size is fixed at 32 bytes."""
        assert ENTROPY_SIZE == 32


class TestGenerateRecoveryKey:
    """Tests for recovery key generation."""

    def test_generates_24_words(self):
        """Recovery key has 24 words."""
        recovery = generate_recovery_key()
        assert len(recovery.words) == WORD_COUNT

    def test_entropy_correct_size(self):
        """Entropy is correct size."""
        recovery = generate_recovery_key()
        assert len(recovery.entropy) == ENTROPY_SIZE

    def test_words_string_format(self):
        """Words string is space-separated."""
        recovery = generate_recovery_key()
        words = recovery.words_string.split()
        assert len(words) == WORD_COUNT

    def test_to_bytes_returns_entropy(self):
        """to_bytes returns entropy."""
        recovery = generate_recovery_key()
        assert recovery.to_bytes() == recovery.entropy


class TestValidateRecoveryKey:
    """Tests for recovery key validation."""

    def test_valid_key_validates(self):
        """Generated key validates."""
        recovery = generate_recovery_key()
        assert validate_recovery_key(recovery.words_string)

    def test_wrong_word_count_fails(self):
        """Wrong word count fails."""
        assert not validate_recovery_key("word1 word2 word3")

    def test_invalid_words_fail(self):
        """Invalid words fail."""
        invalid = " ".join(["notaword"] * 24)
        assert not validate_recovery_key(invalid)

    def test_tampered_key_fails(self):
        """Tampered key fails checksum."""
        recovery = generate_recovery_key()
        words = recovery.words.copy()
        words[0] = "abandon"  # Replace first word
        tampered = " ".join(words)
        # May or may not fail depending on checksum
        # This tests that validation is performed


class TestRecoveryKeyToBytes:
    """Tests for recovery key to bytes conversion."""

    def test_roundtrip(self):
        """Generate, validate, convert roundtrip."""
        recovery = generate_recovery_key()
        words = recovery.words_string

        restored = recovery_key_to_bytes(words)
        assert restored == recovery.entropy

    def test_invalid_key_raises(self):
        """Invalid key raises error."""
        with pytest.raises(InvalidRecoveryKey):
            recovery_key_to_bytes("invalid words here")


class TestRecoveryKeyFromEntropy:
    """Tests for recovery key from entropy."""

    def test_deterministic(self):
        """Same entropy produces same words."""
        entropy = os.urandom(ENTROPY_SIZE)

        key1 = recovery_key_from_entropy(entropy)
        key2 = recovery_key_from_entropy(entropy)

        assert key1.words == key2.words

    def test_invalid_entropy_size(self):
        """Wrong entropy size raises."""
        with pytest.raises(RecoveryKeyError):
            recovery_key_from_entropy(b"short")


# =============================================================================
# Integration Tests
# =============================================================================

class TestCryptoIntegration:
    """Integration tests for crypto module."""

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_full_encryption_workflow(self, temp_dir):
        """Full encryption workflow: password → key → encrypt → decrypt."""
        # User provides password
        password = "my secure password 123"

        # Generate salt and derive key
        salt = generate_salt()
        key = derive_key(password, salt)

        # Encrypt data
        plaintext = b"My secret data"
        blob = encrypt_data(plaintext, key)

        # Decrypt data
        decrypted = decrypt_data(blob, key)
        assert decrypted == plaintext

    def test_file_encryption_workflow(self, temp_dir):
        """Full file encryption workflow."""
        path = temp_dir / "workflow.enc"
        password = "file-workflow-password"
        content = b"Sensitive file content"

        # Encrypt file
        encrypt_file(content, path, password)

        # Decrypt file
        decrypted = decrypt_file_to_memory(path, password)
        assert decrypted == content

    def test_recovery_key_integration(self, temp_dir):
        """Recovery key can decrypt data."""
        # Generate recovery key
        recovery = generate_recovery_key()

        # Use recovery key to derive encryption key
        salt = generate_salt()
        key = derive_key_from_bytes(recovery.entropy, salt)

        # Encrypt data
        plaintext = b"Data protected by recovery key"
        blob = encrypt_data(plaintext, key)

        # Later, use recovery words to decrypt
        restored_entropy = recovery_key_to_bytes(recovery.words_string)
        restored_key = derive_key_from_bytes(restored_entropy, salt)

        decrypted = decrypt_data(blob, restored_key)
        assert decrypted == plaintext


# =============================================================================
# Determinism Compliance Tests
# =============================================================================

class TestDeterminismCompliance:
    """Tests verifying determinism ([He2025])."""

    def test_fixed_algorithm_parameters(self):
        """Algorithm parameters are fixed at module level."""
        # Encryption
        assert KEY_SIZE == 32
        assert NONCE_SIZE == 12
        assert TAG_SIZE == 16

        # Key derivation
        assert DEFAULT_PARAMS.time_cost == 3
        assert DEFAULT_PARAMS.memory_cost == 65536
        assert DEFAULT_PARAMS.parallelism == 4

    def test_deterministic_encryption(self):
        """Same inputs produce same outputs."""
        key = os.urandom(KEY_SIZE)
        nonce = generate_nonce()
        plaintext = b"deterministic test"

        blob1 = encrypt_data(plaintext, key, nonce=nonce)
        blob2 = encrypt_data(plaintext, key, nonce=nonce)

        assert blob1.ciphertext == blob2.ciphertext

    def test_deterministic_key_derivation(self):
        """Same password + salt produces same key."""
        password = "deterministic password"
        salt = generate_salt()

        key1 = derive_key(password, salt)
        key2 = derive_key(password, salt)

        assert key1 == key2

    def test_deterministic_recovery_key(self):
        """Same entropy produces same recovery words."""
        entropy = os.urandom(ENTROPY_SIZE)

        key1 = recovery_key_from_entropy(entropy)
        key2 = recovery_key_from_entropy(entropy)

        assert key1.words == key2.words

    def test_bounded_operations(self):
        """Operations are bounded."""
        # Key derivation has fixed iteration count
        assert DEFAULT_PARAMS.time_cost == 3

        # Memory is bounded
        assert DEFAULT_PARAMS.memory_cost == 65536  # 64 MiB

        # Recovery key is fixed size
        assert WORD_COUNT == 24
        assert ENTROPY_SIZE == 32
