"""
Storage Adapter Interface
=========================

Abstract interface for cloud storage backends.

Determinism:
- FIXED chunk size (5 MiB)
- FIXED retry limits (3 attempts)
- DETERMINISTIC file naming (content-addressed)

Supported Backends:
- WebDAV (Nextcloud, ownCloud, etc.)
- Dropbox (future)
- Google Drive (future)
- Local filesystem (for testing)

Usage:
    adapter = create_storage_adapter("webdav", endpoint="https://...")
    await adapter.connect()
    await adapter.upload("path/to/file.enc", encrypted_data)
    data = await adapter.download("path/to/file.enc")
"""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Optional, Union

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED)
# =============================================================================

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MiB
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
OTTO_FOLDER = ".otto-sync"  # Remote folder for OTTO data


# =============================================================================
# Exceptions
# =============================================================================

class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class AuthenticationError(StorageError):
    """Raised when authentication fails."""
    pass


class QuotaExceededError(StorageError):
    """Raised when storage quota is exceeded."""
    pass


class FileNotFoundError(StorageError):
    """Raised when file is not found."""
    pass


class ConnectionError(StorageError):
    """Raised when connection fails."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

class StorageType(Enum):
    """Supported storage backend types."""
    LOCAL = "local"
    WEBDAV = "webdav"
    DROPBOX = "dropbox"
    GDRIVE = "gdrive"


@dataclass
class StorageInfo:
    """Information about storage backend."""
    storage_type: StorageType
    endpoint: Optional[str] = None
    username: Optional[str] = None
    connected: bool = False
    quota_total: Optional[int] = None
    quota_used: Optional[int] = None
    last_sync: Optional[datetime] = None


@dataclass
class RemoteFile:
    """Metadata for a remote file."""
    path: str
    size: int
    modified: datetime
    etag: Optional[str] = None
    content_hash: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "path": self.path,
            "size": self.size,
            "modified": self.modified.isoformat(),
            "etag": self.etag,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RemoteFile":
        """Deserialize from dictionary."""
        return cls(
            path=data["path"],
            size=data["size"],
            modified=datetime.fromisoformat(data["modified"]),
            etag=data.get("etag"),
            content_hash=data.get("content_hash"),
        )


# =============================================================================
# Abstract Storage Adapter
# =============================================================================

class StorageAdapter(ABC):
    """
    Abstract base class for cloud storage backends.

    All operations are async for non-blocking I/O.

    Determinism:
    - FIXED chunk size for uploads
    - FIXED retry policy
    - DETERMINISTIC file naming via content hash
    """

    def __init__(self, storage_type: StorageType):
        """
        Initialize storage adapter.

        Args:
            storage_type: Type of storage backend
        """
        self.storage_type = storage_type
        self._connected = False
        self._info = StorageInfo(storage_type=storage_type)

    @property
    def connected(self) -> bool:
        """Check if connected to storage."""
        return self._connected

    @property
    def info(self) -> StorageInfo:
        """Get storage information."""
        return self._info

    # =========================================================================
    # Abstract Methods (Must Implement)
    # =========================================================================

    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to storage backend.

        Raises:
            AuthenticationError: If authentication fails
            ConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from storage backend."""
        pass

    @abstractmethod
    async def upload(self, remote_path: str, data: bytes) -> RemoteFile:
        """
        Upload data to storage.

        Args:
            remote_path: Path on remote storage
            data: Data to upload (already encrypted)

        Returns:
            RemoteFile with upload metadata

        Raises:
            StorageError: If upload fails
            QuotaExceededError: If quota exceeded
        """
        pass

    @abstractmethod
    async def download(self, remote_path: str) -> bytes:
        """
        Download data from storage.

        Args:
            remote_path: Path on remote storage

        Returns:
            Downloaded data (still encrypted)

        Raises:
            FileNotFoundError: If file not found
            StorageError: If download fails
        """
        pass

    @abstractmethod
    async def delete(self, remote_path: str) -> None:
        """
        Delete file from storage.

        Args:
            remote_path: Path on remote storage

        Raises:
            FileNotFoundError: If file not found
            StorageError: If delete fails
        """
        pass

    @abstractmethod
    async def list_files(self, remote_path: str = "") -> list[RemoteFile]:
        """
        List files in directory.

        Args:
            remote_path: Directory path (empty for root)

        Returns:
            List of RemoteFile objects

        Raises:
            StorageError: If list fails
        """
        pass

    @abstractmethod
    async def exists(self, remote_path: str) -> bool:
        """
        Check if file exists.

        Args:
            remote_path: Path on remote storage

        Returns:
            True if file exists
        """
        pass

    @abstractmethod
    async def get_file_info(self, remote_path: str) -> RemoteFile:
        """
        Get file metadata.

        Args:
            remote_path: Path on remote storage

        Returns:
            RemoteFile with metadata

        Raises:
            FileNotFoundError: If file not found
        """
        pass

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_otto_path(self, relative_path: str) -> str:
        """
        Get full path within OTTO sync folder.

        Args:
            relative_path: Path relative to OTTO folder

        Returns:
            Full remote path
        """
        if relative_path.startswith("/"):
            relative_path = relative_path[1:]
        return f"{OTTO_FOLDER}/{relative_path}"

    @staticmethod
    def compute_content_hash(data: bytes) -> str:
        """
        Compute content hash for data.

        Uses SHA-256 for content addressing.

        Args:
            data: Data to hash

        Returns:
            Hex-encoded hash
        """
        return hashlib.sha256(data).hexdigest()

    async def upload_with_retry(
        self,
        remote_path: str,
        data: bytes,
        max_retries: int = MAX_RETRIES,
    ) -> RemoteFile:
        """
        Upload with automatic retry.

        Args:
            remote_path: Path on remote storage
            data: Data to upload
            max_retries: Maximum retry attempts

        Returns:
            RemoteFile with upload metadata

        Raises:
            StorageError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.upload(remote_path, data)
            except QuotaExceededError:
                raise  # Don't retry quota errors
            except StorageError as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = RETRY_DELAY_SECONDS * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Upload failed, retry {attempt + 1}/{max_retries} in {delay}s: {e}")
                    await asyncio.sleep(delay)

        raise StorageError(f"Upload failed after {max_retries} attempts: {last_error}")

    async def download_with_retry(
        self,
        remote_path: str,
        max_retries: int = MAX_RETRIES,
    ) -> bytes:
        """
        Download with automatic retry.

        Args:
            remote_path: Path on remote storage
            max_retries: Maximum retry attempts

        Returns:
            Downloaded data

        Raises:
            StorageError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.download(remote_path)
            except FileNotFoundError:
                raise  # Don't retry not found
            except StorageError as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                    logger.warning(f"Download failed, retry {attempt + 1}/{max_retries} in {delay}s: {e}")
                    await asyncio.sleep(delay)

        raise StorageError(f"Download failed after {max_retries} attempts: {last_error}")


