"""
Trail Data Models for OTTO OS Pheromone Architecture
=====================================================

Implements the Pheromone Trail system - enabling emergent learning through
distributed trail signals that allow agents to leave traces and follow paths.

Core Thesis: Trails enable learning without centralized memory.
Good paths get reinforced. Bad paths decay. The system learns by doing.

ThinkingMachines [He2025] Compliance:
- All comparisons use deterministic ordering
- Strength calculations use Kahan summation where applicable
- No unseeded random operations

References:
    [He2025] He, Horace and Thinking Machines Lab, "Defeating Nondeterminism
    in LLM Inference", Sep 2025.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TrailType(Enum):
    """
    Classification of trail signals.

    Each type serves a distinct purpose in the cognitive ecosystem:
    - QUALITY: Code health signals ([He2025] compliance, imports, tests)
    - CONTEXT: Relationship signals (dependencies, used_by)
    - DECISION: Historical choices (why X over Y)
    - PATTERN: Learned successful approaches
    - WORK: Activity signals (currently editing, recently touched)
    """
    QUALITY = "quality"
    CONTEXT = "context"
    DECISION = "decision"
    PATTERN = "pattern"
    WORK = "work"


@dataclass
class Trail:
    """
    A single pheromone trail attached to a file path.

    Trails have strength that decays over time (half-life) and can be
    reinforced through repeated successful use. The UNIQUE constraint
    is on (trail_type, path, signal) - depositing an existing trail
    reinforces rather than duplicates.

    Attributes:
        id: Database primary key (None until persisted)
        trail_type: Classification of this trail's purpose
        path: File path this trail is attached to
        signal: What the trail communicates (e.g., "he2025_compliant")
        strength: Current strength 0.0-1.0, decays over time
        deposited_by: Agent ID that created/last reinforced this trail
        deposited_at: When trail was created/last reinforced
        reinforced_count: Number of times this trail has been reinforced
        metadata: Additional structured data (JSON-serializable)
        half_life_days: Decay rate - strength halves every N days

    Example signals by type:
        QUALITY: "he2025_compliant", "he2025_violation:line45", "imports_clean"
        CONTEXT: "depends_on:prism_detector.py", "used_by:orchestrator.py"
        DECISION: "chose:sorted_max|reason:determinism"
        PATTERN: "when_stuck:check_LIVRPS_order", "transition:cold_start→building"
        WORK: "recently_edited", "currently_editing", "mid_refactor"
    """
    id: Optional[int] = None
    trail_type: TrailType = TrailType.QUALITY
    path: str = ""
    signal: str = ""
    strength: float = 1.0
    deposited_by: str = "unknown"
    deposited_at: datetime = field(default_factory=datetime.now)
    reinforced_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    half_life_days: float = 7.0

    def __post_init__(self):
        """Validate trail fields after initialization."""
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0.0, 1.0], got {self.strength}")
        if self.half_life_days <= 0:
            raise ValueError(f"half_life_days must be positive, got {self.half_life_days}")
        if not self.path:
            raise ValueError("path cannot be empty")
        if not self.signal:
            raise ValueError("signal cannot be empty")

    def current_strength(self, now: Optional[datetime] = None) -> float:
        """
        Calculate current strength after decay.

        Uses exponential decay: strength * 0.5^(days_elapsed / half_life)

        Args:
            now: Current time (defaults to datetime.now())

        Returns:
            Decayed strength value in [0.0, 1.0]
        """
        if now is None:
            now = datetime.now()

        elapsed = now - self.deposited_at
        days_elapsed = elapsed.total_seconds() / 86400.0  # seconds per day

        decay_factor = 0.5 ** (days_elapsed / self.half_life_days)
        return self.strength * decay_factor

    def is_alive(self, threshold: float = 0.1, now: Optional[datetime] = None) -> bool:
        """
        Check if trail strength is above pruning threshold.

        Dead trails (strength < threshold) should be pruned during decay_all().

        Args:
            threshold: Minimum strength to be considered alive (default 0.1)
            now: Current time for decay calculation

        Returns:
            True if trail is still alive
        """
        return self.current_strength(now) >= threshold

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize trail to dictionary for JSON storage.

        Returns:
            Dictionary with all trail fields (trail_type as string)
        """
        return {
            "id": self.id,
            "trail_type": self.trail_type.value,
            "path": self.path,
            "signal": self.signal,
            "strength": self.strength,
            "deposited_by": self.deposited_by,
            "deposited_at": self.deposited_at.isoformat(),
            "reinforced_count": self.reinforced_count,
            "metadata": self.metadata,
            "half_life_days": self.half_life_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trail":
        """
        Deserialize trail from dictionary.

        Args:
            data: Dictionary with trail fields

        Returns:
            Trail instance
        """
        return cls(
            id=data.get("id"),
            trail_type=TrailType(data["trail_type"]),
            path=data["path"],
            signal=data["signal"],
            strength=data.get("strength", 1.0),
            deposited_by=data.get("deposited_by", "unknown"),
            deposited_at=datetime.fromisoformat(data["deposited_at"])
                if isinstance(data.get("deposited_at"), str)
                else data.get("deposited_at", datetime.now()),
            reinforced_count=data.get("reinforced_count", 0),
            metadata=data.get("metadata", {}),
            half_life_days=data.get("half_life_days", 7.0),
        )


@dataclass
class TrailQuery:
    """
    Flexible query parameters for trail searches.

    All fields are optional - only non-None fields are used as filters.
    Results are always returned in deterministic order per [He2025].

    Attributes:
        trail_type: Filter by trail type
        path: Exact path match
        path_prefix: Path starts with this prefix
        signal: Exact signal match
        signal_contains: Signal contains this substring
        deposited_by: Filter by depositing agent
        min_strength: Minimum current strength (after decay)
        max_age_days: Maximum age in days
        limit: Maximum number of results (default 100)
    """
    trail_type: Optional[TrailType] = None
    path: Optional[str] = None
    path_prefix: Optional[str] = None
    signal: Optional[str] = None
    signal_contains: Optional[str] = None
    deposited_by: Optional[str] = None
    min_strength: Optional[float] = None
    max_age_days: Optional[float] = None
    limit: int = 100

    def matches(self, trail: Trail, now: Optional[datetime] = None) -> bool:
        """
        Check if a trail matches this query.

        Used for in-memory filtering. SQLite queries should use SQL WHERE
        clauses for efficiency.

        Args:
            trail: Trail to check
            now: Current time for strength/age calculations

        Returns:
            True if trail matches all specified filters
        """
        if now is None:
            now = datetime.now()

        if self.trail_type is not None and trail.trail_type != self.trail_type:
            return False

        if self.path is not None and trail.path != self.path:
            return False

        if self.path_prefix is not None and not trail.path.startswith(self.path_prefix):
            return False

        if self.signal is not None and trail.signal != self.signal:
            return False

        if self.signal_contains is not None and self.signal_contains not in trail.signal:
            return False

        if self.deposited_by is not None and trail.deposited_by != self.deposited_by:
            return False

        if self.min_strength is not None:
            if trail.current_strength(now) < self.min_strength:
                return False

        if self.max_age_days is not None:
            elapsed = now - trail.deposited_at
            if elapsed.total_seconds() / 86400.0 > self.max_age_days:
                return False

        return True


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TrailType",
    "Trail",
    "TrailQuery",
]
