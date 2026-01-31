"""
Merkle Audit Log
================

Tamper-evident security event logging with cryptographic integrity.

Provides verifiable audit trail using Merkle tree structure:
- Each event is hashed and linked to previous events
- Tree root provides integrity proof for entire log
- Inclusion proofs verify specific events exist
- Tampering detection via hash chain verification

[He2025] Compliance:
- FIXED hash algorithm (SHA-256)
- FIXED tree structure (binary Merkle tree)
- Deterministic proof generation

Usage:
    from otto.security.audit import AuditLog, AuditEvent, EventType

    log = AuditLog()
    log.append(AuditEvent(
        event_type=EventType.KEY_ROTATION,
        actor="system",
        description="Rotated encryption key",
    ))

    # Get proof for event
    proof = log.get_inclusion_proof(event_hash)

    # Verify integrity
    assert log.verify_integrity()
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED - [He2025] Compliant)
# =============================================================================

# Hash algorithm - FIXED, never changes
HASH_ALGORITHM = "sha256"

# Maximum events before rotation
MAX_EVENTS_PER_LOG = 10000

# Checkpoint interval (events)
CHECKPOINT_INTERVAL = 100


# =============================================================================
# Enums
# =============================================================================

class EventType(Enum):
    """Types of security events."""
    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_REVOKED = "auth_revoked"

    # Key management events
    KEY_GENERATED = "key_generated"
    KEY_ROTATION = "key_rotation"
    KEY_REVOKED = "key_revoked"
    KEY_EXPORT = "key_export"

    # Access events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    SCOPE_CHANGED = "scope_changed"

    # Security events
    ANOMALY_DETECTED = "anomaly_detected"
    THREAT_BLOCKED = "threat_blocked"
    POLICY_VIOLATION = "policy_violation"
    RATE_LIMITED = "rate_limited"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGED = "config_changed"
    UPGRADE_APPLIED = "upgrade_applied"

    # Audit events
    LOG_CREATED = "log_created"
    LOG_ROTATED = "log_rotated"
    INTEGRITY_CHECK = "integrity_check"


class Severity(Enum):
    """Event severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AuditEvent:
    """A single audit event."""
    event_type: EventType
    actor: str  # Who/what caused the event
    description: str
    severity: Severity = Severity.INFO
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Computed fields (set after hashing)
    event_hash: str = ""
    sequence: int = 0
    prev_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'event_type': self.event_type.value,
            'actor': self.actor,
            'description': self.description,
            'severity': self.severity.value,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
            'event_hash': self.event_hash,
            'sequence': self.sequence,
            'prev_hash': self.prev_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """Create from dictionary."""
        event = cls(
            event_type=EventType(data['event_type']),
            actor=data['actor'],
            description=data['description'],
            severity=Severity(data.get('severity', 'info')),
            timestamp=data['timestamp'],
            metadata=data.get('metadata', {}),
        )
        event.event_hash = data.get('event_hash', '')
        event.sequence = data.get('sequence', 0)
        event.prev_hash = data.get('prev_hash', '')
        return event

    def compute_hash(self) -> str:
        """Compute hash of event content (excluding hash fields)."""
        content = {
            'event_type': self.event_type.value,
            'actor': self.actor,
            'description': self.description,
            'severity': self.severity.value,
            'timestamp': self.timestamp,
            'metadata': self.metadata,
            'sequence': self.sequence,
            'prev_hash': self.prev_hash,
        }
        content_bytes = json.dumps(content, sort_keys=True).encode('utf-8')
        return hashlib.sha256(content_bytes).hexdigest()


@dataclass
class MerkleProof:
    """Inclusion proof for a Merkle tree."""
    leaf_hash: str
    proof_hashes: List[str]
    proof_directions: List[bool]  # True = right, False = left
    root_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'leaf_hash': self.leaf_hash,
            'proof_hashes': self.proof_hashes,
            'proof_directions': self.proof_directions,
            'root_hash': self.root_hash,
        }


