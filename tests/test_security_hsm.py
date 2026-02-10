"""
Tests for HSM/PKCS#11 Interface
===============================

Tests for Hardware Security Module support.
"""

import pytest

from otto.security.hsm import (
    HSMInterface,
    HSMConfig,
    HSMKeyInfo,
    HSMKeyType,
    HSMSlotInfo,
    HSMOperation,
    HSMException,
    HSMNotAvailable,
    HSMKeyNotFound,
    HSMOperationFailed,
    MockHSM,
    PKCS11HSM,
    create_hsm,
    get_hsm,
    is_hsm_available,
)


class TestHSMConfig:
    """Tests for HSM configuration."""

    def test_default_config(self):
        """Default config is valid."""
        config = HSMConfig()
        assert config.slot == 0
        assert config.use_mock is False

    def test_mock_config(self):
        """Can create mock config."""
        config = HSMConfig(use_mock=True)
        assert config.use_mock is True

    def test_config_to_dict(self):
        """Config serializes without PIN."""
        config = HSMConfig(
            library_path="/usr/lib/softhsm.so",
            slot=1,
            pin="secret",
            label="TEST",
        )
        data = config.to_dict()

        assert data['library_path'] == "/usr/lib/softhsm.so"
        assert data['slot'] == 1
        assert data['label'] == "TEST"
        assert 'pin' not in data  # PIN should not be serialized


class TestHSMKeyInfo:
    """Tests for HSM key info."""

    def test_key_info_creation(self):
        """Can create key info."""
        info = HSMKeyInfo(
            key_id="key123",
            label="test-key",
            key_type=HSMKeyType.EC_P256,
            created_at=1000.0,
        )
        assert info.key_id == "key123"
        assert info.key_type == HSMKeyType.EC_P256

    def test_key_info_to_dict(self):
        """Key info serializes correctly."""
        info = HSMKeyInfo(
            key_id="key123",
            label="test-key",
            key_type=HSMKeyType.AES_256,
            created_at=1000.0,
            operations=[HSMOperation.ENCRYPT, HSMOperation.DECRYPT],
        )
        data = info.to_dict()

        assert data['key_id'] == "key123"
        assert data['key_type'] == "aes_256"
        assert 'encrypt' in data['operations']


class TestMockHSM:
    """Tests for MockHSM implementation."""

    def test_mock_is_available(self):
        """Mock HSM is always available."""
        hsm = MockHSM()
        assert hsm.is_available() is True

    def test_mock_get_slots(self):
        """Can get mock slots."""
        hsm = MockHSM()
        slots = hsm.get_slots()

        assert len(slots) == 1
        assert slots[0].slot_id == 0
        assert "Mock" in slots[0].manufacturer

    def test_generate_ec_key(self):
        """Can generate EC key."""
        hsm = MockHSM()
        key = hsm.generate_key(
            label="test-ec-key",
            key_type=HSMKeyType.EC_P256,
        )

        assert key.label == "test-ec-key"
        assert key.key_type == HSMKeyType.EC_P256
        assert len(key.key_id) == 16
        assert HSMOperation.SIGN in key.operations
        assert HSMOperation.VERIFY in key.operations

    def test_generate_rsa_key(self):
        """Can generate RSA key."""
        hsm = MockHSM()
        key = hsm.generate_key(
            label="test-rsa-key",
            key_type=HSMKeyType.RSA_2048,
        )

        assert key.key_type == HSMKeyType.RSA_2048
        assert HSMOperation.SIGN in key.operations
        assert HSMOperation.ENCRYPT in key.operations

    def test_generate_aes_key(self):
        """Can generate AES key."""
        hsm = MockHSM()
        key = hsm.generate_key(
            label="test-aes-key",
            key_type=HSMKeyType.AES_256,
        )

        assert key.key_type == HSMKeyType.AES_256
        assert HSMOperation.ENCRYPT in key.operations
        assert HSMOperation.DECRYPT in key.operations

    def test_list_keys(self):
        """Can list generated keys."""
        hsm = MockHSM()

        # Generate some keys
        hsm.generate_key("key1", HSMKeyType.EC_P256)
        hsm.generate_key("key2", HSMKeyType.AES_256)

        keys = hsm.get_keys()
        assert len(keys) == 2

    def test_delete_key(self):
        """Can delete keys."""
        hsm = MockHSM()
        key = hsm.generate_key("temp-key", HSMKeyType.EC_P256)

        assert len(hsm.get_keys()) == 1

        result = hsm.delete_key(key.key_id)
        assert result is True
        assert len(hsm.get_keys()) == 0

    def test_delete_nonexistent_key(self):
        """Deleting nonexistent key returns False."""
        hsm = MockHSM()
        result = hsm.delete_key("nonexistent")
        assert result is False

    def test_sign_and_verify(self):
        """Can sign and verify data."""
        hsm = MockHSM()
        key = hsm.generate_key("signing-key", HSMKeyType.EC_P256)

        data = b"Hello, HSM!"
        signature = hsm.sign(key.key_id, data)

        assert len(signature) > 0
        assert hsm.verify(key.key_id, data, signature) is True

    def test_verify_wrong_data_fails(self):
        """Verification fails for wrong data."""
        hsm = MockHSM()
        key = hsm.generate_key("signing-key", HSMKeyType.EC_P256)

        data = b"Hello, HSM!"
        signature = hsm.sign(key.key_id, data)

        wrong_data = b"Wrong data"
        assert hsm.verify(key.key_id, wrong_data, signature) is False

    def test_verify_wrong_signature_fails(self):
        """Verification fails for wrong signature."""
        hsm = MockHSM()
        key = hsm.generate_key("signing-key", HSMKeyType.EC_P256)

        data = b"Hello, HSM!"
        wrong_sig = b"fake_signature"

        assert hsm.verify(key.key_id, data, wrong_sig) is False

    def test_encrypt_and_decrypt(self):
        """Can encrypt and decrypt data."""
        hsm = MockHSM()
        key = hsm.generate_key("encryption-key", HSMKeyType.AES_256)

        plaintext = b"Secret message!"
        ciphertext = hsm.encrypt(key.key_id, plaintext)

        assert ciphertext != plaintext
        decrypted = hsm.decrypt(key.key_id, ciphertext)
        assert decrypted == plaintext

    def test_sign_with_nonexistent_key_fails(self):
        """Signing with nonexistent key raises error."""
        hsm = MockHSM()

        with pytest.raises(HSMKeyNotFound):
            hsm.sign("nonexistent", b"data")

    def test_sign_with_encryption_key_fails(self):
        """Signing with encryption-only key raises error."""
        hsm = MockHSM()
        key = hsm.generate_key("aes-key", HSMKeyType.AES_256)

        with pytest.raises(HSMOperationFailed):
            hsm.sign(key.key_id, b"data")

    def test_get_public_key(self):
        """Can get public key."""
        hsm = MockHSM()
        key = hsm.generate_key("ec-key", HSMKeyType.EC_P256)

        public_key = hsm.get_public_key(key.key_id)
        assert len(public_key) > 0


