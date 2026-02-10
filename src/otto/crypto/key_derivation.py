"""
Argon2id Key Derivation
=======================

Password-based key derivation using Argon2id.

Determinism:
- FIXED algorithm: Argon2id (hybrid of Argon2i and Argon2d)
- FIXED parameters: memory, time, parallelism (no runtime variation)
- DETERMINISTIC: same password + salt → same key

Security Properties:
- Memory-hard: Resistant to GPU/ASIC attacks
- Side-channel resistant: Argon2id hybrid provides protection
- Salt prevents rainbow table attacks
- High iteration count slows brute force

Parameters (OWASP recommended for interactive logins):
- Memory: 64 MiB (65536 KiB)
- Time: 3 iterations
- Parallelism: 4 lanes
- Output: 32 bytes (256 bits for AES-256)

Usage:
    from otto.crypto import derive_key, generate_salt, verify_key

    salt = generate_salt()
    key = derive_key(password, salt)

    # Later, verify the password
    if verify_key(password, salt, expected_key):
        # Password correct
"""

import os
import logging
import secrets
from dataclasses import dataclass
from typing import Optional

from argon2 import PasswordHasher
from argon2.low_level import Type, hash_secret_raw

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED)
# =============================================================================

# Key output size (for AES-256)
KEY_SIZE = 32  # 256 bits

# Salt size (OWASP minimum is 16 bytes)
SALT_SIZE = 32  # 256 bits for extra margin

# Argon2id parameters (OWASP recommended for interactive logins)
# These are tuned for ~500ms derivation on modern hardware
ARGON2_TIME_COST = 3        # Iterations
ARGON2_MEMORY_COST = 65536  # 64 MiB in KiB
ARGON2_PARALLELISM = 4      # Parallel lanes
ARGON2_TYPE = Type.ID       # Argon2id (hybrid)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass(frozen=True)
class KeyDerivationParams:
    """
    Parameters for key derivation.

    Frozen to ensure immutability.
    """
    time_cost: int = ARGON2_TIME_COST
    memory_cost: int = ARGON2_MEMORY_COST
    parallelism: int = ARGON2_PARALLELISM
    key_size: int = KEY_SIZE
    salt_size: int = SALT_SIZE

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "time_cost": self.time_cost,
            "memory_cost": self.memory_cost,
            "parallelism": self.parallelism,
            "key_size": self.key_size,
            "salt_size": self.salt_size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KeyDerivationParams":
        """Deserialize from dictionary."""
        return cls(
            time_cost=data.get("time_cost", ARGON2_TIME_COST),
            memory_cost=data.get("memory_cost", ARGON2_MEMORY_COST),
            parallelism=data.get("parallelism", ARGON2_PARALLELISM),
            key_size=data.get("key_size", KEY_SIZE),
            salt_size=data.get("salt_size", SALT_SIZE),
        )


# Default parameters (immutable singleton)
DEFAULT_PARAMS = KeyDerivationParams()


# =============================================================================
# Exceptions
# =============================================================================

class KeyDerivationError(Exception):
    """Raised when key derivation fails."""
    pass


# =============================================================================
# Core Functions
# =============================================================================

def generate_salt(size: int = SALT_SIZE) -> bytes:
    """
    Generate a cryptographically secure random salt.

    Args:
        size: Salt size in bytes (default 32)

    Returns:
        Random salt bytes

    Determinism: FIXED size (32 bytes default), random generation.
    """
    return secrets.token_bytes(size)


