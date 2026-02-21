"""Tests for centralized database connection management."""

from __future__ import annotations

import threading

import pytest

from otto.db import Database
from otto.state import StateStore
from otto.store import CommitmentStore


class TestConnectionReuse:
    def test_two_connects_same_connection(self, tmp_path):
        """Two connect() calls in the same thread return the same connection."""
        db = Database(str(tmp_path / "test.db"))
        with db.connect() as conn1:
            id1 = id(conn1)
        with db.connect() as conn2:
            id2 = id(conn2)
        assert id1 == id2

    def test_thread_isolation(self, tmp_path):
        """Connections differ across threads."""
        db = Database(str(tmp_path / "test.db"))
        ids = []

        def get_conn_id():
            with db.connect() as conn:
                ids.append(id(conn))

        t1 = threading.Thread(target=get_conn_id)
        t2 = threading.Thread(target=get_conn_id)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(ids) == 2
        assert ids[0] != ids[1]

    def test_rollback_on_exception(self, tmp_path):
        """Exception in context manager triggers rollback."""
        db = Database(str(tmp_path / "test.db"))
        with db.connect() as conn:
            conn.execute("CREATE TABLE t (x TEXT)")

        with pytest.raises(ValueError):
            with db.connect() as conn:
                conn.execute("INSERT INTO t VALUES ('hello')")
                raise ValueError("oops")

        with db.connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM t").fetchone()
            assert row[0] == 0  # Rolled back

    def test_close_releases_connection(self, tmp_path):
        """After close(), next connect() creates a new connection."""
        db = Database(str(tmp_path / "test.db"))
        with db.connect() as conn1:
            id1 = id(conn1)
        db.close()
        with db.connect() as conn2:
            id2 = id(conn2)
        assert id1 != id2


class TestSharedDatabase:
    def test_shared_db_across_stores(self, tmp_path):
        """CommitmentStore and StateStore can share a Database instance."""
        db = Database(str(tmp_path / "shared.db"))
        cs = CommitmentStore(db=db)
        ss = StateStore(db=db)

        # Both should work on the same database
        from otto.models import Commitment

        c = Commitment(
            raw_message="test",
            commitment_text="test",
            who_to="Bob",
            source_chat="cli",
        )
        cs.add(c, dedup=False)
        assert len(cs.get_active()) == 1

        state = ss.load()
        assert state.energy == "medium"  # Default

    def test_path_property(self, tmp_path):
        """Database.path returns the resolved path."""
        db = Database(str(tmp_path / "test.db"))
        assert db.path == tmp_path / "test.db"

    def test_backward_compat_db_path(self, tmp_path):
        """Stores still work when constructed with db_path (no db kwarg)."""
        db_path = str(tmp_path / "compat.db")
        cs = CommitmentStore(db_path=db_path)
        ss = StateStore(db_path=db_path)

        from otto.models import Commitment

        c = Commitment(
            raw_message="compat test",
            commitment_text="compat",
            who_to="Alice",
            source_chat="cli",
        )
        cs.add(c, dedup=False)
        assert len(cs.get_active()) == 1

        state = ss.load()
        assert state.energy == "medium"

    def test_creates_parent_dirs(self, tmp_path):
        """Database creates parent directories if they do not exist."""
        nested = tmp_path / "a" / "b" / "c"
        db = Database(str(nested / "test.db"))
        with db.connect() as conn:
            conn.execute("CREATE TABLE t (x TEXT)")
        assert (nested / "test.db").exists()
