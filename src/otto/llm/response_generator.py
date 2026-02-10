"""
OTTO Response Generator
=======================

Generates responses using LLM provider with cognitive context.

Determinism:
- Fixed system prompts per expert
- Deterministic prompt construction
- Sorted context building
- Voice-aware inference parameters
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Final, List, Optional

from .provider import LLMProvider, LLMConfig, LLMResponse, Message
from .model_router import (
    CognitiveModelRouter,
    ModelRoutingContext,
    ModelTier,
    create_model_router,
)

# Effort controller (v3 API layer)
try:
    from otto_v3.api.effort import EffortController
    _effort_controller = EffortController()
except ImportError:
    _effort_controller = None

# Voice system integration
from ..voice import (
    detect_register,
    get_inference_params,
    get_voice_prompt,
    adapt_response,
    Register,
    InferenceParams,
)

# Atmosphere system integration
from ..atmosphere import (
    apply_atmosphere,
    AtmosphereContext,
)

logger = logging.getLogger(__name__)


# Fixed system prompts per expert
EXPERT_PROMPTS: Final[Dict[str, str]] = {
    "Validator": """You are OTTO, an empathetic AI assistant. The user appears frustrated or upset.

PRIORITY: Acknowledge their feelings first. Don't try to fix anything yet.

Guidelines:
- Start by validating their frustration ("I hear you", "That sounds frustrating")
- Don't minimize or dismiss their feelings
- Ask what's blocking them, but gently
- Keep response SHORT (2-3 sentences max)
- Only offer solutions if they ask""",

    "Scaffolder": """You are OTTO, a supportive AI assistant. The user seems overwhelmed or stuck.

PRIORITY: Break things down. Reduce cognitive load.

Guidelines:
- Acknowledge they're dealing with a lot
- Pick ONE thing to focus on
- Give a single, concrete next step
- Keep response SHORT (2-3 sentences)
- Don't list multiple options - decide for them""",

    "Restorer": """You are OTTO, a gentle AI assistant. The user seems depleted or tired.

PRIORITY: Permission to rest. Easy wins only.

Guidelines:
- Acknowledge their energy is low
- It's okay to stop or take a break
- If they want to continue, suggest the easiest possible task
- Keep response VERY SHORT (1-2 sentences)
- Don't push productivity""",

    "Celebrator": """You are OTTO, a supportive AI assistant. The user just accomplished something!

PRIORITY: Acknowledge the win. Build momentum.

Guidelines:
- Celebrate genuinely but briefly
- Note what they achieved
- Suggest what's next (optional)
- Keep response SHORT (2-3 sentences)
- Match their energy""",

    "Socratic": """You are OTTO, a curious AI assistant. The user is exploring ideas.

PRIORITY: Guide discovery. Follow their curiosity.

Guidelines:
- Ask thoughtful questions to deepen thinking
- Build on their ideas
- Connect related concepts
- Medium length response is okay
- Stay curious, not directive""",

    "Direct": """You are OTTO, an efficient AI assistant.

PRIORITY: Stay out of the way. Minimal friction.

Guidelines:
- Answer directly and concisely
- No unnecessary preamble or pleasantries
- Give them exactly what they asked for
- Keep response SHORT
- Don't comment on their energy, burnout, or emotional state unless they bring it up
- Don't make assumptions about how they're feeling
- Emojis sparingly - garnish, not main dish
- Just help with what they're asking""",
}

# Default prompt for unknown experts
DEFAULT_PROMPT: Final[str] = """You are OTTO, an adaptive AI assistant.

Guidelines:
- Be helpful and concise
- Match the user's energy
- Keep responses brief unless more detail is needed
- Emojis sparingly - garnish, not main dish"""


@dataclass
class ConversationTurn:
    """
    A single turn in a conversation.

    Fixed structure for deterministic serialization.
    """
    role: str  # "user" or "assistant"
    content: str

    def to_message(self) -> Message:
        """Convert to LLM Message format."""
        return Message(role=self.role, content=self.content)


