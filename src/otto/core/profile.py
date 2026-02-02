"""
Profile Manager
===============

User profile management with LIVRPS layering.

Profile Priority Order:
1. Session state (real-time, resets each session) - LOCAL
2. Calibration (learned overrides, cross-session) - REFERENCES
3. Base profile (from intake game) - PAYLOADS
4. System defaults (when no profile exists) - SPECIALIZES

[He2025] Compliance:
- Profile composition uses deterministic LIVRPS order
- All fields use fixed vocabularies
- Serialization uses sorted keys

Reference:
    [He2025] He, Horace and Thinking Machines Lab,
    "Defeating Nondeterminism in LLM Inference", Sep 2025.
    See also: docs/HE2025_DETERMINISM_ADDENDUM.md
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import json

from otto.core.livrps import (
    LIVRPSResolver,
    Layer,
    LayerType,
    CompositionResult,
)


# =============================================================================
# Profile Enums
# =============================================================================

class ProfileSource(Enum):
    """Source of profile data."""
    DEFAULTS = "defaults"       # System defaults
    INTAKE = "intake"           # From intake game
    CALIBRATION = "calibration" # Learned from behavior
    SESSION = "session"         # Current session override


class Chronotype(Enum):
    """User's chronotype preference."""
    EARLY = "early"
    FLEXIBLE = "flexible"
    LATE = "late"


class WorkStyle(Enum):
    """Preferred work style."""
    DEEP = "deep"           # Long focused sessions
    POMODORO = "pomodoro"   # Structured intervals
    FLOW = "flow"           # Follow energy


class StressResponse(Enum):
    """How user responds to stress."""
    PUSH = "push"           # Push through
    PIVOT = "pivot"         # Change approach
    PAUSE = "pause"         # Take a break


class FocusLevel(Enum):
    """Calibrated focus level."""
    SCATTERED = "scattered"
    MODERATE = "moderate"
    LOCKED_IN = "locked_in"


class Urgency(Enum):
    """Current urgency level."""
    RELAXED = "relaxed"
    MODERATE = "moderate"
    DEADLINE = "deadline"


# =============================================================================
# Profile Dataclass
# =============================================================================

@dataclass
class Profile:
    """
    User profile with preferences and calibration.

    Combines:
    - Personality traits (from intake)
    - Work preferences (calibrated)
    - Protection settings (configured)
    - Current state (session-specific)
    """

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    profile_id: str = ""
    profile_version: str = "1.0.0"
    created_at: str = ""
    updated_at: str = ""

    # -------------------------------------------------------------------------
    # Personality (from intake game)
    # -------------------------------------------------------------------------
    chronotype: str = "flexible"
    work_style: str = "flow"
    stress_response: str = "pause"
    perfectionism_tendency: float = 0.5  # 0.0-1.0
    tangent_tendency: float = 0.5        # 0.0-1.0

    # -------------------------------------------------------------------------
    # Work Preferences (calibrated)
    # -------------------------------------------------------------------------
    focus_level: str = "moderate"
    urgency: str = "moderate"
    preferred_depth: str = "standard"    # minimal/standard/deep/ultradeep
    interruption_tolerance: float = 0.5  # 0.0-1.0

    # -------------------------------------------------------------------------
    # Protection Settings
    # -------------------------------------------------------------------------
    intervention_style: str = "gentle"   # gentle/moderate/firm
    body_check_enabled: bool = True
    crash_prediction_enabled: bool = True
    permission_grants_enabled: bool = True

    # -------------------------------------------------------------------------
    # Session State
    # -------------------------------------------------------------------------
    current_energy: str = "medium"       # high/medium/low/depleted
    current_mood: str = "neutral"        # positive/neutral/negative
    session_goal: str = ""
    active_project: str = ""

    # -------------------------------------------------------------------------
    # Calibration Metadata
    # -------------------------------------------------------------------------
    total_sessions: int = 0
    total_exchanges: int = 0
    crash_count: int = 0
    success_count: int = 0
    calibration_confidence: float = 0.0  # 0.0-1.0

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary.

        [He2025] Compliance: Keys sorted for deterministic serialization.
        """
        data = asdict(self)
        return {k: data[k] for k in sorted(data.keys())}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        """Deserialize from dictionary."""
        # Filter to known fields only
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def compute_hash(self) -> str:
        """
        Compute deterministic hash of profile.

        [He2025] Compliance: Uses sorted serialization.
        """
        serialized = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:12]

    def validate(self) -> List[str]:
        """
        Validate profile against schema constraints.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate enums
        valid_chronotypes = {"early", "flexible", "late"}
        if self.chronotype not in valid_chronotypes:
            errors.append(f"Invalid chronotype: {self.chronotype}")

        valid_work_styles = {"deep", "pomodoro", "flow"}
        if self.work_style not in valid_work_styles:
            errors.append(f"Invalid work_style: {self.work_style}")

        valid_stress = {"push", "pivot", "pause"}
        if self.stress_response not in valid_stress:
            errors.append(f"Invalid stress_response: {self.stress_response}")

        valid_focus = {"scattered", "moderate", "locked_in"}
        if self.focus_level not in valid_focus:
            errors.append(f"Invalid focus_level: {self.focus_level}")

        valid_urgency = {"relaxed", "moderate", "deadline"}
        if self.urgency not in valid_urgency:
            errors.append(f"Invalid urgency: {self.urgency}")

        valid_depth = {"minimal", "standard", "deep", "ultradeep"}
        if self.preferred_depth not in valid_depth:
            errors.append(f"Invalid preferred_depth: {self.preferred_depth}")

        valid_style = {"gentle", "moderate", "firm"}
        if self.intervention_style not in valid_style:
            errors.append(f"Invalid intervention_style: {self.intervention_style}")

        valid_energy = {"high", "medium", "low", "depleted"}
        if self.current_energy not in valid_energy:
            errors.append(f"Invalid current_energy: {self.current_energy}")

        # Validate ranges
        for field_name in ["perfectionism_tendency", "tangent_tendency",
                          "interruption_tolerance", "calibration_confidence"]:
            value = getattr(self, field_name)
            if not (0.0 <= value <= 1.0):
                errors.append(f"{field_name} out of range: {value}")

        return errors


