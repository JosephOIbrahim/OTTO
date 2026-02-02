"""
Storage Configuration
=====================

Centralized configuration for all storage paths.
Supports environment variable overrides for flexibility.

[He2025] Compliance:
- Fixed default values
- Deterministic environment variable resolution
- No runtime variation
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


class StorageRoot(Enum):
    """
    Storage root types.

    OTTO: Primary OTTO OS data (~/.otto)
    ORCHESTRA: Cognitive engine state (~/.orchestra)
    CLAUDE: Claude Code integration (~/.claude)
    CACHE: Temporary/cache data
    """
    OTTO = "otto"
    ORCHESTRA = "orchestra"
    CLAUDE = "claude"
    CACHE = "cache"


def _get_env_path(env_var: str, default: Path) -> Path:
    """
    Get a path from environment variable or use default.

    [He2025] Deterministic: Same env → same result.
    """
    value = os.environ.get(env_var)
    if value:
        return Path(value).expanduser().resolve()
    return default


def _get_default_home() -> Path:
    """Get the user's home directory."""
    return Path.home()


@dataclass
class StorageConfig:
    """
    Configuration for storage paths.

    Supports three storage roots:
    - otto: Primary OTTO OS data
    - orchestra: Cognitive engine state
    - claude: Claude Code integration

    Environment Variables:
        OTTO_DATA_DIR: Override ~/.otto root
        OTTO_STATE_DIR: Override state subdirectory
        OTTO_CONFIG_DIR: Override config subdirectory
        OTTO_CACHE_DIR: Override cache directory
        ORCHESTRA_STATE_DIR: Override ~/.orchestra/state
        CLAUDE_SUBSTRATE_DIR: Override ~/.claude/substrate
    """

    # Root directories
    otto_root: Path = field(default_factory=lambda: _get_env_path(
        "OTTO_DATA_DIR",
        _get_default_home() / ".otto"
    ))

    orchestra_root: Path = field(default_factory=lambda: _get_env_path(
        "ORCHESTRA_DATA_DIR",
        _get_default_home() / ".orchestra"
    ))

    claude_root: Path = field(default_factory=lambda: _get_env_path(
        "CLAUDE_DATA_DIR",
        _get_default_home() / ".claude"
    ))

    cache_root: Path = field(default_factory=lambda: _get_env_path(
        "OTTO_CACHE_DIR",
        _get_default_home() / ".otto" / "cache"
    ))

    # Subdirectory overrides (optional)
    state_subdir: str = "state"
    config_subdir: str = "config"
    backup_subdir: str = "backups"
    knowledge_subdir: str = "knowledge"
    calibration_subdir: str = "calibration"

    # Backup settings
    backup_on_write: bool = True
    max_backups: int = 10

    def get_root(self, root_type: StorageRoot) -> Path:
        """
        Get the root path for a storage type.

        [He2025] Fixed mapping, no runtime variation.
        """
        # [He2025] Fixed evaluation order
        roots = {
            StorageRoot.OTTO: self.otto_root,
            StorageRoot.ORCHESTRA: self.orchestra_root,
            StorageRoot.CLAUDE: self.claude_root,
            StorageRoot.CACHE: self.cache_root,
        }
        return roots[root_type]

    def get_root_by_name(self, name: str) -> Path:
        """
        Get root path by string name.

        Args:
            name: One of 'otto', 'orchestra', 'claude', 'cache'

        Returns:
            Root path
        """
        try:
            root_type = StorageRoot(name.lower())
            return self.get_root(root_type)
        except ValueError:
            # Default to otto for unknown roots
            return self.otto_root

    def resolve_path(self, relative_path: str, root_type: str = "otto") -> Path:
        """
        Resolve a relative path against a storage root.

        Args:
            relative_path: Path relative to root
            root_type: Which root to use

        Returns:
            Absolute path
        """
        root = self.get_root_by_name(root_type)
        return root / relative_path

    @classmethod
    def from_env(cls) -> "StorageConfig":
        """
        Create config from environment variables.

        Reads:
            OTTO_DATA_DIR, ORCHESTRA_DATA_DIR, CLAUDE_DATA_DIR,
            OTTO_CACHE_DIR, OTTO_BACKUP_ON_WRITE, OTTO_MAX_BACKUPS
        """
        config = cls()

        # Override backup settings from env
        if os.environ.get("OTTO_BACKUP_ON_WRITE", "").lower() == "false":
            config.backup_on_write = False

        max_backups = os.environ.get("OTTO_MAX_BACKUPS")
        if max_backups and max_backups.isdigit():
            config.max_backups = int(max_backups)

        return config

    def to_dict(self) -> Dict[str, str]:
        """Export config as dictionary (for debugging/logging)."""
        return {
            "otto_root": str(self.otto_root),
            "orchestra_root": str(self.orchestra_root),
            "claude_root": str(self.claude_root),
            "cache_root": str(self.cache_root),
            "backup_on_write": str(self.backup_on_write),
            "max_backups": str(self.max_backups),
        }


# Global default config (lazy-initialized)
_default_config: Optional[StorageConfig] = None


def get_default_config() -> StorageConfig:
    """
    Get the default storage configuration.

    Creates from environment variables on first call.
    """
    global _default_config
    if _default_config is None:
        _default_config = StorageConfig.from_env()
    return _default_config


def set_default_config(config: StorageConfig) -> None:
    """
    Set the default storage configuration.

    Useful for testing or custom deployments.
    """
    global _default_config
    _default_config = config


def reset_default_config() -> None:
    """Reset to re-read from environment."""
    global _default_config
    _default_config = None
