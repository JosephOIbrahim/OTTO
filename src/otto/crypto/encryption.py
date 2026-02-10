"""
AES-256-GCM Encryption
======================

Authenticated encryption using AES-256 in GCM mode.

Determinism:
- FIXED algorithm: AES-256-GCM (no runtime selection)
- FIXED nonce size: 12 bytes (96 bits, GCM optimal)
- FIXED tag size: 16 bytes (128 bits)
- DETERMINISTIC: same key + nonce + data → same ciphertext

Security Properties:
- 256-bit key provides 128-bit security level
- GCM provides authentication (integrity + authenticity)
- Random nonce per encryption prevents replay attacks
- Associated data (AAD) support for metadata authentication

Usage:
    from otto.crypto import encrypt_data, decrypt_data, generate_nonce

    key = derive_key(password, salt)  # 32-byte key
    nonce = generate_nonce()

    blob = encrypt_data(plaintext, key, nonce)
    plaintext = decrypt_data(blob, key)
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED - ThinkingMachines compliant)
# =============================================================================

KEY_SIZE = 32       # 256 bits
NONCE_SIZE = 12     # 96 bits (optimal for GCM)
TAG_SIZE = 16       # 128 bits (GCM authentication tag)

# Version byte for future format changes
BLOB_VERSION = 0x01


# =============================================================================
# Exceptions
# =============================================================================

class EncryptionError(Exception):
    """Raised when encryption fails."""
    pass


class DecryptionError(Exception):
    """Raised when decryption fails."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class EncryptedBlob:
    """
    Container for encrypted data.

    Format:
    ┌─────────┬─────────┬──────────────┬─────────────────┐
    │ Version │  Nonce  │  Ciphertext  │  (Tag in GCM)   │
    │ 1 byte  │ 12 bytes│   variable   │ 16 bytes (incl) │
    └─────────┴─────────┴──────────────┴─────────────────┘

    The tag is included in the ciphertext by AESGCM.
    """
    version: int
    nonce: bytes
    ciphertext: bytes  # Includes GCM authentication tag
    associated_data: Optional[bytes] = None

    def to_bytes(self) -> bytes:
        """Serialize to bytes for storage."""
        return bytes([self.version]) + self.nonce + self.ciphertext

    @classmethod
    def from_bytes(cls, data: bytes, associated_data: Optional[bytes] = None) -> "EncryptedBlob":
        """Deserialize from bytes."""
        if len(data) < 1 + NONCE_SIZE + TAG_SIZE:
            raise DecryptionError("Data too short to be valid encrypted blob")

        version = data[0]
        if version != BLOB_VERSION:
            raise DecryptionError(f"Unsupported blob version: {version}")

        nonce = data[1:1 + NONCE_SIZE]
        ciphertext = data[1 + NONCE_SIZE:]

        return cls(
            version=version,
            nonce=nonce,
            ciphertext=ciphertext,
            associated_data=associated_data,
        )

    def to_base64(self) -> str:
        """Encode blob as base64 string."""
        return base64.b64encode(self.to_bytes()).decode("ascii")

    @classmethod
    def from_base64(cls, data: str, associated_data: Optional[bytes] = None) -> "EncryptedBlob":
        """Decode blob from base64 string."""
        try:
            raw = base64.b64decode(data)
            return cls.from_bytes(raw, associated_data)
        except Exception as e:
            raise DecryptionError(f"Invalid base64 data: {e}")


# =============================================================================
# Core Functions
# =============================================================================

def generate_nonce() -> bytes:
    """
    Generate a cryptographically secure random nonce.

    Returns:
        12-byte random nonce for AES-GCM

    ThinkingMachines: FIXED size (12 bytes), random generation.
    """
    return os.urandom(NONCE_SIZE)


