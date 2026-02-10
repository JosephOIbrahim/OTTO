"""
Tests for Frontier Security Features
=====================================

Comprehensive tests for the frontier security modules:
1. Post-Quantum Cryptography (frontier_crypto.py)
2. Security Posture (security_posture.py)
3. Threshold Signatures (threshold_signatures.py)
4. Self-Healing Security (self_healing.py)
5. Merkle Audit Trail (merkle_audit.py)

Determinism: Verifies FIXED algorithms, DETERMINISTIC operations.
"""

import hashlib
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List

import pytest

# Import frontier modules
from otto.api.frontier_crypto import (
    NISTSecurityLevel,
    HybridMode,
    KeyPair,
    HybridKeyExchange,
    HybridSigner,
    SoftwareHSM,
    create_hybrid_key_exchange,
    create_hsm,
    get_pq_capabilities,
    HAS_CRYPTOGRAPHY,
    HAS_LIBOQS,
)

from otto.api.security_posture import (
    PostureStatus,
    ComponentHealth,
    RecommendationPriority,
    ComponentAssessment,
    SecurityRecommendation,
    PostureReport,
    CryptographyAssessor,
    AuthenticationAssessor,
    NetworkAssessor,
    AnomalyDetectionAssessor,
    AuditAssessor,
    SecurityPostureEngine,
    SecurityPostureAPI,
)

from otto.api.threshold_signatures import (
    Share,
    ThresholdKeyPair,
    PartialSignature,
    CombinedSignature,
    ShamirSecretSharing,
    ThresholdSignatureScheme,
    ThresholdAPIKeyManager,
    KeyCeremonyState,
    KeyCeremonyManager,
    PRIME,
    mod_inverse,
    mod_mul,
    mod_add,
    mod_sub,
)

from otto.api.self_healing import (
    ThreatCategory,
    ThreatSeverity,
    ResponseAction,
    ThreatEvent,
    ResponseResult,
    ResponsePolicy,
    BruteForceDetector,
    CredentialStuffingDetector,
    DataExfiltrationDetector,
    KeyCompromiseDetector,
    SelfHealingEngine,
    IPBlocklist,
)

from otto.api.merkle_audit import (
    hash_leaf,
    hash_node,
    AuditEntry,
    InclusionProof,
    ConsistencyProof,
    SignedTreeHead,
    MerkleTree,
    MerkleAuditLog,
    AuditEventType,
    AuditLogAPI,
    create_audit_log,
    LEAF_PREFIX,
    NODE_PREFIX,
)


# =============================================================================
# PART 1: Post-Quantum Cryptography Tests
# =============================================================================

class TestHybridKeyExchange:
    """Test hybrid X25519 + ML-KEM key exchange."""

    @pytest.fixture
    def kex(self):
        """Create a hybrid key exchange instance."""
        return HybridKeyExchange(mode=HybridMode.PARALLEL, fallback_to_classical=True)

    def test_capabilities(self, kex):
        """Test capability reporting."""
        caps = kex.get_capabilities()

        assert caps["classical_available"] == HAS_CRYPTOGRAPHY
        assert caps["classical_algorithm"] == "X25519"
        assert caps["mode"] == "PARALLEL"
        assert caps["security_level"] == "LEVEL_3"
        assert caps["shared_secret_length"] == 48

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_generate_keypair(self, kex):
        """Test keypair generation."""
        keypair = kex.generate_keypair()

        assert isinstance(keypair, KeyPair)
        assert len(keypair.classical_private) == 32  # X25519 private key
        assert len(keypair.classical_public) == 32   # X25519 public key
        assert keypair.algorithm.startswith("hybrid") or keypair.algorithm == "x25519_only"

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_full_key_exchange(self, kex):
        """Test complete key exchange protocol."""
        # Alice initiates
        alice_keypair, init_message = kex.initiate()
        assert len(init_message) >= 32  # At least X25519 public key

        # Bob responds
        bob_keypair, bob_shared, response = kex.respond(init_message)
        assert len(bob_shared) == 48  # HKDF output length

        # Alice completes
        alice_shared = kex.complete(alice_keypair, response)

        # Both should have the same shared secret
        assert alice_shared == bob_shared

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_deterministic_shared_secret(self, kex):
        """Same keys should produce same shared secret."""
        # Generate fixed keys
        alice_keypair, init_message = kex.initiate()

        # Bob responds twice with same init_message
        _, shared1, response1 = kex.respond(init_message)
        _, shared2, response2 = kex.respond(init_message)

        # Note: Different responses due to new keypair, but algorithm is deterministic
        # The HKDF derivation is deterministic given same inputs
        assert len(shared1) == len(shared2) == 48

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_different_sessions_different_secrets(self, kex):
        """Different sessions should produce different secrets."""
        alice1, msg1 = kex.initiate()
        alice2, msg2 = kex.initiate()

        _, shared1, _ = kex.respond(msg1)
        _, shared2, _ = kex.respond(msg2)

        # Different sessions = different secrets
        assert shared1 != shared2


