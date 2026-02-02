"""
OTTO Voice System.

Handles register detection, voice adaptation, and response shaping.

Components:
- register.py: Detect casual/formal/terse/venting communication style
- inference_params.py: State-aware temperature/top_p/max_tokens
- adapter.py: Post-process responses to strip robot speak
- prompts.py: System prompt injections for voice shaping

[He2025] ThinkingMachines Compliance:
- All pattern lists are sorted for deterministic iteration
- All classifications use fixed priority order
- Same inputs always produce same outputs
"""
from .register import (
    Register,
    RegisterSignals,
    detect_register,
    get_register,
)
from .inference_params import (
    InferenceParams,
    get_inference_params,
    PARAMS_BY_STATE,
    REGISTER_ADJUSTMENTS,
    EXPERT_OVERRIDES,
)
from .adapter import (
    VoiceAdapter,
    adapt_response,
)
from .prompts import (
    get_voice_prompt,
    BASE_VOICE_PROMPT,
    REGISTER_PROMPTS,
    EXPERT_VOICE_PROMPTS,
)

__all__ = [
    # Register
    "Register",
    "RegisterSignals",
    "detect_register",
    "get_register",

    # Inference
    "InferenceParams",
    "get_inference_params",
    "PARAMS_BY_STATE",
    "REGISTER_ADJUSTMENTS",
    "EXPERT_OVERRIDES",

    # Adapter
    "VoiceAdapter",
    "adapt_response",

    # Prompts
    "get_voice_prompt",
    "BASE_VOICE_PROMPT",
    "REGISTER_PROMPTS",
    "EXPERT_VOICE_PROMPTS",
]
