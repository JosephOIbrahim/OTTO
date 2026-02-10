"""
Tests for Post-Quantum Cryptography Module
==========================================

Tests hybrid post-quantum key exchange including:
- X25519 KEM (classical)
- ML-KEM/Kyber (post-quantum, when available)
- Hybrid KEM combining both
- Key exchange protocol
- Serialization

Determinism Tests:
- Determinism: same keys → same shared secrets
- Fixed algorithms: no runtime switching
- HKDF key derivation with fixed parameters
"""

import pytest
from typing import Optional

from otto.crypto.pqcrypto import (
    # Core classes
    HybridKEM,
    HybridKeyExchange,
    X25519KEM,
    # Key types
    HybridKeyPair,
    HybridPublicKey,
    HybridPrivateKey,
    HybridCiphertext,
    KEMKeyPair,
    KEMPublicKey,
    KEMPrivateKey,
    KEMCiphertext,
    KEMAlgorithm,
    # Status
    PQSecurityStatus,
    is_pq_available,
    get_pq_status,
    # Convenience
    create_hybrid_kem,
    create_key_exchange,
    serialize_hybrid_public_key,
    deserialize_hybrid_public_key,
    # Constants
    X25519_PUBLIC_KEY_SIZE,
    X25519_PRIVATE_KEY_SIZE,
    DERIVED_KEY_SIZE,
)


# =============================================================================
# X25519 KEM Tests
# =============================================================================

class TestX25519KEM:
    """Tests for X25519 Key Encapsulation Mechanism."""

    def test_generate_keypair(self):
        """Can generate X25519 keypair."""
        kem = X25519KEM()
        keypair = kem.generate_keypair()

        assert keypair.algorithm == KEMAlgorithm.X25519
        assert len(keypair.public_key.key_bytes) == X25519_PUBLIC_KEY_SIZE
        assert len(keypair.private_key.key_bytes) == X25519_PRIVATE_KEY_SIZE

    def test_encapsulate_decapsulate(self):
        """Encapsulate and decapsulate produce same shared secret."""
        kem = X25519KEM()

        # Generate recipient keypair
        recipient = kem.generate_keypair()

        # Encapsulate for recipient
        ciphertext, sender_secret = kem.encapsulate(recipient.public_key)

        # Decapsulate by recipient
        recipient_secret = kem.decapsulate(ciphertext, recipient.private_key)

        assert sender_secret == recipient_secret
        assert len(sender_secret) == DERIVED_KEY_SIZE

    def test_different_recipients_different_secrets(self):
        """Different recipients get different shared secrets."""
        kem = X25519KEM()

        recipient1 = kem.generate_keypair()
        recipient2 = kem.generate_keypair()

        _, secret1 = kem.encapsulate(recipient1.public_key)
        _, secret2 = kem.encapsulate(recipient2.public_key)

        assert secret1 != secret2

    def test_different_encapsulations_different_secrets(self):
        """Each encapsulation produces a different shared secret."""
        kem = X25519KEM()
        recipient = kem.generate_keypair()

        _, secret1 = kem.encapsulate(recipient.public_key)
        _, secret2 = kem.encapsulate(recipient.public_key)

        # Different ephemeral keys → different secrets
        assert secret1 != secret2

    def test_keypair_uniqueness(self):
        """Each keypair is unique."""
        kem = X25519KEM()

        kp1 = kem.generate_keypair()
        kp2 = kem.generate_keypair()

        assert kp1.public_key.key_bytes != kp2.public_key.key_bytes
        assert kp1.private_key.key_bytes != kp2.private_key.key_bytes

    def test_ciphertext_contains_ephemeral_public(self):
        """Ciphertext contains ephemeral public key."""
        kem = X25519KEM()
        recipient = kem.generate_keypair()

        ciphertext, _ = kem.encapsulate(recipient.public_key)

        assert ciphertext.algorithm == KEMAlgorithm.X25519
        assert len(ciphertext.ciphertext_bytes) == X25519_PUBLIC_KEY_SIZE


