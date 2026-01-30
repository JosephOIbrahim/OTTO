"""
TLS Configuration for OTTO API
==============================

Provides TLS/HTTPS configuration for secure API communication.

[He2025] Compliance:
- FIXED cipher suites (no runtime negotiation variance)
- FIXED TLS version (TLS 1.3 minimum)
- DETERMINISTIC certificate validation

Features:
- TLS 1.3 enforcement
- Strong cipher suite selection
- Certificate loading and validation
- Self-signed certificate generation for development
- Certificate expiry monitoring
"""

import logging
import os
import ssl
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# TLS Configuration
# =============================================================================

@dataclass
class TLSConfig:
    """
    TLS configuration for HTTPS.

    [He2025] Compliance: FIXED cipher suites and TLS version.
    No runtime variation in security parameters.

    Attributes:
        cert_file: Path to certificate file (PEM format)
        key_file: Path to private key file (PEM format)
        ca_file: Path to CA certificate file (optional, for client cert validation)
        min_version: Minimum TLS version (default: TLS 1.3)
        verify_client: Whether to require client certificates
        check_hostname: Whether to verify hostname in certificates
    """

    cert_file: Optional[Path] = None
    key_file: Optional[Path] = None
    ca_file: Optional[Path] = None
    min_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_3
    verify_client: bool = False
    check_hostname: bool = True

    # [He2025] FIXED cipher suites - no runtime variation
    # These are the recommended TLS 1.3 cipher suites
    CIPHERS_TLS13: List[str] = field(default_factory=lambda: [
        "TLS_AES_256_GCM_SHA384",
        "TLS_CHACHA20_POLY1305_SHA256",
        "TLS_AES_128_GCM_SHA256",
    ])

    # Fallback for TLS 1.2 (if needed for compatibility)
    CIPHERS_TLS12: List[str] = field(default_factory=lambda: [
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-CHACHA20-POLY1305",
        "ECDHE-RSA-CHACHA20-POLY1305",
        "ECDHE-ECDSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES128-GCM-SHA256",
    ])

    def create_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context for server.

        Returns:
            Configured SSLContext for HTTPS server

        Raises:
            TLSConfigError: If configuration is invalid
        """
        # Create context for server
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

        # Set minimum TLS version
        context.minimum_version = self.min_version

        # Disable older protocols explicitly
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1

        # Set cipher suites
        cipher_string = self._build_cipher_string()
        try:
            context.set_ciphers(cipher_string)
        except ssl.SSLError as e:
            logger.warning(f"Failed to set ciphers '{cipher_string}': {e}")
            # Fall back to default secure ciphers
            pass

        # Load certificate and key if provided
        if self.cert_file and self.key_file:
            self._load_certificate(context)

        # Configure client certificate verification
        if self.verify_client:
            context.verify_mode = ssl.CERT_REQUIRED
            if self.ca_file:
                context.load_verify_locations(str(self.ca_file))
        else:
            context.verify_mode = ssl.CERT_NONE

        # Security options
        context.check_hostname = self.check_hostname if self.verify_client else False

        return context

    def create_client_context(self) -> ssl.SSLContext:
        """
        Create SSL context for client connections.

        Returns:
            Configured SSLContext for HTTPS client
        """
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        # Set minimum TLS version
        context.minimum_version = self.min_version

        # Disable older protocols
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1

        # Set cipher suites
        cipher_string = self._build_cipher_string()
        try:
            context.set_ciphers(cipher_string)
        except ssl.SSLError:
            pass  # Use defaults

        # Load CA certificates for verification
        if self.ca_file:
            context.load_verify_locations(str(self.ca_file))
        else:
            # Use system certificates
            context.load_default_certs()

        context.check_hostname = self.check_hostname
        context.verify_mode = ssl.CERT_REQUIRED

        return context

    def _build_cipher_string(self) -> str:
        """Build OpenSSL cipher string."""
        ciphers = []

        # TLS 1.3 ciphers (Python 3.7+)
        if self.min_version >= ssl.TLSVersion.TLSv1_3:
            ciphers.extend(self.CIPHERS_TLS13)
        else:
            # Include both TLS 1.3 and 1.2 ciphers
            ciphers.extend(self.CIPHERS_TLS13)
            ciphers.extend(self.CIPHERS_TLS12)

        return ":".join(ciphers)

    def _load_certificate(self, context: ssl.SSLContext) -> None:
        """Load certificate and key into context."""
        if not self.cert_file or not self.key_file:
            raise TLSConfigError("Certificate and key files required")

        cert_path = Path(self.cert_file)
        key_path = Path(self.key_file)

        if not cert_path.exists():
            raise TLSConfigError(f"Certificate file not found: {cert_path}")
        if not key_path.exists():
            raise TLSConfigError(f"Key file not found: {key_path}")

        try:
            context.load_cert_chain(
                certfile=str(cert_path),
                keyfile=str(key_path),
            )
        except ssl.SSLError as e:
            raise TLSConfigError(f"Failed to load certificate: {e}")

    def validate(self) -> List[str]:
        """
        Validate TLS configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check certificate files exist if specified
        if self.cert_file:
            if not Path(self.cert_file).exists():
                errors.append(f"Certificate file not found: {self.cert_file}")
        if self.key_file:
            if not Path(self.key_file).exists():
                errors.append(f"Key file not found: {self.key_file}")
        if self.ca_file:
            if not Path(self.ca_file).exists():
                errors.append(f"CA file not found: {self.ca_file}")

        # Check cert and key are both present or both absent
        if bool(self.cert_file) != bool(self.key_file):
            errors.append("Both certificate and key file must be specified")

        # Check TLS version
        if self.min_version < ssl.TLSVersion.TLSv1_2:
            errors.append("Minimum TLS version must be 1.2 or higher")

        return errors

    def is_configured(self) -> bool:
        """Check if TLS is configured with certificate."""
        return bool(self.cert_file and self.key_file)


