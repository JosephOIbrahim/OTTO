"""
Sync Engine
===========

Orchestrates E2E encrypted synchronization between devices.

Determinism:
- FIXED sync protocol version
- DETERMINISTIC conflict resolution (configurable strategy)
- BOUNDED sync operations (max files per sync)

Sync Process:
1. Pull remote manifest
2. Decrypt manifest with user key
3. Compare with local manifest
4. Resolve conflicts
5. Upload changed files (encrypted)
6. Update and push manifest

Security:
- All data encrypted before leaving device
- Manifest encrypted (prevents metadata leakage)
- Content hashes verify integrity
"""

import asyncio
import logging
import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional, Set

from .storage_adapter import (
    StorageAdapter,
    StorageError,
    FileNotFoundError as SyncFileNotFoundError,
    OTTO_FOLDER,
)
from .manifest import (
    SyncManifest,
    FileEntry,
    ManifestError,
    MANIFEST_FILENAME,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED)
# =============================================================================

SYNC_PROTOCOL_VERSION = 1
MAX_FILES_PER_SYNC = 100  # Bounded sync operations
SYNC_TIMEOUT_SECONDS = 300  # 5 minutes


# =============================================================================
# Enums
# =============================================================================

class SyncStatus(Enum):
    """Sync operation status."""
    IDLE = "idle"
    CONNECTING = "connecting"
    PULLING = "pulling"
    COMPARING = "comparing"
    RESOLVING = "resolving"
    UPLOADING = "uploading"
    DOWNLOADING = "downloading"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


class ConflictResolution(Enum):
    """Conflict resolution strategies."""
    LAST_WRITE_WINS = "last_write_wins"
    KEEP_LOCAL = "keep_local"
    KEEP_REMOTE = "keep_remote"
    MANUAL = "manual"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class SyncConfig:
    """
    Configuration for sync engine.

    All parameters are FIXED at initialization.
    """
    local_data_path: Path
    encryption_key: bytes
    device_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    device_name: str = field(default_factory=platform.node)
    conflict_resolution: ConflictResolution = ConflictResolution.LAST_WRITE_WINS
    auto_sync_interval: int = 0  # 0 = manual sync only
    exclude_patterns: List[str] = field(default_factory=list)
    max_file_size: int = 50 * 1024 * 1024  # 50 MiB

    def to_dict(self) -> dict:
        """Serialize to dictionary (excluding key)."""
        return {
            "local_data_path": str(self.local_data_path),
            "device_id": self.device_id,
            "device_name": self.device_name,
            "conflict_resolution": self.conflict_resolution.value,
            "auto_sync_interval": self.auto_sync_interval,
            "exclude_patterns": self.exclude_patterns,
            "max_file_size": self.max_file_size,
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    status: SyncStatus
    uploaded: List[str] = field(default_factory=list)
    downloaded: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    started: datetime = field(default_factory=datetime.now)
    completed: Optional[datetime] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "status": self.status.value,
            "uploaded": self.uploaded,
            "downloaded": self.downloaded,
            "deleted": self.deleted,
            "conflicts": self.conflicts,
            "errors": self.errors,
            "started": self.started.isoformat(),
            "completed": self.completed.isoformat() if self.completed else None,
            "duration_seconds": self.duration_seconds,
        }


# =============================================================================
# Exceptions
# =============================================================================

class SyncError(Exception):
    """Base exception for sync operations."""
    pass


class SyncConflictError(SyncError):
    """Raised when conflicts require manual resolution."""

    def __init__(self, conflicts: List[str]):
        self.conflicts = conflicts
        super().__init__(f"Manual resolution required for {len(conflicts)} conflicts")


# =============================================================================
# SyncEngine
# =============================================================================

