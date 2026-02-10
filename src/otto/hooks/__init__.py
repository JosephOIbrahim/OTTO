"""
Orchestra Hooks Module
======================

Claude Code hook integration for the cognitive engine with Pheromone Trail support.

Usage:
    python -m orchestra.hooks < input.json

This module processes UserPromptSubmit events through the 5-Phase NEXUS Pipeline
and returns execution anchors for deterministic behavior.

Components:
    - Cognitive Hook: NEXUS pipeline processing
    - Protocol Hook: JSON-RPC request handling
    - Hook Base: Abstract base classes for custom hooks
    - Auto-Validate: Determinism checking
    - Trail Context: Trail-based context injection

Determinism:
- Same message -> same signals -> same routing -> same params
- Deterministic execution anchor
- FIXED evaluation order (5 phases)
- FIXED priority order (experts, signals)
- Hooks execute in deterministic priority order
"""

# Existing cognitive hooks
from .cognitive_hook import process_message, main
from .protocol_hook import (
    process_input as process_protocol_input,
    main as protocol_main,
    is_jsonrpc_request,
)

# New hook base classes
from .base import (
    HookEvent,
    HookContext,
    HookResult,
    Hook,
    HookRegistry,
    get_registry,
    register_hook,
    execute_hooks,
)

# Trail-based hooks
from .auto_validate import (
    AutoValidateHook,
    check_determinism_patterns,
    check_he2025_compliance,  # backward-compat alias
    validate_file,
)
from .trail_context import (
    TrailContextHook,
    WorkTrailHook,
)


def setup_default_hooks():
    """Register the default set of hooks."""
    registry = get_registry()

    # Register trail-based hooks
    registry.register(AutoValidateHook())
    registry.register(TrailContextHook())
    registry.register(WorkTrailHook())


__all__ = [
    # Cognitive hook (existing)
    'process_message',
    'main',
    # Protocol hook
    'process_protocol_input',
    'protocol_main',
    'is_jsonrpc_request',
    # Hook base classes
    'HookEvent',
    'HookContext',
    'HookResult',
    'Hook',
    'HookRegistry',
    'get_registry',
    'register_hook',
    'execute_hooks',
    # Validation hook
    'AutoValidateHook',
    'check_determinism_patterns',
    'check_he2025_compliance',  # backward-compat alias
    'validate_file',
    # Trail context hooks
    'TrailContextHook',
    'WorkTrailHook',
    # Setup
    'setup_default_hooks',
]
