"""
Tests for atomic file operations module.

Tests:
- atomic_write_json functionality
- atomic_write_text functionality
- safe_read_json with defaults
- Atomic write pattern (temp file then rename)
- Backup file creation
- Directory creation
- Error handling
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from file_ops import (
    AtomicWriteError,
    atomic_write_json,
    atomic_write_text,
    safe_read_json,
    backup_file,
    ensure_directory,
)


class TestAtomicWriteJson:
    """Test atomic_write_json functionality."""

    def test_writes_valid_json(self):
        """Should write valid JSON to file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            data = {"key": "value", "nested": {"inner": 123}}

            atomic_write_json(path, data)

            # Verify file exists and contains valid JSON
            assert path.exists()
            with open(path) as f:
                loaded = json.load(f)
            assert loaded == data

    def test_creates_parent_directories(self):
        """Should create parent directories if needed."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a" / "b" / "c" / "test.json"

            atomic_write_json(path, {"data": True})

            assert path.exists()

    def test_atomic_no_partial_write(self):
        """Should not leave partial file on error."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"

            # Create non-serializable object
            class NotSerializable:
                pass

            # Pass default=None to disable str fallback and trigger error
            with pytest.raises(AtomicWriteError):
                atomic_write_json(path, {"obj": NotSerializable()}, default=None)

            # File should not exist
            assert not path.exists()

    def test_no_temp_files_left(self):
        """Should not leave temp files behind."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"

            atomic_write_json(path, {"clean": True})

            # Check for temp files
            tmp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(tmp_files) == 0

    def test_respects_indent(self):
        """Should respect indent parameter."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"

            atomic_write_json(path, {"key": "value"}, indent=4)

            content = path.read_text()
            # Should have 4-space indentation
            assert "    \"key\"" in content

    def test_deterministic_output(self):
        """Should produce deterministic output (sorted keys)."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            data = {"z": 1, "a": 2, "m": 3}

            atomic_write_json(path, data)

            content = path.read_text()
            # Keys should be sorted: a, m, z
            assert content.index('"a"') < content.index('"m"')
            assert content.index('"m"') < content.index('"z"')

    def test_overwrites_existing(self):
        """Should overwrite existing file atomically."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"

            # Write initial
            atomic_write_json(path, {"version": 1})

            # Overwrite
            atomic_write_json(path, {"version": 2})

            data = json.loads(path.read_text())
            assert data["version"] == 2

    def test_accepts_path_string(self):
        """Should accept string path."""
        with TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.json")

            atomic_write_json(path, {"string_path": True})

            assert Path(path).exists()


class TestAtomicWriteText:
    """Test atomic_write_text functionality."""

    def test_writes_text(self):
        """Should write text content to file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"

            atomic_write_text(path, "Hello, World!")

            assert path.read_text() == "Hello, World!"

    def test_creates_parent_directories(self):
        """Should create parent directories."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sub" / "dir" / "test.txt"

            atomic_write_text(path, "content")

            assert path.exists()

    def test_utf8_encoding(self):
        """Should handle UTF-8 content."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"

            atomic_write_text(path, "Hello Unicode: \u4e2d\u6587")

            content = path.read_text(encoding='utf-8')
            assert "\u4e2d\u6587" in content

    def test_no_temp_files_left(self):
        """Should clean up temp files."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"

            atomic_write_text(path, "content")

            tmp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(tmp_files) == 0


class TestSafeReadJson:
    """Test safe_read_json functionality."""

    def test_reads_valid_json(self):
        """Should read valid JSON file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            path.write_text('{"key": "value"}')

            data = safe_read_json(path)

            assert data == {"key": "value"}

    def test_returns_default_for_missing(self):
        """Should return default for missing file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.json"

            data = safe_read_json(path, default={"default": True})

            assert data == {"default": True}

    def test_returns_default_for_invalid_json(self):
        """Should return default for invalid JSON."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.json"
            path.write_text("not valid json {{{")

            data = safe_read_json(path, default=[])

            assert data == []

    def test_default_is_none(self):
        """Should default to None."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing.json"

            data = safe_read_json(path)

            assert data is None

    def test_accepts_path_string(self):
        """Should accept string path."""
        with TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "test.json")
            Path(path).write_text('{"ok": true}')

            data = safe_read_json(path)

            assert data == {"ok": True}


