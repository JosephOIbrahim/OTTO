"""
Human Render Layer
==================

Transforms cognitive state into dignity-first human language.

This is the translation boundary between OTTO's internal state tracking
and user-facing communication. Everything that reaches the user passes
through this layer.

Core Rules:
1. No clinical terms (see FORBIDDEN_WORDS)
2. Descriptions, not diagnoses
3. Supportive, not patronizing
4. Respects user's chosen OTTO role (guardian/companion/tool)
"""

import random
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

from ..cognitive_state import BurnoutLevel, MomentumPhase, EnergyLevel, CognitiveState
from ..prism_detector import SignalVector
from .phrases import (
    STATE_PHRASES,
    PROTECTION_PHRASES,
    CELEBRATION_PHRASES,
    HANDOFF_PHRASES,
    ROLE_ADJUSTED_PHRASES,
    contains_forbidden_word,
)


# =============================================================================
# Protection Event Types
# =============================================================================

@dataclass
class ProtectionEvent:
    """Represents a protection intervention."""
    event_type: str  # time_check, overuse, burnout, hyperfocus
    severity: str    # gentle, moderate, firm
    context: Dict[str, Any] = None

    def __post_init__(self):
        if self.context is None:
            self.context = {}


# =============================================================================
# Human Render Class
# =============================================================================

