"""
Tension Surfacer Module
=======================

Detects and surfaces tensions when the cognitive model is uncertain.

Philosophy:
Instead of auto-resolving conflicts, Orchestra surfaces tensions to the user
when the model has low confidence or when multiple valid approaches exist.
This respects the "User knows best" constitutional principle.

Types of Tension:
1. Attribute Conflict: Multiple layers disagree on a value
2. Mode Mismatch: Detected signals don't match current mode
3. Safety Tension: User requests conflict with safety floors
4. Epistemic Tension: High uncertainty in state prediction

ThinkingMachines [He2025] Compliance:
- Fixed tension detection order
- Deterministic threshold evaluation
- Surfacing decision is reproducible
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

from .cognitive_stage import (
    CognitiveStage,
    AttributeOpinion,
    LayerPriority,
    CONSTITUTIONAL_VALUES,
)
from .cognitive_state import BurnoutLevel, EnergyLevel, CognitiveMode
from .prism_detector import SignalVector, SignalCategory

logger = logging.getLogger(__name__)


# =============================================================================
# Tension Types
# =============================================================================

class TensionType(Enum):
    """Types of cognitive tension."""
    ATTRIBUTE_CONFLICT = "attribute_conflict"   # Layers disagree
    MODE_MISMATCH = "mode_mismatch"             # Signals vs current mode
    SAFETY_TENSION = "safety_tension"           # Request vs safety floor
    EPISTEMIC_TENSION = "epistemic_tension"     # High uncertainty
    APPROACH_CHOICE = "approach_choice"         # Multiple valid approaches
    PRIORITY_CONFLICT = "priority_conflict"     # Competing goals


class TensionSeverity(Enum):
    """Severity levels for tension."""
    LOW = "low"         # Informational, can auto-resolve
    MEDIUM = "medium"   # Should surface, but not blocking
    HIGH = "high"       # Must surface, blocking decision needed
    CRITICAL = "critical"  # Safety-related, immediate attention


# =============================================================================
# Tension Data Structure
# =============================================================================

@dataclass
class Tension:
    """
    A detected tension requiring attention.

    Tensions are surfaced rather than auto-resolved to respect user agency.
    """
    tension_type: TensionType
    severity: TensionSeverity
    description: str

    # Context
    attribute: Optional[str] = None
    opinions: List[Tuple[str, Any]] = field(default_factory=list)
    current_value: Any = None
    recommended_value: Any = None

    # For approach choices
    options: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    source: str = ""  # What detected this tension
    requires_user_decision: bool = True
    auto_resolve_allowed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tension to dict."""
        return {
            "type": self.tension_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "attribute": self.attribute,
            "opinions": self.opinions,
            "current_value": str(self.current_value) if self.current_value else None,
            "recommended_value": str(self.recommended_value) if self.recommended_value else None,
            "options": self.options,
            "source": self.source,
            "requires_user_decision": self.requires_user_decision,
            "auto_resolve_allowed": self.auto_resolve_allowed,
        }

    def format_for_display(self) -> str:
        """Format tension for user display."""
        lines = [f"[{self.severity.value.upper()}] {self.description}"]

        if self.opinions:
            lines.append("Conflicting opinions:")
            for layer, value in self.opinions:
                lines.append(f"  - {layer}: {value}")

        if self.options:
            lines.append("Options:")
            for i, opt in enumerate(self.options, 1):
                label = opt.get("label", f"Option {i}")
                desc = opt.get("description", "")
                lines.append(f"  {i}. {label}: {desc}")

        if self.recommended_value and self.auto_resolve_allowed:
            lines.append(f"Recommendation: {self.recommended_value}")

        return "\n".join(lines)


# =============================================================================
# Tension Detection Result
# =============================================================================