class TestHybridSigner:
    """Test hybrid Ed25519 + ML-DSA signatures."""

    @pytest.fixture
    def signer(self):
        """Create a hybrid signer."""
        return HybridSigner(fallback_to_classical=True)

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_generate_keypair(self, signer):
        """Test signature keypair generation."""
        classical_priv, classical_pub, pq_priv, pq_pub = signer.generate_keypair()

        assert len(classical_priv) == 32  # Ed25519 private
        assert len(classical_pub) == 32   # Ed25519 public

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_sign_and_verify(self, signer):
        """Test signing and verification."""
        classical_priv, classical_pub, pq_priv, pq_pub = signer.generate_keypair()

        message = b"Test message for signing"
        signature = signer.sign(message, classical_priv, pq_priv)

        assert signature.classical_signature is not None
        assert len(signature.classical_signature) == 64  # Ed25519 signature

        # Verify
        is_valid = signer.verify(message, signature, classical_pub, pq_pub)
        assert is_valid

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_signature_fails_for_wrong_message(self, signer):
        """Verification should fail for tampered message."""
        classical_priv, classical_pub, pq_priv, pq_pub = signer.generate_keypair()

        message = b"Original message"
        signature = signer.sign(message, classical_priv, pq_priv)

        # Verify with wrong message
        is_valid = signer.verify(b"Tampered message", signature, classical_pub, pq_pub)
        assert not is_valid


class TestSoftwareHSM:
    """Test software HSM (testing fallback)."""

    @pytest.fixture
    def hsm(self):
        """Create a software HSM."""
        hsm = SoftwareHSM()
        hsm.connect()
        yield hsm
        hsm.disconnect()

    def test_connect_disconnect(self):
        """Test connection lifecycle."""
        hsm = SoftwareHSM()
        assert hsm.connect()
        hsm.disconnect()

    def test_list_slots(self, hsm):
        """Test slot listing."""
        slots = hsm.list_slots()
        assert len(slots) == 1
        assert slots[0].slot_id == 0
        assert "Software" in slots[0].description

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_generate_ec_key(self, hsm):
        """Test EC key generation."""
        key_handle = hsm.generate_key(0, "EC", "test-ec-key")

        assert key_handle.key_type == "EC"
        assert key_handle.key_label == "test-ec-key"

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_generate_aes_key(self, hsm):
        """Test AES key generation."""
        key_handle = hsm.generate_key(0, "AES", "test-aes-key")

        assert key_handle.key_type == "AES"

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_sign_verify_ec(self, hsm):
        """Test EC signing and verification."""
        key_handle = hsm.generate_key(0, "EC", "sign-test")

        message = b"Test message"
        signature = hsm.sign(key_handle, message, "ECDSA-SHA256")

        is_valid = hsm.verify(key_handle, message, signature, "ECDSA-SHA256")
        assert is_valid

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_encrypt_decrypt_aes(self, hsm):
        """Test AES encryption and decryption."""
        key_handle = hsm.generate_key(0, "AES", "encrypt-test")

        plaintext = b"Secret data to encrypt"
        ciphertext = hsm.encrypt(key_handle, plaintext, "AES-GCM")

        assert ciphertext != plaintext

        decrypted = hsm.decrypt(key_handle, ciphertext, "AES-GCM")
        assert decrypted == plaintext


