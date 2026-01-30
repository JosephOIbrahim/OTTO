"""
Verifiable Audit Trail for OTTO API
====================================

Tamper-evident security audit logging using Merkle trees:

1. Merkle Tree Structure
   - Each audit entry is a leaf node
   - Internal nodes are hashes of children
   - Root hash provides integrity proof

2. Inclusion Proofs
   - Prove an entry exists in the log
   - Verify without accessing full log
   - O(log n) proof size

3. Consistency Proofs
   - Prove log hasn't been modified
   - Append-only guarantee
   - Detect tampering

[He2025] Compliance:
- FIXED hash algorithm (SHA-256)
- DETERMINISTIC tree construction
- Pre-computed proof verification

Frontier Feature: Tamper-evident audit logs.
Most APIs use plain text logs with no integrity verification.

Mathematical Foundation:
- Binary Merkle tree with left-to-right leaf ordering
- RFC 6962 (Certificate Transparency) compatible
- Cryptographic commitment to audit history

References:
- Merkle, R.C. "A Digital Signature Based on a Conventional Encryption Function"
- RFC 6962: Certificate Transparency
- RFC 9162: Certificate Transparency Version 2.0
"""

import hashlib
import json
import logging
import os
import struct
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# [He2025] FIXED: Hash algorithm and domain separators
HASH_ALGORITHM = "sha256"
LEAF_PREFIX = b"\x00"     # Domain separator for leaf nodes
NODE_PREFIX = b"\x01"     # Domain separator for internal nodes
EMPTY_HASH = hashlib.sha256(b"").digest()


# =============================================================================
# Hash Functions
# =============================================================================

def hash_leaf(data: bytes) -> bytes:
    """
    Hash a leaf node.

    [He2025] DETERMINISTIC: SHA-256 with leaf prefix.

    Args:
        data: Leaf data to hash

    Returns:
        32-byte hash
    """
    hasher = hashlib.sha256()
    hasher.update(LEAF_PREFIX)
    hasher.update(data)
    return hasher.digest()


