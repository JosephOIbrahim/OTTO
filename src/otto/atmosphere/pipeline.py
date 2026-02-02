"""
Atmosphere Pipeline for OTTO.

Full atmosphere transformation pipeline that integrates all modules.

Pipeline position: Step 6b in response_generator.py
- After voice adapter: Foundation transformations done
- Before return: Atmosphere adds final polish

[He2025] ThinkingMachines Compliance:
- Fixed transformation order (6 phases)
- Deterministic selection via seed
- Same inputs always produce same outputs
- Sorted expert bypass rules (deterministic)
"""

from dataclasses import dataclass, field
from typing import Dict, Final, FrozenSet, Optional, Set

from .patterns import transform_language, ATMOSPHERE_SEED
from .affirmations import maybe_get_affirmation, Affirmation
from .permissions import maybe_get_permission, Permission
from .reframes import detect_struggle, format_reframe, Reframe
from .energy import match_energy, get_energy_profile


# =============================================================================
# Expert Bypass Configuration
# =============================================================================

class TransformPhase:
    """Transformation phases that can be bypassed."""
    LANGUAGE = "language"        # Phase 1: Language transformation
    AFFIRMATION = "affirmation"  # Phase 2: Affirmations
    PERMISSION = "permission"    # Phase 3: Permissions
    REFRAME = "reframe"          # Phase 4: Reframes
    ENERGY = "energy"            # Phase 5: Energy matching
    CLEANUP = "cleanup"          # Phase 6: Final cleanup


# [He2025] Sorted expert bypass rules for deterministic matching
# Key = expert name, Value = set of phases to BYPASS (skip)
EXPERT_BYPASS_RULES: Final[Dict[str, FrozenSet[str]]] = {
    # Celebrator has its own celebratory tone - skip affirmations
    "Celebrator": frozenset({TransformPhase.AFFIRMATION}),

    # Direct expert - full atmosphere (no bypasses)
    "Direct": frozenset(),

    # Refocuser is redirecting - skip affirmations (not earning moment)
    "Refocuser": frozenset({TransformPhase.AFFIRMATION}),

    # Restorer handles recovery - keep all transformations
    "Restorer": frozenset(),

    # Scaffolder breaks down tasks - keep all transformations
    "Scaffolder": frozenset(),

    # Socratic guides discovery - skip reframes (questions are the point)
    "Socratic": frozenset({TransformPhase.REFRAME}),

    # Validator handles emotions directly - skip reframes and affirmations
    # (empathy first, not achievement recognition)
    "Validator": frozenset({TransformPhase.REFRAME, TransformPhase.AFFIRMATION}),
}

# Experts that should receive reframes (explicit allow-list for safety)
REFRAME_ALLOWED_EXPERTS: Final[FrozenSet[str]] = frozenset({
    "Direct", "Scaffolder", "Restorer"
})


@dataclass
class AtmosphereContext:
    """
    Context for atmosphere transformation.

    Contains user message, signals, and cognitive state.
    """
    user_message: str
    register: str = "neutral"           # casual, neutral, formal, terse, venting
    expert: str = "Direct"              # Expert routing decision
    energy_level: str = "medium"        # depleted, low, medium, high, hyperfocus
    burnout_level: str = "GREEN"        # GREEN, YELLOW, ORANGE, RED
    momentum_phase: str = "building"    # cold_start, building, rolling, peak, crashed

    # Computed signals (populated by pipeline)
    has_struggle: bool = False
    struggle_type: Optional[str] = None

    # Bypass configuration (can override default rules)
    custom_bypass: Optional[Set[str]] = None

    def should_bypass(self, phase: str) -> bool:
        """
        Check if a transformation phase should be bypassed.

        [He2025] Deterministic: uses sorted expert rules.

        Args:
            phase: The transformation phase to check

        Returns:
            True if phase should be skipped
        """
        # Custom bypass takes precedence
        if self.custom_bypass is not None:
            return phase in self.custom_bypass

        # Look up expert rules (default to empty = no bypass)
        bypass_rules = EXPERT_BYPASS_RULES.get(self.expert, frozenset())
        return phase in bypass_rules

    def get_active_bypasses(self) -> FrozenSet[str]:
        """
        Get all phases that will be bypassed.

        Returns:
            Set of phase names being bypassed
        """
        if self.custom_bypass is not None:
            return frozenset(self.custom_bypass)
        return EXPERT_BYPASS_RULES.get(self.expert, frozenset())