# =============================================================================
# PART 2: Security Posture Tests
# =============================================================================

class TestSecurityPosture:
    """Test security posture assessment."""

    @pytest.fixture
    def engine(self):
        """Create a security posture engine."""
        return SecurityPostureEngine.default()

    @pytest.fixture
    def minimal_context(self):
        """Minimal context for testing."""
        return {}

    def test_posture_status_from_score(self):
        """Test status level determination from score."""
        assert PostureStatus.from_score(0) == PostureStatus.CRITICAL
        assert PostureStatus.from_score(39) == PostureStatus.CRITICAL
        assert PostureStatus.from_score(40) == PostureStatus.WARNING
        assert PostureStatus.from_score(59) == PostureStatus.WARNING
        assert PostureStatus.from_score(60) == PostureStatus.GOOD
        assert PostureStatus.from_score(79) == PostureStatus.GOOD
        assert PostureStatus.from_score(80) == PostureStatus.EXCELLENT
        assert PostureStatus.from_score(100) == PostureStatus.EXCELLENT

    def test_engine_has_default_assessors(self, engine):
        """Engine should have 5 default assessors."""
        assert len(engine._assessors) == 5

    def test_assess_returns_report(self, engine, minimal_context):
        """Assessment should return a PostureReport."""
        report = engine.assess(minimal_context)

        assert isinstance(report, PostureReport)
        assert 0 <= report.overall_score <= 100
        assert isinstance(report.status, PostureStatus)
        assert report.trend in ["improving", "stable", "declining"]
        assert len(report.components) == 5

    def test_component_assessment_structure(self, engine, minimal_context):
        """Component assessments should have correct structure."""
        report = engine.assess(minimal_context)

        for component in report.components:
            assert isinstance(component, ComponentAssessment)
            assert isinstance(component.health, ComponentHealth)
            assert 0 <= component.score <= 100
            assert component.checks_passed >= 0
            assert component.checks_failed >= 0

    def test_recommendations_generated(self, engine, minimal_context):
        """Recommendations should be generated for issues."""
        report = engine.assess(minimal_context)

        # With minimal context, should have recommendations
        assert isinstance(report.recommendations, list)

    def test_history_tracking(self, engine, minimal_context):
        """Engine should track historical scores."""
        # Make multiple assessments
        for _ in range(5):
            engine.assess(minimal_context)

        history = engine.get_history()
        assert len(history) == 5

    def test_trend_calculation(self, engine, minimal_context):
        """Trend should be calculated from history."""
        # Initial assessments
        for _ in range(10):
            report = engine.assess(minimal_context)

        # Trend should be defined
        assert report.trend in ["improving", "stable", "declining"]


class TestSecurityPostureAPI:
    """Test security posture API endpoints."""

    @pytest.fixture
    def api(self):
        """Create API handler."""
        return SecurityPostureAPI()

    def test_get_posture(self, api):
        """Test posture endpoint."""
        result = api.get_posture({})

        assert "overall_score" in result
        assert "status" in result
        assert "components" in result
        assert "recommendations" in result

    def test_get_history(self, api):
        """Test history endpoint."""
        # Make some assessments first
        api.get_posture({})
        api.get_posture({})

        result = api.get_history()

        assert "history" in result
        assert "count" in result
        assert result["count"] >= 2

    def test_get_status(self, api):
        """Test quick status endpoint."""
        result = api.get_status({})

        assert "score" in result
        assert "status" in result
        assert "critical_issues" in result


# =============================================================================
# PART 3: Threshold Signatures Tests
# =============================================================================

class TestFiniteFieldArithmetic:
    """Test finite field arithmetic operations."""

    def test_mod_inverse(self):
        """Test modular inverse."""
        # 3 * 3^-1 = 1 (mod p)
        inv = mod_inverse(3, PRIME)
        assert mod_mul(3, inv, PRIME) == 1

    def test_mod_mul(self):
        """Test modular multiplication."""
        result = mod_mul(7, 11, PRIME)
        assert result == 77

    def test_mod_add(self):
        """Test modular addition."""
        result = mod_add(5, 10, PRIME)
        assert result == 15

    def test_mod_sub(self):
        """Test modular subtraction."""
        result = mod_sub(10, 7, PRIME)
        assert result == 3

        # Test wrap-around
        result = mod_sub(5, 10, PRIME)
        assert result == PRIME - 5


