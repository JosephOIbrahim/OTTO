"""
Integration Test Fixtures
=========================

Fixtures for memory backbone integration tests.

These fixtures create REAL instances (not mocks) to test
actual memory behavior, trail deposits, and cross-surface state.

[He2025] Compliance:
- All fixtures use real implementations
- Temporary directories ensure test isolation
- Fixed seeds where applicable
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator

# Import memory components
from otto.memory.interface import OTTOMemory, get_memory, Episode, Outcome
from otto.trails.store import TrailStore
from otto.core.livrps import LIVRPSResolver, Layer, LayerType


@pytest.fixture
def temp_data_dir() -> Generator[Path, None, None]:
    """
    Create temporary directory for test data.

    Ensures test isolation - each test gets fresh storage.
    """
    temp_dir = tempfile.mkdtemp(prefix="otto_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def real_trail_store(temp_data_dir: Path) -> TrailStore:
    """
    Create a real TrailStore with temporary SQLite.

    Tests actual SQLite persistence, not mocks.
    """
    db_path = temp_data_dir / "trails.db"
    return TrailStore(db_path=db_path)


@pytest.fixture
def real_memory(temp_data_dir: Path) -> OTTOMemory:
    """
    Create a real OTTOMemory instance with temporary storage.

    This is the core fixture - tests the unified memory interface
    with actual persistence backends.
    """
    return OTTOMemory(data_dir=temp_data_dir)


@pytest.fixture
def memory_with_history(real_memory: OTTOMemory) -> OTTOMemory:
    """
    Memory pre-populated with test episodes and trails.

    Simulates a user who has been using OTTO for a while,
    with established trust patterns.
    """
    # Add historical episodes from different surfaces
    real_memory.record_episode(Episode(
        type="service.calendar.create",
        data={"title": "Dentist", "time": "2pm"},
        outcome=Outcome.SUCCESS,
        actor="mcp.calendar",
        service="calendar",
        resource="event:dentist",
    ))

    real_memory.record_episode(Episode(
        type="service.tasks.create",
        data={"title": "Buy milk"},
        outcome=Outcome.SUCCESS,
        actor="mcp.tasks",
        service="tasks",
        resource="task:milk",
    ))

    real_memory.record_episode(Episode(
        type="surface.cli.message",
        data={"message": "Schedule dentist appointment"},
        outcome=Outcome.SUCCESS,
        actor="cli",
        service="cli",
    ))

    # Build trail history (5 successful calendar creates = some trust)
    for _ in range(5):
        real_memory.deposit_trail(
            action="action.calendar.create",
            outcome=Outcome.SUCCESS,
        )

    return real_memory


@pytest.fixture
def livrps_resolver() -> LIVRPSResolver:
    """
    Create a fresh LIVRPS resolver for testing composition.
    """
    return LIVRPSResolver()


@pytest.fixture
def livrps_with_layers(livrps_resolver: LIVRPSResolver) -> LIVRPSResolver:
    """
    LIVRPS resolver pre-populated with test layers.

    Tests composition priority:
    LOCAL > INHERITS > VARIANTS > REFERENCES > PAYLOADS > SPECIALIZES
    """
    # Add layers in reverse priority (SPECIALIZES first)
    livrps_resolver.add_layer(Layer(
        layer_type=LayerType.SPECIALIZES,
        data={
            "burnout_level": "GREEN",
            "energy_level": "medium",
            "paradigm": "cortex",
        },
        name="constitutional",
    ))

    livrps_resolver.add_layer(Layer(
        layer_type=LayerType.REFERENCES,
        data={
            "preferred_think_depth": "standard",
        },
        name="calibration",
    ))

    livrps_resolver.add_layer(Layer(
        layer_type=LayerType.LOCAL,
        data={
            "burnout_level": "YELLOW",  # Overrides SPECIALIZES
        },
        name="session",
    ))

    return livrps_resolver


@pytest.fixture
def mock_surface():
    """
    Factory for creating mock surfaces for testing.
    """
    class MockSurface:
        def __init__(self, surface_id: str, memory: OTTOMemory):
            self.surface_id = surface_id
            self.memory = memory

        def record_action(self, action_type: str, data: dict):
            self.memory.record_episode(Episode(
                type=f"surface.{self.surface_id}.{action_type}",
                data=data,
                outcome=Outcome.SUCCESS,
                actor=self.surface_id,
                service=self.surface_id,
            ))

    return MockSurface


# Test data fixtures

@pytest.fixture
def sample_episode() -> Episode:
    """Sample episode for testing."""
    return Episode(
        type="test.sample",
        data={"key": "value"},
        outcome=Outcome.SUCCESS,
        actor="pytest",
        service="test",
        resource="fixture",
    )


@pytest.fixture
def sample_trail_name() -> str:
    """Sample trail name for testing."""
    return "action.test.sample"