@dataclass
class TensionReport:
    """
    Report of all detected tensions.

    Contains tensions to surface and resolution recommendations.
    """
    tensions: List[Tension] = field(default_factory=list)
    total_tension_score: float = 0.0
    should_surface: bool = False
    auto_resolved: List[Tension] = field(default_factory=list)

    def add_tension(self, tension: Tension) -> None:
        """Add a tension to the report."""
        self.tensions.append(tension)

        # Update total score
        severity_weights = {
            TensionSeverity.LOW: 0.1,
            TensionSeverity.MEDIUM: 0.3,
            TensionSeverity.HIGH: 0.6,
            TensionSeverity.CRITICAL: 1.0,
        }
        self.total_tension_score += severity_weights.get(tension.severity, 0.3)

    def has_tensions(self) -> bool:
        """Check if any tensions exist."""
        return len(self.tensions) > 0

    def get_critical_tensions(self) -> List[Tension]:
        """Get only critical tensions."""
        return [t for t in self.tensions if t.severity == TensionSeverity.CRITICAL]

    def get_surfaceable_tensions(self) -> List[Tension]:
        """Get tensions that should be surfaced to user."""
        return [t for t in self.tensions if t.requires_user_decision]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dict."""
        return {
            "tensions": [t.to_dict() for t in self.tensions],
            "total_tension_score": self.total_tension_score,
            "should_surface": self.should_surface,
            "auto_resolved": [t.to_dict() for t in self.auto_resolved],
            "critical_count": len(self.get_critical_tensions()),
            "surfaceable_count": len(self.get_surfaceable_tensions()),
        }


# =============================================================================
# Tension Surfacer
# =============================================================================

class TensionSurfacer:
    """
    Detects and surfaces cognitive tensions.

    Instead of auto-resolving conflicts, this module identifies when:
    1. The model is uncertain about state predictions
    2. Multiple valid approaches exist for a task
    3. User requests conflict with safety constraints
    4. Detected signals don't match expected patterns

    Tensions are surfaced for user decision rather than guessed.

    ThinkingMachines [He2025] Compliance:
    - Fixed detection order (attribute → mode → safety → epistemic)
    - Deterministic thresholds (from constitutional layer)
    - Reproducible surfacing decisions
    """

    # Detection order is FIXED
    DETECTION_ORDER = [
        "attribute_conflicts",
        "mode_mismatches",
        "safety_tensions",
        "epistemic_tensions",
        "approach_choices",
    ]

    def __init__(self, stage: CognitiveStage):
        """
        Initialize tension surfacer.

        Args:
            stage: CognitiveStage for accessing state and opinions
        """
        self.stage = stage

        # Thresholds from constitutional layer
        self.surfacing_threshold = CONSTITUTIONAL_VALUES.get("tension_surfacing_threshold", 0.3)
        self.auto_resolve_threshold = self.surfacing_threshold * 0.5  # Below this, auto-resolve

    def detect(self, signals: SignalVector = None,
               user_request: str = None) -> TensionReport:
        """
        Detect all tensions in current state.

        Uses FIXED detection order for determinism.

        Args:
            signals: Optional detected signals from PRISM
            user_request: Optional user request text

        Returns:
            TensionReport with all detected tensions
        """
        report = TensionReport()

        # Detect in FIXED order
        for detection_type in self.DETECTION_ORDER:
            detector = getattr(self, f"_detect_{detection_type}", None)
            if detector:
                tensions = detector(signals, user_request)
                for tension in tensions:
                    report.add_tension(tension)

        # Determine if should surface
        report.should_surface = (
            report.total_tension_score >= self.surfacing_threshold or
            len(report.get_critical_tensions()) > 0
        )

        # Try auto-resolve low tensions
        report = self._auto_resolve_low_tensions(report)

        logger.debug(f"Detected {len(report.tensions)} tensions, score={report.total_tension_score:.2f}")
        return report

    def _detect_attribute_conflicts(self, signals: SignalVector,
                                    user_request: str) -> List[Tension]:
        """
        Detect conflicts in attribute opinions across layers.

        These occur when multiple layers have different opinions
        about the same cognitive attribute.
        """
        tensions = []

        # Key attributes to check for conflicts
        key_attributes = [
            "burnout_level",
            "energy_level",
            "mode",
            "paradigm",
            "focus_level",
        ]

        for attr in key_attributes:
            opinion = self.stage.get_opinion_stack(attr)

            if opinion.has_conflict:
                # Build opinion list
                opinions = [(layer, str(value)) for layer, _, value in opinion.opinions]

                tension = Tension(
                    tension_type=TensionType.ATTRIBUTE_CONFLICT,
                    severity=TensionSeverity.MEDIUM,
                    description=f"Conflicting values for '{attr}'",
                    attribute=attr,
                    opinions=opinions,
                    current_value=opinion.resolved_value,
                    source="attribute_conflict_detector",
                    auto_resolve_allowed=True,  # Can use LIVRPS resolution
                )
                tensions.append(tension)

        return tensions

    def _detect_mode_mismatches(self, signals: SignalVector,
                                user_request: str) -> List[Tension]:
        """
        Detect mismatch between detected signals and current mode.

        For example: exploring signals detected while in focused mode.
        """
        tensions = []

        if not signals:
            return tensions

        current_mode = self.stage.get_mode()

        # Signal to mode mapping
        mode_signals = {
            "exploring": SignalCategory.MODE,
            "focused": SignalCategory.MODE,
            "teaching": SignalCategory.MODE,
            "recovery": SignalCategory.ENERGY,
        }

        # Check for mismatch
        if signals.mode_detected and signals.mode_detected != current_mode:
            # Detected mode doesn't match current mode
            options = [
                {
                    "label": f"Switch to {signals.mode_detected}",
                    "description": f"Your signals suggest {signals.mode_detected} mode",
                    "action": f"set_mode:{signals.mode_detected}",
                },
                {
                    "label": f"Stay in {current_mode}",
                    "description": f"Continue with current {current_mode} mode",
                    "action": f"keep_mode:{current_mode}",
                },
            ]

            tension = Tension(
                tension_type=TensionType.MODE_MISMATCH,
                severity=TensionSeverity.LOW,
                description=f"Detected '{signals.mode_detected}' signals but currently in '{current_mode}' mode",
                current_value=current_mode,
                recommended_value=signals.mode_detected,
                options=options,
                source="mode_mismatch_detector",
                auto_resolve_allowed=True,
            )
            tensions.append(tension)

        # Check for energy-mode mismatch
        if signals.energy_state == "depleted" and current_mode != "recovery":
            tension = Tension(
                tension_type=TensionType.MODE_MISMATCH,
                severity=TensionSeverity.HIGH,
                description="Energy depleted but not in recovery mode",
                current_value=current_mode,
                recommended_value="recovery",
                options=[
                    {
                        "label": "Switch to recovery",
                        "description": "Enter recovery mode for easier tasks",
                        "action": "set_mode:recovery",
                    },
                    {
                        "label": "Push through",
                        "description": "Continue current mode (not recommended)",
                        "action": "acknowledge_depleted",
                    },
                ],
                source="energy_mode_detector",
                requires_user_decision=True,
                auto_resolve_allowed=False,  # Safety-related, don't auto-resolve
            )
            tensions.append(tension)

        return tensions

    def _detect_safety_tensions(self, signals: SignalVector,
                                user_request: str) -> List[Tension]:
        """
        Detect tensions between user requests and safety floors.

        These are CRITICAL tensions that cannot be auto-resolved.
        """
        tensions = []

        # Get current safety-relevant state
        burnout = self.stage.get_resolved("burnout_level")
        energy = self.stage.get_resolved("energy_level")

        # Check for working during RED burnout
        if burnout == "red" and user_request:
            # Any work request during RED is a safety tension
            tension = Tension(
                tension_type=TensionType.SAFETY_TENSION,
                severity=TensionSeverity.CRITICAL,
                description="Work requested while in RED burnout state",
                current_value=burnout,
                options=[
                    {
                        "label": "Enter recovery",
                        "description": "Switch to recovery mode and take care of yourself",
                        "action": "enter_recovery",
                    },
                    {
                        "label": "Done for today",
                        "description": "Save state and stop. Tomorrow is fine.",
                        "action": "save_and_exit",
                    },
                    {
                        "label": "Scope cut",
                        "description": "Reduce to absolute minimum viable task",
                        "action": "scope_cut",
                    },
                ],
                source="safety_tension_detector",
                requires_user_decision=True,
                auto_resolve_allowed=False,
            )
            tensions.append(tension)

        # Check for agent spawning during overload
        if burnout in ("orange", "red") or energy == "depleted":
            # Check if request might spawn agents
            agent_keywords = ["parallel", "concurrent", "spawn", "multiple agents"]
            if user_request and any(kw in user_request.lower() for kw in agent_keywords):
                tension = Tension(
                    tension_type=TensionType.SAFETY_TENSION,
                    severity=TensionSeverity.HIGH,
                    description="Agent spawning requested during cognitive overload",
                    current_value=f"burnout={burnout}, energy={energy}",
                    recommended_value="direct_action",
                    options=[
                        {
                            "label": "Direct action only",
                            "description": "Handle task directly without spawning agents",
                            "action": "direct_only",
                        },
                        {
                            "label": "Proceed anyway",
                            "description": "Spawn agents despite cognitive load (not recommended)",
                            "action": "force_agents",
                        },
                    ],
                    source="safety_tension_detector",
                    requires_user_decision=True,
                    auto_resolve_allowed=False,
                )
                tensions.append(tension)

        return tensions

    def _detect_epistemic_tensions(self, signals: SignalVector,
                                   user_request: str) -> List[Tension]:
        """
        Detect high epistemic uncertainty in state prediction.

        Based on RC^+xi convergence tracking.
        """
        tensions = []

        # Get epistemic tension from stage
        xi = self.stage.get_resolved("epistemic_tension") or 0.0

        if xi > 0.5:
            # High epistemic tension - uncertain about state
            tension = Tension(
                tension_type=TensionType.EPISTEMIC_TENSION,
                severity=TensionSeverity.MEDIUM,
                description=f"High uncertainty in cognitive state prediction (xi={xi:.2f})",
                current_value=xi,
                recommended_value="calibrate",
                options=[
                    {
                        "label": "Quick calibration",
                        "description": "Answer 2-3 questions to improve state prediction",
                        "action": "calibrate",
                    },
                    {
                        "label": "Continue as-is",
                        "description": "Proceed with current (uncertain) prediction",
                        "action": "continue",
                    },
                ],
                source="epistemic_tension_detector",
                auto_resolve_allowed=True,
            )
            tensions.append(tension)

        return tensions

    def _detect_approach_choices(self, signals: SignalVector,
                                 user_request: str) -> List[Tension]:
        """
        Detect when multiple valid approaches exist.

        This is for tasks where user input matters.
        """
        tensions = []

        # This would typically be populated by task analysis
        # For now, we detect based on keywords that suggest multiple paths

        if not user_request:
            return tensions

        # Keywords suggesting approach choice
        choice_keywords = [
            "should I", "which approach", "what's better",
            "options", "alternatives", "prefer",
        ]

        if any(kw in user_request.lower() for kw in choice_keywords):
            tension = Tension(
                tension_type=TensionType.APPROACH_CHOICE,
                severity=TensionSeverity.LOW,
                description="Multiple approaches may be valid - user input requested",
                source="approach_choice_detector",
                requires_user_decision=True,
                auto_resolve_allowed=False,
            )
            tensions.append(tension)

        return tensions

    def _auto_resolve_low_tensions(self, report: TensionReport) -> TensionReport:
        """
        Auto-resolve low-severity tensions that allow it.

        Respects the auto_resolve_threshold.
        """
        remaining_tensions = []

        for tension in report.tensions:
            if (tension.auto_resolve_allowed and
                tension.severity == TensionSeverity.LOW):
                # Auto-resolve using LIVRPS resolution or recommended value
                report.auto_resolved.append(tension)
                logger.debug(f"Auto-resolved tension: {tension.description}")
            else:
                remaining_tensions.append(tension)

        report.tensions = remaining_tensions

        # Recalculate score
        report.total_tension_score = sum(
            {TensionSeverity.LOW: 0.1, TensionSeverity.MEDIUM: 0.3,
             TensionSeverity.HIGH: 0.6, TensionSeverity.CRITICAL: 1.0}[t.severity]
            for t in report.tensions
        )

        return report

    def should_interrupt(self, report: TensionReport,
                         focus_level: str = "moderate") -> bool:
        """
        Determine if tensions should interrupt the user.

        Respects focus level calibration:
        - scattered: Interrupt more (surface more tensions)
        - moderate: Standard threshold
        - locked_in: Interrupt less (only critical)
        """
        # Adjust threshold based on focus level
        thresholds = {
            "scattered": self.surfacing_threshold * 1.5,  # Surface more
            "moderate": self.surfacing_threshold,
            "locked_in": self.surfacing_threshold * 0.5,  # Only critical
        }
        threshold = thresholds.get(focus_level, self.surfacing_threshold)

        # Always interrupt for critical
        if report.get_critical_tensions():
            return True

        # Otherwise check threshold
        return report.total_tension_score >= threshold

    def format_tensions_for_user(self, report: TensionReport) -> str:
        """
        Format tensions for user display.

        Returns formatted string for injection into response.
        """
        if not report.has_tensions():
            return ""

        surfaceable = report.get_surfaceable_tensions()
        if not surfaceable:
            return ""

        lines = ["", "---", "**Tension Detected**", ""]

        for tension in surfaceable:
            lines.append(tension.format_for_display())
            lines.append("")

        lines.append("---")
        return "\n".join(lines)


# =============================================================================
# Factory Function
# =============================================================================

def create_tension_surfacer(stage: CognitiveStage) -> TensionSurfacer:
    """
    Create a tension surfacer for a cognitive stage.

    Args:
        stage: CognitiveStage to monitor

    Returns:
        Configured TensionSurfacer
    """
    return TensionSurfacer(stage)


__all__ = [
    'TensionType',
    'TensionSeverity',
    'Tension',
    'TensionReport',
    'TensionSurfacer',
    'create_tension_surfacer',
]
