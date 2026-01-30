"""
File Encryption Module
======================

Handles encryption/decryption of files on disk.

Encrypted files have the .enc extension added:
    calibration.usda -> calibration.usda.enc

File format:
    [version: 1 byte][salt: 16 bytes][nonce: 12 bytes][ciphertext][tag: 16 bytes]

Design principles:
- Files are decrypted to memory only (never written decrypted to disk)
- Original files are securely deleted after encryption
- Atomic operations prevent partial writes
"""

import os
import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union, List

from .cipher import AESGCMCipher, EncryptedData, DecryptionError, EncryptionError
from .key_derivation import SALT_LENGTH

logger = logging.getLogger(__name__)


# Constants
FILE_VERSION = 1
ENCRYPTED_EXTENSION = ".enc"
VERSION_LENGTH = 1


class FileEncryptionError(Exception):
    """Base exception for file encryption operations."""
    pass


class FileNotEncryptedError(FileEncryptionError):
    """Raised when trying to decrypt an unencrypted file."""
    pass


class FileAlreadyEncryptedError(FileEncryptionError):
    """Raised when trying to encrypt an already encrypted file."""
    pass


@dataclass
class EncryptedFileHeader:
    """
    Header of an encrypted file.

    Attributes:
        version: File format version
        salt: Salt used for key derivation (if passphrase-based)
    """
    version: int
    salt: bytes

    def to_bytes(self) -> bytes:
        """Serialize header to bytes."""
        return bytes([self.version]) + self.salt

    @classmethod
    def from_bytes(cls, data: bytes) -> 'EncryptedFileHeader':
        """Deserialize header from bytes."""
        if len(data) < VERSION_LENGTH + SALT_LENGTH:
            raise FileEncryptionError("Invalid encrypted file header")

        version = data[0]
        salt = data[VERSION_LENGTH:VERSION_LENGTH + SALT_LENGTH]

        return cls(version=version, salt=salt)

    @classmethod
    def header_size(cls) -> int:
        """Get total header size in bytes."""
        return VERSION_LENGTH + SALT_LENGTH


class FileEncryptor:
    """
    Encrypts and decrypts files using AES-256-GCM.

    Example:
        >>> encryptor = FileEncryptor(key)
        >>> encryptor.encrypt_file(Path("secret.txt"))
        >>> # Creates secret.txt.enc, removes secret.txt
        >>> content = encryptor.decrypt_file_to_memory(Path("secret.txt.enc"))
    """

    def __init__(self, key: bytes, salt: bytes):
        """
        Initialize file encryptor.

        Args:
            key: 32-byte encryption key
            salt: Salt that was used to derive the key (stored in file header)
        """
        self._cipher = AESGCMCipher(key)
        self._salt = salt

    def encrypt_file(
        self,
        source: Path,
        dest: Optional[Path] = None,
        delete_original: bool = True,
    ) -> Path:
        """
        Encrypt a file.

        Args:
            source: Path to file to encrypt
            dest: Destination path (default: source + .enc)
            delete_original: Whether to securely delete the original

        Returns:
            Path to encrypted file

        Raises:
            FileEncryptionError: If encryption fails
            FileNotFoundError: If source file doesn't exist
            FileAlreadyEncryptedError: If file is already encrypted
        """
        source = Path(source)

        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")

        if source.suffix == ENCRYPTED_EXTENSION:
            raise FileAlreadyEncryptedError(f"File is already encrypted: {source}")

        if dest is None:
            dest = source.with_suffix(source.suffix + ENCRYPTED_EXTENSION)

        dest = Path(dest)

        try:
            # Read original file
            plaintext = source.read_bytes()
            logger.debug(f"Read {len(plaintext)} bytes from {source}")

            # Create header
            header = EncryptedFileHeader(version=FILE_VERSION, salt=self._salt)

            # Encrypt content
            encrypted = self._cipher.encrypt(plaintext)

            # Write encrypted file atomically
            encrypted_data = header.to_bytes() + encrypted.to_bytes()
            self._atomic_write(dest, encrypted_data)

            logger.info(f"Encrypted {source} -> {dest}")

            # Securely delete original
            if delete_original:
                self._secure_delete(source)

            return dest

        except Exception as e:
            logger.error(f"Failed to encrypt {source}: {e}")
            raise FileEncryptionError(f"Encryption failed: {e}") from e

    def decrypt_file_to_memory(self, source: Path) -> bytes:
        """
        Decrypt a file to memory.

        The decrypted content is NEVER written to disk.

        Args:
            source: Path to encrypted file

        Returns:
            Decrypted content as bytes

        Raises:
            FileEncryptionError: If decryption fails
            FileNotEncryptedError: If file is not encrypted
        """
        source = Path(source)

        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")

        if source.suffix != ENCRYPTED_EXTENSION:
            raise FileNotEncryptedError(f"File is not encrypted: {source}")

        try:
            # Read encrypted file
            data = source.read_bytes()
            logger.debug(f"Read {len(data)} bytes from {source}")

            # Parse header
            header_size = EncryptedFileHeader.header_size()
            if len(data) < header_size:
                raise FileEncryptionError("File too small to be encrypted")

            header = EncryptedFileHeader.from_bytes(data[:header_size])

            if header.version != FILE_VERSION:
                raise FileEncryptionError(
                    f"Unsupported file version: {header.version}"
                )

            # Decrypt content
            encrypted = EncryptedData.from_bytes(data[header_size:])
            plaintext = self._cipher.decrypt(encrypted)

            logger.info(f"Decrypted {source} ({len(plaintext)} bytes)")
            return plaintext

        except DecryptionError:
            raise
        except Exception as e:
            logger.error(f"Failed to decrypt {source}: {e}")
            raise FileEncryptionError(f"Decryption failed: {e}") from e

    def decrypt_file_to_string(
        self,
        source: Path,
        encoding: str = 'utf-8'
    ) -> str:
        """
        Decrypt a file to a string.

        Args:
            source: Path to encrypted file
            encoding: Text encoding (default: utf-8)

        Returns:
            Decrypted content as string
        """
        return self.decrypt_file_to_memory(source).decode(encoding)

    def _atomic_write(self, dest: Path, data: bytes) -> None:
        """Write file atomically using temp file + rename."""
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (for atomic rename)
        fd, temp_path = tempfile.mkstemp(
            dir=dest.parent,
            prefix='.otto_enc_',
            suffix='.tmp'
        )
        try:
            os.write(fd, data)
            os.close(fd)

            # Atomic rename
            Path(temp_path).replace(dest)

        except Exception:
            # Clean up temp file on failure
            try:
                os.close(fd)
            except Exception:
                pass
            try:
                os.unlink(temp_path)
            except Exception:
                pass
            raise

    def _secure_delete(self, path: Path) -> None:
        """
        Securely delete a file.

        Overwrites with random data before unlinking.
        Note: SSDs may retain data in wear-leveling areas.
        """
        try:
            size = path.stat().st_size

            # Overwrite with random data
            with open(path, 'wb') as f:
                f.write(os.urandom(size))
                f.flush()
                os.fsync(f.fileno())

            # Delete
            path.unlink()
            logger.debug(f"Securely deleted {path}")

        except Exception as e:
            logger.warning(f"Secure delete failed, falling back to normal delete: {e}")
            try:
                path.unlink()
            except Exception:
                pass


