"""Encryption subsystem — AES-256-GCM + Argon2id + key management.

Provides authenticated encryption for all cognitive data at rest.
The master key is wrapped by a passphrase-derived key and never
stored in plaintext.  A recovery key (the master key hex-encoded)
is shown once during setup.

Constitutional: ``privacy_is_law`` — raw data never leaves the device,
and all persistent cognitive data is encrypted.

Components:
    CryptoEngine   — AES-256-GCM encrypt/decrypt (stateless)
    derive_key     — Argon2id passphrase → key derivation
    KeyStore       — Master key lifecycle (setup/unlock/recover/lock)
"""

from otto.core.encryption.crypto import (
    CryptoEngine,
    DecryptionError,
    KEY_SIZE_BYTES,
    NONCE_SIZE_BYTES,
    TAG_SIZE_BYTES,
)
from otto.core.encryption.kdf import (
    KDFParams,
    PRODUCTION_PARAMS,
    SALT_SIZE_BYTES,
    TEST_PARAMS,
    derive_key,
    generate_salt,
)
from otto.core.encryption.keystore import (
    InvalidRecoveryKeyError,
    KeyStore,
    KeyStoreAlreadyInitializedError,
    KeyStoreError,
    KeyStoreLockedError,
)

__all__ = [
    # crypto.py
    "CryptoEngine",
    "DecryptionError",
    "KEY_SIZE_BYTES",
    "NONCE_SIZE_BYTES",
    "TAG_SIZE_BYTES",
    # kdf.py
    "KDFParams",
    "PRODUCTION_PARAMS",
    "SALT_SIZE_BYTES",
    "TEST_PARAMS",
    "derive_key",
    "generate_salt",
    # keystore.py
    "InvalidRecoveryKeyError",
    "KeyStore",
    "KeyStoreAlreadyInitializedError",
    "KeyStoreError",
    "KeyStoreLockedError",
]
