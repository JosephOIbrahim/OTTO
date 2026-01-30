"""
Atomic file operations for Framework Orchestrator.

Prevents data corruption by using write-to-temp-then-rename pattern.
This ensures state files are never partially written.

Pattern from Cognitive Orchestrator: Never persist bad state.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Union

logger = logging.getLogger(__name__)


class AtomicWriteError(Exception):
    """Raised when atomic write fails."""
    pass


def atomic_write_json(
    path: Union[str, Path],
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
    default: callable = str
) -> None:
    """
    Atomically write JSON data to a file.

    Uses write-to-temp-then-rename pattern to ensure the file is never
    partially written. If the write fails, the original file is preserved.

    Args:
        path: Target file path
        data: Data to serialize as JSON
        indent: JSON indentation (default: 2)
        ensure_ascii: Whether to escape non-ASCII characters (default: False)
        default: Function for serializing non-standard types (default: str)

    Raises:
        AtomicWriteError: If the write operation fails

    Example:
        >>> atomic_write_json(Path("state.json"), {"status": "ok"})
    """
    path = Path(path)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize JSON first (fail fast if data is not serializable)
    try:
        json_content = json.dumps(
            data,
            indent=indent,
            ensure_ascii=ensure_ascii,
            default=default,
            sort_keys=True  # Deterministic output
        )
    except (TypeError, ValueError) as e:
        raise AtomicWriteError(f"Failed to serialize JSON: {e}") from e

    # Write to temp file in same directory (ensures same filesystem for atomic rename)
    temp_fd = None
    temp_path = None

    try:
        # Create temp file in same directory as target
        temp_fd, temp_path = tempfile.mkstemp(
            suffix='.tmp',
            prefix=f'.{path.name}.',
            dir=path.parent
        )

        # Write content
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            temp_fd = None  # fdopen takes ownership
            f.write(json_content)
            f.flush()
            os.fsync(f.fileno())  # Ensure data is on disk

        # Atomic rename (on POSIX this is atomic; on Windows it replaces)
        temp_path_obj = Path(temp_path)
        temp_path_obj.replace(path)
        temp_path = None  # Rename succeeded, don't clean up

        logger.debug(f"Atomic write completed: {path}")

    except Exception as e:
        raise AtomicWriteError(f"Failed to write {path}: {e}") from e

    finally:
        # Clean up temp file if it still exists (write failed)
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def atomic_write_text(
    path: Union[str, Path],
    content: str,
    encoding: str = 'utf-8'
) -> None:
    """
    Atomically write text content to a file.

    Args:
        path: Target file path
        content: Text content to write
        encoding: Character encoding (default: utf-8)

    Raises:
        AtomicWriteError: If the write operation fails
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_fd = None
    temp_path = None

    try:
        temp_fd, temp_path = tempfile.mkstemp(
            suffix='.tmp',
            prefix=f'.{path.name}.',
            dir=path.parent
        )

        with os.fdopen(temp_fd, 'w', encoding=encoding) as f:
            temp_fd = None
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        Path(temp_path).replace(path)
        temp_path = None

    except Exception as e:
        raise AtomicWriteError(f"Failed to write {path}: {e}") from e

    finally:
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def safe_read_json(
    path: Union[str, Path],
    default: Any = None
) -> Any:
    """
    Safely read JSON from a file.

    Returns default value if file doesn't exist or is invalid JSON.

    Args:
        path: File path to read
        default: Default value if file is missing or invalid

    Returns:
        Parsed JSON data or default value
    """
    path = Path(path)

    if not path.exists():
        logger.debug(f"File not found, using default: {path}")
        return default

    try:
        content = path.read_text(encoding='utf-8')
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in {path}: {e}")
        return default
    except Exception as e:
        logger.warning(f"Failed to read {path}: {e}")
        return default


def backup_file(path: Union[str, Path], suffix: str = '.bak') -> Path:
    """
    Create a backup copy of a file.

    Args:
        path: File to back up
        suffix: Backup file suffix (default: .bak)

    Returns:
        Path to the backup file

    Raises:
        FileNotFoundError: If source file doesn't exist
        AtomicWriteError: If backup fails
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Cannot backup non-existent file: {path}")

    backup_path = path.with_suffix(path.suffix + suffix)

    try:
        content = path.read_bytes()
        backup_path.write_bytes(content)
        logger.debug(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        raise AtomicWriteError(f"Failed to create backup of {path}: {e}") from e


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
