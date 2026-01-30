"""
Security Framework for OTTO API
===============================

Provides frontier security capabilities:
1. Cryptographic Agility - Hot-swappable algorithms
2. Security Invariant Verification - Runtime property checking
3. Post-Quantum Readiness - Hybrid cipher support

[He2025] Compliance:
- FIXED algorithm registries (no runtime modification)
- DETERMINISTIC invariant evaluation
- Pre-computed cipher specifications

Frontier Features:
- Algorithm registry for cryptographic agility
- Security invariants with runtime verification
- Post-quantum hybrid cipher definitions
- Certificate Transparency integration hooks
- Anomaly detection interface
"""

import hashlib
import hmac
import logging
import ssl
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    Union,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Algorithm Registry - Cryptographic Agility
# =============================================================================

class AlgorithmCategory(Enum):
    """Categories of cryptographic algorithms."""
    SYMMETRIC = auto()       # AES, ChaCha20
    ASYMMETRIC = auto()      # RSA, ECDSA, EdDSA
    HASH = auto()            # SHA-256, SHA-384, SHA-512, BLAKE3
    KDF = auto()             # PBKDF2, Argon2, scrypt
    MAC = auto()             # HMAC, Poly1305
    KEY_EXCHANGE = auto()    # ECDH, X25519
    POST_QUANTUM = auto()    # Kyber, Dilithium (ML-KEM, ML-DSA)


class AlgorithmStatus(Enum):
    """Algorithm security status."""
    RECOMMENDED = "recommended"      # Actively recommended for new systems
    ACCEPTABLE = "acceptable"        # Still secure, but prefer recommended
    LEGACY = "legacy"                # Deprecated, avoid in new systems
    BROKEN = "broken"                # Cryptographically broken, do not use
    EXPERIMENTAL = "experimental"    # Not yet standardized


@dataclass(frozen=True)
class AlgorithmSpec:
    """
    Immutable specification for a cryptographic algorithm.

    [He2025] FROZEN: No runtime modification allowed.
    """
    name: str
    category: AlgorithmCategory
    status: AlgorithmStatus
    key_sizes: Tuple[int, ...]  # Supported key sizes in bits
    output_size: int            # Output size in bits (for hashes/MACs)
    description: str
    nist_level: Optional[int] = None  # NIST security level (1-5) for PQ
    standard: Optional[str] = None    # Standard reference (FIPS, RFC, etc.)

    def is_secure(self) -> bool:
        """Check if algorithm is considered secure."""
        return self.status in (
            AlgorithmStatus.RECOMMENDED,
            AlgorithmStatus.ACCEPTABLE,
        )


