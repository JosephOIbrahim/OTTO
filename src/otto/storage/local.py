"""
Local Filesystem Storage Provider
=================================

Implements StorageProvider for local filesystem.
This is the default provider for desktop/CLI usage.

Determinism:
- Atomic writes (temp file + rename)
- Deterministic backup naming
- Fixed file operation order
"""

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .provider import StorageProvider
from .config import StorageConfig, get_default_config

logger = logging.getLogger(__name__)


class LocalStorageProvider(StorageProvider):
    """
    Local filesystem implementation of StorageProvider.

    Features:
    - Atomic writes via temp file + rename
    - Automatic backup on write (configurable)
    - Parent directory auto-creation
    - Graceful degradation on errors
    """

    def __init__(self, config: Optional[StorageConfig] = None):
        """
        Initialize local storage provider.

        Args:
            config: Storage configuration (uses default if None)
        """
        self._config = config or get_default_config()

    @property
    def config(self) -> StorageConfig:
        """Get the storage configuration."""
        return self._config

    def get_root(self, root_type: str) -> Path:
        """Get the root path for a given storage type."""
        return self._config.get_root_by_name(root_type)

    def resolve_path(self, relative_path: str, root_type: str = "otto") -> Path:
        """Resolve a relative path against a storage root."""
        return self._config.resolve_path(relative_path, root_type)

    # =========================================================================
    # JSON Operations
    # =========================================================================

    def read_json(
        self,
        relative_path: str,
        root_type: str = "otto",
        default: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Read a JSON file with graceful fallback."""
        path = self.resolve_path(relative_path, root_type)

        if not path.exists():
            return default if default is not None else {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read JSON from {path}: {e}")
            return default if default is not None else {}

    def write_json(
        self,
        relative_path: str,
        data: Dict[str, Any],
        root_type: str = "otto",
        backup: bool = True
    ) -> bool:
        """Write JSON file atomically with optional backup."""
        path = self.resolve_path(relative_path, root_type)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if requested and file exists
        if backup and self._config.backup_on_write and path.exists():
            self._create_backup(path, root_type)

        # Atomic write: write to temp file, then rename
        try:
            # Create temp file in same directory for atomic rename
            fd, temp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=path.stem + "_",
                dir=path.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Atomic rename (works on same filesystem)
                os.replace(temp_path, path)
                return True
            except Exception:
                # Clean up temp file on failure
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except OSError as e:
            logger.error(f"Failed to write JSON to {path}: {e}")
            return False

    # =========================================================================
    # Text Operations
    # =========================================================================

    def read_text(
        self,
        relative_path: str,
        root_type: str = "otto",
        default: Optional[str] = None
    ) -> Optional[str]:
        """Read a text file with graceful fallback."""
        path = self.resolve_path(relative_path, root_type)

        if not path.exists():
            return default

        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Failed to read text from {path}: {e}")
            return default

    def write_text(
        self,
        relative_path: str,
        content: str,
        root_type: str = "otto",
        backup: bool = False
    ) -> bool:
        """Write text file atomically."""
        path = self.resolve_path(relative_path, root_type)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if requested
        if backup and self._config.backup_on_write and path.exists():
            self._create_backup(path, root_type)

        try:
            fd, temp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=path.stem + "_",
                dir=path.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(temp_path, path)
                return True
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except OSError as e:
            logger.error(f"Failed to write text to {path}: {e}")
            return False

    # =========================================================================
    # Binary Operations
    # =========================================================================

    def read_bytes(
        self,
        relative_path: str,
        root_type: str = "otto"
    ) -> Optional[bytes]:
        """Read a binary file."""
        path = self.resolve_path(relative_path, root_type)

        if not path.exists():
            return None

        try:
            return path.read_bytes()
        except OSError as e:
            logger.warning(f"Failed to read bytes from {path}: {e}")
            return None

    def write_bytes(
        self,
        relative_path: str,
        data: bytes,
        root_type: str = "otto",
        backup: bool = False
    ) -> bool:
        """Write binary file atomically."""
        path = self.resolve_path(relative_path, root_type)

        path.parent.mkdir(parents=True, exist_ok=True)

        if backup and self._config.backup_on_write and path.exists():
            self._create_backup(path, root_type)

        try:
            fd, temp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=path.stem + "_",
                dir=path.parent
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(temp_path, path)
                return True
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except OSError as e:
            logger.error(f"Failed to write bytes to {path}: {e}")
            return False

    # =========================================================================
    # Directory Operations
    # =========================================================================

    def exists(self, relative_path: str, root_type: str = "otto") -> bool:
        """Check if a path exists."""
        return self.resolve_path(relative_path, root_type).exists()

    def is_file(self, relative_path: str, root_type: str = "otto") -> bool:
        """Check if path is a file."""
        return self.resolve_path(relative_path, root_type).is_file()

    def is_dir(self, relative_path: str, root_type: str = "otto") -> bool:
        """Check if path is a directory."""
        return self.resolve_path(relative_path, root_type).is_dir()

    def list_dir(
        self,
        relative_path: str = "",
        root_type: str = "otto",
        pattern: Optional[str] = None
    ) -> List[str]:
        """List directory contents."""
        path = self.resolve_path(relative_path, root_type)

        if not path.is_dir():
            return []

        try:
            if pattern:
                # Use glob pattern
                matches = list(path.glob(pattern))
                return [str(m.relative_to(path)) for m in matches]
            else:
                # List all
                return [p.name for p in path.iterdir()]
        except OSError as e:
            logger.warning(f"Failed to list directory {path}: {e}")
            return []

    def ensure_dir(self, relative_path: str, root_type: str = "otto") -> Path:
        """Ensure a directory exists, creating if needed."""
        path = self.resolve_path(relative_path, root_type)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def delete(self, relative_path: str, root_type: str = "otto") -> bool:
        """Delete a file or empty directory."""
        path = self.resolve_path(relative_path, root_type)

        if not path.exists():
            return False

        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()  # Only removes empty directories
            return True
        except OSError as e:
            logger.warning(f"Failed to delete {path}: {e}")
            return False

    # =========================================================================
    # Backup Management
    # =========================================================================

    def _create_backup(self, path: Path, root_type: str) -> Optional[Path]:
        """
        Create a backup of a file.

        Backup naming: {filename}.{timestamp}.bak
        Location: backups/ subdirectory of the same root
        """
        if not path.exists():
            return None

        # Get backup directory
        backup_dir = self.get_backup_dir(root_type)

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.name}.{timestamp}.bak"
        backup_path = backup_dir / backup_name

        try:
            shutil.copy2(path, backup_path)
            logger.debug(f"Created backup: {backup_path}")

            # Prune old backups if over limit
            self._prune_backups(backup_dir, path.name)

            return backup_path
        except OSError as e:
            logger.warning(f"Failed to create backup for {path}: {e}")
            return None

    def _prune_backups(self, backup_dir: Path, base_name: str) -> None:
        """
        Remove old backups beyond the configured limit.

        Deterministic: sorted by name (includes timestamp)
        """
        pattern = f"{base_name}.*.bak"
        backups = sorted(backup_dir.glob(pattern))

        # Remove oldest backups if over limit
        while len(backups) > self._config.max_backups:
            oldest = backups.pop(0)
            try:
                oldest.unlink()
                logger.debug(f"Pruned old backup: {oldest}")
            except OSError:
                pass
