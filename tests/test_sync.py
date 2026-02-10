"""
Tests for Cloud Sync Module
===========================

Comprehensive tests for storage adapters, manifest, and sync engine.

Determinism Tests:
- Fixed protocol parameters
- Deterministic operations
- Bounded sync operations
"""

import os
import pytest
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from otto.sync.storage_adapter import (
    StorageAdapter,
    LocalStorageAdapter,
    StorageType,
    StorageInfo,
    RemoteFile,
    StorageError,
    AuthenticationError,
    QuotaExceededError,
    FileNotFoundError as SyncFileNotFoundError,
    ConnectionError,
    create_storage_adapter,
    CHUNK_SIZE,
    MAX_RETRIES,
    OTTO_FOLDER,
)

from otto.sync.manifest import (
    SyncManifest,
    FileEntry,
    DeviceInfo,
    ManifestError,
    ManifestVersionError,
    ManifestCorruptError,
    MANIFEST_VERSION,
    MANIFEST_FILENAME,
    MAX_ENTRIES,
)

from otto.sync.sync_engine import (
    SyncEngine,
    SyncConfig,
    SyncStatus,
    SyncResult,
    ConflictResolution,
    SyncError,
    SyncConflictError,
    SYNC_PROTOCOL_VERSION,
    MAX_FILES_PER_SYNC,
)


# =============================================================================
# Storage Adapter Constants Tests
# =============================================================================

class TestStorageAdapterConstants:
    """Tests for storage adapter constants (determinism compliance)."""

    def test_chunk_size_fixed(self):
        """Chunk size is fixed at 5 MiB."""
        assert CHUNK_SIZE == 5 * 1024 * 1024

    def test_max_retries_fixed(self):
        """Max retries is fixed at 3."""
        assert MAX_RETRIES == 3

    def test_otto_folder_fixed(self):
        """OTTO folder name is fixed."""
        assert OTTO_FOLDER == ".otto-sync"


# =============================================================================
# RemoteFile Tests
# =============================================================================

class TestRemoteFile:
    """Tests for RemoteFile dataclass."""

    def test_create_remote_file(self):
        """Create remote file."""
        rf = RemoteFile(
            path="test/file.txt",
            size=1024,
            modified=datetime.now(),
        )
        assert rf.path == "test/file.txt"
        assert rf.size == 1024

    def test_to_dict_and_back(self):
        """Roundtrip through dictionary."""
        rf = RemoteFile(
            path="test/file.txt",
            size=1024,
            modified=datetime.now(),
            etag="abc123",
            content_hash="sha256...",
        )
        data = rf.to_dict()
        restored = RemoteFile.from_dict(data)

        assert restored.path == rf.path
        assert restored.size == rf.size
        assert restored.etag == rf.etag


# =============================================================================
# LocalStorageAdapter Tests
# =============================================================================