class TestPKCS11HSM:
    """Tests for PKCS#11 HSM (requires actual HSM)."""

    def test_unavailable_without_library(self):
        """PKCS#11 HSM reports unavailable without library."""
        config = HSMConfig(library_path=None)
        hsm = PKCS11HSM(config)
        assert hsm.is_available() is False

    def test_unavailable_with_bad_path(self):
        """PKCS#11 HSM reports unavailable with bad path."""
        config = HSMConfig(library_path="/nonexistent/path.so")
        hsm = PKCS11HSM(config)
        assert hsm.is_available() is False


class TestFactoryFunctions:
    """Tests for HSM factory functions."""

    def test_create_mock_hsm(self):
        """Can create mock HSM explicitly."""
        config = HSMConfig(use_mock=True)
        hsm = create_hsm(config)

        assert isinstance(hsm, MockHSM)
        assert hsm.is_available()

    def test_create_hsm_auto_detect(self):
        """create_hsm falls back to mock if no real HSM."""
        # Without any config, should fall back to mock
        hsm = create_hsm()
        assert hsm.is_available()

    def test_get_hsm_returns_same_instance(self):
        """get_hsm returns same instance."""
        import otto.security.hsm as hsm_module
        hsm_module._hsm_instance = None  # Reset

        hsm1 = get_hsm()
        hsm2 = get_hsm()
        assert hsm1 is hsm2

    def test_is_hsm_available(self):
        """is_hsm_available works."""
        import otto.security.hsm as hsm_module
        hsm_module._hsm_instance = None  # Reset

        # Will likely be False in test environment (mock doesn't count)
        result = is_hsm_available()
        assert isinstance(result, bool)


class TestIntegration:
    """Integration tests for HSM."""

    def test_full_key_lifecycle(self):
        """Test complete key lifecycle."""
        hsm = MockHSM()

        # Generate key
        key = hsm.generate_key("lifecycle-key", HSMKeyType.EC_P256)
        assert key.key_id

        # List shows key
        keys = hsm.get_keys()
        assert any(k.key_id == key.key_id for k in keys)

        # Use key
        data = b"Test data"
        sig = hsm.sign(key.key_id, data)
        assert hsm.verify(key.key_id, data, sig)

        # Delete key
        assert hsm.delete_key(key.key_id)

        # List no longer shows key
        keys = hsm.get_keys()
        assert not any(k.key_id == key.key_id for k in keys)

    def test_multiple_keys(self):
        """Can manage multiple keys."""
        hsm = MockHSM()

        keys = [
            hsm.generate_key(f"key-{i}", HSMKeyType.EC_P256)
            for i in range(5)
        ]

        assert len(hsm.get_keys()) == 5

        # Each key works independently
        for key in keys:
            data = f"Data for {key.label}".encode()
            sig = hsm.sign(key.key_id, data)
            assert hsm.verify(key.key_id, data, sig)


class TestDeterminism:
    """Tests for Determinism."""

    def test_fixed_slot_assignments(self):
        """Slot assignments are fixed."""
        from otto.security.hsm import DEFAULT_SLOT, SIGNING_SLOT, ENCRYPTION_SLOT

        assert DEFAULT_SLOT == 0
        assert SIGNING_SLOT == 0
        assert ENCRYPTION_SLOT == 0

    def test_same_key_operations_deterministic(self):
        """Same operations produce consistent results."""
        hsm = MockHSM()
        key = hsm.generate_key("determinism-test", HSMKeyType.EC_P256)

        data = b"Deterministic test data"

        # Sign same data multiple times
        sigs = [hsm.sign(key.key_id, data) for _ in range(5)]

        # All signatures should be identical (HMAC with same key)
        assert len(set(sigs)) == 1

    def test_slot_info_stable(self):
        """Slot info is stable."""
        hsm = MockHSM()

        info1 = hsm.get_slots()[0]
        info2 = hsm.get_slots()[0]

        assert info1.slot_id == info2.slot_id
        assert info1.manufacturer == info2.manufacturer
