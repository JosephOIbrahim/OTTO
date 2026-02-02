"""
Storage Provider Abstract Base Class
=====================================

Defines the interface for all storage backends.

[He2025] Compliance:
- All methods have deterministic behavior
- Path resolution follows fixed rules
- No runtime variation based on external state
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json


class StorageProvider(ABC):
    """
    Abstract base class for storage providers.

    Implementations must provide:
    - Path resolution for different storage roots
    - JSON read/write operations
    - Text read/write operations
    - Directory listing
    - Existence checking
    """

    @abstractmethod
    def get_root(self, root_type: str) -> Path:
        """
        Get the root path for a given storage type.

        Args:
            root_type: One of 'otto', 'orchestra', 'claude', 'cache'

        Returns:
            Path to the root directory
        """
        pass

    @abstractmethod
    def resolve_path(self, relative_path: str, root_type: str = "otto") -> Path:
        """
        Resolve a relative path against a storage root.

        Args:
            relative_path: Path relative to root (e.g., "state/cognitive_state.json")
            root_type: Which root to use ('otto', 'orchestra', 'claude')

        Returns:
            Absolute path
        """
        pass

    # =========================================================================
    # JSON Operations
    # =========================================================================

    @abstractmethod
    def read_json(
        self,
        relative_path: str,
        root_type: str = "otto",
        default: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Read a JSON file.

        Args:
            relative_path: Path relative to root
            root_type: Which root to use
            default: Value to return if file doesn't exist

        Returns:
            Parsed JSON as dict, or default if not found
        """
        pass

    @abstractmethod
    def write_json(
        self,
        relative_path: str,
        data: Dict[str, Any],
        root_type: str = "otto",
        backup: bool = True
    ) -> bool:
        """
        Write a JSON file atomically.

        Args:
            relative_path: Path relative to root
            data: Data to write
            root_type: Which root to use
            backup: Whether to create a backup before writing

        Returns:
            True if successful
        """
        pass

    # =========================================================================
    # Text Operations
    # =========================================================================

    @abstractmethod
    def read_text(
        self,
        relative_path: str,
        root_type: str = "otto",
        default: Optional[str] = None
    ) -> Optional[str]:
        """
        Read a text file.

        Args:
            relative_path: Path relative to root
            root_type: Which root to use
            default: Value to return if file doesn't exist

        Returns:
            File contents as string, or default if not found
        """
        pass

    @abstractmethod
    def write_text(
        self,
        relative_path: str,
        content: str,
        root_type: str = "otto",
        backup: bool = False
    ) -> bool:
        """
        Write a text file atomically.

        Args:
            relative_path: Path relative to root
            content: Text content to write
            root_type: Which root to use
            backup: Whether to create a backup before writing

        Returns:
            True if successful
        """
        pass

    # =========================================================================
    # Binary Operations
    # =========================================================================

    @abstractmethod
    def read_bytes(
        self,
        relative_path: str,
        root_type: str = "otto"
    ) -> Optional[bytes]:
        """
        Read a binary file.

        Args:
            relative_path: Path relative to root
            root_type: Which root to use

        Returns:
            File contents as bytes, or None if not found
        """
        pass

    @abstractmethod
    def write_bytes(
        self,
        relative_path: str,
        data: bytes,
        root_type: str = "otto",
        backup: bool = False
    ) -> bool:
        """
        Write a binary file atomically.

        Args:
            relative_path: Path relative to root
            data: Binary data to write
            root_type: Which root to use
            backup: Whether to create a backup before writing

        Returns:
            True if successful
        """
        pass

    # =========================================================================
    # Directory Operations
    # =========================================================================

    @abstractmethod
    def exists(self, relative_path: str, root_type: str = "otto") -> bool:
        """Check if a path exists."""
        pass

    @abstractmethod
    def is_file(self, relative_path: str, root_type: str = "otto") -> bool:
        """Check if path is a file."""
        pass

    @abstractmethod
    def is_dir(self, relative_path: str, root_type: str = "otto") -> bool:
        """Check if path is a directory."""
        pass

    @abstractmethod
    def list_dir(
        self,
        relative_path: str = "",
        root_type: str = "otto",
        pattern: Optional[str] = None
    ) -> List[str]:
        """
        List directory contents.

        Args:
            relative_path: Path relative to root (empty = root itself)
            root_type: Which root to use
            pattern: Optional glob pattern to filter

        Returns:
            List of relative paths within the directory
        """
        pass

    @abstractmethod
    def ensure_dir(self, relative_path: str, root_type: str = "otto") -> Path:
        """
        Ensure a directory exists, creating if needed.

        Args:
            relative_path: Path relative to root
            root_type: Which root to use

        Returns:
            Absolute path to the directory
        """
        pass

    @abstractmethod
    def delete(self, relative_path: str, root_type: str = "otto") -> bool:
        """
        Delete a file or empty directory.

        Args:
            relative_path: Path relative to root
            root_type: Which root to use

        Returns:
            True if deleted, False if didn't exist
        """
        pass

    # =========================================================================
    # Convenience Methods (Subdirectories)
    # =========================================================================

    def get_state_dir(self, root_type: str = "otto") -> Path:
        """Get the state directory."""
        return self.ensure_dir("state", root_type)

    def get_config_dir(self, root_type: str = "otto") -> Path:
        """Get the config directory."""
        return self.ensure_dir("config", root_type)

    def get_cache_dir(self, root_type: str = "otto") -> Path:
        """Get the cache directory."""
        return self.ensure_dir("cache", root_type)

    def get_backup_dir(self, root_type: str = "otto") -> Path:
        """Get the backup directory."""
        return self.ensure_dir("backups", root_type)

    def get_knowledge_dir(self, root_type: str = "otto") -> Path:
        """Get the knowledge directory."""
        return self.ensure_dir("knowledge", root_type)

    def get_calibration_dir(self, root_type: str = "otto") -> Path:
        """Get the calibration directory."""
        return self.ensure_dir("calibration", root_type)
