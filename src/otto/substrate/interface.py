"""
Cognitive Substrate Interface
=============================

Three-tier cognitive state management with [He2025] determinism compliance.

Tiers:
- CONSTITUTIONAL: Immutable core values (cannot be modified)
- LEARNED: Mutable with approval (user preferences, patterns)
- EPHEMERAL: Session-scoped state (current context)

ThinkingMachines [He2025] Compliance:
- Fixed tier evaluation order (EPHEMERAL > LEARNED > CONSTITUTIONAL)
- Deterministic merge strategy
- Sorted iteration
- Fixed seeds for any randomized operations
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

# ============================================================================
# Constants - [He2025] Compliance
# ============================================================================

COGNITIVE_TILE_SIZE: Final[int] = 32
SUBSTRATE_SEED: Final[int] = 0x50B57A7E
INTERFACE_SEED: Final[int] = 0xCAFEBEEF
CONSTITUTIONAL_HASH_SEED: Final[int] = 0xC0C0A000


class SubstrateTier(IntEnum):
    """Substrate tier levels (order matters for resolution)."""
    CONSTITUTIONAL = 0  # Lowest priority in override, but immutable
    LEARNED = 1         # Can override constitutional, mutable with approval
    EPHEMERAL = 2       # Highest priority, session-scoped


class ModificationResult(str, Enum):
    """Result of a modification attempt."""
    SUCCESS = "success"
    DENIED_CONSTITUTIONAL = "denied_constitutional"
    DENIED_APPROVAL_REQUIRED = "denied_approval_required"
    DENIED_INVALID_VALUE = "denied_invalid_value"
    DENIED_VALIDATION_FAILED = "denied_validation_failed"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SubstrateValue:
    """A value in the cognitive substrate.

    Attributes:
        key: The value's key path (e.g., "safety.burnout_threshold")
        value: The actual value
        tier: Which tier this value belongs to
        modified_at: When this value was last modified
        checksum: SHA-256 hash for integrity verification
        metadata: Optional metadata (e.g., source, reason)
    """
    key: str
    value: Any
    tier: SubstrateTier
    modified_at: datetime = field(default_factory=datetime.now)
    checksum: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Compute checksum after initialization."""
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute SHA-256 checksum of the value."""
        canonical = json.dumps({
            "key": self.key,
            "value": self.value,
            "tier": self.tier.value,
        }, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def verify_integrity(self) -> bool:
        """Verify the value's integrity via checksum."""
        return self.checksum == self._compute_checksum()


@dataclass
class ModificationRequest:
    """Request to modify a substrate value.

    Attributes:
        key: The value's key path
        new_value: The proposed new value
        tier: Target tier for the modification
        reason: Why this modification is requested
        approval_token: Optional approval token if pre-approved
        session_id: Current session ID
    """
    key: str
    new_value: Any
    tier: SubstrateTier
    reason: str = ""
    approval_token: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class ModificationResponse:
    """Response to a modification request.

    Attributes:
        result: The modification result
        previous_value: The value before modification (if any)
        current_value: The value after modification (if successful)
        error_message: Error details if modification failed
        requires_approval: Whether approval is needed
        approval_action: The approval action required (if any)
    """
    result: ModificationResult
    previous_value: Optional[SubstrateValue] = None
    current_value: Optional[SubstrateValue] = None
    error_message: Optional[str] = None
    requires_approval: bool = False
    approval_action: Optional[str] = None


# ============================================================================
# Constitutional Values (Immutable)
# ============================================================================