# =============================================================================
# Local Storage Adapter (For Testing)
# =============================================================================

class LocalStorageAdapter(StorageAdapter):
    """
    Local filesystem storage adapter for testing.

    Simulates cloud storage behavior using local filesystem.
    """

    def __init__(self, base_path: Union[str, Path]):
        """
        Initialize local storage adapter.

        Args:
            base_path: Base directory for storage
        """
        super().__init__(StorageType.LOCAL)
        self.base_path = Path(base_path)
        self._info.endpoint = str(base_path)

    async def connect(self) -> None:
        """Connect (create base directory)."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        otto_path = self.base_path / OTTO_FOLDER
        otto_path.mkdir(exist_ok=True)
        self._connected = True
        self._info.connected = True
        logger.info(f"Connected to local storage: {self.base_path}")

    async def disconnect(self) -> None:
        """Disconnect (no-op for local)."""
        self._connected = False
        self._info.connected = False

    async def upload(self, remote_path: str, data: bytes) -> RemoteFile:
        """Upload data to local filesystem."""
        if not self._connected:
            raise ConnectionError("Not connected")

        full_path = self.base_path / remote_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        full_path.write_bytes(data)

        stat = full_path.stat()
        return RemoteFile(
            path=remote_path,
            size=len(data),
            modified=datetime.fromtimestamp(stat.st_mtime),
            content_hash=self.compute_content_hash(data),
        )

    async def download(self, remote_path: str) -> bytes:
        """Download data from local filesystem."""
        if not self._connected:
            raise ConnectionError("Not connected")

        full_path = self.base_path / remote_path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {remote_path}")

        return full_path.read_bytes()

    async def delete(self, remote_path: str) -> None:
        """Delete file from local filesystem."""
        if not self._connected:
            raise ConnectionError("Not connected")

        full_path = self.base_path / remote_path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {remote_path}")

        full_path.unlink()

    async def list_files(self, remote_path: str = "") -> list[RemoteFile]:
        """List files in directory."""
        if not self._connected:
            raise ConnectionError("Not connected")

        dir_path = self.base_path / remote_path if remote_path else self.base_path
        files = []

        if dir_path.exists():
            for item in dir_path.rglob("*"):
                if item.is_file():
                    rel_path = str(item.relative_to(self.base_path))
                    stat = item.stat()
                    files.append(RemoteFile(
                        path=rel_path,
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                    ))

        return files

    async def exists(self, remote_path: str) -> bool:
        """Check if file exists."""
        full_path = self.base_path / remote_path
        return full_path.exists()

    async def get_file_info(self, remote_path: str) -> RemoteFile:
        """Get file metadata."""
        full_path = self.base_path / remote_path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {remote_path}")

        stat = full_path.stat()
        data = full_path.read_bytes()

        return RemoteFile(
            path=remote_path,
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime),
            content_hash=self.compute_content_hash(data),
        )


# =============================================================================
# Factory Function
# =============================================================================

def create_storage_adapter(
    storage_type: str,
    **kwargs,
) -> StorageAdapter:
    """
    Create storage adapter by type.

    Args:
        storage_type: Type of storage ("local", "webdav", etc.)
        **kwargs: Backend-specific configuration

    Returns:
        StorageAdapter instance

    Raises:
        ValueError: If storage type not supported
    """
    storage_type = storage_type.lower()

    if storage_type == "local":
        if "base_path" not in kwargs:
            raise ValueError("local storage requires 'base_path'")
        return LocalStorageAdapter(kwargs["base_path"])

    elif storage_type == "webdav":
        from .adapters.webdav import WebDAVAdapter
        required = ["endpoint", "username", "password"]
        for req in required:
            if req not in kwargs:
                raise ValueError(f"webdav storage requires '{req}'")
        return WebDAVAdapter(
            endpoint=kwargs["endpoint"],
            username=kwargs["username"],
            password=kwargs["password"],
            verify_ssl=kwargs.get("verify_ssl", True),
            timeout=kwargs.get("timeout", 30),
        )

    elif storage_type == "s3":
        from .adapters.s3 import S3Adapter
        required = ["bucket", "access_key", "secret_key"]
        for req in required:
            if req not in kwargs:
                raise ValueError(f"s3 storage requires '{req}'")
        return S3Adapter(
            bucket=kwargs["bucket"],
            access_key=kwargs["access_key"],
            secret_key=kwargs["secret_key"],
            region=kwargs.get("region", "us-east-1"),
            endpoint=kwargs.get("endpoint"),
            use_ssl=kwargs.get("use_ssl", True),
            timeout=kwargs.get("timeout", 30),
        )

    elif storage_type == "dropbox":
        raise NotImplementedError("Dropbox adapter not yet implemented")

    elif storage_type == "gdrive":
        raise NotImplementedError("Google Drive adapter not yet implemented")

    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


__all__ = [
    "StorageAdapter",
    "LocalStorageAdapter",
    "StorageType",
    "StorageInfo",
    "RemoteFile",
    "StorageError",
    "AuthenticationError",
    "QuotaExceededError",
    "FileNotFoundError",
    "ConnectionError",
    "create_storage_adapter",
    "CHUNK_SIZE",
    "MAX_RETRIES",
    "OTTO_FOLDER",
]
