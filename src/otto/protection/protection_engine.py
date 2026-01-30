"""
Protection Engine
=================

Makes protection decisions based on:
- Current cognitive state (burnout, energy, momentum)
- User's profile (protection_firmness, otto_role, allow_override)
- Detected overuse signals
- Override history

Decision Flow:
1. Check burnout level → may require immediate intervention
2. Check overuse signals → may suggest break
3. Apply firmness threshold → determines when to intervene
4. Respect user override → but track it

The engine produces decisions, not actions. The caller (interactive.py)
decides how to present the decision to the user.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

from ..cognitive_state import CognitiveState, BurnoutLevel, EnergyLevel
from ..profile_loader import ResolvedProfile
from ..prism_detector import SignalVector
from ..render.human_render import HumanRender, ProtectionEvent
from .overuse_detector import OveruseDetector, OveruseSignal, OveruseType
from .calibration import CalibrationEngine, create_calibration_engine

logger = logging.getLogger(__name__)


class ProtectionAction(Enum):
    """Possible protection actions."""
    ALLOW = "allow"                    # Continue without comment
    MENTION = "mention"                # Continue, mention time/state
    SUGGEST_BREAK = "suggest_break"    # Suggest a break
    REQUIRE_CONFIRM = "require_confirm"  # Require confirmation to continue


@dataclass
class ProtectionDecision:
    """
    A protection decision from the engine.

    Contains what action to take, the message to show,
    and whether the user can override.
    """
    action: ProtectionAction
    message: str = ""
    suggestion: str = ""
    can_override: bool = True
    override_logged: bool = False
    trigger: str = ""  # What triggered this decision

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action": self.action.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "can_override": self.can_override,
            "trigger": self.trigger,
        }


class ProtectionEngine:
    """
    Makes protection decisions for OTTO.

    The engine combines:
    - Burnout-based gating (always applies)
    - Overuse detection (time, rapid exchange, energy mismatch)
    - User's firmness preference (how early to intervene)
    - OTTO role (guardian more protective, tool minimal)
    """

    def __init__(
        self,
        profile: ResolvedProfile,
        overuse_detector: OveruseDetector = None,
        calibration_engine: CalibrationEngine = None,
    ):
        """
        Initialize protection engine.

        Args:
            profile: User's resolved profile
            overuse_detector: Optional custom detector
            calibration_engine: Optional calibration engine for learning
        """
        self.profile = profile
        self.overuse_detector = overuse_detector or OveruseDetector()
        self.calibration = calibration_engine or create_calibration_engine()
        self.renderer = HumanRender(otto_role=profile.otto_role)

        # Track overrides this session
        self._session_overrides: int = 0
        self._last_decision: Optional[ProtectionDecision] = None

    def check(
        self,
        state: CognitiveState,
        signals: SignalVector = None
    ) -> ProtectionDecision:
        """
        Check if protection is needed.

        Args:
            state: Current cognitive state
            signals: Optional detected signal vector

        Returns:
            Protection decision
        """
        # Phase 1: Burnout-based gating (ALWAYS applies)
        burnout_decision = self._check_burnout(state)
        if burnout_decision.action != ProtectionAction.ALLOW:
            self._last_decision = burnout_decision
            return burnout_decision

        # Phase 2: Check for explicit break request in signals
        if signals and signals.user_wants_break():
            return ProtectionDecision(
                action=ProtectionAction.ALLOW,
                message="Go for it",
                suggestion="I'll keep your place",
                trigger="user_break_request"
            )

        # Phase 3: Check for user override in signals
        if signals and signals.user_overriding():
            # Use last decision's trigger if available, otherwise generic
            override_trigger = (
                self._last_decision.trigger if self._last_decision else "user_explicit_override"
            )
            self._record_override(override_trigger)
            return ProtectionDecision(
                action=ProtectionAction.ALLOW,
                message="Got it, continuing",
                override_logged=True,
                trigger="user_override"
            )

        # Phase 4: Overuse detection
        overuse_signals = self.overuse_detector.detect(state)
        if overuse_signals:
            overuse_decision = self._check_overuse(overuse_signals, state)
            if overuse_decision.action != ProtectionAction.ALLOW:
                self._last_decision = overuse_decision
                return overuse_decision

        # Phase 5: Protection signals from PRISM
        if signals and signals.requires_protection():
            protection_decision = self._check_protection_signals(signals)
            if protection_decision.action != ProtectionAction.ALLOW:
                self._last_decision = protection_decision
                return protection_decision

        # Default: Allow
        return ProtectionDecision(
            action=ProtectionAction.ALLOW,
            trigger="no_protection_needed"
        )

    def _check_burnout(self, state: CognitiveState) -> ProtectionDecision:
        """
        Check burnout level and return appropriate decision.

        This always applies regardless of other settings.
        """
        if state.burnout_level == BurnoutLevel.GREEN:
            return ProtectionDecision(action=ProtectionAction.ALLOW)

        elif state.burnout_level == BurnoutLevel.YELLOW:
            return ProtectionDecision(
                action=ProtectionAction.MENTION,
                message="You've been going a while",
                suggestion="Break soon?",
                trigger="burnout_yellow"
            )

        elif state.burnout_level == BurnoutLevel.ORANGE:
            event = ProtectionEvent("burnout", "moderate")
            return ProtectionDecision(
                action=ProtectionAction.SUGGEST_BREAK,
                message=self.renderer.render_protection(event),
                suggestion="Want to find a stopping point?",
                trigger="burnout_orange"
            )

        else:  # RED
            event = ProtectionEvent("burnout", "firm")
            return ProtectionDecision(
                action=ProtectionAction.REQUIRE_CONFIRM,
                message=self.renderer.render_protection(event),
                suggestion="You've done enough. Really.",
                can_override=self.profile.allow_override,
                trigger="burnout_red"
            )

    def _get_calibrated_firmness(self) -> float:
        """
        Get firmness adjusted by calibration learning.

        Returns base profile firmness + learned adjustment,
        bounded by FIRMNESS_MIN and FIRMNESS_MAX.
        """
        base_firmness = self.profile.protection_firmness
        return self.calibration.get_recommended_firmness(base_firmness)

    def _get_calibrated_threshold(self) -> float:
        """
        Get protection threshold using calibrated firmness.

        Higher firmness = lower threshold = earlier intervention.
        Formula: 0.8 - (calibrated_firmness * 0.4)
        """
        calibrated_firmness = self._get_calibrated_firmness()
        return 0.8 - (calibrated_firmness * 0.4)

    def _check_overuse(
        self,
        signals: List[OveruseSignal],
        state: CognitiveState
    ) -> ProtectionDecision:
        """
        Check overuse signals and apply firmness threshold.
        """
        if not signals:
            return ProtectionDecision(action=ProtectionAction.ALLOW)

        primary = self.overuse_detector.get_primary_signal(signals)
        if not primary:
            return ProtectionDecision(action=ProtectionAction.ALLOW)

        # Apply calibrated firmness threshold
        # Higher firmness = lower threshold = earlier intervention
        threshold = self._get_calibrated_threshold()

        if primary.severity < threshold:
            return ProtectionDecision(action=ProtectionAction.ALLOW)

        # Determine action based on severity
        if primary.severity >= 0.8:
            action = ProtectionAction.REQUIRE_CONFIRM
            severity_str = "firm"
        elif primary.severity >= 0.5:
            action = ProtectionAction.SUGGEST_BREAK
            severity_str = "moderate"
        else:
            action = ProtectionAction.MENTION
            severity_str = "gentle"

        # Map overuse type to protection event
        event_type_map = {
            OveruseType.TIME_EXTENDED: "time_check",
            OveruseType.RAPID_EXCHANGE: "hyperfocus",
            OveruseType.OVERRIDE_PATTERN: "overuse",
            OveruseType.ENERGY_MISMATCH: "overuse",
            OveruseType.HYPERFOCUS: "hyperfocus",
        }
        event_type = event_type_map.get(primary.overuse_type, "time_check")

        event = ProtectionEvent(
            event_type=event_type,
            severity=severity_str,
            context={"time": f"{primary.duration_minutes} minutes"}
        )

        self.overuse_detector.mark_protection_suggested()

        return ProtectionDecision(
            action=action,
            message=primary.message,
            suggestion=self.renderer.render_protection(event),
            can_override=self.profile.allow_override,
            trigger=f"overuse_{primary.overuse_type.value}"
        )

    def _check_protection_signals(self, signals: SignalVector) -> ProtectionDecision:
        """
        Check PRISM protection signals.
        """
        # Hyperfocus detection
        if signals.protection.get("hyperfocus", 0) > 0.5:
            event = ProtectionEvent("hyperfocus", "moderate")
            return ProtectionDecision(
                action=ProtectionAction.MENTION,
                message="You're deep in the zone",
                suggestion=self.renderer.render_protection(event),
                trigger="hyperfocus_detected"
            )

        # Overuse language detection
        if signals.protection.get("overuse", 0) > 0.3:
            event = ProtectionEvent("overuse", "gentle")
            return ProtectionDecision(
                action=ProtectionAction.MENTION,
                message=self.renderer.render_protection(event),
                trigger="overuse_language"
            )

        return ProtectionDecision(action=ProtectionAction.ALLOW)

    def _record_override(self, trigger: str = "unknown") -> Optional[float]:
        """
        Record that user overrode protection.

        Feeds back to calibration engine for learning.

        Args:
            trigger: What protection event was overridden

        Returns:
            New recommended firmness if adjustment made, None otherwise
        """
        self._session_overrides += 1
        self.overuse_detector.record_override()

        # Feed to calibration engine
        current_firmness = self._get_calibrated_firmness()
        new_firmness = self.calibration.record_override(trigger, current_firmness)

        if new_firmness is not None:
            logger.info(
                f"Calibration adjusted: firmness {current_firmness:.2f} → {new_firmness:.2f} "
                f"(user overrides protection frequently)"
            )

        logger.info(f"Session override count: {self._session_overrides}")
        return new_firmness

    def _record_accept(self, trigger: str = "unknown") -> Optional[float]:
        """
        Record that user accepted a protection suggestion.

        Feeds back to calibration engine for learning.

        Args:
            trigger: What protection event was accepted

        Returns:
            New recommended firmness if adjustment made, None otherwise
        """
        current_firmness = self._get_calibrated_firmness()
        new_firmness = self.calibration.record_accept(trigger, current_firmness)

        if new_firmness is not None:
            logger.info(
                f"Calibration adjusted: firmness {current_firmness:.2f} → {new_firmness:.2f} "
                f"(user accepts protection suggestions)"
            )

        return new_firmness

    def handle_user_response(
        self,
        response: str,
        decision: ProtectionDecision
    ) -> ProtectionDecision:
        """
        Handle user's response to a protection decision.

        Args:
            response: User's response text
            decision: The original protection decision

        Returns:
            Updated decision or new decision
        """
        response_lower = response.lower().strip()

        # Accept variations of "yes, break"
        break_phrases = ["break", "yes", "ok", "sure", "fine", "stopping"]
        if any(phrase in response_lower for phrase in break_phrases):
            # User accepted protection suggestion - feed to calibration
            self._record_accept(decision.trigger)
            return ProtectionDecision(
                action=ProtectionAction.ALLOW,
                message="Go for it. Session saved.",
                trigger="break_accepted"
            )

        # Accept variations of "no, continue"
        continue_phrases = ["no", "continue", "keep going", "i'm fine", "override"]
        if any(phrase in response_lower for phrase in continue_phrases):
            # User overrode protection - feed to calibration
            self._record_override(decision.trigger)
            return ProtectionDecision(
                action=ProtectionAction.ALLOW,
                message="Got it, continuing",
                override_logged=True,
                trigger="override_accepted"
            )

        # Unclear response - ask again
        return decision

    def reset_session(self) -> None:
        """Reset session-specific tracking."""
        self._session_overrides = 0
        self.overuse_detector.reset_overrides()
        self.calibration.reset_session()
        self._last_decision = None

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of protection activity this session."""
        return {
            "overrides": self._session_overrides,
            "last_decision": self._last_decision.to_dict() if self._last_decision else None,
            "calibration": self.calibration.get_summary(),
            "calibrated_firmness": self._get_calibrated_firmness(),
        }


def create_protection_engine(profile: ResolvedProfile) -> ProtectionEngine:
    """Factory function to create a ProtectionEngine."""
    return ProtectionEngine(profile)


__all__ = [
    'ProtectionAction',
    'ProtectionDecision',
    'ProtectionEngine',
    'create_protection_engine',
]
