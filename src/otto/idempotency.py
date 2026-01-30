"""
Idempotency management for Framework Orchestrator.

Prevents double-execution of operations by tracking execution results
by idempotency key. When the same operation is requested again,
returns the cached result instead of re-executing.

Critical for safe retries in distributed systems.

Usage:
    manager = IdempotencyManager()

    # Execute with idempotency
    result = await manager.execute_idempotent(
        idempotency_key="agent:task_hash:iteration",
        func=lambda: agent.execute(task, context)
    )

    # Same key returns cached result without re-execution
    result2 = await manager.execute_idempotent(
        idempotency_key="agent:task_hash:iteration",
        func=lambda: agent.execute(task, context)
    )
    assert result == result2  # Same result, func not called again
"""

import asyncio
import time
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Awaitable, Union
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of an idempotent execution."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionRecord:
    """Record of an execution for idempotency tracking."""

    key: str
    status: ExecutionStatus
    started_at: float
    completed_at: Optional[float] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    attempt_count: int = 1

    @property
    def age_seconds(self) -> float:
        """Get age of this record."""
        return time.time() - self.started_at

    def is_expired(self, ttl: float) -> bool:
        """Check if this record has expired."""
        return self.age_seconds > ttl


class IdempotencyConflict(Exception):
    """Raised when operation is already in progress."""

    def __init__(self, key: str, started_at: float):
        self.key = key
        self.started_at = started_at
        super().__init__(f"Operation '{key}' already in progress since {started_at}")


