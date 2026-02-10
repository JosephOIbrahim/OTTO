"""Keystore — master key lifecycle management.

Design: **key wrapping**.  A random 32-byte master key is generated
once during ``setup()``.  The master key is then encrypted ("wrapped")
with a **wrapping key** derived from the user's passphrase via Argon2id.

The master key never touches disk in plaintext.  What IS stored:

- ``salt`` — random bytes for Argon2id (public, safe)
- ``wrapped_key`` — master key encrypted by wrapping key (safe)
- ``verification`` — known plaintext encrypted by master key, used
  to validate recovery keys without trial decryption of real data
- ``version`` — schema version for future migration

Recovery: the recovery key IS the master key, hex-encoded.  It is
shown exactly once during setup and must be stored by the user in
a secure location.  On recovery, we verify against the verification
blob before accepting.

Lifecycle::

    setup(passphrase) → recovery_key_hex
    unlock(passphrase) → master_key
    recover(recovery_key_hex) → master_key
    change_passphrase(new_passphrase)
    lock()  → wipes master key from memory
"""

from __future__ import annotations

import json
from pathlib import Path

from otto.core.encryption.crypto import (
    CryptoEngine,
    DecryptionError,
    KEY_SIZE_BYTES,
)
from otto.core.encryption.kdf import (
    KDFParams,
    PRODUCTION_PARAMS,
    derive_key,
    generate_salt,
)

# Known plaintext for verification — not secret, just constant
_VERIFICATION_PLAINTEXT: bytes = b"OTTO_KEYSTORE_VERIFIED_v1"


class KeyStoreError(Exception):
    """Base error for keystore operations."""


class KeyStoreLockedError(KeyStoreError):
    """Raised when an operation requires an unlocked keystore."""


class KeyStoreAlreadyInitializedError(KeyStoreError):
    """Raised when setup() is called on an already-initialized store."""


class InvalidRecoveryKeyError(KeyStoreError):
    """Raised when a recovery key fails verification."""