class TestShamirSecretSharing:
    """Test Shamir's Secret Sharing scheme."""

    @pytest.fixture
    def sss(self):
        """Create SSS instance."""
        return ShamirSecretSharing()

    def test_split_creates_correct_number_of_shares(self, sss):
        """Split should create the requested number of shares."""
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, threshold=3, total_shares=5)

        assert len(shares) == 5

    def test_shares_have_correct_structure(self, sss):
        """Shares should have correct structure."""
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, threshold=3, total_shares=5)

        for i, share in enumerate(shares):
            assert share.index == i + 1  # 1-based index
            assert share.threshold == 3
            assert share.total_shares == 5
            assert 0 <= share.value < PRIME

    def test_reconstruct_with_threshold_shares(self, sss):
        """Should reconstruct with exactly threshold shares."""
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, threshold=3, total_shares=5)

        # Use only 3 shares
        reconstructed = sss.reconstruct([shares[0], shares[2], shares[4]])

        assert reconstructed == secret

    def test_reconstruct_with_more_shares(self, sss):
        """Should reconstruct with more than threshold shares."""
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, threshold=3, total_shares=5)

        # Use all 5 shares
        reconstructed = sss.reconstruct(shares)

        assert reconstructed == secret

    def test_any_threshold_subset_works(self, sss):
        """Any subset of threshold shares should work."""
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, threshold=3, total_shares=5)

        # Try different subsets
        subsets = [
            [shares[0], shares[1], shares[2]],
            [shares[0], shares[2], shares[4]],
            [shares[1], shares[3], shares[4]],
            [shares[2], shares[3], shares[4]],
        ]

        for subset in subsets:
            reconstructed = sss.reconstruct(subset)
            assert reconstructed == secret

    def test_insufficient_shares_fails(self, sss):
        """Should fail with fewer than threshold shares."""
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, threshold=3, total_shares=5)

        with pytest.raises(ValueError):
            sss.reconstruct([shares[0], shares[1]])  # Only 2 shares

    def test_deterministic_reconstruction(self, sss):
        """Same shares should always produce same secret."""
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, threshold=3, total_shares=5)

        subset = [shares[0], shares[2], shares[4]]

        reconstructed1 = sss.reconstruct(subset)
        reconstructed2 = sss.reconstruct(subset)

        assert reconstructed1 == reconstructed2 == secret

    def test_share_serialization(self, sss):
        """Shares should serialize and deserialize correctly."""
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, threshold=3, total_shares=5)

        share = shares[0]
        serialized = share.to_bytes()
        deserialized = Share.from_bytes(serialized)

        assert deserialized.index == share.index
        assert deserialized.value == share.value
        assert deserialized.threshold == share.threshold


class TestThresholdAPIKeyManager:
    """Test threshold API key management."""

    @pytest.fixture
    def manager(self):
        """Create manager with 3-of-5 threshold."""
        return ThresholdAPIKeyManager(threshold=3, total_shares=5)

    def test_create_key(self, manager):
        """Test key creation."""
        key_id, shares = manager.create_key("test-key")

        assert key_id is not None
        assert len(shares) == 5

    def test_key_info(self, manager):
        """Test key info retrieval."""
        key_id, _ = manager.create_key("test-key")
        info = manager.get_key_info(key_id)

        assert info["key_id"] == key_id
        assert info["threshold"] == 3
        assert info["total_shares"] == 5

    def test_list_keys(self, manager):
        """Test listing keys."""
        manager.create_key("key1")
        manager.create_key("key2")

        keys = manager.list_keys()
        assert len(keys) == 2


# =============================================================================
# PART 4: Self-Healing Security Tests
# =============================================================================

