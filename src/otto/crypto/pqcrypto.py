"""
Post-Quantum Cryptography
=========================

Hybrid post-quantum key exchange using ML-KEM (Kyber) + X25519.

This module provides quantum-resistant key exchange that protects against
"harvest now, decrypt later" attacks where adversaries store encrypted
traffic to decrypt once quantum computers become available.

Determinism:
- FIXED algorithms: X25519 (classical) + ML-KEM-768 (post-quantum)
- FIXED KDF: HKDF-SHA256 for key derivation
- DETERMINISTIC: same keys → same shared secret
- No runtime algorithm switching

Security Model:
- Hybrid approach: Security of max(classical, post-quantum)
- If either X25519 OR ML-KEM is secure, the combined scheme is secure
- NIST PQC finalist ML-KEM (formerly Kyber) for post-quantum security
- X25519 for classical security (widely deployed, well-analyzed)

Dependencies:
- cryptography: For X25519 and HKDF (required)
- liboqs-python: For ML-KEM/Kyber (optional, graceful degradation)

Usage:
    from otto.crypto.pqcrypto import HybridKEM, HybridKeyExchange

    # Key Encapsulation
    kem = HybridKEM()
    public_key, private_key = kem.generate_keypair()
    ciphertext, shared_secret = kem.encapsulate(public_key)
    recovered_secret = kem.decapsulate(ciphertext, private_key)

    # Full Key Exchange
    kex = HybridKeyExchange()
    alice = kex.generate_keypair()
    bob = kex.generate_keypair()
    alice_secret = kex.derive_shared_secret(alice.private_key, bob.public_key)
    bob_secret = kex.derive_shared_secret(bob.private_key, alice.public_key)
    assert alice_secret == bob_secret

References:
    - NIST SP 800-186: Recommendations for Discrete Logarithm-Based Cryptography
    - NIST FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism (ML-KEM)
    - RFC 7748: Elliptic Curves for Security (X25519)
    - RFC 5869: HMAC-based Extract-and-Expand Key Derivation Function (HKDF)
"""

import hashlib
import hmac
import logging
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, Dict, Any, List

# Classical crypto from cryptography library (required)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)


# =============================================================================
# Constants (FIXED)
# =============================================================================

# Key sizes
X25519_PUBLIC_KEY_SIZE = 32
X25519_PRIVATE_KEY_SIZE = 32
X25519_SHARED_SECRET_SIZE = 32

# ML-KEM-768 (Kyber768) sizes - NIST Level 3 security
MLKEM768_PUBLIC_KEY_SIZE = 1184
MLKEM768_PRIVATE_KEY_SIZE = 2400
MLKEM768_CIPHERTEXT_SIZE = 1088
MLKEM768_SHARED_SECRET_SIZE = 32

# Derived key size for session keys
DERIVED_KEY_SIZE = 32  # 256 bits

# HKDF info strings (fixed, no runtime variation)
HKDF_INFO_KEX = b"OTTO-PQ-KEX-v1"
HKDF_INFO_SESSION = b"OTTO-PQ-SESSION-v1"


# =============================================================================
# liboqs Availability Check
# =============================================================================

_LIBOQS_AVAILABLE = False
_oqs = None


def _check_liboqs() -> bool:
    """
    Check if liboqs is available without blocking.

    The liboqs-python package may try to build native libraries on import,
    which can hang or fail. We check for the shared library first.
    """
    global _LIBOQS_AVAILABLE, _oqs

    if _LIBOQS_AVAILABLE:
        return True

    try:
        # Try to import - this may fail or hang if native lib not built
        import oqs as _oqs_module

        # Verify it actually works by checking for algorithms
        _oqs_module.get_enabled_kem_mechanisms()

        _oqs = _oqs_module
        _LIBOQS_AVAILABLE = True
        logger.info("liboqs-python available: Post-quantum algorithms enabled")
        return True

    except (ImportError, RuntimeError, SystemExit, Exception) as e:
        logger.warning(
            f"liboqs not available ({type(e).__name__}). "
            "Post-quantum key exchange disabled. Using X25519 only."
        )
        return False


