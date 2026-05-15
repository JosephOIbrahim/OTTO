"""Centralized Anthropic model IDs for OTTO.

One-line changes for future swaps. Each constant accepts an env var
override so model swaps require no code edit or redeploy.

NOT to be confused with otto.models (Commitment dataclass).
"""
from __future__ import annotations

import os

# Detector: nuance matters ("I'll try" vs "I will" -> confidence -> nudge
# timing). Opus 4.7 standard context; 1M variant deferred until few-shot
# history retrieval is wired.
DETECTOR_MODEL: str = os.environ.get("OTTO_DETECTOR_MODEL", "claude-opus-4-7")

# Agent: routine dispatch over 10 tools, max 15 turns. Sonnet 4.6 is the
# routine-loop sweet spot; Opus reasoning would leak into tool selection.
AGENT_MODEL: str = os.environ.get("OTTO_AGENT_MODEL", "claude-sonnet-4-6")

# Response rephrase: template touch-up only. Haiku 4.5 is the right tier;
# quality delta vs Sonnet is imperceptible on a 1-3 sentence rephrase.
RESPONSE_GEN_MODEL: str = os.environ.get(
    "OTTO_RESPONSE_GEN_MODEL", "claude-haiku-4-5-20251001"
)

# Shared determinism knob. Patent P1. Do not raise without constitutional review.
TEMPERATURE: float = 0.0