def derive_key(
    password: str,
    salt: bytes,
    params: KeyDerivationParams = DEFAULT_PARAMS,
) -> bytes:
    """
    Derive encryption key from password using Argon2id.

    Args:
        password: User's password/passphrase
        salt: Random salt (should be stored alongside encrypted data)
        params: Key derivation parameters

    Returns:
        Derived key bytes (32 bytes for AES-256)

    Raises:
        KeyDerivationError: If derivation fails

    Determinism:
    - FIXED algorithm: Argon2id
    - FIXED parameters: time, memory, parallelism
    - DETERMINISTIC: same password + salt → same key
    """
    if len(salt) < 16:
        raise KeyDerivationError(f"Salt too short: {len(salt)} bytes (minimum 16)")

    try:
        # Use low-level API for raw key output
        key = hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=salt,
            time_cost=params.time_cost,
            memory_cost=params.memory_cost,
            parallelism=params.parallelism,
            hash_len=params.key_size,
            type=ARGON2_TYPE,
        )

        logger.debug(f"Key derived: {len(key)} bytes")
        return key

    except Exception as e:
        logger.error(f"Key derivation failed: {e}")
        raise KeyDerivationError(f"Key derivation failed: {e}")


def derive_key_from_bytes(
    secret: bytes,
    salt: bytes,
    params: KeyDerivationParams = DEFAULT_PARAMS,
) -> bytes:
    """
    Derive encryption key from byte secret (e.g., recovery key).

    Args:
        secret: Secret bytes (e.g., recovery key)
        salt: Random salt
        params: Key derivation parameters

    Returns:
        Derived key bytes

    Raises:
        KeyDerivationError: If derivation fails
    """
    if len(salt) < 16:
        raise KeyDerivationError(f"Salt too short: {len(salt)} bytes (minimum 16)")

    try:
        key = hash_secret_raw(
            secret=secret,
            salt=salt,
            time_cost=params.time_cost,
            memory_cost=params.memory_cost,
            parallelism=params.parallelism,
            hash_len=params.key_size,
            type=ARGON2_TYPE,
        )

        return key

    except Exception as e:
        logger.error(f"Key derivation failed: {e}")
        raise KeyDerivationError(f"Key derivation failed: {e}")


def verify_key(
    password: str,
    salt: bytes,
    expected_key: bytes,
    params: KeyDerivationParams = DEFAULT_PARAMS,
) -> bool:
    """
    Verify password by comparing derived key.

    Args:
        password: Password to verify
        salt: Salt used in original derivation
        expected_key: Expected key bytes
        params: Key derivation parameters

    Returns:
        True if password produces expected key

    Note: Uses constant-time comparison to prevent timing attacks.
    """
    try:
        derived = derive_key(password, salt, params)
        return secrets.compare_digest(derived, expected_key)
    except KeyDerivationError:
        return False


def estimate_derivation_time_ms(params: KeyDerivationParams = DEFAULT_PARAMS) -> int:
    """
    Estimate key derivation time in milliseconds.

    This is a rough estimate based on parameters. Actual time
    depends on hardware.

    Args:
        params: Key derivation parameters

    Returns:
        Estimated time in milliseconds

    Determinism: FIXED formula, deterministic output.
    """
    # Rough estimate: ~8ms per iteration per 1MiB at 4 parallelism
    memory_mb = params.memory_cost / 1024
    base_time = 8  # ms per iteration per MiB
    estimated = int(params.time_cost * memory_mb * base_time / params.parallelism)
    return max(100, estimated)  # Minimum 100ms


# =============================================================================
# Validation
# =============================================================================

def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password meets minimum strength requirements.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, list of issues)

    Requirements:
    - Minimum 12 characters
    - Not a common password (basic check)
    """
    issues = []

    if len(password) < 12:
        issues.append("Password must be at least 12 characters")

    # Basic common password check
    common_passwords = {
        "password", "123456", "password123", "admin", "letmein",
        "welcome", "monkey", "dragon", "master", "qwerty",
    }
    if password.lower() in common_passwords:
        issues.append("Password is too common")

    return len(issues) == 0, issues


__all__ = [
    "derive_key",
    "derive_key_from_bytes",
    "verify_key",
    "generate_salt",
    "validate_password_strength",
    "estimate_derivation_time_ms",
    "KeyDerivationParams",
    "KeyDerivationError",
    "KEY_SIZE",
    "SALT_SIZE",
    "DEFAULT_PARAMS",
]
