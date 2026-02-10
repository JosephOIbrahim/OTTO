"""Opus 4.6 API integration layer.

Connects OTTO's cognitive architecture to the Anthropic Messages API.

Components:
    OTTOClient        — Anthropic SDK wrapper with lazy init
    EffortController  — Maps routing decisions to effort levels
    NEXUSPipeline     — Full detect → route → call pipeline
    CompactionManager — Token tracking and compaction triggering

What OTTO builds (application layer — patent-protected):
    - Expert routing via NEXUS (API calls merged with safety floors)
    - Effort selection based on cognitive state
    - System prompt generation from expert selection
    - Token-aware conversation compaction

What OTTO uses (Anthropic API features):
    - Effort controls (``effort`` parameter, GA)
    - Context compaction (beta)
    - 1M context window (beta)
    - 128k output tokens (GA)
"""

from otto.api.client import APIResponse, ModelConfig, OPUS_46_CONFIG, OTTOClient
from otto.api.compaction import (
    CompactionConfig,
    CompactionManager,
    CompactionStatus,
)
from otto.api.effort import CostEstimate, EffortController, EffortLevel
from otto.api.nexus import (
    EXPERT_VOICES,
    NEXUSPipeline,
    PipelineResult,
    build_system_prompt,
)

__all__ = [
    "APIResponse",
    "CompactionConfig",
    "CompactionManager",
    "CompactionStatus",
    "CostEstimate",
    "EffortController",
    "EffortLevel",
    "EXPERT_VOICES",
    "ModelConfig",
    "NEXUSPipeline",
    "OPUS_46_CONFIG",
    "OTTOClient",
    "PipelineResult",
    "build_system_prompt",
]