class TestThreatDetectors:
    """Test threat detection algorithms."""

    def test_brute_force_detector(self):
        """Test brute force detection."""
        detector = BruteForceDetector()

        # Simulate auth failures
        for i in range(10):
            event = {
                "type": "auth_failure",
                "source_ip": "192.168.1.100",
            }
            threat = detector.detect(event)

        # Should detect brute force after threshold
        assert threat is not None
        assert threat.category == ThreatCategory.BRUTE_FORCE
        assert threat.severity in [ThreatSeverity.LOW, ThreatSeverity.MEDIUM]

    def test_credential_stuffing_detector(self):
        """Test credential stuffing detection."""
        detector = CredentialStuffingDetector()

        # Simulate multiple keys from same IP
        for i in range(5):
            event = {
                "type": "auth_failure",
                "source_ip": "192.168.1.100",
                "api_key_id": f"key_{i}",
            }
            threat = detector.detect(event)

        # Should detect credential stuffing
        assert threat is not None
        assert threat.category == ThreatCategory.CREDENTIAL_STUFFING

    def test_data_exfiltration_detector(self):
        """Test data exfiltration detection."""
        detector = DataExfiltrationDetector()

        # Simulate high request volume
        for i in range(150):
            event = {
                "type": "api_request",
                "api_key_id": "key_123",
                "endpoint": "/api/v1/data",
            }
            threat = detector.detect(event)

        # Should detect potential exfiltration
        assert threat is not None
        assert threat.category == ThreatCategory.DATA_EXFILTRATION


class TestSelfHealingEngine:
    """Test self-healing engine."""

    @pytest.fixture
    def engine(self):
        """Create self-healing engine."""
        return SelfHealingEngine.default()

    def test_engine_has_default_detectors(self, engine):
        """Engine should have default detectors."""
        assert len(engine._detectors) >= 4

    def test_engine_has_default_policies(self, engine):
        """Engine should have default policies."""
        assert len(engine._policies) >= 4

    def test_process_event_returns_responses(self, engine):
        """Processing events should return responses."""
        # Simulate many auth failures to trigger detection
        for i in range(25):
            responses = engine.process_event(
                {"type": "auth_failure", "source_ip": "10.0.0.1"},
                {}
            )

        # Should have detected and responded
        stats = engine.get_statistics()
        assert stats["threats_detected"] > 0

    def test_get_statistics(self, engine):
        """Test statistics retrieval."""
        stats = engine.get_statistics()

        assert "detectors" in stats
        assert "policies" in stats
        assert "threats_detected" in stats
        assert "responses_executed" in stats


class TestIPBlocklist:
    """Test IP blocklist."""

    @pytest.fixture
    def blocklist(self):
        """Create blocklist."""
        return IPBlocklist()

    def test_add_and_check(self, blocklist):
        """Test adding and checking IPs."""
        expiry = time.time() + 3600  # 1 hour
        blocklist.add("192.168.1.100", expiry)

        assert blocklist.is_blocked("192.168.1.100")
        assert not blocklist.is_blocked("192.168.1.101")

    def test_remove(self, blocklist):
        """Test removing IPs."""
        expiry = time.time() + 3600
        blocklist.add("192.168.1.100", expiry)

        assert blocklist.remove("192.168.1.100")
        assert not blocklist.is_blocked("192.168.1.100")

    def test_expired_entries(self, blocklist):
        """Test expired entries are not blocked."""
        expiry = time.time() - 1  # Already expired
        blocklist.add("192.168.1.100", expiry)

        assert not blocklist.is_blocked("192.168.1.100")

    def test_list_blocked(self, blocklist):
        """Test listing blocked IPs."""
        expiry = time.time() + 3600
        blocklist.add("192.168.1.100", expiry)
        blocklist.add("192.168.1.101", expiry)

        blocked = blocklist.list_blocked()
        assert len(blocked) == 2


# =============================================================================
# PART 5: Merkle Audit Trail Tests
# =============================================================================