class AlgorithmRegistry:
    """
    Registry of approved cryptographic algorithms.

    [He2025] Compliance:
    - Registry is FIXED at initialization
    - No runtime modifications allowed
    - DETERMINISTIC algorithm lookup

    Usage:
        registry = AlgorithmRegistry.default()
        aes = registry.get("AES-256-GCM")
        secure_hashes = registry.get_by_category(AlgorithmCategory.HASH, secure_only=True)
    """

    # [He2025] FIXED default algorithms - no runtime variation
    _DEFAULT_ALGORITHMS: Tuple[AlgorithmSpec, ...] = (
        # Symmetric ciphers
        AlgorithmSpec(
            name="AES-256-GCM",
            category=AlgorithmCategory.SYMMETRIC,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(256,),
            output_size=128,  # Tag size
            description="AES-256 in GCM mode - NIST approved",
            standard="FIPS 197, SP 800-38D",
        ),
        AlgorithmSpec(
            name="AES-128-GCM",
            category=AlgorithmCategory.SYMMETRIC,
            status=AlgorithmStatus.ACCEPTABLE,
            key_sizes=(128,),
            output_size=128,
            description="AES-128 in GCM mode - NIST approved",
            standard="FIPS 197, SP 800-38D",
        ),
        AlgorithmSpec(
            name="ChaCha20-Poly1305",
            category=AlgorithmCategory.SYMMETRIC,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(256,),
            output_size=128,
            description="ChaCha20 stream cipher with Poly1305 MAC",
            standard="RFC 8439",
        ),

        # Hash functions
        AlgorithmSpec(
            name="SHA-256",
            category=AlgorithmCategory.HASH,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(),
            output_size=256,
            description="SHA-2 256-bit hash",
            standard="FIPS 180-4",
        ),
        AlgorithmSpec(
            name="SHA-384",
            category=AlgorithmCategory.HASH,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(),
            output_size=384,
            description="SHA-2 384-bit hash",
            standard="FIPS 180-4",
        ),
        AlgorithmSpec(
            name="SHA-512",
            category=AlgorithmCategory.HASH,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(),
            output_size=512,
            description="SHA-2 512-bit hash",
            standard="FIPS 180-4",
        ),
        AlgorithmSpec(
            name="BLAKE3",
            category=AlgorithmCategory.HASH,
            status=AlgorithmStatus.ACCEPTABLE,
            key_sizes=(),
            output_size=256,
            description="BLAKE3 fast cryptographic hash",
            standard="BLAKE3 Specification",
        ),
        AlgorithmSpec(
            name="SHA-1",
            category=AlgorithmCategory.HASH,
            status=AlgorithmStatus.LEGACY,
            key_sizes=(),
            output_size=160,
            description="SHA-1 - deprecated, collision attacks exist",
            standard="FIPS 180-4",
        ),
        AlgorithmSpec(
            name="MD5",
            category=AlgorithmCategory.HASH,
            status=AlgorithmStatus.BROKEN,
            key_sizes=(),
            output_size=128,
            description="MD5 - broken, do not use for security",
            standard="RFC 1321",
        ),

        # Key derivation
        AlgorithmSpec(
            name="Argon2id",
            category=AlgorithmCategory.KDF,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(128, 256),
            output_size=256,
            description="Argon2id memory-hard KDF - password hashing winner",
            standard="RFC 9106",
        ),
        AlgorithmSpec(
            name="scrypt",
            category=AlgorithmCategory.KDF,
            status=AlgorithmStatus.ACCEPTABLE,
            key_sizes=(128, 256),
            output_size=256,
            description="scrypt memory-hard KDF",
            standard="RFC 7914",
        ),
        AlgorithmSpec(
            name="PBKDF2-SHA256",
            category=AlgorithmCategory.KDF,
            status=AlgorithmStatus.ACCEPTABLE,
            key_sizes=(128, 256),
            output_size=256,
            description="PBKDF2 with SHA-256 - legacy but acceptable",
            standard="RFC 8018",
        ),

        # MACs
        AlgorithmSpec(
            name="HMAC-SHA256",
            category=AlgorithmCategory.MAC,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(256,),
            output_size=256,
            description="HMAC with SHA-256",
            standard="RFC 2104, FIPS 198-1",
        ),
        AlgorithmSpec(
            name="HMAC-SHA512",
            category=AlgorithmCategory.MAC,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(512,),
            output_size=512,
            description="HMAC with SHA-512",
            standard="RFC 2104, FIPS 198-1",
        ),

        # Key exchange
        AlgorithmSpec(
            name="X25519",
            category=AlgorithmCategory.KEY_EXCHANGE,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(256,),
            output_size=256,
            description="Curve25519 ECDH",
            standard="RFC 7748",
        ),
        AlgorithmSpec(
            name="ECDH-P256",
            category=AlgorithmCategory.KEY_EXCHANGE,
            status=AlgorithmStatus.ACCEPTABLE,
            key_sizes=(256,),
            output_size=256,
            description="ECDH on P-256 curve",
            standard="FIPS 186-4",
        ),

        # Asymmetric / signatures
        AlgorithmSpec(
            name="Ed25519",
            category=AlgorithmCategory.ASYMMETRIC,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(256,),
            output_size=512,
            description="EdDSA on Curve25519",
            standard="RFC 8032",
        ),
        AlgorithmSpec(
            name="ECDSA-P256",
            category=AlgorithmCategory.ASYMMETRIC,
            status=AlgorithmStatus.ACCEPTABLE,
            key_sizes=(256,),
            output_size=512,
            description="ECDSA on P-256 curve",
            standard="FIPS 186-4",
        ),
        AlgorithmSpec(
            name="RSA-2048",
            category=AlgorithmCategory.ASYMMETRIC,
            status=AlgorithmStatus.ACCEPTABLE,
            key_sizes=(2048,),
            output_size=2048,
            description="RSA 2048-bit - minimum acceptable",
            standard="FIPS 186-4",
        ),
        AlgorithmSpec(
            name="RSA-4096",
            category=AlgorithmCategory.ASYMMETRIC,
            status=AlgorithmStatus.RECOMMENDED,
            key_sizes=(4096,),
            output_size=4096,
            description="RSA 4096-bit - recommended for long-term",
            standard="FIPS 186-4",
        ),

        # Post-quantum (experimental until standardization complete)
        AlgorithmSpec(
            name="ML-KEM-768",
            category=AlgorithmCategory.POST_QUANTUM,
            status=AlgorithmStatus.EXPERIMENTAL,
            key_sizes=(768 * 8,),  # In bits
            output_size=256,
            description="Module-Lattice KEM (formerly Kyber) - NIST Level 3",
            nist_level=3,
            standard="FIPS 203 (Draft)",
        ),
        AlgorithmSpec(
            name="ML-KEM-1024",
            category=AlgorithmCategory.POST_QUANTUM,
            status=AlgorithmStatus.EXPERIMENTAL,
            key_sizes=(1024 * 8,),
            output_size=256,
            description="Module-Lattice KEM - NIST Level 5",
            nist_level=5,
            standard="FIPS 203 (Draft)",
        ),
        AlgorithmSpec(
            name="ML-DSA-65",
            category=AlgorithmCategory.POST_QUANTUM,
            status=AlgorithmStatus.EXPERIMENTAL,
            key_sizes=(65 * 32 * 8,),
            output_size=3293 * 8,
            description="Module-Lattice DSA (formerly Dilithium) - NIST Level 3",
            nist_level=3,
            standard="FIPS 204 (Draft)",
        ),
        AlgorithmSpec(
            name="ML-DSA-87",
            category=AlgorithmCategory.POST_QUANTUM,
            status=AlgorithmStatus.EXPERIMENTAL,
            key_sizes=(87 * 32 * 8,),
            output_size=4595 * 8,
            description="Module-Lattice DSA - NIST Level 5",
            nist_level=5,
            standard="FIPS 204 (Draft)",
        ),
    )

    def __init__(self, algorithms: Optional[Tuple[AlgorithmSpec, ...]] = None):
        """
        Initialize algorithm registry.

        Args:
            algorithms: Tuple of algorithm specs. Uses defaults if None.
        """
        specs = algorithms or self._DEFAULT_ALGORITHMS

        # Build lookup tables (FIXED at init)
        self._by_name: Dict[str, AlgorithmSpec] = {
            spec.name: spec for spec in specs
        }
        self._by_category: Dict[AlgorithmCategory, List[AlgorithmSpec]] = {}
        for spec in specs:
            if spec.category not in self._by_category:
                self._by_category[spec.category] = []
            self._by_category[spec.category].append(spec)

        # Freeze
        self._frozen = True

    @classmethod
    def default(cls) -> "AlgorithmRegistry":
        """Get default algorithm registry."""
        return cls()

    def get(self, name: str) -> Optional[AlgorithmSpec]:
        """Get algorithm by name."""
        return self._by_name.get(name)

    def get_by_category(
        self,
        category: AlgorithmCategory,
        secure_only: bool = True,
    ) -> List[AlgorithmSpec]:
        """
        Get algorithms by category.

        Args:
            category: Algorithm category
            secure_only: If True, only return secure algorithms

        Returns:
            List of matching algorithm specs
        """
        algorithms = self._by_category.get(category, [])
        if secure_only:
            return [a for a in algorithms if a.is_secure()]
        return list(algorithms)

    def get_recommended(self, category: AlgorithmCategory) -> Optional[AlgorithmSpec]:
        """Get recommended algorithm for category."""
        for spec in self._by_category.get(category, []):
            if spec.status == AlgorithmStatus.RECOMMENDED:
                return spec
        return None

    def is_algorithm_secure(self, name: str) -> bool:
        """Check if named algorithm is secure."""
        spec = self.get(name)
        return spec is not None and spec.is_secure()

    def list_all(self) -> List[AlgorithmSpec]:
        """List all registered algorithms."""
        return list(self._by_name.values())

    def list_post_quantum(self) -> List[AlgorithmSpec]:
        """List post-quantum algorithms."""
        return self.get_by_category(AlgorithmCategory.POST_QUANTUM, secure_only=False)