class AtmospherePipeline:
    """
    Transforms responses through the atmosphere pipeline.

    [He2025] Fixed transformation order (6 phases):
    1. transform_language() - Remove rigid/instructional
    2. match_energy() - Adjust length and tone
    3. maybe_add_affirmation() - If earned
    4. maybe_add_permission() - If needed
    5. maybe_add_reframe() - If struggle detected
    6. add_breathing_room() - Final cleanup

    Usage:
        pipeline = AtmospherePipeline()
        result = pipeline.apply(response, context)
    """

    def __init__(self, seed: int = ATMOSPHERE_SEED):
        """
        Initialize pipeline.

        Args:
            seed: Seed for deterministic selection
        """
        self.seed = seed

    def apply(self, response: str, context: AtmosphereContext) -> str:
        """
        Apply atmosphere transformations to response.

        [He2025] Fixed transformation order ensures determinism.
        Expert bypass rules are checked at each phase.

        Args:
            response: LLM response after voice adapter
            context: Atmosphere context with signals and state

        Returns:
            Transformed response with atmosphere applied
        """
        result = response

        # =====================================================================
        # Phase 1: Transform language (remove instructional patterns)
        # =====================================================================
        if not context.should_bypass(TransformPhase.LANGUAGE):
            result = transform_language(result, seed=self.seed)

        # =====================================================================
        # Phase 2: Maybe add affirmation (if earned)
        # =====================================================================
        if not context.should_bypass(TransformPhase.AFFIRMATION):
            result = self._maybe_add_affirmation(result, context)

        # =====================================================================
        # Phase 3: Maybe add permission (if needed)
        # =====================================================================
        if not context.should_bypass(TransformPhase.PERMISSION):
            result = self._maybe_add_permission(result, context)

        # =====================================================================
        # Phase 4: Maybe add reframe (if struggle detected)
        # =====================================================================
        if not context.should_bypass(TransformPhase.REFRAME):
            result = self._maybe_add_reframe(result, context)

        # =====================================================================
        # Phase 5: Match energy (adjust length and add breathing room)
        # This happens AFTER additions to enforce length limits
        # =====================================================================
        if not context.should_bypass(TransformPhase.ENERGY):
            result = match_energy(result, context.energy_level)

        # =====================================================================
        # Phase 6: Final cleanup (breathing room)
        # =====================================================================
        if not context.should_bypass(TransformPhase.CLEANUP):
            result = self._final_cleanup(result)

        return result

    def _maybe_add_affirmation(
        self,
        response: str,
        context: AtmosphereContext,
    ) -> str:
        """
        Add affirmation if earned.

        Affirmation goes at the START of response.
        """
        # Skip if venting (validator handles this differently)
        if context.register == "venting":
            return response

        affirmation = maybe_get_affirmation(
            user_message=context.user_message,
            momentum_phase=context.momentum_phase,
            energy_level=context.energy_level,
            seed=self.seed,
        )

        if affirmation is None:
            return response

        # Prepend affirmation
        return f"{affirmation.text} {response}"

    def _maybe_add_permission(
        self,
        response: str,
        context: AtmosphereContext,
    ) -> str:
        """
        Add permission if needed.

        Permission goes at the END of response.
        """
        permission = maybe_get_permission(
            user_message=context.user_message,
            burnout_level=context.burnout_level,
            energy_level=context.energy_level,
            momentum_phase=context.momentum_phase,
            seed=self.seed,
        )

        if permission is None:
            return response

        # Append permission
        return f"{response} {permission.text}"

    def _maybe_add_reframe(
        self,
        response: str,
        context: AtmosphereContext,
    ) -> str:
        """
        Add reframe if struggle detected.

        Reframe REPLACES the start of response (acknowledge before help).

        Note: Bypass check happens in apply(), but we also have an allow-list
        for safety (reframes are powerful, should be intentional).
        """
        # Additional safety: only allowed experts can add reframes
        if context.expert not in REFRAME_ALLOWED_EXPERTS:
            return response

        reframe = detect_struggle(context.user_message)
        if reframe is None:
            return response

        # Mark that we detected a struggle
        context.has_struggle = True
        context.struggle_type = reframe.struggle_pattern

        # Prepend the reframe acknowledgment/reframe
        reframe_text = format_reframe(reframe)
        return f"{reframe_text} {response}"

    def _final_cleanup(self, response: str) -> str:
        """
        Final cleanup pass.

        - Remove double spaces
        - Remove double periods
        - Strip whitespace
        """
        import re

        # Double spaces
        response = re.sub(r" {2,}", " ", response)

        # Double periods
        response = re.sub(r"\.{2,}", ".", response)

        # Space before punctuation
        response = re.sub(r" +([.,!?])", r"\1", response)

        return response.strip()


def apply_atmosphere(
    response: str,
    context: AtmosphereContext,
    seed: int = ATMOSPHERE_SEED,
) -> str:
    """
    Apply atmosphere transformation to response.

    Convenience function for one-off transformation.

    Args:
        response: LLM response after voice adapter
        context: Atmosphere context
        seed: Seed for deterministic selection

    Returns:
        Transformed response
    """
    pipeline = AtmospherePipeline(seed=seed)
    return pipeline.apply(response, context)


__all__ = [
    "AtmosphereContext",
    "AtmospherePipeline",
    "apply_atmosphere",
    "TransformPhase",
    "EXPERT_BYPASS_RULES",
    "REFRAME_ALLOWED_EXPERTS",
]
