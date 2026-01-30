"""
Checkpointing for crash recovery in Framework Orchestrator.

Saves progress incrementally during orchestration:
- Pre-orchestration: task + context
- Per-agent: completion status + result
- Post-orchestration: final synthesis

Enables recovery from crashes by resuming incomplete orchestrations.

Usage:
    checkpoint = OrchestrationCheckpoint(checkpoint_dir)

    # Start orchestration
    checkpoint_id = await checkpoint.start_orchestration(iteration, task, context)

    # After each agent completes
    await checkpoint.checkpoint_agent_completion(checkpoint_id, "moe_router", result)

    # Complete orchestration
    await checkpoint.complete_orchestration(checkpoint_id, synthesis)

    # On startup, check for interrupted work
    interrupted = checkpoint.get_interrupted_orchestrations()
"""

import asyncio
import json
import time
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import Enum
import shutil

logger = logging.getLogger(__name__)


class CheckpointStatus(Enum):
    """Status of a checkpoint."""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERED = "recovered"


@dataclass
class CheckpointData:
    """Data stored in a checkpoint."""

    checkpoint_id: str
    iteration: int
    task: str
    context: Dict[str, Any]
    status: CheckpointStatus
    started_at: float
    updated_at: float
    completed_at: Optional[float] = None
    agents_completed: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    agents_pending: List[str] = field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "iteration": self.iteration,
            "task": self.task,
            "context": self.context,
            "status": self.status.value,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "agents_completed": self.agents_completed,
            "agents_pending": self.agents_pending,
            "synthesis": self.synthesis,
            "error": self.error,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'CheckpointData':
        """Create from dictionary."""
        return CheckpointData(
            checkpoint_id=data["checkpoint_id"],
            iteration=data["iteration"],
            task=data["task"],
            context=data.get("context", {}),
            status=CheckpointStatus(data["status"]),
            started_at=data["started_at"],
            updated_at=data["updated_at"],
            completed_at=data.get("completed_at"),
            agents_completed=data.get("agents_completed", {}),
            agents_pending=data.get("agents_pending", []),
            synthesis=data.get("synthesis"),
            error=data.get("error"),
        )


