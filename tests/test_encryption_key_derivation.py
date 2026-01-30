"""
Tests for Key Derivation Module
================================

Tests for Argon2id key derivation and recovery key generation.
"""

import pytest
import secrets

from otto.encryption import (
    derive_key,
    generate_recovery_key,
    recovery_key_to_words,
    words_to_recovery_key,
    derive_key_from_recovery,
    validate_passphrase_strength,
    secure_compare,
    DerivedKey,
    KeyDerivationError,
    SALT_LENGTH,
    KEY_LENGTH,
    RECOVERY_KEY_LENGTH,
    ARGON2_AVAILABLE,
)


@pytest.mark.skipif(not ARGON2_AVAILABLE, reason="argon2-cffi not installed")
class TestDeriveKey:
    """Tests for key derivation."""

    def test_derives_correct_length_key(self):
        """Derived key has correct length."""
        result = derive_key("test-passphrase")
        assert len(result.key) == KEY_LENGTH

    def test_derives_correct_length_salt(self):
        """Derived salt has correct length."""
        result = derive_key("test-passphrase")
        assert len(result.salt) == SALT_LENGTH

    def test_different_passphrases_different_keys(self):
        """Different passphrases produce different keys."""
        result1 = derive_key("passphrase-one")
        result2 = derive_key("passphrase-two")
        assert result1.key != result2.key

    def test_same_passphrase_same_salt_same_key(self):
        """Same passphrase with same salt produces same key."""
        salt = secrets.token_bytes(SALT_LENGTH)
        result1 = derive_key("my-passphrase", salt=salt)
        result2 = derive_key("my-passphrase", salt=salt)
        assert result1.key == result2.key

    def test_same_passphrase_different_salt_different_key(self):
        """Same passphrase with different salt produces different key."""
        salt1 = secrets.token_bytes(SALT_LENGTH)
        salt2 = secrets.token_bytes(SALT_LENGTH)
        result1 = derive_key("my-passphrase", salt=salt1)
        result2 = derive_key("my-passphrase", salt=salt2)
        assert result1.key != result2.key

    def test_empty_passphrase_raises(self):
        """Empty passphrase raises error."""
        with pytest.raises(KeyDerivationError):
            derive_key("")

    def test_invalid_salt_length_raises(self):
        """Invalid salt length raises error."""
        with pytest.raises(KeyDerivationError):
            derive_key("passphrase", salt=b"short")

    def test_custom_parameters(self):
        """Custom Argon2 parameters work."""
        result = derive_key(
            "passphrase",
            time_cost=1,
            memory_cost=8192,
            parallelism=1,
        )
        assert len(result.key) == KEY_LENGTH


class TestDerivedKey:
    """Tests for DerivedKey dataclass."""

    def test_valid_key_and_salt(self):
        """Valid key and salt create DerivedKey."""
        key = secrets.token_bytes(KEY_LENGTH)
        salt = secrets.token_bytes(SALT_LENGTH)
        dk = DerivedKey(key=key, salt=salt)
        assert dk.key == key
        assert dk.salt == salt

    def test_invalid_key_length_raises(self):
        """Invalid key length raises error."""
        with pytest.raises(ValueError):
            DerivedKey(
                key=b"short",
                salt=secrets.token_bytes(SALT_LENGTH)
            )

    def test_invalid_salt_length_raises(self):
        """Invalid salt length raises error."""
        with pytest.raises(ValueError):
            DerivedKey(
                key=secrets.token_bytes(KEY_LENGTH),
                salt=b"short"
            )


class TestRecoveryKey:
    """Tests for recovery key generation."""

    def test_generates_correct_length(self):
        """Recovery key has correct length."""
        key = generate_recovery_key()
        assert len(key) == RECOVERY_KEY_LENGTH

    def test_generates_unique_keys(self):
        """Each call generates unique key."""
        key1 = generate_recovery_key()
        key2 = generate_recovery_key()
        assert key1 != key2

    def test_to_words_format(self):
        """recovery_key_to_words produces correct format."""
        key = generate_recovery_key()
        words = recovery_key_to_words(key)

        # Format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
        groups = words.split('-')
        assert len(groups) == 16  # 64 hex chars / 4 = 16 groups
        for group in groups:
            assert len(group) == 4
            assert all(c in '0123456789ABCDEF' for c in group)

    def test_words_roundtrip(self):
        """Recovery key survives words conversion."""
        key = generate_recovery_key()
        words = recovery_key_to_words(key)
        restored = words_to_recovery_key(words)
        assert restored == key

    def test_words_with_dashes_or_spaces(self):
        """Words conversion handles various formats."""
        key = generate_recovery_key()
        words = recovery_key_to_words(key)

        # With dashes (normal)
        assert words_to_recovery_key(words) == key

        # Without dashes
        no_dashes = words.replace('-', '')
        assert words_to_recovery_key(no_dashes) == key

        # With spaces instead of dashes
        with_spaces = words.replace('-', ' ')
        assert words_to_recovery_key(with_spaces) == key

    def test_invalid_words_raises(self):
        """Invalid recovery key format raises error."""
        with pytest.raises(ValueError):
            words_to_recovery_key("invalid")

        with pytest.raises(ValueError):
            words_to_recovery_key("ZZZZ-ZZZZ-ZZZZ-ZZZZ")  # Invalid hex

    def test_derive_from_recovery(self):
        """Recovery key can be used directly as encryption key."""
        key = generate_recovery_key()
        derived = derive_key_from_recovery(key)
        assert derived == key  # Recovery key IS the encryption key


class TestPassphraseValidation:
    """Tests for passphrase strength validation."""

    def test_valid_passphrase(self):
        """Strong passphrase passes validation."""
        valid, msg = validate_passphrase_strength("this-is-a-strong-passphrase")
        assert valid is True

    def test_too_short(self):
        """Short passphrase fails validation."""
        valid, msg = validate_passphrase_strength("short")
        assert valid is False
        assert "12 characters" in msg

    def test_common_patterns_rejected(self):
        """Common patterns are rejected."""
        valid, msg = validate_passphrase_strength("mypassword1234")
        assert valid is False
        assert "pattern" in msg.lower()

        valid, msg = validate_passphrase_strength("letmein123456")
        assert valid is False


class TestSecureCompare:
    """Tests for constant-time comparison."""

    def test_equal_values_return_true(self):
        """Equal values return True."""
        a = b"same-value-here"
        b = b"same-value-here"
        assert secure_compare(a, b) is True

    def test_different_values_return_false(self):
        """Different values return False."""
        a = b"value-one"
        b = b"value-two"
        assert secure_compare(a, b) is False

    def test_different_lengths_return_false(self):
        """Different lengths return False."""
        a = b"short"
        b = b"much-longer-value"
        assert secure_compare(a, b) is False

    def test_empty_values_equal(self):
        """Empty values are equal."""
        assert secure_compare(b"", b"") is True
