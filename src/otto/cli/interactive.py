"""
OTTO Interactive Mode
=====================

Main conversation loop with OTTO.

Flow:
1. Load profile (from intake or defaults)
2. Check for previous session (handoff)
3. Enter conversation loop:
   a. Get user input
   b. Detect signals (PRISM)
   c. Check protection
   d. Generate response
   e. Update state
   f. Show status line every 10 exchanges
4. On exit: save session for continuity

This is the primary user-facing interface for OTTO.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import logging

from ..profile_loader import ProfileLoader, ResolvedProfile, load_profile
from ..cognitive_state import (
    CognitiveState,
    CognitiveStateManager,
    BurnoutLevel,
    MomentumPhase,
)
from ..prism_detector import PRISMDetector, SignalVector, create_detector
from ..protection import ProtectionEngine, ProtectionDecision, ProtectionAction
from ..render import HumanRender, render_welcome

logger = logging.getLogger(__name__)

# OTTO ASCII face
OTTO_FACE = """
    ╭──────────╮
    │  ◉    ◉  │
    │    ──    │
    │   ╰──╯   │
    ╰──────────╯
"""

OTTO_FACE_SMALL = "◉‿◉"


class InteractiveSession:
    """
    Manages an interactive OTTO session.

    Coordinates between:
    - ProfileLoader: User preferences
    - CognitiveStateManager: State tracking
    - PRISMDetector: Signal detection
    - ProtectionEngine: Protection decisions
    - HumanRender: Output formatting
    """

    def __init__(self, otto_dir: Path = None):
        """
        Initialize interactive session.

        Args:
            otto_dir: OTTO directory (default: ~/.otto)
        """
        self.otto_dir = otto_dir or Path.home() / ".otto"

        # Core components
        self.profile_loader = ProfileLoader(self.otto_dir)
        self.state_manager = CognitiveStateManager(self.otto_dir / "state")
        self.detector = create_detector()

        # Lazy-initialized components
        self._profile: Optional[ResolvedProfile] = None
        self._protection: Optional[ProtectionEngine] = None
        self._renderer: Optional[HumanRender] = None

        # Session tracking
        self.session_goal: str = ""
        self.session_start: float = time.time()
        self._last_status_exchange: int = 0

    @property
    def profile(self) -> ResolvedProfile:
        """Get profile, loading if needed."""
        if self._profile is None:
            self._profile = self.profile_loader.load()
        return self._profile

    @property
    def protection(self) -> ProtectionEngine:
        """Get protection engine, creating if needed."""
        if self._protection is None:
            self._protection = ProtectionEngine(self.profile)
        return self._protection

    @property
    def renderer(self) -> HumanRender:
        """Get renderer, creating if needed."""
        if self._renderer is None:
            self._renderer = HumanRender(otto_role=self.profile.otto_role)
        return self._renderer

    def start(self) -> None:
        """
        Start the interactive session.

        Main entry point for the interactive CLI.
        """
        try:
            self._show_welcome()
            self._run_loop()
        except KeyboardInterrupt:
            self._handle_exit()
        except EOFError:
            self._handle_exit()

    def _show_welcome(self) -> None:
        """Show welcome message and check for previous session."""
        # Check if profile exists
        if not self.profile_loader.profile_exists():
            print(OTTO_FACE)
            print("Welcome to OTTO.")
            print()
            print("I don't have your profile yet.")
            print("Run 'otto-intake' first to set up your preferences.")
            print()
            sys.exit(0)

        # Load state
        state = self.state_manager.load()

        # Check for previous session
        previous = self._load_previous_session()

        print(OTTO_FACE_SMALL)
        welcome = render_welcome(previous, self.profile.otto_role)
        print(welcome)
        print()

        # If we have a previous session with a goal, ask if continuing
        if previous and previous.get("goal"):
            goal = previous["goal"]
            response = input(f"Continue with '{goal}'? (y/n/new): ").strip().lower()
            if response in ("y", "yes", ""):
                self.session_goal = goal
                print(f"Continuing: {goal}")
            elif response in ("new", "n", "no"):
                self.session_goal = input("What's the goal for today? ").strip()
            else:
                self.session_goal = response  # Treat as new goal
        else:
            self.session_goal = input("What's the goal for today? ").strip()

        print()

    def _run_loop(self) -> None:
        """Main conversation loop."""
        state = self.state_manager.get_state()

        while True:
            # Get input
            try:
                user_input = input(f"{OTTO_FACE_SMALL} > ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            # Check for exit commands
            if self._is_exit_command(user_input):
                break

            # Increment exchange
            state.increment_exchange()

            # Detect signals
            signals = self.detector.detect(user_input)

            # Check protection
            decision = self.protection.check(state, signals)

            # Handle protection decision
            should_continue = self._handle_protection(decision, state)
            if not should_continue:
                # User chose to stop
                break

            # Update state based on signals
            self._update_state_from_signals(state, signals)

            # Process the actual request
            response = self._process_request(user_input, signals, state)
            print(response)
            print()

            # Show status line every 10 exchanges
            if state.exchange_count - self._last_status_exchange >= 10:
                self._show_status(state)
                self._last_status_exchange = state.exchange_count

            # Save state
            self.state_manager.save()

    def _is_exit_command(self, text: str) -> bool:
        """Check if input is an exit command."""
        exit_commands = [
            "exit", "quit", "bye", "goodbye", "done",
            "stop", "end", "/exit", "/quit", "goodnight"
        ]
        return text.lower() in exit_commands

    def _handle_protection(
        self,
        decision: ProtectionDecision,
        state: CognitiveState
    ) -> bool:
        """
        Handle a protection decision.

        Returns:
            True to continue, False to stop
        """
        if decision.action == ProtectionAction.ALLOW:
            return True

        # Show protection message
        if decision.message:
            print()
            print(f"[OTTO] {decision.message}")

        if decision.suggestion:
            print(f"       {decision.suggestion}")

        print()

        # For mention, just continue
        if decision.action == ProtectionAction.MENTION:
            return True

        # For suggest/require, ask for confirmation
        if decision.action == ProtectionAction.SUGGEST_BREAK:
            response = input("Take a break? (y/n): ").strip().lower()
            if response in ("y", "yes"):
                print("Good call. Session saved.")
                return False
            else:
                # Record override
                new_decision = self.protection.handle_user_response(response, decision)
                if new_decision.override_logged:
                    print("Noted. Let's continue.")
                return True

        elif decision.action == ProtectionAction.REQUIRE_CONFIRM:
            if not decision.can_override:
                print("Session ending. Get some rest.")
                return False

            response = input("Continue anyway? (yes to confirm): ").strip().lower()
            if response == "yes":
                new_decision = self.protection.handle_user_response(response, decision)
                print("Okay, but I'm watching.")
                return True
            else:
                print("Good call. Session saved.")
                return False

        return True

    def _update_state_from_signals(
        self,
        state: CognitiveState,
        signals: SignalVector
    ) -> None:
        """Update cognitive state based on detected signals."""
        # Energy signals → energy level
        if signals.energy_state == "depleted":
            state.batch_update({"energy_level": "depleted"})
        elif signals.energy_state == "low":
            state.batch_update({"energy_level": "low"})
        elif signals.energy_state == "high":
            state.batch_update({"energy_level": "high"})

        # Task completion → momentum
        if signals.task_completed():
            state.complete_task()

        # Emotional signals → burnout escalation
        if signals.requires_intervention():
            state.escalate_burnout()

        # Mode signals → mode update
        if signals.mode_detected == "recovery":
            state.batch_update({"mode": "recovery"})

    def _process_request(
        self,
        user_input: str,
        signals: SignalVector,
        state: CognitiveState
    ) -> str:
        """
        Process the user's request.

        In the full implementation, this would integrate with an LLM.
        For Phase 1, we return acknowledgment and detected signals.
        """
        # Check for emotional response needed
        emotional_response = self.renderer.render_emotional_response(signals)
        if emotional_response:
            return emotional_response

        # Check for task completion celebration
        if signals.task_completed():
            return self.renderer.render_celebration("medium_win")

        # Default response - acknowledge and note detected signals
        priority = signals.get_priority_signal()

        if priority[0].name == "TASK":
            task_responses = {
                "implement": "Got it. Let's build this.",
                "debug": "Let's figure this out.",
                "plan": "Okay, let's think this through.",
                "research": "I'll help you explore.",
                "review": "Let's take a look.",
            }
            return task_responses.get(priority[1], "Understood.")

        return "Got it."

    def _show_status(self, state: CognitiveState) -> None:
        """Show status line."""
        status = self.renderer.render_status_line(
            state,
            goal=self.session_goal,
            expert="Direct"
        )
        print()
        print(status)
        print()

    def _handle_exit(self) -> None:
        """Handle session exit."""
        print()
        state = self.state_manager.get_state()

        # Save session for continuity
        self._save_session(state)

        # Show goodbye
        goodbye = self.renderer.render_goodbye(state, self.session_goal)
        print(goodbye)
        print()

    def _load_previous_session(self) -> Optional[Dict[str, Any]]:
        """Load previous session data for handoff."""
        session_file = self.otto_dir / "state" / "last_session.json"
        if not session_file.exists():
            return None

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load previous session: {e}")
            return None

    def _save_session(self, state: CognitiveState) -> None:
        """Save session data for next time."""
        session_data = {
            "goal": self.session_goal,
            "burnout_level": state.burnout_level.value,
            "energy_level": state.energy_level.value,
            "momentum_phase": state.momentum_phase.value,
            "exchange_count": state.exchange_count,
            "tasks_completed": state.tasks_completed,
            "ended_at": datetime.now().isoformat(),
            "was_frustrated": state.burnout_level in (BurnoutLevel.ORANGE, BurnoutLevel.RED),
        }

        session_file = self.otto_dir / "state" / "last_session.json"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            logger.info("Session saved for continuity")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

        # Also save cognitive state
        self.state_manager.save()

        # Save profile session state
        self.profile_loader.save_session(self.profile)


def run_interactive(otto_dir: Path = None) -> None:
    """
    Run OTTO in interactive mode.

    Main entry point for the CLI.
    """
    session = InteractiveSession(otto_dir)
    session.start()


__all__ = [
    'InteractiveSession',
    'run_interactive',
]