# =============================================================================
# Hybrid KEM Tests
# =============================================================================

class TestHybridKEM:
    """Tests for Hybrid KEM (X25519 + ML-KEM-768)."""

    def test_create_hybrid_kem(self):
        """Can create hybrid KEM."""
        kem = HybridKEM()

        assert kem is not None
        # Should always have classical
        status = kem.security_status
        assert status.classical_algorithm == "X25519"

    def test_generate_keypair(self):
        """Can generate hybrid keypair."""
        kem = HybridKEM()
        keypair = kem.generate_keypair()

        assert keypair.public_key.classical is not None
        assert keypair.private_key.classical is not None
        assert len(keypair.public_key.classical.key_bytes) == X25519_PUBLIC_KEY_SIZE

    def test_encapsulate_decapsulate(self):
        """Hybrid encapsulate/decapsulate works."""
        kem = HybridKEM()

        recipient = kem.generate_keypair()
        ciphertext, sender_secret = kem.encapsulate(recipient.public_key)
        recipient_secret = kem.decapsulate(ciphertext, recipient.private_key)

        assert sender_secret == recipient_secret
        assert len(sender_secret) == DERIVED_KEY_SIZE

    def test_security_status(self):
        """Security status is accurate."""
        kem = HybridKEM()
        status = kem.security_status

        assert status.classical_algorithm == "X25519"
        assert status.hybrid_mode == kem.is_pq_enabled

        if kem.is_pq_enabled:
            assert status.security_level == "hybrid-pq"
            assert status.algorithm == "ML-KEM-768"
        else:
            assert status.security_level == "classical-only"

    def test_100_key_exchanges(self):
        """100 key exchanges all succeed."""
        kem = HybridKEM()

        for _ in range(100):
            recipient = kem.generate_keypair()
            ct, sender_ss = kem.encapsulate(recipient.public_key)
            recipient_ss = kem.decapsulate(ct, recipient.private_key)
            assert sender_ss == recipient_ss


class TestHybridKEMWithPQ:
    """Tests for Hybrid KEM when PQ is available."""

    @pytest.mark.skipif(not is_pq_available(), reason="liboqs not installed")
    def test_pq_enabled(self):
        """PQ algorithms are enabled."""
        kem = HybridKEM()

        assert kem.is_pq_enabled is True
        assert kem.security_status.pq_available is True

    @pytest.mark.skipif(not is_pq_available(), reason="liboqs not installed")
    def test_keypair_has_pq_component(self):
        """Keypair includes PQ component."""
        kem = HybridKEM()
        keypair = kem.generate_keypair()

        assert keypair.public_key.post_quantum is not None
        assert keypair.private_key.post_quantum is not None

    @pytest.mark.skipif(not is_pq_available(), reason="liboqs not installed")
    def test_ciphertext_has_pq_component(self):
        """Ciphertext includes PQ component."""
        kem = HybridKEM()
        recipient = kem.generate_keypair()

        ciphertext, _ = kem.encapsulate(recipient.public_key)

        assert ciphertext.post_quantum is not None


class TestHybridKEMWithoutPQ:
    """Tests for Hybrid KEM graceful degradation."""

    def test_works_without_pq(self):
        """Key exchange works even without PQ."""
        kem = HybridKEM()

        # Should work regardless of PQ availability
        recipient = kem.generate_keypair()
        ct, sender_ss = kem.encapsulate(recipient.public_key)
        recipient_ss = kem.decapsulate(ct, recipient.private_key)

        assert sender_ss == recipient_ss

    def test_classical_always_present(self):
        """Classical component is always present."""
        kem = HybridKEM()
        keypair = kem.generate_keypair()

        assert keypair.public_key.classical is not None
        assert keypair.private_key.classical is not None


# =============================================================================
# Key Exchange Protocol Tests
# =============================================================================