# Don't check on import - defer until first use to avoid blocking
# _check_liboqs()


def is_pq_available() -> bool:
    """Check if post-quantum algorithms are available."""
    if _LIBOQS_AVAILABLE:
        return True
    # Lazy check - only try once
    return _check_liboqs()


# =============================================================================
# Algorithm Enumeration
# =============================================================================

class KEMAlgorithm(Enum):
    """Supported Key Encapsulation Mechanism algorithms."""
    X25519 = "x25519"           # Classical ECDH
    MLKEM512 = "ML-KEM-512"     # NIST Level 1 (Kyber512)
    MLKEM768 = "ML-KEM-768"     # NIST Level 3 (Kyber768) - RECOMMENDED
    MLKEM1024 = "ML-KEM-1024"   # NIST Level 5 (Kyber1024)
    HYBRID_X25519_MLKEM768 = "hybrid-x25519-mlkem768"  # Hybrid (recommended)


# Map our algorithm names to liboqs algorithm names
_LIBOQS_ALGORITHM_MAP = {
    KEMAlgorithm.MLKEM512: "Kyber512",
    KEMAlgorithm.MLKEM768: "Kyber768",
    KEMAlgorithm.MLKEM1024: "Kyber1024",
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass(frozen=True)
class KEMPublicKey:
    """Public key for key encapsulation."""
    algorithm: KEMAlgorithm
    key_bytes: bytes

    def __len__(self) -> int:
        return len(self.key_bytes)

    def hex(self) -> str:
        return self.key_bytes.hex()


@dataclass(frozen=True)
class KEMPrivateKey:
    """Private key for key decapsulation."""
    algorithm: KEMAlgorithm
    key_bytes: bytes

    def __len__(self) -> int:
        return len(self.key_bytes)


@dataclass(frozen=True)
class KEMKeyPair:
    """Key pair for key encapsulation mechanism."""
    public_key: KEMPublicKey
    private_key: KEMPrivateKey
    algorithm: KEMAlgorithm


@dataclass(frozen=True)
class KEMCiphertext:
    """Encapsulated ciphertext."""
    algorithm: KEMAlgorithm
    ciphertext_bytes: bytes

    def __len__(self) -> int:
        return len(self.ciphertext_bytes)


@dataclass(frozen=True)
class HybridPublicKey:
    """Combined classical + post-quantum public key."""
    classical: KEMPublicKey
    post_quantum: Optional[KEMPublicKey]

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        classical_bytes = self.classical.key_bytes
        pq_bytes = self.post_quantum.key_bytes if self.post_quantum else b""
        # Format: [2-byte classical len][classical][pq]
        return (
            len(classical_bytes).to_bytes(2, 'big') +
            classical_bytes +
            pq_bytes
        )

    @classmethod
    def from_bytes(cls, data: bytes, pq_available: bool = True) -> 'HybridPublicKey':
        """Deserialize from bytes."""
        classical_len = int.from_bytes(data[:2], 'big')
        classical_bytes = data[2:2 + classical_len]
        pq_bytes = data[2 + classical_len:] if pq_available else None

        classical = KEMPublicKey(KEMAlgorithm.X25519, classical_bytes)
        pq = KEMPublicKey(KEMAlgorithm.MLKEM768, pq_bytes) if pq_bytes else None

        return cls(classical=classical, post_quantum=pq)


@dataclass(frozen=True)
class HybridPrivateKey:
    """Combined classical + post-quantum private key."""
    classical: KEMPrivateKey
    post_quantum: Optional[KEMPrivateKey]


@dataclass(frozen=True)
class HybridKeyPair:
    """Combined classical + post-quantum key pair."""
    public_key: HybridPublicKey
    private_key: HybridPrivateKey


@dataclass(frozen=True)
class HybridCiphertext:
    """Combined classical + post-quantum ciphertext."""
    classical: KEMCiphertext
    post_quantum: Optional[KEMCiphertext]

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        classical_bytes = self.classical.ciphertext_bytes
        pq_bytes = self.post_quantum.ciphertext_bytes if self.post_quantum else b""
        return (
            len(classical_bytes).to_bytes(2, 'big') +
            classical_bytes +
            pq_bytes
        )


@dataclass
class PQSecurityStatus:
    """Status of post-quantum security features."""
    pq_available: bool
    algorithm: str
    classical_algorithm: str
    hybrid_mode: bool
    security_level: str  # "classical-only" | "hybrid-pq" | "pq-only"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pq_available': self.pq_available,
            'algorithm': self.algorithm,
            'classical_algorithm': self.classical_algorithm,
            'hybrid_mode': self.hybrid_mode,
            'security_level': self.security_level,
        }