def get_encrypted_path(path: Path) -> Path:
    """Get the encrypted version path of a file."""
    return path.with_suffix(path.suffix + ENCRYPTED_EXTENSION)


def get_decrypted_path(path: Path) -> Path:
    """Get the decrypted version path of an encrypted file."""
    if path.suffix != ENCRYPTED_EXTENSION:
        raise ValueError(f"Not an encrypted file: {path}")
    return Path(str(path)[:-len(ENCRYPTED_EXTENSION)])


def is_encrypted_file(path: Path) -> bool:
    """Check if a file is encrypted."""
    return path.suffix == ENCRYPTED_EXTENSION


def find_encrypted_files(directory: Path, recursive: bool = True) -> List[Path]:
    """
    Find all encrypted files in a directory.

    Args:
        directory: Directory to search
        recursive: Whether to search subdirectories

    Returns:
        List of encrypted file paths
    """
    pattern = f"**/*{ENCRYPTED_EXTENSION}" if recursive else f"*{ENCRYPTED_EXTENSION}"
    return list(directory.glob(pattern))


def find_files_to_encrypt(
    directory: Path,
    patterns: List[str] = None,
    recursive: bool = True,
) -> List[Path]:
    """
    Find files that should be encrypted.

    Args:
        directory: Directory to search
        patterns: File patterns to match (default: common sensitive patterns)
        recursive: Whether to search subdirectories

    Returns:
        List of file paths that should be encrypted
    """
    if patterns is None:
        patterns = [
            "*.usda",       # USD ASCII files (calibration, knowledge)
            "*.json",       # JSON config files
            "session_*.md", # Session files
        ]

    files = []
    for pattern in patterns:
        full_pattern = f"**/{pattern}" if recursive else pattern
        for path in directory.glob(full_pattern):
            # Skip already encrypted files
            if not is_encrypted_file(path):
                files.append(path)

    return files


__all__ = [
    'FileEncryptor',
    'EncryptedFileHeader',
    'FileEncryptionError',
    'FileNotEncryptedError',
    'FileAlreadyEncryptedError',
    'get_encrypted_path',
    'get_decrypted_path',
    'is_encrypted_file',
    'find_encrypted_files',
    'find_files_to_encrypt',
    'ENCRYPTED_EXTENSION',
    'FILE_VERSION',
]
