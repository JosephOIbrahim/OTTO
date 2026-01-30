"""
Encryption Manager
==================

Orchestrates all encryption operations for OTTO OS.

Responsibilities:
- Initial encryption setup (create keys, encrypt files)
- Unlock (derive key from passphrase)
- Lock (clear key from memory)
- Recovery (use recovery key to access data)
- Status reporting

Usage:
    manager = EncryptionManager(otto_dir)
    if not manager.is_setup():
        recovery_key = manager.setup("my-passphrase")
        print(f"Save this: {recovery_key}")
    else:
        manager.unlock("my-passphrase")
        content = manager.read_encrypted("calibration.usda")
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .key_derivation import (
    derive_key,
    generate_recovery_key,
    recovery_key_to_words,
    words_to_recovery_key,
    derive_key_from_recovery,
    validate_passphrase_strength,
    DerivedKey,
    KeyDerivationError,
)
from .cipher import AESGCMCipher, encrypt_bytes, decrypt_bytes, DecryptionError
from .keyring_store import KeyringStore, is_keyring_available, KeyringStoreError
from .file_encryption import (
    FileEncryptor,
    get_encrypted_path,
    is_encrypted_file,
    find_files_to_encrypt,
    find_encrypted_files,
    FileEncryptionError,
)

logger = logging.getLogger(__name__)


# Files that should be encrypted (relative to otto_dir)
SENSITIVE_FILES = [
    "calibration/calibration.json",
    "calibration/outcomes.json",
    "calibration/learned_weights.json",
    "sessions/",  # All session files
    "knowledge/personal.usda",
]


class EncryptionManagerError(Exception):
    """Base exception for encryption manager."""
    pass


class NotSetupError(EncryptionManagerError):
    """Raised when encryption is not set up."""
    pass


class NotUnlockedError(EncryptionManagerError):
    """Raised when encryption is locked."""
    pass


class AlreadySetupError(EncryptionManagerError):
    """Raised when encryption is already set up."""
    pass


class InvalidPassphraseError(EncryptionManagerError):
    """Raised when passphrase is invalid."""
    pass


@dataclass
class EncryptionStatus:
    """
    Current encryption status.

    Attributes:
        is_setup: Whether encryption has been configured
        is_unlocked: Whether encryption is currently unlocked
        encrypted_file_count: Number of encrypted files
        pending_encryption: Files that should be encrypted
        keyring_available: Whether OS keyring is available
        last_unlock: Timestamp of last unlock (if any)
    """
    is_setup: bool = False
    is_unlocked: bool = False
    encrypted_file_count: int = 0
    pending_encryption: List[str] = field(default_factory=list)
    keyring_available: bool = False
    last_unlock: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_setup": self.is_setup,
            "is_unlocked": self.is_unlocked,
            "encrypted_file_count": self.encrypted_file_count,
            "pending_encryption": self.pending_encryption,
            "keyring_available": self.keyring_available,
            "last_unlock": self.last_unlock,
        }


class EncryptionManager:
    """
    Manages all encryption operations for OTTO OS.

    Lifecycle:
    1. setup() - First-time configuration, returns recovery key
    2. unlock() - Derive key from passphrase, enable decryption
    3. read_encrypted() / write_encrypted() - Work with encrypted files
    4. lock() - Clear key from memory
    """

    DEFAULT_DIR = Path.home() / ".otto"

    def __init__(self, otto_dir: Path = None):
        """
        Initialize encryption manager.

        Args:
            otto_dir: Base OTTO directory (default: ~/.otto)
        """
        self.otto_dir = otto_dir or self.DEFAULT_DIR
        self.otto_dir.mkdir(parents=True, exist_ok=True)

        # State
        self._key: Optional[bytes] = None
        self._salt: Optional[bytes] = None
        self._encryptor: Optional[FileEncryptor] = None

        # Keyring store (may fail if unavailable)
        self._keyring: Optional[KeyringStore] = None
        try:
            if is_keyring_available():
                self._keyring = KeyringStore()
        except Exception as e:
            logger.warning(f"Keyring unavailable: {e}")

        # Try to load salt from keyring
        if self._keyring and self._keyring.has_salt():
            self._salt = self._keyring.get_salt()

    # =========================================================================
    # Setup
    # =========================================================================

    def is_setup(self) -> bool:
        """Check if encryption has been configured."""
        # Primary check: look for the recovery key file (directory-specific)
        recovery_path = self.otto_dir / ".recovery_key.enc"
        if recovery_path.exists():
            return True

        # Secondary check: look for encrypted files
        if len(find_encrypted_files(self.otto_dir)) > 0:
            return True

        return False

    def setup(
        self,
        passphrase: str,
        encrypt_existing: bool = True,
        recovery_hint: str = None,
    ) -> str:
        """
        Set up encryption for the first time.

        Args:
            passphrase: User's encryption passphrase
            encrypt_existing: Whether to encrypt existing sensitive files
            recovery_hint: Optional hint about where recovery key is stored

        Returns:
            Recovery key as formatted string (MUST be shown to user)

        Raises:
            AlreadySetupError: If encryption is already configured
            InvalidPassphraseError: If passphrase is too weak
        """
        if self.is_setup():
            raise AlreadySetupError("Encryption is already configured")

        # Validate passphrase strength
        valid, message = validate_passphrase_strength(passphrase)
        if not valid:
            raise InvalidPassphraseError(message)

        # Generate master key (this IS the recovery key - it's the actual encryption key)
        master_key = generate_recovery_key()
        recovery_key_formatted = recovery_key_to_words(master_key)

        # Derive a passphrase key (used only to encrypt the master key)
        derived = derive_key(passphrase)
        self._salt = derived.salt

        # The master key is what encrypts files
        self._key = master_key
        self._encryptor = FileEncryptor(self._key, self._salt)

        # Store salt in keyring
        if self._keyring:
            self._keyring.store_salt(self._salt)
            self._keyring.set_encryption_enabled(True)
            self._keyring.mark_unlocked()
            if recovery_hint:
                self._keyring.store_recovery_hint(recovery_hint)

        # Store master key encrypted with the passphrase-derived key
        # This allows unlock via passphrase OR via recovery key
        self._store_encrypted_master_key(master_key, derived.key)

        # Encrypt existing sensitive files
        if encrypt_existing:
            self._encrypt_sensitive_files()

        logger.info("Encryption setup complete")
        return recovery_key_formatted

    def _store_encrypted_master_key(self, master_key: bytes, passphrase_key: bytes) -> None:
        """Store the master key encrypted with the passphrase-derived key."""
        encrypted = encrypt_bytes(passphrase_key, master_key)
        master_key_path = self.otto_dir / ".recovery_key.enc"
        master_key_path.write_bytes(encrypted)
        logger.debug("Stored encrypted master key")

    def _encrypt_sensitive_files(self) -> int:
        """Encrypt all sensitive files. Returns count."""
        count = 0
        for path in self._find_sensitive_files():
            try:
                self._encryptor.encrypt_file(path, delete_original=True)
                count += 1
            except FileEncryptionError as e:
                logger.warning(f"Failed to encrypt {path}: {e}")
        return count

    def _find_sensitive_files(self) -> List[Path]:
        """Find sensitive files that should be encrypted."""
        files = []
        for pattern in SENSITIVE_FILES:
            if pattern.endswith('/'):
                # Directory pattern
                dir_path = self.otto_dir / pattern.rstrip('/')
                if dir_path.exists():
                    files.extend(find_files_to_encrypt(dir_path, recursive=True))
            else:
                file_path = self.otto_dir / pattern
                if file_path.exists() and not is_encrypted_file(file_path):
                    files.append(file_path)
        return files

    # =========================================================================
    # Unlock / Lock
    # =========================================================================

    def is_unlocked(self) -> bool:
        """Check if encryption is currently unlocked."""
        return self._key is not None

    def unlock(self, passphrase: str) -> bool:
        """
        Unlock encryption using passphrase.

        Args:
            passphrase: User's encryption passphrase

        Returns:
            True if unlock successful

        Raises:
            NotSetupError: If encryption is not configured
            InvalidPassphraseError: If passphrase is wrong
        """
        if not self.is_setup():
            raise NotSetupError("Encryption is not configured")

        # Get salt
        salt = self._salt
        if salt is None and self._keyring:
            salt = self._keyring.get_salt()
        if salt is None:
            raise EncryptionManagerError("Cannot find encryption salt")

        # Derive passphrase key
        try:
            derived = derive_key(passphrase, salt=salt)
        except KeyDerivationError as e:
            raise InvalidPassphraseError(f"Key derivation failed: {e}") from e

        # Decrypt master key using passphrase-derived key
        try:
            master_key = self._decrypt_master_key(derived.key)
        except DecryptionError:
            raise InvalidPassphraseError("Invalid passphrase")

        # Success - use master key for file encryption
        self._key = master_key
        self._salt = derived.salt
        self._encryptor = FileEncryptor(self._key, self._salt)

        if self._keyring:
            self._keyring.mark_unlocked()

        logger.info("Encryption unlocked")
        return True

    def _decrypt_master_key(self, passphrase_key: bytes) -> bytes:
        """Decrypt the master key using passphrase-derived key."""
        master_key_path = self.otto_dir / ".recovery_key.enc"
        if not master_key_path.exists():
            raise EncryptionManagerError("Master key file not found")

        encrypted = master_key_path.read_bytes()
        # Will raise DecryptionError if passphrase is wrong
        return decrypt_bytes(passphrase_key, encrypted)

    def lock(self) -> None:
        """
        Lock encryption (clear key from memory).

        After locking, encrypted files cannot be accessed
        until unlock() is called again.
        """
        self._key = None
        self._encryptor = None
        logger.info("Encryption locked")

    # =========================================================================
    # Recovery
    # =========================================================================

    def unlock_with_recovery_key(self, recovery_key_formatted: str) -> bool:
        """
        Unlock using recovery key.

        Args:
            recovery_key_formatted: Recovery key as shown during setup

        Returns:
            True if unlock successful

        Raises:
            InvalidPassphraseError: If recovery key is invalid
        """
        try:
            recovery_key = words_to_recovery_key(recovery_key_formatted)
        except ValueError as e:
            raise InvalidPassphraseError(f"Invalid recovery key format: {e}") from e

        # Recovery key IS the master key - use it directly
        master_key = derive_key_from_recovery(recovery_key)

        # Verify by trying to decrypt a file or check the master key matches
        # The recovery key should work directly as it's the actual encryption key
        # We can't verify without trying to decrypt something

        # Get salt from keyring (needed for FileEncryptor but not for decryption)
        salt = self._salt or (self._keyring.get_salt() if self._keyring else None)
        if salt is None:
            # Recovery mode without salt - use zeros
            from .key_derivation import SALT_LENGTH
            salt = bytes(SALT_LENGTH)

        self._key = master_key
        self._salt = salt
        self._encryptor = FileEncryptor(self._key, self._salt)

        if self._keyring:
            self._keyring.mark_unlocked()

        logger.info("Encryption unlocked with recovery key")
        return True

    def change_passphrase(self, old_passphrase: str, new_passphrase: str) -> None:
        """
        Change the encryption passphrase.

        Files remain encrypted with the same key; only the key derivation
        salt changes.

        Args:
            old_passphrase: Current passphrase
            new_passphrase: New passphrase

        Raises:
            NotSetupError: If encryption is not configured
            InvalidPassphraseError: If old passphrase is wrong or new is weak
        """
        # Verify old passphrase (this sets self._key to the master key)
        self.unlock(old_passphrase)
        master_key = self._key  # Save the master key

        # Validate new passphrase
        valid, message = validate_passphrase_strength(new_passphrase)
        if not valid:
            raise InvalidPassphraseError(message)

        # Derive new passphrase key
        new_derived = derive_key(new_passphrase)

        # Re-encrypt master key with new passphrase-derived key
        self._store_encrypted_master_key(master_key, new_derived.key)

        # Update salt (the master key stays the same!)
        self._salt = new_derived.salt
        self._encryptor = FileEncryptor(self._key, self._salt)

        # Update keyring with new salt
        if self._keyring:
            self._keyring.store_salt(self._salt)
            self._keyring.mark_unlocked()

        logger.info("Passphrase changed successfully")

    # =========================================================================
    # File Operations
    # =========================================================================

    def read_encrypted(self, relative_path: str) -> bytes:
        """
        Read and decrypt a file.

        Args:
            relative_path: Path relative to otto_dir

        Returns:
            Decrypted content

        Raises:
            NotUnlockedError: If encryption is locked
            FileNotFoundError: If file doesn't exist
        """
        if not self.is_unlocked():
            raise NotUnlockedError("Encryption is locked")

        path = self.otto_dir / relative_path
        if not is_encrypted_file(path):
            path = get_encrypted_path(path)

        return self._encryptor.decrypt_file_to_memory(path)

    def read_encrypted_string(
        self,
        relative_path: str,
        encoding: str = 'utf-8'
    ) -> str:
        """Read and decrypt a file as string."""
        return self.read_encrypted(relative_path).decode(encoding)

    def write_encrypted(
        self,
        relative_path: str,
        content: bytes,
    ) -> Path:
        """
        Encrypt and write content to a file.

        Args:
            relative_path: Path relative to otto_dir (without .enc)
            content: Content to encrypt

        Returns:
            Path to encrypted file

        Raises:
            NotUnlockedError: If encryption is locked
        """
        if not self.is_unlocked():
            raise NotUnlockedError("Encryption is locked")

        # Write to temp file first
        path = self.otto_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write plaintext temporarily
        path.write_bytes(content)

        # Encrypt (which deletes the plaintext)
        return self._encryptor.encrypt_file(path, delete_original=True)

    def write_encrypted_string(
        self,
        relative_path: str,
        content: str,
        encoding: str = 'utf-8',
    ) -> Path:
        """Write string as encrypted file."""
        return self.write_encrypted(relative_path, content.encode(encoding))

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> EncryptionStatus:
        """Get current encryption status."""
        encrypted_files = find_encrypted_files(self.otto_dir)
        pending = self._find_sensitive_files() if self.is_unlocked() else []

        return EncryptionStatus(
            is_setup=self.is_setup(),
            is_unlocked=self.is_unlocked(),
            encrypted_file_count=len(encrypted_files),
            pending_encryption=[str(p) for p in pending],
            keyring_available=is_keyring_available(),
            last_unlock=self._keyring.get_last_unlock_time() if self._keyring else None,
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    def reset(self, confirm: bool = False) -> None:
        """
        Reset all encryption.

        WARNING: This will DELETE all encrypted data if not unlocked!

        Args:
            confirm: Must be True to proceed
        """
        if not confirm:
            raise EncryptionManagerError(
                "Must pass confirm=True to reset encryption"
            )

        # Clear keyring
        if self._keyring:
            self._keyring.clear_all()

        # Delete recovery key
        recovery_path = self.otto_dir / ".recovery_key.enc"
        if recovery_path.exists():
            recovery_path.unlink()

        # Clear state
        self._key = None
        self._salt = None
        self._encryptor = None

        logger.warning("Encryption has been reset")


def create_encryption_manager(otto_dir: Path = None) -> EncryptionManager:
    """Factory function to create an EncryptionManager."""
    return EncryptionManager(otto_dir)


__all__ = [
    'EncryptionManager',
    'EncryptionStatus',
    'EncryptionManagerError',
    'NotSetupError',
    'NotUnlockedError',
    'AlreadySetupError',
    'InvalidPassphraseError',
    'create_encryption_manager',
]
