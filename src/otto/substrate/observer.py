"""
Cognitive Substrate Observer
============================

Monitors belief changes, detects drift, and ensures consistency.

Features:
- Belief change tracking with history
- Drift detection (gradual value shifts)
- Consistency violation detection
- RC^+xi convergence tracking
- Pattern recognition for anomalies

Determinism:
- Fixed evaluation windows
- Deterministic drift calculation
- Sorted iteration for reproducibility
"""

import hashlib
import json
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Final, List, Optional, Set

from .interface import CognitiveSubstrate, SubstrateTier, SubstrateValue

logger = logging.getLogger(__name__)

# ============================================================================
# Constants - Determinism
# ============================================================================

OBSERVER_SEED: Final[int] = 0x0B5E7AE7
MAX_HISTORY_SIZE: Final[int] = 1000
DRIFT_WINDOW_SIZE: Final[int] = 10
CONVERGENCE_EPSILON: Final[float] = 0.1
STABLE_EXCHANGES_THRESHOLD: Final[int] = 3


class ChangeType(str, Enum):
    """Types of substrate changes."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    OVERRIDE = "override"  # Higher tier overriding lower


class DriftSeverity(str, Enum):
    """Severity levels for drift detection."""
    NONE = "none"
    LOW = "low"       # Within normal variation
    MEDIUM = "medium"  # Noticeable but acceptable
    HIGH = "high"     # Requires attention
    CRITICAL = "critical"  # Potential system instability


class ConsistencyStatus(str, Enum):
    """Status of consistency checks."""
    CONSISTENT = "consistent"
    WARNING = "warning"      # Minor inconsistencies
    VIOLATION = "violation"  # Clear inconsistency
    CORRUPTED = "corrupted"  # Integrity failure


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class BeliefChange:
    """Record of a single belief change.

    Attributes:
        timestamp: When the change occurred
        key: The substrate key that changed
        tier: Which tier was affected
        change_type: Type of change
        old_value: Previous value (if any)
        new_value: New value (if any)
        source: What triggered the change
        session_id: Session during which change occurred
    """
    timestamp: datetime
    key: str
    tier: SubstrateTier
    change_type: ChangeType
    old_value: Any = None
    new_value: Any = None
    source: str = "unknown"
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "key": self.key,
            "tier": self.tier.name,
            "change_type": self.change_type.value,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "source": self.source,
            "session_id": self.session_id,
        }


@dataclass
class DriftReport:
    """Report on belief drift detection.

    Attributes:
        key: The substrate key being analyzed
        severity: How severe the drift is
        trend: Direction of drift (positive, negative, oscillating)
        magnitude: Numerical drift magnitude (if applicable)
        window_changes: Number of changes in the observation window
        recommendation: Suggested action
    """
    key: str
    severity: DriftSeverity
    trend: str = "stable"
    magnitude: float = 0.0
    window_changes: int = 0
    recommendation: str = ""


@dataclass
class ConsistencyReport:
    """Report on substrate consistency.

    Attributes:
        status: Overall consistency status
        violations: List of detected violations
        warnings: List of warnings
        checked_keys: Number of keys checked
        healthy_keys: Number of keys passing all checks
        timestamp: When the check was performed
    """
    status: ConsistencyStatus
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_keys: int = 0
    healthy_keys: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ConvergenceState:
    """RC^+xi convergence tracking state.

    Attributes:
        attractor: Current attractor basin (focused, exploring, recovery, teaching)
        xi_value: Current epistemic tension value
        stability: stable | converging | oscillating
        exchanges_at_current: Number of exchanges in current attractor
        last_switch: When attractor last changed
    """
    attractor: str = "focused"
    xi_value: float = 0.0
    stability: str = "stable"
    exchanges_at_current: int = 0
    last_switch: Optional[datetime] = None

    def is_converged(self) -> bool:
        """Check if system has converged."""
        return (
            self.xi_value < CONVERGENCE_EPSILON and
            self.exchanges_at_current >= STABLE_EXCHANGES_THRESHOLD
        )


# ============================================================================
# Observer Class
# ============================================================================

class SubstrateObserver:
    """Observer for cognitive substrate changes.

    Monitors the substrate for:
    - All belief changes (with history)
    - Drift patterns (gradual shifts)
    - Consistency violations
    - Convergence state (RC^+xi)

    Example:
        >>> observer = SubstrateObserver(substrate)
        >>> observer.record_change(BeliefChange(...))
        >>> report = observer.check_drift("mode.current")
        >>> print(report.severity)
    """

    def __init__(
        self,
        substrate: CognitiveSubstrate,
        history_path: Optional[Path] = None,
        consistency_rules: Optional[List[Callable[[CognitiveSubstrate], Optional[str]]]] = None,
    ):
        """Initialize substrate observer.

        Args:
            substrate: The cognitive substrate to observe
            history_path: Path to persist change history
            consistency_rules: Custom consistency check rules
        """
        self.substrate = substrate
        self.history_path = history_path or Path.home() / ".otto" / "substrate" / "observer_history.json"
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        # Change history (bounded deque)
        self._history: Deque[BeliefChange] = deque(maxlen=MAX_HISTORY_SIZE)

        # Per-key change tracking for drift detection
        self._key_changes: Dict[str, Deque[BeliefChange]] = {}

        # Convergence state
        self._convergence = ConvergenceState()

        # Consistency rules
        self._consistency_rules = consistency_rules or self._default_consistency_rules()

        # Callbacks for change notifications
        self._change_callbacks: List[Callable[[BeliefChange], None]] = []

        # Memory interface (lazy-loaded)
        self._memory = None

        # Load persisted history
        self._load_history()

        logger.info("SubstrateObserver initialized with %d history entries", len(self._history))

    def _get_memory(self):
        """Get unified memory interface (lazy load)."""
        if self._memory is None:
            try:
                from ..memory import get_memory
                self._memory = get_memory()
            except ImportError:
                logger.debug("Memory interface not available")
        return self._memory

    # =========================================================================
    # Change Recording
    # =========================================================================

    def record_change(self, change: BeliefChange) -> None:
        """Record a belief change.

        Deterministic recording order.

        Args:
            change: The change to record
        """
        # Add to global history
        self._history.append(change)

        # Add to per-key tracking
        if change.key not in self._key_changes:
            self._key_changes[change.key] = deque(maxlen=DRIFT_WINDOW_SIZE * 2)
        self._key_changes[change.key].append(change)

        # Notify callbacks
        for callback in self._change_callbacks:
            try:
                callback(change)
            except Exception as e:
                logger.warning("Change callback failed: %s", e)

        # Record to memory system (pheromone trails)
        self._record_change_to_memory(change)

        # Persist periodically
        if len(self._history) % 50 == 0:
            self._save_history()

        logger.debug("Recorded change: %s.%s (%s)",
                    change.tier.name, change.key, change.change_type.value)

    def _record_change_to_memory(self, change: BeliefChange) -> None:
        """Record belief change to unified memory system.

        Deterministic trail deposits.

        Args:
            change: The belief change to record
        """
        memory = self._get_memory()
        if memory is None:
            return

        try:
            from ..memory import Episode, Outcome

            # Create episode for the belief change
            episode = Episode(
                type=f"substrate.{change.change_type.value}",
                data={
                    "key": change.key,
                    "tier": change.tier.name,
                    "source": change.source,
                    # Don't store actual values in trails (could be sensitive)
                    "had_old_value": change.old_value is not None,
                    "had_new_value": change.new_value is not None,
                },
                outcome=Outcome.SUCCESS,
                actor=change.source,
                service="substrate_observer",
            )
            memory.record_episode(episode)

            # Record relationship between key and its tier
            memory.record_relationship(
                entity1=change.key,
                relation="stored_in_tier",
                entity2=change.tier.name,
            )

        except Exception as e:
            logger.debug("Memory recording skipped: %s", e)

    def add_change_callback(self, callback: Callable[[BeliefChange], None]) -> None:
        """Register a callback for change notifications.

        Args:
            callback: Function to call on each change
        """
        self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[[BeliefChange], None]) -> None:
        """Remove a change callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    # =========================================================================
    # Drift Detection
    # =========================================================================

    def check_drift(self, key: str) -> DriftReport:
        """Check for drift in a specific key.

        Analyzes the change history for patterns indicating drift:
        - Gradual value shifts in one direction
        - Oscillating values
        - Unusual change frequency

        Args:
            key: The substrate key to analyze

        Returns:
            DriftReport with analysis results
        """
        changes = list(self._key_changes.get(key, []))

        if len(changes) < 2:
            return DriftReport(
                key=key,
                severity=DriftSeverity.NONE,
                trend="stable",
                recommendation="Insufficient data for drift analysis",
            )

        # Get recent window
        window = changes[-DRIFT_WINDOW_SIZE:]
        window_changes = len(window)

        # Analyze numeric drift
        if self._is_numeric_sequence([c.new_value for c in window if c.new_value is not None]):
            values = [c.new_value for c in window if isinstance(c.new_value, (int, float))]
            if len(values) >= 2:
                trend, magnitude = self._calculate_trend(values)
                severity = self._severity_from_magnitude(magnitude)

                return DriftReport(
                    key=key,
                    severity=severity,
                    trend=trend,
                    magnitude=magnitude,
                    window_changes=window_changes,
                    recommendation=self._drift_recommendation(severity, trend),
                )

        # Analyze categorical drift (frequent changes)
        if window_changes >= DRIFT_WINDOW_SIZE:
            unique_values = len(set(str(c.new_value) for c in window))
            if unique_values <= 2:
                # Oscillating between few values
                return DriftReport(
                    key=key,
                    severity=DriftSeverity.MEDIUM,
                    trend="oscillating",
                    window_changes=window_changes,
                    recommendation="Value oscillating - may indicate instability",
                )
            else:
                return DriftReport(
                    key=key,
                    severity=DriftSeverity.HIGH,
                    trend="unstable",
                    window_changes=window_changes,
                    recommendation="High change frequency - review value source",
                )

        return DriftReport(
            key=key,
            severity=DriftSeverity.NONE,
            trend="stable",
            window_changes=window_changes,
            recommendation="No significant drift detected",
        )

    def check_all_drift(self) -> Dict[str, DriftReport]:
        """Check drift for all tracked keys.

        Returns:
            Dictionary mapping keys to their drift reports
        """
        reports = {}
        for key in sorted(self._key_changes.keys()):
            reports[key] = self.check_drift(key)
        return reports

    def _is_numeric_sequence(self, values: List[Any]) -> bool:
        """Check if all values are numeric."""
        return all(isinstance(v, (int, float)) for v in values if v is not None)

    def _calculate_trend(self, values: List[float]) -> tuple[str, float]:
        """Calculate trend direction and magnitude.

        Uses linear regression slope normalized by value range.

        Returns:
            (trend_direction, magnitude)
        """
        if len(values) < 2:
            return "stable", 0.0

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        # Calculate slope using least squares
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "stable", 0.0

        slope = numerator / denominator

        # Normalize by value range
        value_range = max(values) - min(values) if max(values) != min(values) else 1.0
        magnitude = abs(slope) / value_range

        if magnitude < 0.01:
            return "stable", magnitude
        elif slope > 0:
            return "increasing", magnitude
        else:
            return "decreasing", magnitude

    def _severity_from_magnitude(self, magnitude: float) -> DriftSeverity:
        """Convert drift magnitude to severity level."""
        if magnitude < 0.01:
            return DriftSeverity.NONE
        elif magnitude < 0.05:
            return DriftSeverity.LOW
        elif magnitude < 0.15:
            return DriftSeverity.MEDIUM
        elif magnitude < 0.30:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL

    def _drift_recommendation(self, severity: DriftSeverity, trend: str) -> str:
        """Generate recommendation based on drift analysis."""
        recommendations = {
            DriftSeverity.NONE: "No action needed",
            DriftSeverity.LOW: "Monitor for continued drift",
            DriftSeverity.MEDIUM: f"Review {trend} trend - may need adjustment",
            DriftSeverity.HIGH: f"Significant {trend} drift - investigate cause",
            DriftSeverity.CRITICAL: f"Critical {trend} drift - immediate review required",
        }
        return recommendations.get(severity, "Unknown severity")

    # =========================================================================
    # Consistency Checking
    # =========================================================================

    def check_consistency(self) -> ConsistencyReport:
        """Perform consistency check on the substrate.

        Runs all consistency rules and aggregates results.

        Returns:
            ConsistencyReport with findings
        """
        violations = []
        warnings = []

        for rule in self._consistency_rules:
            try:
                result = rule(self.substrate)
                if result:
                    if result.startswith("WARNING:"):
                        warnings.append(result[8:].strip())
                    else:
                        violations.append(result)
            except Exception as e:
                warnings.append(f"Rule execution failed: {e}")

        # Check constitutional integrity
        corrupted = self.substrate.verify_constitutional_integrity()
        if corrupted:
            violations.extend([f"Constitutional integrity failure: {k}" for k in corrupted])

        # Determine overall status
        all_keys = self.substrate.keys()
        healthy = len(all_keys) - len(violations) - len(warnings)

        if corrupted or len(violations) > 0:
            status = ConsistencyStatus.VIOLATION if not corrupted else ConsistencyStatus.CORRUPTED
        elif len(warnings) > 0:
            status = ConsistencyStatus.WARNING
        else:
            status = ConsistencyStatus.CONSISTENT

        return ConsistencyReport(
            status=status,
            violations=violations,
            warnings=warnings,
            checked_keys=len(all_keys),
            healthy_keys=healthy,
        )

    def _default_consistency_rules(self) -> List[Callable[[CognitiveSubstrate], Optional[str]]]:
        """Create default consistency rules."""
        rules = []

        # Rule: Burnout level must match expected values
        def check_burnout(s: CognitiveSubstrate) -> Optional[str]:
            level = s.get("burnout.level")
            if level and level not in {"GREEN", "YELLOW", "ORANGE", "RED"}:
                return f"Invalid burnout level: {level}"
            return None
        rules.append(check_burnout)

        # Rule: Mode must be valid
        def check_mode(s: CognitiveSubstrate) -> Optional[str]:
            mode = s.get("mode.current")
            if mode and mode not in {"focused", "exploring", "teaching", "recovery"}:
                return f"Invalid mode: {mode}"
            return None
        rules.append(check_mode)

        # Rule: Constitutional values must match expected
        def check_constitutional(s: CognitiveSubstrate) -> Optional[str]:
            safety_first = s.get("principles.safety_first")
            if safety_first is not None and safety_first is not True:
                return "Constitutional violation: principles.safety_first must be True"
            return None
        rules.append(check_constitutional)

        # Rule: Max agents must be reasonable
        def check_agents(s: CognitiveSubstrate) -> Optional[str]:
            max_agents = s.get("processing.max_agents")
            if max_agents is not None:
                if not isinstance(max_agents, int) or max_agents < 1 or max_agents > 10:
                    return f"WARNING: Unusual max_agents value: {max_agents}"
            return None
        rules.append(check_agents)

        return rules

    def add_consistency_rule(
        self,
        rule: Callable[[CognitiveSubstrate], Optional[str]],
    ) -> None:
        """Add a custom consistency rule.

        Args:
            rule: Function that returns None if consistent,
                  or an error string if inconsistent.
                  Prefix with "WARNING:" for warnings.
        """
        self._consistency_rules.append(rule)

    # =========================================================================
    # Convergence Tracking (RC^+xi)
    # =========================================================================

    def update_convergence(
        self,
        xi_value: float,
        current_attractor: Optional[str] = None,
    ) -> ConvergenceState:
        """Update convergence state.

        Called after each exchange to track epistemic tension
        and attractor stability.

        Args:
            xi_value: Current epistemic tension (||A_{n+1} - A_n||_2)
            current_attractor: Current attractor basin (if changed)

        Returns:
            Updated ConvergenceState
        """
        self._convergence.xi_value = xi_value

        if current_attractor and current_attractor != self._convergence.attractor:
            # Attractor switch
            self._convergence.attractor = current_attractor
            self._convergence.exchanges_at_current = 0
            self._convergence.last_switch = datetime.now()
        else:
            self._convergence.exchanges_at_current += 1

        # Update stability status
        if xi_value < CONVERGENCE_EPSILON:
            if self._convergence.exchanges_at_current >= STABLE_EXCHANGES_THRESHOLD:
                self._convergence.stability = "stable"
            else:
                self._convergence.stability = "converging"
        else:
            self._convergence.stability = "oscillating"

        return self._convergence

    def get_convergence(self) -> ConvergenceState:
        """Get current convergence state.

        Returns:
            Current ConvergenceState
        """
        return self._convergence

    def format_rc_glyph(self) -> str:
        """Format convergence state as RC glyph.

        Returns:
            String in format [RC:attractor:xi_value:stability]
        """
        return f"[RC:{self._convergence.attractor}:{self._convergence.xi_value:.2f}:{self._convergence.stability}]"

    # =========================================================================
    # Learning Integration
    # =========================================================================

    def propose_learning(
        self,
        key: str,
        proposed_value: Any,
        reason: str,
        evidence_keys: Optional[List[str]] = None,
    ) -> bool:
        """Propose a learning modification to the substrate.

        Uses the unified memory interface to submit learning proposals.
        Deterministic proposal format.

        Args:
            key: The substrate key to modify
            proposed_value: The proposed new value
            reason: Explanation for the change
            evidence_keys: List of keys that support this proposal

        Returns:
            True if proposal was accepted for review
        """
        memory = self._get_memory()
        if memory is None:
            logger.warning("Cannot propose learning: memory not available")
            return False

        try:
            # Build evidence list from recent changes
            evidence = []
            if evidence_keys:
                for ek in sorted(evidence_keys):  # Sorted
                    changes = list(self._key_changes.get(ek, []))
                    if changes:
                        recent = changes[-1]
                        evidence.append(
                            f"{ek}: {recent.old_value} -> {recent.new_value} ({recent.change_type.value})"
                        )

            # Submit proposal via memory interface
            success = memory.propose_learning(
                path=key,
                proposed_value=proposed_value,
                reason=reason,
                evidence=evidence,
            )

            if success:
                logger.info("Learning proposal submitted: %s", key)
            else:
                logger.warning("Learning proposal rejected: %s", key)

            return success

        except Exception as e:
            logger.error("Learning proposal failed: %s", e)
            return False

    def auto_propose_from_drift(self, min_severity: DriftSeverity = DriftSeverity.HIGH) -> List[str]:
        """Automatically propose learnings based on drift detection.

        Analyzes drift patterns and proposes value adjustments.
        Deterministic iteration order.

        Args:
            min_severity: Minimum drift severity to trigger proposal

        Returns:
            List of keys for which proposals were submitted
        """
        proposed_keys = []
        drift_reports = self.check_all_drift()

        for key in sorted(drift_reports.keys()):  # Sorted
            report = drift_reports[key]

            if report.severity.value >= min_severity.value:
                # Get recent values
                changes = list(self._key_changes.get(key, []))
                if not changes:
                    continue

                recent_values = [c.new_value for c in changes[-5:] if c.new_value is not None]
                if not recent_values:
                    continue

                # Propose stabilization based on trend
                if report.trend == "increasing":
                    proposed = max(recent_values)
                elif report.trend == "decreasing":
                    proposed = min(recent_values)
                else:
                    # For oscillating/unstable, use most recent
                    proposed = recent_values[-1]

                # Submit proposal
                success = self.propose_learning(
                    key=key,
                    proposed_value=proposed,
                    reason=f"Auto-stabilization: {report.trend} drift detected (severity: {report.severity.value})",
                    evidence_keys=[key],
                )

                if success:
                    proposed_keys.append(key)

        return proposed_keys

    # =========================================================================
    # History Persistence
    # =========================================================================

    def _load_history(self) -> None:
        """Load change history from disk."""
        if not self.history_path.exists():
            return

        try:
            content = self.history_path.read_text(encoding='utf-8')
            data = json.loads(content)

            for entry in data.get("history", []):
                change = BeliefChange(
                    timestamp=datetime.fromisoformat(entry["timestamp"]),
                    key=entry["key"],
                    tier=SubstrateTier[entry["tier"]],
                    change_type=ChangeType(entry["change_type"]),
                    old_value=entry.get("old_value"),
                    new_value=entry.get("new_value"),
                    source=entry.get("source", "unknown"),
                    session_id=entry.get("session_id"),
                )
                self._history.append(change)

                # Also populate per-key tracking
                if change.key not in self._key_changes:
                    self._key_changes[change.key] = deque(maxlen=DRIFT_WINDOW_SIZE * 2)
                self._key_changes[change.key].append(change)

            # Load convergence state
            conv = data.get("convergence", {})
            self._convergence = ConvergenceState(
                attractor=conv.get("attractor", "focused"),
                xi_value=conv.get("xi_value", 0.0),
                stability=conv.get("stability", "stable"),
                exchanges_at_current=conv.get("exchanges_at_current", 0),
                last_switch=datetime.fromisoformat(conv["last_switch"]) if conv.get("last_switch") else None,
            )

            logger.debug("Loaded %d history entries", len(self._history))

        except Exception as e:
            logger.warning("Failed to load observer history: %s", e)

    def _save_history(self) -> None:
        """Save change history to disk."""
        try:
            data = {
                "history": [c.to_dict() for c in self._history],
                "convergence": {
                    "attractor": self._convergence.attractor,
                    "xi_value": self._convergence.xi_value,
                    "stability": self._convergence.stability,
                    "exchanges_at_current": self._convergence.exchanges_at_current,
                    "last_switch": self._convergence.last_switch.isoformat() if self._convergence.last_switch else None,
                },
                "saved_at": datetime.now().isoformat(),
            }

            content = json.dumps(data, indent=2, default=str, sort_keys=True)
            self.history_path.write_text(content, encoding='utf-8')
            logger.debug("Saved %d history entries", len(self._history))

        except Exception as e:
            logger.error("Failed to save observer history: %s", e)

    # =========================================================================
    # Analysis & Reporting
    # =========================================================================

    def get_recent_changes(
        self,
        limit: int = 20,
        key_filter: Optional[str] = None,
        tier_filter: Optional[SubstrateTier] = None,
    ) -> List[BeliefChange]:
        """Get recent changes with optional filtering.

        Args:
            limit: Maximum changes to return
            key_filter: Filter by key prefix
            tier_filter: Filter by tier

        Returns:
            List of matching changes (newest first)
        """
        changes = list(self._history)
        changes.reverse()  # Newest first

        if key_filter:
            changes = [c for c in changes if c.key.startswith(key_filter)]

        if tier_filter is not None:
            changes = [c for c in changes if c.tier == tier_filter]

        return changes[:limit]

    def get_change_frequency(
        self,
        window_hours: float = 1.0,
    ) -> Dict[str, int]:
        """Get change frequency per key within a time window.

        Args:
            window_hours: Time window in hours

        Returns:
            Dictionary mapping keys to change counts
        """
        cutoff = datetime.now() - timedelta(hours=window_hours)
        frequency: Dict[str, int] = {}

        for change in self._history:
            if change.timestamp >= cutoff:
                frequency[change.key] = frequency.get(change.key, 0) + 1

        return dict(sorted(frequency.items(), key=lambda x: -x[1]))

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive observer report.

        Returns:
            Dictionary containing all observer data
        """
        consistency = self.check_consistency()
        drift_reports = self.check_all_drift()

        high_drift_keys = [
            k for k, r in drift_reports.items()
            if r.severity in {DriftSeverity.HIGH, DriftSeverity.CRITICAL}
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_changes": len(self._history),
                "tracked_keys": len(self._key_changes),
                "consistency_status": consistency.status.value,
                "convergence": self.format_rc_glyph(),
                "high_drift_keys": high_drift_keys,
            },
            "consistency": {
                "status": consistency.status.value,
                "violations": consistency.violations,
                "warnings": consistency.warnings,
                "checked": consistency.checked_keys,
                "healthy": consistency.healthy_keys,
            },
            "convergence": {
                "attractor": self._convergence.attractor,
                "xi_value": self._convergence.xi_value,
                "stability": self._convergence.stability,
                "exchanges_at_current": self._convergence.exchanges_at_current,
                "is_converged": self._convergence.is_converged(),
            },
            "drift": {
                k: {
                    "severity": r.severity.value,
                    "trend": r.trend,
                    "magnitude": r.magnitude,
                }
                for k, r in sorted(drift_reports.items())
            },
            "change_frequency": self.get_change_frequency(window_hours=1.0),
        }


# ============================================================================
# Factory Function
# ============================================================================

_observer: Optional[SubstrateObserver] = None


def get_observer(substrate: Optional[CognitiveSubstrate] = None) -> SubstrateObserver:
    """Get or create the singleton substrate observer.

    Args:
        substrate: The cognitive substrate to observe
                  (uses default if not provided)

    Returns:
        SubstrateObserver instance
    """
    global _observer
    if _observer is None:
        if substrate is None:
            from .interface import get_substrate
            substrate = get_substrate()
        _observer = SubstrateObserver(substrate)
    return _observer


__all__ = [
    # Enums
    "ChangeType",
    "DriftSeverity",
    "ConsistencyStatus",
    # Data classes
    "BeliefChange",
    "DriftReport",
    "ConsistencyReport",
    "ConvergenceState",
    # Main class
    "SubstrateObserver",
    # Constants
    "DRIFT_WINDOW_SIZE",
    "CONVERGENCE_EPSILON",
    "STABLE_EXCHANGES_THRESHOLD",
    # Factory
    "get_observer",
]
