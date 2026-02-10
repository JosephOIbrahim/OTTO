"""Argon2id key derivation for passphrase → AES-256 key.

Argon2id is a **memory-hard** KDF that resists GPU and ASIC attacks.
It combines the data-dependent memory access pattern of Argon2d
(resists GPU) with the data-independent pattern of Argon2i (resists
side-channel attacks).

Determinism: same passphrase + same salt + same params → same key.
This is tested and required by.

Two parameter presets are provided:

- ``PRODUCTION_PARAMS``: Strong defaults for real use.  ~200 ms on
  a modern desktop (64 MiB memory, 3 iterations, 4 threads).
- ``TEST_PARAMS``: Minimal parameters for fast test execution.
  NEVER use these in production — they offer no brute-force
  resistance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw

from otto_v3.core.encryption.crypto import KEY_SIZE_BYTES

# ---- Constants ----

SALT_SIZE_BYTES: int = 16  # 128-bit salt


# ---- Parameter presets ----

@dataclass(frozen=True)
class KDFParams:
    """Argon2id tuning parameters.

    Frozen to prevent accidental mutation in a running system.

    Attributes:
        time_cost: Number of iterations (higher = slower).
        memory_cost: Memory in KiB (higher = more memory-hard).
        parallelism: Thread count.
        key_size: Output key length in bytes.
    """

    time_cost: int = 3
    memory_cost: int = 65_536   # 64 MiB
    parallelism: int = 4
    key_size: int = KEY_SIZE_BYTES  # 32 bytes for AES-256


# Named constant instances, not mutable globals
PRODUCTION_PARAMS: KDFParams = KDFParams()

TEST_PARAMS: KDFParams = KDFParams(
    time_cost=1,
    memory_cost=1_024,    # 1 MiB — fast for tests
    parallelism=1,
    key_size=KEY_SIZE_BYTES,
)


# ---- Public API ----

def derive_key(
    passphrase: str,
    salt: bytes,
    params: KDFParams = PRODUCTION_PARAMS,
) -> bytes:
    """Derive an AES-256 key from a passphrase using Argon2id.

    Deterministic: same inputs → same output (always).

    Args:
        passphrase: User-provided passphrase (UTF-8 encoded).
        salt: Random salt bytes (must be >= 8 bytes).
        params: KDF tuning parameters.

    Returns:
        Derived key of ``params.key_size`` bytes.

    Raises:
        ValueError: If salt is too short.
    """
    if len(salt) < 8:
        raise ValueError(
            f"Salt must be at least 8 bytes, got {len(salt)}."
        )
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_cost,
        parallelism=params.parallelism,
        hash_len=params.key_size,
        type=Type.ID,  # Argon2id
    )


def generate_salt() -> bytes:
    """Generate a cryptographically random salt.

    Returns:
        16 bytes from ``os.urandom``.
    """
    return os.urandom(SALT_SIZE_BYTES)
