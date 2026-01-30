"""
Expert Router (Cognitive Safety MoE)
====================================

Routes incoming signals to intervention experts using FIXED priority,
first-match-wins semantics.

Expert Priority (from CLAUDE.md):
1. Validator   - frustrated, RED, caps, negative → empathy first
2. Scaffolder  - overwhelmed, stuck, too_many → break down, reduce scope
3. Restorer    - depleted, ORANGE, post-crash → easy wins, rest is OK
4. Refocuser   - distracted, tangent_over → gentle redirect
5. Celebrator  - task_complete, milestone → acknowledge win
6. Socratic    - exploring, high_energy, what if → guide discovery
7. Direct      - focused, hyperfocused, flow → stay out of way

ThinkingMachines [He2025] Compliance:
- FIXED expert priority (never reorder)
- First-match-wins (no backtracking)
- Deterministic routing (same signals → same expert)

Constitutional Principles:
- Safety first: Emotional safety before productivity
- User knows best: Their signal trumps our guess
"""

import hashlib
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum
import logging

from .prism_detector import SignalVector, SignalCategory
from .cognitive_state import BurnoutLevel, EnergyLevel, MomentumPhase

logger = logging.getLogger(__name__)


# =============================================================================
# Expert Definitions - FIXED Priority Order
# =============================================================================

class Expert(Enum):
    """Intervention experts in FIXED priority order."""
    VALIDATOR = "validator"      # 1 - Safety/emotional
    SCAFFOLDER = "scaffolder"    # 2 - Reducing overwhelm
    RESTORER = "restorer"        # 3 - Recovery
    REFOCUSER = "refocuser"      # 4 - Redirect
    CELEBRATOR = "celebrator"    # 5 - Win/dopamine
    SOCRATIC = "socratic"        # 6 - Exploration
    DIRECT = "direct"            # 7 - Minimal friction


# Expert trigger conditions (evaluated in FIXED order)
EXPERT_TRIGGERS = {
    Expert.VALIDATOR: {
        "emotional": ["frustrated", "angry", "overwhelmed"],
        "burnout": [BurnoutLevel.RED],
        "caps_detected": True,
        "description": "Empathy first, normalize struggle"
    },
    Expert.SCAFFOLDER: {
        "emotional": ["overwhelmed", "stuck"],
        "signals": ["too_many", "can't handle", "where do I start"],
        "description": "Break down, reduce scope, provide structure"
    },
    Expert.RESTORER: {
        "energy": [EnergyLevel.DEPLETED, EnergyLevel.LOW],
        "burnout": [BurnoutLevel.ORANGE],
        "momentum": [MomentumPhase.CRASHED],
        "description": "Easy wins, rest is OK, recovery mode"
    },
    Expert.REFOCUSER: {
        "signals": ["tangent", "off-topic", "anyway", "but also"],
        "tangent_budget_depleted": True,
        "description": "Gentle redirect to goal"
    },
    Expert.CELEBRATOR: {
        "signals": ["done", "finished", "completed", "works", "fixed"],
        "task_completed": True,
        "description": "Acknowledge win, dopamine boost"
    },
    Expert.SOCRATIC: {
        "mode": ["exploring", "teaching"],
        "signals": ["what if", "could we", "I wonder", "explore", "brainstorm"],
        "energy": [EnergyLevel.HIGH],
        "description": "Guide discovery, follow threads"
    },
    Expert.DIRECT: {
        "mode": ["focused"],
        "momentum": [MomentumPhase.ROLLING, MomentumPhase.PEAK],
        "burnout": [BurnoutLevel.GREEN],
        "description": "Stay out of way, minimal friction"
    }
}

# FIXED priority order - NEVER change this
EXPERT_PRIORITY = [
    Expert.VALIDATOR,
    Expert.SCAFFOLDER,
    Expert.RESTORER,
    Expert.REFOCUSER,
    Expert.CELEBRATOR,
    Expert.SOCRATIC,
    Expert.DIRECT
]


# =============================================================================
# Routing Result
# =============================================================================