# These values are FIXED and cannot be modified by any tier
CONSTITUTIONAL_VALUES: Final[Dict[str, Any]] = {
    # Safety floors - can NEVER be lowered
    "safety.burnout_red_action": "full_stop",
    "safety.validator_minimum_priority": 1,
    "safety.constitutional_approval_required": True,

    # Core principles
    "principles.safety_first": True,
    "principles.ship_over_perfect": True,
    "principles.protect_momentum": True,
    "principles.external_over_internal": True,
    "principles.recover_without_guilt": True,
    "principles.one_at_a_time": True,
    "principles.user_knows_best": True,

    # Processing order - FIXED per [He2025]
    "processing.phase_order": [
        "RETRIEVE", "CLASSIFY", "GROUND",
        "DETECT", "CASCADE", "LOCK",
        "EXECUTE", "UPDATE", "FLUSH"
    ],
    "processing.signal_priority": [
        "emotional", "grounding", "mode", "domain", "task"
    ],
    "processing.expert_priority": [
        "Validator", "Scaffolder", "Restorer",
        "Refocuser", "Celebrator", "Socratic", "Direct"
    ],

    # Determinism constants
    "determinism.cognitive_tile_size": COGNITIVE_TILE_SIZE,
    "determinism.hash_algorithm": "sha256",
    "determinism.seed": INTERFACE_SEED,
}


# ============================================================================
# Validators
# ============================================================================

T = TypeVar('T')


