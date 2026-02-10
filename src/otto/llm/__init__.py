"""
OTTO LLM Provider Layer
=======================

Swappable LLM backends for response generation.

Determinism:
- Fixed system prompts (deterministic instructions)
- Provider-agnostic interface
- Consistent context formatting
- LIVRPS model routing (Haiku/Sonnet selection)

Supported Providers:
- Claude (Anthropic) - Primary, best for cognitive support
- OpenAI - Alternative
- Ollama - Local/free option
- Groq - Fast/cheap option
"""

from .provider import LLMProvider, LLMResponse, LLMConfig
from .claude_provider import ClaudeProvider
from .response_generator import (
    ResponseGenerator,
    GenerationContext,
    create_response_generator,
)
from .model_router import (
    CognitiveModelRouter,
    ModelRoutingContext,
    ModelTier,
    MODEL_IDS,
    MODEL_COSTS,
    create_model_router,
)

__all__ = [
    # Provider
    "LLMProvider",
    "LLMResponse",
    "LLMConfig",
    "ClaudeProvider",
    # Generation
    "ResponseGenerator",
    "GenerationContext",
    "create_response_generator",
    # Model Routing
    "CognitiveModelRouter",
    "ModelRoutingContext",
    "ModelTier",
    "MODEL_IDS",
    "MODEL_COSTS",
    "create_model_router",
]
