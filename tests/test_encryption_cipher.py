"""
Tests for Cipher Module
========================

Tests for AES-256-GCM authenticated encryption.
"""

import pytest
import secrets

from otto.encryption import (
    AESGCMCipher,
    EncryptedData,
    CipherError,
    EncryptionError,
    DecryptionError,
    encrypt_bytes,
    decrypt_bytes,
    encrypt_string,
    decrypt_string,
    KEY_LENGTH,
    NONCE_LENGTH,
    TAG_LENGTH,
    CRYPTO_AVAILABLE,
)


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestAESGCMCipher:
    """Tests for AESGCMCipher."""

    @pytest.fixture
    def key(self):
        """Generate a test key."""
        return secrets.token_bytes(KEY_LENGTH)

    @pytest.fixture
    def cipher(self, key):
        """Create a cipher instance."""
        return AESGCMCipher(key)

    def test_encrypt_decrypt_roundtrip(self, cipher):
        """Encrypted data can be decrypted."""
        plaintext = b"Hello, World!"
        encrypted = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_produces_nonce(self, cipher):
        """Encryption produces correct nonce length."""
        encrypted = cipher.encrypt(b"data")
        assert len(encrypted.nonce) == NONCE_LENGTH

    def test_encrypt_produces_ciphertext(self, cipher):
        """Encryption produces ciphertext with tag."""
        plaintext = b"data"
        encrypted = cipher.encrypt(plaintext)
        # Ciphertext should be plaintext length + tag length
        assert len(encrypted.ciphertext) == len(plaintext) + TAG_LENGTH

    def test_different_encryptions_different_nonces(self, cipher):
        """Each encryption uses different nonce."""
        encrypted1 = cipher.encrypt(b"data")
        encrypted2 = cipher.encrypt(b"data")
        assert encrypted1.nonce != encrypted2.nonce

    def test_wrong_key_fails_decryption(self, key):
        """Wrong key fails to decrypt."""
        cipher1 = AESGCMCipher(key)
        cipher2 = AESGCMCipher(secrets.token_bytes(KEY_LENGTH))

        encrypted = cipher1.encrypt(b"secret")

        with pytest.raises(DecryptionError):
            cipher2.decrypt(encrypted)

    def test_tampered_ciphertext_fails(self, cipher):
        """Tampered ciphertext fails authentication."""
        encrypted = cipher.encrypt(b"secret data")

        # Tamper with ciphertext
        tampered_ciphertext = bytes([
            encrypted.ciphertext[0] ^ 0xFF
        ]) + encrypted.ciphertext[1:]

        tampered = EncryptedData(
            nonce=encrypted.nonce,
            ciphertext=tampered_ciphertext,
        )

        with pytest.raises(DecryptionError):
            cipher.decrypt(tampered)

    def test_tampered_nonce_fails(self, cipher):
        """Tampered nonce fails decryption."""
        encrypted = cipher.encrypt(b"secret data")

        # Tamper with nonce
        tampered_nonce = bytes([
            encrypted.nonce[0] ^ 0xFF
        ]) + encrypted.nonce[1:]

        tampered = EncryptedData(
            nonce=tampered_nonce,
            ciphertext=encrypted.ciphertext,
        )

        with pytest.raises(DecryptionError):
            cipher.decrypt(tampered)

    def test_empty_plaintext_raises(self, cipher):
        """Empty plaintext raises error."""
        with pytest.raises(EncryptionError):
            cipher.encrypt(b"")

    def test_invalid_key_length_raises(self):
        """Invalid key length raises error."""
        with pytest.raises(ValueError):
            AESGCMCipher(b"too-short")

    def test_associated_data(self, cipher):
        """Associated data is authenticated but not encrypted."""
        plaintext = b"secret"
        aad = b"public metadata"

        encrypted = cipher.encrypt(plaintext, associated_data=aad)

        # Correct AAD - decryption succeeds
        encrypted_with_aad = EncryptedData(
            nonce=encrypted.nonce,
            ciphertext=encrypted.ciphertext,
            associated_data=aad,
        )
        decrypted = cipher.decrypt(encrypted_with_aad)
        assert decrypted == plaintext

        # Wrong AAD - decryption fails
        encrypted_wrong_aad = EncryptedData(
            nonce=encrypted.nonce,
            ciphertext=encrypted.ciphertext,
            associated_data=b"wrong metadata",
        )
        with pytest.raises(DecryptionError):
            cipher.decrypt(encrypted_wrong_aad)

    def test_encrypt_string(self, cipher):
        """String encryption works."""
        plaintext = "Hello, World!"
        encrypted = cipher.encrypt_string(plaintext)
        decrypted = cipher.decrypt_string(encrypted)
        assert decrypted == plaintext

    def test_unicode_string(self, cipher):
        """Unicode strings work correctly."""
        plaintext = "Hello 世界! 🎉"
        encrypted = cipher.encrypt_string(plaintext)
        decrypted = cipher.decrypt_string(encrypted)
        assert decrypted == plaintext


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestEncryptedData:
    """Tests for EncryptedData serialization."""

    def test_to_bytes_from_bytes_roundtrip(self):
        """Serialization roundtrip works."""
        key = secrets.token_bytes(KEY_LENGTH)
        cipher = AESGCMCipher(key)

        original = cipher.encrypt(b"test data")
        serialized = original.to_bytes()
        restored = EncryptedData.from_bytes(serialized)

        # Decrypt restored data
        decrypted = cipher.decrypt(restored)
        assert decrypted == b"test data"

    def test_to_bytes_format(self):
        """Serialized format is nonce + ciphertext."""
        key = secrets.token_bytes(KEY_LENGTH)
        cipher = AESGCMCipher(key)

        encrypted = cipher.encrypt(b"data")
        serialized = encrypted.to_bytes()

        assert serialized[:NONCE_LENGTH] == encrypted.nonce
        assert serialized[NONCE_LENGTH:] == encrypted.ciphertext

    def test_from_bytes_too_short_raises(self):
        """Too short data raises error."""
        with pytest.raises(DecryptionError):
            EncryptedData.from_bytes(b"short")


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestConvenienceFunctions:
    """Tests for convenience encryption functions."""

    def test_encrypt_decrypt_bytes(self):
        """encrypt_bytes and decrypt_bytes work."""
        key = secrets.token_bytes(KEY_LENGTH)
        plaintext = b"secret bytes"

        encrypted = encrypt_bytes(key, plaintext)
        decrypted = decrypt_bytes(key, encrypted)

        assert decrypted == plaintext

    def test_encrypt_decrypt_string(self):
        """encrypt_string and decrypt_string work."""
        key = secrets.token_bytes(KEY_LENGTH)
        plaintext = "secret string"

        encrypted = encrypt_string(key, plaintext)
        decrypted = decrypt_string(key, encrypted)

        assert decrypted == plaintext

    def test_wrong_key_fails(self):
        """Wrong key fails decryption."""
        key1 = secrets.token_bytes(KEY_LENGTH)
        key2 = secrets.token_bytes(KEY_LENGTH)

        encrypted = encrypt_bytes(key1, b"secret")

        with pytest.raises(DecryptionError):
            decrypt_bytes(key2, encrypted)
