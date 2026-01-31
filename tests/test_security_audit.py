"""
Tests for Merkle Audit Log
==========================

Comprehensive tests for tamper-evident security logging.
"""

import pytest
import json
import tempfile
from pathlib import Path
import time

from otto.security.audit import (
    AuditLog,
    AuditEvent,
    EventType,
    Severity,
    MerkleTree,
    MerkleProof,
    log_event,
    verify_log_integrity,
    get_audit_summary,
)


class TestMerkleTree:
    """Tests for Merkle tree implementation."""

    def test_empty_tree(self):
        """Empty tree has no root."""
        tree = MerkleTree()
        assert tree.root == ""
        assert tree.leaf_count == 0

    def test_single_leaf(self):
        """Single leaf tree has leaf as root."""
        tree = MerkleTree()
        tree.add_leaf("abc123")
        assert tree.leaf_count == 1
        assert tree.root != ""

    def test_two_leaves(self):
        """Two leaves create proper root."""
        tree = MerkleTree()
        tree.add_leaf("leaf1")
        tree.add_leaf("leaf2")
        assert tree.leaf_count == 2
        # Root should be hash of (leaf1 || leaf2)
        assert len(tree.root) == 64  # SHA-256 hex

    def test_multiple_leaves(self):
        """Multiple leaves build proper tree."""
        tree = MerkleTree()
        for i in range(10):
            tree.add_leaf(f"leaf{i}")
        assert tree.leaf_count == 10
        assert len(tree.root) == 64

    def test_proof_generation(self):
        """Can generate inclusion proofs."""
        tree = MerkleTree()
        for i in range(8):
            tree.add_leaf(f"leaf{i}")

        proof = tree.get_proof(3)
        assert proof is not None
        assert proof.leaf_hash == "leaf3"
        assert proof.root_hash == tree.root
        assert len(proof.proof_hashes) == 3  # log2(8) = 3

    def test_proof_verification(self):
        """Proofs verify correctly."""
        tree = MerkleTree()
        for i in range(8):
            tree.add_leaf(f"leaf{i}")

        for i in range(8):
            proof = tree.get_proof(i)
            assert proof is not None
            assert tree.verify_proof(proof)

    def test_invalid_proof(self):
        """Invalid proofs fail verification."""
        tree = MerkleTree()
        for i in range(8):
            tree.add_leaf(f"leaf{i}")

        proof = tree.get_proof(0)
        assert proof is not None

        # Tamper with proof
        bad_proof = MerkleProof(
            leaf_hash=proof.leaf_hash,
            proof_hashes=["baddata"] + proof.proof_hashes[1:],
            proof_directions=proof.proof_directions,
            root_hash=proof.root_hash,
        )
        assert not tree.verify_proof(bad_proof)

    def test_invalid_index(self):
        """Invalid index returns None."""
        tree = MerkleTree()
        tree.add_leaf("leaf0")
        assert tree.get_proof(-1) is None
        assert tree.get_proof(1) is None
        assert tree.get_proof(100) is None

    def test_odd_number_of_leaves(self):
        """Handles odd number of leaves."""
        tree = MerkleTree()
        for i in range(5):
            tree.add_leaf(f"leaf{i}")

        assert tree.leaf_count == 5
        # Should still work
        proof = tree.get_proof(4)
        assert proof is not None
        assert tree.verify_proof(proof)

    def test_serialization(self):
        """Tree serializes and deserializes."""
        tree = MerkleTree()
        for i in range(5):
            tree.add_leaf(f"leaf{i}")

        data = tree.to_dict()
        restored = MerkleTree.from_dict(data)

        assert restored.root == tree.root
        assert restored.leaf_count == tree.leaf_count