class TestHybridKeyExchange:
    """Tests for high-level key exchange protocol."""

    def test_create_key_exchange(self):
        """Can create key exchange instance."""
        kex = HybridKeyExchange()
        assert kex is not None

    def test_full_key_exchange(self):
        """Full key exchange between two parties."""
        kex = HybridKeyExchange()

        # Alice and Bob generate keypairs
        alice = kex.generate_keypair()
        bob = kex.generate_keypair()

        # Alice encapsulates for Bob
        ct_to_bob, alice_secret = kex.encapsulate(bob.public_key)

        # Bob decapsulates
        bob_secret = kex.decapsulate(ct_to_bob, bob.private_key)

        # They have the same secret
        assert alice_secret == bob_secret

    def test_bidirectional_key_exchange(self):
        """Bidirectional key exchange."""
        kex = HybridKeyExchange()

        alice = kex.generate_keypair()
        bob = kex.generate_keypair()

        # Alice → Bob
        ct1, secret1_alice = kex.encapsulate(bob.public_key)
        secret1_bob = kex.decapsulate(ct1, bob.private_key)

        # Bob → Alice
        ct2, secret2_bob = kex.encapsulate(alice.public_key)
        secret2_alice = kex.decapsulate(ct2, alice.private_key)

        assert secret1_alice == secret1_bob
        assert secret2_alice == secret2_bob
        # But different directions produce different secrets
        assert secret1_alice != secret2_alice

    def test_derive_session_keys(self):
        """Can derive multiple session keys."""
        kex = HybridKeyExchange()

        alice = kex.generate_keypair()
        bob = kex.generate_keypair()

        ct, shared_secret = kex.encapsulate(bob.public_key)
        bob_secret = kex.decapsulate(ct, bob.private_key)

        # Alice derives keys
        alice_keys = kex.derive_session_keys(shared_secret, num_keys=3)

        # Bob derives keys
        bob_keys = kex.derive_session_keys(bob_secret, num_keys=3)

        # Same shared secret → same derived keys
        assert alice_keys == bob_keys
        assert len(alice_keys) == 3
        assert all(len(k) == 32 for k in alice_keys)

    def test_derive_session_keys_with_context(self):
        """Context affects derived keys."""
        kex = HybridKeyExchange()

        alice = kex.generate_keypair()
        bob = kex.generate_keypair()

        _, shared_secret = kex.encapsulate(bob.public_key)

        keys1 = kex.derive_session_keys(shared_secret, context=b"context1")
        keys2 = kex.derive_session_keys(shared_secret, context=b"context2")

        # Different context → different keys
        assert keys1 != keys2

    def test_security_status(self):
        """Security status accessible from key exchange."""
        kex = HybridKeyExchange()
        status = kex.security_status

        assert status is not None
        assert status.classical_algorithm == "X25519"


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerialization:
    """Tests for key serialization."""

    def test_serialize_public_key(self):
        """Can serialize hybrid public key."""
        kem = HybridKEM()
        keypair = kem.generate_keypair()

        serialized = serialize_hybrid_public_key(keypair.public_key)

        assert isinstance(serialized, bytes)
        assert len(serialized) > 0

    def test_deserialize_public_key(self):
        """Can deserialize hybrid public key."""
        kem = HybridKEM()
        keypair = kem.generate_keypair()

        serialized = serialize_hybrid_public_key(keypair.public_key)
        deserialized = deserialize_hybrid_public_key(serialized)

        assert deserialized.classical.key_bytes == keypair.public_key.classical.key_bytes

    def test_serialize_deserialize_roundtrip(self):
        """Serialize/deserialize roundtrip works."""
        kem = HybridKEM()
        original = kem.generate_keypair()

        serialized = serialize_hybrid_public_key(original.public_key)
        restored = deserialize_hybrid_public_key(serialized)

        # Can use restored key for encapsulation
        ct, sender_ss = kem.encapsulate(restored)
        recipient_ss = kem.decapsulate(ct, original.private_key)

        assert sender_ss == recipient_ss

    def test_ciphertext_serialization(self):
        """Ciphertext can be serialized."""
        kem = HybridKEM()
        recipient = kem.generate_keypair()

        ciphertext, _ = kem.encapsulate(recipient.public_key)
        serialized = ciphertext.to_bytes()

        assert isinstance(serialized, bytes)
        assert len(serialized) > 0