# =============================================================================
# Abstract KEM Interface
# =============================================================================

class KEMProvider(ABC):
    """Abstract base class for Key Encapsulation Mechanism providers."""

    @property
    @abstractmethod
    def algorithm(self) -> KEMAlgorithm:
        """Get the algorithm this provider implements."""
        pass

    @abstractmethod
    def generate_keypair(self) -> KEMKeyPair:
        """Generate a new key pair."""
        pass

    @abstractmethod
    def encapsulate(self, public_key: KEMPublicKey) -> Tuple[KEMCiphertext, bytes]:
        """
        Encapsulate a shared secret.

        Args:
            public_key: Recipient's public key

        Returns:
            Tuple of (ciphertext, shared_secret)
        """
        pass

    @abstractmethod
    def decapsulate(self, ciphertext: KEMCiphertext, private_key: KEMPrivateKey) -> bytes:
        """
        Decapsulate a shared secret.

        Args:
            ciphertext: The encapsulated ciphertext
            private_key: Recipient's private key

        Returns:
            The shared secret
        """
        pass


# =============================================================================
# X25519 KEM (Classical)
# =============================================================================

class X25519KEM(KEMProvider):
    """
    X25519-based Key Encapsulation Mechanism.

    Uses ephemeral-static ECDH to create a KEM from X25519.
    This provides IND-CCA2 security when combined with HKDF.
    """

    @property
    def algorithm(self) -> KEMAlgorithm:
        return KEMAlgorithm.X25519

    def generate_keypair(self) -> KEMKeyPair:
        """Generate X25519 key pair."""
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return KEMKeyPair(
            public_key=KEMPublicKey(self.algorithm, public_bytes),
            private_key=KEMPrivateKey(self.algorithm, private_bytes),
            algorithm=self.algorithm,
        )

    def encapsulate(self, public_key: KEMPublicKey) -> Tuple[KEMCiphertext, bytes]:
        """
        Encapsulate using ephemeral-static ECDH.

        1. Generate ephemeral key pair
        2. Compute shared secret = ECDH(ephemeral_private, static_public)
        3. Derive key using HKDF
        4. Return (ephemeral_public, derived_key)
        """
        # Generate ephemeral key pair
        ephemeral_private = x25519.X25519PrivateKey.generate()
        ephemeral_public = ephemeral_private.public_key()

        # Load recipient's public key
        recipient_public = x25519.X25519PublicKey.from_public_bytes(
            public_key.key_bytes
        )

        # Compute raw shared secret
        raw_shared = ephemeral_private.exchange(recipient_public)

        # Derive final shared secret using HKDF
        # Include ephemeral public key in derivation for binding
        ephemeral_public_bytes = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        shared_secret = self._derive_shared_secret(
            raw_shared,
            ephemeral_public_bytes,
            public_key.key_bytes,
        )

        ciphertext = KEMCiphertext(
            algorithm=self.algorithm,
            ciphertext_bytes=ephemeral_public_bytes,
        )

        return ciphertext, shared_secret

    def decapsulate(self, ciphertext: KEMCiphertext, private_key: KEMPrivateKey) -> bytes:
        """
        Decapsulate using static-ephemeral ECDH.

        1. Load ephemeral public from ciphertext
        2. Compute shared secret = ECDH(static_private, ephemeral_public)
        3. Derive key using HKDF
        """
        # Load keys
        static_private = x25519.X25519PrivateKey.from_private_bytes(
            private_key.key_bytes
        )
        static_public = static_private.public_key()
        ephemeral_public = x25519.X25519PublicKey.from_public_bytes(
            ciphertext.ciphertext_bytes
        )

        # Compute raw shared secret
        raw_shared = static_private.exchange(ephemeral_public)

        # Derive final shared secret
        static_public_bytes = static_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        shared_secret = self._derive_shared_secret(
            raw_shared,
            ciphertext.ciphertext_bytes,
            static_public_bytes,
        )

        return shared_secret

    def _derive_shared_secret(
        self,
        raw_shared: bytes,
        ephemeral_public: bytes,
        static_public: bytes,
    ) -> bytes:
        """Derive shared secret using HKDF."""
        # Salt includes both public keys for domain separation
        salt = hashlib.sha256(ephemeral_public + static_public).digest()

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=DERIVED_KEY_SIZE,
            salt=salt,
            info=HKDF_INFO_KEX,
        )

        return hkdf.derive(raw_shared)


