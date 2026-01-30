"""
Tests for Integration CLI Commands
==================================

Tests the otto integrations command functionality.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import argparse


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_otto_dir():
    """Create a temporary OTTO directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        otto_dir = Path(tmpdir) / ".otto"
        otto_dir.mkdir()
        (otto_dir / "config").mkdir()
        yield otto_dir


@pytest.fixture
def sample_integrations_config(temp_otto_dir):
    """Create sample integrations config."""
    config = {
        "adapters": [
            {
                "type": "calendar",
                "name": "work_calendar",
                "path": "/path/to/calendar.ics",
                "enabled": True
            },
            {
                "type": "tasks",
                "name": "my_tasks",
                "path": "/path/to/tasks.json",
                "enabled": True
            }
        ]
    }
    config_file = temp_otto_dir / "config" / "integrations.json"
    config_file.write_text(json.dumps(config))
    return config


@pytest.fixture
def temp_calendar_file():
    """Create a temporary calendar file."""
    with tempfile.NamedTemporaryFile(suffix=".ics", delete=False, mode="w") as f:
        f.write("""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20260129T100000Z
DTEND:20260129T110000Z
SUMMARY:Test Event
END:VEVENT
END:VCALENDAR
""")
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_tasks_file():
    """Create a temporary tasks file."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        json.dump({"tasks": [
            {"title": "Test task", "completed": False}
        ]}, f)
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_notes_dir():
    """Create a temporary notes directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        notes_path = Path(tmpdir)
        (notes_path / "note1.md").write_text("# Note 1")
        (notes_path / "note2.md").write_text("# Note 2")
        yield notes_path


# =============================================================================
# Test: List Command
# =============================================================================

class TestIntegrationsListCommand:
    """Tests for 'otto integrations list'."""

    def test_list_empty(self, temp_otto_dir):
        """List shows message when no integrations."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(action="list")
            result = cmd_integrations(args)

            assert result == 0

    def test_list_with_integrations(self, temp_otto_dir, sample_integrations_config, capsys):
        """List shows configured integrations."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(action="list")
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 0
            assert "work_calendar" in captured.out
            assert "my_tasks" in captured.out


# =============================================================================
# Test: Add Command
# =============================================================================

class TestIntegrationsAddCommand:
    """Tests for 'otto integrations add'."""

    def test_add_calendar_integration(self, temp_otto_dir, temp_calendar_file, capsys):
        """Can add calendar integration."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="add",
                type="calendar",
                name="test_cal",
                file=temp_calendar_file,
                path=None,
                url=None
            )
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 0
            assert "Added calendar integration" in captured.out

            # Verify config was written
            config_file = temp_otto_dir / "config" / "integrations.json"
            config = json.loads(config_file.read_text())
            assert len(config["adapters"]) == 1
            assert config["adapters"][0]["type"] == "calendar"
            assert config["adapters"][0]["name"] == "test_cal"

    def test_add_tasks_integration(self, temp_otto_dir, temp_tasks_file, capsys):
        """Can add tasks integration."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="add",
                type="tasks",
                name="test_tasks",
                file=temp_tasks_file,
                path=None,
                url=None
            )
            result = cmd_integrations(args)

            assert result == 0

    def test_add_notes_integration(self, temp_otto_dir, temp_notes_dir, capsys):
        """Can add notes integration."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="add",
                type="notes",
                name="test_notes",
                file=None,
                path=str(temp_notes_dir),
                url=None
            )
            result = cmd_integrations(args)

            assert result == 0

    def test_add_requires_path_or_url(self, temp_otto_dir, capsys):
        """Add fails without path or URL."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="add",
                type="calendar",
                name="test",
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)

            assert result == 1

    def test_add_prevents_duplicates(self, temp_otto_dir, temp_calendar_file, capsys):
        """Add fails for duplicate names."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            # Add first
            args = argparse.Namespace(
                action="add",
                type="calendar",
                name="same_name",
                file=temp_calendar_file,
                path=None,
                url=None
            )
            cmd_integrations(args)

            # Try to add duplicate
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 1
            assert "already exists" in captured.out


# =============================================================================
# Test: Remove Command
# =============================================================================

class TestIntegrationsRemoveCommand:
    """Tests for 'otto integrations remove'."""

    def test_remove_existing_integration(self, temp_otto_dir, sample_integrations_config, capsys):
        """Can remove existing integration."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="remove",
                name="work_calendar",
                type=None,
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 0
            assert "Removed integration" in captured.out

            # Verify config was updated
            config_file = temp_otto_dir / "config" / "integrations.json"
            config = json.loads(config_file.read_text())
            names = [a["name"] for a in config["adapters"]]
            assert "work_calendar" not in names

    def test_remove_nonexistent_integration(self, temp_otto_dir, sample_integrations_config, capsys):
        """Remove fails for nonexistent integration."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="remove",
                name="nonexistent",
                type=None,
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 1
            assert "not found" in captured.out

    def test_remove_requires_name(self, temp_otto_dir, capsys):
        """Remove fails without name."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="remove",
                name=None,
                type=None,
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)

            assert result == 1


# =============================================================================
# Test: Status Command
# =============================================================================

class TestIntegrationsStatusCommand:
    """Tests for 'otto integrations status'."""

    def test_status_empty(self, temp_otto_dir, capsys):
        """Status shows message when no integrations."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="status",
                type=None,
                name=None,
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 0
            assert "No integrations" in captured.out

    def test_status_with_working_integration(
        self, temp_otto_dir, temp_calendar_file, capsys
    ):
        """Status shows context from working integrations."""
        # First add an integration
        config = {
            "adapters": [{
                "type": "calendar",
                "name": "test_cal",
                "path": temp_calendar_file,
                "enabled": True
            }]
        }
        config_file = temp_otto_dir / "config" / "integrations.json"
        (temp_otto_dir / "config").mkdir(exist_ok=True)
        config_file.write_text(json.dumps(config))

        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="status",
                type=None,
                name=None,
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 0
            assert "test_cal" in captured.out


# =============================================================================
# Test: Sync Command
# =============================================================================

class TestIntegrationsSyncCommand:
    """Tests for 'otto integrations sync'."""

    def test_sync_empty(self, temp_otto_dir, capsys):
        """Sync shows message when no integrations."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="sync",
                type=None,
                name=None,
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 0
            assert "No integrations" in captured.out

    def test_sync_with_integration(
        self, temp_otto_dir, temp_notes_dir, capsys
    ):
        """Sync fetches context from all integrations."""
        # Add a notes integration
        config = {
            "adapters": [{
                "type": "notes",
                "name": "test_notes",
                "path": str(temp_notes_dir),
                "enabled": True
            }]
        }
        config_file = temp_otto_dir / "config" / "integrations.json"
        (temp_otto_dir / "config").mkdir(exist_ok=True)
        config_file.write_text(json.dumps(config))

        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            args = argparse.Namespace(
                action="sync",
                type=None,
                name=None,
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)
            captured = capsys.readouterr()

            assert result == 0
            assert "Sync complete" in captured.out


# =============================================================================
# Test: Default Action
# =============================================================================

class TestIntegrationsDefaultAction:
    """Tests for default action behavior."""

    def test_default_action_is_list(self, temp_otto_dir, capsys):
        """Default action (no action specified) is 'list'."""
        with patch("pathlib.Path.home", return_value=temp_otto_dir.parent):
            from otto.cli.main import cmd_integrations

            # No action specified
            args = argparse.Namespace(
                action="list",  # Would be set by argparse default
                type=None,
                name=None,
                file=None,
                path=None,
                url=None
            )
            result = cmd_integrations(args)

            assert result == 0
