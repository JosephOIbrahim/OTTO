"""
Key Derivation Module
=====================

Implements secure key derivation using Argon2id.

Argon2id is the recommended algorithm for password hashing and key derivation:
- Memory-hard (resists GPU attacks)
- Time-hard (configurable iterations)
- Hybrid mode (side-channel resistant)

NIST recommends Argon2id for password-based key derivation.

Parameters (OWASP recommendations for 2024+):
- Memory: 64 MiB (65536 KiB)
- Iterations: 3
- Parallelism: 4
- Salt: 16 bytes (random)
- Key length: 32 bytes (256 bits for AES-256)
"""

import os
import secrets
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    from argon2 import PasswordHasher, Type
    from argon2.low_level import hash_secret_raw
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False

logger = logging.getLogger(__name__)


# Constants
SALT_LENGTH = 16  # 128 bits
KEY_LENGTH = 32   # 256 bits for AES-256
RECOVERY_KEY_LENGTH = 32  # 256 bits

# Argon2id parameters (OWASP recommended for 2024)
ARGON2_TIME_COST = 3       # iterations
ARGON2_MEMORY_COST = 65536  # 64 MiB in KiB
ARGON2_PARALLELISM = 4     # threads


@dataclass
class DerivedKey:
    """
    A derived encryption key with its salt.

    Attributes:
        key: The derived 256-bit key
        salt: The salt used in derivation (needed for re-derivation)
    """
    key: bytes
    salt: bytes

    def __post_init__(self):
        """Validate key and salt lengths."""
        if len(self.key) != KEY_LENGTH:
            raise ValueError(f"Key must be {KEY_LENGTH} bytes, got {len(self.key)}")
        if len(self.salt) != SALT_LENGTH:
            raise ValueError(f"Salt must be {SALT_LENGTH} bytes, got {len(self.salt)}")


class KeyDerivationError(Exception):
    """Raised when key derivation fails."""
    pass


def derive_key(
    passphrase: str,
    salt: Optional[bytes] = None,
    time_cost: int = ARGON2_TIME_COST,
    memory_cost: int = ARGON2_MEMORY_COST,
    parallelism: int = ARGON2_PARALLELISM,
) -> DerivedKey:
    """
    Derive an encryption key from a passphrase using Argon2id.

    Args:
        passphrase: User's passphrase (any length)
        salt: Optional salt (generated if not provided)
        time_cost: Number of iterations
        memory_cost: Memory usage in KiB
        parallelism: Number of parallel threads

    Returns:
        DerivedKey with the key and salt

    Raises:
        KeyDerivationError: If key derivation fails
        ImportError: If argon2-cffi is not installed
    """
    if not ARGON2_AVAILABLE:
        raise ImportError(
            "argon2-cffi is required for key derivation. "
            "Install with: pip install argon2-cffi"
        )

    if not passphrase:
        raise KeyDerivationError("Passphrase cannot be empty")

    # Generate salt if not provided
    if salt is None:
        salt = secrets.token_bytes(SALT_LENGTH)
    elif len(salt) != SALT_LENGTH:
        raise KeyDerivationError(f"Salt must be {SALT_LENGTH} bytes")

    try:
        # Derive key using Argon2id
        key = hash_secret_raw(
            secret=passphrase.encode('utf-8'),
            salt=salt,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=KEY_LENGTH,
            type=Type.ID,  # Argon2id (hybrid mode)
        )

        logger.debug("Key derived successfully")
        return DerivedKey(key=key, salt=salt)

    except Exception as e:
        logger.error(f"Key derivation failed: {e}")
        raise KeyDerivationError(f"Failed to derive key: {e}") from e


def generate_recovery_key() -> bytes:
    """
    Generate a cryptographically secure recovery key.

    The recovery key is a random 256-bit value that can be used
    to decrypt data if the passphrase is lost.

    Returns:
        32 bytes of cryptographically secure random data
    """
    return secrets.token_bytes(RECOVERY_KEY_LENGTH)


def recovery_key_to_words(recovery_key: bytes) -> str:
    """
    Convert a recovery key to a human-readable format.

    Uses hex encoding split into groups for readability.
    Format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX

    Args:
        recovery_key: 32-byte recovery key

    Returns:
        Formatted string for display to user
    """
    if len(recovery_key) != RECOVERY_KEY_LENGTH:
        raise ValueError(f"Recovery key must be {RECOVERY_KEY_LENGTH} bytes")

    hex_key = recovery_key.hex().upper()
    # Split into 4-character groups
    groups = [hex_key[i:i+4] for i in range(0, len(hex_key), 4)]
    return '-'.join(groups)


def words_to_recovery_key(words: str) -> bytes:
    """
    Convert a human-readable recovery key back to bytes.

    Args:
        words: Formatted recovery key (with or without dashes)

    Returns:
        32-byte recovery key

    Raises:
        ValueError: If the input is invalid
    """
    # Remove dashes and whitespace
    hex_key = words.replace('-', '').replace(' ', '').strip()

    if len(hex_key) != RECOVERY_KEY_LENGTH * 2:
        raise ValueError(
            f"Invalid recovery key length. Expected {RECOVERY_KEY_LENGTH * 2} hex chars"
        )

    try:
        return bytes.fromhex(hex_key)
    except ValueError as e:
        raise ValueError(f"Invalid recovery key format: {e}") from e


def derive_key_from_recovery(recovery_key: bytes) -> bytes:
    """
    Derive an encryption key from a recovery key.

    The recovery key IS the encryption key (no derivation needed,
    as it's already cryptographically random).

    Args:
        recovery_key: 32-byte recovery key

    Returns:
        The same 32 bytes (used directly as AES-256 key)
    """
    if len(recovery_key) != RECOVERY_KEY_LENGTH:
        raise ValueError(f"Recovery key must be {RECOVERY_KEY_LENGTH} bytes")
    return recovery_key


def validate_passphrase_strength(passphrase: str) -> Tuple[bool, str]:
    """
    Validate passphrase meets minimum strength requirements.

    Requirements:
    - At least 12 characters
    - Not a common password pattern

    Args:
        passphrase: The passphrase to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if len(passphrase) < 12:
        return False, "Passphrase must be at least 12 characters"

    # Check for common weak patterns
    weak_patterns = [
        'password', '12345678', 'qwerty', 'letmein',
        'welcome', 'monkey', 'dragon', 'master',
    ]
    lower_pass = passphrase.lower()
    for pattern in weak_patterns:
        if pattern in lower_pass:
            return False, f"Passphrase contains common pattern: {pattern}"

    return True, "Passphrase meets requirements"


def secure_compare(a: bytes, b: bytes) -> bool:
    """
    Compare two byte strings in constant time.

    Prevents timing attacks by comparing all bytes regardless
    of where the first difference occurs.

    Args:
        a: First byte string
        b: Second byte string

    Returns:
        True if equal, False otherwise
    """
    if len(a) != len(b):
        return False

    result = 0
    for x, y in zip(a, b):
        result |= x ^ y

    return result == 0


__all__ = [
    'DerivedKey',
    'KeyDerivationError',
    'derive_key',
    'generate_recovery_key',
    'recovery_key_to_words',
    'words_to_recovery_key',
    'derive_key_from_recovery',
    'validate_passphrase_strength',
    'secure_compare',
    'SALT_LENGTH',
    'KEY_LENGTH',
    'RECOVERY_KEY_LENGTH',
    'ARGON2_AVAILABLE',
]