# =============================================================================
# ML-KEM (Post-Quantum) KEM
# =============================================================================

class MLKEM(KEMProvider):
    """
    ML-KEM (Kyber) Key Encapsulation Mechanism.

    Provides post-quantum security based on Module Learning With Errors (MLWE).
    Requires liboqs-python for the underlying implementation.
    """

    def __init__(self, variant: KEMAlgorithm = KEMAlgorithm.MLKEM768):
        """
        Initialize ML-KEM provider.

        Args:
            variant: Which ML-KEM variant to use (default: ML-KEM-768)
        """
        if not is_pq_available():
            raise RuntimeError(
                "ML-KEM requires liboqs-python with native library. "
                "Install with: pip install liboqs-python (requires cmake and C compiler)"
            )

        if variant not in _LIBOQS_ALGORITHM_MAP:
            raise ValueError(f"Unsupported ML-KEM variant: {variant}")

        self._variant = variant
        self._liboqs_name = _LIBOQS_ALGORITHM_MAP[variant]

    @property
    def algorithm(self) -> KEMAlgorithm:
        return self._variant

    def generate_keypair(self) -> KEMKeyPair:
        """Generate ML-KEM key pair using liboqs."""
        with _oqs.KeyEncapsulation(self._liboqs_name) as kem:
            public_key = kem.generate_keypair()
            private_key = kem.export_secret_key()

        return KEMKeyPair(
            public_key=KEMPublicKey(self.algorithm, public_key),
            private_key=KEMPrivateKey(self.algorithm, private_key),
            algorithm=self.algorithm,
        )

    def encapsulate(self, public_key: KEMPublicKey) -> Tuple[KEMCiphertext, bytes]:
        """Encapsulate a shared secret using ML-KEM."""
        with _oqs.KeyEncapsulation(self._liboqs_name) as kem:
            ciphertext, shared_secret = kem.encap_secret(public_key.key_bytes)

        return (
            KEMCiphertext(self.algorithm, ciphertext),
            shared_secret,
        )

    def decapsulate(self, ciphertext: KEMCiphertext, private_key: KEMPrivateKey) -> bytes:
        """Decapsulate a shared secret using ML-KEM."""
        with _oqs.KeyEncapsulation(self._liboqs_name, private_key.key_bytes) as kem:
            shared_secret = kem.decap_secret(ciphertext.ciphertext_bytes)

        return shared_secret


# =============================================================================
# Hybrid KEM (Classical + Post-Quantum)
# =============================================================================

