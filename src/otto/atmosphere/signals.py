"""
Atmosphere Signals for Cognitive State Integration.

Returns structured signals from atmosphere processing that can
inform cognitive routing and state updates.

These signals flow BACK from atmosphere to the cognitive layer:
- Detected struggles inform expert selection
- Permission needs indicate burnout progression
- Affirmation patterns show momentum
- Reframe usage shows learning state

Determinism:
- Fixed signal structure (deterministic)
- Same inputs produce same signals
- Signals are observational (no side effects)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class SignalSeverity(Enum):
    """Severity level of detected signals."""
    LOW = "low"         # Minor indicator
    MEDIUM = "medium"   # Notable signal
    HIGH = "high"       # Strong signal, may need intervention
    CRITICAL = "critical"  # Immediate attention needed


@dataclass
class AtmosphereSignals:
    """
    Signals extracted from atmosphere processing.

    These signals can inform cognitive routing decisions.
    """
    # === Struggle signals ===
    struggle_detected: bool = False
    struggle_type: Optional[str] = None  # Pattern that matched
    struggle_severity: SignalSeverity = SignalSeverity.LOW

    # === Energy signals ===
    energy_mismatch: bool = False  # Response was truncated significantly
    truncation_ratio: float = 0.0  # How much was truncated (0.0-1.0)
    needs_shorter_responses: bool = False

    # === Permission signals ===
    permission_needed: bool = False
    permission_type: Optional[str] = None
    burnout_indicator: bool = False  # Permission need indicates burnout

    # === Affirmation signals ===
    affirmation_earned: bool = False
    affirmation_type: Optional[str] = None
    momentum_indicator: Optional[str] = None  # "building", "maintaining", "recovering"

    # === Reframe signals ===
    reframe_applied: bool = False
    reframe_pattern: Optional[str] = None
    learning_mode: bool = False  # User is in learning/growth mode

    # === Pattern match signals ===
    patterns_matched: List[str] = field(default_factory=list)
    pattern_categories: Dict[str, int] = field(default_factory=dict)

    # === Aggregate indicators ===
    needs_expert_switch: bool = False
    suggested_expert: Optional[str] = None
    cognitive_load_high: bool = False
    session_fatigue: bool = False

    def get_routing_hints(self) -> Dict[str, any]:
        """
        Get hints for cognitive routing based on signals.

        Returns dict of routing suggestions.
        """
        hints = {}

        # Expert switch suggestions
        if self.struggle_detected and self.struggle_severity in (SignalSeverity.HIGH, SignalSeverity.CRITICAL):
            hints["suggest_scaffolder"] = True
            hints["reason"] = "high_struggle"

        if self.burnout_indicator:
            hints["suggest_restorer"] = True
            hints["reason"] = "burnout_detected"

        if self.permission_type == "stop" or self.permission_type == "rest":
            hints["consider_session_end"] = True
            hints["reason"] = "permission_signals"

        # Energy hints
        if self.needs_shorter_responses:
            hints["reduce_response_length"] = True
            hints["suggested_max_length"] = 100 if self.truncation_ratio > 0.5 else 200

        # Mode hints
        if self.learning_mode:
            hints["socratic_mode"] = True

        return hints

    def should_escalate(self) -> bool:
        """Check if signals indicate need for escalation."""
        return (
            self.struggle_severity == SignalSeverity.CRITICAL
            or self.burnout_indicator
            or (self.struggle_detected and self.permission_needed)
        )


def extract_signals(
    response: str,
    transformed: str,
    user_message: str,
    patterns_matched: List[str],
    affirmation_type: Optional[str] = None,
    permission_type: Optional[str] = None,
    reframe_pattern: Optional[str] = None,
    energy_level: str = "medium",
    burnout_level: str = "GREEN",
) -> AtmosphereSignals:
    """
    Extract atmosphere signals from transformation results.

    Deterministic extraction from transformation outputs.

    Args:
        response: Original response
        transformed: Transformed response
        user_message: Original user message
        patterns_matched: List of patterns that matched
        affirmation_type: Type of affirmation added (if any)
        permission_type: Type of permission granted (if any)
        reframe_pattern: Reframe pattern matched (if any)
        energy_level: Current energy level
        burnout_level: Current burnout level

    Returns:
        AtmosphereSignals with extracted signals
    """
    signals = AtmosphereSignals()

    # === Calculate truncation ===
    original_len = len(response)
    transformed_len = len(transformed)
    if original_len > 0:
        signals.truncation_ratio = max(0, (original_len - transformed_len) / original_len)
        signals.energy_mismatch = signals.truncation_ratio > 0.3
        signals.needs_shorter_responses = signals.truncation_ratio > 0.5

    # === Struggle signals ===
    if reframe_pattern:
        signals.struggle_detected = True
        signals.struggle_type = reframe_pattern
        signals.reframe_applied = True
        signals.reframe_pattern = reframe_pattern
        signals.learning_mode = True

        # Determine severity based on pattern
        high_severity_patterns = [
            "give up", "quit", "hate", "nothing works",
            "not smart", "stupid", "dumb"
        ]
        if any(p in reframe_pattern.lower() for p in high_severity_patterns):
            signals.struggle_severity = SignalSeverity.HIGH
        else:
            signals.struggle_severity = SignalSeverity.MEDIUM

    # === Permission signals ===
    if permission_type:
        signals.permission_needed = True
        signals.permission_type = permission_type
        signals.burnout_indicator = permission_type in ("stop", "rest")

    # === Affirmation signals ===
    if affirmation_type:
        signals.affirmation_earned = True
        signals.affirmation_type = affirmation_type

        # Infer momentum from affirmation type
        if affirmation_type == "completion":
            signals.momentum_indicator = "building"
        elif affirmation_type == "recovery":
            signals.momentum_indicator = "recovering"
        elif affirmation_type in ("progress", "persistence"):
            signals.momentum_indicator = "maintaining"

    # === Pattern signals ===
    signals.patterns_matched = patterns_matched
    for pattern in patterns_matched:
        category = _categorize_pattern(pattern)
        signals.pattern_categories[category] = signals.pattern_categories.get(category, 0) + 1

    # === Aggregate indicators ===
    # Cognitive load high if many patterns matched
    signals.cognitive_load_high = len(patterns_matched) > 5

    # Session fatigue if low energy + permission needed
    signals.session_fatigue = (
        energy_level in ("depleted", "low")
        and signals.permission_needed
    )

    # Expert switch suggestion
    if signals.struggle_severity == SignalSeverity.HIGH:
        signals.needs_expert_switch = True
        signals.suggested_expert = "Scaffolder"
    elif signals.burnout_indicator:
        signals.needs_expert_switch = True
        signals.suggested_expert = "Restorer"

    return signals


def _categorize_pattern(pattern: str) -> str:
    """Categorize a pattern into a group."""
    pattern_lower = pattern.lower()

    if any(x in pattern_lower for x in ["you should", "you need", "you must"]):
        return "instructional"
    elif any(x in pattern_lower for x in ["make sure", "ensure", "important"]):
        return "directive"
    elif any(x in pattern_lower for x in ["let me know", "feel free", "don't hesitate"]):
        return "filler"
    elif any(x in pattern_lower for x in ["i suggest", "i recommend", "i think"]):
        return "hedging"
    else:
        return "other"


def aggregate_session_signals(
    signals_list: List[AtmosphereSignals],
) -> Dict[str, any]:
    """
    Aggregate signals across a session.

    Useful for session-level insights.

    Args:
        signals_list: List of signals from session

    Returns:
        Aggregated session metrics
    """
    if not signals_list:
        return {}

    return {
        "total_transformations": len(signals_list),
        "struggles_detected": sum(1 for s in signals_list if s.struggle_detected),
        "permissions_granted": sum(1 for s in signals_list if s.permission_needed),
        "affirmations_earned": sum(1 for s in signals_list if s.affirmation_earned),
        "reframes_applied": sum(1 for s in signals_list if s.reframe_applied),
        "avg_truncation_ratio": sum(s.truncation_ratio for s in signals_list) / len(signals_list),
        "burnout_indicators": sum(1 for s in signals_list if s.burnout_indicator),
        "escalation_needed": any(s.should_escalate() for s in signals_list),
        "high_severity_count": sum(
            1 for s in signals_list
            if s.struggle_severity in (SignalSeverity.HIGH, SignalSeverity.CRITICAL)
        ),
    }


__all__ = [
    "SignalSeverity",
    "AtmosphereSignals",
    "extract_signals",
    "aggregate_session_signals",
]
