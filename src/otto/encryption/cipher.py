"""
Cipher Module
=============

Implements AES-256-GCM authenticated encryption.

AES-256-GCM provides:
- Confidentiality (encryption)
- Integrity (authentication tag)
- Authenticity (verifies data wasn't tampered)

Wire format:
    [nonce: 12 bytes][ciphertext: variable][tag: 16 bytes]

The nonce is generated randomly for each encryption operation.
GCM mode requires a unique nonce for each encryption with the same key.
"""

import os
import secrets
import logging
from dataclasses import dataclass
from typing import Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    InvalidTag = Exception  # Fallback for type hints

logger = logging.getLogger(__name__)


# Constants
NONCE_LENGTH = 12  # 96 bits (GCM standard)
TAG_LENGTH = 16    # 128 bits (GCM standard)
KEY_LENGTH = 32    # 256 bits for AES-256


class CipherError(Exception):
    """Base exception for cipher operations."""
    pass


class EncryptionError(CipherError):
    """Raised when encryption fails."""
    pass


class DecryptionError(CipherError):
    """Raised when decryption fails (including authentication failure)."""
    pass


@dataclass
class EncryptedData:
    """
    Encrypted data with metadata.

    Attributes:
        nonce: The 12-byte nonce used for encryption
        ciphertext: The encrypted data (includes GCM tag)
        associated_data: Optional authenticated but not encrypted data
    """
    nonce: bytes
    ciphertext: bytes
    associated_data: Optional[bytes] = None

    def to_bytes(self) -> bytes:
        """
        Serialize to bytes for storage.

        Format: [nonce: 12 bytes][ciphertext+tag: variable]
        """
        return self.nonce + self.ciphertext

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        associated_data: Optional[bytes] = None
    ) -> 'EncryptedData':
        """
        Deserialize from bytes.

        Args:
            data: Serialized encrypted data
            associated_data: Optional AAD that was used during encryption

        Returns:
            EncryptedData instance
        """
        if len(data) < NONCE_LENGTH + TAG_LENGTH:
            raise DecryptionError("Data too short to be valid ciphertext")

        nonce = data[:NONCE_LENGTH]
        ciphertext = data[NONCE_LENGTH:]

        return cls(
            nonce=nonce,
            ciphertext=ciphertext,
            associated_data=associated_data,
        )


class AESGCMCipher:
    """
    AES-256-GCM cipher for authenticated encryption.

    Example:
        >>> key = secrets.token_bytes(32)  # 256-bit key
        >>> cipher = AESGCMCipher(key)
        >>> encrypted = cipher.encrypt(b"secret data")
        >>> decrypted = cipher.decrypt(encrypted)
        >>> assert decrypted == b"secret data"
    """

    def __init__(self, key: bytes):
        """
        Initialize cipher with encryption key.

        Args:
            key: 32-byte (256-bit) encryption key

        Raises:
            ImportError: If cryptography library is not installed
            ValueError: If key length is invalid
        """
        if not CRYPTO_AVAILABLE:
            raise ImportError(
                "cryptography is required for encryption. "
                "Install with: pip install cryptography"
            )

        if len(key) != KEY_LENGTH:
            raise ValueError(f"Key must be {KEY_LENGTH} bytes, got {len(key)}")

        self._aesgcm = AESGCM(key)

    def encrypt(
        self,
        plaintext: bytes,
        associated_data: Optional[bytes] = None,
    ) -> EncryptedData:
        """
        Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt
            associated_data: Optional additional authenticated data (AAD)
                            This data is authenticated but not encrypted.

        Returns:
            EncryptedData containing nonce and ciphertext

        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            raise EncryptionError("Cannot encrypt empty data")

        try:
            # Generate random nonce
            nonce = secrets.token_bytes(NONCE_LENGTH)

            # Encrypt with GCM (ciphertext includes auth tag)
            ciphertext = self._aesgcm.encrypt(nonce, plaintext, associated_data)

            logger.debug(f"Encrypted {len(plaintext)} bytes -> {len(ciphertext)} bytes")

            return EncryptedData(
                nonce=nonce,
                ciphertext=ciphertext,
                associated_data=associated_data,
            )

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(
        self,
        encrypted: EncryptedData,
    ) -> bytes:
        """
        Decrypt data using AES-256-GCM.

        Args:
            encrypted: EncryptedData to decrypt

        Returns:
            Decrypted plaintext

        Raises:
            DecryptionError: If decryption or authentication fails
        """
        try:
            plaintext = self._aesgcm.decrypt(
                encrypted.nonce,
                encrypted.ciphertext,
                encrypted.associated_data,
            )

            logger.debug(f"Decrypted {len(encrypted.ciphertext)} bytes -> {len(plaintext)} bytes")

            return plaintext

        except InvalidTag:
            logger.error("Decryption failed: authentication tag invalid")
            raise DecryptionError(
                "Decryption failed: data was tampered with or wrong key"
            )
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise DecryptionError(f"Decryption failed: {e}") from e

    def encrypt_string(
        self,
        plaintext: str,
        encoding: str = 'utf-8',
        associated_data: Optional[bytes] = None,
    ) -> EncryptedData:
        """
        Encrypt a string.

        Args:
            plaintext: String to encrypt
            encoding: String encoding (default: utf-8)
            associated_data: Optional AAD

        Returns:
            EncryptedData
        """
        return self.encrypt(plaintext.encode(encoding), associated_data)

    def decrypt_string(
        self,
        encrypted: EncryptedData,
        encoding: str = 'utf-8',
    ) -> str:
        """
        Decrypt to a string.

        Args:
            encrypted: EncryptedData to decrypt
            encoding: String encoding (default: utf-8)

        Returns:
            Decrypted string
        """
        return self.decrypt(encrypted).decode(encoding)


def encrypt_bytes(key: bytes, plaintext: bytes) -> bytes:
    """
    Convenience function to encrypt bytes.

    Args:
        key: 32-byte encryption key
        plaintext: Data to encrypt

    Returns:
        Serialized encrypted data (nonce + ciphertext)
    """
    cipher = AESGCMCipher(key)
    encrypted = cipher.encrypt(plaintext)
    return encrypted.to_bytes()


def decrypt_bytes(key: bytes, data: bytes) -> bytes:
    """
    Convenience function to decrypt bytes.

    Args:
        key: 32-byte encryption key
        data: Serialized encrypted data

    Returns:
        Decrypted plaintext
    """
    cipher = AESGCMCipher(key)
    encrypted = EncryptedData.from_bytes(data)
    return cipher.decrypt(encrypted)


def encrypt_string(key: bytes, plaintext: str) -> bytes:
    """
    Convenience function to encrypt a string.

    Args:
        key: 32-byte encryption key
        plaintext: String to encrypt

    Returns:
        Serialized encrypted data
    """
    return encrypt_bytes(key, plaintext.encode('utf-8'))


def decrypt_string(key: bytes, data: bytes) -> str:
    """
    Convenience function to decrypt to a string.

    Args:
        key: 32-byte encryption key
        data: Serialized encrypted data

    Returns:
        Decrypted string
    """
    return decrypt_bytes(key, data).decode('utf-8')


__all__ = [
    'AESGCMCipher',
    'EncryptedData',
    'CipherError',
    'EncryptionError',
    'DecryptionError',
    'encrypt_bytes',
    'decrypt_bytes',
    'encrypt_string',
    'decrypt_string',
    'NONCE_LENGTH',
    'TAG_LENGTH',
    'KEY_LENGTH',
    'CRYPTO_AVAILABLE',
]
