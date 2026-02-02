"""
OTTO OS Core Module
===================

Integration layer providing LIVRPS composition, cognitive state management,
and profile resolution.

[He2025] Compliance:
- All composition uses deterministic evaluation order
- Float comparisons use round(value, 6)
- Aggregations use Kahan summation with sorted input
- No runtime variation in routing logic

Components:
- LIVRPSResolver: USD-inspired composition semantics
- CognitiveStateManager: Extended state management with schema validation
- ProfileManager: Profile resolution with LIVRPS layering

Usage:
    from otto.core import get_state_manager, get_profile_manager

    state = get_state_manager()
    profile = get_profile_manager()
"""

from otto.core.livrps import (
    LIVRPSResolver,
    Layer,
    LayerType,
    CompositionResult,
)

from otto.core.state_manager import (
    CognitiveStateManager,
    get_state_manager,
    reset_state_manager,
    CognitiveState,
)

from otto.core.profile import (
    ProfileManager,
    get_profile_manager,
    reset_profile_manager,
    Profile,
    ProfileSource,
)

__all__ = [
    # LIVRPS
    "LIVRPSResolver",
    "Layer",
    "LayerType",
    "CompositionResult",
    # State Management
    "CognitiveStateManager",
    "get_state_manager",
    "reset_state_manager",
    "CognitiveState",
    # Profile
    "ProfileManager",
    "get_profile_manager",
    "reset_profile_manager",
    "Profile",
    "ProfileSource",
]
