"""
Tests for OTTO CLI commands.

Tests the new v1.0 CLI commands: intake, remember, forget, protect, config, export, wipe, sync.
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


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


# =============================================================================
# Test: remember command
# =============================================================================

class TestRememberCommand:
    """Tests for otto remember command."""

    def test_remember_creates_knowledge_file(self, mock_home):
        """Remember creates knowledge file if it doesn't exist."""
        from otto.cli.main import cmd_remember

        args = MagicMock()
        args.text = "Test memory content"
        args.tags = None

        result = cmd_remember(args)

        assert result == 0
        knowledge_file = mock_home / ".otto" / "knowledge" / "personal.json"
        assert knowledge_file.exists()

        with open(knowledge_file) as f:
            data = json.load(f)
        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "Test memory content"

    def test_remember_appends_to_existing(self, mock_home):
        """Remember appends to existing knowledge."""
        from otto.cli.main import cmd_remember

        # First memory
        args1 = MagicMock()
        args1.text = "First memory"
        args1.tags = None
        cmd_remember(args1)

        # Second memory
        args2 = MagicMock()
        args2.text = "Second memory"
        args2.tags = "work,important"
        cmd_remember(args2)

        knowledge_file = mock_home / ".otto" / "knowledge" / "personal.json"
        with open(knowledge_file) as f:
            data = json.load(f)

        assert len(data["items"]) == 2
        assert data["items"][1]["tags"] == ["work", "important"]

    def test_remember_generates_unique_ids(self, mock_home):
        """Remember generates unique IDs for each item."""
        from otto.cli.main import cmd_remember

        for i in range(3):
            args = MagicMock()
            args.text = f"Memory {i}"
            args.tags = None
            cmd_remember(args)

        knowledge_file = mock_home / ".otto" / "knowledge" / "personal.json"
        with open(knowledge_file) as f:
            data = json.load(f)

        ids = [item["id"] for item in data["items"]]
        assert len(ids) == len(set(ids))  # All unique


# =============================================================================
# Test: forget command
# =============================================================================

class TestForgetCommand:
    """Tests for otto forget command."""

    def test_forget_removes_by_content(self, mock_home):
        """Forget removes item by content match."""
        from otto.cli.main import cmd_remember, cmd_forget

        # Add memories
        args = MagicMock()
        args.text = "Important meeting tomorrow"
        args.tags = None
        cmd_remember(args)

        args.text = "Buy groceries"
        cmd_remember(args)

        # Forget one
        forget_args = MagicMock()
        forget_args.query = "groceries"
        forget_args.force = False
        result = cmd_forget(forget_args)

        assert result == 0
        knowledge_file = mock_home / ".otto" / "knowledge" / "personal.json"
        with open(knowledge_file) as f:
            data = json.load(f)

        assert len(data["items"]) == 1
        assert "meeting" in data["items"][0]["content"]

    def test_forget_removes_by_id(self, mock_home):
        """Forget removes item by exact ID."""
        from otto.cli.main import cmd_remember, cmd_forget

        args = MagicMock()
        args.text = "Test memory"
        args.tags = None
        cmd_remember(args)

        forget_args = MagicMock()
        forget_args.query = "mem_0001"
        forget_args.force = False
        result = cmd_forget(forget_args)

        assert result == 0

    def test_forget_no_match_returns_zero(self, mock_home):
        """Forget returns 0 when no match found."""
        from otto.cli.main import cmd_remember, cmd_forget

        args = MagicMock()
        args.text = "Test memory"
        args.tags = None
        cmd_remember(args)

        forget_args = MagicMock()
        forget_args.query = "nonexistent"
        forget_args.force = False
        result = cmd_forget(forget_args)

        assert result == 0

    def test_forget_multiple_requires_force(self, mock_home):
        """Forget with multiple matches requires --force."""
        from otto.cli.main import cmd_remember, cmd_forget

        # Add similar memories
        for i in range(3):
            args = MagicMock()
            args.text = f"Test memory {i}"
            args.tags = None
            cmd_remember(args)

        forget_args = MagicMock()
        forget_args.query = "test"  # Matches all
        forget_args.force = False
        result = cmd_forget(forget_args)

        assert result == 1  # Requires force

    def test_forget_force_removes_all_matches(self, mock_home):
        """Forget with --force removes all matches."""
        from otto.cli.main import cmd_remember, cmd_forget

        for i in range(3):
            args = MagicMock()
            args.text = f"Test memory {i}"
            args.tags = None
            cmd_remember(args)

        forget_args = MagicMock()
        forget_args.query = "test"
        forget_args.force = True
        result = cmd_forget(forget_args)

        assert result == 0
        knowledge_file = mock_home / ".otto" / "knowledge" / "personal.json"
        with open(knowledge_file) as f:
            data = json.load(f)
        assert len(data["items"]) == 0


