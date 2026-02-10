"""
Confidence Scoring for Atmosphere Detection.

Adds nuanced confidence scores to signal detection, enabling:
- Weighted signal detection
- Threshold tuning
- Context-aware sensitivity
- Accumulation across messages

Determinism:
- Fixed scoring formulas (deterministic)
- Sorted signal evaluation order
- Same inputs always produce same scores
"""

from dataclasses import dataclass, field
from typing import Dict, Final, List, Optional, Tuple
from enum import Enum


class SignalCategory(Enum):
    """Categories of detected signals."""
    STRUGGLE = "struggle"
    FRUSTRATION = "frustration"
    EXHAUSTION = "exhaustion"
    PERFECTIONISM = "perfectionism"
    COMPLETION = "completion"
    RETURN = "return"
    START = "start"


@dataclass
class ConfidenceScore:
    """
    Confidence score for a detected signal.

    Attributes:
        category: What type of signal was detected
        score: Confidence level (0.0 to 1.0)
        signals: List of specific signals that contributed
        context_boost: Additional boost from context
    """
    category: SignalCategory
    score: float
    signals: List[str] = field(default_factory=list)
    context_boost: float = 0.0

    @property
    def adjusted_score(self) -> float:
        """Score after context adjustment, capped at 1.0."""
        return min(1.0, self.score + self.context_boost)

    def meets_threshold(self, threshold: float = 0.5) -> bool:
        """Check if score meets the given threshold."""
        return self.adjusted_score >= threshold


@dataclass
class DetectionContext:
    """
    Context that affects detection sensitivity.

    Attributes:
        recent_struggles: Number of struggles detected recently
        burnout_level: Current burnout level (GREEN/YELLOW/ORANGE/RED)
        energy_level: Current energy level
        momentum_phase: Current momentum phase
        message_count: Messages in current session
    """
    recent_struggles: int = 0
    burnout_level: str = "GREEN"
    energy_level: str = "medium"
    momentum_phase: str = "building"
    message_count: int = 0

    def get_sensitivity_multiplier(self) -> float:
        """
        Get sensitivity multiplier based on context.

        Higher values = more sensitive (lower thresholds).
        Lower values = less sensitive (higher thresholds).
        """
        multiplier = 1.0

        # Burnout increases sensitivity to struggles
        if self.burnout_level == "RED":
            multiplier *= 1.5
        elif self.burnout_level == "ORANGE":
            multiplier *= 1.3
        elif self.burnout_level == "YELLOW":
            multiplier *= 1.1

        # Low energy increases sensitivity
        if self.energy_level == "depleted":
            multiplier *= 1.4
        elif self.energy_level == "low":
            multiplier *= 1.2

        # Crashed momentum increases sensitivity
        if self.momentum_phase == "crashed":
            multiplier *= 1.3

        # Recent struggles compound
        if self.recent_struggles >= 3:
            multiplier *= 1.2
        elif self.recent_struggles >= 1:
            multiplier *= 1.1

        return multiplier


# Signal weights for confidence scoring (sorted for determinism)
STRUGGLE_SIGNAL_WEIGHTS: Final[Dict[str, float]] = {
    "can't": 0.7,
    "cannot": 0.7,
    "confused": 0.6,
    "don't understand": 0.8,
    "failing": 0.7,
    "frustrated": 0.9,
    "give up": 0.9,
    "hate": 0.8,
    "lost": 0.6,
    "nothing works": 0.9,
    "overwhelmed": 0.8,
    "stuck": 0.8,
    "unable": 0.7,
}

EXHAUSTION_SIGNAL_WEIGHTS: Final[Dict[str, float]] = {
    "burnt out": 0.9,
    "can't focus": 0.7,
    "depleted": 0.8,
    "drained": 0.8,
    "exhausted": 0.9,
    "need a break": 0.8,
    "no energy": 0.8,
    "tired": 0.7,
}

PERFECTIONISM_SIGNAL_WEIGHTS: Final[Dict[str, float]] = {
    "almost": 0.4,
    "could be better": 0.6,
    "let me just": 0.7,
    "needs work": 0.5,
    "not done": 0.5,
    "not perfect": 0.6,
    "not quite": 0.5,
    "one more thing": 0.8,
    "should polish": 0.6,
}

COMPLETION_SIGNAL_WEIGHTS: Final[Dict[str, float]] = {
    "completed": 0.9,
    "deployed": 0.9,
    "done": 0.8,
    "finished": 0.9,
    "fixed": 0.8,
    "merged": 0.9,
    "passed": 0.7,
    "resolved": 0.8,
    "shipped": 0.9,
}


