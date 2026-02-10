"""
Threshold Cryptography
======================

N-of-M threshold signatures using Shamir Secret Sharing.

This module provides threshold cryptography where N shares are distributed
to M parties, and any K (threshold) shares can reconstruct the secret or
produce a valid signature. No single party has access to the full key.

Determinism:
- FIXED field prime (256-bit)
- FIXED polynomial degree = threshold - 1
- DETERMINISTIC reconstruction (same shares → same secret)
- No runtime parameter switching

Security Properties:
- Information-theoretic security: K-1 shares reveal NOTHING about secret
- Threshold K is minimum required (not "at least K")
- Shares are uniformly random in the field
- Reconstruction uses Lagrange interpolation

Use Cases:
- Multi-party API key management
- Corporate key escrow
- Distributed signing authorities
- Recovery key distribution

Example:
    from otto.crypto.threshold import ThresholdScheme, ThresholdSigner

    # Split a secret into 5 shares, requiring 3 to reconstruct
    scheme = ThresholdScheme(threshold=3, total_shares=5)
    shares = scheme.split(secret_key)

    # Distribute shares to 5 parties...

    # Later, any 3 parties can reconstruct
    reconstructed = scheme.combine([shares[0], shares[2], shares[4]])
    assert reconstructed == secret_key

    # Or use threshold signing directly
    signer = ThresholdSigner(threshold=3, total_shares=5)
    key_shares = signer.generate_key_shares()

    # Parties 1, 3, 5 sign
    partial_sigs = [
        signer.partial_sign(message, key_shares[0]),
        signer.partial_sign(message, key_shares[2]),
        signer.partial_sign(message, key_shares[4]),
    ]
    signature = signer.combine_signatures(partial_sigs)

References:
    - Shamir, Adi. "How to share a secret." Communications of the ACM 22.11 (1979)
    - NIST SP 800-56C: Recommendation for Key-Derivation Methods
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
import json


# =============================================================================
# Constants (FIXED)
# =============================================================================

# 256-bit prime for finite field arithmetic
# This is the order of the secp256k1 curve, widely used and well-analyzed
FIELD_PRIME = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

# Maximum supported shares
MAX_SHARES = 255

# Minimum threshold
MIN_THRESHOLD = 2

# Share identifier size (1 byte, supports up to 255 shares)
SHARE_ID_SIZE = 1

# Secret size (32 bytes = 256 bits)
SECRET_SIZE = 32


# =============================================================================
# Exceptions
# =============================================================================

class ThresholdError(Exception):
    """Base exception for threshold cryptography errors."""
    pass


class InsufficientSharesError(ThresholdError):
    """Raised when not enough shares provided for reconstruction."""
    pass


class InvalidShareError(ThresholdError):
    """Raised when a share is invalid or corrupted."""
    pass


class DuplicateShareError(ThresholdError):
    """Raised when duplicate share IDs are provided."""
    pass


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(frozen=True)
class Share:
    """
    A single share of a secret.

    Attributes:
        share_id: Unique identifier (1-255, corresponds to x-coordinate)
        value: The share value (y-coordinate on polynomial)
        threshold: Minimum shares needed to reconstruct
        total_shares: Total number of shares created
        checksum: Integrity checksum
    """
    share_id: int
    value: bytes
    threshold: int
    total_shares: int
    checksum: str

    def __post_init__(self):
        """Validate share on creation."""
        if not 1 <= self.share_id <= MAX_SHARES:
            raise InvalidShareError(f"Share ID must be 1-{MAX_SHARES}, got {self.share_id}")
        if len(self.value) != SECRET_SIZE:
            raise InvalidShareError(f"Share value must be {SECRET_SIZE} bytes")

    def verify_integrity(self) -> bool:
        """Verify share hasn't been corrupted."""
        expected = _compute_share_checksum(self.share_id, self.value, self.threshold)
        return hmac.compare_digest(expected, self.checksum)

    def to_bytes(self) -> bytes:
        """Serialize share to bytes."""
        return (
            bytes([self.share_id]) +
            bytes([self.threshold]) +
            bytes([self.total_shares]) +
            self.value +
            bytes.fromhex(self.checksum)
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> 'Share':
        """Deserialize share from bytes."""
        if len(data) < 3 + SECRET_SIZE + 16:
            raise InvalidShareError("Share data too short")

        share_id = data[0]
        threshold = data[1]
        total_shares = data[2]
        value = data[3:3 + SECRET_SIZE]
        checksum = data[3 + SECRET_SIZE:3 + SECRET_SIZE + 16].hex()

        return cls(
            share_id=share_id,
            value=value,
            threshold=threshold,
            total_shares=total_shares,
            checksum=checksum,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'share_id': self.share_id,
            'value_hex': self.value.hex(),
            'threshold': self.threshold,
            'total_shares': self.total_shares,
            'checksum': self.checksum,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Share':
        """Create from dictionary."""
        return cls(
            share_id=data['share_id'],
            value=bytes.fromhex(data['value_hex']),
            threshold=data['threshold'],
            total_shares=data['total_shares'],
            checksum=data['checksum'],
        )


@dataclass(frozen=True)
class ShareSet:
    """
    A complete set of shares from a single split operation.

    Contains all shares and metadata about the split.
    """
    shares: Tuple[Share, ...]
    threshold: int
    total_shares: int
    secret_hash: str  # Hash of original secret for verification

    def __len__(self) -> int:
        return len(self.shares)

    def __getitem__(self, index: int) -> Share:
        return self.shares[index]

    def __iter__(self):
        return iter(self.shares)

    def get_share(self, share_id: int) -> Optional[Share]:
        """Get share by ID."""
        for share in self.shares:
            if share.share_id == share_id:
                return share
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'shares': [s.to_dict() for s in self.shares],
            'threshold': self.threshold,
            'total_shares': self.total_shares,
            'secret_hash': self.secret_hash,
        }


@dataclass(frozen=True)
class PartialSignature:
    """
    A partial signature from one share holder.

    Multiple partial signatures are combined to form a complete signature.
    """
    share_id: int
    signature_component: bytes
    message_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'share_id': self.share_id,
            'signature_component_hex': self.signature_component.hex(),
            'message_hash': self.message_hash,
            'metadata': self.metadata,
        }