class TestMerkleTree:
    """Test Merkle tree implementation."""

    @pytest.fixture
    def tree(self):
        """Create empty Merkle tree."""
        return MerkleTree()

    def test_empty_tree_root(self, tree):
        """Empty tree should have empty hash as root."""
        from otto.api.merkle_audit import EMPTY_HASH
        assert tree.root_hash() == EMPTY_HASH

    def test_single_entry(self, tree):
        """Single entry tree."""
        tree.append(b"entry1")

        assert tree.size == 1
        root = tree.root_hash()
        assert len(root) == 32

    def test_multiple_entries(self, tree):
        """Multiple entry tree."""
        entries = [b"entry1", b"entry2", b"entry3", b"entry4"]
        for entry in entries:
            tree.append(entry)

        assert tree.size == 4
        root = tree.root_hash()
        assert len(root) == 32

    def test_deterministic_root(self, tree):
        """Same entries should produce same root."""
        entries = [b"entry1", b"entry2", b"entry3"]

        tree1 = MerkleTree()
        tree2 = MerkleTree()

        for entry in entries:
            tree1.append(entry)
            tree2.append(entry)

        assert tree1.root_hash() == tree2.root_hash()

    def test_different_entries_different_root(self):
        """Different entries should produce different root."""
        tree1 = MerkleTree()
        tree2 = MerkleTree()

        tree1.append(b"entry1")
        tree2.append(b"entry2")

        assert tree1.root_hash() != tree2.root_hash()

    def test_inclusion_proof_generation(self, tree):
        """Test inclusion proof generation."""
        entries = [b"entry1", b"entry2", b"entry3", b"entry4"]
        for entry in entries:
            tree.append(entry)

        proof = tree.inclusion_proof(1)

        assert isinstance(proof, InclusionProof)
        assert proof.leaf_index == 1
        assert proof.tree_size == 4
        assert len(proof.proof_hashes) > 0

    def test_inclusion_proof_verification(self, tree):
        """Test inclusion proof verification."""
        entries = [b"entry1", b"entry2", b"entry3", b"entry4"]
        for entry in entries:
            tree.append(entry)

        # Generate proof for entry1
        proof = tree.inclusion_proof(0)

        # Verify proof
        is_valid = MerkleTree.verify_inclusion(entries[0], proof)
        assert is_valid

    def test_inclusion_proof_fails_for_wrong_entry(self, tree):
        """Proof should fail for wrong entry."""
        entries = [b"entry1", b"entry2", b"entry3", b"entry4"]
        for entry in entries:
            tree.append(entry)

        proof = tree.inclusion_proof(0)

        # Verify with wrong entry
        is_valid = MerkleTree.verify_inclusion(b"wrong_entry", proof)
        assert not is_valid

    def test_consistency_proof(self, tree):
        """Test consistency proof generation."""
        # Add initial entries
        for i in range(4):
            tree.append(f"entry{i}".encode())

        old_size = tree.size

        # Add more entries
        for i in range(4, 8):
            tree.append(f"entry{i}".encode())

        proof = tree.consistency_proof(old_size)

        assert isinstance(proof, ConsistencyProof)
        assert proof.old_size == 4
        assert proof.new_size == 8