def calculate_confidence(
    message: str,
    signal_weights: Dict[str, float],
    category: SignalCategory,
) -> ConfidenceScore:
    """
    Calculate confidence score for a signal category.

    Deterministic: signals checked in sorted order,
    weights combined using fixed formula.

    Args:
        message: User message to analyze
        signal_weights: Dictionary of signal -> weight mappings
        category: Category being scored

    Returns:
        ConfidenceScore with calculated confidence
    """
    msg_lower = message.lower()
    matched_signals = []
    total_weight = 0.0

    # Check signals in sorted order (deterministic)
    for signal in sorted(signal_weights.keys()):
        if signal in msg_lower:
            matched_signals.append(signal)
            total_weight += signal_weights[signal]

    # Calculate score: diminishing returns for multiple signals
    # First signal counts full, subsequent signals count less
    if len(matched_signals) == 0:
        score = 0.0
    elif len(matched_signals) == 1:
        score = total_weight
    else:
        # Weighted average with diminishing returns
        # score = max_weight + 0.3 * (remaining_weight)
        weights = sorted([signal_weights[s] for s in matched_signals], reverse=True)
        score = weights[0] + 0.3 * sum(weights[1:])

    # Cap at 1.0
    score = min(1.0, score)

    return ConfidenceScore(
        category=category,
        score=score,
        signals=matched_signals,
    )


def detect_with_confidence(
    message: str,
    context: Optional[DetectionContext] = None,
) -> Dict[SignalCategory, ConfidenceScore]:
    """
    Detect all signal categories with confidence scores.

    Deterministic: categories checked in fixed order.

    Args:
        message: User message to analyze
        context: Optional context for sensitivity adjustment

    Returns:
        Dictionary of category -> ConfidenceScore
    """
    ctx = context or DetectionContext()
    sensitivity = ctx.get_sensitivity_multiplier()

    scores = {}

    # Calculate confidence for each category (fixed order)
    scores[SignalCategory.STRUGGLE] = calculate_confidence(
        message, STRUGGLE_SIGNAL_WEIGHTS, SignalCategory.STRUGGLE
    )
    scores[SignalCategory.EXHAUSTION] = calculate_confidence(
        message, EXHAUSTION_SIGNAL_WEIGHTS, SignalCategory.EXHAUSTION
    )
    scores[SignalCategory.PERFECTIONISM] = calculate_confidence(
        message, PERFECTIONISM_SIGNAL_WEIGHTS, SignalCategory.PERFECTIONISM
    )
    scores[SignalCategory.COMPLETION] = calculate_confidence(
        message, COMPLETION_SIGNAL_WEIGHTS, SignalCategory.COMPLETION
    )

    # Apply context boost based on sensitivity
    for category, score in scores.items():
        if score.score > 0:
            # Boost is proportional to (sensitivity - 1.0)
            score.context_boost = score.score * (sensitivity - 1.0) * 0.5

    return scores


def get_highest_confidence(
    scores: Dict[SignalCategory, ConfidenceScore],
    threshold: float = 0.5,
) -> Optional[Tuple[SignalCategory, ConfidenceScore]]:
    """
    Get the highest-confidence signal above threshold.

    Args:
        scores: Dictionary of category -> ConfidenceScore
        threshold: Minimum confidence threshold

    Returns:
        Tuple of (category, score) or None if nothing above threshold
    """
    above_threshold = [
        (cat, score)
        for cat, score in scores.items()
        if score.meets_threshold(threshold)
    ]

    if not above_threshold:
        return None

    # Sort by adjusted score (deterministic)
    above_threshold.sort(key=lambda x: x[1].adjusted_score, reverse=True)
    return above_threshold[0]


@dataclass
class TuningConfig:
    """
    Configuration for detection tuning.

    Allows adjustment of thresholds and weights.
    """
    struggle_threshold: float = 0.5
    exhaustion_threshold: float = 0.6
    perfectionism_threshold: float = 0.6
    completion_threshold: float = 0.5
    context_sensitivity: float = 1.0  # Multiplier for context effects

    def get_threshold(self, category: SignalCategory) -> float:
        """Get threshold for a category."""
        thresholds = {
            SignalCategory.STRUGGLE: self.struggle_threshold,
            SignalCategory.EXHAUSTION: self.exhaustion_threshold,
            SignalCategory.PERFECTIONISM: self.perfectionism_threshold,
            SignalCategory.COMPLETION: self.completion_threshold,
        }
        return thresholds.get(category, 0.5)


# Default tuning configuration
DEFAULT_TUNING = TuningConfig()


__all__ = [
    "SignalCategory",
    "ConfidenceScore",
    "DetectionContext",
    "TuningConfig",
    "DEFAULT_TUNING",
    "calculate_confidence",
    "detect_with_confidence",
    "get_highest_confidence",
    "STRUGGLE_SIGNAL_WEIGHTS",
    "EXHAUSTION_SIGNAL_WEIGHTS",
    "PERFECTIONISM_SIGNAL_WEIGHTS",
    "COMPLETION_SIGNAL_WEIGHTS",
]
