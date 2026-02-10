"""otto_hooks.py -- Constitutional gating hooks for the OTTO Agent.

The constitutional layer sits ABOVE the tools. Before any nudge-related
tool executes, the hook checks the user's cognitive state and suppresses
the action if they're in RED burnout, ORANGE+depleted, or nudges aren't
helping.

This is the "manage the noise without falling into it" in code.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

_otto_src = str(Path(__file__).resolve().parent.parent / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

from otto.constitutional import should_suppress
from otto.state import CognitiveState

logger = logging.getLogger("otto.agent.hooks")

# Tools that the constitutional layer can gate
_GATED_TOOLS = frozenset({"otto_run_nudge"})


def constitutional_gate(
    tool_name: str,
    tool_input: dict,
    state: CognitiveState,
) -> dict[str, Any] | None:
    """Check if a tool call should be suppressed by the constitutional layer.

    Parameters
    ----------
    tool_name:
        Name of the tool being called.
    tool_input:
        The tool's input arguments.
    state:
        Current cognitive state snapshot.

    Returns
    -------
    dict | None
        A suppression result dict if the tool should be blocked,
        ``None`` if it should proceed.
    """
    if tool_name not in _GATED_TOOLS:
        return None

    # Map tool names to action types the constitutional layer understands
    action = "nudge" if tool_name == "otto_run_nudge" else tool_name

    result = should_suppress(state, action)

    if result is not None:
        logger.info(
            "Constitutional gate blocked %s: %s", tool_name, result.reason
        )
        return {
            "suppressed": True,
            "tool": tool_name,
            "reason": result.reason,
            "action": result.action,
        }

    return None


def format_suppression_result(suppression: dict) -> str:
    """Format a suppression into a tool result string for the agent."""
    reason = suppression["reason"]

    # Translate to warm, non-clinical language
    if "RED" in reason:
        message = (
            "OTTO is giving you space right now. Your commitments are safe "
            "and will be here when you're ready."
        )
    elif "ORANGE" in reason:
        message = (
            "You seem to be running low. OTTO is backing off on nudges "
            "to give you breathing room."
        )
    elif "effectiveness" in reason:
        message = (
            "The last few nudges haven't led to completions, so OTTO is "
            "pausing them. When you're ready, they'll be here."
        )
    else:
        message = f"Nudge suppressed: {reason}"

    return json.dumps({
        "suppressed": True,
        "message": message,
        "reason": reason,
    })
