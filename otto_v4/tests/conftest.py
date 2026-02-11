"""Shared test fixtures for OTTO v4."""

import pytest

from otto.models import Commitment
from otto.store import CommitmentStore


@pytest.fixture()
def store(tmp_path) -> CommitmentStore:
    """Provide a CommitmentStore backed by a temp directory."""
    db_path = str(tmp_path / "test_commitments.db")
    return CommitmentStore(db_path=db_path)


@pytest.fixture()
def sample() -> Commitment:
    """Provide a sample commitment for tests."""
    return Commitment(
        raw_message="I'll send the report to Sarah by Friday",
        commitment_text="send the report to Sarah",
        who_to="Sarah",
        source_chat="test",
    )
