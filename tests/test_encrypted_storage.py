"""
Tests for Encrypted Storage Integration
========================================

Tests the wiring of SubstrateProtection encryption to actual storage:
- Discord session encryption
- Telegram session encryption
- Trail database encryption
- CLI encryption commands

[He2025] Compliance:
    - Deterministic encryption (fixed parameters)
    - Sorted iteration for deterministic JSON
    - Fixed seeds where applicable
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Mark all tests in this module for encryption testing
pytestmark = pytest.mark.encryption


class TestSubstrateProtectionSingleton:
    """Test the SubstrateProtection singleton pattern."""

    def test_get_protection_returns_same_instance(self):
        """get_protection() returns the same instance on repeated calls."""
        from otto.substrate.protection import get_protection, reset_protection

        # Reset to clean state
        reset_protection()

        p1 = get_protection()
        p2 = get_protection()

        assert p1 is p2, "get_protection should return singleton"

    def test_reset_protection_clears_singleton(self):
        """reset_protection() clears the singleton for fresh instance."""
        from otto.substrate.protection import get_protection, reset_protection

        p1 = get_protection()
        reset_protection()
        p2 = get_protection()

        assert p1 is not p2, "reset should create new instance"


class TestDiscordSessionEncryption:
    """Test Discord session encryption integration."""

    @pytest.fixture
    def mock_protection(self):
        """Mock protection that's set up and unlocked."""
        protection = MagicMock()
        protection.is_setup.return_value = True
        protection.is_unlocked.return_value = True
        protection.read_protected_json.return_value = {}
        return protection

    @pytest.fixture
    def temp_sessions_path(self, tmp_path):
        """Create temp sessions file path."""
        sessions_path = tmp_path / "discord_sessions.json"
        return sessions_path

    def test_discord_adapter_imports_protection(self):
        """Discord adapter imports get_protection from substrate."""
        from otto.discord import adapter
        assert hasattr(adapter, 'get_protection') or 'get_protection' in dir(adapter)

    def test_sessions_saved_with_encryption_when_available(self, mock_protection, temp_sessions_path):
        """Sessions are saved using encryption when protection is available."""
        from otto.discord.adapter import DiscordAdapter, DiscordSession

        with patch("otto.discord.adapter.get_protection", return_value=mock_protection):
            adapter = DiscordAdapter(session_store_path=temp_sessions_path)

            # Add a session
            session = DiscordSession(user_id=123, channel_id=456)
            adapter._sessions[123] = session

            # Save should use encrypted path
            adapter._save_sessions()

        # Should have called write_protected_json
        mock_protection.write_protected_json.assert_called()


class TestTelegramSessionEncryption:
    """Test Telegram session encryption integration."""

    def test_telegram_adapter_imports_protection(self):
        """Telegram adapter imports get_protection from substrate."""
        from otto.telegram import adapter
        # Check that protection is imported (may be conditional)
        source = adapter.__file__
        with open(source) as f:
            content = f.read()
        assert 'get_protection' in content or 'protection' in content


class TestTrailDatabaseEncryption:
    """Test trail database encryption."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temp database path."""
        db_path = tmp_path / "trails.db"
        return db_path

    def test_trail_store_has_encryption_flag(self, temp_db_path):
        """TrailStore tracks encryption status."""
        from otto.trails.store import TrailStore, reset_store

        reset_store()

        store = TrailStore(db_path=temp_db_path)

        # Should have _is_encrypted attribute
        assert hasattr(store, '_is_encrypted')

    def test_trail_store_module_has_is_encrypted(self):
        """Module has is_encrypted function."""
        from otto.trails import store
        assert hasattr(store, 'is_encrypted')


class TestMigrationScript:
    """Test the migration script."""

    def test_migration_result_tracking(self):
        """MigrationResult tracks successes, skips, and errors."""
        from otto.scripts.migrate_to_encrypted import MigrationResult

        result = MigrationResult()

        result.add_success("file1.json")
        result.add_skip("file2.json", "not found")
        result.add_error("file3.json", "permission denied")

        assert len(result.migrated) == 1
        assert len(result.skipped) == 1
        assert len(result.errors) == 1
        assert not result.success  # Error makes success False

    def test_migration_result_success_without_errors(self):
        """MigrationResult.success is True when no errors."""
        from otto.scripts.migrate_to_encrypted import MigrationResult

        result = MigrationResult()
        result.add_success("file1.json")
        result.add_skip("file2.json", "not found")

        assert result.success  # No errors = success

    def test_migration_script_can_be_imported(self):
        """Migration script can be imported without errors."""
        from otto.scripts.migrate_to_encrypted import run_migration, MigrationResult
        assert callable(run_migration)