class TestAuditEvent:
    """Tests for audit events."""

    def test_event_creation(self):
        """Can create audit event."""
        event = AuditEvent(
            event_type=EventType.AUTH_SUCCESS,
            actor="user@example.com",
            description="User logged in",
        )
        assert event.event_type == EventType.AUTH_SUCCESS
        assert event.actor == "user@example.com"
        assert event.severity == Severity.INFO

    def test_event_hash(self):
        """Event hash is computed correctly."""
        event = AuditEvent(
            event_type=EventType.AUTH_SUCCESS,
            actor="user@example.com",
            description="User logged in",
            timestamp=1000.0,
        )
        event.sequence = 0
        event.prev_hash = "0" * 64

        hash1 = event.compute_hash()
        hash2 = event.compute_hash()

        assert hash1 == hash2  # Deterministic
        assert len(hash1) == 64  # SHA-256

    def test_different_events_different_hashes(self):
        """Different events have different hashes."""
        event1 = AuditEvent(
            event_type=EventType.AUTH_SUCCESS,
            actor="user1",
            description="Login",
            timestamp=1000.0,
        )
        event2 = AuditEvent(
            event_type=EventType.AUTH_SUCCESS,
            actor="user2",
            description="Login",
            timestamp=1000.0,
        )
        event1.sequence = event2.sequence = 0
        event1.prev_hash = event2.prev_hash = "0" * 64

        assert event1.compute_hash() != event2.compute_hash()

    def test_event_serialization(self):
        """Event serializes to dict and back."""
        event = AuditEvent(
            event_type=EventType.KEY_ROTATION,
            actor="system",
            description="Key rotated",
            severity=Severity.MEDIUM,
            metadata={"key_id": "abc123"},
        )
        event.event_hash = "hash123"
        event.sequence = 5
        event.prev_hash = "prevhash"

        data = event.to_dict()
        restored = AuditEvent.from_dict(data)

        assert restored.event_type == event.event_type
        assert restored.actor == event.actor
        assert restored.severity == event.severity
        assert restored.metadata == event.metadata
        assert restored.event_hash == event.event_hash


