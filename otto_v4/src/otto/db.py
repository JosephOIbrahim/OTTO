"""Centralized SQLite connection management for OTTO.

Provides a thread-safe connection cache (one connection per thread,
since SQLite connections cannot be safely shared across threads).

Usage:
    db = Database("~/.otto/commitments.db")
    with db.connect() as conn:
        conn.execute("SELECT ...")
    db.close()  # Call on shutdown
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class Database:
    """Thread-local SQLite connection manager.

    Each thread gets its own connection, reused across calls.
    The context manager handles commit/rollback automatically.
    """

    def __init__(self, db_path: str) -> None:
        expanded = os.path.expanduser(db_path)
        self._db_path = Path(expanded)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    @property
    def path(self) -> Path:
        """Return the resolved database file path."""
        return self._db_path

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
            )
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    @contextmanager
    def connect(self):
        """Yield a connection with automatic commit/rollback."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        """Close the current thread's connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
