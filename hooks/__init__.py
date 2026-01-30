"""
Orchestra Claude Code Hooks
===========================

Hooks that integrate Orchestra's cognitive state tracking with Claude Code.

Hook Types:
- SessionStart: Load/create cognitive stage, run calibration
- PreAssistantTurn: Inject cognitive context into prompt
- PostToolCall: Update state based on outcomes
- SessionEnd: Persist state, export session .usda

These hooks make Orchestra's cognitive tracking automatic and transparent.
"""

from .session_start import on_session_start, run_calibration
from .pre_assistant_turn import on_pre_assistant_turn, get_cognitive_context
from .post_tool_call import on_post_tool_call, update_state_from_tool
from .session_end import on_session_end, persist_and_export

__all__ = [
    # Session Start
    'on_session_start',
    'run_calibration',

    # Pre Assistant Turn
    'on_pre_assistant_turn',
    'get_cognitive_context',

    # Post Tool Call
    'on_post_tool_call',
    'update_state_from_tool',

    # Session End
    'on_session_end',
    'persist_and_export',
]
