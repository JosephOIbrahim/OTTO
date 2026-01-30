"""
Tests for checkpoint/recovery module.

Tests:
- CheckpointStatus enum values
- CheckpointData serialization/deserialization
- OrchestrationCheckpoint file operations
- Atomic write safety
- Orchestration lifecycle (start, update, complete, fail)
- Recovery from interrupted orchestrations
- Cleanup of old checkpoints
"""

import asyncio
import json
import time
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from otto.checkpoint import (
    CheckpointStatus,
    CheckpointData,
    OrchestrationCheckpoint,
    recover_from_crash,
)


class TestCheckpointStatus:
    """Test CheckpointStatus enum."""

    def test_status_values(self):
        """Should have correct status values."""
        assert CheckpointStatus.STARTED.value == "started"
        assert CheckpointStatus.IN_PROGRESS.value == "in_progress"
        assert CheckpointStatus.COMPLETED.value == "completed"
        assert CheckpointStatus.FAILED.value == "failed"
        assert CheckpointStatus.RECOVERED.value == "recovered"


class TestCheckpointData:
    """Test CheckpointData dataclass."""

    def test_creation(self):
        """Should create checkpoint data with required fields."""
        data = CheckpointData(
            checkpoint_id="test123",
            iteration=1,
            task="test task",
            context={"key": "value"},
            status=CheckpointStatus.STARTED,
            started_at=1000.0,
            updated_at=1000.0,
        )

        assert data.checkpoint_id == "test123"
        assert data.iteration == 1
        assert data.task == "test task"
        assert data.status == CheckpointStatus.STARTED

    def test_default_values(self):
        """Should have correct default values."""
        data = CheckpointData(
            checkpoint_id="test",
            iteration=1,
            task="task",
            context={},
            status=CheckpointStatus.STARTED,
            started_at=1000.0,
            updated_at=1000.0,
        )

        assert data.completed_at is None
        assert data.agents_completed == {}
        assert data.agents_pending == []
        assert data.synthesis is None
        assert data.error is None

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        data = CheckpointData(
            checkpoint_id="test123",
            iteration=1,
            task="test task",
            context={"key": "value"},
            status=CheckpointStatus.IN_PROGRESS,
            started_at=1000.0,
            updated_at=1001.0,
            agents_completed={"agent1": {"result": "ok"}},
            agents_pending=["agent2"],
        )

        d = data.to_dict()

        assert d["checkpoint_id"] == "test123"
        assert d["status"] == "in_progress"
        assert d["agents_completed"]["agent1"]["result"] == "ok"
        assert "agent2" in d["agents_pending"]

    def test_from_dict(self):
        """Should create from dictionary correctly."""
        d = {
            "checkpoint_id": "test456",
            "iteration": 2,
            "task": "another task",
            "context": {"ctx": "data"},
            "status": "completed",
            "started_at": 2000.0,
            "updated_at": 2100.0,
            "completed_at": 2100.0,
            "agents_completed": {"a1": {"r": 1}},
            "agents_pending": [],
            "synthesis": {"final": "result"},
            "error": None,
        }

        data = CheckpointData.from_dict(d)

        assert data.checkpoint_id == "test456"
        assert data.iteration == 2
        assert data.status == CheckpointStatus.COMPLETED
        assert data.synthesis == {"final": "result"}

    def test_roundtrip_serialization(self):
        """Should survive to_dict -> from_dict roundtrip."""
        original = CheckpointData(
            checkpoint_id="roundtrip",
            iteration=5,
            task="complex task",
            context={"nested": {"deep": True}},
            status=CheckpointStatus.IN_PROGRESS,
            started_at=time.time(),
            updated_at=time.time(),
            agents_completed={"agent1": {"data": [1, 2, 3]}},
            agents_pending=["agent2", "agent3"],
        )

        restored = CheckpointData.from_dict(original.to_dict())

        assert restored.checkpoint_id == original.checkpoint_id
        assert restored.iteration == original.iteration
        assert restored.status == original.status
        assert restored.agents_pending == original.agents_pending


class TestOrchestrationCheckpointBasic:
    """Test basic OrchestrationCheckpoint functionality."""

    def test_initialization(self):
        """Should initialize and create directory."""
        with TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir) / "checkpoints"
            checkpoint = OrchestrationCheckpoint(checkpoint_dir)

            assert checkpoint.checkpoint_dir.exists()
            assert checkpoint.max_checkpoints == 100
            assert checkpoint.retention_seconds == 86400.0

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(
                Path(tmpdir),
                max_checkpoints=50,
                retention_seconds=3600.0
            )

            assert checkpoint.max_checkpoints == 50
            assert checkpoint.retention_seconds == 3600.0