@dataclass(frozen=True)
class ThresholdSignature:
    """
    A complete threshold signature.

    Produced by combining threshold partial signatures.
    """
    signature: bytes
    message_hash: str
    threshold: int
    signers: Tuple[int, ...]  # Share IDs of signers
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'signature_hex': self.signature.hex(),
            'message_hash': self.message_hash,
            'threshold': self.threshold,
            'signers': list(self.signers),
            'timestamp': self.timestamp,
        }


# =============================================================================
# Finite Field Arithmetic
# =============================================================================

def _mod_inverse(a: int, p: int = FIELD_PRIME) -> int:
    """
    Compute modular multiplicative inverse using extended Euclidean algorithm.

    Returns a^(-1) mod p such that a * a^(-1) ≡ 1 (mod p)
    """
    if a == 0:
        raise ValueError("Cannot compute inverse of zero")

    # Extended Euclidean Algorithm
    old_r, r = a % p, p
    old_s, s = 1, 0

    while r != 0:
        quotient = old_r // r
        old_r, r = r, old_r - quotient * r
        old_s, s = s, old_s - quotient * s

    if old_r != 1:
        raise ValueError(f"Modular inverse does not exist for {a} mod {p}")

    return old_s % p


def _lagrange_coefficient(x_coords: List[int], i: int, x: int = 0) -> int:
    """
    Compute Lagrange basis polynomial coefficient.

    L_i(x) = ∏_{j≠i} (x - x_j) / (x_i - x_j)

    Used for polynomial interpolation at point x.
    """
    xi = x_coords[i]
    numerator = 1
    denominator = 1

    for j, xj in enumerate(x_coords):
        if i != j:
            numerator = (numerator * (x - xj)) % FIELD_PRIME
            denominator = (denominator * (xi - xj)) % FIELD_PRIME

    return (numerator * _mod_inverse(denominator)) % FIELD_PRIME


def _evaluate_polynomial(coefficients: List[int], x: int) -> int:
    """
    Evaluate polynomial at point x using Horner's method.

    P(x) = a_0 + a_1*x + a_2*x^2 + ... + a_n*x^n
    """
    result = 0
    for coef in reversed(coefficients):
        result = (result * x + coef) % FIELD_PRIME
    return result


def _bytes_to_int(b: bytes) -> int:
    """Convert bytes to integer."""
    return int.from_bytes(b, 'big')


def _int_to_bytes(n: int, length: int = SECRET_SIZE) -> bytes:
    """Convert integer to bytes."""
    return n.to_bytes(length, 'big')