class SyncEngine:
    """
    Orchestrates E2E encrypted cloud synchronization.

    Determinism:
    - FIXED protocol version
    - DETERMINISTIC conflict resolution
    - BOUNDED operations per sync

    Usage:
        config = SyncConfig(
            local_data_path=Path("~/.otto"),
            encryption_key=key,
        )
        engine = SyncEngine(storage, config)

        result = await engine.sync()
        print(f"Uploaded: {len(result.uploaded)} files")
    """

    def __init__(
        self,
        storage: StorageAdapter,
        config: SyncConfig,
    ):
        """
        Initialize sync engine.

        Args:
            storage: Storage backend adapter
            config: Sync configuration
        """
        self.storage = storage
        self.config = config
        self._status = SyncStatus.IDLE
        self._local_manifest: Optional[SyncManifest] = None
        self._progress_callback: Optional[Callable] = None
        self._cancel_requested = False

    @property
    def status(self) -> SyncStatus:
        """Current sync status."""
        return self._status

    def on_progress(self, callback: Callable[[SyncStatus, str], None]) -> None:
        """
        Set progress callback.

        Args:
            callback: Function called with (status, message)
        """
        self._progress_callback = callback

    def cancel(self) -> None:
        """Request sync cancellation."""
        self._cancel_requested = True
        logger.info("Sync cancellation requested")

    # =========================================================================
    # Main Sync Operation
    # =========================================================================

    async def sync(self) -> SyncResult:
        """
        Perform full sync operation.

        Returns:
            SyncResult with details

        Raises:
            SyncError: If sync fails
            SyncConflictError: If manual resolution required
        """
        result = SyncResult(success=False, status=SyncStatus.IDLE)
        self._cancel_requested = False

        try:
            # Connect to storage
            self._update_status(SyncStatus.CONNECTING, "Connecting to storage...")
            if not self.storage.connected:
                await self.storage.connect()

            # Pull remote manifest
            self._update_status(SyncStatus.PULLING, "Pulling remote manifest...")
            remote_manifest = await self._pull_manifest()

            # Load or create local manifest
            local_manifest = await self._load_local_manifest()

            # Compare manifests
            self._update_status(SyncStatus.COMPARING, "Comparing files...")
            diff = local_manifest.diff(remote_manifest) if remote_manifest else {
                "added": [],
                "removed": [],
                "modified": [],
                "conflicts": [],
            }

            # Scan local files for changes
            local_changes = await self._scan_local_changes(local_manifest)

            # Handle conflicts
            if diff["conflicts"] and self.config.conflict_resolution == ConflictResolution.MANUAL:
                raise SyncConflictError(diff["conflicts"])

            # Resolve conflicts
            self._update_status(SyncStatus.RESOLVING, "Resolving conflicts...")
            if diff["conflicts"]:
                result.conflicts = diff["conflicts"]

            # Upload local changes
            self._update_status(SyncStatus.UPLOADING, "Uploading changes...")
            for path in local_changes[:MAX_FILES_PER_SYNC]:
                if self._cancel_requested:
                    break

                try:
                    await self._upload_file(path, local_manifest)
                    result.uploaded.append(path)
                except Exception as e:
                    result.errors.append(f"Upload {path}: {e}")
                    logger.error(f"Failed to upload {path}: {e}")

            # Download remote changes (files in remote but not local)
            self._update_status(SyncStatus.DOWNLOADING, "Downloading changes...")
            if remote_manifest:
                for path in diff["removed"][:MAX_FILES_PER_SYNC]:
                    if self._cancel_requested:
                        break

                    try:
                        await self._download_file(path, remote_manifest)
                        result.downloaded.append(path)
                    except Exception as e:
                        result.errors.append(f"Download {path}: {e}")
                        logger.error(f"Failed to download {path}: {e}")

            # Merge manifests
            if remote_manifest:
                conflicts = local_manifest.merge(
                    remote_manifest,
                    self.config.conflict_resolution.value,
                )
                result.conflicts.extend(conflicts)

            # Finalize
            self._update_status(SyncStatus.FINALIZING, "Finalizing...")
            await self._push_manifest(local_manifest)
            await self._save_local_manifest(local_manifest)

            # Complete
            result.success = len(result.errors) == 0
            result.status = SyncStatus.COMPLETE
            result.completed = datetime.now()
            result.duration_seconds = (result.completed - result.started).total_seconds()

            self._update_status(SyncStatus.COMPLETE, "Sync complete")
            logger.info(f"Sync complete: {len(result.uploaded)} up, {len(result.downloaded)} down")

        except SyncConflictError:
            raise
        except Exception as e:
            result.status = SyncStatus.ERROR
            result.errors.append(str(e))
            self._update_status(SyncStatus.ERROR, str(e))
            logger.error(f"Sync failed: {e}")
            raise SyncError(f"Sync failed: {e}")

        finally:
            self._status = SyncStatus.IDLE

        return result

    # =========================================================================
    # Manifest Operations
    # =========================================================================

    async def _pull_manifest(self) -> Optional[SyncManifest]:
        """Pull and decrypt remote manifest."""
        try:
            manifest_path = f"{OTTO_FOLDER}/{MANIFEST_FILENAME}"

            if not await self.storage.exists(manifest_path):
                logger.info("No remote manifest found, starting fresh")
                return None

            encrypted_data = await self.storage.download(manifest_path)

            # Decrypt manifest
            from ..crypto import decrypt_data, EncryptedBlob
            blob = EncryptedBlob.from_bytes(encrypted_data)
            decrypted = decrypt_data(blob, self.config.encryption_key)

            manifest = SyncManifest.from_bytes(decrypted)
            logger.info(f"Pulled manifest: {manifest.entry_count} entries")
            return manifest

        except SyncFileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to pull manifest: {e}")
            raise SyncError(f"Failed to pull manifest: {e}")

    async def _push_manifest(self, manifest: SyncManifest) -> None:
        """Encrypt and push manifest to remote."""
        try:
            manifest.update_device_sync_time()
            manifest_data = manifest.to_bytes()

            # Encrypt manifest
            from ..crypto import encrypt_data
            blob = encrypt_data(manifest_data, self.config.encryption_key)
            encrypted_data = blob.to_bytes()

            manifest_path = f"{OTTO_FOLDER}/{MANIFEST_FILENAME}"
            await self.storage.upload(manifest_path, encrypted_data)

            logger.info(f"Pushed manifest: {manifest.entry_count} entries")

        except Exception as e:
            logger.error(f"Failed to push manifest: {e}")
            raise SyncError(f"Failed to push manifest: {e}")

    async def _load_local_manifest(self) -> SyncManifest:
        """Load or create local manifest."""
        manifest_path = self.config.local_data_path / "sync_manifest.json"

        if manifest_path.exists():
            try:
                data = manifest_path.read_text()
                manifest = SyncManifest.from_json(data)
                logger.debug(f"Loaded local manifest: {manifest.entry_count} entries")
                return manifest
            except Exception as e:
                logger.warning(f"Failed to load local manifest: {e}")

        # Create new manifest
        manifest = SyncManifest(
            device_id=self.config.device_id,
            device_name=self.config.device_name,
            platform=platform.system().lower(),
        )
        self._local_manifest = manifest
        return manifest

    async def _save_local_manifest(self, manifest: SyncManifest) -> None:
        """Save manifest locally."""
        manifest_path = self.config.local_data_path / "sync_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(manifest.to_json(indent=2))

    # =========================================================================
    # File Operations
    # =========================================================================

    async def _scan_local_changes(self, manifest: SyncManifest) -> List[str]:
        """Scan local files for changes compared to manifest."""
        changes = []

        # Get syncable files
        syncable_files = self._get_syncable_files()

        for file_path in syncable_files:
            relative_path = str(file_path.relative_to(self.config.local_data_path))

            # Check if file is new or modified
            entry = manifest.get_entry(relative_path)
            if entry is None:
                changes.append(relative_path)
            else:
                # Check if content changed
                current_hash = self._compute_file_hash(file_path)
                if current_hash != entry.content_hash:
                    changes.append(relative_path)

        return changes

    def _get_syncable_files(self) -> List[Path]:
        """Get list of files to sync."""
        files = []
        data_path = self.config.local_data_path

        if not data_path.exists():
            return files

        for file_path in data_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip manifest
            if file_path.name == "sync_manifest.json":
                continue

            # Skip excluded patterns
            relative = str(file_path.relative_to(data_path))
            if self._is_excluded(relative):
                continue

            # Skip large files
            if file_path.stat().st_size > self.config.max_file_size:
                logger.warning(f"Skipping large file: {relative}")
                continue

            files.append(file_path)

        return files

    def _is_excluded(self, path: str) -> bool:
        """Check if path matches exclusion patterns."""
        import fnmatch
        for pattern in self.config.exclude_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file content."""
        import hashlib
        hasher = hashlib.sha256()

        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)

        return hasher.hexdigest()

    async def _upload_file(self, relative_path: str, manifest: SyncManifest) -> None:
        """Encrypt and upload a file."""
        from ..crypto import encrypt_data

        local_path = self.config.local_data_path / relative_path
        content = local_path.read_bytes()

        # Encrypt content
        blob = encrypt_data(content, self.config.encryption_key)
        encrypted_data = blob.to_bytes()

        # Upload
        remote_path = f"{OTTO_FOLDER}/data/{relative_path}.enc"
        await self.storage.upload_with_retry(remote_path, encrypted_data)

        # Update manifest
        stat = local_path.stat()
        entry = FileEntry(
            path=relative_path,
            content_hash=self._compute_file_hash(local_path),
            size=len(encrypted_data),
            modified=datetime.fromtimestamp(stat.st_mtime),
        )
        manifest.add_entry(entry)

        logger.debug(f"Uploaded: {relative_path}")

    async def _download_file(self, relative_path: str, manifest: SyncManifest) -> None:
        """Download and decrypt a file."""
        from ..crypto import decrypt_data, EncryptedBlob

        # Download
        remote_path = f"{OTTO_FOLDER}/data/{relative_path}.enc"
        encrypted_data = await self.storage.download_with_retry(remote_path)

        # Decrypt content
        blob = EncryptedBlob.from_bytes(encrypted_data)
        content = decrypt_data(blob, self.config.encryption_key)

        # Save locally
        local_path = self.config.local_data_path / relative_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)

        logger.debug(f"Downloaded: {relative_path}")

    # =========================================================================
    # Status Updates
    # =========================================================================

    def _update_status(self, status: SyncStatus, message: str) -> None:
        """Update status and notify callback."""
        self._status = status
        logger.debug(f"Sync status: {status.value} - {message}")

        if self._progress_callback:
            try:
                self._progress_callback(status, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")


__all__ = [
    "SyncEngine",
    "SyncConfig",
    "SyncStatus",
    "SyncResult",
    "ConflictResolution",
    "SyncError",
    "SyncConflictError",
    "SYNC_PROTOCOL_VERSION",
    "MAX_FILES_PER_SYNC",
]
