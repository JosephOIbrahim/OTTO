"""
OTTO OS Cloud Sync Module
=========================

End-to-end encrypted cloud synchronization.

ThinkingMachines [He2025] Compliance:
- FIXED sync protocol (version, manifest format)
- DETERMINISTIC conflict resolution (last-write-wins with vector clocks)
- BOUNDED operations (chunk size, retry limits)

Architecture:
- Client-side encryption (OTTO encrypts before upload)
- User-held keys (server never has key)
- Pluggable storage backends (Dropbox, Drive, WebDAV)

Components:
- storage_adapter: Abstract storage backend interface
- sync_engine: Sync orchestration with conflict resolution
- manifest: Encrypted manifest for tracking synced files
- adapters/: Storage backend implementations

Security Properties:
- E2E encryption using crypto module (AES-256-GCM)
- Encrypted manifest prevents metadata leakage
- Server NEVER sees: passphrase, decrypted content, personal data

Usage:
    from otto.sync import SyncEngine, create_storage_adapter

    # Create storage adapter
    storage = create_storage_adapter("webdav", endpoint="https://...")

    # Initialize sync engine
    engine = SyncEngine(storage, encryption_key)

    # Sync files
    await engine.sync()
"""

from .storage_adapter import (
    StorageAdapter,
    StorageError,
    AuthenticationError,
    QuotaExceededError,
    FileNotFoundError as SyncFileNotFoundError,
    create_storage_adapter,
)

from .sync_engine import (
    SyncEngine,
    SyncConfig,
    SyncStatus,
    SyncResult,
    ConflictResolution,
    SyncError,
)

from .manifest import (
    SyncManifest,
    FileEntry,
    ManifestError,
)

__all__ = [
    # Storage
    "StorageAdapter",
    "StorageError",
    "AuthenticationError",
    "QuotaExceededError",
    "SyncFileNotFoundError",
    "create_storage_adapter",
    # Engine
    "SyncEngine",
    "SyncConfig",
    "SyncStatus",
    "SyncResult",
    "ConflictResolution",
    "SyncError",
    # Manifest
    "SyncManifest",
    "FileEntry",
    "ManifestError",
]