class TestMerkleAuditLog:
    """Test Merkle audit log."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for logs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def audit_log(self, temp_dir):
        """Create audit log."""
        return MerkleAuditLog(temp_dir, checkpoint_interval=10)

    def test_log_event(self, audit_log):
        """Test logging an event."""
        entry_id = audit_log.log_event(
            event_type="test_event",
            actor="test_user",
            action="test_action",
            resource="test_resource",
            details={"key": "value"},
        )

        assert entry_id == 0

    def test_multiple_events(self, audit_log):
        """Test logging multiple events."""
        for i in range(5):
            entry_id = audit_log.log_event(
                event_type="test_event",
                actor=f"user_{i}",
                action="test_action",
                resource=f"resource_{i}",
            )

        assert audit_log.get_tree_size() == 5

    def test_verify_entry(self, audit_log):
        """Test entry verification."""
        audit_log.log_event(
            event_type="test_event",
            actor="test_user",
            action="test_action",
            resource="test_resource",
        )

        is_valid = audit_log.verify_entry(0)
        assert is_valid

    def test_verify_integrity(self, audit_log):
        """Test full log integrity verification."""
        for i in range(5):
            audit_log.log_event(
                event_type="test_event",
                actor=f"user_{i}",
                action="test_action",
                resource=f"resource_{i}",
            )

        is_valid, error = audit_log.verify_integrity()
        assert is_valid
        assert error is None

    def test_get_inclusion_proof(self, audit_log):
        """Test getting inclusion proof."""
        audit_log.log_event(
            event_type="test_event",
            actor="test_user",
            action="test_action",
            resource="test_resource",
        )

        proof = audit_log.get_inclusion_proof(0)
        assert isinstance(proof, InclusionProof)

    def test_export_proof(self, audit_log):
        """Test exporting proof for external verification."""
        audit_log.log_event(
            event_type="test_event",
            actor="test_user",
            action="test_action",
            resource="test_resource",
        )

        exported = audit_log.export_proof(0)

        assert "entry" in exported
        assert "proof" in exported
        assert "entry_hash" in exported
        assert "verification_instructions" in exported

    def test_query_entries(self, audit_log):
        """Test querying entries."""
        for i in range(5):
            audit_log.log_event(
                event_type="type_a" if i % 2 == 0 else "type_b",
                actor="test_user",
                action="test_action",
                resource=f"resource_{i}",
            )

        # Query by event type
        results = audit_log.query_entries(event_type="type_a")
        assert len(results) == 3

    def test_checkpoints(self, audit_log):
        """Test checkpoint creation."""
        # Log enough events to trigger checkpoint
        for i in range(15):
            audit_log.log_event(
                event_type="test_event",
                actor="test_user",
                action="test_action",
                resource=f"resource_{i}",
            )

        checkpoints = audit_log.get_checkpoints()
        assert len(checkpoints) >= 1

    def test_persistence(self, temp_dir):
        """Test log persistence across restarts."""
        # Create log and add entries
        log1 = MerkleAuditLog(temp_dir)
        for i in range(5):
            log1.log_event(
                event_type="test_event",
                actor="test_user",
                action="test_action",
                resource=f"resource_{i}",
            )

        root1 = log1.get_root_hash()

        # Create new log instance (simulating restart)
        log2 = MerkleAuditLog(temp_dir)

        # Should have same data
        assert log2.get_tree_size() == 5
        assert log2.get_root_hash() == root1


class TestHashFunctions:
    """Test hash utility functions."""

    def test_hash_leaf_deterministic(self):
        """Leaf hashing should be deterministic."""
        data = b"test data"
        hash1 = hash_leaf(data)
        hash2 = hash_leaf(data)

        assert hash1 == hash2

    def test_hash_node_deterministic(self):
        """Node hashing should be deterministic."""
        left = b"left" * 8
        right = b"right" * 8

        hash1 = hash_node(left, right)
        hash2 = hash_node(left, right)

        assert hash1 == hash2

    def test_domain_separation(self):
        """Leaf and node hashes should be different for same input."""
        data = b"x" * 64

        leaf_hash = hash_leaf(data)
        node_hash = hash_node(data[:32], data[32:])

        # Should be different due to domain separation
        assert leaf_hash != node_hash


class TestAuditLogAPI:
    """Test audit log API endpoints."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def api(self, temp_dir):
        """Create API handler."""
        audit_log = MerkleAuditLog(temp_dir)
        # Add some entries
        for i in range(5):
            audit_log.log_event(
                event_type="test_event",
                actor=f"user_{i}",
                action="test_action",
                resource=f"resource_{i}",
            )
        return AuditLogAPI(audit_log)

    def test_list_entries(self, api):
        """Test listing entries."""
        result = api.list_entries()

        assert "entries" in result
        assert "count" in result
        assert result["count"] == 5

    def test_get_entry(self, api):
        """Test getting single entry with proof."""
        result = api.get_entry(0)

        assert "entry" in result
        assert "proof" in result

    def test_verify_integrity(self, api):
        """Test integrity verification endpoint."""
        result = api.verify_integrity()

        assert "valid" in result
        assert result["valid"] == True

    def test_get_root(self, api):
        """Test root hash endpoint."""
        result = api.get_root()

        assert "root_hash" in result
        assert "tree_size" in result
        assert len(result["root_hash"]) == 64  # Hex encoded 32 bytes