class TestAuditLog:
    """Tests for audit log."""

    def test_log_creation(self):
        """New log has initial event."""
        log = AuditLog()
        assert log.event_count == 1  # LOG_CREATED event
        assert log.last_event.event_type == EventType.LOG_CREATED

    def test_append_event(self):
        """Can append events to log."""
        log = AuditLog()
        initial_count = log.event_count

        event = AuditEvent(
            event_type=EventType.AUTH_SUCCESS,
            actor="user@test.com",
            description="Test login",
        )
        event_hash = log.append(event)

        assert log.event_count == initial_count + 1
        assert len(event_hash) == 64
        assert event.event_hash == event_hash

    def test_hash_chain(self):
        """Events form a proper hash chain."""
        log = AuditLog()

        for i in range(5):
            log.append(AuditEvent(
                event_type=EventType.AUTH_SUCCESS,
                actor=f"user{i}",
                description=f"Login {i}",
            ))

        # Verify chain
        events = log._events
        for i in range(1, len(events)):
            assert events[i].prev_hash == events[i - 1].event_hash

    def test_merkle_root_updates(self):
        """Merkle root updates with each event."""
        log = AuditLog()
        roots = [log.merkle_root]

        for i in range(3):
            log.append(AuditEvent(
                event_type=EventType.AUTH_SUCCESS,
                actor=f"user{i}",
                description=f"Login {i}",
            ))
            roots.append(log.merkle_root)

        # Each root should be different
        assert len(set(roots)) == len(roots)

    def test_get_event_by_hash(self):
        """Can retrieve event by hash."""
        log = AuditLog()

        event = AuditEvent(
            event_type=EventType.KEY_ROTATION,
            actor="system",
            description="Key rotated",
        )
        event_hash = log.append(event)

        retrieved = log.get_event(event_hash)
        assert retrieved is not None
        assert retrieved.actor == "system"
        assert retrieved.description == "Key rotated"

    def test_get_nonexistent_event(self):
        """Returns None for nonexistent event."""
        log = AuditLog()
        assert log.get_event("nonexistent") is None

    def test_query_events_by_type(self):
        """Can query events by type."""
        log = AuditLog()

        log.append(AuditEvent(EventType.AUTH_SUCCESS, "user1", "Login"))
        log.append(AuditEvent(EventType.AUTH_FAILURE, "user2", "Bad password"))
        log.append(AuditEvent(EventType.AUTH_SUCCESS, "user3", "Login"))

        successes = log.get_events(event_types=[EventType.AUTH_SUCCESS])
        assert len(successes) == 2

        failures = log.get_events(event_types=[EventType.AUTH_FAILURE])
        assert len(failures) == 1

    def test_query_events_by_actor(self):
        """Can query events by actor."""
        log = AuditLog()

        log.append(AuditEvent(EventType.AUTH_SUCCESS, "alice", "Login"))
        log.append(AuditEvent(EventType.AUTH_SUCCESS, "bob", "Login"))
        log.append(AuditEvent(EventType.AUTH_SUCCESS, "alice", "Action"))

        alice_events = log.get_events(actor="alice")
        assert len(alice_events) == 2

    def test_query_events_limit(self):
        """Query respects limit."""
        log = AuditLog()

        for i in range(20):
            log.append(AuditEvent(EventType.AUTH_SUCCESS, f"user{i}", "Login"))

        events = log.get_events(limit=5)
        assert len(events) == 5

    def test_inclusion_proof(self):
        """Can get and verify inclusion proofs."""
        log = AuditLog()

        hashes = []
        for i in range(10):
            h = log.append(AuditEvent(
                EventType.AUTH_SUCCESS, f"user{i}", f"Login {i}"
            ))
            hashes.append(h)

        # Verify each event
        for h in hashes:
            proof = log.get_inclusion_proof(h)
            assert proof is not None
            assert log.verify_inclusion(proof)

    def test_integrity_verification_passes(self):
        """Valid log passes integrity check."""
        log = AuditLog()

        for i in range(10):
            log.append(AuditEvent(
                EventType.AUTH_SUCCESS, f"user{i}", f"Login {i}"
            ))

        valid, error = log.verify_integrity()
        assert valid
        assert error is None

    def test_integrity_detects_tampering(self):
        """Tampered log fails integrity check."""
        log = AuditLog()

        for i in range(5):
            log.append(AuditEvent(
                EventType.AUTH_SUCCESS, f"user{i}", f"Login {i}"
            ))

        # Tamper with an event
        log._events[2].description = "TAMPERED"

        valid, error = log.verify_integrity()
        assert not valid
        assert "hash mismatch" in error.lower()

    def test_persistence(self):
        """Log persists to and loads from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audit.json"

            # Create and populate log
            log1 = AuditLog(storage_path=path)
            log1.append(AuditEvent(EventType.AUTH_SUCCESS, "user1", "Login"))
            log1.append(AuditEvent(EventType.KEY_ROTATION, "system", "Rotate"))

            # Load from file
            log2 = AuditLog.load(path)

            assert log2.event_count == log1.event_count
            assert log2.merkle_root == log1.merkle_root

            valid, _ = log2.verify_integrity()
            assert valid

    def test_summary(self):
        """Can get log summary."""
        log = AuditLog()

        log.append(AuditEvent(EventType.AUTH_SUCCESS, "user1", "Login"))
        log.append(AuditEvent(EventType.AUTH_SUCCESS, "user2", "Login"))
        log.append(AuditEvent(EventType.AUTH_FAILURE, "user3", "Bad pass"))

        summary = log.get_summary()
        assert summary['event_count'] == 4  # 3 + LOG_CREATED
        assert 'merkle_root' in summary
        assert 'event_counts' in summary


class TestGlobalFunctions:
    """Tests for global audit functions."""

    def test_log_event(self):
        """log_event helper works."""
        # Reset global
        import otto.security.audit as audit_module
        audit_module._audit_log = None

        event_hash = log_event(
            EventType.AUTH_SUCCESS,
            "test_user",
            "Test login",
            metadata={"ip": "127.0.0.1"},
        )

        assert len(event_hash) == 64

    def test_verify_integrity(self):
        """verify_log_integrity helper works."""
        import otto.security.audit as audit_module
        audit_module._audit_log = None

        log_event(EventType.AUTH_SUCCESS, "user", "Login")

        valid, error = verify_log_integrity()
        assert valid
        assert error is None

    def test_get_summary(self):
        """get_audit_summary helper works."""
        import otto.security.audit as audit_module
        audit_module._audit_log = None

        log_event(EventType.AUTH_SUCCESS, "user", "Login")

        summary = get_audit_summary()
        assert 'event_count' in summary
        assert 'merkle_root' in summary


class TestDeterminism:
    """Tests for [He2025] determinism compliance."""

    def test_same_input_same_hash(self):
        """Same input produces same hash."""
        event = AuditEvent(
            event_type=EventType.AUTH_SUCCESS,
            actor="user",
            description="Login",
            timestamp=1000.0,
        )
        event.sequence = 0
        event.prev_hash = "0" * 64

        hashes = [event.compute_hash() for _ in range(10)]
        assert len(set(hashes)) == 1

    def test_proof_determinism(self):
        """Same tree produces same proofs."""
        tree1 = MerkleTree()
        tree2 = MerkleTree()

        for i in range(5):
            tree1.add_leaf(f"leaf{i}")
            tree2.add_leaf(f"leaf{i}")

        proof1 = tree1.get_proof(2)
        proof2 = tree2.get_proof(2)

        assert proof1.root_hash == proof2.root_hash
        assert proof1.proof_hashes == proof2.proof_hashes
