"""
Tests for TLS Configuration

Tests TLS/HTTPS configuration for secure API communication.

[He2025] Compliance: Verifies FIXED cipher suites, FIXED TLS version.
"""

import pytest
import ssl
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from otto.api import (
    TLSConfig,
    HSTSConfig,
    CertificateInfo,
    TLSConfigError,
    generate_self_signed_cert,
    create_development_tls,
    create_production_tls,
    get_certificate_info,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir(tmp_path) -> Path:
    """Temporary directory for test files."""
    return tmp_path


@pytest.fixture
def self_signed_cert(temp_dir) -> tuple[Path, Path]:
    """Generate a self-signed certificate for testing."""
    try:
        return generate_self_signed_cert(
            common_name="test.local",
            san_names=["localhost", "127.0.0.1"],
            valid_days=30,
            output_dir=temp_dir,
        )
    except TLSConfigError as e:
        if "cryptography library required" in str(e):
            pytest.skip("cryptography library not available")
        raise


@pytest.fixture
def tls_config(self_signed_cert) -> TLSConfig:
    """Create TLS config with test certificate."""
    cert_path, key_path = self_signed_cert
    return TLSConfig(
        cert_file=cert_path,
        key_file=key_path,
    )


# =============================================================================
# Test: TLSConfig Basic
# =============================================================================

class TestTLSConfigBasic:
    """Test basic TLSConfig functionality."""

    def test_default_values(self):
        """Default TLS config has secure defaults."""
        config = TLSConfig()

        assert config.cert_file is None
        assert config.key_file is None
        assert config.min_version == ssl.TLSVersion.TLSv1_3
        assert config.verify_client is False
        assert config.check_hostname is True

    def test_custom_values(self, temp_dir):
        """Custom values are applied correctly."""
        config = TLSConfig(
            cert_file=temp_dir / "cert.pem",
            key_file=temp_dir / "key.pem",
            min_version=ssl.TLSVersion.TLSv1_2,
            verify_client=True,
        )

        assert config.cert_file == temp_dir / "cert.pem"
        assert config.key_file == temp_dir / "key.pem"
        assert config.min_version == ssl.TLSVersion.TLSv1_2
        assert config.verify_client is True

    def test_is_configured_without_cert(self):
        """is_configured returns False without certificate."""
        config = TLSConfig()
        assert config.is_configured() is False

    def test_is_configured_with_cert(self, self_signed_cert):
        """is_configured returns True with certificate."""
        cert_path, key_path = self_signed_cert
        config = TLSConfig(cert_file=cert_path, key_file=key_path)
        assert config.is_configured() is True


# =============================================================================
# Test: [He2025] Fixed Cipher Suites
# =============================================================================

class TestCipherSuites:
    """Test cipher suite configuration for [He2025] compliance."""

    def test_tls13_ciphers_are_fixed(self):
        """TLS 1.3 cipher suites are fixed (no runtime variation)."""
        config1 = TLSConfig()
        config2 = TLSConfig()

        assert config1.CIPHERS_TLS13 == config2.CIPHERS_TLS13

    def test_tls13_ciphers_include_aes256(self):
        """TLS 1.3 includes AES-256-GCM."""
        config = TLSConfig()
        assert "TLS_AES_256_GCM_SHA384" in config.CIPHERS_TLS13

    def test_tls13_ciphers_include_chacha20(self):
        """TLS 1.3 includes ChaCha20-Poly1305."""
        config = TLSConfig()
        assert "TLS_CHACHA20_POLY1305_SHA256" in config.CIPHERS_TLS13

    def test_tls12_ciphers_are_fixed(self):
        """TLS 1.2 cipher suites are fixed."""
        config1 = TLSConfig()
        config2 = TLSConfig()

        assert config1.CIPHERS_TLS12 == config2.CIPHERS_TLS12

    def test_cipher_string_is_deterministic(self):
        """Cipher string generation is deterministic."""
        config1 = TLSConfig()
        config2 = TLSConfig()

        assert config1._build_cipher_string() == config2._build_cipher_string()


# =============================================================================
# Test: SSL Context Creation
# =============================================================================

class TestSSLContextCreation:
    """Test SSL context creation."""

    def test_create_server_context(self, tls_config):
        """create_ssl_context returns valid SSLContext."""
        ctx = tls_config.create_ssl_context()

        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2

    def test_server_context_disables_old_protocols(self, tls_config):
        """Server context disables old SSL/TLS versions."""
        ctx = tls_config.create_ssl_context()

        # Check options are set to disable old protocols
        # Note: OP_NO_SSLv2 is 0 in Python 3.10+ (SSLv2 already removed)
        # so we skip that check if the flag is 0
        if ssl.OP_NO_SSLv2 != 0:
            assert ctx.options & ssl.OP_NO_SSLv2
        assert ctx.options & ssl.OP_NO_SSLv3
        assert ctx.options & ssl.OP_NO_TLSv1
        assert ctx.options & ssl.OP_NO_TLSv1_1

    def test_create_client_context(self, tls_config):
        """create_client_context returns valid SSLContext."""
        ctx = tls_config.create_client_context()

        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_context_without_cert(self):
        """Context can be created without certificate."""
        config = TLSConfig()

        # Should not raise - just won't load certificate
        ctx = config.create_ssl_context()
        assert isinstance(ctx, ssl.SSLContext)


# =============================================================================
# Test: Certificate Validation
# =============================================================================

class TestCertificateValidation:
    """Test certificate validation."""

    def test_validate_valid_config(self, tls_config):
        """Valid configuration passes validation."""
        errors = tls_config.validate()
        assert errors == []

    def test_validate_missing_cert(self, temp_dir):
        """Missing certificate file fails validation."""
        config = TLSConfig(
            cert_file=temp_dir / "nonexistent.pem",
            key_file=temp_dir / "key.pem",
        )

        errors = config.validate()
        assert len(errors) >= 1
        assert any("not found" in e for e in errors)

    def test_validate_cert_without_key(self, self_signed_cert):
        """Certificate without key file fails validation."""
        cert_path, _ = self_signed_cert
        config = TLSConfig(cert_file=cert_path)

        errors = config.validate()
        assert len(errors) >= 1
        assert any("Both certificate and key" in e for e in errors)

    def test_validate_key_without_cert(self, self_signed_cert):
        """Key without certificate file fails validation."""
        _, key_path = self_signed_cert
        config = TLSConfig(key_file=key_path)

        errors = config.validate()
        assert len(errors) >= 1
        assert any("Both certificate and key" in e for e in errors)

    def test_validate_old_tls_version(self):
        """TLS version below 1.2 fails validation."""
        config = TLSConfig(min_version=ssl.TLSVersion.TLSv1_1)

        errors = config.validate()
        assert len(errors) >= 1
        assert any("1.2 or higher" in e for e in errors)


# =============================================================================
# Test: Self-Signed Certificate Generation
# =============================================================================

class TestSelfSignedCertGeneration:
    """Test self-signed certificate generation."""

    def test_generate_creates_files(self, temp_dir):
        """generate_self_signed_cert creates cert and key files."""
        try:
            cert_path, key_path = generate_self_signed_cert(
                output_dir=temp_dir
            )

            assert cert_path.exists()
            assert key_path.exists()
        except TLSConfigError as e:
            if "cryptography library required" in str(e):
                pytest.skip("cryptography library not available")
            raise

    def test_generate_custom_common_name(self, temp_dir):
        """generate_self_signed_cert uses custom common name."""
        try:
            cert_path, key_path = generate_self_signed_cert(
                common_name="myapp.local",
                output_dir=temp_dir,
            )

            info = get_certificate_info(cert_path)
            assert "myapp.local" in info.subject
        except TLSConfigError as e:
            if "cryptography library required" in str(e):
                pytest.skip("cryptography library not available")
            raise

    def test_generate_custom_validity(self, temp_dir):
        """generate_self_signed_cert respects validity period."""
        try:
            cert_path, key_path = generate_self_signed_cert(
                valid_days=7,
                output_dir=temp_dir,
            )

            info = get_certificate_info(cert_path)
            assert info.days_until_expiry <= 7
            assert info.days_until_expiry >= 6  # Allow for test execution time
        except TLSConfigError as e:
            if "cryptography library required" in str(e):
                pytest.skip("cryptography library not available")
            raise

    def test_generate_includes_san(self, temp_dir):
        """generate_self_signed_cert includes SAN names."""
        try:
            cert_path, key_path = generate_self_signed_cert(
                common_name="test.local",
                san_names=["api.local", "web.local"],
                output_dir=temp_dir,
            )

            info = get_certificate_info(cert_path)
            # Should include common name and additional SANs
            assert "test.local" in info.san_names or "test.local" in info.subject
        except TLSConfigError as e:
            if "cryptography library required" in str(e):
                pytest.skip("cryptography library not available")
            raise


# =============================================================================
# Test: Certificate Info
# =============================================================================

class TestCertificateInfo:
    """Test certificate information extraction."""

    def test_get_certificate_info(self, self_signed_cert):
        """get_certificate_info returns valid info."""
        cert_path, _ = self_signed_cert
        info = get_certificate_info(cert_path)

        assert isinstance(info, CertificateInfo)
        assert info.subject is not None
        assert info.issuer is not None
        assert info.not_before is not None
        assert info.not_after is not None

    def test_is_self_signed(self, self_signed_cert):
        """is_self_signed is True for self-signed certs."""
        cert_path, _ = self_signed_cert
        info = get_certificate_info(cert_path)

        assert info.is_self_signed is True

    def test_is_expired(self, self_signed_cert):
        """is_expired is False for valid certs."""
        cert_path, _ = self_signed_cert
        info = get_certificate_info(cert_path)

        assert info.is_expired is False

    def test_days_until_expiry(self, self_signed_cert):
        """days_until_expiry returns positive value for valid certs."""
        cert_path, _ = self_signed_cert
        info = get_certificate_info(cert_path)

        assert info.days_until_expiry > 0

    def test_nonexistent_cert_raises(self, temp_dir):
        """get_certificate_info raises for nonexistent file."""
        with pytest.raises(TLSConfigError):
            get_certificate_info(temp_dir / "nonexistent.pem")


# =============================================================================
# Test: HSTS Configuration
# =============================================================================

class TestHSTSConfig:
    """Test HSTS configuration."""

    def test_default_values(self):
        """HSTS has secure defaults."""
        hsts = HSTSConfig()

        assert hsts.max_age == 31536000  # 1 year
        assert hsts.include_subdomains is True
        assert hsts.preload is False

    def test_header_value_basic(self):
        """to_header_value returns basic HSTS header."""
        hsts = HSTSConfig(
            max_age=86400,
            include_subdomains=False,
            preload=False,
        )

        header = hsts.to_header_value()
        assert header == "max-age=86400"

    def test_header_value_with_subdomains(self):
        """to_header_value includes includeSubDomains."""
        hsts = HSTSConfig(
            max_age=86400,
            include_subdomains=True,
            preload=False,
        )

        header = hsts.to_header_value()
        assert "max-age=86400" in header
        assert "includeSubDomains" in header

    def test_header_value_with_preload(self):
        """to_header_value includes preload."""
        hsts = HSTSConfig(
            max_age=31536000,
            include_subdomains=True,
            preload=True,
        )

        header = hsts.to_header_value()
        assert "max-age=31536000" in header
        assert "includeSubDomains" in header
        assert "preload" in header


# =============================================================================
# Test: Factory Functions
# =============================================================================

class TestFactoryFunctions:
    """Test TLS factory functions."""

    def test_create_development_tls(self, temp_dir):
        """create_development_tls creates valid config."""
        try:
            config = create_development_tls(output_dir=temp_dir)

            assert config.is_configured()
            assert config.cert_file.exists()
            assert config.key_file.exists()
            assert config.min_version == ssl.TLSVersion.TLSv1_3
        except TLSConfigError as e:
            if "cryptography library required" in str(e):
                pytest.skip("cryptography library not available")
            raise

    def test_create_production_tls(self, self_signed_cert):
        """create_production_tls creates valid config."""
        cert_path, key_path = self_signed_cert

        config = create_production_tls(
            cert_file=cert_path,
            key_file=key_path,
        )

        assert config.is_configured()
        assert config.min_version == ssl.TLSVersion.TLSv1_3

    def test_create_production_tls_validates(self, temp_dir):
        """create_production_tls validates configuration."""
        with pytest.raises(TLSConfigError) as exc_info:
            create_production_tls(
                cert_file=temp_dir / "nonexistent.pem",
                key_file=temp_dir / "nonexistent.key",
            )

        assert "Invalid TLS configuration" in str(exc_info.value)


# =============================================================================
# Test: [He2025] Determinism
# =============================================================================

class TestDeterminism:
    """Test [He2025] determinism compliance."""

    def test_cipher_suites_deterministic(self):
        """Cipher suites are identical across instantiations."""
        configs = [TLSConfig() for _ in range(5)]

        cipher_strings = [c._build_cipher_string() for c in configs]
        assert all(s == cipher_strings[0] for s in cipher_strings)

    def test_ssl_context_settings_deterministic(self, tls_config):
        """SSL context settings are deterministic."""
        ctx1 = tls_config.create_ssl_context()
        ctx2 = tls_config.create_ssl_context()

        assert ctx1.minimum_version == ctx2.minimum_version
        assert ctx1.options == ctx2.options
        assert ctx1.verify_mode == ctx2.verify_mode

    def test_hsts_header_deterministic(self):
        """HSTS header value is deterministic."""
        configs = [HSTSConfig() for _ in range(5)]

        headers = [c.to_header_value() for c in configs]
        assert all(h == headers[0] for h in headers)


# =============================================================================
# Test: Error Handling
# =============================================================================

class TestErrorHandling:
    """Test error handling."""

    def test_tls_config_error_is_exception(self):
        """TLSConfigError is a proper Exception."""
        error = TLSConfigError("test error")

        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_invalid_cert_raises(self, temp_dir):
        """Invalid certificate file raises TLSConfigError."""
        # Create an invalid certificate file
        invalid_cert = temp_dir / "invalid.pem"
        invalid_cert.write_text("not a certificate")

        with pytest.raises(TLSConfigError):
            get_certificate_info(invalid_cert)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
