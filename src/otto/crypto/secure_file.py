"""
Secure File Operations
======================

Encrypted file I/O with memory-only decryption.

Determinism:
- FIXED file format (header + encrypted blob)
- DETERMINISTIC operations
- BOUNDED memory usage

Security Properties:
- Decrypted data NEVER written to disk
- Atomic writes (temp file + rename)
- Secure file permissions (0600)

File Format:
┌────────────────────────────────────────────────────────────┐
│ Magic     │ Version │ Salt    │ KDF Params │ Encrypted   │
│ 4 bytes   │ 1 byte  │ 32 bytes│ JSON       │ Blob        │
└────────────────────────────────────────────────────────────┘

Usage:
    from otto.crypto import encrypt_file, decrypt_file_to_memory

    # Encrypt file
    encrypt_file(data, path, password)

    # Decrypt to memory only
    plaintext = decrypt_file_to_memory(path, password)
"""

import os
import json
import stat
import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union

from .encryption import (
    encrypt_data,
    decrypt_data,
    EncryptedBlob,
    EncryptionError,
    DecryptionError,
)
from .key_derivation import (
    derive_key,
    generate_salt,
    KeyDerivationParams,
    DEFAULT_PARAMS,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED - ThinkingMachines compliant)
# =============================================================================

MAGIC = b"OTTO"  # File magic bytes
FORMAT_VERSION = 0x01
HEADER_SIZE = 4 + 1 + 32  # magic + version + salt = 37 bytes


# =============================================================================
# Exceptions
# =============================================================================

class SecureFileError(Exception):
    """Base exception for secure file operations."""
    pass


class InvalidFileFormat(SecureFileError):
    """Raised when file format is invalid."""
    pass


class FileIntegrityError(SecureFileError):
    """Raised when file integrity check fails."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class SecureFileHeader:
    """
    Header for encrypted files.

    Contains metadata needed for decryption (except password).
    """
    magic: bytes
    version: int
    salt: bytes
    kdf_params: KeyDerivationParams

    def to_bytes(self) -> bytes:
        """Serialize header to bytes."""
        params_json = json.dumps(self.kdf_params.to_dict()).encode("utf-8")
        params_len = len(params_json).to_bytes(2, "big")

        return (
            self.magic +
            bytes([self.version]) +
            self.salt +
            params_len +
            params_json
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> tuple["SecureFileHeader", int]:
        """
        Deserialize header from bytes.

        Returns:
            Tuple of (header, bytes_consumed)
        """
        if len(data) < HEADER_SIZE + 2:
            raise InvalidFileFormat("File too short")

        magic = data[0:4]
        if magic != MAGIC:
            raise InvalidFileFormat(f"Invalid magic bytes: {magic!r}")

        version = data[4]
        if version != FORMAT_VERSION:
            raise InvalidFileFormat(f"Unsupported format version: {version}")

        salt = data[5:37]
        params_len = int.from_bytes(data[37:39], "big")

        if len(data) < HEADER_SIZE + 2 + params_len:
            raise InvalidFileFormat("File truncated in header")

        params_json = data[39:39 + params_len]
        try:
            params_dict = json.loads(params_json.decode("utf-8"))
            kdf_params = KeyDerivationParams.from_dict(params_dict)
        except Exception as e:
            raise InvalidFileFormat(f"Invalid KDF params: {e}")

        header = cls(
            magic=magic,
            version=version,
            salt=salt,
            kdf_params=kdf_params,
        )

        bytes_consumed = 39 + params_len
        return header, bytes_consumed


# =============================================================================
# SecureFile Class
# =============================================================================

class SecureFile:
    """
    Context manager for secure file operations.

    Provides memory-only access to encrypted file content.

    Example:
        with SecureFile(path, password) as sf:
            data = sf.read()
            # Process data in memory
        # Data is automatically cleared when exiting context
    """

    def __init__(self, path: Union[str, Path], password: str):
        """
        Initialize secure file.

        Args:
            path: Path to encrypted file
            password: Decryption password
        """
        self.path = Path(path)
        self._password = password
        self._data: Optional[bytearray] = None
        self._header: Optional[SecureFileHeader] = None

    def __enter__(self) -> "SecureFile":
        """Enter context, decrypt file to memory."""
        self._data = bytearray(self._decrypt())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context, securely clear memory."""
        if self._data is not None:
            # Zero out the data
            for i in range(len(self._data)):
                self._data[i] = 0
            self._data = None
        return False

    def read(self) -> bytes:
        """
        Read decrypted content.

        Returns:
            Decrypted bytes

        Raises:
            SecureFileError: If not in context
        """
        if self._data is None:
            raise SecureFileError("Must use within 'with' context")
        return bytes(self._data)

    def read_text(self, encoding: str = "utf-8") -> str:
        """
        Read decrypted content as text.

        Args:
            encoding: Text encoding

        Returns:
            Decrypted string
        """
        return self.read().decode(encoding)

    def _decrypt(self) -> bytes:
        """Decrypt file content."""
        if not self.path.exists():
            raise SecureFileError(f"File not found: {self.path}")

        with open(self.path, "rb") as f:
            file_data = f.read()

        # Parse header
        self._header, header_size = SecureFileHeader.from_bytes(file_data)

        # Derive key
        key = derive_key(
            self._password,
            self._header.salt,
            self._header.kdf_params,
        )

        # Parse and decrypt blob
        encrypted_data = file_data[header_size:]
        blob = EncryptedBlob.from_bytes(encrypted_data)

        try:
            return decrypt_data(blob, key)
        except DecryptionError as e:
            raise FileIntegrityError(f"Decryption failed: {e}")