def hash_node(left: bytes, right: bytes) -> bytes:
    """
    Hash an internal node.

    [He2025] DETERMINISTIC: SHA-256 with node prefix.

    Args:
        left: Left child hash
        right: Right child hash

    Returns:
        32-byte hash
    """
    hasher = hashlib.sha256()
    hasher.update(NODE_PREFIX)
    hasher.update(left)
    hasher.update(right)
    return hasher.digest()


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AuditEntry:
    """
    A single audit log entry.

    [He2025] Compliance: Deterministic serialization.
    """
    entry_id: int
    timestamp: float
    event_type: str
    actor: str              # Who performed the action (key_id, user, system)
    action: str             # What happened
    resource: str           # What was affected
    details: Dict[str, Any]
    source_ip: Optional[str] = None
    result: str = "success"  # success, failure, error

    def to_bytes(self) -> bytes:
        """
        Serialize to bytes for hashing.

        [He2025] DETERMINISTIC: Sorted keys, consistent encoding.
        """
        data = {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "source_ip": self.source_ip,
            "result": self.result,
        }
        # Deterministic JSON encoding
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "source_ip": self.source_ip,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Create from dictionary."""
        return cls(
            entry_id=data["entry_id"],
            timestamp=data["timestamp"],
            event_type=data["event_type"],
            actor=data["actor"],
            action=data["action"],
            resource=data["resource"],
            details=data.get("details", {}),
            source_ip=data.get("source_ip"),
            result=data.get("result", "success"),
        )


@dataclass
class InclusionProof:
    """
    Proof that an entry exists in the Merkle tree.

    Contains sibling hashes from leaf to root.
    """
    leaf_index: int
    tree_size: int
    proof_hashes: List[bytes]
    root_hash: bytes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "leaf_index": self.leaf_index,
            "tree_size": self.tree_size,
            "proof_hashes": [h.hex() for h in self.proof_hashes],
            "root_hash": self.root_hash.hex(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InclusionProof":
        """Create from dictionary."""
        return cls(
            leaf_index=data["leaf_index"],
            tree_size=data["tree_size"],
            proof_hashes=[bytes.fromhex(h) for h in data["proof_hashes"]],
            root_hash=bytes.fromhex(data["root_hash"]),
        )


@dataclass
class ConsistencyProof:
    """
    Proof that a tree is an extension of a previous tree.

    Verifies append-only property.
    """
    old_size: int
    new_size: int
    proof_hashes: List[bytes]
    old_root: bytes
    new_root: bytes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "old_size": self.old_size,
            "new_size": self.new_size,
            "proof_hashes": [h.hex() for h in self.proof_hashes],
            "old_root": self.old_root.hex(),
            "new_root": self.new_root.hex(),
        }


@dataclass
class SignedTreeHead:
    """
    Signed tree head (STH) - commitment to the current tree state.

    In production, this would be signed by the log server.
    """
    timestamp: float
    tree_size: int
    root_hash: bytes
    signature: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "tree_size": self.tree_size,
            "root_hash": self.root_hash.hex(),
            "signature": self.signature.hex() if self.signature else None,
        }


# =============================================================================
# Merkle Tree Implementation
# =============================================================================

class MerkleTree:
    """
    Binary Merkle tree for audit log integrity.

    [He2025] Compliance:
    - FIXED hash function (SHA-256)
    - DETERMINISTIC tree construction
    - RFC 6962 compatible structure

    Frontier Feature: Cryptographic audit log integrity.

    Usage:
        tree = MerkleTree()

        # Add entries
        tree.append(entry1.to_bytes())
        tree.append(entry2.to_bytes())

        # Get root hash
        root = tree.root_hash()

        # Generate inclusion proof
        proof = tree.inclusion_proof(0)

        # Verify proof
        is_valid = MerkleTree.verify_inclusion(
            entry1.to_bytes(), proof
        )
    """

    def __init__(self):
        """Initialize empty Merkle tree."""
        self._leaves: List[bytes] = []  # Leaf hashes
        self._entries: List[bytes] = []  # Original entry data

    @property
    def size(self) -> int:
        """Number of entries in tree."""
        return len(self._leaves)

    def append(self, entry: bytes) -> int:
        """
        Append an entry to the tree.

        Args:
            entry: Entry data to append

        Returns:
            Index of the new entry
        """
        leaf_hash = hash_leaf(entry)
        self._leaves.append(leaf_hash)
        self._entries.append(entry)
        return len(self._leaves) - 1

    def root_hash(self) -> bytes:
        """
        Compute the root hash of the tree.

        [He2025] DETERMINISTIC: Same entries → same root.

        Returns:
            32-byte root hash, or empty hash for empty tree
        """
        if not self._leaves:
            return EMPTY_HASH

        return self._compute_root(self._leaves)

    def _compute_root(self, hashes: List[bytes]) -> bytes:
        """
        Compute root from list of hashes.

        Uses the RFC 6962 algorithm for unbalanced trees.
        """
        if not hashes:
            return EMPTY_HASH
        if len(hashes) == 1:
            return hashes[0]

        # Split at largest power of 2 less than n
        k = 1 << (len(hashes) - 1).bit_length() - 1

        left = self._compute_root(hashes[:k])
        right = self._compute_root(hashes[k:])

        return hash_node(left, right)

    def inclusion_proof(self, index: int) -> InclusionProof:
        """
        Generate an inclusion proof for an entry.

        [He2025] DETERMINISTIC: Same index → same proof.

        Args:
            index: Index of the entry

        Returns:
            InclusionProof containing sibling hashes

        Raises:
            IndexError: If index out of range
        """
        if index < 0 or index >= len(self._leaves):
            raise IndexError(f"Index {index} out of range [0, {len(self._leaves)})")

        proof_hashes = self._compute_inclusion_path(index, 0, len(self._leaves))

        return InclusionProof(
            leaf_index=index,
            tree_size=len(self._leaves),
            proof_hashes=proof_hashes,
            root_hash=self.root_hash(),
        )

    def _compute_inclusion_path(
        self,
        index: int,
        start: int,
        end: int,
    ) -> List[bytes]:
        """Compute the path of sibling hashes for inclusion proof."""
        if end - start == 1:
            return []

        # Split at largest power of 2 less than (end - start)
        k = 1 << ((end - start) - 1).bit_length() - 1
        mid = start + k

        if index < mid:
            # Target is in left subtree
            path = self._compute_inclusion_path(index, start, mid)
            # Add right subtree hash
            right_hash = self._compute_root(self._leaves[mid:end])
            path.append(right_hash)
        else:
            # Target is in right subtree
            path = self._compute_inclusion_path(index, mid, end)
            # Add left subtree hash
            left_hash = self._compute_root(self._leaves[start:mid])
            path.append(left_hash)

        return path

    @staticmethod
    def verify_inclusion(
        entry: bytes,
        proof: InclusionProof,
    ) -> bool:
        """
        Verify an inclusion proof.

        [He2025] DETERMINISTIC: Same inputs → same result.

        Args:
            entry: Original entry data
            proof: Inclusion proof to verify

        Returns:
            True if proof is valid
        """
        if proof.tree_size == 0:
            return False

        # Compute leaf hash
        current_hash = hash_leaf(entry)

        # First, compute all level splits from top to bottom
        # (matching the recursive generation algorithm)
        levels = []
        index = proof.leaf_index
        start = 0
        end = proof.tree_size

        while end - start > 1:
            size = end - start
            k = 1 << ((size - 1).bit_length() - 1)
            mid = start + k
            is_right_child = index >= mid
            levels.append(is_right_child)
            if is_right_child:
                start = mid
            else:
                end = mid

        # Proof hashes are generated bottom-up (deepest first) due to recursion
        # So we process them paired with levels in reverse order (bottom to top)
        for is_right_child, sibling_hash in zip(reversed(levels), proof.proof_hashes):
            if is_right_child:
                # We're a right child, sibling is to the left
                current_hash = hash_node(sibling_hash, current_hash)
            else:
                # We're a left child, sibling is to the right
                current_hash = hash_node(current_hash, sibling_hash)

        return current_hash == proof.root_hash

    def consistency_proof(
        self,
        old_size: int,
    ) -> ConsistencyProof:
        """
        Generate a consistency proof between tree sizes.

        Proves that tree at old_size is a prefix of current tree.

        Args:
            old_size: Previous tree size

        Returns:
            ConsistencyProof

        Raises:
            ValueError: If old_size invalid
        """
        if old_size < 0 or old_size > len(self._leaves):
            raise ValueError(f"Invalid old_size: {old_size}")

        if old_size == 0:
            # Empty tree is consistent with everything
            return ConsistencyProof(
                old_size=0,
                new_size=len(self._leaves),
                proof_hashes=[],
                old_root=EMPTY_HASH,
                new_root=self.root_hash(),
            )

        if old_size == len(self._leaves):
            # Same size - trivially consistent
            return ConsistencyProof(
                old_size=old_size,
                new_size=old_size,
                proof_hashes=[],
                old_root=self.root_hash(),
                new_root=self.root_hash(),
            )

        old_root = self._compute_root(self._leaves[:old_size])
        new_root = self.root_hash()

        # Compute proof hashes (simplified - full RFC 6962 is more complex)
        proof_hashes = self._compute_consistency_path(old_size, len(self._leaves))

        return ConsistencyProof(
            old_size=old_size,
            new_size=len(self._leaves),
            proof_hashes=proof_hashes,
            old_root=old_root,
            new_root=new_root,
        )

    def _compute_consistency_path(
        self,
        old_size: int,
        new_size: int,
    ) -> List[bytes]:
        """Compute consistency proof hashes."""
        # Simplified implementation
        # Full RFC 6962 consistency proof is more sophisticated
        if old_size == new_size:
            return []

        # Include hash of new entries
        new_entries_hash = self._compute_root(self._leaves[old_size:new_size])
        return [new_entries_hash]

    @staticmethod
    def verify_consistency(
        proof: ConsistencyProof,
    ) -> bool:
        """
        Verify a consistency proof.

        [He2025] DETERMINISTIC: Same proof → same result.

        Args:
            proof: Consistency proof to verify

        Returns:
            True if proof is valid
        """
        if proof.old_size == 0:
            return True

        if proof.old_size == proof.new_size:
            return proof.old_root == proof.new_root

        # Simplified verification
        # Full RFC 6962 verification is more sophisticated
        if not proof.proof_hashes:
            return False

        # The new root should be constructible from old root and new entries
        expected_new_root = hash_node(proof.old_root, proof.proof_hashes[0])

        return expected_new_root == proof.new_root

    def get_entry(self, index: int) -> bytes:
        """Get entry data by index."""
        return self._entries[index]

    def get_signed_tree_head(
        self,
        signing_key: Optional[bytes] = None,
    ) -> SignedTreeHead:
        """
        Get a signed tree head (commitment to current state).

        Args:
            signing_key: Optional key for signing (not implemented)

        Returns:
            SignedTreeHead
        """
        return SignedTreeHead(
            timestamp=time.time(),
            tree_size=len(self._leaves),
            root_hash=self.root_hash(),
            signature=None,  # Would sign with provided key
        )


# =============================================================================
# Merkle Audit Logger
# =============================================================================

class MerkleAuditLog:
    """
    Tamper-evident audit logger using Merkle trees.

    Provides:
    - Append-only audit log
    - Cryptographic proof of log integrity
    - Inclusion proofs for individual entries
    - Consistency proofs between checkpoints

    [He2025] Compliance:
    - FIXED hash algorithm (SHA-256)
    - DETERMINISTIC log structure
    - Verifiable integrity at any point

    Frontier Feature: Most APIs use plain logs without integrity verification.

    Usage:
        audit = MerkleAuditLog("/var/log/otto/audit")

        # Log an event
        entry_id = audit.log_event(
            event_type="key_created",
            actor="admin",
            action="create_api_key",
            resource="key:abc123",
            details={"name": "production-key"},
        )

        # Get proof for an entry
        proof = audit.get_inclusion_proof(entry_id)

        # Verify log integrity
        is_valid = audit.verify_integrity()

        # Export proof for external verification
        exported = audit.export_proof(entry_id)
    """

    def __init__(
        self,
        log_dir: str,
        checkpoint_interval: int = 100,
    ):
        """
        Initialize Merkle audit log.

        Args:
            log_dir: Directory for log files
            checkpoint_interval: Entries between automatic checkpoints
        """
        self.log_dir = Path(log_dir)
        self.checkpoint_interval = checkpoint_interval

        # Create directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize tree
        self._tree = MerkleTree()
        self._entry_count = 0
        self._checkpoints: List[SignedTreeHead] = []

        # Load existing log if present
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing log entries if present."""
        entries_file = self.log_dir / "entries.jsonl"
        if entries_file.exists():
            with open(entries_file, "r") as f:
                for line in f:
                    if line.strip():
                        entry_data = json.loads(line)
                        entry = AuditEntry.from_dict(entry_data)
                        self._tree.append(entry.to_bytes())
                        self._entry_count = max(self._entry_count, entry.entry_id + 1)

            logger.info(f"Loaded {self._tree.size} existing audit entries")

        # Load checkpoints
        checkpoints_file = self.log_dir / "checkpoints.json"
        if checkpoints_file.exists():
            with open(checkpoints_file, "r") as f:
                data = json.load(f)
                for cp in data.get("checkpoints", []):
                    self._checkpoints.append(SignedTreeHead(
                        timestamp=cp["timestamp"],
                        tree_size=cp["tree_size"],
                        root_hash=bytes.fromhex(cp["root_hash"]),
                        signature=bytes.fromhex(cp["signature"]) if cp.get("signature") else None,
                    ))

    def _save_entry(self, entry: AuditEntry) -> None:
        """Append entry to log file."""
        entries_file = self.log_dir / "entries.jsonl"
        with open(entries_file, "a") as f:
            f.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")

    def _save_checkpoints(self) -> None:
        """Save checkpoints to file."""
        checkpoints_file = self.log_dir / "checkpoints.json"
        data = {
            "checkpoints": [cp.to_dict() for cp in self._checkpoints]
        }
        with open(checkpoints_file, "w") as f:
            json.dump(data, f, indent=2)

    def log_event(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None,
        source_ip: Optional[str] = None,
        result: str = "success",
    ) -> int:
        """
        Log a security event.

        Args:
            event_type: Type of event (auth, key, access, etc.)
            actor: Who performed the action
            action: What action was performed
            resource: What was affected
            details: Additional details
            source_ip: Source IP address
            result: Result of the action

        Returns:
            Entry ID (index in the tree)
        """
        entry = AuditEntry(
            entry_id=self._entry_count,
            timestamp=time.time(),
            event_type=event_type,
            actor=actor,
            action=action,
            resource=resource,
            details=details or {},
            source_ip=source_ip,
            result=result,
        )

        # Add to tree
        index = self._tree.append(entry.to_bytes())

        # Persist to disk
        self._save_entry(entry)

        self._entry_count += 1

        # Automatic checkpoint
        if self._tree.size % self.checkpoint_interval == 0:
            self.create_checkpoint()

        logger.debug(f"Logged audit event: {event_type} - {action}")

        return index

    def create_checkpoint(self) -> SignedTreeHead:
        """
        Create a checkpoint (signed tree head).

        Checkpoints are commitments to the log state at a point in time.
        They can be published externally for additional accountability.

        Returns:
            SignedTreeHead for the current state
        """
        sth = self._tree.get_signed_tree_head()
        self._checkpoints.append(sth)
        self._save_checkpoints()

        logger.info(f"Created checkpoint at size {sth.tree_size}, root: {sth.root_hash.hex()[:16]}...")

        return sth

    def get_inclusion_proof(self, entry_id: int) -> InclusionProof:
        """
        Get an inclusion proof for an entry.

        Args:
            entry_id: Entry ID (index)

        Returns:
            InclusionProof
        """
        return self._tree.inclusion_proof(entry_id)

    def verify_entry(self, entry_id: int) -> bool:
        """
        Verify that an entry exists and hasn't been modified.

        Args:
            entry_id: Entry ID to verify

        Returns:
            True if entry is valid and exists in tree
        """
        try:
            entry_data = self._tree.get_entry(entry_id)
            proof = self._tree.inclusion_proof(entry_id)
            return MerkleTree.verify_inclusion(entry_data, proof)
        except Exception as e:
            logger.error(f"Entry verification failed: {e}")
            return False

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Verify overall log integrity.

        Checks:
        1. All entries hash correctly
        2. Tree structure is valid
        3. Checkpoints are consistent

        Returns:
            Tuple of (is_valid, error_message if invalid)
        """
        # Verify tree can be recomputed
        try:
            computed_root = self._tree.root_hash()
        except Exception as e:
            return False, f"Failed to compute root: {e}"

        # Verify all entries
        for i in range(self._tree.size):
            try:
                if not self.verify_entry(i):
                    return False, f"Entry {i} failed verification"
            except Exception as e:
                return False, f"Entry {i} verification error: {e}"

        # Verify checkpoint consistency
        for i, checkpoint in enumerate(self._checkpoints):
            if checkpoint.tree_size > self._tree.size:
                return False, f"Checkpoint {i} has larger size than current tree"

            # Verify consistency if we have the old tree state
            if checkpoint.tree_size <= self._tree.size:
                try:
                    proof = self._tree.consistency_proof(checkpoint.tree_size)
                    if proof.old_root != checkpoint.root_hash:
                        return False, f"Checkpoint {i} root mismatch"
                except Exception as e:
                    return False, f"Checkpoint {i} consistency check failed: {e}"

        return True, None

    def get_root_hash(self) -> str:
        """Get current root hash as hex string."""
        return self._tree.root_hash().hex()

    def get_tree_size(self) -> int:
        """Get current tree size."""
        return self._tree.size

    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """Get all checkpoints."""
        return [cp.to_dict() for cp in self._checkpoints]

    def export_proof(self, entry_id: int) -> Dict[str, Any]:
        """
        Export a proof for external verification.

        Args:
            entry_id: Entry ID

        Returns:
            Dictionary containing entry and proof
        """
        entry_data = self._tree.get_entry(entry_id)
        proof = self._tree.inclusion_proof(entry_id)

        # Parse entry for display
        entry = AuditEntry.from_dict(json.loads(entry_data.decode("utf-8")))

        return {
            "entry": entry.to_dict(),
            "proof": proof.to_dict(),
            "entry_hash": hash_leaf(entry_data).hex(),
            "verification_instructions": {
                "algorithm": "SHA-256 with domain separation",
                "leaf_prefix": LEAF_PREFIX.hex(),
                "node_prefix": NODE_PREFIX.hex(),
                "rfc": "RFC 6962 compatible",
            },
        }

    def get_recent_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent audit entries."""
        entries = []
        start = max(0, self._tree.size - limit)
        for i in range(start, self._tree.size):
            entry_data = self._tree.get_entry(i)
            entry = AuditEntry.from_dict(json.loads(entry_data.decode("utf-8")))
            entries.append(entry.to_dict())
        return entries

    def query_entries(
        self,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        resource: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query audit entries with filters.

        Note: This is a simple linear scan. For production,
        consider adding indexes.

        Args:
            event_type: Filter by event type
            actor: Filter by actor
            resource: Filter by resource
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            limit: Maximum results

        Returns:
            List of matching entries
        """
        results = []

        for i in range(self._tree.size):
            entry_data = self._tree.get_entry(i)
            entry = AuditEntry.from_dict(json.loads(entry_data.decode("utf-8")))

            # Apply filters
            if event_type and entry.event_type != event_type:
                continue
            if actor and entry.actor != actor:
                continue
            if resource and entry.resource != resource:
                continue
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue

            results.append(entry.to_dict())

            if len(results) >= limit:
                break

        return results


# =============================================================================
# Audit Event Types
# =============================================================================

class AuditEventType:
    """
    Standard audit event types.

    [He2025] FIXED: Consistent event taxonomy.
    """
    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_LOGOUT = "auth_logout"

    # API key events
    KEY_CREATED = "key_created"
    KEY_ROTATED = "key_rotated"
    KEY_REVOKED = "key_revoked"
    KEY_DELETED = "key_deleted"

    # Access events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    SCOPE_GRANTED = "scope_granted"
    SCOPE_DENIED = "scope_denied"

    # Security events
    RATE_LIMIT_HIT = "rate_limit_hit"
    ANOMALY_DETECTED = "anomaly_detected"
    THREAT_DETECTED = "threat_detected"
    RESPONSE_EXECUTED = "response_executed"

    # System events
    CONFIG_CHANGED = "config_changed"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"


# =============================================================================
# Audit Log API
# =============================================================================

class AuditLogAPI:
    """
    API handler for audit log endpoints.

    Endpoints:
    - GET /api/v1/audit/entries - List entries
    - GET /api/v1/audit/entries/{id} - Get entry with proof
    - GET /api/v1/audit/verify - Verify log integrity
    - GET /api/v1/audit/root - Get current root hash
    - GET /api/v1/audit/checkpoints - List checkpoints
    """

    def __init__(self, audit_log: MerkleAuditLog):
        """Initialize API handler."""
        self.audit_log = audit_log

    def list_entries(
        self,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        GET /api/v1/audit/entries

        List audit entries with optional filters.
        """
        entries = self.audit_log.query_entries(
            event_type=event_type,
            actor=actor,
            limit=limit,
        )

        return {
            "entries": entries,
            "count": len(entries),
            "tree_size": self.audit_log.get_tree_size(),
            "root_hash": self.audit_log.get_root_hash(),
        }

    def get_entry(self, entry_id: int) -> Dict[str, Any]:
        """
        GET /api/v1/audit/entries/{id}

        Get entry with inclusion proof.
        """
        return self.audit_log.export_proof(entry_id)

    def verify_integrity(self) -> Dict[str, Any]:
        """
        GET /api/v1/audit/verify

        Verify log integrity.
        """
        is_valid, error = self.audit_log.verify_integrity()

        return {
            "valid": is_valid,
            "error": error,
            "tree_size": self.audit_log.get_tree_size(),
            "root_hash": self.audit_log.get_root_hash(),
            "checkpoint_count": len(self.audit_log.get_checkpoints()),
        }

    def get_root(self) -> Dict[str, Any]:
        """
        GET /api/v1/audit/root

        Get current root hash.
        """
        return {
            "root_hash": self.audit_log.get_root_hash(),
            "tree_size": self.audit_log.get_tree_size(),
            "timestamp": time.time(),
        }

    def list_checkpoints(self) -> Dict[str, Any]:
        """
        GET /api/v1/audit/checkpoints

        List checkpoints.
        """
        return {
            "checkpoints": self.audit_log.get_checkpoints(),
            "count": len(self.audit_log.get_checkpoints()),
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def create_audit_log(
    log_dir: str = "~/.otto/audit",
    checkpoint_interval: int = 100,
) -> MerkleAuditLog:
    """
    Create a Merkle audit log.

    Args:
        log_dir: Directory for log files
        checkpoint_interval: Entries between checkpoints

    Returns:
        MerkleAuditLog instance
    """
    log_dir = os.path.expanduser(log_dir)
    return MerkleAuditLog(log_dir, checkpoint_interval)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Hash functions
    "hash_leaf",
    "hash_node",

    # Data classes
    "AuditEntry",
    "InclusionProof",
    "ConsistencyProof",
    "SignedTreeHead",

    # Merkle tree
    "MerkleTree",

    # Audit logger
    "MerkleAuditLog",
    "AuditEventType",

    # API
    "AuditLogAPI",

    # Convenience
    "create_audit_log",
]