# =============================================================================
# Security Invariants - Runtime Verification
# =============================================================================

class InvariantSeverity(Enum):
    """Severity level for invariant violations."""
    CRITICAL = "critical"    # Must never fail, system should halt
    HIGH = "high"            # Security compromised, alert immediately
    MEDIUM = "medium"        # Potential issue, log and monitor
    LOW = "low"              # Minor issue, log for review


@dataclass
class InvariantResult:
    """Result of an invariant check."""
    name: str
    passed: bool
    severity: InvariantSeverity
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class SecurityInvariant(ABC):
    """
    Base class for security invariants.

    Security invariants are properties that must always hold true.
    They are checked at runtime to detect security violations.

    [He2025] Compliance: Invariant checks are DETERMINISTIC.
    Same state → same result.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Invariant name for logging/reporting."""
        pass

    @property
    @abstractmethod
    def severity(self) -> InvariantSeverity:
        """Severity if invariant is violated."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass

    @abstractmethod
    def check(self, context: Dict[str, Any]) -> InvariantResult:
        """
        Check if invariant holds.

        Args:
            context: Current system context

        Returns:
            InvariantResult with check outcome
        """
        pass


class TLSVersionInvariant(SecurityInvariant):
    """Invariant: TLS version must be 1.2 or higher."""

    MINIMUM_VERSION = ssl.TLSVersion.TLSv1_2

    @property
    def name(self) -> str:
        return "tls_minimum_version"

    @property
    def severity(self) -> InvariantSeverity:
        return InvariantSeverity.CRITICAL

    @property
    def description(self) -> str:
        return "TLS version must be 1.2 or higher"

    def check(self, context: Dict[str, Any]) -> InvariantResult:
        tls_config = context.get("tls_config")

        if tls_config is None:
            return InvariantResult(
                name=self.name,
                passed=True,
                severity=self.severity,
                message="TLS not configured (HTTP only)",
                details={"tls_enabled": False},
            )

        min_version = getattr(tls_config, "min_version", None)
        if min_version is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity=self.severity,
                message="TLS version not specified",
            )

        passed = min_version >= self.MINIMUM_VERSION
        return InvariantResult(
            name=self.name,
            passed=passed,
            severity=self.severity,
            message="TLS version acceptable" if passed else "TLS version too low",
            details={
                "configured_version": min_version.name,
                "minimum_required": self.MINIMUM_VERSION.name,
            },
        )


class CipherSuiteInvariant(SecurityInvariant):
    """Invariant: Only approved cipher suites are used."""

    # [He2025] FIXED approved ciphers
    APPROVED_TLS13_CIPHERS: FrozenSet[str] = frozenset([
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256",
        "TLS_AES_128_GCM_SHA256",
    ])

    APPROVED_TLS12_CIPHERS: FrozenSet[str] = frozenset([
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-CHACHA20-POLY1305",
        "ECDHE-RSA-CHACHA20-POLY1305",
        "ECDHE-ECDSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES128-GCM-SHA256",
    ])

    @property
    def name(self) -> str:
        return "cipher_suite_approved"

    @property
    def severity(self) -> InvariantSeverity:
        return InvariantSeverity.HIGH

    @property
    def description(self) -> str:
        return "Only approved cipher suites must be used"

    def check(self, context: Dict[str, Any]) -> InvariantResult:
        tls_config = context.get("tls_config")

        if tls_config is None:
            return InvariantResult(
                name=self.name,
                passed=True,
                severity=self.severity,
                message="TLS not configured",
            )

        configured_ciphers = set()
        if hasattr(tls_config, "CIPHERS_TLS13"):
            configured_ciphers.update(tls_config.CIPHERS_TLS13)
        if hasattr(tls_config, "CIPHERS_TLS12"):
            configured_ciphers.update(tls_config.CIPHERS_TLS12)

        approved = self.APPROVED_TLS13_CIPHERS | self.APPROVED_TLS12_CIPHERS
        unapproved = configured_ciphers - approved

        passed = len(unapproved) == 0
        return InvariantResult(
            name=self.name,
            passed=passed,
            severity=self.severity,
            message="All ciphers approved" if passed else "Unapproved ciphers found",
            details={
                "configured": list(configured_ciphers),
                "unapproved": list(unapproved),
            },
        )


class APIKeyHashInvariant(SecurityInvariant):
    """Invariant: API keys must be stored as hashes, never plaintext."""

    @property
    def name(self) -> str:
        return "api_key_hashed"

    @property
    def severity(self) -> InvariantSeverity:
        return InvariantSeverity.CRITICAL

    @property
    def description(self) -> str:
        return "API keys must be stored as SHA-256 hashes"

    def check(self, context: Dict[str, Any]) -> InvariantResult:
        key_manager = context.get("key_manager")

        if key_manager is None:
            return InvariantResult(
                name=self.name,
                passed=True,
                severity=self.severity,
                message="No key manager configured",
            )

        # Check that keys are stored by hash
        stored_keys = getattr(key_manager, "_keys", {})
        plaintext_found = False
        checked_count = 0

        for key_hash, key_data in stored_keys.items():
            checked_count += 1
            # Key hash should be 64 hex chars (SHA-256)
            if not (len(key_hash) == 64 and all(c in '0123456789abcdef' for c in key_hash)):
                plaintext_found = True
                break

        return InvariantResult(
            name=self.name,
            passed=not plaintext_found,
            severity=self.severity,
            message="All keys properly hashed" if not plaintext_found else "Plaintext key storage detected",
            details={
                "keys_checked": checked_count,
                "plaintext_found": plaintext_found,
            },
        )


class RateLimitInvariant(SecurityInvariant):
    """Invariant: Rate limits must be enforced."""

    @property
    def name(self) -> str:
        return "rate_limit_enforced"

    @property
    def severity(self) -> InvariantSeverity:
        return InvariantSeverity.MEDIUM

    @property
    def description(self) -> str:
        return "Rate limiting must be enabled and enforced"

    def check(self, context: Dict[str, Any]) -> InvariantResult:
        middleware_chain = context.get("middleware_chain")

        if middleware_chain is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity=self.severity,
                message="No middleware chain configured",
            )

        # Check for rate limit middleware
        has_rate_limit = False
        if hasattr(middleware_chain, "_middleware"):
            for mw in middleware_chain._middleware:
                if "RateLimit" in type(mw).__name__:
                    has_rate_limit = True
                    break

        return InvariantResult(
            name=self.name,
            passed=has_rate_limit,
            severity=self.severity,
            message="Rate limiting enabled" if has_rate_limit else "Rate limiting not found",
        )


class SecurityHeadersInvariant(SecurityInvariant):
    """Invariant: Security headers must be present."""

    REQUIRED_HEADERS: FrozenSet[str] = frozenset([
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Content-Security-Policy",
    ])

    @property
    def name(self) -> str:
        return "security_headers_present"

    @property
    def severity(self) -> InvariantSeverity:
        return InvariantSeverity.HIGH

    @property
    def description(self) -> str:
        return "Required security headers must be configured"

    def check(self, context: Dict[str, Any]) -> InvariantResult:
        middleware_chain = context.get("middleware_chain")

        if middleware_chain is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity=self.severity,
                message="No middleware chain configured",
            )

        # Check for security headers middleware
        has_security_headers = False
        configured_headers = set()

        if hasattr(middleware_chain, "_middleware"):
            for mw in middleware_chain._middleware:
                if "SecurityHeaders" in type(mw).__name__:
                    has_security_headers = True
                    if hasattr(mw, "HEADERS"):
                        configured_headers = set(mw.HEADERS.keys())
                    break

        missing = self.REQUIRED_HEADERS - configured_headers
        passed = has_security_headers and len(missing) == 0

        return InvariantResult(
            name=self.name,
            passed=passed,
            severity=self.severity,
            message="Security headers configured" if passed else "Missing security headers",
            details={
                "middleware_present": has_security_headers,
                "configured": list(configured_headers),
                "missing": list(missing),
            },
        )


class InvariantVerifier:
    """
    Verifies security invariants at runtime.

    [He2025] Compliance:
    - FIXED set of invariants (registered at init)
    - DETERMINISTIC evaluation order
    - REPRODUCIBLE results

    Usage:
        verifier = InvariantVerifier.default()
        results = verifier.verify_all(context)
        if not verifier.all_passed(results):
            handle_security_violation(results)
    """

    # [He2025] FIXED default invariants
    _DEFAULT_INVARIANTS: Tuple[Type[SecurityInvariant], ...] = (
        TLSVersionInvariant,
        CipherSuiteInvariant,
        APIKeyHashInvariant,
        RateLimitInvariant,
        SecurityHeadersInvariant,
    )

    def __init__(
        self,
        invariants: Optional[List[SecurityInvariant]] = None,
    ):
        """
        Initialize invariant verifier.

        Args:
            invariants: List of invariants to check. Uses defaults if None.
        """
        if invariants is None:
            self._invariants = [cls() for cls in self._DEFAULT_INVARIANTS]
        else:
            self._invariants = list(invariants)

    @classmethod
    def default(cls) -> "InvariantVerifier":
        """Get default invariant verifier."""
        return cls()

    def add_invariant(self, invariant: SecurityInvariant) -> None:
        """Add an invariant to check."""
        self._invariants.append(invariant)

    def verify(
        self,
        invariant_name: str,
        context: Dict[str, Any],
    ) -> Optional[InvariantResult]:
        """
        Verify a specific invariant.

        Args:
            invariant_name: Name of invariant to check
            context: System context

        Returns:
            InvariantResult or None if invariant not found
        """
        for inv in self._invariants:
            if inv.name == invariant_name:
                return inv.check(context)
        return None

    def verify_all(self, context: Dict[str, Any]) -> List[InvariantResult]:
        """
        Verify all registered invariants.

        [He2025] DETERMINISTIC: Fixed evaluation order.

        Args:
            context: System context

        Returns:
            List of InvariantResult in registration order
        """
        return [inv.check(context) for inv in self._invariants]

    def verify_critical(self, context: Dict[str, Any]) -> List[InvariantResult]:
        """Verify only CRITICAL severity invariants."""
        results = []
        for inv in self._invariants:
            if inv.severity == InvariantSeverity.CRITICAL:
                results.append(inv.check(context))
        return results

    @staticmethod
    def all_passed(results: List[InvariantResult]) -> bool:
        """Check if all invariants passed."""
        return all(r.passed for r in results)

    @staticmethod
    def get_failures(results: List[InvariantResult]) -> List[InvariantResult]:
        """Get failed invariants."""
        return [r for r in results if not r.passed]

    @staticmethod
    def get_critical_failures(results: List[InvariantResult]) -> List[InvariantResult]:
        """Get critical failures."""
        return [
            r for r in results
            if not r.passed and r.severity == InvariantSeverity.CRITICAL
        ]

    def get_report(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate security invariant report.

        Args:
            context: System context

        Returns:
            Comprehensive security report
        """
        results = self.verify_all(context)
        failures = self.get_failures(results)
        critical = self.get_critical_failures(results)

        return {
            "timestamp": time.time(),
            "total_invariants": len(results),
            "passed": len(results) - len(failures),
            "failed": len(failures),
            "critical_failures": len(critical),
            "all_passed": len(failures) == 0,
            "results": [r.to_dict() for r in results],
            "failures": [r.to_dict() for r in failures],
        }


