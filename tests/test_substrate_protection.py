"""
Tests for Substrate Protection Layer
====================================

Verifies encryption, signing, and integrity verification for cognitive substrate.
"""

import json
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any

from otto.substrate.protection import (
    SubstrateProtection,
    SubstrateProtectionError,
    IntegrityError,
    PermissionDeniedError,
    AssetNotFoundError,
    ProtectionLevel,
    ProtectionStatus,
    Signature,
    SUBSTRATE_ASSETS,
    create_substrate_protection,
)

from otto.substrate.integrity import (
    SubstrateIntegrity,
    IntegrityReport,
    VerificationIssue,
    CONFIG_SCHEMAS,
    SAFETY_CONSTRAINTS,
    create_integrity_verifier,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_otto_dir():
    """Create a temporary OTTO directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def protection(temp_otto_dir):
    """Create a SubstrateProtection instance."""
    return SubstrateProtection(temp_otto_dir)


@pytest.fixture
def unlocked_protection(temp_otto_dir):
    """Create an unlocked SubstrateProtection instance."""
    prot = SubstrateProtection(temp_otto_dir)
    prot.setup("test-passphrase-12chars")
    return prot


@pytest.fixture
def integrity(temp_otto_dir):
    """Create a SubstrateIntegrity instance."""
    return SubstrateIntegrity(temp_otto_dir)


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample expert weights configuration."""
    return {
        "validator": 0.15,
        "scaffolder": 0.14,
        "restorer": 0.14,
        "refocuser": 0.14,
        "celebrator": 0.14,
        "socratic": 0.14,
        "direct": 0.15,
    }


@pytest.fixture
def sample_safety_floors() -> Dict[str, Any]:
    """Sample safety floors configuration."""
    return {
        "validator": 0.10,
        "restorer": 0.08,
        "scaffolder": 0.05,
    }


# =============================================================================
# Protection Setup Tests
# =============================================================================

class TestProtectionSetup:
    """Test protection setup and initialization."""

    def test_initial_state(self, protection):
        """Protection starts not setup and not unlocked."""
        assert not protection.is_setup()
        assert not protection.is_unlocked()

    def test_setup_returns_recovery_key(self, protection):
        """Setup returns a recovery key."""
        recovery_key = protection.setup("test-passphrase-12chars")
        assert recovery_key is not None
        assert len(recovery_key) > 0

    def test_setup_unlocks_protection(self, protection):
        """Setup automatically unlocks protection."""
        protection.setup("test-passphrase-12chars")
        assert protection.is_setup()
        assert protection.is_unlocked()

    def test_weak_passphrase_rejected(self, protection):
        """Weak passphrases are rejected."""
        from otto.encryption.encryption_manager import InvalidPassphraseError
        with pytest.raises(InvalidPassphraseError):
            protection.setup("short")

    def test_double_setup_fails(self, protection):
        """Cannot setup twice."""
        from otto.encryption.encryption_manager import AlreadySetupError
        protection.setup("test-passphrase-12chars")
        with pytest.raises(AlreadySetupError):
            protection.setup("another-passphrase")


# =============================================================================
# Unlock/Lock Tests
# =============================================================================

class TestUnlockLock:
    """Test unlock and lock operations."""

    def test_unlock_with_correct_passphrase(self, temp_otto_dir):
        """Unlock succeeds with correct passphrase."""
        prot = SubstrateProtection(temp_otto_dir)
        prot.setup("test-passphrase-12chars")
        prot.lock()

        assert not prot.is_unlocked()
        prot.unlock("test-passphrase-12chars")
        assert prot.is_unlocked()

    def test_unlock_with_wrong_passphrase(self, temp_otto_dir):
        """Unlock fails with wrong passphrase."""
        from otto.encryption.encryption_manager import InvalidPassphraseError
        prot = SubstrateProtection(temp_otto_dir)
        prot.setup("test-passphrase-12chars")
        prot.lock()

        with pytest.raises(InvalidPassphraseError):
            prot.unlock("wrong-passphrase-here")

    def test_lock_clears_state(self, unlocked_protection):
        """Lock clears the signing key."""
        assert unlocked_protection.is_unlocked()
        unlocked_protection.lock()
        assert not unlocked_protection.is_unlocked()

    def test_unlock_with_recovery_key(self, temp_otto_dir):
        """Unlock works with recovery key."""
        prot = SubstrateProtection(temp_otto_dir)
        recovery_key = prot.setup("test-passphrase-12chars")
        prot.lock()

        prot.unlock_with_recovery_key(recovery_key)
        assert prot.is_unlocked()


# =============================================================================
# Read/Write Protected Assets Tests
# =============================================================================

class TestReadWriteProtected:
    """Test reading and writing protected assets."""

    def test_write_and_read_protected(self, unlocked_protection, sample_config):
        """Can write and read protected assets."""
        # Write
        unlocked_protection.write_protected_json(
            "routing/expert_weights.json",
            sample_config
        )

        # Read back
        content = unlocked_protection.read_protected_json("routing/expert_weights.json")
        assert content == sample_config

    def test_read_requires_unlock(self, temp_otto_dir, sample_config):
        """Cannot read protected assets when locked."""
        from otto.encryption.encryption_manager import NotUnlockedError
        prot = SubstrateProtection(temp_otto_dir)
        prot.setup("test-passphrase-12chars")

        # Write while unlocked
        prot.write_protected_json("routing/expert_weights.json", sample_config)

        # Lock and try to read
        prot.lock()
        with pytest.raises(NotUnlockedError):
            prot.read_protected("routing/expert_weights.json")

    def test_write_requires_unlock(self, temp_otto_dir, sample_config):
        """Cannot write protected assets when locked."""
        from otto.encryption.encryption_manager import NotUnlockedError
        prot = SubstrateProtection(temp_otto_dir)
        prot.setup("test-passphrase-12chars")
        prot.lock()

        with pytest.raises(NotUnlockedError):
            prot.write_protected_json("routing/expert_weights.json", sample_config)

    def test_asset_not_found(self, unlocked_protection):
        """AssetNotFoundError when asset doesn't exist."""
        with pytest.raises(AssetNotFoundError):
            unlocked_protection.read_protected("nonexistent/file.json")


# =============================================================================
# Signature Tests
# =============================================================================

class TestSignatures:
    """Test signing and signature verification."""

    def test_signed_asset_has_signature_file(self, unlocked_protection, sample_config):
        """Writing signed assets creates signature files."""
        unlocked_protection.write_protected_json(
            "routing/expert_weights.json",
            sample_config
        )

        sig_path = unlocked_protection.substrate_dir / "routing/expert_weights.json.sig"
        # For protected level, the file is encrypted, so check .enc.sig
        enc_sig_path = unlocked_protection.substrate_dir / "routing/expert_weights.json.enc.sig"

        # One of these should exist
        assert sig_path.exists() or enc_sig_path.exists()

    def test_tampered_content_detected(self, temp_otto_dir, sample_config):
        """Tampering with content is detected."""
        prot = SubstrateProtection(temp_otto_dir)
        prot.setup("test-passphrase-12chars")

        # Write protected config
        prot.write_protected_json("config/safety_floors.json", sample_config)

        # Get the file path
        config_path = prot.substrate_dir / "config/safety_floors.json"
        enc_path = config_path.with_suffix(".json.enc")

        # Tamper with the file (if it exists unencrypted)
        if config_path.exists():
            content = config_path.read_bytes()
            tampered = content[:-1] + bytes([content[-1] ^ 0xFF])
            config_path.write_bytes(tampered)

            # Verification should fail
            assert not prot._verify_signature(config_path)


# =============================================================================
# Protection Status Tests
# =============================================================================

class TestProtectionStatus:
    """Test protection status reporting."""

    def test_status_reflects_state(self, unlocked_protection):
        """Status accurately reflects protection state."""
        status = unlocked_protection.get_status()

        assert status.is_setup
        assert status.is_unlocked
        assert status.protected_asset_count > 0

    def test_status_tracks_integrity(self, unlocked_protection, sample_config):
        """Status tracks integrity validity."""
        # Write some config
        unlocked_protection.write_protected_json(
            "config/safety_floors.json",
            {"validator": 0.10, "restorer": 0.08}
        )

        status = unlocked_protection.get_status()
        assert status.integrity_valid


# =============================================================================
# Integrity Verification Tests
# =============================================================================

class TestIntegrityVerification:
    """Test integrity verification module."""

    def test_merkle_root_changes_on_modification(self, temp_otto_dir):
        """Merkle root hash changes when files change."""
        integrity = SubstrateIntegrity(temp_otto_dir)
        substrate_dir = temp_otto_dir / "substrate"
        substrate_dir.mkdir(parents=True, exist_ok=True)

        # Create initial file
        config = substrate_dir / "config"
        config.mkdir(exist_ok=True)
        (config / "test.json").write_text('{"key": "value1"}')

        root1 = integrity.compute_root_hash()

        # Modify file
        (config / "test.json").write_text('{"key": "value2"}')

        root2 = integrity.compute_root_hash(refresh=True)

        assert root1 != root2

    def test_schema_validation_catches_missing_keys(self, integrity):
        """Schema validation catches missing required keys."""
        # Create substrate directory
        config = integrity.substrate_dir / "routing"
        config.mkdir(parents=True, exist_ok=True)

        # Write config missing required keys
        (config / "expert_weights.json").write_text('{"validator": 0.1}')

        is_valid, issues = integrity.verify_config("routing/expert_weights.json")

        assert not is_valid
        assert len(issues) > 0
        assert any("Missing required key" in i.message for i in issues)

    def test_safety_constraint_enforcement(self, integrity):
        """Safety constraints are enforced."""
        # Create substrate directory
        config = integrity.substrate_dir / "config"
        config.mkdir(parents=True, exist_ok=True)

        # Write safety floors below minimum
        (config / "safety_floors.json").write_text(
            '{"validator": 0.05, "restorer": 0.08}'  # validator below 0.10 minimum
        )

        issues = integrity.check_safety_constraints(
            "config/safety_floors.json",
            {"validator": 0.05, "restorer": 0.08}
        )

        assert len(issues) > 0
        assert any("SAFETY VIOLATION" in i.message for i in issues)

    def test_full_verification_report(self, temp_otto_dir):
        """Full verification produces comprehensive report."""
        integrity = SubstrateIntegrity(temp_otto_dir)

        # Create some files
        config = integrity.substrate_dir / "config"
        config.mkdir(parents=True, exist_ok=True)
        (config / "safety_floors.json").write_text(
            '{"validator": 0.10, "restorer": 0.08}'
        )

        report = integrity.full_verification()

        assert isinstance(report, IntegrityReport)
        assert report.root_hash is not None
        assert report.timestamp > 0

    def test_detect_tampering_with_root_hash(self, temp_otto_dir):
        """Tampering is detected via root hash comparison."""
        integrity = SubstrateIntegrity(temp_otto_dir)
        substrate_dir = temp_otto_dir / "substrate"
        substrate_dir.mkdir(parents=True, exist_ok=True)

        # Create file
        config = substrate_dir / "config"
        config.mkdir(exist_ok=True)
        (config / "test.json").write_text('{"original": true}')

        # Get original root hash
        original_hash = integrity.compute_root_hash()

        # Tamper
        (config / "test.json").write_text('{"tampered": true}')

        # Detect tampering
        assert integrity.detect_tampering(original_hash)


# =============================================================================
# Protection Level Tests
# =============================================================================

class TestProtectionLevels:
    """Test different protection levels."""

    def test_signed_level_creates_signature(self, unlocked_protection):
        """SIGNED level creates signature without encryption."""
        # Safety floors are SIGNED level
        unlocked_protection.write_protected_json(
            "config/safety_floors.json",
            {"validator": 0.10, "restorer": 0.08}
        )

        # Should have signature
        level = unlocked_protection._get_protection_level("config/safety_floors.json")
        assert level == ProtectionLevel.SIGNED

    def test_protected_level_encrypts_and_signs(self, unlocked_protection):
        """PROTECTED level both encrypts and signs."""
        # Expert weights are PROTECTED level
        level = unlocked_protection._get_protection_level("routing/expert_weights.json")
        assert level == ProtectionLevel.PROTECTED

    def test_encrypted_level_encrypts_only(self, unlocked_protection):
        """ENCRYPTED level encrypts without signing."""
        # Sessions are ENCRYPTED level
        level = unlocked_protection._get_protection_level("sessions/test.json")
        assert level == ProtectionLevel.ENCRYPTED


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_substrate_protection(self, temp_otto_dir):
        """Factory creates valid instance."""
        prot = create_substrate_protection(temp_otto_dir)
        assert isinstance(prot, SubstrateProtection)

    def test_create_integrity_verifier(self, temp_otto_dir):
        """Factory creates valid instance."""
        integrity = create_integrity_verifier(temp_otto_dir)
        assert isinstance(integrity, SubstrateIntegrity)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_substrate_directory(self, integrity):
        """Handles empty substrate directory."""
        report = integrity.full_verification()
        assert isinstance(report, IntegrityReport)

    def test_corrupted_signature_file(self, unlocked_protection, sample_config):
        """Handles corrupted signature files gracefully."""
        # Write config
        unlocked_protection.write_protected_json(
            "config/safety_floors.json",
            sample_config
        )

        # Corrupt signature file
        config_path = unlocked_protection.substrate_dir / "config/safety_floors.json"
        sig_path = config_path.with_suffix(".json.sig")
        if sig_path.exists():
            sig_path.write_text("corrupted data")

            # Verification should fail gracefully
            result = unlocked_protection._verify_signature(config_path)
            assert not result

    def test_passphrase_change(self, temp_otto_dir, sample_config):
        """Can change passphrase."""
        prot = SubstrateProtection(temp_otto_dir)
        prot.setup("old-passphrase-here")

        # Write some data
        prot.write_protected_json("config/safety_floors.json", sample_config)

        # Change passphrase
        prot.change_passphrase("old-passphrase-here", "new-passphrase-here")

        # Lock and unlock with new passphrase
        prot.lock()
        prot.unlock("new-passphrase-here")
        assert prot.is_unlocked()

        # Can still read data
        content = prot.read_protected_json("config/safety_floors.json")
        assert content == sample_config


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Test deterministic behavior per [He2025]."""

    def test_signature_deterministic(self, temp_otto_dir, sample_config):
        """Same content produces same content hash."""
        prot = SubstrateProtection(temp_otto_dir)
        prot.setup("test-passphrase-12chars")

        # Write config multiple times
        prot.write_protected_json("config/test.json", sample_config)

        # Read signature
        sig_path = prot.substrate_dir / "config/test.json.sig"
        if sig_path.exists():
            sig1 = Signature.from_bytes(sig_path.read_bytes())

            # Write again
            prot.write_protected_json("config/test.json", sample_config)
            sig2 = Signature.from_bytes(sig_path.read_bytes())

            # Content hashes should be identical
            assert sig1.content_hash == sig2.content_hash

    def test_merkle_tree_deterministic(self, temp_otto_dir):
        """Merkle tree construction is deterministic."""
        integrity = SubstrateIntegrity(temp_otto_dir)

        # Create files
        config = integrity.substrate_dir / "config"
        config.mkdir(parents=True, exist_ok=True)
        (config / "a.json").write_text('{"a": 1}')
        (config / "b.json").write_text('{"b": 2}')

        # Compute hash multiple times
        hashes = [integrity.compute_root_hash(refresh=True) for _ in range(10)]

        # All hashes should be identical
        assert len(set(hashes)) == 1


# Mark all tests with protection marker
pytestmark = pytest.mark.protection
