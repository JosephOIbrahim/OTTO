"""
PRISM Signal Detector
=====================

Multi-perspective signal detection with FIXED evaluation order.

Signal Categories (evaluated in this FIXED order):
1. EMOTIONAL - frustrated, overwhelmed, stuck (highest priority)
2. MODE - exploring, focused, teaching
3. DOMAIN - VFX, WebDev, AI Research (from active payload)
4. TASK - implement, debug, plan, research
5. ENERGY - tired, exhausted, break

ThinkingMachines [He2025] Compliance:
- Fixed evaluation order (SIGNAL_PRIORITY)
- Deterministic pattern matching
- No dynamic algorithm switching
- Reproducible signal vectors

PRISM 6-Perspective Framework:
- Causal: cause-effect relationships
- Optimization: efficiency improvements
- Hierarchical: structure/layers
- Temporal: time-based patterns
- Risk: potential problems
- Opportunity: potential benefits
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Signal Categories - FIXED Priority Order
# =============================================================================

class SignalCategory(Enum):
    """Signal categories in FIXED priority order."""
    EMOTIONAL = 1   # Highest priority - safety first
    PROTECTION = 2  # Protection signals - overuse, needs break
    MODE = 3        # Cognitive mode switches
    DOMAIN = 4      # Domain-specific signals
    TASK = 5        # Task type signals
    ENERGY = 6      # Energy level signals


# Signal patterns - evaluated in category order
SIGNAL_PATTERNS = {
    SignalCategory.EMOTIONAL: {
        "frustrated": ["frustrated", "annoying", "ugh", "damn", "wtf", "hate"],
        "overwhelmed": ["overwhelmed", "too much", "can't handle", "drowning"],
        "stuck": ["stuck", "blocked", "can't figure", "don't understand", "confused"],
        "anxious": ["anxious", "worried", "nervous", "stress"],
        "angry": ["angry", "pissed", "furious"],  # Higher severity
    },
    SignalCategory.PROTECTION: {
        # Overuse signals - user pushing past limits
        "overuse": [
            "keep going", "just one more", "almost done", "push through",
            "can't stop now", "need to finish", "just a bit more"
        ],
        # Break request signals
        "needs_break": [
            "need a break", "stepping away", "back soon", "taking five",
            "be back", "grabbing coffee", "quick walk"
        ],
        # Override signals - user explicitly overriding protection
        "override": [
            "i know but", "ignore that", "let me", "i'm fine",
            "don't worry", "i can handle", "override"
        ],
        # Hyperfocus warning signals
        "hyperfocus": [
            "in the zone", "flow state", "don't interrupt", "on a roll",
            "got momentum", "can't stop", "so close"
        ],
    },
    SignalCategory.MODE: {
        "exploring": ["what if", "explore", "brainstorm", "ideas", "consider", "might"],
        "focused": ["focus", "just do", "implement", "execute", "get it done"],
        "teaching": ["explain", "how does", "why does", "teach me", "help me understand"],
        "recovery": ["break", "rest", "pause", "step back", "need time"],
    },
    SignalCategory.DOMAIN: {
        # WebDev domain
        "webdev": ["react", "next", "css", "api", "frontend", "backend", "component"],
        # AI Research domain
        "ai_research": ["model", "train", "inference", "llm", "agent", "cognitive"],
    },
    SignalCategory.TASK: {
        "implement": ["implement", "code", "build", "create", "write", "add"],
        "debug": ["debug", "fix", "error", "bug", "broken", "not working"],
        "plan": ["plan", "design", "architect", "structure", "organize"],
        "research": ["research", "find", "search", "learn", "investigate"],
        "review": ["review", "check", "verify", "validate", "test"],
        "completed": ["done", "finished", "completed", "works now", "it works", "fixed it", "shipped", "deployed", "pushed"],
    },
    SignalCategory.ENERGY: {
        # Human-state language (no clinical terms)
        "depleted": [
            "exhausted", "burnt out", "done for today", "can't anymore",
            "brain fried", "completely wiped", "running on empty"
        ],
        "low": [
            "tired", "sleepy", "drained", "low energy", "not feeling it",
            "slow today", "foggy", "scattered"
        ],
        "high": [
            "let's go", "ready", "feeling good", "energized", "sharp",
            "on it", "got this"
        ],
        "taking_break": ["taking a break", "be right back", "brb", "quick break"],
    }
}

# Protection signal severity (higher = more concerning)
PROTECTION_SEVERITY = {
    "overuse": 0.7,      # Pushing past limits
    "needs_break": 0.3,  # Normal, healthy request
    "override": 0.5,     # User asserting control
    "hyperfocus": 0.6,   # Can be productive but risky
}

# Severity weights for emotional signals
EMOTIONAL_SEVERITY = {
    "frustrated": 0.6,
    "overwhelmed": 0.8,
    "stuck": 0.5,
    "anxious": 0.7,
    "angry": 0.9,  # Highest severity
}

# PRISM perspectives for multi-angle analysis
PRISM_PERSPECTIVES = [
    "causal",       # Cause-effect relationships
    "optimization", # Efficiency improvements
    "hierarchical", # Structure/layers
    "temporal",     # Time-based patterns
    "risk",         # Potential problems
    "opportunity"   # Potential benefits
]


# =============================================================================
# Signal Detection Result
# =============================================================================

@dataclass
class SignalVector:
    """
    Detected signals organized by category.

    Maintains FIXED structure for deterministic processing.
    """
    emotional: Dict[str, float] = field(default_factory=dict)
    protection: Dict[str, float] = field(default_factory=dict)  # OTTO protection signals
    mode: Dict[str, float] = field(default_factory=dict)
    domain: Dict[str, float] = field(default_factory=dict)
    task: Dict[str, float] = field(default_factory=dict)
    energy: Dict[str, float] = field(default_factory=dict)

    # Aggregate scores
    emotional_score: float = 0.0
    protection_score: float = 0.0  # OTTO: aggregate protection concern
    mode_detected: Optional[str] = None
    primary_domain: Optional[str] = None
    primary_task: Optional[str] = None
    energy_state: Optional[str] = None
    protection_signal: Optional[str] = None  # OTTO: primary protection signal

    # PRISM perspectives
    perspectives: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    input_hash: str = ""
    signals_detected: int = 0

    def get_priority_signal(self) -> Tuple[SignalCategory, str, float]:
        """
        Get highest priority signal (emotional > protection > mode > domain > task > energy).

        Returns:
            (category, signal_name, score) tuple
        """
        # Check in FIXED priority order
        if self.emotional and max(self.emotional.values()) > 0:
            top_emotional = max(self.emotional.items(), key=lambda x: x[1])
            return (SignalCategory.EMOTIONAL, top_emotional[0], top_emotional[1])

        # OTTO: Protection signals are second priority
        if self.protection_signal and self.protection_score > 0.3:
            return (SignalCategory.PROTECTION, self.protection_signal, self.protection_score)

        if self.mode_detected:
            score = self.mode.get(self.mode_detected, 0.5)
            return (SignalCategory.MODE, self.mode_detected, score)

        if self.primary_domain:
            score = self.domain.get(self.primary_domain, 0.5)
            return (SignalCategory.DOMAIN, self.primary_domain, score)

        if self.primary_task:
            score = self.task.get(self.primary_task, 0.5)
            return (SignalCategory.TASK, self.primary_task, score)

        if self.energy_state:
            score = self.energy.get(self.energy_state, 0.5)
            return (SignalCategory.ENERGY, self.energy_state, score)

        # Default to focused task execution
        return (SignalCategory.TASK, "implement", 0.1)

    def requires_intervention(self) -> bool:
        """Check if emotional state requires safety intervention."""
        return self.emotional_score >= 0.5

    def requires_protection(self) -> bool:
        """
        Check if protection signals indicate user needs support.

        OTTO-specific: detects overuse patterns or hyperfocus.
        """
        return (
            self.protection_score >= 0.5 or
            self.protection.get("overuse", 0) > 0.3 or
            self.protection.get("hyperfocus", 0) > 0.5
        )

    def user_wants_break(self) -> bool:
        """Check if user explicitly wants a break."""
        return self.protection.get("needs_break", 0) > 0

    def user_overriding(self) -> bool:
        """Check if user is explicitly overriding protection."""
        return self.protection.get("override", 0) > 0.3

    def task_completed(self) -> bool:
        """
        Check if task completion signals are present.

        Used by Celebrator expert to trigger dopamine acknowledgment.
        """
        return self.task.get("completed", 0) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "emotional": self.emotional,
            "protection": self.protection,
            "mode": self.mode,
            "domain": self.domain,
            "task": self.task,
            "energy": self.energy,
            "emotional_score": self.emotional_score,
            "protection_score": self.protection_score,
            "mode_detected": self.mode_detected,
            "primary_domain": self.primary_domain,
            "primary_task": self.primary_task,
            "energy_state": self.energy_state,
            "protection_signal": self.protection_signal,
            "perspectives": self.perspectives,
            "input_hash": self.input_hash,
            "signals_detected": self.signals_detected,
            "priority_signal": {
                "category": self.get_priority_signal()[0].name,
                "signal": self.get_priority_signal()[1],
                "score": self.get_priority_signal()[2]
            }
        }


# =============================================================================
# PRISM Signal Detector
# =============================================================================

class PRISMDetector:
    """
    Multi-perspective signal detector with FIXED evaluation order.

    Implements the PRISM framework for 6-perspective analysis while
    maintaining ThinkingMachines [He2025] batch-invariance.
    """

    # FIXED evaluation order - NEVER change
    SIGNAL_PRIORITY = [
        SignalCategory.EMOTIONAL,
        SignalCategory.PROTECTION,  # OTTO: protection signals second priority
        SignalCategory.MODE,
        SignalCategory.DOMAIN,
        SignalCategory.TASK,
        SignalCategory.ENERGY
    ]

    def __init__(self, custom_patterns: Dict[SignalCategory, Dict[str, List[str]]] = None):
        """
        Initialize detector with optional custom patterns.

        Args:
            custom_patterns: Additional patterns to merge with defaults
        """
        self.patterns = SIGNAL_PATTERNS.copy()
        if custom_patterns:
            for category, signals in custom_patterns.items():
                if category in self.patterns:
                    self.patterns[category].update(signals)
                else:
                    self.patterns[category] = signals

        # Pre-compile regex patterns for performance
        self._compiled_patterns: Dict[SignalCategory, Dict[str, re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for all signals."""
        for category in self.SIGNAL_PRIORITY:
            self._compiled_patterns[category] = {}
            for signal_name, keywords in self.patterns.get(category, {}).items():
                # Build case-insensitive pattern
                pattern = r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b'
                self._compiled_patterns[category][signal_name] = re.compile(
                    pattern, re.IGNORECASE
                )

    def detect(self, text: str, context: Dict[str, Any] = None) -> SignalVector:
        """
        Detect signals in text using FIXED evaluation order.

        ThinkingMachines compliance:
        - Evaluation order is FIXED (SIGNAL_PRIORITY)
        - Same input always produces same output
        - No dynamic algorithm switching

        Args:
            text: Input text to analyze
            context: Optional context (e.g., active domain)

        Returns:
            SignalVector with detected signals
        """
        context = context or {}
        text_lower = text.lower()
        input_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        result = SignalVector(input_hash=input_hash)
        signals_count = 0

        # Evaluate in FIXED order
        for category in self.SIGNAL_PRIORITY:
            category_results = self._detect_category(text_lower, category)
            signals_count += len([v for v in category_results.values() if v > 0])

            if category == SignalCategory.EMOTIONAL:
                result.emotional = category_results
                result.emotional_score = self._calculate_emotional_score(category_results)

            elif category == SignalCategory.PROTECTION:
                result.protection = category_results
                result.protection_score = self._calculate_protection_score(category_results)
                result.protection_signal = self._get_primary(category_results)

            elif category == SignalCategory.MODE:
                result.mode = category_results
                result.mode_detected = self._get_primary(category_results)

            elif category == SignalCategory.DOMAIN:
                result.domain = category_results
                result.primary_domain = self._get_primary(category_results)
                # Override with context if provided
                if context.get("active_domain"):
                    result.primary_domain = context["active_domain"]

            elif category == SignalCategory.TASK:
                result.task = category_results
                result.primary_task = self._get_primary(category_results)

            elif category == SignalCategory.ENERGY:
                result.energy = category_results
                result.energy_state = self._get_primary(category_results)

        result.signals_detected = signals_count

        # Apply PRISM perspectives
        result.perspectives = self._apply_perspectives(text, result)

        logger.debug(f"PRISM detected {signals_count} signals in input {input_hash}")
        return result

    def _detect_category(self, text: str, category: SignalCategory) -> Dict[str, float]:
        """
        Detect signals for a single category.

        Returns:
            Dict mapping signal names to detection scores (0-1)
        """
        results = {}
        patterns = self._compiled_patterns.get(category, {})

        for signal_name, pattern in patterns.items():
            matches = pattern.findall(text)
            if matches:
                # Score based on match count (normalized)
                score = min(len(matches) / 3.0, 1.0)  # Cap at 3 mentions = 1.0
                results[signal_name] = score

        return results

    def _calculate_emotional_score(self, emotional_signals: Dict[str, float]) -> float:
        """
        Calculate aggregate emotional score with severity weighting.

        Higher severity emotions (angry, overwhelmed) weight more heavily.
        """
        if not emotional_signals:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0

        for signal, score in emotional_signals.items():
            severity = EMOTIONAL_SEVERITY.get(signal, 0.5)
            weighted_sum += score * severity
            weight_total += severity

        if weight_total == 0:
            return 0.0

        return min(weighted_sum / weight_total, 1.0)

    def _calculate_protection_score(self, protection_signals: Dict[str, float]) -> float:
        """
        Calculate aggregate protection score with severity weighting.

        OTTO-specific: weighs signals by how concerning they are for user wellbeing.
        """
        if not protection_signals:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0

        for signal, score in protection_signals.items():
            severity = PROTECTION_SEVERITY.get(signal, 0.5)
            weighted_sum += score * severity
            weight_total += severity

        if weight_total == 0:
            return 0.0

        return min(weighted_sum / weight_total, 1.0)

    def _get_primary(self, signals: Dict[str, float]) -> Optional[str]:
        """Get primary signal (highest score) from dict."""
        if not signals:
            return None
        return max(signals.items(), key=lambda x: x[1])[0]

    def _apply_perspectives(self, text: str, signals: SignalVector) -> Dict[str, Any]:
        """
        Apply PRISM 6-perspective analysis.

        Each perspective provides a different lens on the input.
        """
        perspectives = {}

        # Causal perspective - look for cause-effect language
        causal_patterns = ["because", "therefore", "causes", "leads to", "results in"]
        perspectives["causal"] = {
            "relevant": any(p in text.lower() for p in causal_patterns),
            "indicators": [p for p in causal_patterns if p in text.lower()]
        }

        # Optimization perspective - look for improvement language
        opt_patterns = ["faster", "better", "improve", "optimize", "efficient"]
        perspectives["optimization"] = {
            "relevant": any(p in text.lower() for p in opt_patterns),
            "indicators": [p for p in opt_patterns if p in text.lower()]
        }

        # Hierarchical perspective - look for structure language
        hier_patterns = ["layer", "level", "parent", "child", "contains", "part of"]
        perspectives["hierarchical"] = {
            "relevant": any(p in text.lower() for p in hier_patterns),
            "indicators": [p for p in hier_patterns if p in text.lower()]
        }

        # Temporal perspective - look for time language
        temp_patterns = ["before", "after", "when", "then", "first", "next", "finally"]
        perspectives["temporal"] = {
            "relevant": any(p in text.lower() for p in temp_patterns),
            "indicators": [p for p in temp_patterns if p in text.lower()]
        }

        # Risk perspective - look for problem language
        risk_patterns = ["risk", "danger", "problem", "issue", "warning", "fail"]
        perspectives["risk"] = {
            "relevant": any(p in text.lower() for p in risk_patterns) or signals.requires_intervention(),
            "indicators": [p for p in risk_patterns if p in text.lower()],
            "emotional_risk": signals.requires_intervention()
        }

        # Opportunity perspective - look for potential language
        opp_patterns = ["could", "might", "opportunity", "potential", "possible"]
        perspectives["opportunity"] = {
            "relevant": any(p in text.lower() for p in opp_patterns),
            "indicators": [p for p in opp_patterns if p in text.lower()]
        }

        return perspectives

    def detect_caps_anger(self, text: str) -> bool:
        """
        Detect ALL CAPS as anger signal.

        Per CLAUDE.md: "caps|negative → Validator (empathy first)"
        """
        # Find words that are 3+ chars and all caps
        words = text.split()
        caps_words = [w for w in words if len(w) >= 3 and w.isupper() and w.isalpha()]
        # If more than 2 caps words, likely frustrated
        return len(caps_words) >= 2

    def quick_safety_check(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Quick safety check for immediate intervention signals.

        Returns:
            (requires_intervention, reason)
        """
        text_lower = text.lower()

        # Check for caps anger
        if self.detect_caps_anger(text):
            return (True, "caps_detected")

        # Check for high-severity emotional signals
        for signal, keywords in SIGNAL_PATTERNS[SignalCategory.EMOTIONAL].items():
            severity = EMOTIONAL_SEVERITY.get(signal, 0.5)
            if severity >= 0.8:  # High severity
                if any(kw in text_lower for kw in keywords):
                    return (True, f"high_severity_{signal}")

        # Check for energy depletion
        for keyword in SIGNAL_PATTERNS[SignalCategory.ENERGY].get("depleted", []):
            if keyword in text_lower:
                return (True, "energy_depleted")

        return (False, None)


# =============================================================================
# Factory Functions
# =============================================================================

def create_detector(domain_keywords: Dict[str, List[str]] = None) -> PRISMDetector:
    """
    Create a PRISMDetector with optional domain-specific keywords.

    Args:
        domain_keywords: Additional domain keywords to add

    Returns:
        Configured PRISMDetector
    """
    custom_patterns = None
    if domain_keywords:
        custom_patterns = {
            SignalCategory.DOMAIN: domain_keywords
        }
    return PRISMDetector(custom_patterns=custom_patterns)


__all__ = [
    'SignalCategory', 'SignalVector', 'PRISMDetector',
    'SIGNAL_PATTERNS', 'PRISM_PERSPECTIVES', 'PROTECTION_SEVERITY',
    'create_detector'
]