class HumanRender:
    """
    Transforms cognitive state to human-friendly output.

    Respects the user's OTTO role preference:
    - guardian: More proactive, protective messaging
    - companion: Balanced, supportive messaging
    - tool: Minimal, informational only
    """

    def __init__(self, otto_role: str = "companion", seed: int = None):
        """
        Initialize renderer.

        Args:
            otto_role: guardian | companion | tool
            seed: Random seed for phrase selection (for determinism)
        """
        self.otto_role = otto_role
        self._rng = random.Random(seed) if seed else random.Random()

    def render_status(self, state: CognitiveState) -> str:
        """
        Render current cognitive state as human-friendly status.

        Args:
            state: Current cognitive state

        Returns:
            Human-readable status string
        """
        burnout_key = f"burnout_{state.burnout_level.value}"
        energy_key = f"energy_{state.energy_level.value}"
        momentum_key = f"momentum_{state.momentum_phase.value}"

        burnout_phrase = STATE_PHRASES.get(burnout_key, {})
        energy_phrase = STATE_PHRASES.get(energy_key, {})
        momentum_phrase = STATE_PHRASES.get(momentum_key, {})

        # Build status based on role
        if self.otto_role == "tool":
            # Minimal, just facts
            return (
                f"{burnout_phrase.get('short', 'OK')} | "
                f"{momentum_phrase.get('short', 'Going')}"
            )

        elif self.otto_role == "guardian":
            # More descriptive
            return (
                f"{burnout_phrase.get('status', 'Doing okay')}. "
                f"{momentum_phrase.get('status', '')}."
            )

        else:  # companion (default)
            return f"{burnout_phrase.get('status', 'Doing okay')}."

    def render_status_line(
        self,
        state: CognitiveState,
        goal: str = None,
        expert: str = "Direct",
        include_time: bool = True
    ) -> str:
        """
        Render the status line shown every 10 exchanges.

        Format: [~45 min | Goal: X | Direct | 15k | GREEN | rolling]

        Args:
            state: Current cognitive state
            goal: Current session goal
            expert: Active expert
            include_time: Whether to include time estimate

        Returns:
            Formatted status line
        """
        parts = []

        if include_time:
            # Estimate time from exchange count (10 exchanges ≈ 45 min)
            minutes = int(state.exchange_count * 4.5)
            if minutes < 60:
                parts.append(f"~{minutes} min")
            else:
                hours = minutes // 60
                remaining = minutes % 60
                parts.append(f"~{hours}h {remaining}m")

        if goal:
            parts.append(f"Goal: {goal}")

        parts.append(expert)

        # Altitude shorthand
        altitude_short = {
            30000: "30k",
            15000: "15k",
            5000: "5k",
            0: "Ground"
        }
        parts.append(altitude_short.get(state.altitude.value, "30k"))

        # Burnout as color
        parts.append(state.burnout_level.value.upper())

        # Momentum
        parts.append(state.momentum_phase.value)

        return f"[{' | '.join(parts)}]"

    def render_protection(self, event: ProtectionEvent) -> str:
        """
        Render a protection message with dignity-first language.

        Args:
            event: The protection event

        Returns:
            Human-friendly protection message
        """
        phrase_key = f"{event.event_type}_{event.severity}"
        phrases = PROTECTION_PHRASES.get(phrase_key, {})

        # Get role-adjusted phrasing if available
        role_phrases = ROLE_ADJUSTED_PHRASES.get(self.otto_role, {})

        message = phrases.get("message", "Checking in")
        suggestion = phrases.get("suggestion", "")

        # Format with context
        if event.context:
            message = message.format(**event.context)
            suggestion = suggestion.format(**event.context)

        # Adjust based on role
        if self.otto_role == "tool":
            return message  # Just the info, no suggestion
        elif self.otto_role == "guardian":
            return f"{message} {suggestion}"
        else:  # companion
            if suggestion:
                return f"{message}\n{suggestion}"
            return message

    def render_celebration(
        self,
        win_size: str = "small_win",
        after_struggle: bool = False
    ) -> str:
        """
        Render a celebration message for task completion.

        Args:
            win_size: small_win | medium_win | big_win | milestone
            after_struggle: If true, use struggle-specific phrases

        Returns:
            Celebration message
        """
        if after_struggle:
            phrases = CELEBRATION_PHRASES.get("after_struggle", ["Nice."])
        else:
            phrases = CELEBRATION_PHRASES.get(win_size, ["Done."])

        return self._rng.choice(phrases)

    def render_welcome(
        self,
        previous_session: Dict[str, Any] = None,
        current_hour: int = None
    ) -> str:
        """
        Render welcome message for session start.

        Args:
            previous_session: Previous session data (if continuing)
            current_hour: Current hour for time-of-day awareness

        Returns:
            Welcome message
        """
        if self.otto_role == "tool":
            return "Ready."

        if previous_session:
            task = previous_session.get("task", "your project")
            burnout = previous_session.get("burnout_level", "green")

            if burnout in ("orange", "red"):
                return HANDOFF_PHRASES["welcome_back_tired"]
            elif previous_session.get("was_frustrated"):
                return HANDOFF_PHRASES["welcome_back_frustrated"]
            else:
                return HANDOFF_PHRASES["welcome_back_with_state"].format(
                    burnout=burnout,
                    task=task
                )

        # New session
        if current_hour is not None:
            if 5 <= current_hour < 12:
                return "Morning. What are we working on?"
            elif 12 <= current_hour < 17:
                return "Afternoon. What's the focus?"
            elif 17 <= current_hour < 21:
                return "Evening session. What's up?"
            else:
                return "Late one. What are we tackling?"

        return HANDOFF_PHRASES["new_session"]

    def render_goodbye(
        self,
        state: CognitiveState,
        task: str = None,
        progress: int = None
    ) -> str:
        """
        Render goodbye message when session ends.

        Args:
            state: Final cognitive state
            task: Current task
            progress: Progress percentage

        Returns:
            Goodbye message
        """
        if self.otto_role == "tool":
            return "Session saved."

        if state.burnout_level in (BurnoutLevel.ORANGE, BurnoutLevel.RED):
            return "Get some rest. You earned it."

        if progress and task:
            return HANDOFF_PHRASES["session_saved_with_state"].format(
                burnout=state.burnout_level.value,
                progress=progress,
                task=task
            )

        return HANDOFF_PHRASES["session_saved"]

    def render_emotional_response(self, signals: SignalVector) -> Optional[str]:
        """
        Render appropriate response to emotional signals.

        Args:
            signals: Detected signal vector

        Returns:
            Empathetic response or None if no response needed
        """
        if not signals.emotional:
            return None

        # Find highest emotional signal
        top_emotion = max(signals.emotional.items(), key=lambda x: x[1])
        emotion_name = top_emotion[0]

        phrase = STATE_PHRASES.get(emotion_name, {})
        response = phrase.get("response")

        if response and self.otto_role != "tool":
            return response

        return None

    def validate_output(self, text: str) -> bool:
        """
        Validate that output contains no forbidden clinical terms.

        Args:
            text: Text to validate

        Returns:
            True if text is clean, False if contains forbidden words
        """
        return not contains_forbidden_word(text)


# =============================================================================
# Convenience Functions
# =============================================================================

def render_status(state: CognitiveState, otto_role: str = "companion") -> str:
    """Render cognitive state as human-friendly status."""
    renderer = HumanRender(otto_role)
    return renderer.render_status(state)


def render_protection_message(
    event_type: str,
    severity: str = "gentle",
    otto_role: str = "companion",
    **context
) -> str:
    """Render a protection intervention message."""
    renderer = HumanRender(otto_role)
    event = ProtectionEvent(event_type, severity, context)
    return renderer.render_protection(event)


def render_welcome(
    previous_session: Dict[str, Any] = None,
    otto_role: str = "companion"
) -> str:
    """Render welcome message."""
    renderer = HumanRender(otto_role)
    current_hour = datetime.now().hour
    return renderer.render_welcome(previous_session, current_hour)


__all__ = [
    'HumanRender',
    'ProtectionEvent',
    'render_status',
    'render_protection_message',
    'render_welcome',
]