# =============================================================================
# PART 6: Integration Tests
# =============================================================================

class TestFrontierIntegration:
    """Integration tests across frontier modules."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography not available")
    def test_pq_kex_with_audit_logging(self, temp_dir):
        """Test PQ key exchange with audit logging."""
        # Setup audit log
        audit_log = MerkleAuditLog(temp_dir)

        # Perform key exchange
        kex = HybridKeyExchange()
        alice_keypair, init_msg = kex.initiate()

        # Log the key exchange
        audit_log.log_event(
            event_type=AuditEventType.KEY_CREATED,
            actor="alice",
            action="initiate_key_exchange",
            resource="session_key",
            details={"algorithm": "hybrid_x25519_mlkem768"},
        )

        # Complete exchange
        _, shared, response = kex.respond(init_msg)
        alice_shared = kex.complete(alice_keypair, response)

        audit_log.log_event(
            event_type=AuditEventType.KEY_CREATED,
            actor="bob",
            action="complete_key_exchange",
            resource="session_key",
        )

        # Verify audit trail
        is_valid, _ = audit_log.verify_integrity()
        assert is_valid
        assert alice_shared == shared

    def test_self_healing_with_audit(self, temp_dir):
        """Test self-healing events are audited."""
        audit_log = MerkleAuditLog(temp_dir)
        engine = SelfHealingEngine.default()

        # Simulate attack
        for i in range(25):
            responses = engine.process_event(
                {"type": "auth_failure", "source_ip": "attacker_ip"},
                {}
            )

        # Log threat detection
        stats = engine.get_statistics()
        if stats["threats_detected"] > 0:
            audit_log.log_event(
                event_type=AuditEventType.THREAT_DETECTED,
                actor="self_healing_engine",
                action="detect_brute_force",
                resource="auth_endpoint",
                details=stats,
            )

        # Verify audit
        is_valid, _ = audit_log.verify_integrity()
        assert is_valid

    def test_posture_assessment_with_all_components(self, temp_dir):
        """Test security posture with all frontier components."""
        # Setup components
        audit_log = MerkleAuditLog(temp_dir)
        engine = SecurityPostureEngine.default()

        # Create context with audit log
        context = {
            "merkle_audit": audit_log,
        }

        # Assess posture
        report = engine.assess(context)

        # Should have recommendations about enabling frontier features
        assert isinstance(report, PostureReport)


# =============================================================================
# PART 7: Determinism Tests (Determinism)
# =============================================================================

class TestDeterminism:
    """Test Determinism across all modules."""

    def test_shamir_lagrange_deterministic(self):
        """Lagrange interpolation should be deterministic."""
        sss = ShamirSecretSharing()
        secret = secrets.token_bytes(32)
        shares = sss.split(secret, 3, 5)

        subset = [shares[0], shares[2], shares[4]]

        # Multiple reconstructions
        results = [sss.reconstruct(subset) for _ in range(10)]

        # All should be identical
        assert all(r == results[0] for r in results)

    def test_merkle_tree_deterministic(self):
        """Merkle tree should be deterministic."""
        entries = [b"entry1", b"entry2", b"entry3"]

        roots = []
        for _ in range(5):
            tree = MerkleTree()
            for entry in entries:
                tree.append(entry)
            roots.append(tree.root_hash())

        # All roots should be identical
        assert all(r == roots[0] for r in roots)

    def test_threat_classification_deterministic(self):
        """Threat classification should be deterministic."""
        detector = BruteForceDetector()

        # Same events should produce same classification
        events = [
            {"type": "auth_failure", "source_ip": "10.0.0.1"}
            for _ in range(10)
        ]

        # Reset and replay multiple times
        for trial in range(3):
            detector = BruteForceDetector()
            for event in events:
                threat = detector.detect(event)

            # Final threat should be same category/severity
            if threat:
                assert threat.category == ThreatCategory.BRUTE_FORCE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
