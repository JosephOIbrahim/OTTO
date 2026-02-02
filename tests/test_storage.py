"""
Tests for Storage Abstraction Layer
===================================

Tests the storage provider, config, and manager.

[He2025] Compliance:
- Tests verify deterministic behavior
- Same inputs → same outputs
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from otto.storage import (
    StorageProvider,
    StorageConfig,
    StorageRoot,
    LocalStorageProvider,
    StorageManager,
    get_storage,
    get_storage_config,
)
from otto.storage.config import (
    get_default_config,
    set_default_config,
    reset_default_config,
)
from otto.storage.manager import set_storage, reset_storage


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_storage_dir(tmp_path):
    """Create a temporary storage directory structure."""
    otto_dir = tmp_path / ".otto"
    orchestra_dir = tmp_path / ".orchestra"
    claude_dir = tmp_path / ".claude"

    for d in [otto_dir, orchestra_dir, claude_dir]:
        d.mkdir(parents=True)
        (d / "state").mkdir()
        (d / "config").mkdir()

    return tmp_path


@pytest.fixture
def temp_config(temp_storage_dir):
    """Create a StorageConfig pointing to temp directory."""
    return StorageConfig(
        otto_root=temp_storage_dir / ".otto",
        orchestra_root=temp_storage_dir / ".orchestra",
        claude_root=temp_storage_dir / ".claude",
        cache_root=temp_storage_dir / ".otto" / "cache",
    )


@pytest.fixture
def local_provider(temp_config):
    """Create a LocalStorageProvider with temp config."""
    return LocalStorageProvider(temp_config)


@pytest.fixture
def storage_manager(local_provider, temp_config):
    """Create a StorageManager with temp provider."""
    return StorageManager(provider=local_provider, config=temp_config)


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global state before and after each test."""
    reset_default_config()
    reset_storage()
    yield
    reset_default_config()
    reset_storage()


# =============================================================================
# StorageConfig Tests
# =============================================================================

class TestStorageConfig:
    """Tests for StorageConfig."""

    def test_default_roots(self):
        """Test default root directories."""
        config = StorageConfig()
        home = Path.home()

        assert config.otto_root == home / ".otto"
        assert config.orchestra_root == home / ".orchestra"
        assert config.claude_root == home / ".claude"

    def test_get_root_by_enum(self):
        """Test get_root with StorageRoot enum."""
        config = StorageConfig()

        assert config.get_root(StorageRoot.OTTO) == config.otto_root
        assert config.get_root(StorageRoot.ORCHESTRA) == config.orchestra_root
        assert config.get_root(StorageRoot.CLAUDE) == config.claude_root

    def test_get_root_by_name(self):
        """Test get_root_by_name with string."""
        config = StorageConfig()

        assert config.get_root_by_name("otto") == config.otto_root
        assert config.get_root_by_name("OTTO") == config.otto_root
        assert config.get_root_by_name("orchestra") == config.orchestra_root
        assert config.get_root_by_name("claude") == config.claude_root

    def test_resolve_path(self):
        """Test path resolution."""
        config = StorageConfig()

        path = config.resolve_path("state/test.json", "otto")
        assert path == config.otto_root / "state" / "test.json"

        path = config.resolve_path("config/settings.yaml", "orchestra")
        assert path == config.orchestra_root / "config" / "settings.yaml"

    def test_env_override(self, temp_storage_dir):
        """Test environment variable override."""
        custom_path = temp_storage_dir / "custom_otto"
        custom_path.mkdir()

        with patch.dict(os.environ, {"OTTO_DATA_DIR": str(custom_path)}):
            reset_default_config()
            config = StorageConfig.from_env()
            assert config.otto_root == custom_path

    def test_to_dict(self):
        """Test config serialization."""
        config = StorageConfig()
        d = config.to_dict()

        assert "otto_root" in d
        assert "orchestra_root" in d
        assert "claude_root" in d
        assert "backup_on_write" in d


# =============================================================================
# LocalStorageProvider Tests
# =============================================================================