class KeyStore:
    """Master key lifecycle manager.

    Args:
        store_path: Path to the keystore JSON file.
        kdf_params: Argon2id parameters (use TEST_PARAMS in tests).
    """

    def __init__(
        self,
        store_path: str | Path,
        kdf_params: KDFParams = PRODUCTION_PARAMS,
    ) -> None:
        self._store_path = Path(store_path)
        self._kdf_params = kdf_params
        self._master_key: bytes | None = None

    # ---- Setup (first-time) ----

    def setup(self, passphrase: str) -> str:
        """Initialize the keystore with a new master key.

        Generates a random master key, wraps it with a passphrase-
        derived key, and stores the wrapped key + salt + verification.

        Args:
            passphrase: User-chosen passphrase.

        Returns:
            Recovery key as a hex string (64 chars = 32 bytes).
            Show this ONCE to the user.  It cannot be regenerated.

        Raises:
            KeyStoreAlreadyInitializedError: If store file exists.
        """
        if self.is_initialized():
            raise KeyStoreAlreadyInitializedError(
                "Keystore already initialized. Use change_passphrase() "
                "or delete the store file to re-initialize."
            )

        master_key = CryptoEngine.generate_key()
        salt = generate_salt()
        wrapping_key = derive_key(passphrase, salt, self._kdf_params)

        # Wrap the master key with the passphrase-derived key
        wrapped_key = CryptoEngine.encrypt(master_key, wrapping_key)

        # Verification blob: known plaintext encrypted with master key
        # Used to validate recovery keys without trial-decrypting data
        verification = CryptoEngine.encrypt(
            _VERIFICATION_PLAINTEXT, master_key
        )

        store_data = {
            "salt": salt.hex(),
            "verification": verification.hex(),
            "version": 1,
            "wrapped_key": wrapped_key.hex(),
        }
        # sort_keys=True for [He2025] — deterministic serialization
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(
            json.dumps(store_data, sort_keys=True)
        )

        self._master_key = master_key
        return master_key.hex()

    # ---- Unlock / Lock ----

    def unlock(self, passphrase: str) -> bytes:
        """Unlock the keystore with the user's passphrase.

        Derives the wrapping key from passphrase + stored salt,
        then unwraps the master key.

        Args:
            passphrase: User's passphrase.

        Returns:
            The 32-byte master key.

        Raises:
            KeyStoreError: If store is not initialized.
            DecryptionError: If passphrase is wrong.
        """
        data = self._load_store_data()
        salt = bytes.fromhex(data["salt"])
        wrapped_key = bytes.fromhex(data["wrapped_key"])

        wrapping_key = derive_key(passphrase, salt, self._kdf_params)

        # Unwrap — DecryptionError propagates if passphrase is wrong
        master_key = CryptoEngine.decrypt(wrapped_key, wrapping_key)

        self._master_key = master_key
        return master_key

    def lock(self) -> None:
        """Wipe the master key from memory.

        After locking, all operations requiring the key will raise
        KeyStoreLockedError until unlock() or recover() is called.
        """
        self._master_key = None

    # ---- Recovery ----

    def recover(self, recovery_key_hex: str) -> bytes:
        """Recover using the recovery key shown during setup.

        The recovery key IS the master key hex-encoded.  We verify
        it against the stored verification blob before accepting.

        Args:
            recovery_key_hex: 64-character hex string (32 bytes).

        Returns:
            The 32-byte master key.

        Raises:
            ValueError: If hex string is wrong length.
            InvalidRecoveryKeyError: If key fails verification.
            KeyStoreError: If store is not initialized.
        """
        try:
            candidate_key = bytes.fromhex(recovery_key_hex)
        except ValueError as exc:
            raise ValueError(
                "Recovery key must be a valid hex string."
            ) from exc

        if len(candidate_key) != KEY_SIZE_BYTES:
            raise ValueError(
                f"Recovery key must be {KEY_SIZE_BYTES * 2} hex chars "
                f"({KEY_SIZE_BYTES} bytes), got {len(candidate_key)} bytes."
            )

        data = self._load_store_data()
        verification_blob = bytes.fromhex(data["verification"])

        try:
            plaintext = CryptoEngine.decrypt(
                verification_blob, candidate_key
            )
        except DecryptionError as exc:
            raise InvalidRecoveryKeyError(
                "Recovery key failed verification."
            ) from exc

        if plaintext != _VERIFICATION_PLAINTEXT:
            raise InvalidRecoveryKeyError(
                "Recovery key failed verification."
            )

        self._master_key = candidate_key
        return candidate_key

    # ---- Passphrase management ----

    def change_passphrase(self, new_passphrase: str) -> None:
        """Re-wrap the master key with a new passphrase.

        The keystore must be unlocked.  The recovery key does NOT
        change — it is still the same master key.

        Args:
            new_passphrase: The new passphrase.

        Raises:
            KeyStoreLockedError: If keystore is locked.
        """
        if not self.is_unlocked():
            raise KeyStoreLockedError(
                "Keystore must be unlocked to change passphrase."
            )

        new_salt = generate_salt()
        new_wrapping_key = derive_key(
            new_passphrase, new_salt, self._kdf_params
        )
        new_wrapped_key = CryptoEngine.encrypt(
            self._master_key, new_wrapping_key
        )

        data = self._load_store_data()
        data["salt"] = new_salt.hex()
        data["wrapped_key"] = new_wrapped_key.hex()
        # Verification stays the same — it's encrypted by master key

        self._store_path.write_text(
            json.dumps(data, sort_keys=True)
        )

    # ---- State queries ----

    def is_initialized(self) -> bool:
        """Check if the keystore file exists."""
        return self._store_path.exists()

    def is_unlocked(self) -> bool:
        """Check if the master key is currently in memory."""
        return self._master_key is not None

    @property
    def master_key(self) -> bytes:
        """Access the master key.  Must be unlocked.

        Raises:
            KeyStoreLockedError: If keystore is locked.
        """
        if self._master_key is None:
            raise KeyStoreLockedError(
                "Keystore is locked. Call unlock() or recover() first."
            )
        return self._master_key

    # ---- Internal helpers ----

    def _load_store_data(self) -> dict:
        """Load and validate the keystore JSON file.

        Raises:
            KeyStoreError: If store is not initialized or corrupted.
        """
        if not self.is_initialized():
            raise KeyStoreError(
                "Keystore not initialized. Call setup() first."
            )
        try:
            raw = self._store_path.read_text()
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise KeyStoreError(
                "Keystore file is corrupted or unreadable."
            ) from exc

        # Validate required fields
        for field in ("salt", "wrapped_key", "verification", "version"):
            if field not in data:
                raise KeyStoreError(
                    f"Keystore file missing required field: {field!r}"
                )
        return data
