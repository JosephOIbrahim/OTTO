"""
Storage Abstraction Layer for OTTO OS
=====================================

Provides platform-agnostic storage abstraction to support:
- Local filesystem (current behavior)
- Cloud storage (future: S3, GCS, Azure Blob)
- Mobile storage (future: secure enclave, app sandbox)

[He2025] Compliance:
- Fixed path resolution order
- Deterministic provider selection
- No runtime variation in path computation

Usage:
    from otto.storage import get_storage, StorageConfig

    # Get default storage (reads from env vars or uses defaults)
    storage = get_storage()

    # Read/write state
    state = storage.read_json("state/cognitive_state.json")
    storage.write_json("state/cognitive_state.json", state)

    # Get paths for external tools
    state_dir = storage.get_state_dir()

Environment Variables:
    OTTO_DATA_DIR      - Base data directory (default: ~/.otto)
    OTTO_STATE_DIR     - State files (default: $OTTO_DATA_DIR/state)
    OTTO_CONFIG_DIR    - Config files (default: $OTTO_DATA_DIR/config)
    OTTO_CACHE_DIR     - Cache files (default: $OTTO_DATA_DIR/cache)
    ORCHESTRA_STATE_DIR - Orchestra state (default: ~/.orchestra/state)
"""

from .provider import StorageProvider
from .config import StorageConfig, StorageRoot
from .local import LocalStorageProvider
from .manager import StorageManager, get_storage, get_storage_config

__all__ = [
    # Core abstractions
    "StorageProvider",
    "StorageConfig",
    "StorageRoot",
    # Implementations
    "LocalStorageProvider",
    # Manager
    "StorageManager",
    "get_storage",
    "get_storage_config",
]
