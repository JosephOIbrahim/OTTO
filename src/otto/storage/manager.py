"""
Storage Manager
===============

Global storage manager that provides a single interface to storage operations.
Manages provider selection and caching.

Determinism:
- Fixed provider selection order
- Deterministic initialization
- No runtime variation
"""

import logging
from typing import Optional

from .provider import StorageProvider
from .config import StorageConfig, get_default_config
from .local import LocalStorageProvider

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages storage providers and provides a unified interface.

    Supports multiple provider types:
    - local: Local filesystem (default)
    - memory: In-memory (for testing)
    - cloud: Cloud storage (future)

    Usage:
        manager = StorageManager()
        data = manager.read_json("state/cognitive_state.json")
    """

    def __init__(
        self,
        provider: Optional[StorageProvider] = None,
        config: Optional[StorageConfig] = None
    ):
        """
        Initialize storage manager.

        Args:
            provider: Storage provider to use (creates LocalStorageProvider if None)
            config: Storage config (uses default if None)
        """
        self._config = config or get_default_config()
        self._provider = provider or LocalStorageProvider(self._config)

    @property
    def provider(self) -> StorageProvider:
        """Get the current storage provider."""
        return self._provider

    @property
    def config(self) -> StorageConfig:
        """Get the storage configuration."""
        return self._config

    # =========================================================================
    # Delegate to Provider
    # =========================================================================

    def read_json(self, relative_path: str, root_type: str = "otto", **kwargs):
        """Read a JSON file."""
        return self._provider.read_json(relative_path, root_type, **kwargs)

    def write_json(self, relative_path: str, data: dict, root_type: str = "otto", **kwargs):
        """Write a JSON file."""
        return self._provider.write_json(relative_path, data, root_type, **kwargs)

    def read_text(self, relative_path: str, root_type: str = "otto", **kwargs):
        """Read a text file."""
        return self._provider.read_text(relative_path, root_type, **kwargs)

    def write_text(self, relative_path: str, content: str, root_type: str = "otto", **kwargs):
        """Write a text file."""
        return self._provider.write_text(relative_path, content, root_type, **kwargs)

    def read_bytes(self, relative_path: str, root_type: str = "otto"):
        """Read a binary file."""
        return self._provider.read_bytes(relative_path, root_type)

    def write_bytes(self, relative_path: str, data: bytes, root_type: str = "otto", **kwargs):
        """Write a binary file."""
        return self._provider.write_bytes(relative_path, data, root_type, **kwargs)

    def exists(self, relative_path: str, root_type: str = "otto"):
        """Check if path exists."""
        return self._provider.exists(relative_path, root_type)

    def is_file(self, relative_path: str, root_type: str = "otto"):
        """Check if path is a file."""
        return self._provider.is_file(relative_path, root_type)

    def is_dir(self, relative_path: str, root_type: str = "otto"):
        """Check if path is a directory."""
        return self._provider.is_dir(relative_path, root_type)

    def list_dir(self, relative_path: str = "", root_type: str = "otto", **kwargs):
        """List directory contents."""
        return self._provider.list_dir(relative_path, root_type, **kwargs)

    def ensure_dir(self, relative_path: str, root_type: str = "otto"):
        """Ensure directory exists."""
        return self._provider.ensure_dir(relative_path, root_type)

    def delete(self, relative_path: str, root_type: str = "otto"):
        """Delete a file or directory."""
        return self._provider.delete(relative_path, root_type)

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def get_state_dir(self, root_type: str = "otto"):
        """Get state directory path."""
        return self._provider.get_state_dir(root_type)

    def get_config_dir(self, root_type: str = "otto"):
        """Get config directory path."""
        return self._provider.get_config_dir(root_type)

    def get_cache_dir(self, root_type: str = "otto"):
        """Get cache directory path."""
        return self._provider.get_cache_dir(root_type)

    def get_backup_dir(self, root_type: str = "otto"):
        """Get backup directory path."""
        return self._provider.get_backup_dir(root_type)

    def resolve_path(self, relative_path: str, root_type: str = "otto"):
        """Resolve a relative path to absolute."""
        return self._provider.resolve_path(relative_path, root_type)

    def get_root(self, root_type: str = "otto"):
        """Get a storage root path."""
        return self._provider.get_root(root_type)


# =============================================================================
# Global Instance
# =============================================================================

_storage_manager: Optional[StorageManager] = None


def get_storage() -> StorageManager:
    """
    Get the global storage manager instance.

    Creates LocalStorageProvider on first call.
    """
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager


def get_storage_config() -> StorageConfig:
    """Get the storage configuration from the global manager."""
    return get_storage().config


def set_storage(manager: StorageManager) -> None:
    """
    Set the global storage manager.

    Useful for testing or custom deployments.
    """
    global _storage_manager
    _storage_manager = manager


def reset_storage() -> None:
    """Reset global storage manager (for testing)."""
    global _storage_manager
    _storage_manager = None
