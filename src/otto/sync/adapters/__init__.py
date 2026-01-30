"""
Storage Adapters
================

Implementations of storage backends for cloud sync.

Available Adapters:
- LocalStorageAdapter: Local filesystem (testing)
- WebDAVAdapter: WebDAV/Nextcloud/ownCloud
- S3Adapter: AWS S3 / MinIO
- DropboxAdapter: Dropbox (planned)
- GDriveAdapter: Google Drive (planned)
"""

# Re-export LocalStorageAdapter from parent module
from ..storage_adapter import LocalStorageAdapter
from .webdav import WebDAVAdapter
from .s3 import S3Adapter

__all__ = [
    "LocalStorageAdapter",
    "WebDAVAdapter",
    "S3Adapter",
]
