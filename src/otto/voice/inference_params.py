"""
State-Aware Inference Parameters.

Adjusts temperature, top_p, max_tokens based on:
- Cognitive state (focused, stuck, depleted, etc.)
- Register (casual, formal, venting)
- Expert mode (Validator, Direct, Socratic, etc.)

Determinism:
- All mappings are fixed dictionaries
- Calculations use deterministic arithmetic
- Same inputs always produce same outputs
"""
from dataclasses import dataclass, field
from typing import List, Optional

from .register import Register


@dataclass
class InferenceParams:
    """Parameters for LLM inference."""
    temperature: float = 0.5
    top_p: float = 0.9
    max_tokens: int = 1024
    stop_sequences: List[str] = field(default_factory=lambda: [
        "\n\nHuman:",
        "\n\nUser:",
    ])


# === State Configurations (FIXED mappings) ===

PARAMS_BY_STATE = {
    # Flow states - stay out of the way
    "focused": InferenceParams(temperature=0.3, top_p=0.85, max_tokens=256),
    "hyperfocused": InferenceParams(temperature=0.2, top_p=0.8, max_tokens=128),
    "rolling": InferenceParams(temperature=0.3, top_p=0.85, max_tokens=256),
    "peak": InferenceParams(temperature=0.2, top_p=0.8, max_tokens=128),

    # Exploring - more creative
    "exploring": InferenceParams(temperature=0.7, top_p=0.95, max_tokens=1500),
    "curious": InferenceParams(temperature=0.7, top_p=0.95, max_tokens=1500),

    # Struggling - helpful but not overwhelming
    "stuck": InferenceParams(temperature=0.5, top_p=0.9, max_tokens=512),
    "confused": InferenceParams(temperature=0.4, top_p=0.9, max_tokens=512),
    "overwhelmed": InferenceParams(temperature=0.3, top_p=0.85, max_tokens=200),

    # Emotional - warm and steady
    "frustrated": InferenceParams(temperature=0.4, top_p=0.9, max_tokens=256),
    "anxious": InferenceParams(temperature=0.4, top_p=0.9, max_tokens=200),
    "crashed": InferenceParams(temperature=0.4, top_p=0.9, max_tokens=150),
    "depleted": InferenceParams(temperature=0.4, top_p=0.9, max_tokens=150),

    # Building - supportive
    "building": InferenceParams(temperature=0.5, top_p=0.9, max_tokens=512),
    "cold_start": InferenceParams(temperature=0.5, top_p=0.9, max_tokens=384),

    # Default
    "default": InferenceParams(temperature=0.5, top_p=0.9, max_tokens=1024),
}

# === Register Adjustments (FIXED deltas) ===

REGISTER_ADJUSTMENTS = {
    Register.CASUAL: {
        "temperature_delta": +0.1,
        "max_tokens_multiplier": 0.7,
    },
    Register.FORMAL: {
        "temperature_delta": -0.1,
        "max_tokens_multiplier": 1.2,
    },
    Register.TERSE: {
        "temperature_delta": -0.2,
        "max_tokens_multiplier": 0.3,
    },
    Register.VENTING: {
        "temperature_delta": -0.1,
        "max_tokens_multiplier": 0.5,
    },
    Register.NEUTRAL: {
        "temperature_delta": 0.0,
        "max_tokens_multiplier": 1.0,
    },
}

# === Expert Overrides (FIXED caps/floors) ===

EXPERT_OVERRIDES = {
    "Validator": {"max_temp": 0.4, "max_tokens": 200},
    "Restorer": {"max_temp": 0.4, "max_tokens": 150},
    "Direct": {"max_temp": 0.3, "max_tokens": 150},
    "Scaffolder": {"max_temp": 0.4, "max_tokens": 300},
    "Socratic": {"min_temp": 0.6, "max_tokens": 1500},
    "Celebrator": {"max_temp": 0.5, "max_tokens": 100},
    "Refocuser": {"max_temp": 0.4, "max_tokens": 200},
}


def get_inference_params(
    detected_state: str,
    register: Register,
    expert: Optional[str] = None,
) -> InferenceParams:
    """
    Get inference parameters for context.

    Deterministic: same inputs always produce same outputs.

    Args:
        detected_state: Cognitive state (focused, stuck, etc.)
        register: Communication register
        expert: Active expert mode (optional)

    Returns:
        Tuned InferenceParams
    """
    # Base params from state
    base = PARAMS_BY_STATE.get(detected_state, PARAMS_BY_STATE["default"])

    # Apply register adjustment
    adjustment = REGISTER_ADJUSTMENTS.get(register, REGISTER_ADJUSTMENTS[Register.NEUTRAL])

    temperature = base.temperature + adjustment["temperature_delta"]
    temperature = round(max(0.1, min(1.0, temperature)), 2)

    max_tokens = int(base.max_tokens * adjustment["max_tokens_multiplier"])

    # Apply expert override
    if expert and expert in EXPERT_OVERRIDES:
        override = EXPERT_OVERRIDES[expert]

        if "max_temp" in override:
            temperature = min(temperature, override["max_temp"])
        if "min_temp" in override:
            temperature = max(temperature, override["min_temp"])
        if "max_tokens" in override:
            max_tokens = min(max_tokens, override["max_tokens"])

    return InferenceParams(
        temperature=temperature,
        top_p=base.top_p,
        max_tokens=max_tokens,
        stop_sequences=base.stop_sequences.copy(),
    )


__all__ = [
    'InferenceParams',
    'PARAMS_BY_STATE',
    'REGISTER_ADJUSTMENTS',
    'EXPERT_OVERRIDES',
    'get_inference_params',
]