class TestBackupFile:
    """Test backup_file functionality."""

    def test_creates_backup(self):
        """Should create backup copy."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "original.json"
            path.write_text('{"original": true}')

            backup_path = backup_file(path)

            assert backup_path.exists()
            assert backup_path.suffix == ".bak"
            content = json.loads(backup_path.read_text())
            assert content == {"original": True}

    def test_custom_suffix(self):
        """Should use custom suffix."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "file.txt"
            path.write_text("content")

            backup_path = backup_file(path, suffix=".backup")

            assert backup_path.name == "file.txt.backup"

    def test_raises_for_nonexistent(self):
        """Should raise for nonexistent file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.txt"

            with pytest.raises(FileNotFoundError):
                backup_file(path)

    def test_preserves_content(self):
        """Should preserve exact content."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "data.bin"
            original_content = b"\x00\x01\x02\xff"
            path.write_bytes(original_content)

            backup_path = backup_file(path)

            assert backup_path.read_bytes() == original_content


class TestEnsureDirectory:
    """Test ensure_directory functionality."""

    def test_creates_directory(self):
        """Should create directory if not exists."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "new" / "dir"

            result = ensure_directory(path)

            assert path.exists()
            assert path.is_dir()
            assert result == path

    def test_idempotent(self):
        """Should be idempotent (no error if exists)."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "existing"
            path.mkdir()

            # Should not raise
            result = ensure_directory(path)

            assert result == path

    def test_creates_parents(self):
        """Should create parent directories."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a" / "b" / "c" / "d"

            ensure_directory(path)

            assert path.exists()

    def test_accepts_string(self):
        """Should accept string path."""
        with TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "string_dir")

            result = ensure_directory(path)

            assert Path(path).exists()
            assert isinstance(result, Path)


class TestAtomicWriteErrorHandling:
    """Test error handling in atomic writes."""

    def test_error_on_non_serializable(self):
        """Should raise AtomicWriteError for non-serializable data."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"

            # Pass default=None to disable str fallback and trigger error
            with pytest.raises(AtomicWriteError) as exc_info:
                atomic_write_json(path, {"func": lambda x: x}, default=None)

            assert "Failed to serialize" in str(exc_info.value)

    def test_cleans_up_on_error(self):
        """Should clean up temp file on error."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"

            # Pass default=None to disable str fallback and trigger error
            try:
                atomic_write_json(path, {"bad": object()}, default=None)
            except AtomicWriteError:
                pass

            # No temp files should remain
            all_files = list(Path(tmpdir).glob("*"))
            assert len(all_files) == 0


class TestAtomicWriteIntegration:
    """Integration tests for atomic writes."""

    def test_roundtrip_json(self):
        """Should handle roundtrip write then read."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "roundtrip.json"
            original = {
                "string": "value",
                "number": 42,
                "float": 3.14,
                "bool": True,
                "null": None,
                "array": [1, 2, 3],
                "nested": {"deep": {"value": "here"}}
            }

            atomic_write_json(path, original)
            loaded = safe_read_json(path)

            assert loaded == original

    def test_overwrite_preserves_on_crash(self):
        """Simulated crash during write should preserve original."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "preserved.json"

            # Write initial valid data
            atomic_write_json(path, {"version": 1})

            # Attempt to write invalid data (should fail at serialization)
            # Pass default=None to disable str fallback and trigger error
            try:
                atomic_write_json(path, {"bad": lambda: None}, default=None)
            except AtomicWriteError:
                pass

            # Original should be preserved
            data = safe_read_json(path)
            assert data == {"version": 1}