class IdempotencyManager:
    """
    Manager for idempotent operation execution.

    Tracks execution results by idempotency key to prevent double-execution:
    1. Before executing, check if key exists with completed result
    2. If found and valid, return cached result
    3. If not found, mark as in-progress and execute
    4. After execution, cache result with key

    Handles concurrent requests to same key by blocking duplicates.

    Thread-safe and async-safe.
    """

    def __init__(
        self,
        retention_seconds: float = 3600.0,
        max_entries: int = 10000,
        allow_retry_on_error: bool = True,
        in_progress_timeout: float = 300.0
    ):
        """
        Initialize idempotency manager.

        Args:
            retention_seconds: How long to keep completed records
            max_entries: Maximum number of records to keep
            allow_retry_on_error: Whether to allow retry after failure
            in_progress_timeout: Timeout for in-progress operations
        """
        self.retention_seconds = retention_seconds
        self.max_entries = max_entries
        self.allow_retry_on_error = allow_retry_on_error
        self.in_progress_timeout = in_progress_timeout

        # Storage
        self._executions: Dict[str, ExecutionRecord] = {}

        # Locks for preventing concurrent execution
        self._key_locks: Dict[str, asyncio.Lock] = {}

        # Statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._conflicts = 0

        # Thread safety
        self._lock = threading.Lock()

        logger.info(
            f"IdempotencyManager initialized: retention={retention_seconds}s, "
            f"max_entries={max_entries}"
        )

    def _get_or_create_lock(self, key: str) -> asyncio.Lock:
        """Get or create async lock for a key."""
        with self._lock:
            if key not in self._key_locks:
                self._key_locks[key] = asyncio.Lock()
            return self._key_locks[key]

    def _get_record(self, key: str) -> Optional[ExecutionRecord]:
        """Get execution record if exists and valid."""
        with self._lock:
            record = self._executions.get(key)
            if not record:
                return None

            # Check expiration
            if record.is_expired(self.retention_seconds):
                del self._executions[key]
                return None

            # Check in-progress timeout
            if record.status == ExecutionStatus.IN_PROGRESS:
                if record.age_seconds > self.in_progress_timeout:
                    # Treat as failed
                    record.status = ExecutionStatus.FAILED
                    record.error = "Timed out"

            return record

    def _set_record(self, record: ExecutionRecord) -> None:
        """Set execution record."""
        with self._lock:
            self._executions[record.key] = record
            self._cleanup_if_needed()

    def _cleanup_if_needed(self) -> None:
        """Remove old/excess entries."""
        if len(self._executions) <= self.max_entries:
            return

        # Sort by time, remove oldest
        now = time.time()
        entries = list(self._executions.items())
        entries.sort(key=lambda x: x[1].started_at)

        # Remove expired first
        for key, record in entries:
            if record.is_expired(self.retention_seconds):
                del self._executions[key]

        # Remove oldest if still over limit
        while len(self._executions) > self.max_entries:
            oldest_key = min(
                self._executions.keys(),
                key=lambda k: self._executions[k].started_at
            )
            del self._executions[oldest_key]

    async def execute_idempotent(
        self,
        idempotency_key: str,
        func: Union[Callable[[], Any], Callable[[], Awaitable[Any]]],
        force_execute: bool = False
    ) -> Any:
        """
        Execute a function idempotently.

        Args:
            idempotency_key: Unique key for this operation
            func: Function to execute (sync or async)
            force_execute: If True, execute even if cached result exists

        Returns:
            Result from function (possibly cached)

        Raises:
            IdempotencyConflict: If operation is already in progress
            Exception: If function raises and allow_retry_on_error is False
        """
        # Get lock for this key
        key_lock = self._get_or_create_lock(idempotency_key)

        async with key_lock:
            # Check for existing record
            record = self._get_record(idempotency_key)

            if record and not force_execute:
                if record.status == ExecutionStatus.COMPLETED:
                    # Return cached result
                    with self._lock:
                        self._cache_hits += 1
                    logger.debug(f"Idempotency cache hit: {idempotency_key}")
                    return record.result

                elif record.status == ExecutionStatus.IN_PROGRESS:
                    # Conflict - already running
                    with self._lock:
                        self._conflicts += 1
                    raise IdempotencyConflict(idempotency_key, record.started_at)

                elif record.status == ExecutionStatus.FAILED:
                    if not self.allow_retry_on_error:
                        # Return the error
                        raise Exception(f"Previous execution failed: {record.error}")
                    # Allow retry, continue to execute

            # Mark as in-progress
            with self._lock:
                self._cache_misses += 1

            record = ExecutionRecord(
                key=idempotency_key,
                status=ExecutionStatus.IN_PROGRESS,
                started_at=time.time(),
                attempt_count=record.attempt_count + 1 if record else 1
            )
            self._set_record(record)

            # Execute function
            try:
                result = func()
                if asyncio.iscoroutine(result):
                    result = await result

                # Mark as completed
                record.status = ExecutionStatus.COMPLETED
                record.completed_at = time.time()
                record.result = result
                self._set_record(record)

                logger.debug(f"Idempotent execution completed: {idempotency_key}")
                return result

            except Exception as e:
                # Mark as failed
                record.status = ExecutionStatus.FAILED
                record.completed_at = time.time()
                record.error = str(e)
                self._set_record(record)

                logger.warning(f"Idempotent execution failed: {idempotency_key} - {e}")
                raise

    def get_status(self, idempotency_key: str) -> Optional[ExecutionStatus]:
        """Get status of an operation by key."""
        record = self._get_record(idempotency_key)
        return record.status if record else None

    def get_result(self, idempotency_key: str) -> Optional[Any]:
        """Get result of a completed operation."""
        record = self._get_record(idempotency_key)
        if record and record.status == ExecutionStatus.COMPLETED:
            return record.result
        return None

    def invalidate(self, idempotency_key: str) -> bool:
        """
        Invalidate a cached result.

        Args:
            idempotency_key: Key to invalidate

        Returns:
            True if key was found and removed
        """
        with self._lock:
            if idempotency_key in self._executions:
                del self._executions[idempotency_key]
                logger.debug(f"Invalidated idempotency key: {idempotency_key}")
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get idempotency manager statistics."""
        with self._lock:
            total = self._cache_hits + self._cache_misses
            hit_rate = self._cache_hits / total if total > 0 else 0.0

            status_counts = {s.value: 0 for s in ExecutionStatus}
            for record in self._executions.values():
                status_counts[record.status.value] += 1

            return {
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_hit_rate": hit_rate,
                "conflicts": self._conflicts,
                "total_entries": len(self._executions),
                "status_counts": status_counts,
            }

    def clear(self) -> int:
        """
        Clear all records.

        Returns:
            Number of records cleared
        """
        with self._lock:
            count = len(self._executions)
            self._executions.clear()
            self._key_locks.clear()
            return count


def generate_idempotency_key(
    agent_name: str,
    task: str,
    iteration: int,
    extra: Dict[str, Any] = None
) -> str:
    """
    Generate a deterministic idempotency key.

    Args:
        agent_name: Name of the agent
        task: Task being executed
        iteration: Orchestration iteration
        extra: Additional context for key generation

    Returns:
        Deterministic key string
    """
    data = {
        "agent": agent_name,
        "task_hash": hashlib.sha256(task.encode()).hexdigest()[:16],
        "iteration": iteration,
    }
    if extra:
        data.update(extra)

    # Create deterministic hash
    key_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()[:32]