# =============================================================================
# Data Class Tests
# =============================================================================

class TestDataClasses:
    """Tests for data class properties."""

    def test_kem_public_key_frozen(self):
        """KEMPublicKey is immutable."""
        key = KEMPublicKey(KEMAlgorithm.X25519, b"test")

        with pytest.raises(Exception):
            key.key_bytes = b"modified"

    def test_kem_keypair_frozen(self):
        """KEMKeyPair is immutable."""
        kem = X25519KEM()
        keypair = kem.generate_keypair()

        with pytest.raises(Exception):
            keypair.algorithm = KEMAlgorithm.MLKEM768

    def test_public_key_hex(self):
        """Public key has hex representation."""
        kem = X25519KEM()
        keypair = kem.generate_keypair()

        hex_str = keypair.public_key.hex()

        assert isinstance(hex_str, str)
        assert len(hex_str) == X25519_PUBLIC_KEY_SIZE * 2

    def test_public_key_len(self):
        """Public key has length."""
        kem = X25519KEM()
        keypair = kem.generate_keypair()

        assert len(keypair.public_key) == X25519_PUBLIC_KEY_SIZE

    def test_security_status_to_dict(self):
        """Security status can be converted to dict."""
        status = get_pq_status()
        d = status.to_dict()

        assert 'pq_available' in d
        assert 'classical_algorithm' in d
        assert 'security_level' in d


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_is_pq_available(self):
        """is_pq_available returns boolean."""
        result = is_pq_available()
        assert isinstance(result, bool)

    def test_get_pq_status(self):
        """get_pq_status returns status object."""
        status = get_pq_status()

        assert isinstance(status, PQSecurityStatus)
        assert status.classical_algorithm == "X25519"

    def test_create_hybrid_kem(self):
        """create_hybrid_kem returns HybridKEM."""
        kem = create_hybrid_kem()
        assert isinstance(kem, HybridKEM)

    def test_create_key_exchange(self):
        """create_key_exchange returns HybridKeyExchange."""
        kex = create_key_exchange()
        assert isinstance(kex, HybridKeyExchange)


# =============================================================================
# Algorithm Enum Tests
# =============================================================================

class TestKEMAlgorithm:
    """Tests for KEMAlgorithm enum."""

    def test_all_algorithms(self):
        """All algorithms have values."""
        assert KEMAlgorithm.X25519.value == "x25519"
        assert KEMAlgorithm.MLKEM512.value == "ML-KEM-512"
        assert KEMAlgorithm.MLKEM768.value == "ML-KEM-768"
        assert KEMAlgorithm.MLKEM1024.value == "ML-KEM-1024"
        assert KEMAlgorithm.HYBRID_X25519_MLKEM768.value == "hybrid-x25519-mlkem768"


# =============================================================================
# Determinism Tests (Determinism)
# =============================================================================