class TestOrchestrationCheckpointLifecycle:
    """Test checkpoint lifecycle operations."""

    @pytest.mark.asyncio
    async def test_start_orchestration(self):
        """Should create checkpoint on start."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            checkpoint_id = await checkpoint.start_orchestration(
                iteration=1,
                task="test task",
                context={"key": "value"},
                agents_to_run=["agent1", "agent2"]
            )

            assert checkpoint_id is not None
            assert len(checkpoint_id) == 16  # SHA256 truncated

            # Verify file exists
            path = checkpoint._get_checkpoint_path(checkpoint_id)
            assert path.exists()

            # Verify content
            data = checkpoint.get_checkpoint(checkpoint_id)
            assert data.status == CheckpointStatus.STARTED
            assert data.iteration == 1
            assert "agent1" in data.agents_pending

    @pytest.mark.asyncio
    async def test_checkpoint_agent_completion(self):
        """Should update checkpoint with agent completion."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            checkpoint_id = await checkpoint.start_orchestration(
                iteration=1,
                task="test",
                context={},
                agents_to_run=["agent1", "agent2"]
            )

            await checkpoint.checkpoint_agent_completion(
                checkpoint_id,
                "agent1",
                {"output": "result1"}
            )

            data = checkpoint.get_checkpoint(checkpoint_id)
            assert data.status == CheckpointStatus.IN_PROGRESS
            assert "agent1" in data.agents_completed
            assert data.agents_completed["agent1"]["result"]["output"] == "result1"
            assert "agent1" not in data.agents_pending

    @pytest.mark.asyncio
    async def test_complete_orchestration(self):
        """Should mark orchestration as complete."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            checkpoint_id = await checkpoint.start_orchestration(
                iteration=1,
                task="test",
                context={},
            )

            await checkpoint.complete_orchestration(
                checkpoint_id,
                {"final": "synthesis"}
            )

            data = checkpoint.get_checkpoint(checkpoint_id)
            assert data.status == CheckpointStatus.COMPLETED
            assert data.completed_at is not None
            assert data.synthesis == {"final": "synthesis"}

    @pytest.mark.asyncio
    async def test_fail_orchestration(self):
        """Should mark orchestration as failed."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            checkpoint_id = await checkpoint.start_orchestration(
                iteration=1,
                task="test",
                context={},
            )

            await checkpoint.fail_orchestration(
                checkpoint_id,
                "Something went wrong"
            )

            data = checkpoint.get_checkpoint(checkpoint_id)
            assert data.status == CheckpointStatus.FAILED
            assert data.error == "Something went wrong"


class TestOrchestrationCheckpointRecovery:
    """Test checkpoint recovery functionality."""

    @pytest.mark.asyncio
    async def test_get_interrupted_orchestrations(self):
        """Should find incomplete orchestrations."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            # Create started checkpoint
            id1 = await checkpoint.start_orchestration(1, "task1", {})

            # Create in-progress checkpoint
            id2 = await checkpoint.start_orchestration(2, "task2", {})
            await checkpoint.checkpoint_agent_completion(id2, "agent1", {})

            # Create completed checkpoint
            id3 = await checkpoint.start_orchestration(3, "task3", {})
            await checkpoint.complete_orchestration(id3, {})

            interrupted = checkpoint.get_interrupted_orchestrations()

            assert len(interrupted) == 2
            ids = [c.checkpoint_id for c in interrupted]
            assert id1 in ids
            assert id2 in ids
            assert id3 not in ids

    @pytest.mark.asyncio
    async def test_resume_orchestration(self):
        """Should resume interrupted orchestration."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            checkpoint_id = await checkpoint.start_orchestration(
                iteration=1,
                task="test",
                context={"original": "context"},
                agents_to_run=["agent1", "agent2"]
            )
            await checkpoint.checkpoint_agent_completion(
                checkpoint_id, "agent1", {"partial": "result"}
            )

            # Resume
            resumed = await checkpoint.resume_orchestration(checkpoint_id)

            assert resumed is not None
            assert resumed.status == CheckpointStatus.RECOVERED
            assert len(resumed.agents_completed) == 1
            assert "agent1" in resumed.agents_completed
            assert "agent2" in resumed.agents_pending

    @pytest.mark.asyncio
    async def test_resume_completed_fails(self):
        """Should not resume completed orchestration."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            checkpoint_id = await checkpoint.start_orchestration(1, "test", {})
            await checkpoint.complete_orchestration(checkpoint_id, {})

            resumed = await checkpoint.resume_orchestration(checkpoint_id)

            assert resumed is None

    @pytest.mark.asyncio
    async def test_resume_nonexistent_fails(self):
        """Should return None for nonexistent checkpoint."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            resumed = await checkpoint.resume_orchestration("nonexistent")

            assert resumed is None


