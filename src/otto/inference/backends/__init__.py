"""
Inference Backends
==================

Abstract backend interface and concrete implementations for different
LLM inference providers.

Supported backends:
- Claude (Anthropic)
- OpenAI
- Local vLLM
- Local Ollama
- Mock (for testing)
"""

from .base import (
    InferenceBackend,
    BackendCapabilities,
    BackendStatus,
)
from .claude import ClaudeBackend
from .openai import OpenAIBackend
from .local import LocalVLLMBackend, LocalOllamaBackend
from .mock import MockBackend

__all__ = [
    'InferenceBackend',
    'BackendCapabilities',
    'BackendStatus',
    'ClaudeBackend',
    'OpenAIBackend',
    'LocalVLLMBackend',
    'LocalOllamaBackend',
    'MockBackend',
]
