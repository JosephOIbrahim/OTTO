"""
Human Render Layer
==================

Transforms cognitive state into dignity-first human language.

Core Principle: No clinical terms. Just human descriptions.
- Never: ADHD, disorder, symptom, manage, cope, dysfunction
- Always: stuck, scattered, depleted, frustrated, wiped, foggy
"""

from .human_render import (
    HumanRender,
    render_status,
    render_protection_message,
    render_welcome,
)

from .phrases import (
    FORBIDDEN_WORDS,
    STATE_PHRASES,
    PROTECTION_PHRASES,
    CELEBRATION_PHRASES,
)

__all__ = [
    'HumanRender',
    'render_status',
    'render_protection_message',
    'render_welcome',
    'FORBIDDEN_WORDS',
    'STATE_PHRASES',
    'PROTECTION_PHRASES',
    'CELEBRATION_PHRASES',
]