# =============================================================================
# File Operations
# =============================================================================

def encrypt_file(
    data: bytes,
    path: Union[str, Path],
    password: str,
    kdf_params: KeyDerivationParams = DEFAULT_PARAMS,
    atomic: bool = True,
) -> None:
    """
    Encrypt data and write to file.

    Args:
        data: Plaintext data to encrypt
        path: Output file path
        password: Encryption password
        kdf_params: Key derivation parameters
        atomic: Use atomic write (temp file + rename)

    Raises:
        SecureFileError: If write fails
        EncryptionError: If encryption fails
    """
    path = Path(path)

    # Generate salt
    salt = generate_salt()

    # Derive key
    key = derive_key(password, salt, kdf_params)

    # Encrypt data
    blob = encrypt_data(data, key)

    # Create header
    header = SecureFileHeader(
        magic=MAGIC,
        version=FORMAT_VERSION,
        salt=salt,
        kdf_params=kdf_params,
    )

    # Combine header and encrypted data
    file_data = header.to_bytes() + blob.to_bytes()

    # Write file
    if atomic:
        _atomic_write(path, file_data)
    else:
        _direct_write(path, file_data)

    logger.info(f"Encrypted file written: {path}")


def decrypt_file_to_memory(
    path: Union[str, Path],
    password: str,
) -> bytes:
    """
    Decrypt file content to memory only.

    IMPORTANT: Decrypted data is NEVER written to disk.

    Args:
        path: Path to encrypted file
        password: Decryption password

    Returns:
        Decrypted bytes

    Raises:
        SecureFileError: If file not found or format invalid
        FileIntegrityError: If decryption fails
    """
    path = Path(path)

    if not path.exists():
        raise SecureFileError(f"File not found: {path}")

    with open(path, "rb") as f:
        file_data = f.read()

    # Parse header
    header, header_size = SecureFileHeader.from_bytes(file_data)

    # Derive key
    key = derive_key(password, header.salt, header.kdf_params)

    # Parse and decrypt blob
    encrypted_data = file_data[header_size:]
    blob = EncryptedBlob.from_bytes(encrypted_data)

    try:
        return decrypt_data(blob, key)
    except DecryptionError as e:
        raise FileIntegrityError(f"Decryption failed: {e}")


def encrypt_text_file(
    text: str,
    path: Union[str, Path],
    password: str,
    encoding: str = "utf-8",
) -> None:
    """
    Encrypt text and write to file.

    Convenience wrapper for encrypt_file.

    Args:
        text: Plaintext string
        path: Output file path
        password: Encryption password
        encoding: Text encoding
    """
    encrypt_file(text.encode(encoding), path, password)


def is_encrypted_file(path: Union[str, Path]) -> bool:
    """
    Check if file is an OTTO encrypted file.

    Args:
        path: File path

    Returns:
        True if file has OTTO magic bytes
    """
    path = Path(path)

    if not path.exists():
        return False

    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            return magic == MAGIC
    except Exception:
        return False


# =============================================================================
# Internal Helpers
# =============================================================================

def _atomic_write(path: Path, data: bytes) -> None:
    """
    Write file atomically using temp file + rename.

    Args:
        path: Target file path
        data: Data to write
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory
    fd, temp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=".otto_",
        suffix=".tmp",
    )

    try:
        os.write(fd, data)
        os.close(fd)

        # Set secure permissions (owner read/write only)
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)

        # Atomic rename
        os.replace(temp_path, path)

    except Exception as e:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        raise SecureFileError(f"Failed to write file: {e}")


def _direct_write(path: Path, data: bytes) -> None:
    """
    Write file directly (non-atomic).

    Args:
        path: Target file path
        data: Data to write
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        f.write(data)

    # Set secure permissions
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


__all__ = [
    "SecureFile",
    "SecureFileHeader",
    "SecureFileError",
    "InvalidFileFormat",
    "FileIntegrityError",
    "encrypt_file",
    "decrypt_file_to_memory",
    "encrypt_text_file",
    "is_encrypted_file",
    "MAGIC",
    "FORMAT_VERSION",
]