@dataclass
class GenerationContext:
    """
    Context for response generation.

    Contains cognitive state, routing info, and conversation history.

    Determinism:
    - Conversation history in fixed order (oldest to newest)
    - Deterministic serialization
    """
    expert: str = "Direct"
    burnout_level: str = "GREEN"
    energy_level: str = "medium"
    momentum_phase: str = "building"
    mode: str = "focused"

    # Optional metadata
    platform: str = "discord"
    user_id: Optional[int] = None
    session_id: Optional[str] = None

    # Conversation history for multi-turn context
    # Ordered list: oldest first, newest last
    conversation_history: List[ConversationTurn] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Build context string for system prompt."""
        # Only mention state if it's notable (not default/normal)
        notes = []
        if self.burnout_level in ("YELLOW", "ORANGE", "RED"):
            notes.append(f"burnout level: {self.burnout_level}")
        if self.energy_level in ("low", "depleted"):
            notes.append(f"energy: {self.energy_level}")
        if self.momentum_phase in ("crashed", "cold_start"):
            notes.append(f"momentum: {self.momentum_phase}")

        if notes:
            return "Note: " + ", ".join(notes)
        return ""  # Don't add context if everything is normal


class ResponseGenerator:
    """
    Generates responses using LLM with cognitive context.

    Determinism:
    - Fixed prompt templates per expert
    - Deterministic context building
    - Provider-agnostic generation
    - LIVRPS-based model routing

    Usage:
        generator = ResponseGenerator(claude_provider)
        response = await generator.generate(
            message="I'm stuck on this bug",
            context=GenerationContext(expert="Scaffolder", burnout_level="YELLOW")
        )
    """

    def __init__(
        self,
        provider: LLMProvider,
        config: Optional[LLMConfig] = None,
        router: Optional[CognitiveModelRouter] = None,
    ):
        """
        Initialize response generator.

        Args:
            provider: LLM provider (Claude, OpenAI, etc.)
            config: Default generation config
            router: Model router for Haiku/Sonnet selection (creates default if None)
        """
        self.provider = provider
        self.default_config = config or LLMConfig(
            max_tokens=512,  # Keep responses concise
            temperature=0.7,
        )
        self.router = router or create_model_router(cost_optimized=True)

    async def generate(
        self,
        message: str,
        context: Optional[GenerationContext] = None,
        config: Optional[LLMConfig] = None,
    ) -> str:
        """
        Generate a response with voice awareness.

        Voice-aware generation pipeline:
        1. Detect register from user message
        2. Get voice-aware inference params (temperature, top_p, max_tokens)
        3. Build voice-enhanced system prompt
        4. Route to appropriate model
        5. Generate response
        6. Post-process through voice adapter

        Args:
            message: User's message
            context: Cognitive context (expert, state, etc.)
            config: Override generation config

        Returns:
            Generated and voice-adapted response text
        """
        ctx = context or GenerationContext()

        # =================================================================
        # STEP 1: Detect register from user message
        # =================================================================
        register, register_signals = detect_register(message)

        # =================================================================
        # STEP 2: Get voice-aware inference params
        # =================================================================
        # Map cognitive context to detected state for voice params
        detected_state = self._get_detected_state(ctx)
        voice_params = get_inference_params(detected_state, register, ctx.expert)

        # =================================================================
        # STEP 3: Build voice-enhanced system prompt
        # =================================================================
        voice_prompt = get_voice_prompt(register, ctx.expert)
        expert_prompt = self._build_system_prompt(ctx)
        system_prompt = f"{expert_prompt}\n\n{voice_prompt}"

        # =================================================================
        # STEP 4: Route to appropriate model
        # =================================================================
        routing_ctx = self._build_routing_context(ctx)
        model_tier = self.router.route(routing_ctx)
        model_id = self.router.get_model_id(model_tier)

        # Merge config: voice params override defaults, explicit config overrides voice
        cfg = config or self.default_config

        # Compute effort level from routing context
        effort_value = None
        if _effort_controller is not None:
            effort_level = _effort_controller.select_effort(
                primary_expert=ctx.expert,
                use_agent_team=False,
                signal_count=len(ctx.conversation_history) if ctx.conversation_history else 0,
            )
            effort_value = effort_level.value

        routed_config = LLMConfig(
            model=model_id,
            max_tokens=config.max_tokens if config else voice_params.max_tokens,
            temperature=config.temperature if config else voice_params.temperature,
            top_p=voice_params.top_p,
            stop_sequences=voice_params.stop_sequences,
            effort=effort_value,
        )

        # =================================================================
        # STEP 4b: Build conversation history
        # =================================================================
        messages = None
        if ctx.conversation_history:
            messages = [turn.to_message() for turn in ctx.conversation_history]
            logger.debug(f"Including {len(messages)} turns of conversation history")

        # =================================================================
        # STEP 5: Generate response
        # =================================================================
        try:
            response = await self.provider.generate(
                prompt=message,
                system=system_prompt,
                config=routed_config,
                messages=messages,
            )

            logger.info(
                f"Generated response: expert={ctx.expert}, "
                f"model={model_tier.value}, "
                f"register={register.value}, "
                f"temp={routed_config.temperature}, "
                f"tokens={response.total_tokens}, "
                f"provider={response.provider}"
            )

            # =================================================================
            # STEP 6: Post-process through voice adapter
            # =================================================================
            adapted_response = adapt_response(
                response.text,
                register,
                user_uses_emoji=register_signals.has_emoji,
            )

            # =================================================================
            # STEP 6b: Apply atmosphere (supportive language transformation)
            # =================================================================
            atmosphere_context = AtmosphereContext(
                user_message=message,
                register=register.value,
                expert=ctx.expert,
                energy_level=self._map_energy_level(ctx.energy_level),
                burnout_level=ctx.burnout_level,
                momentum_phase=ctx.momentum_phase,
            )
            final_response = apply_atmosphere(adapted_response, atmosphere_context)

            return final_response

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            # Return fallback response based on expert
            return self._get_fallback_response(ctx.expert)

    def _get_detected_state(self, ctx: GenerationContext) -> str:
        """
        Map GenerationContext to a detected state string for voice params.

        Deterministic mapping from context to state.
        """
        # Priority order for state detection
        if ctx.burnout_level == "RED":
            return "frustrated"
        if ctx.burnout_level == "ORANGE":
            return "depleted"
        if ctx.energy_level == "depleted":
            return "depleted"
        if ctx.energy_level == "low":
            return "crashed"
        if ctx.momentum_phase == "crashed":
            return "crashed"
        if ctx.momentum_phase == "peak":
            return "hyperfocused"
        if ctx.momentum_phase == "rolling":
            return "focused"
        if ctx.mode == "exploring":
            return "exploring"
        if ctx.mode == "focused":
            return "focused"

        return "default"

    def _build_routing_context(self, ctx: GenerationContext) -> ModelRoutingContext:
        """
        Build model routing context from generation context.

        Fixed mapping - same context → same routing.
        """
        return ModelRoutingContext(
            expert=ctx.expert,
            burnout_level=ctx.burnout_level,
            energy_level=ctx.energy_level,
            momentum_phase=ctx.momentum_phase,
            # These could be derived from message analysis in future
            signal_complexity=0.0,
            emotional_intensity=0.0,
            cost_sensitive=True,
        )

    def _build_system_prompt(self, context: GenerationContext) -> str:
        """
        Build system prompt for generation.

        Fixed prompt structure:
        1. Expert-specific base prompt
        2. User state context (only if notable)
        """
        # Get expert prompt
        base_prompt = EXPERT_PROMPTS.get(context.expert, DEFAULT_PROMPT)

        # Add state context only if there's something notable
        state_context = context.to_context_string()

        if state_context:
            return f"{base_prompt}\n\n{state_context}"
        return base_prompt

    def _map_energy_level(self, energy_level: str) -> str:
        """
        Map GenerationContext energy_level to atmosphere energy level.

        Fixed mapping for deterministic behavior.
        """
        # Direct mapping - atmosphere uses same terms
        # but we ensure valid values
        valid_levels = {"high", "medium", "low", "depleted", "hyperfocus"}
        if energy_level.lower() in valid_levels:
            return energy_level.lower()
        return "medium"  # Default

    def _get_fallback_response(self, expert: str) -> str:
        """Get fallback response when generation fails."""
        fallbacks = {
            "Validator": "I hear you. What's the main thing frustrating you right now?",
            "Scaffolder": "Let's focus on one thing. What's the smallest next step?",
            "Restorer": "It's okay to take a break. What feels manageable right now?",
            "Celebrator": "Nice work! What's next?",
            "Socratic": "That's interesting. What made you think of that?",
            "Direct": "How can I help?",
        }
        return fallbacks.get(expert, "How can I help you with this?")


def create_response_generator(
    provider: Optional[LLMProvider] = None,
    api_key: Optional[str] = None,
) -> ResponseGenerator:
    """
    Create a response generator with Claude provider.

    Args:
        provider: LLM provider (creates Claude if None)
        api_key: Anthropic API key (for Claude)

    Returns:
        Configured ResponseGenerator
    """
    if provider is None:
        from .claude_provider import create_claude_provider
        provider = create_claude_provider(api_key=api_key)

    return ResponseGenerator(provider)


__all__ = [
    "ResponseGenerator",
    "GenerationContext",
    "ConversationTurn",
    "create_response_generator",
    "EXPERT_PROMPTS",
    "DEFAULT_PROMPT",
]