def encrypt_data(
    plaintext: bytes,
    key: bytes,
    nonce: Optional[bytes] = None,
    associated_data: Optional[bytes] = None,
) -> EncryptedBlob:
    """
    Encrypt data using AES-256-GCM.

    Args:
        plaintext: Data to encrypt
        key: 32-byte encryption key
        nonce: 12-byte nonce (generated if not provided)
        associated_data: Additional authenticated data (not encrypted, but authenticated)

    Returns:
        EncryptedBlob containing ciphertext and metadata

    Raises:
        EncryptionError: If encryption fails

    ThinkingMachines Compliance:
    - FIXED algorithm: AES-256-GCM
    - FIXED key size: 32 bytes
    - FIXED nonce size: 12 bytes
    - DETERMINISTIC: same inputs → same output
    """
    # Validate key size
    if len(key) != KEY_SIZE:
        raise EncryptionError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")

    # Generate nonce if not provided
    if nonce is None:
        nonce = generate_nonce()
    elif len(nonce) != NONCE_SIZE:
        raise EncryptionError(f"Nonce must be {NONCE_SIZE} bytes, got {len(nonce)}")

    try:
        cipher = AESGCM(key)
        ciphertext = cipher.encrypt(nonce, plaintext, associated_data)

        return EncryptedBlob(
            version=BLOB_VERSION,
            nonce=nonce,
            ciphertext=ciphertext,
            associated_data=associated_data,
        )

    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise EncryptionError(f"Encryption failed: {e}")


def decrypt_data(
    blob: EncryptedBlob,
    key: bytes,
) -> bytes:
    """
    Decrypt data using AES-256-GCM.

    Args:
        blob: EncryptedBlob containing ciphertext
        key: 32-byte decryption key

    Returns:
        Decrypted plaintext bytes

    Raises:
        DecryptionError: If decryption fails (wrong key, tampered data)

    ThinkingMachines Compliance:
    - FIXED algorithm: AES-256-GCM
    - Authentication verified before returning plaintext
    """
    # Validate key size
    if len(key) != KEY_SIZE:
        raise DecryptionError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")

    # Validate blob version
    if blob.version != BLOB_VERSION:
        raise DecryptionError(f"Unsupported blob version: {blob.version}")

    try:
        cipher = AESGCM(key)
        plaintext = cipher.decrypt(blob.nonce, blob.ciphertext, blob.associated_data)
        return plaintext

    except InvalidTag:
        raise DecryptionError("Decryption failed: invalid key or tampered data")
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise DecryptionError(f"Decryption failed: {e}")


def encrypt_string(
    plaintext: str,
    key: bytes,
    nonce: Optional[bytes] = None,
    encoding: str = "utf-8",
) -> EncryptedBlob:
    """
    Encrypt a string using AES-256-GCM.

    Convenience wrapper for encrypt_data that handles encoding.

    Args:
        plaintext: String to encrypt
        key: 32-byte encryption key
        nonce: Optional nonce (generated if not provided)
        encoding: String encoding (default UTF-8)

    Returns:
        EncryptedBlob containing ciphertext
    """
    return encrypt_data(plaintext.encode(encoding), key, nonce)


def decrypt_string(
    blob: EncryptedBlob,
    key: bytes,
    encoding: str = "utf-8",
) -> str:
    """
    Decrypt to string using AES-256-GCM.

    Convenience wrapper for decrypt_data that handles decoding.

    Args:
        blob: EncryptedBlob containing ciphertext
        key: 32-byte decryption key
        encoding: String encoding (default UTF-8)

    Returns:
        Decrypted string
    """
    plaintext = decrypt_data(blob, key)
    return plaintext.decode(encoding)


# =============================================================================
# Utility Functions
# =============================================================================

def secure_zero(data: bytearray) -> None:
    """
    Securely zero out sensitive data in memory.

    Note: This is a best-effort attempt. Python's memory management
    may have already copied the data elsewhere. For critical applications,
    consider using a secure memory library.

    Args:
        data: Mutable bytearray to zero
    """
    for i in range(len(data)):
        data[i] = 0


def validate_key(key: bytes) -> bool:
    """
    Validate that key has correct size.

    Args:
        key: Key bytes to validate

    Returns:
        True if key is valid size
    """
    return len(key) == KEY_SIZE


__all__ = [
    "encrypt_data",
    "decrypt_data",
    "encrypt_string",
    "decrypt_string",
    "generate_nonce",
    "secure_zero",
    "validate_key",
    "EncryptedBlob",
    "EncryptionError",
    "DecryptionError",
    "KEY_SIZE",
    "NONCE_SIZE",
    "TAG_SIZE",
    "BLOB_VERSION",
]