class ValueValidator(ABC):
    """Abstract base for value validators."""

    @abstractmethod
    def validate(self, key: str, value: Any) -> bool:
        """Validate a value.

        Args:
            key: The value's key path
            value: The value to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def get_error_message(self, key: str, value: Any) -> str:
        """Get error message for invalid value."""
        pass


class TypeValidator(ValueValidator):
    """Validates value types."""

    def __init__(self, type_map: Dict[str, type]):
        """Initialize with key -> type mapping."""
        self.type_map = type_map

    def validate(self, key: str, value: Any) -> bool:
        if key not in self.type_map:
            return True  # No constraint
        expected_type = self.type_map[key]
        return isinstance(value, expected_type)

    def get_error_message(self, key: str, value: Any) -> str:
        expected = self.type_map.get(key, "unknown")
        return f"Expected type {expected} for {key}, got {type(value).__name__}"


class RangeValidator(ValueValidator):
    """Validates numeric ranges."""

    def __init__(self, range_map: Dict[str, tuple]):
        """Initialize with key -> (min, max) mapping."""
        self.range_map = range_map

    def validate(self, key: str, value: Any) -> bool:
        if key not in self.range_map:
            return True
        min_val, max_val = self.range_map[key]
        if not isinstance(value, (int, float)):
            return False
        return min_val <= value <= max_val

    def get_error_message(self, key: str, value: Any) -> str:
        min_val, max_val = self.range_map.get(key, (None, None))
        return f"Value {value} for {key} must be in range [{min_val}, {max_val}]"


class EnumValidator(ValueValidator):
    """Validates enum values."""

    def __init__(self, enum_map: Dict[str, Set[str]]):
        """Initialize with key -> allowed values mapping."""
        self.enum_map = enum_map

    def validate(self, key: str, value: Any) -> bool:
        if key not in self.enum_map:
            return True
        return value in self.enum_map[key]

    def get_error_message(self, key: str, value: Any) -> str:
        allowed = self.enum_map.get(key, set())
        return f"Value {value} for {key} must be one of {sorted(allowed)}"


# ============================================================================
# Cognitive Substrate Interface
# ============================================================================

class CognitiveSubstrate:
    """Three-tier cognitive substrate with [He2025] determinism compliance.

    Manages state across three tiers:
    - CONSTITUTIONAL: Immutable core values
    - LEARNED: Mutable with approval (persisted)
    - EPHEMERAL: Session-scoped (not persisted)

    Resolution order (LIVRPS-inspired):
    EPHEMERAL > LEARNED > CONSTITUTIONAL

    Higher tiers can override lower tiers, except CONSTITUTIONAL
    values which are immutable.

    Example:
        >>> substrate = CognitiveSubstrate()
        >>> substrate.get("safety.burnout_red_action")
        'full_stop'
        >>> substrate.set_ephemeral("mode.current", "focused")
        ModificationResponse(result=SUCCESS, ...)
    """

    def __init__(
        self,
        state_dir: Optional[Path] = None,
        validators: Optional[List[ValueValidator]] = None,
        approval_callback: Optional[Callable[[str, Any], bool]] = None,
    ):
        """Initialize cognitive substrate.

        Args:
            state_dir: Directory for persisting LEARNED tier
            validators: List of value validators
            approval_callback: Callback to check approval for LEARNED modifications
        """
        self.state_dir = state_dir or Path.home() / ".otto" / "substrate"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.validators = validators or [
            TypeValidator({
                "safety.burnout_threshold": float,
                "processing.max_agents": int,
            }),
            RangeValidator({
                "safety.burnout_threshold": (0.0, 1.0),
                "processing.max_agents": (1, 10),
            }),
            EnumValidator({
                "mode.current": {"focused", "exploring", "teaching", "recovery"},
                "burnout.level": {"GREEN", "YELLOW", "ORANGE", "RED"},
            }),
        ]

        self.approval_callback = approval_callback

        # Initialize tiers
        self._constitutional: Dict[str, SubstrateValue] = {}
        self._learned: Dict[str, SubstrateValue] = {}
        self._ephemeral: Dict[str, SubstrateValue] = {}

        # Load constitutional values (immutable)
        self._load_constitutional()

        # Load learned values from disk
        self._load_learned()

        logger.info("CognitiveSubstrate initialized with %d constitutional values",
                   len(self._constitutional))

    # =========================================================================
    # Initialization
    # =========================================================================

    def _load_constitutional(self) -> None:
        """Load constitutional values (immutable after this)."""
        for key, value in sorted(CONSTITUTIONAL_VALUES.items()):
            self._constitutional[key] = SubstrateValue(
                key=key,
                value=value,
                tier=SubstrateTier.CONSTITUTIONAL,
                metadata={"source": "hardcoded", "immutable": True},
            )

    def _load_learned(self) -> None:
        """Load learned values from persistent storage."""
        learned_path = self.state_dir / "learned_state.json"

        if not learned_path.exists():
            logger.debug("No learned state file found")
            return

        try:
            content = learned_path.read_text(encoding='utf-8')
            data = json.loads(content)

            for key, entry in sorted(data.items()):
                self._learned[key] = SubstrateValue(
                    key=key,
                    value=entry["value"],
                    tier=SubstrateTier.LEARNED,
                    modified_at=datetime.fromisoformat(entry.get("modified_at", datetime.now().isoformat())),
                    checksum=entry.get("checksum", ""),
                    metadata=entry.get("metadata", {}),
                )

            logger.info("Loaded %d learned values", len(self._learned))

        except Exception as e:
            logger.warning("Failed to load learned state: %s", e)

    def _save_learned(self) -> None:
        """Persist learned values to storage."""
        learned_path = self.state_dir / "learned_state.json"

        data = {}
        for key in sorted(self._learned.keys()):
            sv = self._learned[key]
            data[key] = {
                "value": sv.value,
                "modified_at": sv.modified_at.isoformat(),
                "checksum": sv.checksum,
                "metadata": sv.metadata,
            }

        try:
            content = json.dumps(data, indent=2, sort_keys=True, default=str)
            learned_path.write_text(content, encoding='utf-8')
            logger.debug("Saved %d learned values", len(data))
        except Exception as e:
            logger.error("Failed to save learned state: %s", e)

    # =========================================================================
    # Read Operations
    # =========================================================================

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the substrate.

        Resolution order: EPHEMERAL > LEARNED > CONSTITUTIONAL

        Args:
            key: The value's key path
            default: Default if key not found in any tier

        Returns:
            The resolved value
        """
        # Check tiers in priority order (EPHEMERAL first)
        if key in self._ephemeral:
            return self._ephemeral[key].value
        if key in self._learned:
            return self._learned[key].value
        if key in self._constitutional:
            return self._constitutional[key].value
        return default

    def get_with_tier(self, key: str) -> Optional[SubstrateValue]:
        """Get a value with its tier information.

        Args:
            key: The value's key path

        Returns:
            SubstrateValue if found, None otherwise
        """
        if key in self._ephemeral:
            return self._ephemeral[key]
        if key in self._learned:
            return self._learned[key]
        if key in self._constitutional:
            return self._constitutional[key]
        return None

    def get_tier(self, tier: SubstrateTier) -> Dict[str, Any]:
        """Get all values from a specific tier.

        Args:
            tier: The tier to retrieve

        Returns:
            Dictionary of key -> value for that tier
        """
        tier_map = {
            SubstrateTier.CONSTITUTIONAL: self._constitutional,
            SubstrateTier.LEARNED: self._learned,
            SubstrateTier.EPHEMERAL: self._ephemeral,
        }

        storage = tier_map.get(tier, {})
        return {k: v.value for k, v in sorted(storage.items())}

    def keys(self, tier: Optional[SubstrateTier] = None) -> List[str]:
        """Get all keys, optionally filtered by tier.

        Args:
            tier: Optional tier filter

        Returns:
            Sorted list of keys
        """
        if tier is not None:
            tier_map = {
                SubstrateTier.CONSTITUTIONAL: self._constitutional,
                SubstrateTier.LEARNED: self._learned,
                SubstrateTier.EPHEMERAL: self._ephemeral,
            }
            return sorted(tier_map.get(tier, {}).keys())

        # All keys across tiers (deduplicated)
        all_keys = set(self._constitutional.keys())
        all_keys.update(self._learned.keys())
        all_keys.update(self._ephemeral.keys())
        return sorted(all_keys)

    # =========================================================================
    # Write Operations
    # =========================================================================

    def _validate(self, key: str, value: Any) -> tuple[bool, str]:
        """Validate a value against all validators.

        Args:
            key: The value's key path
            value: The value to validate

        Returns:
            (is_valid, error_message)
        """
        for validator in self.validators:
            if not validator.validate(key, value):
                return False, validator.get_error_message(key, value)
        return True, ""

    def set_ephemeral(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModificationResponse:
        """Set an ephemeral (session-scoped) value.

        Ephemeral values are not persisted and are lost when the session ends.
        They can override LEARNED and CONSTITUTIONAL values within the session.

        Cannot override CONSTITUTIONAL values that are marked as immutable floors.

        Args:
            key: The value's key path
            value: The new value
            metadata: Optional metadata

        Returns:
            ModificationResponse
        """
        # Check if this is a constitutional floor
        if key in self._constitutional:
            const_val = self._constitutional[key]
            if const_val.metadata.get("immutable"):
                return ModificationResponse(
                    result=ModificationResult.DENIED_CONSTITUTIONAL,
                    error_message=f"Cannot override immutable constitutional value: {key}",
                )

        # Validate
        is_valid, error = self._validate(key, value)
        if not is_valid:
            return ModificationResponse(
                result=ModificationResult.DENIED_VALIDATION_FAILED,
                error_message=error,
            )

        previous = self._ephemeral.get(key)

        self._ephemeral[key] = SubstrateValue(
            key=key,
            value=value,
            tier=SubstrateTier.EPHEMERAL,
            metadata=metadata or {},
        )

        return ModificationResponse(
            result=ModificationResult.SUCCESS,
            previous_value=previous,
            current_value=self._ephemeral[key],
        )

    def set_learned(
        self,
        key: str,
        value: Any,
        reason: str = "",
        approval_token: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModificationResponse:
        """Set a learned (persistent) value.

        Learned values require approval and are persisted across sessions.
        They can override CONSTITUTIONAL values except immutable floors.

        Args:
            key: The value's key path
            value: The new value
            reason: Reason for the modification
            approval_token: Pre-approved token (if any)
            metadata: Optional metadata

        Returns:
            ModificationResponse
        """
        # Check constitutional immutability
        if key in self._constitutional:
            const_val = self._constitutional[key]
            if const_val.metadata.get("immutable"):
                return ModificationResponse(
                    result=ModificationResult.DENIED_CONSTITUTIONAL,
                    error_message=f"Cannot modify immutable constitutional value: {key}",
                )

        # Validate
        is_valid, error = self._validate(key, value)
        if not is_valid:
            return ModificationResponse(
                result=ModificationResult.DENIED_VALIDATION_FAILED,
                error_message=error,
            )

        # Check approval
        if self.approval_callback:
            if not approval_token:
                # Need approval
                return ModificationResponse(
                    result=ModificationResult.DENIED_APPROVAL_REQUIRED,
                    error_message=f"Approval required to modify learned value: {key}",
                    requires_approval=True,
                    approval_action=f"substrate.learned.modify.{key}",
                )

            # Verify approval token
            if not self.approval_callback(f"substrate.learned.modify.{key}", approval_token):
                return ModificationResponse(
                    result=ModificationResult.DENIED_APPROVAL_REQUIRED,
                    error_message="Invalid or expired approval token",
                    requires_approval=True,
                    approval_action=f"substrate.learned.modify.{key}",
                )

        previous = self._learned.get(key)

        meta = metadata or {}
        meta["reason"] = reason
        meta["modified_at"] = datetime.now().isoformat()

        self._learned[key] = SubstrateValue(
            key=key,
            value=value,
            tier=SubstrateTier.LEARNED,
            metadata=meta,
        )

        # Persist
        self._save_learned()

        return ModificationResponse(
            result=ModificationResult.SUCCESS,
            previous_value=previous,
            current_value=self._learned[key],
        )

    def clear_ephemeral(self, key: Optional[str] = None) -> None:
        """Clear ephemeral values.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            self._ephemeral.pop(key, None)
        else:
            self._ephemeral.clear()
            logger.debug("Cleared all ephemeral values")

    # =========================================================================
    # Integrity Operations
    # =========================================================================

    def compute_state_hash(self) -> str:
        """Compute a hash of the entire substrate state.

        Returns:
            SHA-256 hash of the canonical state representation
        """
        state = {
            "constitutional": {k: v.value for k, v in sorted(self._constitutional.items())},
            "learned": {k: v.value for k, v in sorted(self._learned.items())},
            "ephemeral": {k: v.value for k, v in sorted(self._ephemeral.items())},
        }
        canonical = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify_constitutional_integrity(self) -> List[str]:
        """Verify integrity of constitutional values.

        Returns:
            List of corrupted keys (empty if all valid)
        """
        corrupted = []
        for key, sv in sorted(self._constitutional.items()):
            if not sv.verify_integrity():
                corrupted.append(key)
        return corrupted

    # =========================================================================
    # Snapshot Operations
    # =========================================================================

    def snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of the current state.

        Returns:
            Dictionary representation of all tiers
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "state_hash": self.compute_state_hash(),
            "tiers": {
                "constitutional": {k: v.value for k, v in sorted(self._constitutional.items())},
                "learned": {k: v.value for k, v in sorted(self._learned.items())},
                "ephemeral": {k: v.value for k, v in sorted(self._ephemeral.items())},
            },
        }

    def restore_learned(self, snapshot: Dict[str, Any]) -> int:
        """Restore learned values from a snapshot.

        Args:
            snapshot: Snapshot dictionary

        Returns:
            Number of values restored
        """
        learned_data = snapshot.get("tiers", {}).get("learned", {})
        count = 0

        for key, value in sorted(learned_data.items()):
            self._learned[key] = SubstrateValue(
                key=key,
                value=value,
                tier=SubstrateTier.LEARNED,
                metadata={"restored_from_snapshot": True},
            )
            count += 1

        self._save_learned()
        logger.info("Restored %d learned values from snapshot", count)
        return count


# ============================================================================
# Module-level singleton
# ============================================================================

_substrate: Optional[CognitiveSubstrate] = None


def get_substrate() -> CognitiveSubstrate:
    """Get or create the singleton cognitive substrate."""
    global _substrate
    if _substrate is None:
        _substrate = CognitiveSubstrate()
    return _substrate


__all__ = [
    # Enums
    "SubstrateTier",
    "ModificationResult",
    # Data classes
    "SubstrateValue",
    "ModificationRequest",
    "ModificationResponse",
    # Validators
    "ValueValidator",
    "TypeValidator",
    "RangeValidator",
    "EnumValidator",
    # Main class
    "CognitiveSubstrate",
    # Constants
    "CONSTITUTIONAL_VALUES",
    "COGNITIVE_TILE_SIZE",
    # Singleton
    "get_substrate",
]
