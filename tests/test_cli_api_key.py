"""
Tests for OTTO CLI api-key command.

Determinism:
- Tests verify deterministic command behavior
- Same inputs → same outputs
- Fixed error message format
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
from io import StringIO

from otto.api import APIScope, APIKey, APIKeyManager


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_otto_dir(tmp_path):
    """Create a temporary .otto directory."""
    otto_dir = tmp_path / ".otto"
    otto_dir.mkdir()
    return otto_dir


@pytest.fixture
def mock_home(temp_otto_dir, monkeypatch):
    """Mock Path.home() to return temp directory."""
    parent = temp_otto_dir.parent
    monkeypatch.setattr(Path, "home", lambda: parent)
    return parent


@pytest.fixture
def mock_manager():
    """Create a mock APIKeyManager for testing."""
    manager = APIKeyManager(use_keyring=False)
    return manager


# =============================================================================
# Test: api-key create
# =============================================================================

class TestApiKeyCreate:
    """Tests for otto api-key create command."""

    def test_create_with_defaults(self, mock_home, capsys):
        """Create API key with default settings."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_key = MagicMock()
            mock_key.key_id = "abc123"
            mock_key.name = "API Key"
            mock_key.environment = "live"
            mock_key.scopes = {APIScope.READ_STATUS, APIScope.READ_STATE}
            mock_key.expires_at = None
            MockManager.return_value = mock_manager
            mock_manager.create.return_value = ("otto_live_abc123_secret", mock_key)

            args = MagicMock()
            args.action = "create"
            args.name = None
            args.scopes = None
            args.expires = None
            args.test = False

            result = cmd_api_key(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "API Key Created" in captured.out
            assert "otto_live_abc123_secret" in captured.out
            assert "abc123" in captured.out

    def test_create_with_name(self, mock_home, capsys):
        """Create API key with custom name."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_key = MagicMock()
            mock_key.key_id = "xyz789"
            mock_key.name = "My Custom Key"
            mock_key.environment = "live"
            mock_key.scopes = {APIScope.READ_STATUS}
            mock_key.expires_at = None
            MockManager.return_value = mock_manager
            mock_manager.create.return_value = ("otto_live_xyz789_secret", mock_key)

            args = MagicMock()
            args.action = "create"
            args.name = "My Custom Key"
            args.scopes = None
            args.expires = None
            args.test = False

            result = cmd_api_key(args)

            assert result == 0
            mock_manager.create.assert_called_once()
            call_kwargs = mock_manager.create.call_args.kwargs
            assert call_kwargs["name"] == "My Custom Key"

    def test_create_with_scopes(self, mock_home, capsys):
        """Create API key with specific scopes."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_key = MagicMock()
            mock_key.key_id = "scoped123"
            mock_key.name = "Scoped Key"
            mock_key.environment = "live"
            mock_key.scopes = {APIScope.READ_STATUS, APIScope.WRITE_STATE}
            mock_key.expires_at = None
            MockManager.return_value = mock_manager
            mock_manager.create.return_value = ("otto_live_scoped123_secret", mock_key)

            args = MagicMock()
            args.action = "create"
            args.name = "Scoped Key"
            args.scopes = "read:status,write:state"
            args.expires = None
            args.test = False

            result = cmd_api_key(args)

            assert result == 0
            call_kwargs = mock_manager.create.call_args.kwargs
            assert APIScope.READ_STATUS in call_kwargs["scopes"]
            assert APIScope.WRITE_STATE in call_kwargs["scopes"]

    def test_create_test_environment(self, mock_home, capsys):
        """Create API key in test environment."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_key = MagicMock()
            mock_key.key_id = "test123"
            mock_key.name = "Test Key"
            mock_key.environment = "test"
            mock_key.scopes = {APIScope.READ_STATUS}
            mock_key.expires_at = None
            MockManager.return_value = mock_manager
            mock_manager.create.return_value = ("otto_test_test123_secret", mock_key)

            args = MagicMock()
            args.action = "create"
            args.name = "Test Key"
            args.scopes = None
            args.expires = None
            args.test = True

            result = cmd_api_key(args)

            assert result == 0
            call_kwargs = mock_manager.create.call_args.kwargs
            assert call_kwargs["environment"] == "test"

    def test_create_with_expiration(self, mock_home, capsys):
        """Create API key with expiration."""
        from otto.cli.main import cmd_api_key
        import time

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_key = MagicMock()
            mock_key.key_id = "exp123"
            mock_key.name = "Expiring Key"
            mock_key.environment = "live"
            mock_key.scopes = {APIScope.READ_STATUS}
            mock_key.expires_at = time.time() + 86400 * 30  # 30 days
            MockManager.return_value = mock_manager
            mock_manager.create.return_value = ("otto_live_exp123_secret", mock_key)

            args = MagicMock()
            args.action = "create"
            args.name = "Expiring Key"
            args.scopes = None
            args.expires = 30
            args.test = False

            result = cmd_api_key(args)

            assert result == 0
            call_kwargs = mock_manager.create.call_args.kwargs
            assert call_kwargs["expires_in_days"] == 30
            captured = capsys.readouterr()
            assert "Expires:" in captured.out

    def test_create_invalid_scopes(self, mock_home, capsys):
        """Create with invalid scope should fail."""
        from otto.cli.main import cmd_api_key

        args = MagicMock()
        args.action = "create"
        args.name = "Invalid Key"
        args.scopes = "invalid:scope"
        args.expires = None
        args.test = False

        result = cmd_api_key(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out or "Valid scopes" in captured.out

    def test_create_error_handling(self, mock_home, capsys):
        """Create should handle errors gracefully."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.create.side_effect = Exception("Storage error")
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "create"
            args.name = "Error Key"
            args.scopes = None
            args.expires = None
            args.test = False

            result = cmd_api_key(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "Error" in captured.out


# =============================================================================
# Test: api-key list
# =============================================================================

class TestApiKeyList:
    """Tests for otto api-key list command."""

    def test_list_empty(self, mock_home, capsys):
        """List with no keys should show message."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.list.return_value = []
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "list"
            args.all = False

            result = cmd_api_key(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "No API keys found" in captured.out

    def test_list_with_keys(self, mock_home, capsys):
        """List should show all active keys."""
        from otto.cli.main import cmd_api_key
        import time

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_key1 = MagicMock()
            mock_key1.key_id = "key1"
            mock_key1.name = "First Key"
            mock_key1.environment = "live"
            mock_key1.scopes = {APIScope.READ_STATUS}
            mock_key1.use_count = 5
            mock_key1.last_used_at = time.time() - 3600
            mock_key1.is_revoked.return_value = False
            mock_key1.is_expired.return_value = False

            mock_key2 = MagicMock()
            mock_key2.key_id = "key2"
            mock_key2.name = "Second Key"
            mock_key2.environment = "test"
            mock_key2.scopes = {APIScope.ADMIN}
            mock_key2.use_count = 0
            mock_key2.last_used_at = None
            mock_key2.is_revoked.return_value = False
            mock_key2.is_expired.return_value = False

            mock_manager.list.return_value = [mock_key1, mock_key2]
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "list"
            args.all = False

            result = cmd_api_key(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "key1" in captured.out
            assert "key2" in captured.out
            assert "First Key" in captured.out
            assert "Second Key" in captured.out
            assert "2 total" in captured.out

    def test_list_shows_status(self, mock_home, capsys):
        """List should show revoked/expired status."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()

            mock_key = MagicMock()
            mock_key.key_id = "revoked1"
            mock_key.name = "Revoked Key"
            mock_key.environment = "live"
            mock_key.scopes = {APIScope.READ_STATUS}
            mock_key.use_count = 10
            mock_key.last_used_at = None
            mock_key.is_revoked.return_value = True
            mock_key.is_expired.return_value = False

            mock_manager.list.return_value = [mock_key]
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "list"
            args.all = True

            result = cmd_api_key(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "revoked" in captured.out.lower()

    def test_list_include_all(self, mock_home, capsys):
        """List with --all should include revoked and expired."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.list.return_value = []
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "list"
            args.all = True

            cmd_api_key(args)

            mock_manager.list.assert_called_once_with(
                include_revoked=True,
                include_expired=True,
            )


# =============================================================================
# Test: api-key revoke
# =============================================================================

class TestApiKeyRevoke:
    """Tests for otto api-key revoke command."""

    def test_revoke_success(self, mock_home, capsys):
        """Revoke should succeed with valid key_id."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.revoke.return_value = True
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "revoke"
            args.key_id = "abc123"
            args.reason = "No longer needed"

            result = cmd_api_key(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "Revoked" in captured.out
            assert "abc123" in captured.out
            mock_manager.revoke.assert_called_once_with("abc123", reason="No longer needed")

    def test_revoke_not_found(self, mock_home, capsys):
        """Revoke should fail if key not found."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.revoke.return_value = False
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "revoke"
            args.key_id = "nonexistent"
            args.reason = None

            result = cmd_api_key(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.out.lower()

    def test_revoke_requires_key_id(self, mock_home, capsys):
        """Revoke should require --key-id."""
        from otto.cli.main import cmd_api_key

        args = MagicMock()
        args.action = "revoke"
        args.key_id = None
        args.reason = None

        result = cmd_api_key(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "--key-id required" in captured.out


# =============================================================================
# Test: api-key delete
# =============================================================================

class TestApiKeyDelete:
    """Tests for otto api-key delete command."""

    def test_delete_requires_force(self, mock_home, capsys):
        """Delete should require --force flag."""
        from otto.cli.main import cmd_api_key

        args = MagicMock()
        args.action = "delete"
        args.key_id = "abc123"
        args.force = False

        result = cmd_api_key(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "Are you sure" in captured.out or "--force" in captured.out

    def test_delete_with_force(self, mock_home, capsys):
        """Delete with --force should succeed."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.delete.return_value = True
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "delete"
            args.key_id = "abc123"
            args.force = True

            result = cmd_api_key(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "Deleted" in captured.out
            assert "abc123" in captured.out

    def test_delete_not_found(self, mock_home, capsys):
        """Delete should fail if key not found."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_manager.delete.return_value = False
            MockManager.return_value = mock_manager

            args = MagicMock()
            args.action = "delete"
            args.key_id = "nonexistent"
            args.force = True

            result = cmd_api_key(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.out.lower()

    def test_delete_requires_key_id(self, mock_home, capsys):
        """Delete should require --key-id."""
        from otto.cli.main import cmd_api_key

        args = MagicMock()
        args.action = "delete"
        args.key_id = None
        args.force = True

        result = cmd_api_key(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "--key-id required" in captured.out


# =============================================================================
# Test: Unknown action
# =============================================================================

class TestApiKeyUnknown:
    """Tests for unknown action handling."""

    def test_unknown_action(self, mock_home, capsys):
        """Unknown action should fail with helpful message."""
        from otto.cli.main import cmd_api_key

        with patch('otto.api.APIKeyManager') as MockManager:
            MockManager.return_value = MagicMock()

            args = MagicMock()
            args.action = "unknown"

            result = cmd_api_key(args)

            assert result == 1
            captured = capsys.readouterr()
            assert "Unknown action" in captured.out
            assert "create" in captured.out
            assert "list" in captured.out
            assert "revoke" in captured.out
            assert "delete" in captured.out


# =============================================================================
# Test: Determinism
# =============================================================================

class TestDeterminism:
    """
    Verify CLI command output is deterministic.

    Principle: Same inputs → same outputs.
    """

    def test_list_output_deterministic(self, mock_home, capsys):
        """List output should be deterministic for same keys."""
        from otto.cli.main import cmd_api_key
        import time

        with patch('otto.api.APIKeyManager') as MockManager:
            mock_manager = MagicMock()
            mock_key = MagicMock()
            mock_key.key_id = "det123"
            mock_key.name = "Deterministic Key"
            mock_key.environment = "live"
            mock_key.scopes = {APIScope.READ_STATUS}
            mock_key.use_count = 0
            mock_key.last_used_at = None
            mock_key.is_revoked.return_value = False
            mock_key.is_expired.return_value = False
            mock_manager.list.return_value = [mock_key]
            MockManager.return_value = mock_manager

            # Run same command multiple times
            outputs = []
            for _ in range(3):
                args = MagicMock()
                args.action = "list"
                args.all = False
                cmd_api_key(args)
                captured = capsys.readouterr()
                outputs.append(captured.out)

            # All outputs should be identical
            assert outputs[0] == outputs[1] == outputs[2]

    def test_error_messages_deterministic(self, mock_home, capsys):
        """Error messages should be deterministic."""
        from otto.cli.main import cmd_api_key

        outputs = []
        for _ in range(3):
            args = MagicMock()
            args.action = "revoke"
            args.key_id = None
            args.reason = None
            cmd_api_key(args)
            captured = capsys.readouterr()
            outputs.append(captured.out)

        assert outputs[0] == outputs[1] == outputs[2]