class TestLocalStorageAdapter:
    """Tests for local filesystem storage adapter."""

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    async def adapter(self, temp_dir):
        """Create connected adapter."""
        adapter = LocalStorageAdapter(temp_dir)
        await adapter.connect()
        yield adapter
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_connect_creates_otto_folder(self, temp_dir):
        """Connect creates OTTO folder."""
        adapter = LocalStorageAdapter(temp_dir)
        await adapter.connect()

        otto_path = temp_dir / OTTO_FOLDER
        assert otto_path.exists()

    @pytest.mark.asyncio
    async def test_upload_download_roundtrip(self, adapter, temp_dir):
        """Upload then download returns same data."""
        data = b"Hello, OTTO Sync!"
        path = f"{OTTO_FOLDER}/test.enc"

        await adapter.upload(path, data)
        downloaded = await adapter.download(path)

        assert downloaded == data

    @pytest.mark.asyncio
    async def test_upload_returns_remote_file(self, adapter):
        """Upload returns RemoteFile metadata."""
        data = b"Test data"
        path = f"{OTTO_FOLDER}/test.enc"

        result = await adapter.upload(path, data)

        assert isinstance(result, RemoteFile)
        assert result.path == path
        assert result.size == len(data)

    @pytest.mark.asyncio
    async def test_download_nonexistent_raises(self, adapter):
        """Download nonexistent file raises."""
        with pytest.raises(SyncFileNotFoundError):
            await adapter.download(f"{OTTO_FOLDER}/nonexistent.enc")

    @pytest.mark.asyncio
    async def test_delete_file(self, adapter, temp_dir):
        """Delete removes file."""
        data = b"To be deleted"
        path = f"{OTTO_FOLDER}/delete.enc"

        await adapter.upload(path, data)
        await adapter.delete(path)

        with pytest.raises(SyncFileNotFoundError):
            await adapter.download(path)

    @pytest.mark.asyncio
    async def test_list_files(self, adapter):
        """List returns uploaded files."""
        await adapter.upload(f"{OTTO_FOLDER}/file1.enc", b"data1")
        await adapter.upload(f"{OTTO_FOLDER}/file2.enc", b"data2")

        files = await adapter.list_files(OTTO_FOLDER)

        paths = [f.path for f in files]
        assert any("file1" in p for p in paths)
        assert any("file2" in p for p in paths)

    @pytest.mark.asyncio
    async def test_exists_true(self, adapter):
        """Exists returns True for existing file."""
        path = f"{OTTO_FOLDER}/exists.enc"
        await adapter.upload(path, b"data")

        assert await adapter.exists(path)

    @pytest.mark.asyncio
    async def test_exists_false(self, adapter):
        """Exists returns False for missing file."""
        assert not await adapter.exists(f"{OTTO_FOLDER}/missing.enc")

    @pytest.mark.asyncio
    async def test_compute_content_hash(self, adapter):
        """Content hash is computed correctly."""
        data = b"test content"
        hash1 = adapter.compute_content_hash(data)
        hash2 = adapter.compute_content_hash(data)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex


class TestStorageAdapterFactory:
    """Tests for storage adapter factory."""

    def test_create_local_adapter(self):
        """Create local adapter."""
        with tempfile.TemporaryDirectory() as d:
            adapter = create_storage_adapter("local", base_path=d)
            assert isinstance(adapter, LocalStorageAdapter)

    def test_create_local_missing_path(self):
        """Local adapter requires base_path."""
        with pytest.raises(ValueError):
            create_storage_adapter("local")

    def test_unknown_type_raises(self):
        """Unknown type raises ValueError."""
        with pytest.raises(ValueError):
            create_storage_adapter("unknown")


# =============================================================================
# Manifest Constants Tests
# =============================================================================

class TestManifestConstants:
    """Tests for manifest constants (determinism compliance)."""

    def test_version_fixed(self):
        """Manifest version is fixed."""
        assert MANIFEST_VERSION == 1

    def test_filename_fixed(self):
        """Manifest filename is fixed."""
        assert MANIFEST_FILENAME == "manifest.enc"

    def test_max_entries_fixed(self):
        """Max entries is bounded."""
        assert MAX_ENTRIES == 10000


# =============================================================================
# FileEntry Tests
# =============================================================================

class TestFileEntry:
    """Tests for FileEntry dataclass."""

    def test_create_entry(self):
        """Create file entry."""
        entry = FileEntry(
            path="test/file.usda",
            content_hash="abc123",
            size=1024,
            modified=datetime.now(),
        )
        assert entry.path == "test/file.usda"
        assert entry.size == 1024

    def test_to_dict_and_back(self):
        """Roundtrip through dictionary."""
        entry = FileEntry(
            path="test/file.usda",
            content_hash="abc123",
            size=1024,
            modified=datetime.now(),
            vector_clock={"device1": 3},
        )
        data = entry.to_dict()
        restored = FileEntry.from_dict(data)

        assert restored.path == entry.path
        assert restored.vector_clock == entry.vector_clock

    def test_increment_clock(self):
        """Increment vector clock."""
        entry = FileEntry(
            path="test.usda",
            content_hash="abc",
            size=100,
            modified=datetime.now(),
        )
        entry.increment_clock("device1")
        entry.increment_clock("device1")
        entry.increment_clock("device2")

        assert entry.vector_clock["device1"] == 2
        assert entry.vector_clock["device2"] == 1

    def test_conflict_detection(self):
        """Conflict detection with vector clocks."""
        # Entry 1: device1=2, device2=1
        entry1 = FileEntry(
            path="test.usda",
            content_hash="hash1",
            size=100,
            modified=datetime.now(),
            vector_clock={"device1": 2, "device2": 1},
        )

        # Entry 2: device1=1, device2=2 (concurrent edit)
        entry2 = FileEntry(
            path="test.usda",
            content_hash="hash2",
            size=100,
            modified=datetime.now(),
            vector_clock={"device1": 1, "device2": 2},
        )

        assert entry1.conflicts_with(entry2)

    def test_no_conflict_same_hash(self):
        """Same hash means no conflict."""
        entry1 = FileEntry(
            path="test.usda",
            content_hash="same_hash",
            size=100,
            modified=datetime.now(),
            vector_clock={"device1": 1},
        )
        entry2 = FileEntry(
            path="test.usda",
            content_hash="same_hash",
            size=100,
            modified=datetime.now(),
            vector_clock={"device2": 1},
        )

        assert not entry1.conflicts_with(entry2)


