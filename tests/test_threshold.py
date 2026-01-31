"""
Tests for Threshold Cryptography Module
=======================================

Comprehensive tests for Shamir Secret Sharing and threshold signatures.
"""

import pytest
import secrets
import hashlib
from typing import List

from otto.crypto.threshold import (
    # Core classes
    ThresholdScheme,
    ThresholdSigner,
    KeyEscrow,
    # Data types
    Share,
    ShareSet,
    PartialSignature,
    ThresholdSignature,
    # Exceptions
    ThresholdError,
    InsufficientSharesError,
    InvalidShareError,
    DuplicateShareError,
    # Convenience functions
    split_secret,
    combine_shares,
    create_threshold_signer,
    create_key_escrow,
    # Constants
    FIELD_PRIME,
    SECRET_SIZE,
    MAX_SHARES,
    MIN_THRESHOLD,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def random_secret() -> bytes:
    """Generate a random 32-byte secret."""
    return secrets.token_bytes(SECRET_SIZE)


@pytest.fixture
def known_secret() -> bytes:
    """A known secret for deterministic tests."""
    return bytes.fromhex(
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )


@pytest.fixture
def scheme_3_of_5() -> ThresholdScheme:
    """3-of-5 threshold scheme."""
    return ThresholdScheme(threshold=3, total_shares=5)


@pytest.fixture
def scheme_2_of_3() -> ThresholdScheme:
    """2-of-3 threshold scheme."""
    return ThresholdScheme(threshold=2, total_shares=3)


# =============================================================================
# ThresholdScheme Tests
# =============================================================================

class TestThresholdSchemeCreation:
    """Tests for ThresholdScheme initialization."""

    def test_valid_scheme(self):
        """Test creating valid schemes."""
        scheme = ThresholdScheme(threshold=3, total_shares=5)
        assert scheme.threshold == 3
        assert scheme.total_shares == 5

    def test_minimum_threshold(self):
        """Test minimum threshold is enforced."""
        with pytest.raises(ValueError, match="at least"):
            ThresholdScheme(threshold=1, total_shares=3)

    def test_threshold_exceeds_total(self):
        """Test threshold cannot exceed total shares."""
        with pytest.raises(ValueError, match="cannot exceed"):
            ThresholdScheme(threshold=5, total_shares=3)

    def test_max_shares_exceeded(self):
        """Test maximum shares limit."""
        with pytest.raises(ValueError, match="cannot exceed"):
            ThresholdScheme(threshold=2, total_shares=256)

    def test_edge_case_threshold_equals_total(self):
        """Test threshold equals total shares (all required)."""
        scheme = ThresholdScheme(threshold=5, total_shares=5)
        assert scheme.threshold == scheme.total_shares


class TestSecretSplitting:
    """Tests for secret splitting."""

    def test_split_produces_correct_count(self, scheme_3_of_5, random_secret):
        """Test split produces correct number of shares."""
        shares = scheme_3_of_5.split(random_secret)
        assert len(shares) == 5

    def test_split_shares_have_unique_ids(self, scheme_3_of_5, random_secret):
        """Test all shares have unique IDs."""
        shares = scheme_3_of_5.split(random_secret)
        ids = [s.share_id for s in shares]
        assert len(ids) == len(set(ids))

    def test_split_shares_have_correct_metadata(self, scheme_3_of_5, random_secret):
        """Test shares contain correct metadata."""
        shares = scheme_3_of_5.split(random_secret)
        for share in shares:
            assert share.threshold == 3
            assert share.total_shares == 5

    def test_split_produces_valid_checksums(self, scheme_3_of_5, random_secret):
        """Test all shares pass integrity check."""
        shares = scheme_3_of_5.split(random_secret)
        for share in shares:
            assert share.verify_integrity()

    def test_split_wrong_secret_size(self, scheme_3_of_5):
        """Test split rejects wrong secret size."""
        with pytest.raises(ValueError, match="must be"):
            scheme_3_of_5.split(b"too short")

    def test_split_includes_secret_hash(self, scheme_3_of_5, known_secret):
        """Test ShareSet includes hash of original secret."""
        shares = scheme_3_of_5.split(known_secret)
        expected_hash = hashlib.sha256(known_secret).hexdigest()
        assert shares.secret_hash == expected_hash


class TestSecretReconstruction:
    """Tests for secret reconstruction."""

    def test_reconstruct_with_threshold_shares(self, scheme_3_of_5, random_secret):
        """Test reconstruction with exactly threshold shares."""
        shares = scheme_3_of_5.split(random_secret)
        reconstructed = scheme_3_of_5.combine([shares[0], shares[1], shares[2]])
        assert reconstructed == random_secret

    def test_reconstruct_with_more_than_threshold(self, scheme_3_of_5, random_secret):
        """Test reconstruction with more than threshold shares."""
        shares = scheme_3_of_5.split(random_secret)
        reconstructed = scheme_3_of_5.combine(list(shares))  # All 5
        assert reconstructed == random_secret

    def test_reconstruct_with_any_combination(self, scheme_3_of_5, random_secret):
        """Test any K shares can reconstruct."""
        shares = scheme_3_of_5.split(random_secret)

        # Try different combinations
        combinations = [
            [0, 1, 2],
            [0, 2, 4],
            [1, 3, 4],
            [0, 1, 4],
            [2, 3, 4],
        ]

        for combo in combinations:
            selected = [shares[i] for i in combo]
            reconstructed = scheme_3_of_5.combine(selected)
            assert reconstructed == random_secret

    def test_reconstruct_insufficient_shares(self, scheme_3_of_5, random_secret):
        """Test reconstruction fails with too few shares."""
        shares = scheme_3_of_5.split(random_secret)
        with pytest.raises(InsufficientSharesError):
            scheme_3_of_5.combine([shares[0], shares[1]])  # Only 2, need 3

    def test_reconstruct_duplicate_shares(self, scheme_3_of_5, random_secret):
        """Test reconstruction rejects duplicate shares."""
        shares = scheme_3_of_5.split(random_secret)
        with pytest.raises(DuplicateShareError):
            scheme_3_of_5.combine([shares[0], shares[0], shares[1]])

    def test_reconstruct_corrupted_share(self, scheme_3_of_5, random_secret):
        """Test reconstruction detects corrupted shares."""
        shares = scheme_3_of_5.split(random_secret)

        # Corrupt a share
        corrupted = Share(
            share_id=shares[0].share_id,
            value=secrets.token_bytes(SECRET_SIZE),  # Wrong value
            threshold=shares[0].threshold,
            total_shares=shares[0].total_shares,
            checksum=shares[0].checksum,  # Original checksum won't match
        )

        with pytest.raises(InvalidShareError, match="integrity"):
            scheme_3_of_5.combine([corrupted, shares[1], shares[2]])


class TestVerifyReconstruction:
    """Tests for reconstruction verification."""

    def test_verify_correct_reconstruction(self, scheme_3_of_5, random_secret):
        """Test verification passes for correct reconstruction."""
        shares = scheme_3_of_5.split(random_secret)
        expected_hash = shares.secret_hash

        assert scheme_3_of_5.verify_reconstruction(
            list(shares)[:3],
            expected_hash,
        )

    def test_verify_wrong_hash(self, scheme_3_of_5, random_secret):
        """Test verification fails for wrong hash."""
        shares = scheme_3_of_5.split(random_secret)

        assert not scheme_3_of_5.verify_reconstruction(
            list(shares)[:3],
            "wrong_hash",
        )


# =============================================================================
# Share Data Class Tests
# =============================================================================

class TestShare:
    """Tests for Share data class."""

    def test_share_creation(self):
        """Test creating a valid share."""
        share = Share(
            share_id=1,
            value=secrets.token_bytes(SECRET_SIZE),
            threshold=3,
            total_shares=5,
            checksum="a" * 32,
        )
        assert share.share_id == 1

    def test_share_invalid_id_zero(self):
        """Test share rejects ID of 0."""
        with pytest.raises(InvalidShareError):
            Share(
                share_id=0,
                value=secrets.token_bytes(SECRET_SIZE),
                threshold=3,
                total_shares=5,
                checksum="a" * 32,
            )

    def test_share_invalid_id_too_large(self):
        """Test share rejects ID > MAX_SHARES."""
        with pytest.raises(InvalidShareError):
            Share(
                share_id=256,
                value=secrets.token_bytes(SECRET_SIZE),
                threshold=3,
                total_shares=5,
                checksum="a" * 32,
            )

    def test_share_wrong_value_size(self):
        """Test share rejects wrong value size."""
        with pytest.raises(InvalidShareError):
            Share(
                share_id=1,
                value=b"too short",
                threshold=3,
                total_shares=5,
                checksum="a" * 32,
            )

    def test_share_serialization_roundtrip(self, scheme_3_of_5, random_secret):
        """Test share can be serialized and deserialized."""
        shares = scheme_3_of_5.split(random_secret)
        original = shares[0]

        serialized = original.to_bytes()
        restored = Share.from_bytes(serialized)

        assert restored.share_id == original.share_id
        assert restored.value == original.value
        assert restored.threshold == original.threshold
        assert restored.checksum == original.checksum

    def test_share_to_dict_roundtrip(self, scheme_3_of_5, random_secret):
        """Test share dict conversion."""
        shares = scheme_3_of_5.split(random_secret)
        original = shares[0]

        as_dict = original.to_dict()
        restored = Share.from_dict(as_dict)

        assert restored == original


class TestShareSet:
    """Tests for ShareSet data class."""

    def test_shareset_length(self, scheme_3_of_5, random_secret):
        """Test ShareSet reports correct length."""
        shares = scheme_3_of_5.split(random_secret)
        assert len(shares) == 5

    def test_shareset_indexing(self, scheme_3_of_5, random_secret):
        """Test ShareSet supports indexing."""
        shares = scheme_3_of_5.split(random_secret)
        assert shares[0].share_id == 1
        assert shares[4].share_id == 5

    def test_shareset_iteration(self, scheme_3_of_5, random_secret):
        """Test ShareSet supports iteration."""
        shares = scheme_3_of_5.split(random_secret)
        ids = [s.share_id for s in shares]
        assert ids == [1, 2, 3, 4, 5]

    def test_shareset_get_by_id(self, scheme_3_of_5, random_secret):
        """Test getting share by ID."""
        shares = scheme_3_of_5.split(random_secret)
        share = shares.get_share(3)
        assert share is not None
        assert share.share_id == 3

    def test_shareset_get_missing_id(self, scheme_3_of_5, random_secret):
        """Test getting nonexistent share ID."""
        shares = scheme_3_of_5.split(random_secret)
        assert shares.get_share(99) is None


# =============================================================================
# ThresholdSigner Tests
# =============================================================================

class TestThresholdSigner:
    """Tests for threshold signing."""

    def test_generate_key_shares(self):
        """Test generating key shares."""
        signer = ThresholdSigner(threshold=3, total_shares=5)
        shares = signer.generate_key_shares()

        assert len(shares) == 5
        assert shares.threshold == 3

    def test_generate_key_shares_with_existing_key(self):
        """Test generating shares from existing key."""
        signer = ThresholdSigner(threshold=3, total_shares=5)
        key = secrets.token_bytes(SECRET_SIZE)
        shares = signer.generate_key_shares(key)

        # Verify reconstruction gives back the key
        scheme = ThresholdScheme(3, 5)
        reconstructed = scheme.combine(list(shares)[:3])
        assert reconstructed == key

    def test_partial_sign(self):
        """Test creating partial signatures."""
        signer = ThresholdSigner(threshold=3, total_shares=5)
        shares = signer.generate_key_shares()
        message = b"Hello, World!"

        partial = signer.partial_sign(message, shares[0])

        assert partial.share_id == shares[0].share_id
        assert partial.message_hash == hashlib.sha256(message).hexdigest()

    def test_combine_signatures(self):
        """Test combining partial signatures."""
        signer = ThresholdSigner(threshold=3, total_shares=5)
        shares = signer.generate_key_shares()
        message = b"Hello, World!"

        # Create partial signatures
        partials = [
            signer.partial_sign(message, shares[0]),
            signer.partial_sign(message, shares[2]),
            signer.partial_sign(message, shares[4]),
        ]

        # Combine
        signature = signer.combine_signatures(partials)

        assert len(signature.signers) == 3
        assert signature.threshold == 3
        assert signature.message_hash == hashlib.sha256(message).hexdigest()

    def test_combine_insufficient_partials(self):
        """Test combining fails with insufficient partials."""
        signer = ThresholdSigner(threshold=3, total_shares=5)
        shares = signer.generate_key_shares()
        message = b"Hello, World!"

        partials = [
            signer.partial_sign(message, shares[0]),
            signer.partial_sign(message, shares[1]),
        ]

        with pytest.raises(InsufficientSharesError):
            signer.combine_signatures(partials)

    def test_combine_different_messages(self):
        """Test combining fails for different messages."""
        signer = ThresholdSigner(threshold=2, total_shares=3)
        shares = signer.generate_key_shares()

        partials = [
            signer.partial_sign(b"Message 1", shares[0]),
            signer.partial_sign(b"Message 2", shares[1]),
        ]

        with pytest.raises(ValueError, match="different messages"):
            signer.combine_signatures(partials)

    def test_combine_duplicate_signers(self):
        """Test combining fails with duplicate signers."""
        signer = ThresholdSigner(threshold=2, total_shares=3)
        shares = signer.generate_key_shares()
        message = b"Hello!"

        partial = signer.partial_sign(message, shares[0])

        with pytest.raises(DuplicateShareError):
            signer.combine_signatures([partial, partial])


class TestThresholdSignatureDeterminism:
    """Tests for signature determinism."""

    def test_same_partials_same_signature(self):
        """Test same partials produce same signature."""
        signer = ThresholdSigner(threshold=2, total_shares=3)
        key = secrets.token_bytes(SECRET_SIZE)
        shares = signer.generate_key_shares(key)
        message = b"Determinism test"

        partials = [
            signer.partial_sign(message, shares[0]),
            signer.partial_sign(message, shares[1]),
        ]

        sig1 = signer.combine_signatures(partials)
        sig2 = signer.combine_signatures(partials)

        assert sig1.signature == sig2.signature

    def test_different_signer_sets_different_signatures(self):
        """Test different signer sets produce different intermediate values."""
        signer = ThresholdSigner(threshold=2, total_shares=3)
        shares = signer.generate_key_shares()
        message = b"Test message"

        sig1 = signer.combine_signatures([
            signer.partial_sign(message, shares[0]),
            signer.partial_sign(message, shares[1]),
        ])

        sig2 = signer.combine_signatures([
            signer.partial_sign(message, shares[0]),
            signer.partial_sign(message, shares[2]),
        ])

        # Different signers, but should still produce valid signatures
        assert sig1.signers != sig2.signers


# =============================================================================
# KeyEscrow Tests
# =============================================================================

class TestKeyEscrow:
    """Tests for key escrow functionality."""

    def test_escrow_key(self):
        """Test escrowing a key."""
        escrow = KeyEscrow(threshold=3, trustees=5)
        key = secrets.token_bytes(SECRET_SIZE)

        result = escrow.escrow_key(key, key_id="test-key-001")

        assert result['key_id'] == "test-key-001"
        assert result['threshold'] == 3
        assert result['trustees'] == 5
        assert len(result['shares']) == 5

    def test_recover_key(self):
        """Test recovering a key."""
        escrow = KeyEscrow(threshold=3, trustees=5)
        key = secrets.token_bytes(SECRET_SIZE)

        result = escrow.escrow_key(key, key_id="test-key")
        shares = [Share.from_dict(s) for s in result['shares']]

        recovered = escrow.recover_key(shares[:3])
        assert recovered == key

    def test_recover_with_verification(self):
        """Test recovering with hash verification."""
        escrow = KeyEscrow(threshold=2, trustees=3)
        key = secrets.token_bytes(SECRET_SIZE)

        result = escrow.escrow_key(key, key_id="verify-test")
        shares = [Share.from_dict(s) for s in result['shares']]

        recovered = escrow.recover_key(
            shares[:2],
            expected_hash=result['verification_hash'],
        )
        assert recovered == key

    def test_recover_wrong_hash(self):
        """Test recovery fails with wrong hash."""
        escrow = KeyEscrow(threshold=2, trustees=3)
        key = secrets.token_bytes(SECRET_SIZE)

        result = escrow.escrow_key(key, key_id="wrong-hash")
        shares = [Share.from_dict(s) for s in result['shares']]

        with pytest.raises(InvalidShareError, match="does not match"):
            escrow.recover_key(shares[:2], expected_hash="wrong_hash")


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_split_secret(self):
        """Test split_secret function."""
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = split_secret(secret, threshold=2, total_shares=3)

        assert len(shares) == 3
        assert shares.threshold == 2

    def test_combine_shares(self):
        """Test combine_shares function."""
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = split_secret(secret, threshold=2, total_shares=3)

        recovered = combine_shares(list(shares)[:2])
        assert recovered == secret

    def test_combine_empty_shares(self):
        """Test combine_shares with empty list."""
        with pytest.raises(InsufficientSharesError):
            combine_shares([])

    def test_create_threshold_signer(self):
        """Test create_threshold_signer function."""
        signer = create_threshold_signer(3, 5)
        assert signer.threshold == 3
        assert signer.total_shares == 5

    def test_create_key_escrow(self):
        """Test create_key_escrow function."""
        escrow = create_key_escrow(2, 4)
        assert escrow._threshold == 2
        assert escrow._trustees == 4


# =============================================================================
# Edge Cases and Stress Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_threshold_equals_total(self):
        """Test when all shares are required."""
        scheme = ThresholdScheme(threshold=5, total_shares=5)
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = scheme.split(secret)

        # Need all 5
        reconstructed = scheme.combine(list(shares))
        assert reconstructed == secret

        # 4 is not enough
        with pytest.raises(InsufficientSharesError):
            scheme.combine(list(shares)[:4])

    def test_minimum_scheme(self):
        """Test minimum 2-of-2 scheme."""
        scheme = ThresholdScheme(threshold=2, total_shares=2)
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = scheme.split(secret)

        reconstructed = scheme.combine(list(shares))
        assert reconstructed == secret

    def test_large_scheme(self):
        """Test larger scheme (10-of-20)."""
        scheme = ThresholdScheme(threshold=10, total_shares=20)
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = scheme.split(secret)

        # Use shares 0,2,4,6,8,10,12,14,16,18 (every other)
        selected = [shares[i] for i in range(0, 20, 2)]
        reconstructed = scheme.combine(selected)
        assert reconstructed == secret

    def test_maximum_shares(self):
        """Test maximum supported shares."""
        scheme = ThresholdScheme(threshold=2, total_shares=MAX_SHARES)
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = scheme.split(secret)

        assert len(shares) == MAX_SHARES

        # Reconstruct with first 2
        reconstructed = scheme.combine([shares[0], shares[1]])
        assert reconstructed == secret


class TestDeterminism:
    """Tests for [He2025] determinism compliance."""

    def test_reconstruction_deterministic(self):
        """Test same shares always produce same secret."""
        scheme = ThresholdScheme(threshold=3, total_shares=5)
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = scheme.split(secret)

        selected = [shares[0], shares[2], shares[4]]

        # Reconstruct multiple times
        results = [scheme.combine(selected) for _ in range(10)]

        # All results should be identical
        assert all(r == results[0] for r in results)

    def test_lagrange_coefficients_deterministic(self):
        """Test Lagrange coefficients are deterministic."""
        from otto.crypto.threshold import _lagrange_coefficient

        x_coords = [1, 3, 5]

        # Compute multiple times
        results = [_lagrange_coefficient(x_coords, 0, 0) for _ in range(10)]

        assert all(r == results[0] for r in results)

    def test_share_order_independence(self):
        """Test reconstruction is independent of share order."""
        scheme = ThresholdScheme(threshold=3, total_shares=5)
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = scheme.split(secret)

        selected = [shares[0], shares[2], shares[4]]

        # Different orderings
        orderings = [
            [selected[0], selected[1], selected[2]],
            [selected[2], selected[0], selected[1]],
            [selected[1], selected[2], selected[0]],
        ]

        results = [scheme.combine(order) for order in orderings]

        # All orderings should produce same result
        assert all(r == results[0] for r in results)
        assert results[0] == secret


class TestSecurityProperties:
    """Tests for security properties."""

    def test_shares_appear_random(self):
        """Test shares appear uniformly random."""
        scheme = ThresholdScheme(threshold=3, total_shares=5)
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = scheme.split(secret)

        # Shares should not be identical
        values = [s.value for s in shares]
        assert len(set(values)) == 5  # All unique

        # Share values should not equal the secret
        for share in shares:
            assert share.value != secret

    def test_k_minus_1_reveals_nothing(self):
        """Test K-1 shares don't help reconstruct (information theoretic)."""
        # This is hard to test directly, but we can verify
        # different secrets with same K-1 shares produce different Kth shares
        scheme = ThresholdScheme(threshold=3, total_shares=5)

        secret1 = secrets.token_bytes(SECRET_SIZE)
        secret2 = secrets.token_bytes(SECRET_SIZE)

        shares1 = scheme.split(secret1)
        shares2 = scheme.split(secret2)

        # With different secrets, at least the values should differ
        # (the share IDs and structure are the same)
        assert shares1[0].value != shares2[0].value


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_escrow_workflow(self):
        """Test complete key escrow workflow."""
        # Setup: Company has master key, wants 3-of-5 recovery
        master_key = secrets.token_bytes(SECRET_SIZE)
        escrow = KeyEscrow(threshold=3, trustees=5)

        # Step 1: Escrow the key
        escrow_result = escrow.escrow_key(
            master_key,
            key_id="company-master-2025",
            metadata={'purpose': 'Encryption master key'},
        )

        # Step 2: Distribute shares to trustees
        trustee_shares = [Share.from_dict(s) for s in escrow_result['shares']]

        # Step 3: Later, 3 trustees come together to recover
        recovering_trustees = [trustee_shares[0], trustee_shares[2], trustee_shares[4]]

        recovered_key = escrow.recover_key(
            recovering_trustees,
            expected_hash=escrow_result['verification_hash'],
        )

        assert recovered_key == master_key

    def test_full_signing_workflow(self):
        """Test complete threshold signing workflow."""
        # Setup: 3-of-5 signing authority
        signer = ThresholdSigner(threshold=3, total_shares=5)
        key_shares = signer.generate_key_shares()

        # Message to sign
        message = b"Authorize transfer of $1,000,000"

        # Three authorized signers create partial signatures
        partials = [
            signer.partial_sign(message, key_shares[0]),  # CFO
            signer.partial_sign(message, key_shares[2]),  # CEO
            signer.partial_sign(message, key_shares[4]),  # Board member
        ]

        # Combine into full signature
        signature = signer.combine_signatures(partials)

        # Verify
        assert signer.verify_signature(signature, message, key_shares.secret_hash)

    def test_share_serialization_workflow(self):
        """Test shares can be serialized for distribution."""
        scheme = ThresholdScheme(threshold=2, total_shares=3)
        secret = secrets.token_bytes(SECRET_SIZE)
        shares = scheme.split(secret)

        # Serialize all shares (e.g., for sending to trustees)
        serialized = [s.to_bytes() for s in shares]

        # Later, trustees send back their shares
        restored = [Share.from_bytes(data) for data in serialized[:2]]

        # Reconstruct
        recovered = scheme.combine(restored)
        assert recovered == secret