class TestDeterminism:
    """Tests for Determinism."""

    def test_same_keypair_same_decapsulation(self):
        """Same ciphertext + private key → same shared secret."""
        kem = HybridKEM()

        recipient = kem.generate_keypair()
        ct, _ = kem.encapsulate(recipient.public_key)

        # Decapsulate multiple times
        secrets = [
            kem.decapsulate(ct, recipient.private_key)
            for _ in range(100)
        ]

        # All should be identical
        assert len(set(secrets)) == 1

    def test_key_derivation_deterministic(self):
        """Key derivation is deterministic."""
        kex = HybridKeyExchange()

        shared_secret = b"test_secret_32_bytes_exactly!!"

        keys1 = kex.derive_session_keys(shared_secret, context=b"test")
        keys2 = kex.derive_session_keys(shared_secret, context=b"test")

        assert keys1 == keys2

    def test_fixed_hkdf_parameters(self):
        """HKDF uses fixed parameters."""
        # This is implicit in the implementation, but we verify
        # by checking that key derivation is deterministic
        kex = HybridKeyExchange()

        secret = b"x" * 32

        # Derive keys multiple times
        results = [
            kex.derive_session_keys(secret, context=b"fixed")
            for _ in range(50)
        ]

        # All should be identical
        assert all(r == results[0] for r in results)


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_context(self):
        """Empty context works."""
        kex = HybridKeyExchange()
        secret = b"x" * 32

        keys = kex.derive_session_keys(secret, context=b"")
        assert len(keys) == 2

    def test_single_key_derivation(self):
        """Can derive single key."""
        kex = HybridKeyExchange()
        secret = b"x" * 32

        keys = kex.derive_session_keys(secret, num_keys=1)
        assert len(keys) == 1

    def test_many_keys_derivation(self):
        """Can derive many keys."""
        kex = HybridKeyExchange()
        secret = b"x" * 32

        keys = kex.derive_session_keys(secret, num_keys=10)
        assert len(keys) == 10

        # All keys should be unique
        assert len(set(keys)) == 10

    def test_custom_key_size(self):
        """Can derive custom size keys."""
        kex = HybridKeyExchange()
        secret = b"x" * 32

        keys = kex.derive_session_keys(secret, num_keys=2, key_size=64)
        assert all(len(k) == 64 for k in keys)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for full workflows."""

    def test_multi_party_key_exchange(self):
        """Key exchange with multiple parties."""
        kex = HybridKeyExchange()

        # Three parties
        alice = kex.generate_keypair()
        bob = kex.generate_keypair()
        charlie = kex.generate_keypair()

        # Alice establishes keys with Bob and Charlie
        ct_ab, secret_ab_alice = kex.encapsulate(bob.public_key)
        ct_ac, secret_ac_alice = kex.encapsulate(charlie.public_key)

        # Bob and Charlie recover their shared secrets
        secret_ab_bob = kex.decapsulate(ct_ab, bob.private_key)
        secret_ac_charlie = kex.decapsulate(ct_ac, charlie.private_key)

        # Verify pairwise secrets match
        assert secret_ab_alice == secret_ab_bob
        assert secret_ac_alice == secret_ac_charlie

        # But different pairs have different secrets
        assert secret_ab_alice != secret_ac_alice

    def test_key_exchange_with_serialization(self):
        """Key exchange with serialized public keys."""
        kex = HybridKeyExchange()

        # Alice generates keypair and serializes public key
        alice = kex.generate_keypair()
        alice_public_bytes = serialize_hybrid_public_key(alice.public_key)

        # Bob receives serialized key and uses it
        alice_public_restored = deserialize_hybrid_public_key(alice_public_bytes)
        ct, bob_secret = kex.encapsulate(alice_public_restored)

        # Alice decapsulates
        alice_secret = kex.decapsulate(ct, alice.private_key)

        assert alice_secret == bob_secret

    def test_session_key_usage(self):
        """Derived session keys are suitable for use."""
        kex = HybridKeyExchange()

        alice = kex.generate_keypair()
        bob = kex.generate_keypair()

        # Establish shared secret
        ct, shared_secret = kex.encapsulate(bob.public_key)
        bob_secret = kex.decapsulate(ct, bob.private_key)

        # Derive encryption and MAC keys
        alice_keys = kex.derive_session_keys(
            shared_secret,
            context=b"alice-bob-session-1",
            num_keys=2,
        )
        bob_keys = kex.derive_session_keys(
            bob_secret,
            context=b"alice-bob-session-1",
            num_keys=2,
        )

        # Keys match and are suitable for crypto
        assert alice_keys == bob_keys
        assert len(alice_keys[0]) == 32  # AES-256 key
        assert len(alice_keys[1]) == 32  # HMAC key
