"""Constitutional hooks for OTTO agents.

These hooks run BEFORE tool execution via the Agent SDK's PreToolUse
hook system. They enforce OTTO's constitutional principles:

1. Safety First -- suppress actions in RED burnout
2. Don't Become Noise -- back off when nudges aren't helping
3. Protector is NEVER suppressed -- safety mode always runs

The hook checks cognitive state from OTTO's StateStore and denies
tool execution when the constitutional layer says to suppress.
"""

from __future__ import annotations

import sys
from typing import Any

from claude_agent_sdk import HookContext

from ..config import OTTO_V4_SRC, get_default_db_path

# Add OTTO source to path
if OTTO_V4_SRC not in sys.path:
    sys.path.insert(0, OTTO_V4_SRC)

from otto.constitutional import should_suppress
from otto.state import StateStore


def _get_state_store() -> StateStore:
    return StateStore(db_path=get_default_db_path())


# Tools that trigger nudge-like output (gated by constitutional layer)
_NUDGE_TOOLS = frozenset({
    "mcp__otto__otto_nudge",
})

# Tools that are NEVER suppressed (safety-critical)
_UNSUPPRESSABLE_TOOLS = frozenset({
    "mcp__otto__otto_energy_get",
    "mcp__otto__otto_energy_set",
    "mcp__otto__otto_list",
    "mcp__otto__otto_stats",
    "mcp__otto__otto_done",
    "mcp__otto__otto_park",
    "mcp__otto__otto_snooze",
    "mcp__otto__otto_wip",
})


async def constitutional_gate(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """PreToolUse hook: constitutional gating for OTTO tools.

    Checks cognitive state and suppresses nudge-related tools when
    the user is in RED burnout, ORANGE+depleted, or nudges aren't
    leading to completions.

    Read-only and user-initiated tools (list, done, park, snooze,
    energy) are never suppressed -- the user should always be able
    to manage their own commitments.
    """
    tool_name = input_data.get("tool_name", "")

    # Never gate non-OTTO tools or safety-exempt tools
    if not tool_name.startswith("mcp__otto__"):
        return {}
    if tool_name in _UNSUPPRESSABLE_TOOLS:
        return {}

    # Check constitutional layer for nudge tools
    if tool_name in _NUDGE_TOOLS:
        state_store = _get_state_store()
        state = state_store.load()
        suppression = should_suppress(state, "nudge")

        if suppression is not None:
            state_store.increment_suppressed()
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Constitutional suppression: {suppression.reason}"
                    ),
                }
            }

    return {}


async def red_burnout_gate(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """PreToolUse hook: hard gate on ALL outbound actions in RED burnout.

    When burnout is RED, this hook denies ANY tool that generates
    outbound output (nudges, decomposition, redirection). Only
    passive tools (list, stats, energy) pass through.

    This is defense-in-depth on top of the constitutional_gate.
    """
    tool_name = input_data.get("tool_name", "")

    if not tool_name.startswith("mcp__otto__"):
        return {}
    if tool_name in _UNSUPPRESSABLE_TOOLS:
        return {}

    state_store = _get_state_store()
    state = state_store.load()

    if state.burnout == "RED":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Burnout is RED. OTTO is giving you space. "
                    "Your commitments are safe."
                ),
            }
        }

    return {}