class OrchestrationCheckpoint:
    """
    Checkpointing system for crash recovery.

    Saves orchestration progress incrementally to disk:
    1. Pre-orchestration: Creates checkpoint file with task + context
    2. Per-agent: Updates checkpoint with completed agent results
    3. Post-orchestration: Marks checkpoint as complete with synthesis

    On startup, can detect and resume interrupted orchestrations.

    Uses atomic writes to prevent corruption.
    """

    def __init__(
        self,
        checkpoint_dir: Path,
        max_checkpoints: int = 100,
        retention_seconds: float = 86400.0  # 24 hours
    ):
        """
        Initialize checkpoint system.

        Args:
            checkpoint_dir: Directory to store checkpoint files
            max_checkpoints: Maximum number of checkpoints to retain
            retention_seconds: How long to keep completed checkpoints
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.max_checkpoints = max_checkpoints
        self.retention_seconds = retention_seconds

        # Create directory if needed
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Checkpoint system initialized: {self.checkpoint_dir}")

    def _generate_checkpoint_id(self, iteration: int, task: str) -> str:
        """Generate unique checkpoint ID."""
        data = f"{iteration}:{task}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get path to checkpoint file."""
        return self.checkpoint_dir / f"checkpoint_{checkpoint_id}.json"

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write data atomically (write to temp, then rename)."""
        temp_path = path.with_suffix('.tmp')
        try:
            temp_path.write_text(json.dumps(data, indent=2, default=str, sort_keys=True), encoding='utf-8')
            temp_path.replace(path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e

    def _read_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Read checkpoint from disk."""
        path = self._get_checkpoint_path(checkpoint_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return CheckpointData.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to read checkpoint {checkpoint_id}: {e}")
            return None

    async def start_orchestration(
        self,
        iteration: int,
        task: str,
        context: Dict[str, Any],
        agents_to_run: List[str] = None
    ) -> str:
        """
        Start a new orchestration checkpoint.

        Args:
            iteration: Orchestration iteration number
            task: The task being processed
            context: Execution context
            agents_to_run: List of agents that will be executed

        Returns:
            checkpoint_id: Unique ID for this checkpoint
        """
        checkpoint_id = self._generate_checkpoint_id(iteration, task)

        checkpoint = CheckpointData(
            checkpoint_id=checkpoint_id,
            iteration=iteration,
            task=task,
            context=context,
            status=CheckpointStatus.STARTED,
            started_at=time.time(),
            updated_at=time.time(),
            agents_pending=agents_to_run or [],
        )

        path = self._get_checkpoint_path(checkpoint_id)
        self._atomic_write(path, checkpoint.to_dict())

        logger.info(f"Checkpoint started: {checkpoint_id} (iteration {iteration})")

        # Cleanup old checkpoints
        await self._cleanup_old_checkpoints()

        return checkpoint_id

    async def checkpoint_agent_completion(
        self,
        checkpoint_id: str,
        agent_name: str,
        result: Dict[str, Any]
    ) -> None:
        """
        Record an agent completion in the checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint
            agent_name: Name of the completed agent
            result: Agent result (will be serialized)
        """
        checkpoint = self._read_checkpoint(checkpoint_id)
        if not checkpoint:
            logger.warning(f"Checkpoint not found: {checkpoint_id}")
            return

        # Update checkpoint
        checkpoint.status = CheckpointStatus.IN_PROGRESS
        checkpoint.updated_at = time.time()
        checkpoint.agents_completed[agent_name] = {
            "result": result,
            "completed_at": time.time(),
        }

        # Remove from pending if present
        if agent_name in checkpoint.agents_pending:
            checkpoint.agents_pending.remove(agent_name)

        # Write updated checkpoint
        path = self._get_checkpoint_path(checkpoint_id)
        self._atomic_write(path, checkpoint.to_dict())

        logger.debug(f"Checkpoint updated: {checkpoint_id} - agent {agent_name} completed")

    async def complete_orchestration(
        self,
        checkpoint_id: str,
        synthesis: Dict[str, Any]
    ) -> None:
        """
        Mark orchestration as complete.

        Args:
            checkpoint_id: ID of the checkpoint
            synthesis: Final orchestration result
        """
        checkpoint = self._read_checkpoint(checkpoint_id)
        if not checkpoint:
            logger.warning(f"Checkpoint not found: {checkpoint_id}")
            return

        checkpoint.status = CheckpointStatus.COMPLETED
        checkpoint.completed_at = time.time()
        checkpoint.updated_at = time.time()
        checkpoint.synthesis = synthesis
        checkpoint.agents_pending = []

        path = self._get_checkpoint_path(checkpoint_id)
        self._atomic_write(path, checkpoint.to_dict())

        logger.info(f"Checkpoint completed: {checkpoint_id}")

    async def fail_orchestration(
        self,
        checkpoint_id: str,
        error: str
    ) -> None:
        """
        Mark orchestration as failed.

        Args:
            checkpoint_id: ID of the checkpoint
            error: Error message
        """
        checkpoint = self._read_checkpoint(checkpoint_id)
        if not checkpoint:
            logger.warning(f"Checkpoint not found: {checkpoint_id}")
            return

        checkpoint.status = CheckpointStatus.FAILED
        checkpoint.updated_at = time.time()
        checkpoint.error = error

        path = self._get_checkpoint_path(checkpoint_id)
        self._atomic_write(path, checkpoint.to_dict())

        logger.error(f"Checkpoint failed: {checkpoint_id} - {error}")

    def get_interrupted_orchestrations(self) -> List[CheckpointData]:
        """
        Find orchestrations that were interrupted (not completed).

        Returns:
            List of checkpoint data for incomplete orchestrations
        """
        interrupted = []

        for path in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                checkpoint = CheckpointData.from_dict(data)

                # Not completed or failed = interrupted
                if checkpoint.status in (CheckpointStatus.STARTED, CheckpointStatus.IN_PROGRESS):
                    interrupted.append(checkpoint)

            except Exception as e:
                logger.warning(f"Failed to read checkpoint {path}: {e}")

        # Sort by most recent first
        interrupted.sort(key=lambda c: c.started_at, reverse=True)

        return interrupted

    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Get a specific checkpoint by ID."""
        return self._read_checkpoint(checkpoint_id)

    async def resume_orchestration(
        self,
        checkpoint_id: str,
        mark_as_recovered: bool = True
    ) -> Optional[CheckpointData]:
        """
        Prepare to resume an interrupted orchestration.

        Args:
            checkpoint_id: ID of the checkpoint to resume
            mark_as_recovered: Whether to update status to RECOVERED

        Returns:
            Checkpoint data with information needed to resume, or None if not found
        """
        checkpoint = self._read_checkpoint(checkpoint_id)
        if not checkpoint:
            logger.warning(f"Cannot resume - checkpoint not found: {checkpoint_id}")
            return None

        if checkpoint.status not in (CheckpointStatus.STARTED, CheckpointStatus.IN_PROGRESS):
            logger.warning(
                f"Cannot resume checkpoint {checkpoint_id} - status is {checkpoint.status.value}"
            )
            return None

        if mark_as_recovered:
            checkpoint.status = CheckpointStatus.RECOVERED
            checkpoint.updated_at = time.time()
            path = self._get_checkpoint_path(checkpoint_id)
            self._atomic_write(path, checkpoint.to_dict())

        logger.info(
            f"Resuming checkpoint {checkpoint_id}: "
            f"{len(checkpoint.agents_completed)} agents completed, "
            f"{len(checkpoint.agents_pending)} pending"
        )

        return checkpoint

    async def _cleanup_old_checkpoints(self) -> None:
        """Remove old completed checkpoints."""
        now = time.time()
        checkpoints = []

        for path in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                checkpoint = CheckpointData.from_dict(data)
                checkpoints.append((path, checkpoint))
            except Exception as e:
                # Log instead of silently ignoring [He2025 production safety]
                logger.warning(f"Failed to read checkpoint {path}: {e}")

        # Sort by time, newest first
        checkpoints.sort(key=lambda x: x[1].started_at, reverse=True)

        # Remove old completed/failed checkpoints
        for i, (path, checkpoint) in enumerate(checkpoints):
            should_remove = False

            # Over retention limit for completed/failed
            if checkpoint.status in (CheckpointStatus.COMPLETED, CheckpointStatus.FAILED):
                age = now - checkpoint.started_at
                if age > self.retention_seconds:
                    should_remove = True

            # Over max count
            if i >= self.max_checkpoints:
                should_remove = True

            if should_remove:
                try:
                    path.unlink()
                    logger.debug(f"Cleaned up old checkpoint: {checkpoint.checkpoint_id}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup checkpoint {path}: {e}")

    def list_checkpoints(
        self,
        status: CheckpointStatus = None,
        limit: int = 50
    ) -> List[CheckpointData]:
        """
        List checkpoints, optionally filtered by status.

        Args:
            status: Filter by status (None = all)
            limit: Maximum number to return

        Returns:
            List of checkpoint data
        """
        checkpoints = []

        for path in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                checkpoint = CheckpointData.from_dict(data)

                if status is None or checkpoint.status == status:
                    checkpoints.append(checkpoint)

            except Exception as e:
                logger.warning(f"Failed to read checkpoint {path}: {e}")

        # Sort by time, newest first
        checkpoints.sort(key=lambda c: c.started_at, reverse=True)

        return checkpoints[:limit]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.

        Args:
            checkpoint_id: ID of checkpoint to delete

        Returns:
            True if deleted, False if not found
        """
        path = self._get_checkpoint_path(checkpoint_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted checkpoint: {checkpoint_id}")
            return True
        return False

    def clear_all(self) -> int:
        """
        Delete all checkpoints (use with caution).

        Returns:
            Number of checkpoints deleted
        """
        count = 0
        for path in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                path.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {path}: {e}")

        logger.info(f"Cleared {count} checkpoints")
        return count


# Convenience function for startup recovery
async def recover_from_crash(
    checkpoint_dir: Path,
    auto_resume: bool = False
) -> List[CheckpointData]:
    """
    Check for and optionally resume interrupted orchestrations.

    Args:
        checkpoint_dir: Directory containing checkpoints
        auto_resume: If True, automatically mark checkpoints as recovered

    Returns:
        List of interrupted checkpoint data
    """
    checkpoint = OrchestrationCheckpoint(checkpoint_dir)
    interrupted = checkpoint.get_interrupted_orchestrations()

    if interrupted:
        logger.warning(f"Found {len(interrupted)} interrupted orchestration(s)")
        for cp in interrupted:
            logger.warning(
                f"  - {cp.checkpoint_id}: iteration={cp.iteration}, "
                f"status={cp.status.value}, agents_completed={len(cp.agents_completed)}"
            )

        if auto_resume:
            for cp in interrupted:
                await checkpoint.resume_orchestration(cp.checkpoint_id, mark_as_recovered=True)

    return interrupted
