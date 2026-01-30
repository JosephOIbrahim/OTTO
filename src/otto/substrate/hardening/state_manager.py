"""
Production-Hardened State Manager

Provides graceful degradation, backup on write, and recovery for cognitive state.
Part of USD Cognitive Substrate production hardening.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class StateResult:
    """Result of a state operation.

    Attributes:
        success: Whether the operation succeeded
        data: The state data (if read) or None
        error: Error message if failed
        used_default: Whether default state was used due to failure
        backup_path: Path to backup file (if write with backup)
    """
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    used_default: bool = False
    backup_path: Path | None = None


class StateManager:
    """Production-hardened state management for cognitive substrate.

    Features:
    - Graceful degradation: missing/corrupted files use defaults
    - Backup on write: auto-backup before modification
    - Schema validation: verify structure before writing
    - Recovery: list and restore from backups

    Example:
        >>> manager = StateManager()
        >>> result = manager.read_session_state()
        >>> if result.success:
        ...     print(result.data)
        >>> else:
        ...     print(f"Using defaults: {result.used_default}")
    """

    def __init__(
        self,
        state_dir: Path | str | None = None,
        backup_dir: Path | str | None = None,
        max_backups: int = 10,
    ):
        """Initialize state manager.

        Args:
            state_dir: Directory for state files.
                      Defaults to ~/.claude/substrate/
            backup_dir: Directory for backups.
                       Defaults to state_dir/backups/
            max_backups: Maximum backups to retain per file
        """
        if state_dir is None:
            state_dir = Path.home() / ".claude" / "substrate"
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        if backup_dir is None:
            backup_dir = self.state_dir / "backups"
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.max_backups = max_backups

    # =========================================================================
    # Read Operations
    # =========================================================================

    def read_json(
        self,
        file_path: Path | str,
        default: dict[str, Any] | None = None,
        validator: Callable[[dict], bool] | None = None,
    ) -> StateResult:
        """Read JSON file with graceful degradation.

        Args:
            file_path: Path to JSON file
            default: Default data if file missing/corrupted
            validator: Optional function to validate data structure

        Returns:
            StateResult with data or default
        """
        path = Path(file_path)
        default = default or {}

        # File doesn't exist - use default
        if not path.exists():
            logger.debug(f"State file not found: {path}, using default")
            return StateResult(
                success=True,
                data=default,
                used_default=True,
            )

        # Try to read file
        try:
            content = path.read_text(encoding='utf-8')
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error in {path}: {e}")
            return StateResult(
                success=True,
                data=default,
                error=f"JSON decode error: {e}",
                used_default=True,
            )
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")
            return StateResult(
                success=True,
                data=default,
                error=f"Read error: {e}",
                used_default=True,
            )

        # Validate if validator provided
        if validator and not validator(data):
            logger.warning(f"Validation failed for {path}, using default")
            return StateResult(
                success=True,
                data=default,
                error="Validation failed",
                used_default=True,
            )

        return StateResult(success=True, data=data)

    def read_session_state(
        self,
        file_path: Path | str | None = None,
    ) -> StateResult:
        """Read session state with validation and graceful degradation.

        Args:
            file_path: Path to session state file.
                      Defaults to state_dir/session_state.json

        Returns:
            StateResult with session state data
        """
        if file_path is None:
            file_path = self.state_dir / "session_state.json"

        default = {
            'schema_version': '1.0',
            'session': {
                'id': None,
                'started_at': None,
                'goal': None,
            },
            'tracking': {
                'exchange_count': 0,
                'last_beacon_at': 0,
            },
            'config': {
                'intervention_style': 'gentle',
            },
        }

        def validate(data: dict) -> bool:
            """Validate session state structure."""
            required = ['schema_version']
            return all(key in data for key in required)

        return self.read_json(file_path, default, validate)

    # =========================================================================
    # Write Operations
    # =========================================================================

    def write_json(
        self,
        file_path: Path | str,
        data: dict[str, Any],
        backup: bool = True,
        validator: Callable[[dict], bool] | None = None,
    ) -> StateResult:
        """Write JSON file with optional backup.

        Args:
            file_path: Path to JSON file
            data: Data to write
            backup: Whether to backup existing file first
            validator: Optional function to validate data before write

        Returns:
            StateResult with success status and backup path
        """
        path = Path(file_path)
        backup_path = None

        # Validate data before writing
        if validator and not validator(data):
            return StateResult(
                success=False,
                error="Validation failed, refusing to write",
            )

        # Create backup if file exists and backup requested
        if backup and path.exists():
            try:
                backup_path = self._create_backup(path)
            except Exception as e:
                logger.warning(f"Backup failed for {path}: {e}")
                # Continue with write even if backup fails

        # Write file
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps(data, indent=2, default=str, sort_keys=True)
            path.write_text(content, encoding='utf-8')
            return StateResult(
                success=True,
                data=data,
                backup_path=backup_path,
            )
        except Exception as e:
            logger.error(f"Failed to write {path}: {e}")
            return StateResult(
                success=False,
                error=f"Write error: {e}",
                backup_path=backup_path,
            )

    def write_session_state(
        self,
        data: dict[str, Any],
        file_path: Path | str | None = None,
        backup: bool = True,
    ) -> StateResult:
        """Write session state with validation and backup.

        Args:
            data: Session state data
            file_path: Path to session state file.
                      Defaults to state_dir/session_state.json
            backup: Whether to backup existing file first

        Returns:
            StateResult with success status
        """
        if file_path is None:
            file_path = self.state_dir / "session_state.json"

        def validate(data: dict) -> bool:
            """Validate session state structure."""
            return 'schema_version' in data

        return self.write_json(file_path, data, backup, validate)

    # =========================================================================
    # Backup Operations
    # =========================================================================

    def _create_backup(self, file_path: Path) -> Path:
        """Create timestamped backup of a file.

        Args:
            file_path: Path to file to backup

        Returns:
            Path to backup file
        """
        # Include microseconds for uniqueness in rapid succession
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        logger.debug(f"Created backup: {backup_path}")

        # Cleanup old backups
        self._cleanup_backups(file_path.stem)

        return backup_path

    def _cleanup_backups(self, file_stem: str) -> None:
        """Remove old backups beyond max_backups limit.

        Args:
            file_stem: Base filename (without extension)
        """
        pattern = f"{file_stem}_*"
        backups = sorted(
            self.backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for backup in backups[self.max_backups:]:
            try:
                backup.unlink()
                logger.debug(f"Removed old backup: {backup}")
            except Exception as e:
                logger.warning(f"Failed to remove backup {backup}: {e}")

    def list_backups(self, file_stem: str | None = None) -> list[Path]:
        """List available backups.

        Args:
            file_stem: Filter to specific file (optional)

        Returns:
            List of backup file paths, newest first
        """
        if file_stem:
            pattern = f"{file_stem}_*"
        else:
            pattern = "*"

        backups = sorted(
            self.backup_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return backups

    def restore_backup(
        self,
        backup_path: Path | str,
        target_path: Path | str | None = None,
    ) -> StateResult:
        """Restore a backup file.

        Args:
            backup_path: Path to backup file
            target_path: Where to restore (defaults to original location)

        Returns:
            StateResult with success status
        """
        backup_path = Path(backup_path)

        if not backup_path.exists():
            return StateResult(
                success=False,
                error=f"Backup not found: {backup_path}",
            )

        # Determine target path from backup name
        if target_path is None:
            # Extract original filename from backup (remove timestamp)
            # Format: filename_YYYYMMDD_HHMMSS.ext
            parts = backup_path.stem.rsplit('_', 2)
            if len(parts) >= 2:
                original_stem = '_'.join(parts[:-2]) or parts[0]
            else:
                original_stem = backup_path.stem
            target_path = self.state_dir / f"{original_stem}{backup_path.suffix}"

        target_path = Path(target_path)

        try:
            shutil.copy2(backup_path, target_path)
            logger.info(f"Restored backup {backup_path} to {target_path}")
            return StateResult(
                success=True,
                backup_path=backup_path,
            )
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return StateResult(
                success=False,
                error=f"Restore error: {e}",
            )

    # =========================================================================
    # Checksum Operations
    # =========================================================================

    def compute_checksum(self, data: dict[str, Any]) -> str:
        """Compute SHA256 checksum of data.

        Args:
            data: Dictionary to checksum

        Returns:
            First 16 characters of SHA256 hash
        """
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def verify_checksum(
        self,
        data: dict[str, Any],
        expected_checksum: str,
    ) -> bool:
        """Verify data checksum.

        Args:
            data: Dictionary to verify
            expected_checksum: Expected checksum value

        Returns:
            True if checksums match
        """
        computed = self.compute_checksum(data)
        return computed == expected_checksum


# Module-level singleton
_manager: StateManager | None = None


def get_state_manager() -> StateManager:
    """Get or create the singleton state manager."""
    global _manager
    if _manager is None:
        _manager = StateManager()
    return _manager
