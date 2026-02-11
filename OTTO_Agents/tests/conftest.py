"""Shared fixtures for OTTO_Agents tests."""

import sys
from pathlib import Path

import pytest

# Ensure otto modules are importable
_otto_src = str(Path(__file__).resolve().parent.parent.parent / "otto_v4" / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

from otto.models import Commitment
from otto.state import StateStore
from otto.store import CommitmentStore


@pytest.fixture()
def store(tmp_path) -> CommitmentStore:
    """CommitmentStore backed by a temp directory."""
    return CommitmentStore(db_path=str(tmp_path / "test.db"))


@pytest.fixture()
def state_store(tmp_path) -> StateStore:
    """StateStore backed by a temp directory."""
    return StateStore(db_path=str(tmp_path / "test.db"))


@pytest.fixture()
def sample() -> Commitment:
    """A sample commitment for tests."""
    return Commitment(
        raw_message="I'll send the report to Sarah by Friday",
        commitment_text="send the report to Sarah",
        who_to="Sarah",
        source_chat="test",
    )