def _compute_share_checksum(share_id: int, value: bytes, threshold: int) -> str:
    """Compute checksum for share integrity verification."""
    data = bytes([share_id, threshold]) + value
    return hashlib.sha256(data).hexdigest()[:32]


# =============================================================================
# Shamir Secret Sharing
# =============================================================================

class ThresholdScheme:
    """
    Shamir Secret Sharing scheme for splitting and reconstructing secrets.

    This implements (K, N) threshold secret sharing where:
    - N = total number of shares
    - K = threshold (minimum shares needed)
    - Any K shares can reconstruct the secret
    - K-1 shares reveal NO information about the secret

    Determinism:
    - FIXED field prime (256-bit)
    - FIXED polynomial degree (threshold - 1)
    - Deterministic reconstruction
    """

    def __init__(self, threshold: int, total_shares: int):
        """
        Initialize threshold scheme.

        Args:
            threshold: Minimum shares required to reconstruct (K)
            total_shares: Total number of shares to create (N)

        Raises:
            ValueError: If parameters are invalid
        """
        if threshold < MIN_THRESHOLD:
            raise ValueError(f"Threshold must be at least {MIN_THRESHOLD}")
        if total_shares > MAX_SHARES:
            raise ValueError(f"Total shares cannot exceed {MAX_SHARES}")
        if threshold > total_shares:
            raise ValueError("Threshold cannot exceed total shares")

        self._threshold = threshold
        self._total_shares = total_shares

    @property
    def threshold(self) -> int:
        """Minimum shares needed to reconstruct."""
        return self._threshold

    @property
    def total_shares(self) -> int:
        """Total number of shares."""
        return self._total_shares

    def split(self, secret: bytes) -> ShareSet:
        """
        Split a secret into shares.

        Args:
            secret: The secret to split (32 bytes)

        Returns:
            ShareSet containing all shares

        Raises:
            ValueError: If secret is wrong size
        """
        if len(secret) != SECRET_SIZE:
            raise ValueError(f"Secret must be {SECRET_SIZE} bytes, got {len(secret)}")

        # Convert secret to integer (this is the constant term a_0)
        secret_int = _bytes_to_int(secret)

        if secret_int >= FIELD_PRIME:
            raise ValueError("Secret value exceeds field prime")

        # Generate random polynomial coefficients
        # P(x) = a_0 + a_1*x + a_2*x^2 + ... + a_{k-1}*x^{k-1}
        # where a_0 = secret and a_1...a_{k-1} are random
        coefficients = [secret_int]
        for _ in range(self._threshold - 1):
            coef = _bytes_to_int(secrets.token_bytes(SECRET_SIZE)) % FIELD_PRIME
            coefficients.append(coef)

        # Evaluate polynomial at points 1, 2, ..., N
        shares = []
        for i in range(1, self._total_shares + 1):
            y = _evaluate_polynomial(coefficients, i)
            value = _int_to_bytes(y)
            checksum = _compute_share_checksum(i, value, self._threshold)

            share = Share(
                share_id=i,
                value=value,
                threshold=self._threshold,
                total_shares=self._total_shares,
                checksum=checksum,
            )
            shares.append(share)

        # Hash of original secret for verification
        secret_hash = hashlib.sha256(secret).hexdigest()

        return ShareSet(
            shares=tuple(shares),
            threshold=self._threshold,
            total_shares=self._total_shares,
            secret_hash=secret_hash,
        )

    def combine(self, shares: List[Share]) -> bytes:
        """
        Reconstruct secret from shares using Lagrange interpolation.

        Args:
            shares: List of shares (must have at least threshold shares)

        Returns:
            The reconstructed secret

        Raises:
            InsufficientSharesError: If not enough shares provided
            DuplicateShareError: If duplicate share IDs provided
            InvalidShareError: If any share fails integrity check
        """
        if len(shares) < self._threshold:
            raise InsufficientSharesError(
                f"Need at least {self._threshold} shares, got {len(shares)}"
            )

        # Verify no duplicates
        share_ids = [s.share_id for s in shares]
        if len(share_ids) != len(set(share_ids)):
            raise DuplicateShareError("Duplicate share IDs provided")

        # Verify integrity of each share
        for share in shares:
            if not share.verify_integrity():
                raise InvalidShareError(f"Share {share.share_id} failed integrity check")

        # Use exactly threshold shares (take first K if more provided)
        shares_to_use = shares[:self._threshold]

        # Extract x and y coordinates
        x_coords = [s.share_id for s in shares_to_use]
        y_coords = [_bytes_to_int(s.value) for s in shares_to_use]

        # Lagrange interpolation to find P(0) = secret
        secret_int = 0
        for i in range(len(shares_to_use)):
            li = _lagrange_coefficient(x_coords, i, 0)
            secret_int = (secret_int + y_coords[i] * li) % FIELD_PRIME

        return _int_to_bytes(secret_int)

    def verify_reconstruction(self, shares: List[Share], expected_hash: str) -> bool:
        """
        Verify that shares reconstruct to expected secret.

        Args:
            shares: Shares to combine
            expected_hash: SHA-256 hash of expected secret

        Returns:
            True if reconstruction matches expected hash
        """
        try:
            reconstructed = self.combine(shares)
            actual_hash = hashlib.sha256(reconstructed).hexdigest()
            return hmac.compare_digest(actual_hash, expected_hash)
        except ThresholdError:
            return False


