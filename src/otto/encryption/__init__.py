"""
Encryption Module
=================

Provides at-rest encryption for sensitive OTTO OS data.

Architecture:
    User Passphrase
         ↓
    Argon2id (key derivation)
         ↓
    256-bit Encryption Key
         ↓
    AES-256-GCM (authenticated encryption)
         ↓
    Encrypted Files (.enc)

Components:
- key_derivation: Argon2id passphrase-to-key derivation
- cipher: AES-256-GCM authenticated encryption
- keyring_store: OS keychain integration (Windows/macOS/Linux)
- file_encryption: File-level encryption wrapper
- encryption_manager: High-level orchestration

Data Classification:
- PUBLIC: No encryption (config, UI settings)
- PRIVATE: Encrypted (calibration, sessions, knowledge)
- SENSITIVE: Encrypted + additional protection (health, crisis)

Security Properties:
- Confidentiality: AES-256-GCM encryption
- Integrity: GCM authentication tag
- Key protection: Argon2id memory-hard derivation
- Key storage: OS keychain (Credential Manager/Keychain/libsecret)
- Recovery: One-time recovery key shown at setup
"""

from .key_derivation import (
    DerivedKey,
    KeyDerivationError,
    derive_key,
    generate_recovery_key,
    recovery_key_to_words,
    words_to_recovery_key,
    derive_key_from_recovery,
    validate_passphrase_strength,
    secure_compare,
    SALT_LENGTH,
    KEY_LENGTH,
    RECOVERY_KEY_LENGTH,
    ARGON2_AVAILABLE,
)

from .cipher import (
    AESGCMCipher,
    EncryptedData,
    CipherError,
    EncryptionError,
    DecryptionError,
    encrypt_bytes,
    decrypt_bytes,
    encrypt_string,
    decrypt_string,
    NONCE_LENGTH,
    TAG_LENGTH,
    CRYPTO_AVAILABLE,
)

from .keyring_store import (
    KeyringStore,
    KeyringEntry,
    KeyringStoreError,
    KeyringUnavailableError,
    create_keyring_store,
    is_keyring_available,
    SERVICE_NAME,
    KEYRING_AVAILABLE,
)

from .file_encryption import (
    FileEncryptor,
    EncryptedFileHeader,
    FileEncryptionError,
    FileNotEncryptedError,
    FileAlreadyEncryptedError,
    get_encrypted_path,
    get_decrypted_path,
    is_encrypted_file,
    find_encrypted_files,
    find_files_to_encrypt,
    ENCRYPTED_EXTENSION,
    FILE_VERSION,
)

from .encryption_manager import (
    EncryptionManager,
    EncryptionStatus,
    EncryptionManagerError,
    NotSetupError,
    NotUnlockedError,
    AlreadySetupError,
    InvalidPassphraseError,
    create_encryption_manager,
)


def check_dependencies() -> dict:
    """
    Check encryption dependency availability.

    Returns:
        Dict with availability status for each dependency
    """
    return {
        "argon2": ARGON2_AVAILABLE,
        "cryptography": CRYPTO_AVAILABLE,
        "keyring": KEYRING_AVAILABLE,
        "all_available": ARGON2_AVAILABLE and CRYPTO_AVAILABLE and KEYRING_AVAILABLE,
    }


__all__ = [
    # Key Derivation
    "DerivedKey",
    "KeyDerivationError",
    "derive_key",
    "generate_recovery_key",
    "recovery_key_to_words",
    "words_to_recovery_key",
    "derive_key_from_recovery",
    "validate_passphrase_strength",
    "secure_compare",
    "SALT_LENGTH",
    "KEY_LENGTH",
    "RECOVERY_KEY_LENGTH",
    "ARGON2_AVAILABLE",
    # Cipher
    "AESGCMCipher",
    "EncryptedData",
    "CipherError",
    "EncryptionError",
    "DecryptionError",
    "encrypt_bytes",
    "decrypt_bytes",
    "encrypt_string",
    "decrypt_string",
    "NONCE_LENGTH",
    "TAG_LENGTH",
    "CRYPTO_AVAILABLE",
    # Keyring
    "KeyringStore",
    "KeyringEntry",
    "KeyringStoreError",
    "KeyringUnavailableError",
    "create_keyring_store",
    "is_keyring_available",
    "SERVICE_NAME",
    "KEYRING_AVAILABLE",
    # File Encryption
    "FileEncryptor",
    "EncryptedFileHeader",
    "FileEncryptionError",
    "FileNotEncryptedError",
    "FileAlreadyEncryptedError",
    "get_encrypted_path",
    "get_decrypted_path",
    "is_encrypted_file",
    "find_encrypted_files",
    "find_files_to_encrypt",
    "ENCRYPTED_EXTENSION",
    "FILE_VERSION",
    # Manager
    "EncryptionManager",
    "EncryptionStatus",
    "EncryptionManagerError",
    "NotSetupError",
    "NotUnlockedError",
    "AlreadySetupError",
    "InvalidPassphraseError",
    "create_encryption_manager",
    # Utilities
    "check_dependencies",
]