@dataclass
class RoutingResult:
    """
    Result of expert routing.

    Contains the selected expert, trigger reason, and gate status.
    """
    expert: Expert
    trigger: str
    constitutional_pass: bool = True
    safety_gate_pass: bool = True
    safety_redirect: Optional[str] = None
    priority_index: int = 7  # 1-7, lower = higher priority

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for WebSocket."""
        return {
            "expert": self.expert.value,
            "trigger": self.trigger,
            "constitutional_pass": self.constitutional_pass,
            "safety_gate_pass": self.safety_gate_pass,
            "safety_redirect": self.safety_redirect,
            "priority_index": self.priority_index
        }


# =============================================================================
# Expert Router
# =============================================================================

class ExpertRouter:
    """
    Routes signals to intervention experts.

    Implements Cognitive Safety MoE from CLAUDE.md with:
    - FIXED priority order (1-7)
    - First-match-wins semantics
    - Safety gates for constitutional compliance
    - Deterministic routing (same inputs → same output)
    """

    def __init__(self):
        """Initialize router."""
        self._last_routing: Optional[RoutingResult] = None

    def route(
        self,
        signals: SignalVector,
        burnout: BurnoutLevel,
        energy: EnergyLevel,
        momentum: MomentumPhase,
        mode: str = "focused",
        tangent_budget: int = 5,
        task_completed: bool = False,
        caps_detected: bool = False
    ) -> RoutingResult:
        """
        Route to expert based on signals and state.

        ThinkingMachines [He2025]: Fixed evaluation order, first-match-wins.

        Args:
            signals: PRISM signal vector
            burnout: Current burnout level
            energy: Current energy level
            momentum: Current momentum phase
            mode: Current cognitive mode
            tangent_budget: Remaining tangent budget
            task_completed: Whether a task was just completed
            caps_detected: Whether ALL CAPS was detected

        Returns:
            RoutingResult with selected expert and reasoning
        """
        # =================================================================
        # GATE 1: Constitutional Check
        # =================================================================
        # Constitutional principles are NEVER violated
        constitutional_pass = self._check_constitutional(burnout, energy)

        # =================================================================
        # GATE 2: Safety Gate
        # =================================================================
        # Safety states force specific experts
        safety_result = self._check_safety_gate(burnout, energy, signals, caps_detected)

        if safety_result is not None:
            self._last_routing = safety_result
            logger.info(f"Safety gate → {safety_result.expert.value}: {safety_result.trigger}")
            return safety_result

        # =================================================================
        # GATE 3: Cognitive Safety MoE Routing (FIXED priority, first-match-wins)
        # =================================================================
        context = {
            "signals": signals,
            "burnout": burnout,
            "energy": energy,
            "momentum": momentum,
            "mode": mode,
            "tangent_budget": tangent_budget,
            "task_completed": task_completed,
            "caps_detected": caps_detected
        }

        # Evaluate in FIXED priority order
        for priority_idx, expert in enumerate(EXPERT_PRIORITY, start=1):
            trigger = self._check_expert_triggers(expert, context)
            if trigger:
                result = RoutingResult(
                    expert=expert,
                    trigger=trigger,
                    constitutional_pass=constitutional_pass,
                    safety_gate_pass=True,
                    priority_index=priority_idx
                )
                self._last_routing = result
                logger.info(f"CognitiveSafetyMoE → {expert.value} (priority {priority_idx}): {trigger}")
                return result

        # Default to Direct (should always match, but safety fallback)
        result = RoutingResult(
            expert=Expert.DIRECT,
            trigger="default_fallback",
            constitutional_pass=constitutional_pass,
            priority_index=7
        )
        self._last_routing = result
        return result

    def _check_constitutional(self, burnout: BurnoutLevel, energy: EnergyLevel) -> bool:
        """
        Check constitutional principles (safety floors).

        Constitutional principles from CLAUDE.md:
        1. Safety first: Emotional safety before productivity
        2. User knows best: Their signal trumps our guess
        3. Rest is productive: Recovery without guilt

        Returns:
            True if constitutional (always True - we enforce, not fail)
        """
        # We don't fail constitutional checks - we ENFORCE them via safety gate
        # This check is for logging/tracking
        return True

    def _check_safety_gate(
        self,
        burnout: BurnoutLevel,
        energy: EnergyLevel,
        signals: SignalVector,
        caps_detected: bool
    ) -> Optional[RoutingResult]:
        """
        Safety gate: Force specific experts for critical states.

        Per CLAUDE.md:
        - frustrated|RED|caps → Validator (empathy first, full stop)
        - overwhelmed|stuck → Scaffolder (break down, reduce scope)
        - depleted|ORANGE → Restorer (easy wins, rest is OK)

        Returns:
            RoutingResult if safety redirect needed, None otherwise
        """
        # RED burnout → Validator (full stop, empathy)
        if burnout == BurnoutLevel.RED:
            return RoutingResult(
                expert=Expert.VALIDATOR,
                trigger="RED_burnout",
                constitutional_pass=True,
                safety_gate_pass=False,
                safety_redirect="validator",
                priority_index=1
            )

        # ALL CAPS detected → Validator
        if caps_detected:
            return RoutingResult(
                expert=Expert.VALIDATOR,
                trigger="caps_detected",
                constitutional_pass=True,
                safety_gate_pass=False,
                safety_redirect="validator",
                priority_index=1
            )

        # High emotional score → Validator
        if signals.requires_intervention():
            return RoutingResult(
                expert=Expert.VALIDATOR,
                trigger=f"emotional_score_{signals.emotional_score:.2f}",
                constitutional_pass=True,
                safety_gate_pass=False,
                safety_redirect="validator",
                priority_index=1
            )

        # ORANGE burnout + low energy → Restorer
        if burnout == BurnoutLevel.ORANGE and energy in (EnergyLevel.LOW, EnergyLevel.DEPLETED):
            return RoutingResult(
                expert=Expert.RESTORER,
                trigger="ORANGE_burnout_low_energy",
                constitutional_pass=True,
                safety_gate_pass=False,
                safety_redirect="restorer",
                priority_index=3
            )

        # Depleted energy → Restorer
        if energy == EnergyLevel.DEPLETED:
            return RoutingResult(
                expert=Expert.RESTORER,
                trigger="energy_depleted",
                constitutional_pass=True,
                safety_gate_pass=False,
                safety_redirect="restorer",
                priority_index=3
            )

        return None

    def _check_expert_triggers(self, expert: Expert, context: Dict[str, Any]) -> Optional[str]:
        """
        Check if an expert's triggers match the current context.

        Returns:
            Trigger reason if matched, None otherwise
        """
        triggers = EXPERT_TRIGGERS.get(expert, {})
        signals = context["signals"]
        burnout = context["burnout"]
        energy = context["energy"]
        momentum = context["momentum"]
        mode = context["mode"]

        # Check emotional signals
        if "emotional" in triggers:
            for emotion in triggers["emotional"]:
                if signals.emotional.get(emotion, 0) > 0:
                    return f"emotional_{emotion}"

        # Check burnout levels
        if "burnout" in triggers:
            if burnout in triggers["burnout"]:
                return f"burnout_{burnout.value}"

        # Check energy levels
        if "energy" in triggers:
            if energy in triggers["energy"]:
                return f"energy_{energy.value}"

        # Check momentum phases
        if "momentum" in triggers:
            if momentum in triggers["momentum"]:
                return f"momentum_{momentum.value}"

        # Check mode
        if "mode" in triggers:
            if mode in triggers["mode"]:
                return f"mode_{mode}"

        # Check text signals (from SignalVector)
        if "signals" in triggers:
            # Check mode signals
            for sig in triggers["signals"]:
                if signals.mode.get(sig, 0) > 0:
                    return f"signal_{sig}"
                if signals.task.get(sig, 0) > 0:
                    return f"signal_{sig}"

        # Check caps
        if triggers.get("caps_detected") and context.get("caps_detected"):
            return "caps_detected"

        # Check tangent budget
        if triggers.get("tangent_budget_depleted") and context.get("tangent_budget", 5) <= 0:
            return "tangent_budget_depleted"

        # Check task completion
        if triggers.get("task_completed") and context.get("task_completed"):
            return "task_completed"

        return None

    def get_last_routing(self) -> Optional[RoutingResult]:
        """Get the last routing result."""
        return self._last_routing

    def get_expert_info(self, expert: Expert) -> Dict[str, Any]:
        """Get information about an expert."""
        triggers = EXPERT_TRIGGERS.get(expert, {})
        return {
            "name": expert.value,
            "priority": EXPERT_PRIORITY.index(expert) + 1,
            "description": triggers.get("description", ""),
            "triggers": {k: v for k, v in triggers.items() if k != "description"}
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_router() -> ExpertRouter:
    """Create an ExpertRouter instance."""
    return ExpertRouter()


__all__ = [
    'Expert', 'RoutingResult', 'ExpertRouter',
    'EXPERT_TRIGGERS', 'EXPERT_PRIORITY', 'create_router'
]