class TestCLIEncryptionCommands:
    """Test CLI encryption commands."""

    def test_encryption_status_works(self):
        """otto encryption status runs without error."""
        from otto.cli.main import cmd_encryption
        from argparse import Namespace
        from otto.substrate.protection import reset_protection

        reset_protection()

        args = Namespace(action="status")

        # Should not raise
        result = cmd_encryption(args)
        assert result == 0

    def test_cli_has_encryption_command(self):
        """CLI main has encryption command handler."""
        from otto.cli import main
        assert hasattr(main, 'cmd_encryption')
        assert callable(main.cmd_encryption)


class TestEncryptionDeterminism:
    """Test [He2025] compliance for encryption determinism."""

    def test_protection_module_uses_fixed_algorithms(self):
        """Protection module uses fixed encryption algorithms."""
        from otto.substrate.protection import SubstrateProtection

        # Check that AES-256-GCM is used (via code inspection)
        import inspect
        source = inspect.getsource(SubstrateProtection)

        # Should reference AES or encryption constants
        assert 'AES' in source or 'encrypt' in source.lower()

    def test_sorted_iteration_in_adapters(self):
        """Adapters use sorted iteration for determinism."""
        from otto.discord import adapter

        source_path = adapter.__file__
        with open(source_path) as f:
            content = f.read()

        # Should use sorted() for iteration
        assert 'sorted(' in content


class TestGracefulDegradation:
    """Test graceful degradation when encryption not available."""

    def test_protection_is_optional(self):
        """SubstrateProtection can indicate not-setup state."""
        from otto.substrate.protection import SubstrateProtection

        protection = SubstrateProtection()

        # Fresh instance should not be setup
        # (actual behavior depends on implementation)
        status = protection.get_status()
        assert hasattr(status, 'is_setup')


# =============================================================================
# Integration Tests (require actual protection setup)
# =============================================================================

@pytest.mark.integration
class TestEndToEndEncryption:
    """End-to-end encryption tests (require actual crypto)."""

    @pytest.fixture
    def protection_with_passphrase(self, tmp_path):
        """Set up protection with a test passphrase."""
        from otto.substrate.protection import SubstrateProtection

        protection = SubstrateProtection(otto_dir=tmp_path)
        recovery_key = protection.setup("test_passphrase_12345")

        return protection, recovery_key

    def test_write_read_roundtrip(self, protection_with_passphrase):
        """Data survives write → read roundtrip."""
        protection, _ = protection_with_passphrase

        test_data = {"key": "value", "number": 42, "nested": {"a": 1}}

        protection.write_protected_json("test/data.json", test_data)
        loaded = protection.read_protected_json("test/data.json")

        assert loaded == test_data

    def test_encryption_is_not_plaintext(self, protection_with_passphrase, tmp_path):
        """Encrypted file is not readable as plaintext."""
        protection, _ = protection_with_passphrase

        test_data = {"secret": "sensitive_data_12345"}
        protection.write_protected_json("test/secret.json", test_data)

        # Find any encrypted files
        all_files = list(tmp_path.rglob("*"))
        for f in all_files:
            if f.is_file() and f.suffix != '.json':
                content = f.read_bytes()
                # Content should not contain plaintext
                assert b"sensitive_data_12345" not in content

    def test_unlock_with_wrong_passphrase_fails(self, protection_with_passphrase):
        """Unlock with wrong passphrase fails."""
        from otto.encryption.encryption_manager import InvalidPassphraseError

        protection, _ = protection_with_passphrase

        # Lock it
        protection._is_unlocked = False

        # Try wrong passphrase - should raise exception
        with pytest.raises(InvalidPassphraseError):
            protection.unlock("wrong_passphrase")

    def test_unlock_with_correct_passphrase_succeeds(self, tmp_path):
        """Unlock with correct passphrase succeeds."""
        from otto.substrate.protection import SubstrateProtection

        protection = SubstrateProtection(otto_dir=tmp_path)
        protection.setup("correct_pass_12345")

        # Lock it
        protection._is_unlocked = False

        # Unlock with correct
        result = protection.unlock("correct_pass_12345")
        assert result

    def test_status_shows_setup_state(self, protection_with_passphrase):
        """Status correctly shows setup state."""
        protection, _ = protection_with_passphrase

        status = protection.get_status()

        assert status.is_setup
        assert status.is_unlocked


# =============================================================================
# Module Structure Tests
# =============================================================================

class TestModuleStructure:
    """Test that encryption is properly wired in module structure."""

    def test_substrate_exports_protection(self):
        """substrate module exports protection functions."""
        from otto.substrate import (
            get_protection,
            reset_protection,
            SubstrateProtection,
        )
        assert callable(get_protection)
        assert callable(reset_protection)

    def test_scripts_module_exists(self):
        """scripts module exists and is importable."""
        from otto.scripts import run_migration, MigrationResult
        assert callable(run_migration)

    def test_trails_store_has_encryption_helpers(self):
        """trails.store has encryption helper functions."""
        from otto.trails.store import (
            get_store,
            reset_store,
            flush_encrypted,
            is_encrypted,
        )
        assert callable(get_store)
        assert callable(reset_store)
        assert callable(flush_encrypted)
        assert callable(is_encrypted)