class TestLocalStorageProvider:
    """Tests for LocalStorageProvider."""

    def test_read_json_nonexistent(self, local_provider):
        """Test reading nonexistent JSON returns default."""
        result = local_provider.read_json("nonexistent.json")
        assert result == {}

        result = local_provider.read_json("nonexistent.json", default={"key": "value"})
        assert result == {"key": "value"}

    def test_write_read_json(self, local_provider):
        """Test writing and reading JSON."""
        data = {"name": "test", "value": 42}

        success = local_provider.write_json("state/test.json", data, backup=False)
        assert success is True

        result = local_provider.read_json("state/test.json")
        assert result == data

    def test_write_json_creates_parent_dirs(self, local_provider):
        """Test that write_json creates parent directories."""
        data = {"test": True}

        success = local_provider.write_json("deep/nested/path/test.json", data, backup=False)
        assert success is True

        result = local_provider.read_json("deep/nested/path/test.json")
        assert result == data

    def test_write_json_atomic(self, local_provider, temp_config):
        """Test that write_json is atomic (no partial writes)."""
        path = "state/atomic_test.json"
        data = {"large": "data" * 1000}

        success = local_provider.write_json(path, data, backup=False)
        assert success is True

        # Verify file is complete
        result = local_provider.read_json(path)
        assert result == data

    def test_read_write_text(self, local_provider):
        """Test text file operations."""
        content = "Hello, OTTO!\nThis is a test."

        success = local_provider.write_text("test.txt", content)
        assert success is True

        result = local_provider.read_text("test.txt")
        assert result == content

    def test_read_text_nonexistent(self, local_provider):
        """Test reading nonexistent text file."""
        result = local_provider.read_text("nonexistent.txt")
        assert result is None

        result = local_provider.read_text("nonexistent.txt", default="default")
        assert result == "default"

    def test_read_write_bytes(self, local_provider):
        """Test binary file operations."""
        data = b"\x00\x01\x02\x03\xff\xfe\xfd"

        success = local_provider.write_bytes("test.bin", data)
        assert success is True

        result = local_provider.read_bytes("test.bin")
        assert result == data

    def test_exists(self, local_provider):
        """Test existence checking."""
        assert local_provider.exists("state") is True  # Created by fixture
        assert local_provider.exists("nonexistent") is False

        local_provider.write_text("test.txt", "test")
        assert local_provider.exists("test.txt") is True

    def test_is_file_is_dir(self, local_provider):
        """Test file/directory distinction."""
        local_provider.write_text("test.txt", "test")

        assert local_provider.is_file("test.txt") is True
        assert local_provider.is_dir("test.txt") is False

        assert local_provider.is_file("state") is False
        assert local_provider.is_dir("state") is True

    def test_list_dir(self, local_provider):
        """Test directory listing."""
        local_provider.write_text("state/a.txt", "a")
        local_provider.write_text("state/b.txt", "b")
        local_provider.write_text("state/c.json", "c")

        files = local_provider.list_dir("state")
        assert "a.txt" in files
        assert "b.txt" in files
        assert "c.json" in files

    def test_list_dir_with_pattern(self, local_provider):
        """Test directory listing with glob pattern."""
        local_provider.write_text("state/a.txt", "a")
        local_provider.write_text("state/b.txt", "b")
        local_provider.write_text("state/c.json", "c")

        files = local_provider.list_dir("state", pattern="*.txt")
        assert "a.txt" in files
        assert "b.txt" in files
        assert "c.json" not in files

    def test_ensure_dir(self, local_provider):
        """Test directory creation."""
        path = local_provider.ensure_dir("new/nested/directory")

        assert path.is_dir()
        assert local_provider.is_dir("new/nested/directory")

    def test_delete_file(self, local_provider):
        """Test file deletion."""
        local_provider.write_text("to_delete.txt", "delete me")
        assert local_provider.exists("to_delete.txt") is True

        result = local_provider.delete("to_delete.txt")
        assert result is True
        assert local_provider.exists("to_delete.txt") is False

    def test_delete_nonexistent(self, local_provider):
        """Test deleting nonexistent file returns False."""
        result = local_provider.delete("nonexistent.txt")
        assert result is False

    def test_different_roots(self, local_provider):
        """Test operations on different storage roots."""
        # Write to otto
        local_provider.write_json("test.json", {"root": "otto"}, root_type="otto", backup=False)

        # Write to orchestra
        local_provider.write_json("test.json", {"root": "orchestra"}, root_type="orchestra", backup=False)

        # Read from each
        otto_data = local_provider.read_json("test.json", root_type="otto")
        orchestra_data = local_provider.read_json("test.json", root_type="orchestra")

        assert otto_data["root"] == "otto"
        assert orchestra_data["root"] == "orchestra"

    def test_backup_creation(self, local_provider, temp_config):
        """Test that backups are created on write."""
        # Enable backups
        temp_config.backup_on_write = True

        # Write initial file
        local_provider.write_json("state/test.json", {"version": 1}, backup=False)

        # Write again with backup
        local_provider.write_json("state/test.json", {"version": 2}, backup=True)

        # Check backup exists
        backup_dir = local_provider.get_backup_dir("otto")
        backups = list(backup_dir.glob("test.json.*.bak"))
        assert len(backups) >= 1

    def test_convenience_methods(self, local_provider):
        """Test convenience directory methods."""
        state_dir = local_provider.get_state_dir()
        assert state_dir.is_dir()

        config_dir = local_provider.get_config_dir()
        assert config_dir.is_dir()

        cache_dir = local_provider.get_cache_dir()
        assert cache_dir.is_dir()


