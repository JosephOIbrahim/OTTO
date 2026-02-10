"""
Sync Manifest
=============

Encrypted manifest for tracking synced files.

Determinism:
- FIXED manifest format version
- DETERMINISTIC file entry ordering (sorted by path)
- BOUNDED entry count (configurable limit)

The manifest is:
1. JSON serialized
2. Encrypted with user's key
3. Stored on remote as .otto-sync/manifest.enc

Contents:
- File entries with path, hash, size, modified time
- Vector clock for conflict detection
- Last sync timestamp per device
- Schema version for migrations

Security:
- Manifest is encrypted (metadata protection)
- Content hashes prevent tampering
- Vector clocks enable conflict detection
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# =============================================================================
# Constants (FIXED - ThinkingMachines compliant)
# =============================================================================

MANIFEST_VERSION = 1
MANIFEST_FILENAME = "manifest.enc"
MAX_ENTRIES = 10000  # Bounded manifest size


# =============================================================================
# Exceptions
# =============================================================================

class ManifestError(Exception):
    """Base exception for manifest operations."""
    pass


class ManifestVersionError(ManifestError):
    """Raised when manifest version is incompatible."""
    pass


class ManifestCorruptError(ManifestError):
    """Raised when manifest data is corrupt."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class FileEntry:
    """
    Entry for a synced file.

    Attributes:
        path: Relative path within OTTO data directory
        content_hash: SHA-256 hash of encrypted content
        size: Size of encrypted data in bytes
        modified: Last modification timestamp
        vector_clock: Per-device version counters
    """
    path: str
    content_hash: str
    size: int
    modified: datetime
    vector_clock: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "path": self.path,
            "content_hash": self.content_hash,
            "size": self.size,
            "modified": self.modified.isoformat(),
            "vector_clock": self.vector_clock,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileEntry":
        """Deserialize from dictionary."""
        return cls(
            path=data["path"],
            content_hash=data["content_hash"],
            size=data["size"],
            modified=datetime.fromisoformat(data["modified"]),
            vector_clock=data.get("vector_clock", {}),
        )

    def increment_clock(self, device_id: str) -> None:
        """Increment vector clock for device."""
        current = self.vector_clock.get(device_id, 0)
        self.vector_clock[device_id] = current + 1

    def is_newer_than(self, other: "FileEntry", device_id: str) -> bool:
        """
        Check if this entry is newer than another.

        Uses vector clock comparison for conflict detection.
        """
        my_version = self.vector_clock.get(device_id, 0)
        other_version = other.vector_clock.get(device_id, 0)
        return my_version > other_version

    def conflicts_with(self, other: "FileEntry") -> bool:
        """
        Check if entries have conflicting changes.

        Returns True if neither dominates the other (concurrent edits).
        """
        if self.content_hash == other.content_hash:
            return False

        # Check if one dominates the other
        self_dominates = all(
            self.vector_clock.get(k, 0) >= v
            for k, v in other.vector_clock.items()
        )
        other_dominates = all(
            other.vector_clock.get(k, 0) >= v
            for k, v in self.vector_clock.items()
        )

        # Conflict if neither dominates
        return not (self_dominates or other_dominates)


@dataclass
class DeviceInfo:
    """Information about a syncing device."""
    device_id: str
    device_name: str
    last_sync: datetime
    platform: str = "unknown"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "last_sync": self.last_sync.isoformat(),
            "platform": self.platform,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceInfo":
        """Deserialize from dictionary."""
        return cls(
            device_id=data["device_id"],
            device_name=data["device_name"],
            last_sync=datetime.fromisoformat(data["last_sync"]),
            platform=data.get("platform", "unknown"),
        )


# =============================================================================
# SyncManifest
# =============================================================================

