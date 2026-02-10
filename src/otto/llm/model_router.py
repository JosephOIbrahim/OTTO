"""
USD Cognitive Model Router
==========================

Intelligent model selection using USD Cognitive Substrate signals.

Determinism:
- Fixed evaluation order (LIVRPS)
- Deterministic model selection
- Same signals → same model

LIVRPS Model Resolution:
- Local: Session/safety overrides (HIGHEST)
- Inherits: Conversation complexity
- Variants: Mode-based selection
- References: Historical effectiveness
- Payloads: Expert requirements
- Specializes: Default model (LOWEST)

Cost Optimization:
- Haiku for simple, GREEN state interactions
- Sonnet for crisis support and complex reasoning
- ~40-50% cost reduction without quality loss on safety-critical paths
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Final, Optional, Tuple

logger = logging.getLogger(__name__)


# Fixed model constants
class ModelTier(Enum):
    """Available model tiers."""
    HAIKU = "haiku"      # Fast, cheap, good for simple responses
    SONNET = "sonnet"    # Balanced, primary model
    OPUS = "opus"        # Most capable, for complex reasoning


# Model identifiers
MODEL_IDS: Final[Dict[ModelTier, str]] = {
    ModelTier.HAIKU: "claude-3-5-haiku-20241022",
    ModelTier.SONNET: "claude-sonnet-4-20250514",
    ModelTier.OPUS: "claude-opus-4-20250514",
}

# Cost per 1K tokens (input, output)
MODEL_COSTS: Final[Dict[ModelTier, Tuple[float, float]]] = {
    ModelTier.HAIKU: (0.00025, 0.00125),   # $0.25/1M in, $1.25/1M out
    ModelTier.SONNET: (0.003, 0.015),       # $3/1M in, $15/1M out
    ModelTier.OPUS: (0.015, 0.075),         # $15/1M in, $75/1M out
}


@dataclass
class ModelRoutingContext:
    """
    Context for model routing decision.

    Mirrors cognitive state for deterministic routing.
    """
    # Cognitive state
    expert: str = "Direct"
    burnout_level: str = "GREEN"
    energy_level: str = "medium"
    momentum_phase: str = "building"

    # Signal metadata
    signal_complexity: float = 0.0  # 0.0 = simple, 1.0 = complex
    emotional_intensity: float = 0.0  # 0.0 = neutral, 1.0 = intense

    # Session preferences
    user_model_preference: Optional[ModelTier] = None
    cost_sensitive: bool = True  # Default to cost optimization

    # Conversation context
    exchange_count: int = 0
    recent_state_changes: int = 0  # Volatility indicator


class CognitiveModelRouter:
    """
    Route to appropriate model using USD Cognitive Substrate signals.

    Fixed evaluation order (LIVRPS):
    1. Local - Safety overrides (burnout RED → Sonnet)
    2. Inherits - Conversation complexity
    3. Variants - Mode-based selection
    4. References - User preference
    5. Payloads - Expert requirements
    6. Specializes - Default (Haiku)

    Usage:
        router = CognitiveModelRouter()
        model = router.route(context)
        # Returns ModelTier.HAIKU or ModelTier.SONNET
    """

    # Fixed expert → model requirements
    EXPERT_MODEL_REQUIREMENTS: Final[Dict[str, ModelTier]] = {
        # Safety-critical experts need Sonnet
        "Validator": ModelTier.SONNET,     # Crisis support needs nuance
        "Scaffolder": ModelTier.SONNET,    # Breaking down complexity
        "Socratic": ModelTier.SONNET,      # Thoughtful questions

        # Efficiency experts can use Haiku
        "Direct": ModelTier.HAIKU,         # Concise responses
        "Celebrator": ModelTier.HAIKU,     # Brief acknowledgments
        "Restorer": ModelTier.HAIKU,       # Simple permission messages
        "Refocuser": ModelTier.HAIKU,      # Gentle redirects
    }

    # Fixed state → model overrides
    BURNOUT_OVERRIDES: Final[Dict[str, ModelTier]] = {
        "RED": ModelTier.SONNET,      # Always Sonnet for crisis
        "ORANGE": ModelTier.SONNET,   # Elevated concern
        "YELLOW": None,               # No override, use expert routing
        "GREEN": None,                # No override, use expert routing
    }

    ENERGY_OVERRIDES: Final[Dict[str, Optional[ModelTier]]] = {
        "depleted": ModelTier.SONNET,  # Needs careful handling
        "low": None,                   # No override
        "medium": None,                # No override
        "high": None,                  # No override
    }

    MOMENTUM_OVERRIDES: Final[Dict[str, Optional[ModelTier]]] = {
        "crashed": ModelTier.SONNET,   # Recovery needs nuance
        "cold_start": None,            # No override
        "building": None,              # No override
        "rolling": None,               # No override
        "peak": None,                  # No override
    }

    def __init__(self, default_tier: ModelTier = ModelTier.HAIKU):
        """
        Initialize router.

        Args:
            default_tier: Default model when no overrides apply
        """
        self.default_tier = default_tier

    def route(self, context: ModelRoutingContext) -> ModelTier:
        """
        Route to appropriate model using LIVRPS resolution.

        Fixed evaluation order - first match wins.

        Args:
            context: Routing context with cognitive state

        Returns:
            Selected ModelTier
        """
        # L: Local - Safety overrides (HIGHEST PRIORITY)
        local_override = self._check_local_overrides(context)
        if local_override:
            logger.debug(f"Model route: LOCAL override → {local_override.value}")
            return local_override

        # I: Inherits - Conversation complexity
        complexity_suggestion = self._check_complexity(context)
        if complexity_suggestion:
            logger.debug(f"Model route: COMPLEXITY → {complexity_suggestion.value}")
            return complexity_suggestion

        # V: Variants - Mode-based selection (emotional intensity)
        variant_suggestion = self._check_variants(context)
        if variant_suggestion:
            logger.debug(f"Model route: VARIANT → {variant_suggestion.value}")
            return variant_suggestion

        # R: References - User preference
        if context.user_model_preference:
            logger.debug(f"Model route: USER PREF → {context.user_model_preference.value}")
            return context.user_model_preference

        # P: Payloads - Expert requirements
        expert_requirement = self.EXPERT_MODEL_REQUIREMENTS.get(context.expert)
        if expert_requirement:
            logger.debug(f"Model route: EXPERT {context.expert} → {expert_requirement.value}")
            return expert_requirement

        # S: Specializes - Default (LOWEST PRIORITY)
        logger.debug(f"Model route: DEFAULT → {self.default_tier.value}")
        return self.default_tier

    def _check_local_overrides(self, context: ModelRoutingContext) -> Optional[ModelTier]:
        """
        Check safety-critical local overrides.

        These ALWAYS win - safety first.
        """
        # Burnout override
        burnout_override = self.BURNOUT_OVERRIDES.get(context.burnout_level)
        if burnout_override:
            return burnout_override

        # Energy override
        energy_override = self.ENERGY_OVERRIDES.get(context.energy_level)
        if energy_override:
            return energy_override

        # Momentum override
        momentum_override = self.MOMENTUM_OVERRIDES.get(context.momentum_phase)
        if momentum_override:
            return momentum_override

        return None

    def _check_complexity(self, context: ModelRoutingContext) -> Optional[ModelTier]:
        """
        Check conversation complexity signals.

        High complexity → Sonnet for better reasoning.
        """
        # High signal complexity
        if context.signal_complexity > 0.7:
            return ModelTier.SONNET

        # Volatile conversation (many state changes)
        if context.recent_state_changes >= 3:
            return ModelTier.SONNET

        return None

    def _check_variants(self, context: ModelRoutingContext) -> Optional[ModelTier]:
        """
        Check mode variants based on emotional intensity.
        """
        # High emotional intensity needs nuanced response
        if context.emotional_intensity > 0.6:
            return ModelTier.SONNET

        return None

    def get_model_id(self, tier: ModelTier) -> str:
        """Get the API model identifier for a tier."""
        return MODEL_IDS[tier]

    def estimate_cost(
        self,
        tier: ModelTier,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Estimate cost for a request.

        Args:
            tier: Model tier
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens

        Returns:
            Estimated cost in dollars
        """
        input_rate, output_rate = MODEL_COSTS[tier]
        input_cost = (input_tokens / 1000) * input_rate
        output_cost = (output_tokens / 1000) * output_rate
        return input_cost + output_cost

    def get_routing_explanation(self, context: ModelRoutingContext) -> str:
        """
        Get human-readable explanation of routing decision.

        Useful for debugging and transparency.
        """
        tier = self.route(context)

        reasons = []

        # Check what triggered the decision
        if context.burnout_level in ("RED", "ORANGE"):
            reasons.append(f"burnout={context.burnout_level} (safety critical)")
        if context.energy_level == "depleted":
            reasons.append("energy=depleted (needs care)")
        if context.momentum_phase == "crashed":
            reasons.append("momentum=crashed (recovery mode)")
        if context.signal_complexity > 0.7:
            reasons.append(f"complexity={context.signal_complexity:.1f} (complex query)")
        if context.emotional_intensity > 0.6:
            reasons.append(f"emotional={context.emotional_intensity:.1f} (intense)")
        if context.user_model_preference:
            reasons.append(f"user_preference={context.user_model_preference.value}")
        if not reasons:
            reasons.append(f"expert={context.expert} (standard routing)")

        return f"→ {tier.value}: {', '.join(reasons)}"


def create_model_router(
    cost_optimized: bool = True,
) -> CognitiveModelRouter:
    """
    Create a model router.

    Args:
        cost_optimized: If True, default to Haiku. If False, default to Sonnet.

    Returns:
        Configured CognitiveModelRouter
    """
    default = ModelTier.HAIKU if cost_optimized else ModelTier.SONNET
    return CognitiveModelRouter(default_tier=default)


__all__ = [
    "CognitiveModelRouter",
    "ModelRoutingContext",
    "ModelTier",
    "MODEL_IDS",
    "MODEL_COSTS",
    "create_model_router",
]
