"""AES-256-GCM authenticated encryption engine.

Provides AEAD (Authenticated Encryption with Associated Data) using
AES-256 in GCM mode via the ``cryptography`` library.

Wire format (single contiguous blob):
    nonce (12 bytes) || ciphertext || GCM tag (16 bytes)

The nonce is generated from ``os.urandom`` on every encrypt() call,
so **identical plaintext + key → different ciphertext** (by design).
This is the ONE intentional non-determinism in OTTO's crypto layer,
documented as a safety exception.

The tag is appended by ``AESGCM.encrypt`` — we do not need to split
it manually. ``AESGCM.decrypt`` expects ``ciphertext || tag`` and
handles verification internally.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---- Constants (fixed, never configurable) ----

KEY_SIZE_BYTES: int = 32     # AES-256
NONCE_SIZE_BYTES: int = 12   # GCM standard
TAG_SIZE_BYTES: int = 16     # GCM authentication tag

# Minimum ciphertext blob = nonce + tag (empty plaintext)
_MIN_BLOB_SIZE: int = NONCE_SIZE_BYTES + TAG_SIZE_BYTES


class DecryptionError(Exception):
    """Raised when decryption fails.

    This deliberately provides NO information about *why* it failed
    (wrong key vs. corrupted data vs. tampered AAD) — leaking the
    failure mode is an oracle attack vector.
    """


class CryptoEngine:
    """Stateless AES-256-GCM encryption engine.

    All methods are ``@staticmethod`` — the engine holds no state.
    Key management is the Keystore's responsibility.
    """

    @staticmethod
    def encrypt(
        plaintext: bytes,
        key: bytes,
        aad: bytes | None = None,
    ) -> bytes:
        """Encrypt plaintext with AES-256-GCM.

        Args:
            plaintext: Data to encrypt (may be empty).
            key: 32-byte AES-256 key.
            aad: Optional additional authenticated data (integrity-
                protected but NOT encrypted).

        Returns:
            Blob of ``nonce || ciphertext || tag``.

        Raises:
            ValueError: If key is not exactly 32 bytes.
        """
        _validate_key(key)
        nonce = os.urandom(NONCE_SIZE_BYTES)
        aesgcm = AESGCM(key)
        # AESGCM.encrypt returns ciphertext || tag
        ct_and_tag = aesgcm.encrypt(nonce, plaintext, aad)
        return nonce + ct_and_tag

    @staticmethod
    def decrypt(
        blob: bytes,
        key: bytes,
        aad: bytes | None = None,
    ) -> bytes:
        """Decrypt an AES-256-GCM blob.

        Args:
            blob: ``nonce (12) || ciphertext || tag (16)``.
            key: 32-byte AES-256 key.
            aad: Must match the AAD used during encryption.

        Returns:
            Original plaintext bytes.

        Raises:
            ValueError: If key is not exactly 32 bytes.
            DecryptionError: If decryption fails for any reason.
        """
        _validate_key(key)
        if len(blob) < _MIN_BLOB_SIZE:
            raise DecryptionError(
                "Ciphertext blob too short to contain nonce + tag."
            )
        nonce = blob[:NONCE_SIZE_BYTES]
        ct_and_tag = blob[NONCE_SIZE_BYTES:]
        aesgcm = AESGCM(key)
        try:
            return aesgcm.decrypt(nonce, ct_and_tag, aad)
        except Exception as exc:
            # Wrap ALL failures in DecryptionError — no oracle leaks
            raise DecryptionError(
                "Decryption failed."
            ) from exc

    @staticmethod
    def generate_key() -> bytes:
        """Generate a cryptographically random AES-256 key.

        Returns:
            32 bytes from ``os.urandom``.
        """
        return os.urandom(KEY_SIZE_BYTES)


# ---- Internal helpers ----

def _validate_key(key: bytes) -> None:
    """Raise ValueError if key is not 32 bytes."""
    if len(key) != KEY_SIZE_BYTES:
        raise ValueError(
            f"Key must be exactly {KEY_SIZE_BYTES} bytes, "
            f"got {len(key)}."
        )
