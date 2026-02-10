"""
Interaction Surfaces
====================

Adapters for different interaction surfaces (CLI, desktop, voice, etc.).

Each surface implements the same interface but adapts to its specific
interaction paradigm.

Determinism:
- Fixed input normalization
- Deterministic output formatting
- Sorted iteration for context presentation
"""

from .base import (
    Surface,
    SurfaceType,
    SurfaceMessage,
    SurfaceResponse,
    MessageRole,
    RenderFormat,
    get_surface,
)

from .cli import (
    CLISurface,
    CLIConfig,
)

__all__ = [
    # Base
    "Surface",
    "SurfaceType",
    "SurfaceMessage",
    "SurfaceResponse",
    "MessageRole",
    "RenderFormat",
    "get_surface",
    # CLI
    "CLISurface",
    "CLIConfig",
]
