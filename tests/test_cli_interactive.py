"""
Tests for CLI Interactive Mode
===============================

Tests the interactive session management.
"""

import pytest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

from otto.cli.interactive import InteractiveSession, run_interactive
from otto.intake.profile_writer import write_profile, ProfileData
from otto.cognitive_state import BurnoutLevel, EnergyLevel


class TestInteractiveSession:
    """Tests for InteractiveSession class."""

    @pytest.fixture
    def otto_dir_with_profile(self):
        """Create a temp directory with a profile."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)

            # Create profile
            profile_data = ProfileData(traits={
                "chronotype": "morning_person",
                "protection_firmness": 0.5,
                "otto_role": "companion",
            })
            write_profile(profile_data, otto_dir / "profile.usda")

            yield otto_dir

    def test_init(self, otto_dir_with_profile):
        """Test session initialization."""
        session = InteractiveSession(otto_dir_with_profile)

        assert session.otto_dir == otto_dir_with_profile
        assert session.session_goal == ""

    def test_profile_lazy_loading(self, otto_dir_with_profile):
        """Test that profile is lazy-loaded."""
        session = InteractiveSession(otto_dir_with_profile)

        # Before accessing profile
        assert session._profile is None

        # Access profile
        profile = session.profile

        # Now loaded
        assert session._profile is not None
        assert profile.chronotype == "morning_person"

    def test_protection_lazy_loading(self, otto_dir_with_profile):
        """Test that protection engine is lazy-loaded."""
        session = InteractiveSession(otto_dir_with_profile)

        assert session._protection is None

        protection = session.protection

        assert session._protection is not None

    def test_renderer_lazy_loading(self, otto_dir_with_profile):
        """Test that renderer is lazy-loaded."""
        session = InteractiveSession(otto_dir_with_profile)

        assert session._renderer is None

        renderer = session.renderer

        assert session._renderer is not None

    def test_is_exit_command(self, otto_dir_with_profile):
        """Test exit command detection."""
        session = InteractiveSession(otto_dir_with_profile)

        assert session._is_exit_command("exit") is True
        assert session._is_exit_command("quit") is True
        assert session._is_exit_command("bye") is True
        assert session._is_exit_command("goodbye") is True
        assert session._is_exit_command("/exit") is True

        assert session._is_exit_command("hello") is False
        assert session._is_exit_command("help me exit") is False

    def test_load_previous_session(self, otto_dir_with_profile):
        """Test loading previous session."""
        session = InteractiveSession(otto_dir_with_profile)

        # Create previous session data
        session_file = otto_dir_with_profile / "state" / "last_session.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps({
            "goal": "Build feature X",
            "burnout_level": "yellow",
            "exchange_count": 25,
        }))

        previous = session._load_previous_session()

        assert previous is not None
        assert previous["goal"] == "Build feature X"
        assert previous["burnout_level"] == "yellow"

    def test_load_previous_session_none_when_missing(self, otto_dir_with_profile):
        """Test None returned when no previous session."""
        session = InteractiveSession(otto_dir_with_profile)

        previous = session._load_previous_session()

        assert previous is None

    def test_save_session(self, otto_dir_with_profile):
        """Test saving session data."""
        session = InteractiveSession(otto_dir_with_profile)
        session.session_goal = "Test goal"

        state = session.state_manager.get_state()
        state.exchange_count = 15
        state.tasks_completed = 3

        session._save_session(state)

        # Check saved file
        session_file = otto_dir_with_profile / "state" / "last_session.json"
        assert session_file.exists()

        with open(session_file) as f:
            data = json.load(f)

        assert data["goal"] == "Test goal"
        assert data["exchange_count"] == 15
        assert data["tasks_completed"] == 3

    def test_update_state_from_signals(self, otto_dir_with_profile):
        """Test state update from signals."""
        from otto.prism_detector import SignalVector

        session = InteractiveSession(otto_dir_with_profile)
        state = session.state_manager.get_state()

        # Depleted energy signal
        signals = SignalVector(
            energy={"depleted": 0.8},
            energy_state="depleted"
        )

        initial_energy = state.energy_level
        session._update_state_from_signals(state, signals)

        assert state.energy_level == EnergyLevel.DEPLETED

    def test_update_state_task_completed(self, otto_dir_with_profile):
        """Test state update on task completion."""
        from otto.prism_detector import SignalVector

        session = InteractiveSession(otto_dir_with_profile)
        state = session.state_manager.get_state()

        initial_tasks = state.tasks_completed

        # Task completion signal
        signals = SignalVector(
            task={"completed": 0.8}
        )

        session._update_state_from_signals(state, signals)

        assert state.tasks_completed == initial_tasks + 1

    def test_process_request_emotional_response(self, otto_dir_with_profile):
        """Test emotional response processing."""
        from otto.prism_detector import SignalVector

        session = InteractiveSession(otto_dir_with_profile)
        state = session.state_manager.get_state()

        signals = SignalVector(
            emotional={"frustrated": 0.8},
            emotional_score=0.8
        )

        response = session._process_request("ugh this is broken", signals, state)

        # Should get empathetic response
        assert response is not None
        assert len(response) > 0

    @patch('otto.cli.interactive.create_response_generator', side_effect=ImportError("test"))
    def test_process_request_task_types(self, mock_gen, otto_dir_with_profile):
        """Test task type fallback responses (no LLM)."""
        from otto.prism_detector import SignalVector, SignalCategory

        session = InteractiveSession(otto_dir_with_profile)
        state = session.state_manager.get_state()

        # Implement task
        signals = SignalVector(
            task={"implement": 0.8},
            primary_task="implement"
        )

        response = session._process_request("implement the feature", signals, state)
        assert "build" in response.lower() or "got it" in response.lower()

        # Debug task
        signals = SignalVector(
            task={"debug": 0.8},
            primary_task="debug"
        )

        response = session._process_request("debug this issue", signals, state)
        assert "figure" in response.lower() or "got it" in response.lower()

    def test_show_status(self, otto_dir_with_profile, capsys):
        """Test status display."""
        session = InteractiveSession(otto_dir_with_profile)
        session.session_goal = "Test goal"
        state = session.state_manager.get_state()

        session._show_status(state)

        captured = capsys.readouterr()
        assert "Test goal" in captured.out or "Goal" in captured.out


class TestSessionWithNoProfile:
    """Tests for session when no profile exists."""

    def test_no_profile_exits(self, capsys):
        """Test that no profile triggers exit with message."""
        with TemporaryDirectory() as tmpdir:
            session = InteractiveSession(Path(tmpdir))

            with pytest.raises(SystemExit) as exc_info:
                session._show_welcome()

            assert exc_info.value.code == 0

            captured = capsys.readouterr()
            assert "otto-intake" in captured.out.lower() or "profile" in captured.out.lower()


class TestHandleProtection:
    """Tests for protection handling in interactive mode."""

    @pytest.fixture
    def session_with_profile(self):
        """Create session with profile."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)
            profile_data = ProfileData(traits={
                "protection_firmness": 0.5,
                "otto_role": "companion",
            })
            write_profile(profile_data, otto_dir / "profile.usda")

            session = InteractiveSession(otto_dir)
            yield session

    def test_allow_returns_true(self, session_with_profile):
        """Test ALLOW action returns True (continue)."""
        from otto.protection import ProtectionDecision, ProtectionAction

        decision = ProtectionDecision(action=ProtectionAction.ALLOW)
        state = session_with_profile.state_manager.get_state()

        result = session_with_profile._handle_protection(decision, state)

        assert result is True

    def test_mention_returns_true(self, session_with_profile, capsys):
        """Test MENTION action prints and returns True."""
        from otto.protection import ProtectionDecision, ProtectionAction

        decision = ProtectionDecision(
            action=ProtectionAction.MENTION,
            message="You've been going a while"
        )
        state = session_with_profile.state_manager.get_state()

        result = session_with_profile._handle_protection(decision, state)

        assert result is True
        captured = capsys.readouterr()
        assert "going a while" in captured.out


class TestRunInteractive:
    """Tests for run_interactive function."""

    def test_run_interactive_calls_start(self):
        """Test that run_interactive creates session and calls start."""
        with TemporaryDirectory() as tmpdir:
            otto_dir = Path(tmpdir)

            # Create profile
            profile_data = ProfileData(traits={})
            write_profile(profile_data, otto_dir / "profile.usda")

            # Mock the start method to avoid actual interaction
            with patch.object(InteractiveSession, 'start') as mock_start:
                run_interactive(otto_dir)
                mock_start.assert_called_once()