class HybridKEM:
    """
    Hybrid Key Encapsulation combining X25519 and ML-KEM-768.

    Security: max(classical_security, pq_security)
    - If X25519 is broken but ML-KEM is not → still secure
    - If ML-KEM is broken but X25519 is not → still secure
    - Only vulnerable if BOTH are broken

    This is the recommended approach during the post-quantum transition.
    Gracefully degrades to X25519-only if liboqs is not available.
    """

    def __init__(self):
        """Initialize hybrid KEM."""
        self._classical = X25519KEM()
        self._pq: Optional[MLKEM] = None
        self._pq_checked = False

    def _ensure_pq_checked(self) -> None:
        """Lazily check for PQ availability."""
        if self._pq_checked:
            return
        self._pq_checked = True

        if is_pq_available():
            try:
                self._pq = MLKEM(KEMAlgorithm.MLKEM768)
            except Exception as e:
                logger.warning(f"Failed to initialize ML-KEM: {e}")

    @property
    def is_pq_enabled(self) -> bool:
        """Check if post-quantum algorithms are enabled."""
        self._ensure_pq_checked()
        return self._pq is not None

    @property
    def security_status(self) -> PQSecurityStatus:
        """Get current security status."""
        return PQSecurityStatus(
            pq_available=self.is_pq_enabled,
            algorithm="ML-KEM-768" if self.is_pq_enabled else "none",
            classical_algorithm="X25519",
            hybrid_mode=self.is_pq_enabled,
            security_level="hybrid-pq" if self.is_pq_enabled else "classical-only",
        )

    def generate_keypair(self) -> HybridKeyPair:
        """Generate hybrid key pair."""
        self._ensure_pq_checked()
        classical_kp = self._classical.generate_keypair()

        pq_kp = None
        if self._pq:
            pq_kp = self._pq.generate_keypair()

        return HybridKeyPair(
            public_key=HybridPublicKey(
                classical=classical_kp.public_key,
                post_quantum=pq_kp.public_key if pq_kp else None,
            ),
            private_key=HybridPrivateKey(
                classical=classical_kp.private_key,
                post_quantum=pq_kp.private_key if pq_kp else None,
            ),
        )

    def encapsulate(self, public_key: HybridPublicKey) -> Tuple[HybridCiphertext, bytes]:
        """
        Encapsulate a shared secret using hybrid KEM.

        Combines secrets from both classical and PQ KEMs using HKDF.
        """
        self._ensure_pq_checked()

        # Classical encapsulation (always)
        classical_ct, classical_ss = self._classical.encapsulate(public_key.classical)

        # Post-quantum encapsulation (if available)
        pq_ct = None
        pq_ss = b""
        if self._pq and public_key.post_quantum:
            pq_ct, pq_ss = self._pq.encapsulate(public_key.post_quantum)

        # Combine shared secrets
        combined_secret = self._combine_secrets(classical_ss, pq_ss)

        ciphertext = HybridCiphertext(
            classical=classical_ct,
            post_quantum=pq_ct,
        )

        return ciphertext, combined_secret

    def decapsulate(
        self,
        ciphertext: HybridCiphertext,
        private_key: HybridPrivateKey,
    ) -> bytes:
        """
        Decapsulate a shared secret using hybrid KEM.
        """
        # Classical decapsulation (always)
        classical_ss = self._classical.decapsulate(
            ciphertext.classical,
            private_key.classical,
        )

        # Post-quantum decapsulation (if available)
        pq_ss = b""
        if self._pq and ciphertext.post_quantum and private_key.post_quantum:
            pq_ss = self._pq.decapsulate(
                ciphertext.post_quantum,
                private_key.post_quantum,
            )

        # Combine shared secrets
        return self._combine_secrets(classical_ss, pq_ss)

    def _combine_secrets(self, classical_ss: bytes, pq_ss: bytes) -> bytes:
        """
        Combine classical and post-quantum shared secrets.

        Uses HKDF with both secrets as input keying material.
        If PQ secret is empty, still produces a valid derived key.
        """
        # Concatenate secrets (empty pq_ss is fine)
        combined_input = classical_ss + pq_ss

        # Domain separation based on whether PQ was used
        info = HKDF_INFO_KEX + (b":hybrid" if pq_ss else b":classical")

        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=DERIVED_KEY_SIZE,
            salt=None,  # Secrets are already high-entropy
            info=info,
        )

        return hkdf.derive(combined_input)


# =============================================================================
# High-Level Key Exchange
# =============================================================================

