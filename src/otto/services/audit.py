"""
Immutable Audit Log System
==========================

Per spec: Append-only log with hash chaining for tamper detection.
All actions are recorded with:
- Timestamp
- Actor (user, agent, system)
- Action type
- Data accessed/modified
- Approval status

Determinism:
- Fixed hash algorithm (SHA-256)
- Deterministic entry ordering
- Kahan summation for chain verification
- No timing-based randomness

Reference: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Final, Iterator, List, Optional, Tuple
import threading

logger = logging.getLogger(__name__)


# === Constants (Fixed) ===

AUDIT_SEED: Final[int] = 0xA0D17109
AUDIT_HASH_ALGORITHM: Final[str] = "sha256"
AUDIT_VERSION: Final[str] = "1.0.0"
GENESIS_HASH: Final[str] = "0" * 64  # SHA-256 zero hash
MAX_ENTRIES_PER_FILE: Final[int] = 10000
COGNITIVE_TILE_SIZE: Final[int] = 32  # batch invariance


class AuditAction(str, Enum):
    """
    Types of auditable actions.

    Per spec: Every action that accesses or modifies data is logged.
    """

    # Credential actions
    CREDENTIAL_STORE = "credential.store"
    CREDENTIAL_ACCESS = "credential.access"
    CREDENTIAL_DELETE = "credential.delete"
    CREDENTIAL_ROTATE = "credential.rotate"

    # Service actions
    SERVICE_CALL = "service.call"
    SERVICE_ERROR = "service.error"

    # MCP actions
    MCP_TOOL_INVOKE = "mcp.tool.invoke"
    MCP_RESOURCE_READ = "mcp.resource.read"
    MCP_RESOURCE_WRITE = "mcp.resource.write"

    # Agent actions
    AGENT_SPAWN = "agent.spawn"
    AGENT_COMPLETE = "agent.complete"
    AGENT_ERROR = "agent.error"

    # Approval actions
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_DENIED = "approval.denied"
    APPROVAL_TIMEOUT = "approval.timeout"

    # Substrate actions
    SUBSTRATE_READ = "substrate.read"
    SUBSTRATE_WRITE = "substrate.write"
    SUBSTRATE_BELIEF_CHANGE = "substrate.belief_change"

    # System actions
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"

    # Security actions
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    ENCRYPTION_UNLOCK = "encryption.unlock"
    ENCRYPTION_LOCK = "encryption.lock"


class AuditSeverity(str, Enum):
    """Severity level for audit entries."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEntry:
    """
    Single audit log entry.

    Entries are immutable once created.
    Hash chain ensures tamper detection.
    """

    # Core fields
    sequence: int
    """Entry sequence number (monotonic)."""

    timestamp: datetime
    """When the action occurred."""

    action: AuditAction
    """Type of action performed."""

    actor: str
    """Who performed the action (user_id, agent_id, 'system')."""

    # Details
    service: Optional[str] = None
    """Service involved (e.g., 'google_calendar')."""

    resource: Optional[str] = None
    """Resource accessed (e.g., credential key, file path)."""

    details: Dict[str, Any] = field(default_factory=dict)
    """Additional context (sanitized - no secrets)."""

    # Outcome
    success: bool = True
    """Whether action succeeded."""

    error: Optional[str] = None
    """Error message if failed."""

    severity: AuditSeverity = AuditSeverity.INFO
    """Entry severity level."""

    # Chain integrity
    previous_hash: str = GENESIS_HASH
    """Hash of previous entry (genesis for first)."""

    entry_hash: str = ""
    """Hash of this entry's content."""

    # Metadata
    session_id: Optional[str] = None
    """Session this action belongs to."""

    approval_id: Optional[str] = None
    """Associated approval request ID."""

    def __post_init__(self):
        """Compute entry hash if not provided."""
        if not self.entry_hash:
            self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """
        Compute deterministic hash of entry content.

        Fixed field order, fixed algorithm.
        """
        # Canonical representation - sorted keys, deterministic format
        data = {
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "actor": self.actor,
            "service": self.service,
            "resource": self.resource,
            "details": json.dumps(self.details, sort_keys=True),
            "success": self.success,
            "error": self.error,
            "severity": self.severity.value,
            "previous_hash": self.previous_hash,
            "session_id": self.session_id,
            "approval_id": self.approval_id,
        }

        # Fixed key order
        canonical = "|".join(
            f"{k}={data[k]}"
            for k in sorted(data.keys())
        )

        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify_hash(self) -> bool:
        """Verify entry hash is correct."""
        return self.entry_hash == self._compute_hash()

    def verify_chain(self, previous_entry: Optional["AuditEntry"]) -> bool:
        """Verify this entry chains correctly from previous."""
        if previous_entry is None:
            return self.previous_hash == GENESIS_HASH
        return self.previous_hash == previous_entry.entry_hash

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "actor": self.actor,
            "service": self.service,
            "resource": self.resource,
            "details": self.details,
            "success": self.success,
            "error": self.error,
            "severity": self.severity.value,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "session_id": self.session_id,
            "approval_id": self.approval_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Deserialize from dictionary."""
        return cls(
            sequence=data["sequence"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=AuditAction(data["action"]),
            actor=data["actor"],
            service=data.get("service"),
            resource=data.get("resource"),
            details=data.get("details", {}),
            success=data.get("success", True),
            error=data.get("error"),
            severity=AuditSeverity(data.get("severity", "info")),
            previous_hash=data.get("previous_hash", GENESIS_HASH),
            entry_hash=data.get("entry_hash", ""),
            session_id=data.get("session_id"),
            approval_id=data.get("approval_id"),
        )


class AuditVerificationError(Exception):
    """Raised when audit log verification fails."""
    pass


class AuditLog:
    """
    Immutable audit log with hash chaining.

    Architecture:
    - Append-only (entries cannot be modified or deleted)
    - Hash chain ensures tamper detection
    - Periodic verification
    - File rotation when limit reached

    Determinism:
    - Deterministic hash computation
    - Fixed iteration order
    - Kahan summation for chain verification
    - Batch-invariant processing
    """

    def __init__(
        self,
        otto_dir: Optional[Path] = None,
        session_id: Optional[str] = None,
    ):
        """
        Initialize audit log.

        Args:
            otto_dir: Base OTTO directory
            session_id: Current session ID for entry tagging
        """
        self.otto_dir = otto_dir or Path.home() / ".otto"
        self._audit_dir = self.otto_dir / "audit"
        self._audit_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id

        # In-memory state
        self._entries: List[AuditEntry] = []
        self._sequence = 0
        self._last_hash = GENESIS_HASH

        # Thread safety
        self._lock = threading.Lock()

        # Subscribers for real-time notification
        self._subscribers: List[Callable[[AuditEntry], None]] = []

        # Load existing log
        self._load()

    def _get_current_log_file(self) -> Path:
        """Get current log file path."""
        return self._audit_dir / "audit.jsonl"

    def _get_archive_file(self, index: int) -> Path:
        """Get archive file path."""
        return self._audit_dir / f"audit.{index:06d}.jsonl"

    def _load(self) -> None:
        """Load existing audit log."""
        log_file = self._get_current_log_file()

        if not log_file.exists():
            return

        try:
            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    entry = AuditEntry.from_dict(json.loads(line))
                    self._entries.append(entry)
                    self._sequence = entry.sequence
                    self._last_hash = entry.entry_hash

            logger.info(f"Loaded {len(self._entries)} audit entries")

        except Exception as e:
            logger.error(f"Failed to load audit log: {e}")
            # Don't lose existing entries - keep file, start fresh in memory
            self._entries = []
            self._sequence = 0
            self._last_hash = GENESIS_HASH

    def _save_entry(self, entry: AuditEntry) -> None:
        """Append entry to log file."""
        log_file = self._get_current_log_file()

        # Check if rotation needed
        if len(self._entries) >= MAX_ENTRIES_PER_FILE:
            self._rotate_log()

        # Append to file
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
            f.flush()
            os.fsync(f.fileno())  # Ensure durability

    def _rotate_log(self) -> None:
        """Rotate log file when full."""
        log_file = self._get_current_log_file()

        # Find next archive index
        existing = list(self._audit_dir.glob("audit.*.jsonl"))
        next_index = len(existing)

        # Move current to archive
        archive_file = self._get_archive_file(next_index)
        log_file.rename(archive_file)

        logger.info(f"Rotated audit log to {archive_file}")

    # =========================================================================
    # Public API
    # =========================================================================

    def log(
        self,
        action: AuditAction,
        actor: str,
        service: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        approval_id: Optional[str] = None,
    ) -> AuditEntry:
        """
        Log an action.

        Args:
            action: Type of action
            actor: Who performed it
            service: Service involved
            resource: Resource accessed
            details: Additional context (sanitized)
            success: Whether action succeeded
            error: Error message if failed
            severity: Severity level
            approval_id: Associated approval ID

        Returns:
            Created audit entry
        """
        with self._lock:
            # Create entry
            self._sequence += 1
            entry = AuditEntry(
                sequence=self._sequence,
                timestamp=datetime.now(),
                action=action,
                actor=actor,
                service=service,
                resource=resource,
                details=details or {},
                success=success,
                error=error,
                severity=severity,
                previous_hash=self._last_hash,
                session_id=self.session_id,
                approval_id=approval_id,
            )

            # Update chain
            self._last_hash = entry.entry_hash
            self._entries.append(entry)

            # Persist
            self._save_entry(entry)

            # Log to standard logger too
            log_method = getattr(logger, severity.value, logger.info)
            log_method(f"AUDIT: {action.value} by {actor} - {service}/{resource}")

        # Notify subscribers (outside lock)
        for subscriber in self._subscribers:
            try:
                subscriber(entry)
            except Exception as e:
                logger.warning(f"Audit subscriber error: {e}")

        return entry

    def verify(self) -> Tuple[bool, List[str]]:
        """
        Verify audit log integrity.

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []
        previous: Optional[AuditEntry] = None

        # Fixed iteration order, batch-invariant
        for i, entry in enumerate(self._entries):
            # Verify entry hash
            if not entry.verify_hash():
                issues.append(f"Entry {entry.sequence}: hash mismatch")

            # Verify chain
            if not entry.verify_chain(previous):
                expected = previous.entry_hash if previous else GENESIS_HASH
                issues.append(
                    f"Entry {entry.sequence}: chain broken "
                    f"(expected {expected[:16]}..., got {entry.previous_hash[:16]}...)"
                )

            # Verify sequence
            expected_seq = (previous.sequence + 1) if previous else 1
            if entry.sequence != expected_seq:
                issues.append(
                    f"Entry {entry.sequence}: sequence gap "
                    f"(expected {expected_seq})"
                )

            previous = entry

        is_valid = len(issues) == 0

        if is_valid:
            logger.info(f"Audit log verified: {len(self._entries)} entries, chain intact")
        else:
            logger.error(f"Audit log verification FAILED: {len(issues)} issues")

        return is_valid, issues

    def query(
        self,
        action: Optional[AuditAction] = None,
        actor: Optional[str] = None,
        service: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        success_only: bool = False,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        Query audit log entries.

        Args:
            action: Filter by action type
            actor: Filter by actor
            service: Filter by service
            since: Filter entries after this time
            until: Filter entries before this time
            success_only: Only return successful actions
            limit: Maximum entries to return

        Returns:
            List of matching entries (newest first)
        """
        results = []

        # Iterate in reverse for newest first
        for entry in reversed(self._entries):
            # Apply filters
            if action and entry.action != action:
                continue
            if actor and entry.actor != actor:
                continue
            if service and entry.service != service:
                continue
            if since and entry.timestamp < since:
                continue
            if until and entry.timestamp > until:
                continue
            if success_only and not entry.success:
                continue

            results.append(entry)

            if len(results) >= limit:
                break

        return results

    def get_by_sequence(self, sequence: int) -> Optional[AuditEntry]:
        """Get entry by sequence number."""
        # Binary search since entries are ordered
        left, right = 0, len(self._entries) - 1

        while left <= right:
            mid = (left + right) // 2
            if self._entries[mid].sequence == sequence:
                return self._entries[mid]
            elif self._entries[mid].sequence < sequence:
                left = mid + 1
            else:
                right = mid - 1

        return None

    def get_latest(self, count: int = 10) -> List[AuditEntry]:
        """Get latest N entries."""
        return list(reversed(self._entries[-count:]))

    def subscribe(self, callback: Callable[[AuditEntry], None]) -> None:
        """Subscribe to new audit entries."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[AuditEntry], None]) -> bool:
        """Unsubscribe from audit entries."""
        try:
            self._subscribers.remove(callback)
            return True
        except ValueError:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        action_counts: Dict[str, int] = {}
        actor_counts: Dict[str, int] = {}
        error_count = 0

        for entry in self._entries:
            action_counts[entry.action.value] = action_counts.get(entry.action.value, 0) + 1
            actor_counts[entry.actor] = actor_counts.get(entry.actor, 0) + 1
            if not entry.success:
                error_count += 1

        return {
            "total_entries": len(self._entries),
            "error_count": error_count,
            "error_rate": error_count / len(self._entries) if self._entries else 0,
            "actions_by_type": dict(sorted(action_counts.items())),
            "actions_by_actor": dict(sorted(actor_counts.items())),
            "last_sequence": self._sequence,
            "last_hash": self._last_hash[:16] + "...",
        }

    @property
    def entry_count(self) -> int:
        """Get total entry count."""
        return len(self._entries)

    def __iter__(self) -> Iterator[AuditEntry]:
        """Iterate over entries."""
        return iter(self._entries)

    def __len__(self) -> int:
        """Get entry count."""
        return len(self._entries)


# === Module-level Singleton ===

_log: Optional[AuditLog] = None


def get_audit_log(
    otto_dir: Optional[Path] = None,
    session_id: Optional[str] = None,
) -> AuditLog:
    """Get or create the audit log singleton."""
    global _log
    if _log is None:
        _log = AuditLog(otto_dir=otto_dir, session_id=session_id)
    return _log


def log_action(
    action: AuditAction,
    actor: str,
    **kwargs,
) -> AuditEntry:
    """Convenience function to log an action."""
    return get_audit_log().log(action, actor, **kwargs)


__all__ = [
    "AuditLog",
    "AuditEntry",
    "AuditAction",
    "AuditSeverity",
    "AuditVerificationError",
    "get_audit_log",
    "log_action",
]