# =============================================================================
# Default Profile Values
# =============================================================================

DEFAULT_PROFILE = {
    "profile_version": "1.0.0",
    "chronotype": "flexible",
    "work_style": "flow",
    "stress_response": "pause",
    "perfectionism_tendency": 0.5,
    "tangent_tendency": 0.5,
    "focus_level": "moderate",
    "urgency": "moderate",
    "preferred_depth": "standard",
    "interruption_tolerance": 0.5,
    "intervention_style": "gentle",
    "body_check_enabled": True,
    "crash_prediction_enabled": True,
    "permission_grants_enabled": True,
    "current_energy": "medium",
    "current_mood": "neutral",
    "calibration_confidence": 0.0,
}


# =============================================================================
# Profile Manager
# =============================================================================

class ProfileManager:
    """
    Manages user profile with LIVRPS layering.

    Layer Structure:
    - LOCAL: Session-specific overrides (energy, mood, goal)
    - REFERENCES: Calibration overrides (learned preferences)
    - PAYLOADS: Base profile (from intake game)
    - SPECIALIZES: System defaults

    Example:
        manager = get_profile_manager()

        # Load base profile from intake
        manager.load_intake_profile({"chronotype": "early", ...})

        # Update session state
        manager.update_session("current_energy", "low")

        # Get resolved profile
        profile = manager.get_profile()
        print(profile.chronotype)  # "early" (from intake)
        print(profile.current_energy)  # "low" (from session)

        # Save calibration
        manager.save()
    """

    PROFILE_FILE = "profile/base.json"
    CALIBRATION_FILE = "calibration/profile.json"
    SESSION_FILE = "state/profile_session.json"

    def __init__(self, storage=None):
        """
        Initialize the profile manager.

        Args:
            storage: Optional storage provider (uses default if None)
        """
        self._storage = storage
        self._resolver = LIVRPSResolver(safety_floors=[])  # No safety floors for profile
        self._profile: Optional[Profile] = None
        self._dirty = False

        # Initialize layers
        self._init_layers()

    def _get_storage(self):
        """Lazy-load storage to avoid circular imports."""
        if self._storage is None:
            try:
                from otto.storage import get_storage
                self._storage = get_storage()
            except ImportError:
                self._storage = None
        return self._storage

    def _init_layers(self):
        """Initialize LIVRPS layers with defaults."""
        # S (Specializes) - System defaults
        self._resolver.add_layer(Layer(
            LayerType.SPECIALIZES,
            DEFAULT_PROFILE.copy(),
            name="defaults"
        ))

        # P (Payloads) - Base profile from intake
        intake = self._load_intake_profile()
        self._resolver.add_layer(Layer(
            LayerType.PAYLOADS,
            intake,
            name="intake"
        ))

        # R (References) - Calibration overrides
        calibration = self._load_calibration()
        self._resolver.add_layer(Layer(
            LayerType.REFERENCES,
            calibration,
            name="calibration"
        ))

        # L (Local) - Session state
        session = self._load_session()
        self._resolver.add_layer(Layer(
            LayerType.LOCAL,
            session,
            name="session"
        ))

    def _load_intake_profile(self) -> Dict[str, Any]:
        """Load base profile from intake game."""
        storage = self._get_storage()
        if storage:
            return storage.read_json(self.PROFILE_FILE, root_type="otto", default={})
        return {}

    def _load_calibration(self) -> Dict[str, Any]:
        """Load calibration overrides."""
        storage = self._get_storage()
        if storage:
            return storage.read_json(self.CALIBRATION_FILE, root_type="otto", default={})
        return {}

    def _load_session(self) -> Dict[str, Any]:
        """Load session-specific state."""
        storage = self._get_storage()
        if storage:
            return storage.read_json(self.SESSION_FILE, root_type="otto", default={})
        return {}

    def get_profile(self) -> Profile:
        """
        Get the current resolved profile.

        Returns:
            Profile with all LIVRPS layers resolved
        """
        if self._profile is None or self._dirty:
            result = self._resolver.resolve()
            self._profile = Profile.from_dict(result.resolved)
            self._dirty = False
        return self._profile

    def get_composition_result(self) -> CompositionResult:
        """
        Get the full composition result with provenance.

        Returns:
            CompositionResult showing where each value came from
        """
        return self._resolver.resolve()

    def load_intake_profile(self, profile_data: Dict[str, Any]) -> None:
        """
        Load a new base profile from intake game.

        Args:
            profile_data: Profile data from intake
        """
        # Update timestamp
        profile_data["created_at"] = datetime.utcnow().isoformat()
        profile_data["updated_at"] = profile_data["created_at"]

        # Replace PAYLOADS layer
        self._resolver.clear_layer_type(LayerType.PAYLOADS)
        self._resolver.add_layer(Layer(
            LayerType.PAYLOADS,
            profile_data,
            name="intake"
        ))
        self._dirty = True

    def update_session(self, key: str, value: Any) -> None:
        """
        Update a session-specific value.

        Args:
            key: Attribute to update
            value: New value
        """
        self._resolver.update_local(key, value)
        self._dirty = True

    def update_calibration(self, key: str, value: Any) -> None:
        """
        Update a calibration override.

        Args:
            key: Attribute to update
            value: New value (learned from behavior)
        """
        self._resolver.update_references(key, value)
        self._dirty = True

    def increment_stats(self, crash: bool = False, success: bool = False) -> None:
        """
        Increment calibration statistics.

        Args:
            crash: Whether this session crashed
            success: Whether this session was successful
        """
        profile = self.get_profile()

        self.update_calibration("total_sessions", profile.total_sessions + 1)

        if crash:
            self.update_calibration("crash_count", profile.crash_count + 1)

        if success:
            self.update_calibration("success_count", profile.success_count + 1)

        # Update calibration confidence based on sample size
        total = profile.total_sessions + 1
        confidence = min(1.0, total / 20.0)  # Full confidence after 20 sessions
        self.update_calibration("calibration_confidence", round(confidence, 2))

    def save(self) -> bool:
        """
        Save profile data to storage.

        Saves:
        - Base profile to PROFILE_FILE (if exists)
        - Calibration to CALIBRATION_FILE
        - Session state to SESSION_FILE

        Returns:
            True if successful
        """
        storage = self._get_storage()
        if not storage:
            return False

        # Save base profile (PAYLOADS)
        payload_layers = self._resolver.get_layers(LayerType.PAYLOADS)
        if payload_layers and payload_layers[0].data:
            data = payload_layers[0].data.copy()
            data["updated_at"] = datetime.utcnow().isoformat()
            storage.write_json(self.PROFILE_FILE, data, root_type="otto", backup=True)

        # Save calibration (REFERENCES)
        ref_layers = self._resolver.get_layers(LayerType.REFERENCES)
        if ref_layers and ref_layers[0].data:
            storage.write_json(self.CALIBRATION_FILE, ref_layers[0].data,
                              root_type="otto", backup=True)

        # Save session (LOCAL)
        local_layers = self._resolver.get_layers(LayerType.LOCAL)
        if local_layers and local_layers[0].data:
            storage.write_json(self.SESSION_FILE, local_layers[0].data,
                              root_type="otto", backup=True)

        return True

    def reset_session(self) -> None:
        """
        Reset session-specific state.

        Called when starting a new session.
        """
        self._resolver.clear_layer_type(LayerType.LOCAL)
        self._resolver.add_layer(Layer(
            LayerType.LOCAL,
            {
                "current_energy": "medium",
                "current_mood": "neutral",
                "session_goal": "",
                "active_project": "",
            },
            name="session"
        ))
        self._dirty = True

    def has_intake_profile(self) -> bool:
        """Check if a base profile from intake exists."""
        payload_layers = self._resolver.get_layers(LayerType.PAYLOADS)
        if not payload_layers:
            return False
        return bool(payload_layers[0].data)

    def get_profile_source(self, key: str) -> Optional[ProfileSource]:
        """
        Get the source of a specific profile value.

        Args:
            key: The attribute to check

        Returns:
            ProfileSource indicating where the value came from
        """
        result = self._resolver.resolve()
        source = result.source_of(key)

        if source is None:
            return None
        elif source == LayerType.LOCAL:
            return ProfileSource.SESSION
        elif source == LayerType.REFERENCES:
            return ProfileSource.CALIBRATION
        elif source == LayerType.PAYLOADS:
            return ProfileSource.INTAKE
        else:
            return ProfileSource.DEFAULTS

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize manager state.

        [He2025] Compliance: Deterministic serialization.
        """
        return {
            "resolver": self._resolver.to_dict(),
            "profile": self.get_profile().to_dict(),
            "has_intake": self.has_intake_profile(),
        }


# =============================================================================
# Global Singleton
# =============================================================================

_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """
    Get the global profile manager instance.

    Creates the manager on first call.

    Returns:
        ProfileManager instance
    """
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager


def reset_profile_manager() -> None:
    """
    Reset the global profile manager.

    Used for testing to ensure clean state.
    """
    global _manager
    _manager = None