class SyncManifest:
    """
    Encrypted manifest for tracking synced files.

    ThinkingMachines Compliance:
    - FIXED version format
    - DETERMINISTIC serialization (sorted entries)
    - BOUNDED entry count

    Usage:
        manifest = SyncManifest(device_id="laptop-001")
        manifest.add_entry(FileEntry(...))
        data = manifest.to_json()
        # Encrypt data before storing
    """

    def __init__(
        self,
        device_id: str,
        device_name: str = "unknown",
        platform: str = "unknown",
    ):
        """
        Initialize sync manifest.

        Args:
            device_id: Unique device identifier
            device_name: Human-readable device name
            platform: Device platform (windows, linux, macos)
        """
        self.version = MANIFEST_VERSION
        self.device_id = device_id
        self.created = datetime.now()
        self.modified = datetime.now()

        self._entries: Dict[str, FileEntry] = {}
        self._devices: Dict[str, DeviceInfo] = {}

        # Register this device
        self._devices[device_id] = DeviceInfo(
            device_id=device_id,
            device_name=device_name,
            last_sync=datetime.now(),
            platform=platform,
        )

    @property
    def entries(self) -> List[FileEntry]:
        """Get all file entries sorted by path."""
        return sorted(self._entries.values(), key=lambda e: e.path)

    @property
    def entry_count(self) -> int:
        """Get number of entries."""
        return len(self._entries)

    @property
    def devices(self) -> List[DeviceInfo]:
        """Get all registered devices."""
        return list(self._devices.values())

    # =========================================================================
    # Entry Management
    # =========================================================================

    def add_entry(self, entry: FileEntry) -> None:
        """
        Add or update file entry.

        Args:
            entry: FileEntry to add

        Raises:
            ManifestError: If max entries exceeded
        """
        if entry.path not in self._entries and len(self._entries) >= MAX_ENTRIES:
            raise ManifestError(f"Manifest full: max {MAX_ENTRIES} entries")

        # Increment vector clock for this device
        entry.increment_clock(self.device_id)
        self._entries[entry.path] = entry
        self.modified = datetime.now()

    def get_entry(self, path: str) -> Optional[FileEntry]:
        """Get entry by path."""
        return self._entries.get(path)

    def remove_entry(self, path: str) -> bool:
        """
        Remove entry by path.

        Returns:
            True if entry was removed
        """
        if path in self._entries:
            del self._entries[path]
            self.modified = datetime.now()
            return True
        return False

    def has_entry(self, path: str) -> bool:
        """Check if entry exists."""
        return path in self._entries

    # =========================================================================
    # Comparison and Merge
    # =========================================================================

    def diff(self, other: "SyncManifest") -> Dict[str, List[str]]:
        """
        Compare manifests and find differences.

        Returns:
            Dictionary with keys:
            - added: paths in self but not other
            - removed: paths in other but not self
            - modified: paths with different hashes
            - conflicts: paths with conflicting changes
        """
        my_paths = set(self._entries.keys())
        other_paths = set(other._entries.keys())

        added = my_paths - other_paths
        removed = other_paths - my_paths
        common = my_paths & other_paths

        modified = []
        conflicts = []

        for path in common:
            my_entry = self._entries[path]
            other_entry = other._entries[path]

            if my_entry.content_hash != other_entry.content_hash:
                if my_entry.conflicts_with(other_entry):
                    conflicts.append(path)
                else:
                    modified.append(path)

        return {
            "added": sorted(added),
            "removed": sorted(removed),
            "modified": sorted(modified),
            "conflicts": sorted(conflicts),
        }

    def merge(
        self,
        other: "SyncManifest",
        conflict_resolution: str = "last_write_wins",
    ) -> List[str]:
        """
        Merge another manifest into this one.

        Args:
            other: Manifest to merge from
            conflict_resolution: Strategy for conflicts
                - "last_write_wins": Use most recent modification
                - "keep_local": Keep local version
                - "keep_remote": Keep remote version

        Returns:
            List of paths that had conflicts
        """
        conflicts = []

        for path, other_entry in other._entries.items():
            if path in self._entries:
                my_entry = self._entries[path]

                if my_entry.content_hash == other_entry.content_hash:
                    # Same content, merge vector clocks
                    for device, version in other_entry.vector_clock.items():
                        current = my_entry.vector_clock.get(device, 0)
                        my_entry.vector_clock[device] = max(current, version)

                elif my_entry.conflicts_with(other_entry):
                    conflicts.append(path)

                    if conflict_resolution == "last_write_wins":
                        if other_entry.modified > my_entry.modified:
                            self._entries[path] = other_entry
                    elif conflict_resolution == "keep_remote":
                        self._entries[path] = other_entry
                    # keep_local: do nothing

                else:
                    # No conflict, take newer version
                    if other_entry.is_newer_than(my_entry, self.device_id):
                        self._entries[path] = other_entry

            else:
                # New entry from other
                self._entries[path] = other_entry

        # Register other devices
        for device_id, device_info in other._devices.items():
            if device_id not in self._devices:
                self._devices[device_id] = device_info

        self.modified = datetime.now()
        return conflicts

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """Serialize manifest to dictionary."""
        return {
            "version": self.version,
            "device_id": self.device_id,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "entries": [e.to_dict() for e in self.entries],  # Sorted
            "devices": {k: v.to_dict() for k, v in self._devices.items()},
        }

    def to_json(self, indent: int = None) -> str:
        """
        Serialize manifest to JSON.

        Args:
            indent: JSON indentation (None for compact)

        Returns:
            JSON string
        """
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_bytes(self) -> bytes:
        """Serialize manifest to bytes (UTF-8 JSON)."""
        return self.to_json().encode("utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> "SyncManifest":
        """Deserialize manifest from dictionary."""
        version = data.get("version", 1)

        if version > MANIFEST_VERSION:
            raise ManifestVersionError(
                f"Manifest version {version} not supported (max {MANIFEST_VERSION})"
            )

        device_id = data.get("device_id", "unknown")
        manifest = cls(device_id=device_id)

        manifest.version = version
        manifest.created = datetime.fromisoformat(data.get("created", datetime.now().isoformat()))
        manifest.modified = datetime.fromisoformat(data.get("modified", datetime.now().isoformat()))

        # Load entries
        for entry_data in data.get("entries", []):
            entry = FileEntry.from_dict(entry_data)
            manifest._entries[entry.path] = entry

        # Load devices
        for device_id, device_data in data.get("devices", {}).items():
            manifest._devices[device_id] = DeviceInfo.from_dict(device_data)

        return manifest

    @classmethod
    def from_json(cls, json_str: str) -> "SyncManifest":
        """Deserialize manifest from JSON string."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ManifestCorruptError(f"Invalid JSON: {e}")

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncManifest":
        """Deserialize manifest from bytes."""
        try:
            return cls.from_json(data.decode("utf-8"))
        except UnicodeDecodeError as e:
            raise ManifestCorruptError(f"Invalid UTF-8: {e}")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def compute_checksum(self) -> str:
        """
        Compute checksum of manifest content.

        Used to detect changes.
        """
        content = self.to_json()
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def update_device_sync_time(self) -> None:
        """Update last sync time for this device."""
        if self.device_id in self._devices:
            self._devices[self.device_id].last_sync = datetime.now()
        self.modified = datetime.now()

    def get_stale_entries(self, max_age_days: int = 30) -> List[str]:
        """
        Get entries not modified in max_age_days.

        Returns:
            List of paths to stale entries
        """
        cutoff = datetime.now().timestamp() - (max_age_days * 86400)
        return [
            e.path for e in self.entries
            if e.modified.timestamp() < cutoff
        ]


__all__ = [
    "SyncManifest",
    "FileEntry",
    "DeviceInfo",
    "ManifestError",
    "ManifestVersionError",
    "ManifestCorruptError",
    "MANIFEST_VERSION",
    "MANIFEST_FILENAME",
    "MAX_ENTRIES",
]