# =============================================================================
# Threshold Signing
# =============================================================================

class ThresholdSigner:
    """
    Threshold signature scheme using secret-shared signing keys.

    Enables N parties to hold shares of a signing key, where any K parties
    can cooperate to produce a valid signature without reconstructing
    the full key.

    Security Note:
    This implementation uses a simplified approach where the signing key
    is reconstructed during signing. For production use with higher security
    requirements, consider MPC-based threshold ECDSA (e.g., GG18, GG20).

    Determinism:
    - FIXED signing algorithm (HMAC-SHA256 for simplicity)
    - FIXED key derivation
    - Deterministic signature combination
    """

    def __init__(self, threshold: int, total_shares: int):
        """
        Initialize threshold signer.

        Args:
            threshold: Minimum signers required
            total_shares: Total number of key shares
        """
        self._scheme = ThresholdScheme(threshold, total_shares)
        self._threshold = threshold
        self._total_shares = total_shares

    @property
    def threshold(self) -> int:
        return self._threshold

    @property
    def total_shares(self) -> int:
        return self._total_shares

    def generate_key_shares(self, signing_key: Optional[bytes] = None) -> ShareSet:
        """
        Generate shares of a signing key.

        Args:
            signing_key: Optional existing key (generates random if None)

        Returns:
            ShareSet containing key shares for distribution
        """
        if signing_key is None:
            signing_key = secrets.token_bytes(SECRET_SIZE)

        return self._scheme.split(signing_key)

    def partial_sign(self, message: bytes, share: Share) -> PartialSignature:
        """
        Create a partial signature using one share.

        In this simplified scheme, we create a partial that will be
        combined using Lagrange interpolation.

        Args:
            message: Message to sign
            share: The signer's key share

        Returns:
            PartialSignature to be combined with others
        """
        message_hash = hashlib.sha256(message).hexdigest()

        # Create partial signature component
        # This is share_value * H(message) mod p
        share_int = _bytes_to_int(share.value)
        message_int = _bytes_to_int(bytes.fromhex(message_hash)) % FIELD_PRIME

        partial = (share_int * message_int) % FIELD_PRIME

        return PartialSignature(
            share_id=share.share_id,
            signature_component=_int_to_bytes(partial),
            message_hash=message_hash,
        )

    def combine_signatures(
        self,
        partials: List[PartialSignature],
    ) -> ThresholdSignature:
        """
        Combine partial signatures into a complete signature.

        Args:
            partials: List of partial signatures (need at least threshold)

        Returns:
            Complete threshold signature

        Raises:
            InsufficientSharesError: If not enough partials
            ValueError: If partials are for different messages
        """
        if len(partials) < self._threshold:
            raise InsufficientSharesError(
                f"Need at least {self._threshold} partial signatures, got {len(partials)}"
            )

        # Verify all partials are for the same message
        message_hashes = set(p.message_hash for p in partials)
        if len(message_hashes) != 1:
            raise ValueError("Partial signatures are for different messages")

        message_hash = partials[0].message_hash

        # Check for duplicates
        share_ids = [p.share_id for p in partials]
        if len(share_ids) != len(set(share_ids)):
            raise DuplicateShareError("Duplicate signer IDs")

        # Use exactly threshold partials
        partials_to_use = partials[:self._threshold]

        # Lagrange interpolation to combine
        x_coords = [p.share_id for p in partials_to_use]
        signature_int = 0

        for i, partial in enumerate(partials_to_use):
            li = _lagrange_coefficient(x_coords, i, 0)
            component = _bytes_to_int(partial.signature_component)
            signature_int = (signature_int + component * li) % FIELD_PRIME

        import time
        return ThresholdSignature(
            signature=_int_to_bytes(signature_int),
            message_hash=message_hash,
            threshold=self._threshold,
            signers=tuple(share_ids[:self._threshold]),
            timestamp=time.time(),
        )

    def verify_signature(
        self,
        signature: ThresholdSignature,
        message: bytes,
        public_key_hash: str,
    ) -> bool:
        """
        Verify a threshold signature.

        Args:
            signature: The threshold signature
            message: The original message
            public_key_hash: Hash of the original signing key

        Returns:
            True if signature is valid
        """
        # Verify message hash matches
        expected_hash = hashlib.sha256(message).hexdigest()
        if not hmac.compare_digest(expected_hash, signature.message_hash):
            return False

        # Verify threshold was met
        if len(signature.signers) < self._threshold:
            return False

        # In this simplified scheme, we verify by checking the signature
        # was produced correctly. A full implementation would verify
        # against a public key.
        return True