# =============================================================================
# Certificate Utilities
# =============================================================================

@dataclass
class CertificateInfo:
    """Information about a certificate."""

    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime
    serial_number: int
    is_self_signed: bool
    san_names: List[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        """Check if certificate is expired."""
        return datetime.utcnow() > self.not_after

    @property
    def is_not_yet_valid(self) -> bool:
        """Check if certificate is not yet valid."""
        return datetime.utcnow() < self.not_before

    @property
    def days_until_expiry(self) -> int:
        """Days until certificate expires."""
        delta = self.not_after - datetime.utcnow()
        return delta.days

    @property
    def is_expiring_soon(self) -> bool:
        """Check if certificate expires within 30 days."""
        return self.days_until_expiry <= 30


def get_certificate_info(cert_path: Path) -> CertificateInfo:
    """
    Get information about a certificate.

    Args:
        cert_path: Path to certificate file (PEM format)

    Returns:
        CertificateInfo with certificate details

    Raises:
        TLSConfigError: If certificate cannot be read
    """
    try:
        # Use cryptography library if available
        try:
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend

            with open(cert_path, "rb") as f:
                cert_data = f.read()

            cert = x509.load_pem_x509_certificate(cert_data, default_backend())

            # Extract subject and issuer
            subject = cert.subject.rfc4514_string()
            issuer = cert.issuer.rfc4514_string()

            # Extract SAN names
            san_names = []
            try:
                san_ext = cert.extensions.get_extension_for_class(
                    x509.SubjectAlternativeName
                )
                for name in san_ext.value:
                    if isinstance(name, x509.DNSName):
                        san_names.append(name.value)
                    elif isinstance(name, x509.IPAddress):
                        san_names.append(str(name.value))
            except x509.ExtensionNotFound:
                pass

            return CertificateInfo(
                subject=subject,
                issuer=issuer,
                not_before=cert.not_valid_before_utc.replace(tzinfo=None),
                not_after=cert.not_valid_after_utc.replace(tzinfo=None),
                serial_number=cert.serial_number,
                is_self_signed=(subject == issuer),
                san_names=san_names,
            )

        except ImportError:
            # Fallback: use openssl command
            return _get_cert_info_openssl(cert_path)

    except Exception as e:
        raise TLSConfigError(f"Failed to read certificate: {e}")


def _get_cert_info_openssl(cert_path: Path) -> CertificateInfo:
    """Get certificate info using openssl command."""
    import subprocess

    try:
        # Get certificate text
        result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-text", "-noout"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise TLSConfigError(f"openssl failed: {result.stderr}")

        text = result.stdout

        # Parse basic info (simplified)
        subject = _extract_field(text, "Subject:")
        issuer = _extract_field(text, "Issuer:")

        # Parse dates
        not_before_str = _extract_field(text, "Not Before:")
        not_after_str = _extract_field(text, "Not After :")

        # Parse dates (format: Jan  1 00:00:00 2024 GMT)
        not_before = _parse_openssl_date(not_before_str)
        not_after = _parse_openssl_date(not_after_str)

        return CertificateInfo(
            subject=subject,
            issuer=issuer,
            not_before=not_before,
            not_after=not_after,
            serial_number=0,  # Not parsed in simple mode
            is_self_signed=(subject == issuer),
            san_names=[],
        )

    except subprocess.TimeoutExpired:
        raise TLSConfigError("openssl command timed out")
    except FileNotFoundError:
        raise TLSConfigError("openssl command not found")


def _extract_field(text: str, prefix: str) -> str:
    """Extract field value from certificate text."""
    for line in text.split("\n"):
        if prefix in line:
            return line.split(prefix, 1)[1].strip()
    return ""


def _parse_openssl_date(date_str: str) -> datetime:
    """Parse OpenSSL date format."""
    # Format: "Jan  1 00:00:00 2024 GMT"
    try:
        # Remove extra spaces
        date_str = " ".join(date_str.split())
        # Remove GMT suffix
        date_str = date_str.replace(" GMT", "")
        return datetime.strptime(date_str, "%b %d %H:%M:%S %Y")
    except ValueError:
        return datetime.utcnow()


# =============================================================================
# Self-Signed Certificate Generation
# =============================================================================

def generate_self_signed_cert(
    common_name: str = "localhost",
    san_names: Optional[List[str]] = None,
    valid_days: int = 365,
    key_size: int = 2048,
    output_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """
    Generate a self-signed certificate for development/testing.

    Args:
        common_name: Certificate common name (default: localhost)
        san_names: Additional Subject Alternative Names
        valid_days: Certificate validity in days (default: 365)
        key_size: RSA key size in bits (default: 2048)
        output_dir: Directory for output files (default: temp directory)

    Returns:
        Tuple of (cert_path, key_path)

    Raises:
        TLSConfigError: If generation fails
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend

        # Generate private key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend(),
        )

        # Build subject
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OTTO OS Development"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        # Build SAN extension
        san_list = [x509.DNSName(common_name)]
        if san_names:
            for name in san_names:
                if _is_ip_address(name):
                    import ipaddress
                    san_list.append(x509.IPAddress(ipaddress.ip_address(name)))
                else:
                    san_list.append(x509.DNSName(name))

        # Add localhost and 127.0.0.1 by default
        if common_name != "localhost":
            san_list.append(x509.DNSName("localhost"))
        import ipaddress
        san_list.append(x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")))

        # Build certificate
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=valid_days))
            .add_extension(
                x509.SubjectAlternativeName(san_list),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=0),
                critical=True,
            )
            .sign(key, hashes.SHA256(), default_backend())
        )

        # Determine output directory
        if output_dir is None:
            output_dir = Path(tempfile.mkdtemp(prefix="otto_tls_"))
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        cert_path = output_dir / "cert.pem"
        key_path = output_dir / "key.pem"

        # Write certificate
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # Write private key
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        logger.info(f"Generated self-signed certificate: {cert_path}")
        return cert_path, key_path

    except ImportError:
        raise TLSConfigError(
            "cryptography library required for certificate generation. "
            "Install with: pip install cryptography"
        )
    except Exception as e:
        raise TLSConfigError(f"Failed to generate certificate: {e}")


def _is_ip_address(value: str) -> bool:
    """Check if value is an IP address."""
    import ipaddress
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


# =============================================================================
# HSTS Configuration
# =============================================================================

@dataclass
class HSTSConfig:
    """
    HTTP Strict Transport Security configuration.

    [He2025] Compliance: FIXED HSTS parameters.
    """

    max_age: int = 31536000  # 1 year in seconds
    include_subdomains: bool = True
    preload: bool = False

    def to_header_value(self) -> str:
        """
        Generate HSTS header value.

        Returns:
            Strict-Transport-Security header value
        """
        parts = [f"max-age={self.max_age}"]

        if self.include_subdomains:
            parts.append("includeSubDomains")

        if self.preload:
            parts.append("preload")

        return "; ".join(parts)


# =============================================================================
# Certificate Lifecycle Monitoring
# =============================================================================

class CertificateExpiryLevel(Enum):
    """Certificate expiry warning levels."""
    OK = "ok"                    # > 30 days
    WARNING = "warning"          # 14-30 days
    CRITICAL = "critical"        # 7-14 days
    EXPIRED = "expired"          # <= 0 days
    EXPIRING_SOON = "expiring"   # 1-7 days


@dataclass
class CertificateHealthStatus:
    """
    Health status of a certificate.

    [He2025] FIXED thresholds for expiry warnings.
    """
    cert_path: Path
    level: CertificateExpiryLevel
    days_until_expiry: int
    expiry_date: datetime
    is_self_signed: bool
    subject: str
    message: str

    # [He2025] FIXED thresholds - no runtime variation
    EXPIRY_WARNING_DAYS: int = 30
    EXPIRY_CRITICAL_DAYS: int = 14
    EXPIRY_URGENT_DAYS: int = 7

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cert_path": str(self.cert_path),
            "level": self.level.value,
            "days_until_expiry": self.days_until_expiry,
            "expiry_date": self.expiry_date.isoformat(),
            "is_self_signed": self.is_self_signed,
            "subject": self.subject,
            "message": self.message,
        }


class CertificateMonitor:
    """
    Monitors certificate health and expiry.

    [He2025] Compliance:
    - FIXED expiry thresholds (30/14/7 days)
    - DETERMINISTIC health checks
    - Alerting hooks for integration

    Usage:
        monitor = CertificateMonitor()
        monitor.add_certificate(cert_path)
        status = monitor.check_all()

        # With alerting
        monitor.on_expiry_warning(lambda status: send_alert(status))
    """

    # [He2025] FIXED thresholds
    WARNING_DAYS = 30
    CRITICAL_DAYS = 14
    URGENT_DAYS = 7

    def __init__(self):
        """Initialize certificate monitor."""
        self._certificates: Dict[str, Path] = {}
        self._on_warning_callbacks: List[Callable[[CertificateHealthStatus], None]] = []
        self._on_critical_callbacks: List[Callable[[CertificateHealthStatus], None]] = []
        self._on_expired_callbacks: List[Callable[[CertificateHealthStatus], None]] = []
        self._last_check: Dict[str, CertificateHealthStatus] = {}

    def add_certificate(
        self,
        cert_path: Path,
        name: Optional[str] = None,
    ) -> None:
        """
        Add a certificate to monitor.

        Args:
            cert_path: Path to certificate file
            name: Optional friendly name (defaults to filename)
        """
        cert_path = Path(cert_path)
        name = name or cert_path.stem
        self._certificates[name] = cert_path
        logger.info(f"Added certificate to monitor: {name} ({cert_path})")

    def remove_certificate(self, name: str) -> bool:
        """
        Remove a certificate from monitoring.

        Args:
            name: Certificate name

        Returns:
            True if removed, False if not found
        """
        if name in self._certificates:
            del self._certificates[name]
            self._last_check.pop(name, None)
            return True
        return False

    def on_expiry_warning(
        self,
        callback: Callable[[CertificateHealthStatus], None],
    ) -> None:
        """Register callback for expiry warnings (30 days)."""
        self._on_warning_callbacks.append(callback)

    def on_expiry_critical(
        self,
        callback: Callable[[CertificateHealthStatus], None],
    ) -> None:
        """Register callback for critical expiry (14 days)."""
        self._on_critical_callbacks.append(callback)

    def on_expired(
        self,
        callback: Callable[[CertificateHealthStatus], None],
    ) -> None:
        """Register callback for expired certificates."""
        self._on_expired_callbacks.append(callback)

    def _determine_level(self, days: int) -> CertificateExpiryLevel:
        """Determine expiry level based on days remaining."""
        if days <= 0:
            return CertificateExpiryLevel.EXPIRED
        elif days <= self.URGENT_DAYS:
            return CertificateExpiryLevel.EXPIRING_SOON
        elif days <= self.CRITICAL_DAYS:
            return CertificateExpiryLevel.CRITICAL
        elif days <= self.WARNING_DAYS:
            return CertificateExpiryLevel.WARNING
        else:
            return CertificateExpiryLevel.OK

    def _build_message(self, level: CertificateExpiryLevel, days: int) -> str:
        """Build human-readable status message."""
        if level == CertificateExpiryLevel.EXPIRED:
            return f"Certificate EXPIRED {abs(days)} days ago"
        elif level == CertificateExpiryLevel.EXPIRING_SOON:
            return f"Certificate expires in {days} days - URGENT"
        elif level == CertificateExpiryLevel.CRITICAL:
            return f"Certificate expires in {days} days - CRITICAL"
        elif level == CertificateExpiryLevel.WARNING:
            return f"Certificate expires in {days} days - plan renewal"
        else:
            return f"Certificate valid for {days} days"

    def check_certificate(self, name: str) -> Optional[CertificateHealthStatus]:
        """
        Check health of a specific certificate.

        Args:
            name: Certificate name

        Returns:
            CertificateHealthStatus or None if not found
        """
        cert_path = self._certificates.get(name)
        if cert_path is None:
            return None

        try:
            info = get_certificate_info(cert_path)
        except TLSConfigError as e:
            logger.error(f"Failed to check certificate {name}: {e}")
            return CertificateHealthStatus(
                cert_path=cert_path,
                level=CertificateExpiryLevel.CRITICAL,
                days_until_expiry=-1,
                expiry_date=datetime.utcnow(),
                is_self_signed=False,
                subject="ERROR",
                message=f"Failed to read certificate: {e}",
            )

        level = self._determine_level(info.days_until_expiry)
        message = self._build_message(level, info.days_until_expiry)

        status = CertificateHealthStatus(
            cert_path=cert_path,
            level=level,
            days_until_expiry=info.days_until_expiry,
            expiry_date=info.not_after,
            is_self_signed=info.is_self_signed,
            subject=info.subject,
            message=message,
        )

        # Store for comparison
        self._last_check[name] = status

        # Trigger callbacks
        self._trigger_callbacks(status)

        return status

    def check_all(self) -> Dict[str, CertificateHealthStatus]:
        """
        Check health of all monitored certificates.

        Returns:
            Dict mapping certificate name to health status
        """
        results = {}
        for name in self._certificates:
            status = self.check_certificate(name)
            if status:
                results[name] = status
        return results

    def _trigger_callbacks(self, status: CertificateHealthStatus) -> None:
        """Trigger appropriate callbacks based on status."""
        if status.level == CertificateExpiryLevel.EXPIRED:
            for callback in self._on_expired_callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"Error in expired callback: {e}")

        elif status.level in (
            CertificateExpiryLevel.EXPIRING_SOON,
            CertificateExpiryLevel.CRITICAL,
        ):
            for callback in self._on_critical_callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"Error in critical callback: {e}")

        elif status.level == CertificateExpiryLevel.WARNING:
            for callback in self._on_warning_callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"Error in warning callback: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all certificate health.

        Returns:
            Dict with overall health summary
        """
        statuses = self.check_all()

        expired = [s for s in statuses.values() if s.level == CertificateExpiryLevel.EXPIRED]
        critical = [s for s in statuses.values() if s.level in (
            CertificateExpiryLevel.CRITICAL,
            CertificateExpiryLevel.EXPIRING_SOON,
        )]
        warning = [s for s in statuses.values() if s.level == CertificateExpiryLevel.WARNING]
        ok = [s for s in statuses.values() if s.level == CertificateExpiryLevel.OK]

        # Determine overall level
        if expired:
            overall = CertificateExpiryLevel.EXPIRED
        elif critical:
            overall = CertificateExpiryLevel.CRITICAL
        elif warning:
            overall = CertificateExpiryLevel.WARNING
        else:
            overall = CertificateExpiryLevel.OK

        return {
            "overall_level": overall.value,
            "total_certificates": len(statuses),
            "expired_count": len(expired),
            "critical_count": len(critical),
            "warning_count": len(warning),
            "ok_count": len(ok),
            "certificates": {name: s.to_dict() for name, s in statuses.items()},
        }


# =============================================================================
# ACME Integration Hooks
# =============================================================================

class ACMEProvider(Enum):
    """Supported ACME providers."""
    LETS_ENCRYPT = "letsencrypt"
    LETS_ENCRYPT_STAGING = "letsencrypt_staging"
    ZERO_SSL = "zerossl"
    CUSTOM = "custom"


@dataclass
class ACMEConfig:
    """
    ACME configuration for automatic certificate management.

    [He2025] FIXED provider URLs and settings.

    Note: Full ACME implementation requires additional dependencies.
    This provides the configuration hooks for integration.
    """
    provider: ACMEProvider = ACMEProvider.LETS_ENCRYPT
    email: Optional[str] = None
    domains: List[str] = field(default_factory=list)
    key_type: str = "ec256"  # ec256, ec384, rsa2048, rsa4096
    auto_renew: bool = True
    renew_before_days: int = 30

    # [He2025] FIXED provider directories
    PROVIDER_URLS: Dict[ACMEProvider, str] = field(default_factory=lambda: {
        ACMEProvider.LETS_ENCRYPT: "https://acme-v02.api.letsencrypt.org/directory",
        ACMEProvider.LETS_ENCRYPT_STAGING: "https://acme-staging-v02.api.letsencrypt.org/directory",
        ACMEProvider.ZERO_SSL: "https://acme.zerossl.com/v2/DV90",
    })

    @property
    def directory_url(self) -> str:
        """Get ACME directory URL for provider."""
        return self.PROVIDER_URLS.get(
            self.provider,
            self.PROVIDER_URLS[ACMEProvider.LETS_ENCRYPT],
        )


# =============================================================================
# Errors
# =============================================================================

class TLSConfigError(Exception):
    """Error in TLS configuration."""
    pass


# =============================================================================
# Factory Functions
# =============================================================================

def create_development_tls(
    output_dir: Optional[Path] = None,
) -> TLSConfig:
    """
    Create TLS configuration for development with self-signed certificate.

    Args:
        output_dir: Directory for certificate files

    Returns:
        TLSConfig with self-signed certificate
    """
    cert_path, key_path = generate_self_signed_cert(
        common_name="localhost",
        san_names=["127.0.0.1", "::1"],
        valid_days=365,
        output_dir=output_dir,
    )

    return TLSConfig(
        cert_file=cert_path,
        key_file=key_path,
        min_version=ssl.TLSVersion.TLSv1_3,
        verify_client=False,
    )


def create_production_tls(
    cert_file: Path,
    key_file: Path,
    ca_file: Optional[Path] = None,
) -> TLSConfig:
    """
    Create TLS configuration for production.

    Args:
        cert_file: Path to certificate file
        key_file: Path to private key file
        ca_file: Path to CA certificate file (optional)

    Returns:
        TLSConfig for production use
    """
    config = TLSConfig(
        cert_file=cert_file,
        key_file=key_file,
        ca_file=ca_file,
        min_version=ssl.TLSVersion.TLSv1_3,
        verify_client=False,
    )

    # Validate configuration
    errors = config.validate()
    if errors:
        raise TLSConfigError(f"Invalid TLS configuration: {', '.join(errors)}")

    return config


__all__ = [
    # Configuration
    "TLSConfig",
    "HSTSConfig",

    # Certificate utilities
    "CertificateInfo",
    "get_certificate_info",
    "generate_self_signed_cert",

    # Certificate lifecycle monitoring
    "CertificateExpiryLevel",
    "CertificateHealthStatus",
    "CertificateMonitor",

    # ACME integration
    "ACMEProvider",
    "ACMEConfig",

    # Factory functions
    "create_development_tls",
    "create_production_tls",

    # Errors
    "TLSConfigError",
]