class HybridKeyExchange:
    """
    High-level hybrid key exchange protocol.

    Provides an easy-to-use interface for establishing shared secrets
    between two parties using hybrid post-quantum cryptography.

    Example:
        kex = HybridKeyExchange()

        # Alice generates her keys
        alice_keypair = kex.generate_keypair()

        # Bob generates his keys
        bob_keypair = kex.generate_keypair()

        # Alice encapsulates a secret for Bob
        ciphertext, alice_secret = kex.encapsulate(bob_keypair.public_key)

        # Bob decapsulates to get the same secret
        bob_secret = kex.decapsulate(ciphertext, bob_keypair.private_key)

        assert alice_secret == bob_secret
    """

    def __init__(self):
        """Initialize key exchange."""
        self._kem = HybridKEM()

    @property
    def security_status(self) -> PQSecurityStatus:
        """Get security status."""
        return self._kem.security_status

    def generate_keypair(self) -> HybridKeyPair:
        """Generate a new key pair for key exchange."""
        return self._kem.generate_keypair()

    def encapsulate(self, recipient_public_key: HybridPublicKey) -> Tuple[HybridCiphertext, bytes]:
        """
        Encapsulate a shared secret for a recipient.

        Args:
            recipient_public_key: The recipient's public key

        Returns:
            Tuple of (ciphertext to send, shared_secret)
        """
        return self._kem.encapsulate(recipient_public_key)

    def decapsulate(
        self,
        ciphertext: HybridCiphertext,
        private_key: HybridPrivateKey,
    ) -> bytes:
        """
        Decapsulate a shared secret.

        Args:
            ciphertext: The received ciphertext
            private_key: Your private key

        Returns:
            The shared secret
        """
        return self._kem.decapsulate(ciphertext, private_key)

    def derive_session_keys(
        self,
        shared_secret: bytes,
        context: bytes = b"",
        num_keys: int = 2,
        key_size: int = 32,
    ) -> List[bytes]:
        """
        Derive multiple session keys from a shared secret.

        Useful for deriving separate encryption and MAC keys.

        Args:
            shared_secret: The shared secret from encapsulate/decapsulate
            context: Optional context for domain separation
            num_keys: Number of keys to derive
            key_size: Size of each key in bytes

        Returns:
            List of derived keys
        """
        keys = []
        for i in range(num_keys):
            info = HKDF_INFO_SESSION + context + i.to_bytes(1, 'big')
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=key_size,
                salt=None,
                info=info,
            )
            keys.append(hkdf.derive(shared_secret))

        return keys


# =============================================================================
# Convenience Functions
# =============================================================================

def create_hybrid_kem() -> HybridKEM:
    """Create a hybrid KEM instance."""
    return HybridKEM()


def create_key_exchange() -> HybridKeyExchange:
    """Create a key exchange instance."""
    return HybridKeyExchange()


def get_pq_status() -> PQSecurityStatus:
    """Get current post-quantum security status."""
    kem = HybridKEM()
    return kem.security_status


# =============================================================================
# Serialization Helpers
# =============================================================================

def serialize_hybrid_public_key(key: HybridPublicKey) -> bytes:
    """Serialize a hybrid public key to bytes."""
    return key.to_bytes()


def deserialize_hybrid_public_key(data: bytes) -> HybridPublicKey:
    """Deserialize a hybrid public key from bytes."""
    return HybridPublicKey.from_bytes(data, pq_available=_LIBOQS_AVAILABLE)


def serialize_hybrid_ciphertext(ct: HybridCiphertext) -> bytes:
    """Serialize a hybrid ciphertext to bytes."""
    return ct.to_bytes()


# =============================================================================
# Module Initialization
# =============================================================================

def _log_pq_status():
    """Log post-quantum status on module load."""
    status = get_pq_status()
    if status.pq_available:
        logger.info(
            f"Post-quantum cryptography enabled: {status.algorithm} + "
            f"{status.classical_algorithm} (hybrid mode)"
        )
    else:
        logger.warning(
            f"Post-quantum cryptography NOT available. "
            f"Using classical {status.classical_algorithm} only. "
            f"Install liboqs-python for quantum resistance."
        )


# Log status on import (but don't fail)
try:
    _log_pq_status()
except Exception:
    pass