# =============================================================================
# SyncManifest Tests
# =============================================================================

class TestSyncManifest:
    """Tests for SyncManifest."""

    def test_create_manifest(self):
        """Create empty manifest."""
        manifest = SyncManifest(
            device_id="test-device",
            device_name="Test Laptop",
        )

        assert manifest.device_id == "test-device"
        assert manifest.entry_count == 0

    def test_add_entry(self):
        """Add file entry."""
        manifest = SyncManifest(device_id="test")
        entry = FileEntry(
            path="data/file.usda",
            content_hash="abc123",
            size=1024,
            modified=datetime.now(),
        )

        manifest.add_entry(entry)

        assert manifest.entry_count == 1
        assert manifest.has_entry("data/file.usda")

    def test_get_entry(self):
        """Get entry by path."""
        manifest = SyncManifest(device_id="test")
        entry = FileEntry(
            path="data/file.usda",
            content_hash="abc123",
            size=1024,
            modified=datetime.now(),
        )
        manifest.add_entry(entry)

        retrieved = manifest.get_entry("data/file.usda")

        assert retrieved is not None
        assert retrieved.content_hash == "abc123"

    def test_remove_entry(self):
        """Remove entry."""
        manifest = SyncManifest(device_id="test")
        entry = FileEntry(
            path="data/file.usda",
            content_hash="abc123",
            size=1024,
            modified=datetime.now(),
        )
        manifest.add_entry(entry)

        removed = manifest.remove_entry("data/file.usda")

        assert removed
        assert not manifest.has_entry("data/file.usda")

    def test_entries_sorted(self):
        """Entries are returned sorted by path."""
        manifest = SyncManifest(device_id="test")

        manifest.add_entry(FileEntry("z/file.usda", "hash1", 100, datetime.now()))
        manifest.add_entry(FileEntry("a/file.usda", "hash2", 100, datetime.now()))
        manifest.add_entry(FileEntry("m/file.usda", "hash3", 100, datetime.now()))

        entries = manifest.entries
        paths = [e.path for e in entries]

        assert paths == sorted(paths)

    def test_to_json_and_back(self):
        """Roundtrip through JSON."""
        manifest = SyncManifest(device_id="test", device_name="Test")
        manifest.add_entry(FileEntry("file1.usda", "hash1", 100, datetime.now()))
        manifest.add_entry(FileEntry("file2.usda", "hash2", 200, datetime.now()))

        json_str = manifest.to_json()
        restored = SyncManifest.from_json(json_str)

        assert restored.device_id == manifest.device_id
        assert restored.entry_count == manifest.entry_count

    def test_diff_manifests(self):
        """Diff two manifests."""
        manifest1 = SyncManifest(device_id="device1")
        manifest1.add_entry(FileEntry("file1.usda", "hash1", 100, datetime.now()))
        manifest1.add_entry(FileEntry("file2.usda", "hash2", 100, datetime.now()))

        manifest2 = SyncManifest(device_id="device2")
        manifest2.add_entry(FileEntry("file2.usda", "hash2", 100, datetime.now()))
        manifest2.add_entry(FileEntry("file3.usda", "hash3", 100, datetime.now()))

        diff = manifest1.diff(manifest2)

        assert "file1.usda" in diff["added"]  # In manifest1, not manifest2
        assert "file3.usda" in diff["removed"]  # In manifest2, not manifest1

    def test_max_entries_enforced(self):
        """Max entries limit is enforced."""
        manifest = SyncManifest(device_id="test")

        # Add entries up to limit
        for i in range(MAX_ENTRIES):
            manifest._entries[f"file{i}.usda"] = FileEntry(
                f"file{i}.usda", f"hash{i}", 100, datetime.now()
            )

        # Adding one more should fail
        with pytest.raises(ManifestError):
            manifest.add_entry(FileEntry("overflow.usda", "hash", 100, datetime.now()))