@dataclass
class AuditCheckpoint:
    """Checkpoint of audit log state."""
    sequence: int
    merkle_root: str
    event_count: int
    timestamp: float
    last_event_hash: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'sequence': self.sequence,
            'merkle_root': self.merkle_root,
            'event_count': self.event_count,
            'timestamp': self.timestamp,
            'last_event_hash': self.last_event_hash,
        }


# =============================================================================
# Merkle Tree Implementation
# =============================================================================

class MerkleTree:
    """
    Binary Merkle tree for audit log integrity.

    Provides O(log n) inclusion proofs and O(n) tree construction.
    """

    def __init__(self):
        self._leaves: List[str] = []
        self._root: str = ""
        self._tree: List[List[str]] = []

    @property
    def root(self) -> str:
        """Get the Merkle root."""
        return self._root

    @property
    def leaf_count(self) -> int:
        """Number of leaves in tree."""
        return len(self._leaves)

    def add_leaf(self, data_hash: str) -> None:
        """Add a leaf to the tree."""
        self._leaves.append(data_hash)
        self._rebuild_tree()

    def _hash_pair(self, left: str, right: str) -> str:
        """Hash two nodes together."""
        combined = (left + right).encode('utf-8')
        return hashlib.sha256(combined).hexdigest()

    def _rebuild_tree(self) -> None:
        """Rebuild the Merkle tree from leaves."""
        if not self._leaves:
            self._root = ""
            self._tree = []
            return

        # Start with leaves
        current_level = self._leaves.copy()
        self._tree = [current_level]

        # Build up the tree
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                # If odd number, duplicate last node
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(self._hash_pair(left, right))
            current_level = next_level
            self._tree.append(current_level)

        self._root = current_level[0] if current_level else ""

    def get_proof(self, leaf_index: int) -> Optional[MerkleProof]:
        """
        Get inclusion proof for a leaf.

        Args:
            leaf_index: Index of the leaf in the tree

        Returns:
            MerkleProof or None if index invalid
        """
        if leaf_index < 0 or leaf_index >= len(self._leaves):
            return None

        if not self._tree:
            return None

        proof_hashes: List[str] = []
        proof_directions: List[bool] = []

        idx = leaf_index
        for level in self._tree[:-1]:  # All levels except root
            if idx % 2 == 0:
                # We're on the left, sibling is on the right
                sibling_idx = idx + 1
                if sibling_idx < len(level):
                    proof_hashes.append(level[sibling_idx])
                    proof_directions.append(True)  # Right
                else:
                    # No sibling (odd tree), use self
                    proof_hashes.append(level[idx])
                    proof_directions.append(True)
            else:
                # We're on the right, sibling is on the left
                sibling_idx = idx - 1
                proof_hashes.append(level[sibling_idx])
                proof_directions.append(False)  # Left

            idx //= 2

        return MerkleProof(
            leaf_hash=self._leaves[leaf_index],
            proof_hashes=proof_hashes,
            proof_directions=proof_directions,
            root_hash=self._root,
        )

    def verify_proof(self, proof: MerkleProof) -> bool:
        """
        Verify an inclusion proof.

        Args:
            proof: The MerkleProof to verify

        Returns:
            True if proof is valid
        """
        current = proof.leaf_hash

        for sibling, is_right in zip(proof.proof_hashes, proof.proof_directions):
            if is_right:
                current = self._hash_pair(current, sibling)
            else:
                current = self._hash_pair(sibling, current)

        return current == proof.root_hash

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tree state."""
        return {
            'leaves': self._leaves,
            'root': self._root,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MerkleTree':
        """Deserialize tree state."""
        tree = cls()
        tree._leaves = data.get('leaves', [])
        tree._rebuild_tree()
        return tree


# =============================================================================
# Audit Log
# =============================================================================

class AuditLog:
    """
    Tamper-evident audit log with Merkle tree integrity.

    Features:
    - Hash chain linking events
    - Merkle tree for efficient verification
    - Periodic checkpoints
    - Inclusion proofs for specific events
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize audit log.

        Args:
            storage_path: Optional path for persistence
        """
        self._events: List[AuditEvent] = []
        self._merkle_tree = MerkleTree()
        self._checkpoints: List[AuditCheckpoint] = []
        self._storage_path = storage_path
        self._hash_to_index: Dict[str, int] = {}

        # Record log creation
        self._append_internal(AuditEvent(
            event_type=EventType.LOG_CREATED,
            actor="system",
            description="Audit log initialized",
            severity=Severity.INFO,
        ))

    @property
    def event_count(self) -> int:
        """Number of events in log."""
        return len(self._events)

    @property
    def merkle_root(self) -> str:
        """Current Merkle root."""
        return self._merkle_tree.root

    @property
    def last_event(self) -> Optional[AuditEvent]:
        """Most recent event."""
        return self._events[-1] if self._events else None

    def _append_internal(self, event: AuditEvent) -> str:
        """Internal append without triggering checkpoint."""
        # Set sequence and prev_hash
        event.sequence = len(self._events)
        event.prev_hash = self._events[-1].event_hash if self._events else "0" * 64

        # Compute event hash
        event.event_hash = event.compute_hash()

        # Add to events and merkle tree
        self._events.append(event)
        self._merkle_tree.add_leaf(event.event_hash)
        self._hash_to_index[event.event_hash] = event.sequence

        return event.event_hash

    def append(self, event: AuditEvent) -> str:
        """
        Append an event to the log.

        Args:
            event: The event to append

        Returns:
            Event hash
        """
        event_hash = self._append_internal(event)

        # Create checkpoint if needed
        if len(self._events) % CHECKPOINT_INTERVAL == 0:
            self._create_checkpoint()

        # Persist if storage path set
        if self._storage_path:
            self._persist()

        logger.debug(f"Audit event appended: {event.event_type.value} ({event_hash[:16]}...)")
        return event_hash

    def _create_checkpoint(self) -> None:
        """Create a checkpoint of current state."""
        if not self._events:
            return

        checkpoint = AuditCheckpoint(
            sequence=len(self._events) - 1,
            merkle_root=self._merkle_tree.root,
            event_count=len(self._events),
            timestamp=time.time(),
            last_event_hash=self._events[-1].event_hash,
        )
        self._checkpoints.append(checkpoint)
        logger.debug(f"Audit checkpoint created at sequence {checkpoint.sequence}")

    def get_event(self, event_hash: str) -> Optional[AuditEvent]:
        """
        Get an event by hash.

        Args:
            event_hash: Hash of the event

        Returns:
            AuditEvent or None
        """
        index = self._hash_to_index.get(event_hash)
        if index is not None:
            return self._events[index]
        return None

    def get_events(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        event_types: Optional[List[EventType]] = None,
        actor: Optional[str] = None,
        severity: Optional[Severity] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """
        Query events with filters.

        Args:
            start_time: Filter events after this time
            end_time: Filter events before this time
            event_types: Filter by event types
            actor: Filter by actor
            severity: Filter by severity
            limit: Maximum events to return

        Returns:
            List of matching events
        """
        results = []

        for event in reversed(self._events):  # Most recent first
            if len(results) >= limit:
                break

            # Apply filters
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if event_types and event.event_type not in event_types:
                continue
            if actor and event.actor != actor:
                continue
            if severity and event.severity != severity:
                continue

            results.append(event)

        return results

    def get_inclusion_proof(self, event_hash: str) -> Optional[MerkleProof]:
        """
        Get inclusion proof for an event.

        Args:
            event_hash: Hash of the event

        Returns:
            MerkleProof or None if event not found
        """
        index = self._hash_to_index.get(event_hash)
        if index is None:
            return None

        return self._merkle_tree.get_proof(index)

    def verify_inclusion(self, proof: MerkleProof) -> bool:
        """
        Verify an inclusion proof.

        Args:
            proof: The proof to verify

        Returns:
            True if proof is valid
        """
        return self._merkle_tree.verify_proof(proof)

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Verify integrity of entire log.

        Returns:
            (is_valid, error_message)
        """
        if not self._events:
            return True, None

        # Verify hash chain
        prev_hash = "0" * 64
        for i, event in enumerate(self._events):
            if event.prev_hash != prev_hash:
                return False, f"Hash chain broken at event {i}"

            computed_hash = event.compute_hash()
            if computed_hash != event.event_hash:
                return False, f"Event hash mismatch at event {i}"

            prev_hash = event.event_hash

        # Verify Merkle tree
        if self._merkle_tree.leaf_count != len(self._events):
            return False, "Merkle tree leaf count mismatch"

        # Verify checkpoints
        for checkpoint in self._checkpoints:
            if checkpoint.sequence >= len(self._events):
                return False, f"Invalid checkpoint sequence {checkpoint.sequence}"

            event = self._events[checkpoint.sequence]
            if event.event_hash != checkpoint.last_event_hash:
                return False, f"Checkpoint hash mismatch at sequence {checkpoint.sequence}"

        return True, None

    def get_summary(self) -> Dict[str, Any]:
        """Get log summary for API response."""
        event_counts: Dict[str, int] = {}
        for event in self._events:
            key = event.event_type.value
            event_counts[key] = event_counts.get(key, 0) + 1

        return {
            'event_count': len(self._events),
            'merkle_root': self._merkle_tree.root,
            'checkpoint_count': len(self._checkpoints),
            'first_event': self._events[0].timestamp if self._events else None,
            'last_event': self._events[-1].timestamp if self._events else None,
            'event_counts': event_counts,
        }

    def _persist(self) -> None:
        """Persist log to storage."""
        if not self._storage_path:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'events': [e.to_dict() for e in self._events],
            'merkle_tree': self._merkle_tree.to_dict(),
            'checkpoints': [c.to_dict() for c in self._checkpoints],
        }

        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, storage_path: Path) -> 'AuditLog':
        """
        Load audit log from storage.

        Args:
            storage_path: Path to log file

        Returns:
            Loaded AuditLog
        """
        log = cls.__new__(cls)
        log._storage_path = storage_path
        log._events = []
        log._checkpoints = []
        log._hash_to_index = {}

        if storage_path.exists():
            with open(storage_path, 'r') as f:
                data = json.load(f)

            for event_data in data.get('events', []):
                event = AuditEvent.from_dict(event_data)
                log._events.append(event)
                log._hash_to_index[event.event_hash] = event.sequence

            log._merkle_tree = MerkleTree.from_dict(data.get('merkle_tree', {}))

            for cp_data in data.get('checkpoints', []):
                log._checkpoints.append(AuditCheckpoint(**cp_data))
        else:
            log._merkle_tree = MerkleTree()
            # Record log creation
            log._append_internal(AuditEvent(
                event_type=EventType.LOG_CREATED,
                actor="system",
                description="Audit log initialized",
                severity=Severity.INFO,
            ))

        return log


