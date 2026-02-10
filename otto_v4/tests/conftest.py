"""Shared test fixtures for OTTO v4."""

import pytest

from otto.store import CommitmentStore


@pytest.fixture()
def store(tmp_path) -> CommitmentStore:
    """Provide a CommitmentStore backed by a temp directory."""
    db_path = str(tmp_path / "test_commitments.db")
    return CommitmentStore(db_path=db_path)