# =============================================================================
# SyncEngine Constants Tests
# =============================================================================

class TestSyncEngineConstants:
    """Tests for sync engine constants (determinism compliance)."""

    def test_protocol_version_fixed(self):
        """Protocol version is fixed."""
        assert SYNC_PROTOCOL_VERSION == 1

    def test_max_files_per_sync_fixed(self):
        """Max files per sync is bounded."""
        assert MAX_FILES_PER_SYNC == 100


# =============================================================================
# SyncConfig Tests
# =============================================================================

class TestSyncConfig:
    """Tests for SyncConfig."""

    def test_create_config(self):
        """Create sync config."""
        key = os.urandom(32)
        config = SyncConfig(
            local_data_path=Path("/tmp/otto"),
            encryption_key=key,
            device_name="Test Device",
        )

        assert config.encryption_key == key
        assert config.device_name == "Test Device"

    def test_to_dict_excludes_key(self):
        """to_dict excludes encryption key."""
        key = os.urandom(32)
        config = SyncConfig(
            local_data_path=Path("/tmp/otto"),
            encryption_key=key,
        )

        data = config.to_dict()

        assert "encryption_key" not in data


# =============================================================================
# SyncResult Tests
# =============================================================================

class TestSyncResult:
    """Tests for SyncResult."""

    def test_create_result(self):
        """Create sync result."""
        result = SyncResult(
            success=True,
            status=SyncStatus.COMPLETE,
            uploaded=["file1.usda"],
            downloaded=["file2.usda"],
        )

        assert result.success
        assert result.status == SyncStatus.COMPLETE

    def test_to_dict(self):
        """Serialize result."""
        result = SyncResult(
            success=True,
            status=SyncStatus.COMPLETE,
        )
        result.completed = datetime.now()

        data = result.to_dict()

        assert data["success"] is True
        assert data["status"] == "complete"


# =============================================================================
# SyncEngine Tests
# =============================================================================

class TestSyncEngine:
    """Tests for SyncEngine."""

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def encryption_key(self):
        """Generate test key."""
        return os.urandom(32)

    @pytest.fixture
    async def storage(self, temp_dir):
        """Create connected storage adapter."""
        adapter = LocalStorageAdapter(temp_dir / "remote")
        await adapter.connect()
        yield adapter
        await adapter.disconnect()

    @pytest.fixture
    def config(self, temp_dir, encryption_key):
        """Create sync config."""
        return SyncConfig(
            local_data_path=temp_dir / "local",
            encryption_key=encryption_key,
            device_id="test-device",
            device_name="Test Device",
        )

    def test_create_engine(self, storage, config):
        """Create sync engine."""
        engine = SyncEngine(storage, config)

        assert engine.status == SyncStatus.IDLE
        assert engine.config == config

    def test_cancel_sets_flag(self, storage, config):
        """Cancel sets flag."""
        engine = SyncEngine(storage, config)
        engine.cancel()

        assert engine._cancel_requested

    @pytest.mark.asyncio
    async def test_sync_empty_local(self, storage, config, temp_dir):
        """Sync with empty local directory."""
        # Create local data directory
        (temp_dir / "local").mkdir()

        engine = SyncEngine(storage, config)
        result = await engine.sync()

        assert result.success
        assert result.status == SyncStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_sync_uploads_new_file(self, storage, config, temp_dir):
        """Sync uploads new local file."""
        # Create local file
        local_dir = temp_dir / "local"
        local_dir.mkdir()
        test_file = local_dir / "test.usda"
        test_file.write_text("# Test USD file")

        engine = SyncEngine(storage, config)
        result = await engine.sync()

        assert result.success
        assert "test.usda" in result.uploaded

    @pytest.mark.asyncio
    async def test_status_callback(self, storage, config, temp_dir):
        """Progress callback is called."""
        (temp_dir / "local").mkdir()

        statuses = []

        def on_progress(status, message):
            statuses.append(status)

        engine = SyncEngine(storage, config)
        engine.on_progress(on_progress)

        await engine.sync()

        assert SyncStatus.CONNECTING in statuses
        assert SyncStatus.COMPLETE in statuses