# =============================================================================
# Test: protect command
# =============================================================================

class TestProtectCommand:
    """Tests for otto protect command."""

    def test_protect_status_default(self, mock_home):
        """Protect status shows enabled by default."""
        from otto.cli.main import cmd_protect

        args = MagicMock()
        args.action = "status"
        result = cmd_protect(args)

        assert result == 0

    def test_protect_off_disables(self, mock_home):
        """Protect off disables protection."""
        from otto.cli.main import cmd_protect

        args = MagicMock()
        args.action = "off"
        result = cmd_protect(args)

        assert result == 0
        state_file = mock_home / ".otto" / "state" / "protection.json"
        with open(state_file) as f:
            data = json.load(f)
        assert data["enabled"] is False

    def test_protect_on_enables(self, mock_home):
        """Protect on enables protection."""
        from otto.cli.main import cmd_protect

        # Disable first
        args = MagicMock()
        args.action = "off"
        cmd_protect(args)

        # Enable
        args.action = "on"
        result = cmd_protect(args)

        assert result == 0
        state_file = mock_home / ".otto" / "state" / "protection.json"
        with open(state_file) as f:
            data = json.load(f)
        assert data["enabled"] is True


# =============================================================================
# Test: config command
# =============================================================================

class TestConfigCommand:
    """Tests for otto config command."""

    def test_config_set_value(self, mock_home):
        """Config sets a value."""
        from otto.cli.main import cmd_config

        args = MagicMock()
        args.key = "test_key"
        args.value = "test_value"
        result = cmd_config(args)

        assert result == 0
        config_file = mock_home / ".otto" / "config" / "otto.json"
        with open(config_file) as f:
            data = json.load(f)
        assert data["test_key"] == "test_value"

    def test_config_get_value(self, mock_home, capsys):
        """Config gets a value."""
        from otto.cli.main import cmd_config

        # Set first
        args = MagicMock()
        args.key = "my_setting"
        args.value = "my_value"
        cmd_config(args)

        # Get
        args.value = None
        result = cmd_config(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "my_setting = my_value" in captured.out


# =============================================================================
# Test: export command
# =============================================================================

class TestExportCommand:
    """Tests for otto export command."""

    def test_export_creates_zip(self, mock_home, tmp_path):
        """Export creates a zip file."""
        from otto.cli.main import cmd_export, cmd_remember

        # Create some data
        args = MagicMock()
        args.text = "Test memory"
        args.tags = None
        cmd_remember(args)

        # Export
        export_args = MagicMock()
        export_args.output = str(tmp_path / "export.zip")
        result = cmd_export(export_args)

        assert result == 0
        assert (tmp_path / "export.zip").exists()

    def test_export_no_data_returns_zero(self, tmp_path, monkeypatch):
        """Export with no data returns 0."""
        from otto.cli.main import cmd_export

        # Point to empty dir
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        args = MagicMock()
        args.output = None
        result = cmd_export(args)

        assert result == 0


# =============================================================================
# Test: wipe command
# =============================================================================

class TestWipeCommand:
    """Tests for otto wipe command."""

    def test_wipe_requires_confirm(self, mock_home):
        """Wipe requires --confirm flag."""
        from otto.cli.main import cmd_wipe, cmd_remember

        # Create data
        args = MagicMock()
        args.text = "Test"
        args.tags = None
        cmd_remember(args)

        # Wipe without confirm
        wipe_args = MagicMock()
        wipe_args.confirm = False
        wipe_args.no_backup = False
        result = cmd_wipe(wipe_args)

        assert result == 1  # Should fail without confirm
        assert (mock_home / ".otto").exists()

    def test_wipe_with_confirm_deletes(self, mock_home):
        """Wipe with --confirm deletes data."""
        from otto.cli.main import cmd_wipe, cmd_remember

        # Create data
        args = MagicMock()
        args.text = "Test"
        args.tags = None
        cmd_remember(args)

        # Wipe with confirm
        wipe_args = MagicMock()
        wipe_args.confirm = True
        wipe_args.no_backup = True
        result = cmd_wipe(wipe_args)

        assert result == 0
        assert not (mock_home / ".otto").exists()

    def test_wipe_creates_backup_by_default(self, mock_home):
        """Wipe creates backup unless --no-backup."""
        from otto.cli.main import cmd_wipe, cmd_remember

        # Create data
        args = MagicMock()
        args.text = "Test"
        args.tags = None
        cmd_remember(args)

        # Wipe with backup
        wipe_args = MagicMock()
        wipe_args.confirm = True
        wipe_args.no_backup = False
        result = cmd_wipe(wipe_args)

        assert result == 0
        # Check backup was created
        backups = list(mock_home.glob(".otto_backup_*"))
        assert len(backups) == 1


# =============================================================================
# Test: sync command
# =============================================================================

class TestSyncCommand:
    """Tests for otto sync command."""

    def test_sync_status_no_config(self, mock_home, capsys):
        """Sync status with no config shows not configured."""
        from otto.cli.main import cmd_sync

        args = MagicMock()
        args.action = "status"
        result = cmd_sync(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "not configured" in captured.out.lower()

    def test_sync_now_requires_config(self, mock_home):
        """Sync now requires configuration."""
        from otto.cli.main import cmd_sync

        args = MagicMock()
        args.action = "now"
        result = cmd_sync(args)

        assert result == 1

    def test_sync_setup_shows_options(self, mock_home, capsys):
        """Sync setup shows available backends."""
        from otto.cli.main import cmd_sync

        args = MagicMock()
        args.action = "setup"
        result = cmd_sync(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "WebDAV" in captured.out
        assert "[Available]" in captured.out
        assert "S3" in captured.out


# =============================================================================
# Test: intake command
# =============================================================================

class TestIntakeCommand:
    """Tests for otto intake command."""

    def test_intake_skips_if_profile_exists(self, mock_home, capsys):
        """Intake skips if profile already exists."""
        from otto.cli.main import cmd_intake

        # Create existing profile
        profile_path = mock_home / ".otto" / "profile.usda"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text("# existing profile")

        args = MagicMock()
        args.reset = False
        result = cmd_intake(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "already exists" in captured.out.lower()

    def test_intake_reset_flag_allows_overwrite(self, mock_home):
        """Intake --reset allows overwriting existing profile."""
        # Create existing profile
        profile_path = mock_home / ".otto" / "profile.usda"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text("# existing profile")

        args = MagicMock()
        args.reset = True

        # Mock run_intake to avoid interactive prompts
        with patch("otto.intake.run_intake") as mock_run:
            mock_profile = MagicMock()
            mock_profile.traits = {}
            mock_run.return_value = mock_profile

            with patch("otto.intake.write_profile"):
                from otto.cli.main import cmd_intake
                result = cmd_intake(args)

        assert mock_run.called


# =============================================================================
# Test: Command parsing
# =============================================================================

class TestCommandParsing:
    """Tests for argument parsing."""

    def test_remember_requires_text(self):
        """Remember command requires text argument."""
        from otto.cli.main import main
        import sys

        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, "argv", ["otto", "remember"]):
                main()

        assert exc_info.value.code == 2  # argparse error

    def test_protect_accepts_actions(self):
        """Protect command accepts on/off/status."""
        from otto.cli.main import main
        import sys

        for action in ["on", "off", "status"]:
            with patch("otto.cli.main.cmd_protect", return_value=0) as mock:
                with patch.object(sys, "argv", ["otto", "protect", action]):
                    main()
                assert mock.called

    def test_sync_accepts_actions(self):
        """Sync command accepts status/now/setup."""
        from otto.cli.main import main
        import sys

        for action in ["status", "now", "setup"]:
            with patch("otto.cli.main.cmd_sync", return_value=0) as mock:
                with patch.object(sys, "argv", ["otto", "sync", action]):
                    main()
                assert mock.called
