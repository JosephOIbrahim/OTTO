"""
Tests for File Encryption Module
=================================

Tests for file-level encryption operations.
"""

import pytest
import secrets
import tempfile
from pathlib import Path

from otto.encryption import (
    FileEncryptor,
    EncryptedFileHeader,
    FileEncryptionError,
    FileNotEncryptedError,
    FileAlreadyEncryptedError,
    get_encrypted_path,
    get_decrypted_path,
    is_encrypted_file,
    find_encrypted_files,
    find_files_to_encrypt,
    ENCRYPTED_EXTENSION,
    FILE_VERSION,
    KEY_LENGTH,
    SALT_LENGTH,
    CRYPTO_AVAILABLE,
)


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
class TestFileEncryptor:
    """Tests for FileEncryptor."""

    @pytest.fixture
    def key(self):
        """Generate a test key."""
        return secrets.token_bytes(KEY_LENGTH)

    @pytest.fixture
    def salt(self):
        """Generate a test salt."""
        return secrets.token_bytes(SALT_LENGTH)

    @pytest.fixture
    def encryptor(self, key, salt):
        """Create a FileEncryptor instance."""
        return FileEncryptor(key, salt)

    def test_encrypt_file(self, encryptor):
        """Encrypt a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            source = Path(tmpdir) / "test.txt"
            source.write_text("secret content")

            # Encrypt
            dest = encryptor.encrypt_file(source, delete_original=False)

            assert dest.exists()
            assert dest.suffix == ENCRYPTED_EXTENSION
            assert source.exists()  # Not deleted

    def test_encrypt_file_deletes_original(self, encryptor):
        """Encrypt deletes original by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test.txt"
            source.write_text("secret content")

            encryptor.encrypt_file(source, delete_original=True)

            assert not source.exists()

    def test_decrypt_to_memory(self, encryptor):
        """Decrypt file to memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and encrypt
            source = Path(tmpdir) / "test.txt"
            content = "secret content"
            source.write_text(content)

            encrypted_path = encryptor.encrypt_file(source, delete_original=False)

            # Decrypt to memory
            decrypted = encryptor.decrypt_file_to_memory(encrypted_path)

            assert decrypted == content.encode()

    def test_decrypt_to_string(self, encryptor):
        """Decrypt file to string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test.txt"
            content = "secret content with unicode: 世界"
            source.write_text(content, encoding='utf-8')

            encrypted_path = encryptor.encrypt_file(source, delete_original=False)
            decrypted = encryptor.decrypt_file_to_string(encrypted_path)

            assert decrypted == content

    def test_encrypt_nonexistent_file_raises(self, encryptor):
        """Encrypting nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            encryptor.encrypt_file(Path("/nonexistent/file.txt"))

    def test_encrypt_already_encrypted_raises(self, encryptor):
        """Encrypting already encrypted file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            encrypted = Path(tmpdir) / "test.txt.enc"
            encrypted.write_bytes(b"data")

            with pytest.raises(FileAlreadyEncryptedError):
                encryptor.encrypt_file(encrypted)

    def test_decrypt_nonexistent_file_raises(self, encryptor):
        """Decrypting nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            encryptor.decrypt_file_to_memory(Path("/nonexistent/file.enc"))

    def test_decrypt_non_encrypted_file_raises(self, encryptor):
        """Decrypting non-encrypted file raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plain = Path(tmpdir) / "plain.txt"
            plain.write_text("not encrypted")

            with pytest.raises(FileNotEncryptedError):
                encryptor.decrypt_file_to_memory(plain)

    def test_wrong_key_fails_decryption(self, salt):
        """Wrong key fails decryption."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key1 = secrets.token_bytes(KEY_LENGTH)
            key2 = secrets.token_bytes(KEY_LENGTH)

            encryptor1 = FileEncryptor(key1, salt)
            encryptor2 = FileEncryptor(key2, salt)

            source = Path(tmpdir) / "test.txt"
            source.write_text("secret")

            encrypted = encryptor1.encrypt_file(source, delete_original=False)

            from otto.encryption import DecryptionError
            with pytest.raises(DecryptionError):
                encryptor2.decrypt_file_to_memory(encrypted)

    def test_custom_destination(self, encryptor):
        """Custom destination path works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.txt"
            source.write_text("content")

            dest = Path(tmpdir) / "subdir" / "encrypted.data"

            result = encryptor.encrypt_file(source, dest=dest, delete_original=False)

            assert result == dest
            assert dest.exists()


class TestEncryptedFileHeader:
    """Tests for EncryptedFileHeader."""

    def test_to_bytes_from_bytes_roundtrip(self):
        """Header serialization roundtrip."""
        salt = secrets.token_bytes(SALT_LENGTH)
        header = EncryptedFileHeader(version=FILE_VERSION, salt=salt)

        serialized = header.to_bytes()
        restored = EncryptedFileHeader.from_bytes(serialized)

        assert restored.version == header.version
        assert restored.salt == header.salt

    def test_header_size(self):
        """Header has correct size."""
        size = EncryptedFileHeader.header_size()
        assert size == 1 + SALT_LENGTH  # version + salt

    def test_too_short_data_raises(self):
        """Too short data raises error."""
        with pytest.raises(FileEncryptionError):
            EncryptedFileHeader.from_bytes(b"short")


class TestPathUtilities:
    """Tests for path utility functions."""

    def test_get_encrypted_path(self):
        """get_encrypted_path adds extension."""
        path = Path("/path/to/file.txt")
        encrypted = get_encrypted_path(path)
        assert encrypted == Path("/path/to/file.txt.enc")

    def test_get_decrypted_path(self):
        """get_decrypted_path removes extension."""
        path = Path("/path/to/file.txt.enc")
        decrypted = get_decrypted_path(path)
        assert decrypted == Path("/path/to/file.txt")

    def test_get_decrypted_path_not_encrypted_raises(self):
        """get_decrypted_path on non-encrypted raises."""
        with pytest.raises(ValueError):
            get_decrypted_path(Path("/path/to/file.txt"))

    def test_is_encrypted_file(self):
        """is_encrypted_file checks extension."""
        assert is_encrypted_file(Path("file.enc"))
        assert is_encrypted_file(Path("file.txt.enc"))
        assert not is_encrypted_file(Path("file.txt"))
        assert not is_encrypted_file(Path("file.encrypted"))


class TestFindFunctions:
    """Tests for file finding functions."""

    def test_find_encrypted_files(self):
        """find_encrypted_files finds .enc files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create some files
            (base / "plain.txt").write_text("plain")
            (base / "encrypted.txt.enc").write_bytes(b"encrypted")
            (base / "subdir").mkdir()
            (base / "subdir" / "nested.enc").write_bytes(b"nested")

            found = find_encrypted_files(base)

            assert len(found) == 2
            names = {f.name for f in found}
            assert "encrypted.txt.enc" in names
            assert "nested.enc" in names

    def test_find_files_to_encrypt(self):
        """find_files_to_encrypt finds matching patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create files matching patterns
            (base / "data.usda").write_text("usda")
            (base / "config.json").write_text("{}")
            (base / "already.usda.enc").write_bytes(b"encrypted")
            (base / "other.py").write_text("python")

            found = find_files_to_encrypt(base)

            names = {f.name for f in found}
            assert "data.usda" in names
            assert "config.json" in names
            assert "already.usda.enc" not in names  # Skip encrypted
            assert "other.py" not in names  # Doesn't match patterns