class TestOrchestrationCheckpointCleanup:
    """Test checkpoint cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints_by_retention(self):
        """Should clean up old completed checkpoints."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(
                Path(tmpdir),
                retention_seconds=0.1  # Very short for testing
            )

            # Create and complete a checkpoint
            checkpoint_id = await checkpoint.start_orchestration(1, "test", {})
            await checkpoint.complete_orchestration(checkpoint_id, {})

            # Wait past retention
            await asyncio.sleep(0.2)

            # Trigger cleanup
            await checkpoint._cleanup_old_checkpoints()

            # Should be cleaned up
            path = checkpoint._get_checkpoint_path(checkpoint_id)
            assert not path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_preserves_incomplete(self):
        """Should not clean up incomplete checkpoints."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(
                Path(tmpdir),
                retention_seconds=0.1
            )

            # Create incomplete checkpoint
            checkpoint_id = await checkpoint.start_orchestration(1, "test", {})

            await asyncio.sleep(0.2)
            await checkpoint._cleanup_old_checkpoints()

            # Should still exist
            path = checkpoint._get_checkpoint_path(checkpoint_id)
            assert path.exists()

    @pytest.mark.asyncio
    async def test_cleanup_respects_max_count(self):
        """Should clean up when exceeding max checkpoints."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(
                Path(tmpdir),
                max_checkpoints=3
            )

            # Create 5 completed checkpoints
            for i in range(5):
                cid = await checkpoint.start_orchestration(i, f"task{i}", {})
                await checkpoint.complete_orchestration(cid, {})

            # Should have at most 3
            all_checkpoints = checkpoint.list_checkpoints()
            assert len(all_checkpoints) <= 3


class TestOrchestrationCheckpointListing:
    """Test checkpoint listing functionality."""

    @pytest.mark.asyncio
    async def test_list_all_checkpoints(self):
        """Should list all checkpoints."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            await checkpoint.start_orchestration(1, "task1", {})
            await checkpoint.start_orchestration(2, "task2", {})
            await checkpoint.start_orchestration(3, "task3", {})

            all_checkpoints = checkpoint.list_checkpoints()

            assert len(all_checkpoints) == 3

    @pytest.mark.asyncio
    async def test_list_filtered_by_status(self):
        """Should filter by status."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            id1 = await checkpoint.start_orchestration(1, "task1", {})
            id2 = await checkpoint.start_orchestration(2, "task2", {})
            await checkpoint.complete_orchestration(id2, {})

            started = checkpoint.list_checkpoints(status=CheckpointStatus.STARTED)
            completed = checkpoint.list_checkpoints(status=CheckpointStatus.COMPLETED)

            assert len(started) == 1
            assert len(completed) == 1
            assert started[0].checkpoint_id == id1

    @pytest.mark.asyncio
    async def test_list_respects_limit(self):
        """Should respect limit parameter."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            for i in range(10):
                await checkpoint.start_orchestration(i, f"task{i}", {})

            limited = checkpoint.list_checkpoints(limit=5)

            assert len(limited) == 5


class TestOrchestrationCheckpointDeletion:
    """Test checkpoint deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_checkpoint(self):
        """Should delete specific checkpoint."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            checkpoint_id = await checkpoint.start_orchestration(1, "test", {})

            result = checkpoint.delete_checkpoint(checkpoint_id)

            assert result is True
            assert checkpoint.get_checkpoint(checkpoint_id) is None

    def test_delete_nonexistent(self):
        """Should return False for nonexistent checkpoint."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            result = checkpoint.delete_checkpoint("nonexistent")

            assert result is False

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Should delete all checkpoints."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            await checkpoint.start_orchestration(1, "task1", {})
            await checkpoint.start_orchestration(2, "task2", {})
            await checkpoint.start_orchestration(3, "task3", {})

            count = checkpoint.clear_all()

            assert count == 3
            assert len(checkpoint.list_checkpoints()) == 0


class TestOrchestrationCheckpointAtomicWrite:
    """Test atomic write safety."""

    @pytest.mark.asyncio
    async def test_atomic_write_temp_file_cleanup(self):
        """Should clean up temp file on success."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))

            checkpoint_id = await checkpoint.start_orchestration(1, "test", {})

            # No .tmp files should remain
            tmp_files = list(checkpoint.checkpoint_dir.glob("*.tmp"))
            assert len(tmp_files) == 0


class TestRecoverFromCrash:
    """Test recover_from_crash helper function."""

    @pytest.mark.asyncio
    async def test_recover_finds_interrupted(self):
        """Should find interrupted orchestrations."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))
            await checkpoint.start_orchestration(1, "incomplete", {})

            interrupted = await recover_from_crash(Path(tmpdir))

            assert len(interrupted) == 1

    @pytest.mark.asyncio
    async def test_recover_auto_marks_recovered(self):
        """Should mark as recovered when auto_resume=True."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))
            checkpoint_id = await checkpoint.start_orchestration(1, "test", {})

            await recover_from_crash(Path(tmpdir), auto_resume=True)

            data = checkpoint.get_checkpoint(checkpoint_id)
            assert data.status == CheckpointStatus.RECOVERED

    @pytest.mark.asyncio
    async def test_recover_returns_empty_when_none(self):
        """Should return empty list when no interrupted."""
        with TemporaryDirectory() as tmpdir:
            checkpoint = OrchestrationCheckpoint(Path(tmpdir))
            cid = await checkpoint.start_orchestration(1, "test", {})
            await checkpoint.complete_orchestration(cid, {})

            interrupted = await recover_from_crash(Path(tmpdir))

            assert len(interrupted) == 0

