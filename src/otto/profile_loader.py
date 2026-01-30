"""
Profile Loader
==============

Loads personality profiles with LIVRPS (USD composition) resolution.

Priority Order (highest to lowest):
1. Session state (real-time, resets each session)
2. Calibration (learned overrides)
3. Base profile (from intake game)
4. System defaults (when no profile exists)

This ensures user preferences are respected while allowing
runtime adjustments and learned patterns.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
import json
import logging

from .intake.profile_writer import read_profile

logger = logging.getLogger(__name__)


# =============================================================================
# Default Profile Values
# =============================================================================

DEFAULT_PROFILE = {
    # Chronotype
    "chronotype": "variable",
    "peak_hours": [10, 11, 12, 14, 15, 16],
    "recovery_hours": [7, 8, 21, 22, 23],

    # Work Style
    "work_style": "deep_diver",
    "focus_duration_minutes": 45,
    "context_switch_cost": 0.7,
    "interruption_recovery_minutes": 15,
    "notification_sensitivity": 0.6,

    # Stress Response
    "stress_response": "withdraw",
    "overwhelm_threshold": 0.6,

    # Protection Preferences
    "protection_firmness": 0.5,  # 0.0 = gentle, 1.0 = firm
    "allow_override": True,
    "override_cooldown_minutes": 30,
    "otto_role": "companion",  # guardian | companion | tool
    "intervention_style": "gentle",  # gentle | moderate | firm

    # Recovery Style
    "preferred_recovery": "solitude",
    "recovery_social_need": 0.3,

    # Energy Patterns
    "decision_fatigue_sensitivity": 0.6,
    "max_daily_decisions": 50,
}


# =============================================================================
# Resolved Profile
# =============================================================================

@dataclass
class ResolvedProfile:
    """
    A fully-resolved personality profile.

    Created by applying LIVRPS resolution across all layers:
    Session > Calibration > Base > Defaults
    """

    # Chronotype
    chronotype: str = "variable"
    peak_hours: list = field(default_factory=lambda: [10, 11, 12, 14, 15, 16])
    recovery_hours: list = field(default_factory=lambda: [7, 8, 21, 22, 23])

    # Work Style
    work_style: str = "deep_diver"
    focus_duration_minutes: int = 45
    context_switch_cost: float = 0.7
    interruption_recovery_minutes: int = 15
    notification_sensitivity: float = 0.6

    # Stress Response
    stress_response: str = "withdraw"
    overwhelm_threshold: float = 0.6

    # Protection Preferences
    protection_firmness: float = 0.5
    allow_override: bool = True
    override_cooldown_minutes: int = 30
    otto_role: str = "companion"
    intervention_style: str = "gentle"

    # Recovery Style
    preferred_recovery: str = "solitude"
    recovery_social_need: float = 0.3

    # Energy Patterns
    decision_fatigue_sensitivity: float = 0.6
    max_daily_decisions: int = 50

    # Session State (from Session layer)
    current_energy: str = "unknown"
    current_mood: str = "unknown"
    exchanges_this_session: int = 0
    user_requested_no_protection: bool = False

    # Metadata
    profile_source: str = "defaults"  # defaults | intake | calibrated

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "chronotype": self.chronotype,
            "peak_hours": self.peak_hours,
            "recovery_hours": self.recovery_hours,
            "work_style": self.work_style,
            "focus_duration_minutes": self.focus_duration_minutes,
            "context_switch_cost": self.context_switch_cost,
            "interruption_recovery_minutes": self.interruption_recovery_minutes,
            "notification_sensitivity": self.notification_sensitivity,
            "stress_response": self.stress_response,
            "overwhelm_threshold": self.overwhelm_threshold,
            "protection_firmness": self.protection_firmness,
            "allow_override": self.allow_override,
            "override_cooldown_minutes": self.override_cooldown_minutes,
            "otto_role": self.otto_role,
            "intervention_style": self.intervention_style,
            "preferred_recovery": self.preferred_recovery,
            "recovery_social_need": self.recovery_social_need,
            "decision_fatigue_sensitivity": self.decision_fatigue_sensitivity,
            "max_daily_decisions": self.max_daily_decisions,
            "current_energy": self.current_energy,
            "current_mood": self.current_mood,
            "exchanges_this_session": self.exchanges_this_session,
            "user_requested_no_protection": self.user_requested_no_protection,
            "profile_source": self.profile_source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResolvedProfile':
        """Create from dictionary."""
        return cls(
            chronotype=data.get("chronotype", "variable"),
            peak_hours=data.get("peak_hours", [10, 11, 12, 14, 15, 16]),
            recovery_hours=data.get("recovery_hours", [7, 8, 21, 22, 23]),
            work_style=data.get("work_style", "deep_diver"),
            focus_duration_minutes=data.get("focus_duration_minutes", 45),
            context_switch_cost=data.get("context_switch_cost", 0.7),
            interruption_recovery_minutes=data.get("interruption_recovery_minutes", 15),
            notification_sensitivity=data.get("notification_sensitivity", 0.6),
            stress_response=data.get("stress_response", "withdraw"),
            overwhelm_threshold=data.get("overwhelm_threshold", 0.6),
            protection_firmness=data.get("protection_firmness", 0.5),
            allow_override=data.get("allow_override", True),
            override_cooldown_minutes=data.get("override_cooldown_minutes", 30),
            otto_role=data.get("otto_role", "companion"),
            intervention_style=data.get("intervention_style", "gentle"),
            preferred_recovery=data.get("preferred_recovery", "solitude"),
            recovery_social_need=data.get("recovery_social_need", 0.3),
            decision_fatigue_sensitivity=data.get("decision_fatigue_sensitivity", 0.6),
            max_daily_decisions=data.get("max_daily_decisions", 50),
            current_energy=data.get("current_energy", "unknown"),
            current_mood=data.get("current_mood", "unknown"),
            exchanges_this_session=data.get("exchanges_this_session", 0),
            user_requested_no_protection=data.get("user_requested_no_protection", False),
            profile_source=data.get("profile_source", "defaults"),
        )

    def is_in_peak_hours(self, hour: int) -> bool:
        """Check if current hour is in peak focus hours."""
        return hour in self.peak_hours

    def is_in_recovery_hours(self, hour: int) -> bool:
        """Check if current hour is in recovery hours."""
        return hour in self.recovery_hours

    def get_protection_threshold(self) -> float:
        """
        Get the burnout threshold for triggering protection.

        Higher firmness = lower threshold = earlier intervention.
        """
        # Firmness 0.0 → threshold 0.8 (only intervene when very high)
        # Firmness 1.0 → threshold 0.4 (intervene early)
        return 0.8 - (self.protection_firmness * 0.4)


# =============================================================================
# Profile Loader
# =============================================================================

class ProfileLoader:
    """
    Loads personality profiles with LIVRPS resolution.

    Files:
        ~/.otto/profile.usda  - Base profile from intake
        ~/.otto/calibration.usda - Learned overrides
        ~/.otto/state/session.json - Current session state
    """

    DEFAULT_OTTO_DIR = Path.home() / ".otto"
    DEFAULT_PROFILE_FILE = "profile.usda"
    DEFAULT_CALIBRATION_FILE = "calibration.usda"
    DEFAULT_SESSION_FILE = "state/session.json"

    def __init__(self, otto_dir: Path = None):
        """
        Initialize profile loader.

        Args:
            otto_dir: Directory for OTTO files (default: ~/.otto)
        """
        self.otto_dir = otto_dir or self.DEFAULT_OTTO_DIR
        self.profile_path = self.otto_dir / self.DEFAULT_PROFILE_FILE
        self.calibration_path = self.otto_dir / self.DEFAULT_CALIBRATION_FILE
        self.session_path = self.otto_dir / self.DEFAULT_SESSION_FILE

        self._cached_profile: Optional[ResolvedProfile] = None

    def load(self, force_reload: bool = False) -> ResolvedProfile:
        """
        Load profile with LIVRPS resolution.

        Priority (highest to lowest):
        1. Session state (if exists)
        2. Calibration (if exists)
        3. Base profile (from intake)
        4. System defaults

        Args:
            force_reload: Force reload from disk even if cached

        Returns:
            Fully resolved profile
        """
        if self._cached_profile and not force_reload:
            return self._cached_profile

        # Start with defaults
        resolved = dict(DEFAULT_PROFILE)
        profile_source = "defaults"

        # Layer 1: Base profile (from intake)
        base = self._load_usda(self.profile_path)
        if base:
            resolved.update(base)
            profile_source = "intake"
            logger.debug(f"Loaded base profile from {self.profile_path}")

        # Layer 2: Calibration (learned overrides)
        calibration = self._load_usda(self.calibration_path)
        if calibration:
            resolved.update(calibration)
            profile_source = "calibrated"
            logger.debug(f"Applied calibration from {self.calibration_path}")

        # Layer 3: Session state (highest priority)
        session = self._load_session()
        if session:
            # Only apply session-specific fields
            for key in ["current_energy", "current_mood", "exchanges_this_session",
                       "user_requested_no_protection"]:
                if key in session:
                    resolved[key] = session[key]
            logger.debug(f"Applied session state from {self.session_path}")

        resolved["profile_source"] = profile_source

        # Create resolved profile
        self._cached_profile = ResolvedProfile.from_dict(resolved)

        logger.info(f"Profile loaded: source={profile_source}, "
                   f"firmness={self._cached_profile.protection_firmness}, "
                   f"role={self._cached_profile.otto_role}")

        return self._cached_profile

    def _load_usda(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load traits from a USD file."""
        if not path.exists():
            return None

        try:
            return read_profile(path)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
            return None

    def _load_session(self) -> Optional[Dict[str, Any]]:
        """Load session state from JSON."""
        if not self.session_path.exists():
            return None

        try:
            with open(self.session_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load session: {e}")
            return None

    def save_session(self, profile: ResolvedProfile) -> None:
        """
        Save session state for continuity.

        This is called when exiting to preserve state for next session.
        """
        session_data = {
            "current_energy": profile.current_energy,
            "current_mood": profile.current_mood,
            "exchanges_this_session": profile.exchanges_this_session,
            "user_requested_no_protection": profile.user_requested_no_protection,
        }

        # Ensure directory exists
        self.session_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.session_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
            logger.info("Session state saved")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def profile_exists(self) -> bool:
        """Check if a profile has been created (intake completed)."""
        return self.profile_path.exists()

    def clear_cache(self) -> None:
        """Clear cached profile, forcing reload on next access."""
        self._cached_profile = None

    def get_profile_summary(self) -> str:
        """Get a human-readable summary of the profile."""
        profile = self.load()

        role_desc = {
            "guardian": "protective guide",
            "companion": "supportive partner",
            "tool": "minimal presence"
        }

        firmness_desc = (
            "gentle" if profile.protection_firmness < 0.4 else
            "moderate" if profile.protection_firmness < 0.7 else
            "firm"
        )

        return (
            f"Profile: {profile.chronotype} {profile.work_style}\n"
            f"Role: {role_desc.get(profile.otto_role, profile.otto_role)}\n"
            f"Protection: {firmness_desc} ({profile.protection_firmness:.1f})\n"
            f"Focus duration: {profile.focus_duration_minutes} min\n"
            f"Source: {profile.profile_source}"
        )


# =============================================================================
# Factory Functions
# =============================================================================

def get_profile_loader(otto_dir: Path = None) -> ProfileLoader:
    """Get a ProfileLoader instance."""
    return ProfileLoader(otto_dir)


def load_profile(otto_dir: Path = None) -> ResolvedProfile:
    """
    Convenience function to load a profile.

    Args:
        otto_dir: Optional OTTO directory path

    Returns:
        Resolved profile
    """
    loader = ProfileLoader(otto_dir)
    return loader.load()


__all__ = [
    'ResolvedProfile',
    'ProfileLoader',
    'DEFAULT_PROFILE',
    'get_profile_loader',
    'load_profile',
]