# =============================================================================
# Global Audit Log Instance
# =============================================================================

_audit_log: Optional[AuditLog] = None


def get_audit_log(storage_path: Optional[Path] = None) -> AuditLog:
    """Get the global audit log instance."""
    global _audit_log
    if _audit_log is None:
        _audit_log = AuditLog(storage_path)
    return _audit_log


def log_event(
    event_type: EventType,
    actor: str,
    description: str,
    severity: Severity = Severity.INFO,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Log a security event.

    Args:
        event_type: Type of event
        actor: Who/what caused the event
        description: Human-readable description
        severity: Event severity
        metadata: Additional context

    Returns:
        Event hash
    """
    event = AuditEvent(
        event_type=event_type,
        actor=actor,
        description=description,
        severity=severity,
        metadata=metadata or {},
    )
    return get_audit_log().append(event)


def verify_log_integrity() -> Tuple[bool, Optional[str]]:
    """Verify integrity of the audit log."""
    return get_audit_log().verify_integrity()


# =============================================================================
# API Response Helpers
# =============================================================================

def get_audit_summary() -> Dict[str, Any]:
    """Get audit log summary for API response."""
    return get_audit_log().get_summary()


def get_recent_events(
    limit: int = 50,
    event_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Get recent audit events for API response."""
    types = [EventType(t) for t in event_types] if event_types else None
    events = get_audit_log().get_events(event_types=types, limit=limit)
    return [e.to_dict() for e in events]
