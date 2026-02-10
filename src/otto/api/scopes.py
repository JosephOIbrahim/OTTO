"""
Permission Scopes for OTTO Public REST API
==========================================

Defines granular permission scopes for API key access control.

Scopes follow a hierarchical pattern:
- read:* - Read-only access
- write:* - Modification access
- admin - Full access

Sensitive fields (requiring read:state:full):
- burnout_level, energy_level, momentum_phase
- epistemic_tension, convergence_attractor
- rapid_exchange_count

Determinism:
- FIXED scope names and values
- DETERMINISTIC: scope → permission mapping
"""

from enum import Enum
from typing import Set, FrozenSet


class APIScope(Enum):
    """
    Permission scopes for API key access.

    Granular permissions enable fine-grained access control:
    - Separate read/write for each resource type
    - Special scope for sensitive cognitive state fields
    - Admin scope for full access
    """

    # Read-only scopes
    READ_STATUS = "read:status"           # Status, ping, methods
    READ_STATE = "read:state"             # State (filtered - no sensitive fields)
    READ_STATE_FULL = "read:state:full"   # State (all fields - sensitive)
    READ_AGENTS = "read:agents"           # Agent list/status
    READ_INTEGRATIONS = "read:integrations"  # Integration status

    # Write scopes
    WRITE_STATE = "write:state"           # Update cognitive state
    WRITE_SESSION = "write:session"       # Session lifecycle (start/end)
    WRITE_AGENTS = "write:agents"         # Spawn/abort agents

    # Admin scope (includes all permissions)
    ADMIN = "admin"


# =============================================================================
# Scope Hierarchy
# =============================================================================

# Scopes that ADMIN includes
ADMIN_INCLUDES: FrozenSet[APIScope] = frozenset([
    APIScope.READ_STATUS,
    APIScope.READ_STATE,
    APIScope.READ_STATE_FULL,
    APIScope.READ_AGENTS,
    APIScope.READ_INTEGRATIONS,
    APIScope.WRITE_STATE,
    APIScope.WRITE_SESSION,
    APIScope.WRITE_AGENTS,
])

# Scopes that READ_STATE_FULL includes
READ_STATE_FULL_INCLUDES: FrozenSet[APIScope] = frozenset([
    APIScope.READ_STATE,
])


# =============================================================================
# Sensitive Fields (require read:state:full)
# =============================================================================

SENSITIVE_FIELDS: FrozenSet[str] = frozenset([
    "burnout_level",
    "energy_level",
    "momentum_phase",
    "epistemic_tension",
    "convergence_attractor",
    "rapid_exchange_count",
    "hyperfocus_phase",
    "vulnerability_patterns",
    "crisis_events",
])


# =============================================================================
# Helper Functions
# =============================================================================

def expand_scopes(scopes: Set[APIScope]) -> Set[APIScope]:
    """
    Expand scope set to include implied scopes.

    Args:
        scopes: Set of explicitly granted scopes

    Returns:
        Expanded set including implied scopes

    Example:
        >>> expand_scopes({APIScope.ADMIN})
        {APIScope.ADMIN, APIScope.READ_STATUS, ...}  # All scopes
    """
    expanded = set(scopes)

    # ADMIN implies all other scopes
    if APIScope.ADMIN in expanded:
        expanded.update(ADMIN_INCLUDES)

    # READ_STATE_FULL implies READ_STATE
    if APIScope.READ_STATE_FULL in expanded:
        expanded.update(READ_STATE_FULL_INCLUDES)

    return expanded


def has_scope(granted: Set[APIScope], required: APIScope) -> bool:
    """
    Check if a required scope is covered by granted scopes.

    Args:
        granted: Set of scopes the API key has
        required: Scope required for the operation

    Returns:
        True if the required scope is granted (directly or via hierarchy)
    """
    expanded = expand_scopes(granted)
    return required in expanded


def can_access_field(scopes: Set[APIScope], field_name: str) -> bool:
    """
    Check if given scopes allow access to a state field.

    Args:
        scopes: Granted scopes
        field_name: Name of the state field

    Returns:
        True if access is allowed
    """
    expanded = expand_scopes(scopes)

    # Sensitive fields require READ_STATE_FULL or ADMIN
    if field_name in SENSITIVE_FIELDS:
        return APIScope.READ_STATE_FULL in expanded

    # Non-sensitive fields require READ_STATE or better
    return APIScope.READ_STATE in expanded or APIScope.READ_STATE_FULL in expanded


def filter_state_by_scope(state: dict, scopes: Set[APIScope]) -> dict:
    """
    Filter state dict based on scope permissions.

    Args:
        state: Full cognitive state dict
        scopes: Granted scopes

    Returns:
        Filtered state with only accessible fields
    """
    expanded = expand_scopes(scopes)

    # Full access with READ_STATE_FULL or ADMIN
    if APIScope.READ_STATE_FULL in expanded:
        return state

    # Filter out sensitive fields
    if APIScope.READ_STATE in expanded:
        return {
            k: v for k, v in state.items()
            if k not in SENSITIVE_FIELDS
        }

    # No state access
    return {}


def parse_scope(scope_str: str) -> APIScope:
    """
    Parse a scope string into APIScope enum.

    Args:
        scope_str: Scope string (e.g., "read:status")

    Returns:
        Corresponding APIScope

    Raises:
        ValueError: If scope string is invalid
    """
    for scope in APIScope:
        if scope.value == scope_str:
            return scope
    raise ValueError(f"Unknown scope: {scope_str}")


def parse_scopes(scope_strs: list[str]) -> Set[APIScope]:
    """
    Parse a list of scope strings into APIScope set.

    Args:
        scope_strs: List of scope strings

    Returns:
        Set of APIScope enums

    Raises:
        ValueError: If any scope string is invalid
    """
    return {parse_scope(s) for s in scope_strs}


__all__ = [
    "APIScope",
    "SENSITIVE_FIELDS",
    "expand_scopes",
    "has_scope",
    "can_access_field",
    "filter_state_by_scope",
    "parse_scope",
    "parse_scopes",
]
