"""
OTTO OS Input Abstraction Layer
================================

Platform-agnostic input handling for mobile builds.

Components:
- InputProvider: Abstract base for input handling
- SyncInputProvider: Synchronous input interface
- AsyncInputProvider: Asynchronous input interface
- MemoryInputProvider: In-memory provider for testing

[He2025] Compliance:
- Fixed provider selection order
- Deterministic input handling
- No runtime variation

Usage:
    from otto.input import get_input_provider, set_input_provider

    # Get current provider
    provider = get_input_provider()
    response = await provider.get_input("Enter your name: ")

    # Use specific provider for testing
    set_input_provider(MemoryInputProvider(responses=["test"]))
"""

from .provider import (
    InputProvider,
    InputType,
    InputChoice,
    InputResult,
    SyncInputProvider,
    AsyncInputProvider,
    MemoryInputProvider,
    get_input_provider,
    set_input_provider,
    reset_input_provider,
)

__all__ = [
    "InputProvider",
    "InputType",
    "InputChoice",
    "InputResult",
    "SyncInputProvider",
    "AsyncInputProvider",
    "MemoryInputProvider",
    "get_input_provider",
    "set_input_provider",
    "reset_input_provider",
]