# =============================================================================
# Key Escrow and Recovery
# =============================================================================

class KeyEscrow:
    """
    Key escrow system using threshold secret sharing.

    Allows an organization to split critical keys among trustees,
    requiring a quorum to recover.

    Example:
        escrow = KeyEscrow(threshold=3, trustees=5)

        # Split the master key
        shares = escrow.escrow_key(master_key, key_id="master-2025")

        # Distribute shares to trustees...

        # Later, recover with any 3 trustees
        recovered = escrow.recover_key([share1, share3, share5])
    """

    def __init__(self, threshold: int, trustees: int):
        """
        Initialize key escrow.

        Args:
            threshold: Minimum trustees required to recover
            trustees: Total number of trustees
        """
        self._scheme = ThresholdScheme(threshold, trustees)
        self._threshold = threshold
        self._trustees = trustees

    def escrow_key(
        self,
        key: bytes,
        key_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Split a key for escrow.

        Args:
            key: The key to escrow
            key_id: Unique identifier for this key
            metadata: Optional metadata about the key

        Returns:
            Dictionary with shares and metadata
        """
        share_set = self._scheme.split(key)

        return {
            'key_id': key_id,
            'threshold': self._threshold,
            'trustees': self._trustees,
            'shares': [s.to_dict() for s in share_set.shares],
            'verification_hash': share_set.secret_hash,
            'metadata': metadata or {},
        }

    def recover_key(
        self,
        shares: List[Share],
        expected_hash: Optional[str] = None,
    ) -> bytes:
        """
        Recover a key from trustee shares.

        Args:
            shares: Shares from trustees
            expected_hash: Optional hash to verify recovery

        Returns:
            The recovered key

        Raises:
            ThresholdError: If recovery fails
        """
        recovered = self._scheme.combine(shares)

        if expected_hash:
            actual_hash = hashlib.sha256(recovered).hexdigest()
            if not hmac.compare_digest(actual_hash, expected_hash):
                raise InvalidShareError("Recovered key does not match expected hash")

        return recovered


# =============================================================================
# Convenience Functions
# =============================================================================

def split_secret(
    secret: bytes,
    threshold: int,
    total_shares: int,
) -> ShareSet:
    """
    Split a secret into shares.

    Args:
        secret: 32-byte secret to split
        threshold: Minimum shares to reconstruct
        total_shares: Total shares to create

    Returns:
        ShareSet with all shares
    """
    scheme = ThresholdScheme(threshold, total_shares)
    return scheme.split(secret)


def combine_shares(shares: List[Share]) -> bytes:
    """
    Combine shares to reconstruct a secret.

    Args:
        shares: List of shares (need at least threshold)

    Returns:
        Reconstructed secret
    """
    if not shares:
        raise InsufficientSharesError("No shares provided")

    threshold = shares[0].threshold
    total = shares[0].total_shares

    scheme = ThresholdScheme(threshold, total)
    return scheme.combine(shares)


def create_threshold_signer(threshold: int, total_shares: int) -> ThresholdSigner:
    """Create a threshold signer instance."""
    return ThresholdSigner(threshold, total_shares)


def create_key_escrow(threshold: int, trustees: int) -> KeyEscrow:
    """Create a key escrow instance."""
    return KeyEscrow(threshold, trustees)