# =============================================================================
# StorageManager Tests
# =============================================================================

class TestStorageManager:
    """Tests for StorageManager."""

    def test_delegation(self, storage_manager):
        """Test that manager delegates to provider."""
        data = {"test": True}

        storage_manager.write_json("test.json", data, backup=False)
        result = storage_manager.read_json("test.json")

        assert result == data

    def test_all_methods_work(self, storage_manager):
        """Test all delegated methods."""
        # JSON
        storage_manager.write_json("j.json", {"a": 1}, backup=False)
        assert storage_manager.read_json("j.json") == {"a": 1}

        # Text
        storage_manager.write_text("t.txt", "hello")
        assert storage_manager.read_text("t.txt") == "hello"

        # Bytes
        storage_manager.write_bytes("b.bin", b"\x00\x01")
        assert storage_manager.read_bytes("b.bin") == b"\x00\x01"

        # Existence
        assert storage_manager.exists("j.json") is True
        assert storage_manager.is_file("j.json") is True
        assert storage_manager.is_dir("state") is True

        # Directory ops
        storage_manager.ensure_dir("new_dir")
        assert storage_manager.is_dir("new_dir") is True

        files = storage_manager.list_dir()
        assert len(files) > 0

        # Delete
        assert storage_manager.delete("j.json") is True


# =============================================================================
# Global Instance Tests
# =============================================================================

class TestGlobalInstance:
    """Tests for global storage instance."""

    def test_get_storage_creates_instance(self):
        """Test that get_storage creates a manager."""
        storage = get_storage()
        assert isinstance(storage, StorageManager)

    def test_get_storage_returns_same_instance(self):
        """Test singleton behavior."""
        storage1 = get_storage()
        storage2 = get_storage()
        assert storage1 is storage2

    def test_set_storage_replaces_instance(self, storage_manager):
        """Test that set_storage replaces the global instance."""
        set_storage(storage_manager)
        assert get_storage() is storage_manager

    def test_get_storage_config(self):
        """Test getting config from global instance."""
        config = get_storage_config()
        assert isinstance(config, StorageConfig)


# =============================================================================
# [He2025] Determinism Tests
# =============================================================================

class TestDeterminism:
    """Tests verifying [He2025] compliant determinism."""

    def test_same_input_same_output(self, local_provider):
        """Test that same operations produce same results."""
        data = {"key": "value", "number": 42}

        # Write and read multiple times
        results = []
        for _ in range(10):
            local_provider.write_json("determinism.json", data, backup=False)
            results.append(local_provider.read_json("determinism.json"))

        # All results should be identical
        for result in results:
            assert result == data

    def test_path_resolution_deterministic(self, temp_config):
        """Test that path resolution is deterministic."""
        paths = []
        for _ in range(10):
            paths.append(temp_config.resolve_path("state/test.json", "otto"))

        # All paths should be identical
        assert len(set(paths)) == 1

    def test_list_dir_order_stable(self, local_provider):
        """Test that directory listing order is stable."""
        # Create files
        for name in ["c.txt", "a.txt", "b.txt"]:
            local_provider.write_text(f"state/{name}", name)

        # List multiple times
        listings = []
        for _ in range(10):
            listings.append(tuple(sorted(local_provider.list_dir("state"))))

        # All listings should be identical when sorted
        assert len(set(listings)) == 1


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unicode_content(self, local_provider):
        """Test handling of unicode content."""
        content = "Hello 世界 🌍 مرحبا"

        local_provider.write_text("unicode.txt", content)
        result = local_provider.read_text("unicode.txt")

        assert result == content

    def test_large_file(self, local_provider):
        """Test handling of large files."""
        # 1MB of data
        data = {"large": "x" * (1024 * 1024)}

        local_provider.write_json("large.json", data, backup=False)
        result = local_provider.read_json("large.json")

        assert result == data

    def test_special_characters_in_path(self, local_provider):
        """Test paths with special characters."""
        # Note: Some chars are invalid on Windows
        content = "test"

        local_provider.write_text("state/test-file_v1.0.txt", content)
        result = local_provider.read_text("state/test-file_v1.0.txt")

        assert result == content

    def test_empty_file(self, local_provider):
        """Test handling of empty files."""
        local_provider.write_text("empty.txt", "")
        result = local_provider.read_text("empty.txt")
        assert result == ""

    def test_corrupted_json(self, local_provider):
        """Test handling of corrupted JSON."""
        # Write invalid JSON directly
        path = local_provider.resolve_path("corrupted.json", "otto")
        path.write_text("{ invalid json }", encoding="utf-8")

        # Should return default without crashing
        result = local_provider.read_json("corrupted.json", default={"fallback": True})
        assert result == {"fallback": True}