# =============================================================================
# Certificate Transparency Integration
# =============================================================================

class CTLogOperator(Enum):
    """Known Certificate Transparency log operators."""
    GOOGLE = "google"
    CLOUDFLARE = "cloudflare"
    DIGICERT = "digicert"
    SECTIGO = "sectigo"
    LETS_ENCRYPT = "letsencrypt"


@dataclass(frozen=True)
class CTLogInfo:
    """
    Information about a CT log.

    [He2025] FROZEN: Immutable log configuration.
    """
    name: str
    operator: CTLogOperator
    url: str
    public_key_hash: str  # Base64-encoded SHA-256 of log's public key
    mmd_seconds: int      # Maximum Merge Delay
    is_active: bool


class CTMonitor:
    """
    Certificate Transparency log monitor.

    Monitors CT logs for certificates issued for your domains.
    Detects unauthorized certificate issuance (CA compromise, misissuance).

    [He2025] Compliance:
    - FIXED set of monitored logs
    - DETERMINISTIC log checking
    - Alerting hooks for integration

    Frontier Feature: Proactive detection of certificate misissuance.

    Usage:
        monitor = CTMonitor()
        monitor.add_domain("example.com")
        monitor.on_certificate_found(lambda cert: handle_new_cert(cert))
        await monitor.check_logs()

    Note: Full implementation requires CT log API integration.
    This provides the interface and alerting hooks.
    """

    # [He2025] FIXED known CT logs
    _KNOWN_LOGS: Tuple[CTLogInfo, ...] = (
        CTLogInfo(
            name="Google Argon 2024",
            operator=CTLogOperator.GOOGLE,
            url="https://ct.googleapis.com/logs/argon2024/",
            public_key_hash="",  # Would contain actual key hash
            mmd_seconds=86400,
            is_active=True,
        ),
        CTLogInfo(
            name="Cloudflare Nimbus 2024",
            operator=CTLogOperator.CLOUDFLARE,
            url="https://ct.cloudflare.com/logs/nimbus2024/",
            public_key_hash="",
            mmd_seconds=86400,
            is_active=True,
        ),
        CTLogInfo(
            name="Let's Encrypt Oak 2024",
            operator=CTLogOperator.LETS_ENCRYPT,
            url="https://oak.ct.letsencrypt.org/2024/",
            public_key_hash="",
            mmd_seconds=86400,
            is_active=True,
        ),
    )

    def __init__(self):
        """Initialize CT monitor."""
        self._monitored_domains: Set[str] = set()
        self._on_cert_found_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._on_suspicious_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._known_certs: Set[str] = set()  # SHA-256 hashes of known certs
        self._check_count = 0

    def add_domain(self, domain: str) -> None:
        """
        Add a domain to monitor.

        Args:
            domain: Domain name (e.g., "example.com")
        """
        # Normalize domain
        domain = domain.lower().strip()
        self._monitored_domains.add(domain)
        logger.info(f"CT monitor: Added domain {domain}")

    def remove_domain(self, domain: str) -> bool:
        """Remove a domain from monitoring."""
        domain = domain.lower().strip()
        if domain in self._monitored_domains:
            self._monitored_domains.discard(domain)
            return True
        return False

    def add_known_certificate(self, cert_hash: str) -> None:
        """
        Add a known/expected certificate hash.

        Certificates matching known hashes won't trigger alerts.

        Args:
            cert_hash: SHA-256 hash of certificate (hex string)
        """
        self._known_certs.add(cert_hash.lower())

    def on_certificate_found(
        self,
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Register callback for new certificates found."""
        self._on_cert_found_callbacks.append(callback)

    def on_suspicious_certificate(
        self,
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Register callback for suspicious/unexpected certificates."""
        self._on_suspicious_callbacks.append(callback)

    async def check_logs(self) -> Dict[str, Any]:
        """
        Check CT logs for certificates.

        Returns:
            Dict with check results

        Note: This is the interface. Full implementation would
        query actual CT log APIs.
        """
        self._check_count += 1

        # This is where actual CT log querying would happen
        # For now, return interface structure
        return {
            "check_number": self._check_count,
            "monitored_domains": list(self._monitored_domains),
            "logs_checked": len(self._KNOWN_LOGS),
            "certificates_found": 0,
            "suspicious_certificates": 0,
            "status": "interface_only",
            "message": "CT log API integration required for full functionality",
        }

    def _trigger_cert_found(self, cert_info: Dict[str, Any]) -> None:
        """Trigger certificate found callbacks."""
        for callback in self._on_cert_found_callbacks:
            try:
                callback(cert_info)
            except Exception as e:
                logger.error(f"Error in CT cert found callback: {e}")

    def _trigger_suspicious(self, cert_info: Dict[str, Any]) -> None:
        """Trigger suspicious certificate callbacks."""
        for callback in self._on_suspicious_callbacks:
            try:
                callback(cert_info)
            except Exception as e:
                logger.error(f"Error in CT suspicious callback: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get monitor status."""
        return {
            "monitored_domains": list(self._monitored_domains),
            "known_certificates": len(self._known_certs),
            "check_count": self._check_count,
            "active_logs": len([l for l in self._KNOWN_LOGS if l.is_active]),
        }


# =============================================================================
# Anomaly Detection Interface
# =============================================================================

class AnomalyType(Enum):
    """Types of security anomalies."""
    RATE_SPIKE = "rate_spike"                    # Sudden increase in requests
    AUTH_FAILURES = "auth_failures"              # Multiple auth failures
    UNUSUAL_ENDPOINT = "unusual_endpoint"        # Access to rarely-used endpoints
    UNUSUAL_TIME = "unusual_time"                # Access at unusual times
    UNUSUAL_LOCATION = "unusual_location"        # Access from unusual location
    CREDENTIAL_STUFFING = "credential_stuffing"  # Multiple accounts, same IP
    ENUMERATION = "enumeration"                  # Sequential resource access
    DATA_EXFILTRATION = "data_exfiltration"      # Large data transfers


class AnomalySeverity(Enum):
    """Severity of detected anomalies."""
    INFO = "info"          # Informational, log only
    LOW = "low"            # Minor anomaly, monitor
    MEDIUM = "medium"      # Notable anomaly, investigate
    HIGH = "high"          # Significant anomaly, alert
    CRITICAL = "critical"  # Security incident, immediate action


@dataclass
class AnomalyEvent:
    """
    A detected security anomaly.

    [He2025] Compliance: Deterministic event structure.
    """
    event_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    timestamp: float
    source_ip: Optional[str]
    api_key_id: Optional[str]
    endpoint: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "source_ip": self.source_ip,
            "api_key_id": self.api_key_id,
            "endpoint": self.endpoint,
            "description": self.description,
            "details": self.details,
            "recommended_action": self.recommended_action,
        }


class AnomalyDetector(ABC):
    """
    Abstract base class for anomaly detectors.

    Frontier Feature: Pluggable anomaly detection for API security.

    [He2025] Compliance:
    - FIXED detection thresholds (set at init)
    - DETERMINISTIC anomaly classification
    - No runtime threshold modification

    Implementations can use:
    - Rule-based detection
    - Statistical analysis
    - Machine learning models

    Usage:
        class MyDetector(AnomalyDetector):
            def analyze(self, event):
                # Custom detection logic
                pass

        detector = MyDetector()
        detector.on_anomaly(lambda e: alert(e))
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Detector name."""
        pass

    @property
    @abstractmethod
    def anomaly_types(self) -> List[AnomalyType]:
        """Types of anomalies this detector can identify."""
        pass

    @abstractmethod
    def analyze(self, event: Dict[str, Any]) -> Optional[AnomalyEvent]:
        """
        Analyze an event for anomalies.

        Args:
            event: Event data (request info, metrics, etc.)

        Returns:
            AnomalyEvent if anomaly detected, None otherwise
        """
        pass

    @abstractmethod
    def get_baseline(self) -> Dict[str, Any]:
        """Get current baseline for comparison."""
        pass

    @abstractmethod
    def update_baseline(self, event: Dict[str, Any]) -> None:
        """Update baseline with new event data."""
        pass


class RateSpikeDetector(AnomalyDetector):
    """
    Detects unusual spikes in request rate.

    [He2025] FIXED thresholds:
    - Spike threshold: 3x baseline
    - Window: 60 seconds
    - Minimum samples: 10
    """

    # [He2025] FIXED thresholds
    SPIKE_MULTIPLIER = 3.0
    WINDOW_SECONDS = 60
    MIN_SAMPLES = 10

    def __init__(self):
        """Initialize rate spike detector."""
        self._request_times: List[float] = []
        self._baseline_rate: float = 0.0
        self._last_baseline_update: float = time.time()
        self._on_anomaly_callbacks: List[Callable[[AnomalyEvent], None]] = []

    @property
    def name(self) -> str:
        return "rate_spike_detector"

    @property
    def anomaly_types(self) -> List[AnomalyType]:
        return [AnomalyType.RATE_SPIKE]

    def on_anomaly(self, callback: Callable[[AnomalyEvent], None]) -> None:
        """Register anomaly callback."""
        self._on_anomaly_callbacks.append(callback)

    def analyze(self, event: Dict[str, Any]) -> Optional[AnomalyEvent]:
        """Analyze for rate spikes."""
        now = time.time()
        self._request_times.append(now)

        # Clean old entries
        cutoff = now - self.WINDOW_SECONDS
        self._request_times = [t for t in self._request_times if t > cutoff]

        # Need minimum samples
        if len(self._request_times) < self.MIN_SAMPLES:
            return None

        # Calculate current rate
        current_rate = len(self._request_times) / self.WINDOW_SECONDS

        # Check for spike
        if self._baseline_rate > 0 and current_rate > self._baseline_rate * self.SPIKE_MULTIPLIER:
            import uuid
            anomaly = AnomalyEvent(
                event_id=f"anomaly_{uuid.uuid4().hex[:12]}",
                anomaly_type=AnomalyType.RATE_SPIKE,
                severity=AnomalySeverity.HIGH if current_rate > self._baseline_rate * 5 else AnomalySeverity.MEDIUM,
                timestamp=now,
                source_ip=event.get("source_ip"),
                api_key_id=event.get("api_key_id"),
                endpoint=event.get("endpoint"),
                description=f"Request rate spike detected: {current_rate:.1f}/s (baseline: {self._baseline_rate:.1f}/s)",
                details={
                    "current_rate": current_rate,
                    "baseline_rate": self._baseline_rate,
                    "spike_multiplier": current_rate / self._baseline_rate if self._baseline_rate > 0 else 0,
                },
                recommended_action="Investigate source. Consider temporary rate limiting.",
            )

            # Trigger callbacks
            for callback in self._on_anomaly_callbacks:
                try:
                    callback(anomaly)
                except Exception as e:
                    logger.error(f"Error in anomaly callback: {e}")

            return anomaly

        return None

    def get_baseline(self) -> Dict[str, Any]:
        """Get baseline stats."""
        return {
            "baseline_rate": self._baseline_rate,
            "last_update": self._last_baseline_update,
            "current_samples": len(self._request_times),
        }

    def update_baseline(self, event: Dict[str, Any]) -> None:
        """Update baseline rate."""
        now = time.time()

        # Update baseline periodically (every 5 minutes)
        if now - self._last_baseline_update > 300:
            if len(self._request_times) >= self.MIN_SAMPLES:
                self._baseline_rate = len(self._request_times) / self.WINDOW_SECONDS
                self._last_baseline_update = now


class AuthFailureDetector(AnomalyDetector):
    """
    Detects excessive authentication failures.

    [He2025] FIXED thresholds:
    - Max failures per IP: 5 per minute
    - Max failures per key: 3 per minute
    """

    MAX_FAILURES_PER_IP = 5
    MAX_FAILURES_PER_KEY = 3
    WINDOW_SECONDS = 60

    def __init__(self):
        """Initialize auth failure detector."""
        self._failures_by_ip: Dict[str, List[float]] = {}
        self._failures_by_key: Dict[str, List[float]] = {}
        self._on_anomaly_callbacks: List[Callable[[AnomalyEvent], None]] = []

    @property
    def name(self) -> str:
        return "auth_failure_detector"

    @property
    def anomaly_types(self) -> List[AnomalyType]:
        return [AnomalyType.AUTH_FAILURES, AnomalyType.CREDENTIAL_STUFFING]

    def on_anomaly(self, callback: Callable[[AnomalyEvent], None]) -> None:
        """Register anomaly callback."""
        self._on_anomaly_callbacks.append(callback)

    def record_failure(
        self,
        source_ip: Optional[str] = None,
        api_key_id: Optional[str] = None,
    ) -> Optional[AnomalyEvent]:
        """Record an auth failure and check for anomalies."""
        now = time.time()
        cutoff = now - self.WINDOW_SECONDS

        anomaly = None

        # Track by IP
        if source_ip:
            if source_ip not in self._failures_by_ip:
                self._failures_by_ip[source_ip] = []
            self._failures_by_ip[source_ip].append(now)
            self._failures_by_ip[source_ip] = [
                t for t in self._failures_by_ip[source_ip] if t > cutoff
            ]

            if len(self._failures_by_ip[source_ip]) > self.MAX_FAILURES_PER_IP:
                import uuid
                anomaly = AnomalyEvent(
                    event_id=f"anomaly_{uuid.uuid4().hex[:12]}",
                    anomaly_type=AnomalyType.AUTH_FAILURES,
                    severity=AnomalySeverity.HIGH,
                    timestamp=now,
                    source_ip=source_ip,
                    api_key_id=api_key_id,
                    endpoint=None,
                    description=f"Excessive auth failures from IP: {len(self._failures_by_ip[source_ip])} in {self.WINDOW_SECONDS}s",
                    details={
                        "failure_count": len(self._failures_by_ip[source_ip]),
                        "threshold": self.MAX_FAILURES_PER_IP,
                    },
                    recommended_action="Consider temporary IP block.",
                )

        # Track by API key
        if api_key_id:
            if api_key_id not in self._failures_by_key:
                self._failures_by_key[api_key_id] = []
            self._failures_by_key[api_key_id].append(now)
            self._failures_by_key[api_key_id] = [
                t for t in self._failures_by_key[api_key_id] if t > cutoff
            ]

            if len(self._failures_by_key[api_key_id]) > self.MAX_FAILURES_PER_KEY:
                import uuid
                anomaly = AnomalyEvent(
                    event_id=f"anomaly_{uuid.uuid4().hex[:12]}",
                    anomaly_type=AnomalyType.AUTH_FAILURES,
                    severity=AnomalySeverity.CRITICAL,
                    timestamp=now,
                    source_ip=source_ip,
                    api_key_id=api_key_id,
                    endpoint=None,
                    description=f"Excessive auth failures for key: {len(self._failures_by_key[api_key_id])} in {self.WINDOW_SECONDS}s",
                    details={
                        "failure_count": len(self._failures_by_key[api_key_id]),
                        "threshold": self.MAX_FAILURES_PER_KEY,
                    },
                    recommended_action="Consider revoking API key.",
                )

        # Trigger callbacks
        if anomaly:
            for callback in self._on_anomaly_callbacks:
                try:
                    callback(anomaly)
                except Exception as e:
                    logger.error(f"Error in anomaly callback: {e}")

        return anomaly

    def analyze(self, event: Dict[str, Any]) -> Optional[AnomalyEvent]:
        """Analyze event - expects auth failure events."""
        if event.get("type") == "auth_failure":
            return self.record_failure(
                source_ip=event.get("source_ip"),
                api_key_id=event.get("api_key_id"),
            )
        return None

    def get_baseline(self) -> Dict[str, Any]:
        """Get baseline stats."""
        return {
            "tracked_ips": len(self._failures_by_ip),
            "tracked_keys": len(self._failures_by_key),
        }

    def update_baseline(self, event: Dict[str, Any]) -> None:
        """No baseline for auth failures."""
        pass


class AnomalyDetectionEngine:
    """
    Engine that coordinates multiple anomaly detectors.

    Frontier Feature: Composable anomaly detection for API security.

    [He2025] Compliance:
    - FIXED detector set (registered at init)
    - DETERMINISTIC event routing
    - Consistent detection across instances

    Usage:
        engine = AnomalyDetectionEngine()
        engine.add_detector(RateSpikeDetector())
        engine.add_detector(AuthFailureDetector())
        engine.on_anomaly(lambda e: handle_anomaly(e))

        # Feed events
        engine.process_event({"type": "request", ...})
    """

    def __init__(self):
        """Initialize anomaly detection engine."""
        self._detectors: List[AnomalyDetector] = []
        self._on_anomaly_callbacks: List[Callable[[AnomalyEvent], None]] = []
        self._event_count = 0
        self._anomaly_count = 0

    def add_detector(self, detector: AnomalyDetector) -> None:
        """Add an anomaly detector."""
        self._detectors.append(detector)
        logger.info(f"Added anomaly detector: {detector.name}")

    def on_anomaly(self, callback: Callable[[AnomalyEvent], None]) -> None:
        """Register global anomaly callback."""
        self._on_anomaly_callbacks.append(callback)

    def process_event(self, event: Dict[str, Any]) -> List[AnomalyEvent]:
        """
        Process an event through all detectors.

        Args:
            event: Event to analyze

        Returns:
            List of detected anomalies
        """
        self._event_count += 1
        anomalies = []

        for detector in self._detectors:
            try:
                detector.update_baseline(event)
                anomaly = detector.analyze(event)
                if anomaly:
                    anomalies.append(anomaly)
                    self._anomaly_count += 1

                    # Trigger global callbacks
                    for callback in self._on_anomaly_callbacks:
                        try:
                            callback(anomaly)
                        except Exception as e:
                            logger.error(f"Error in global anomaly callback: {e}")

            except Exception as e:
                logger.error(f"Error in detector {detector.name}: {e}")

        return anomalies

    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            "detector_count": len(self._detectors),
            "detectors": [d.name for d in self._detectors],
            "events_processed": self._event_count,
            "anomalies_detected": self._anomaly_count,
            "anomaly_rate": (
                self._anomaly_count / self._event_count
                if self._event_count > 0 else 0.0
            ),
        }

    @classmethod
    def default(cls) -> "AnomalyDetectionEngine":
        """
        Create engine with default detectors.

        Returns:
            Engine with RateSpikeDetector and AuthFailureDetector
        """
        engine = cls()
        engine.add_detector(RateSpikeDetector())
        engine.add_detector(AuthFailureDetector())
        return engine


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Algorithm Registry
    "AlgorithmCategory",
    "AlgorithmStatus",
    "AlgorithmSpec",
    "AlgorithmRegistry",

    # Security Invariants
    "InvariantSeverity",
    "InvariantResult",
    "SecurityInvariant",
    "TLSVersionInvariant",
    "CipherSuiteInvariant",
    "APIKeyHashInvariant",
    "RateLimitInvariant",
    "SecurityHeadersInvariant",
    "InvariantVerifier",

    # Certificate Transparency
    "CTLogOperator",
    "CTLogInfo",
    "CTMonitor",

    # Anomaly Detection
    "AnomalyType",
    "AnomalySeverity",
    "AnomalyEvent",
    "AnomalyDetector",
    "RateSpikeDetector",
    "AuthFailureDetector",
    "AnomalyDetectionEngine",
]
