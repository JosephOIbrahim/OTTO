"""
OTTO OS Cryptography Module
============================

End-to-end encryption for privacy-first data protection.

ThinkingMachines [He2025] Compliance:
- Fixed algorithm parameters (no runtime variation)
- Deterministic key derivation (same password → same key)
- Bounded operations (memory limits, iteration counts)

Components:
- encryption: AES-256-GCM symmetric encryption
- key_derivation: Argon2id password-based key derivation
- keyring_adapter: OS keychain integration
- secure_file: Memory-only file decryption
- recovery: Recovery key generation
- pqcrypto: Post-quantum hybrid key exchange (X25519 + ML-KEM-768)

Security Properties:
- AES-256-GCM: Authenticated encryption with 256-bit key
- Argon2id: Memory-hard, side-channel resistant
- Hybrid PQ: Quantum-resistant key exchange (when liboqs available)
- NEVER writes decrypted data to disk
- Key material zeroed after use
"""

from .encryption import (
    encrypt_data,
    decrypt_data,
    generate_nonce,
    EncryptedBlob,
    EncryptionError,
    DecryptionError,
)

from .key_derivation import (
    derive_key,
    verify_key,
    generate_salt,
    KeyDerivationParams,
    KEY_SIZE,
    SALT_SIZE,
)

from .keyring_adapter import (
    KeyringAdapter,
    store_key,
    retrieve_key,
    delete_key,
    KeyringError,
)

from .secure_file import (
    SecureFile,
    encrypt_file,
    decrypt_file_to_memory,
    SecureFileError,
)

from .recovery import (
    generate_recovery_key,
    validate_recovery_key,
    recovery_key_to_bytes,
    RecoveryKey,
)

from .pqcrypto import (
    # Core classes
    HybridKEM,
    HybridKeyExchange,
    X25519KEM,
    # Key types
    HybridKeyPair,
    HybridPublicKey,
    HybridPrivateKey,
    HybridCiphertext,
    KEMKeyPair,
    KEMPublicKey,
    KEMPrivateKey,
    KEMCiphertext,
    KEMAlgorithm,
    # Status
    PQSecurityStatus,
    is_pq_available,
    get_pq_status,
    # Convenience
    create_hybrid_kem,
    create_key_exchange,
    serialize_hybrid_public_key,
    deserialize_hybrid_public_key,
)

__all__ = [
    # Encryption
    "encrypt_data",
    "decrypt_data",
    "generate_nonce",
    "EncryptedBlob",
    "EncryptionError",
    "DecryptionError",
    # Key Derivation
    "derive_key",
    "verify_key",
    "generate_salt",
    "KeyDerivationParams",
    "KEY_SIZE",
    "SALT_SIZE",
    # Keyring
    "KeyringAdapter",
    "store_key",
    "retrieve_key",
    "delete_key",
    "KeyringError",
    # Secure File
    "SecureFile",
    "encrypt_file",
    "decrypt_file_to_memory",
    "SecureFileError",
    # Recovery
    "generate_recovery_key",
    "validate_recovery_key",
    "recovery_key_to_bytes",
    "RecoveryKey",
    # Post-Quantum Cryptography
    "HybridKEM",
    "HybridKeyExchange",
    "X25519KEM",
    "HybridKeyPair",
    "HybridPublicKey",
    "HybridPrivateKey",
    "HybridCiphertext",
    "KEMKeyPair",
    "KEMPublicKey",
    "KEMPrivateKey",
    "KEMCiphertext",
    "KEMAlgorithm",
    "PQSecurityStatus",
    "is_pq_available",
    "get_pq_status",
    "create_hybrid_kem",
    "create_key_exchange",
    "serialize_hybrid_public_key",
    "deserialize_hybrid_public_key",
]