# =============================================================================
# Integration Tests
# =============================================================================

class TestSyncIntegration:
    """Integration tests for full sync workflow."""

    @pytest.fixture
    def temp_dir(self):
        """Create temp directory."""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def encryption_key(self):
        """Generate test key."""
        return os.urandom(32)

    @pytest.mark.asyncio
    async def test_two_device_sync(self, temp_dir, encryption_key):
        """Sync between two simulated devices."""
        # Setup
        remote_dir = temp_dir / "remote"
        device1_dir = temp_dir / "device1"
        device2_dir = temp_dir / "device2"

        device1_dir.mkdir()
        device2_dir.mkdir()

        # Create shared storage
        storage1 = LocalStorageAdapter(remote_dir)
        storage2 = LocalStorageAdapter(remote_dir)

        await storage1.connect()
        await storage2.connect()

        # Config for both devices
        config1 = SyncConfig(
            local_data_path=device1_dir,
            encryption_key=encryption_key,
            device_id="device1",
        )
        config2 = SyncConfig(
            local_data_path=device2_dir,
            encryption_key=encryption_key,
            device_id="device2",
        )

        # Create file on device1
        (device1_dir / "shared.usda").write_text("# Created on device1")

        # Sync device1
        engine1 = SyncEngine(storage1, config1)
        result1 = await engine1.sync()

        assert result1.success
        assert "shared.usda" in result1.uploaded

        # Sync device2
        engine2 = SyncEngine(storage2, config2)
        result2 = await engine2.sync()

        assert result2.success
        assert "shared.usda" in result2.downloaded

        # Verify file on device2
        assert (device2_dir / "shared.usda").exists()

        await storage1.disconnect()
        await storage2.disconnect()


# =============================================================================
# Determinism Compliance Tests
# =============================================================================

class TestDeterminismCompliance:
    """Tests verifying determinism ([He2025])."""

    def test_fixed_protocol_parameters(self):
        """Protocol parameters are fixed."""
        assert SYNC_PROTOCOL_VERSION == 1
        assert MAX_FILES_PER_SYNC == 100
        assert CHUNK_SIZE == 5 * 1024 * 1024
        assert MAX_RETRIES == 3

    def test_deterministic_manifest_serialization(self):
        """Manifest serialization is deterministic."""
        manifest = SyncManifest(device_id="test")

        # Add entries in random order
        manifest.add_entry(FileEntry("z.usda", "hash1", 100, datetime.now()))
        manifest.add_entry(FileEntry("a.usda", "hash2", 100, datetime.now()))

        json1 = manifest.to_json()
        json2 = manifest.to_json()

        assert json1 == json2

    def test_deterministic_conflict_resolution(self):
        """Conflict resolution is deterministic."""
        # Create two entries with same modification time
        now = datetime.now()

        entry1 = FileEntry("test.usda", "hash1", 100, now, {"d1": 1})
        entry2 = FileEntry("test.usda", "hash2", 100, now, {"d2": 1})

        # Should consistently detect conflict
        assert entry1.conflicts_with(entry2)
        assert entry2.conflicts_with(entry1)

    def test_bounded_manifest_entries(self):
        """Manifest entries are bounded."""
        assert MAX_ENTRIES == 10000  # Fixed bound

    def test_bounded_sync_files(self):
        """Files per sync are bounded."""
        assert MAX_FILES_PER_SYNC == 100  # Fixed bound
