"""otto_tools.py -- Tool definitions for the OTTO Agent.

Each tool wraps an existing OTTO module (store, nudge, state).
The agent calls these via the Anthropic tool-use protocol.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add otto source to path so imports work standalone
_otto_src = str(Path(__file__).resolve().parent.parent / "src")
if _otto_src not in sys.path:
    sys.path.insert(0, _otto_src)

from otto.constitutional import should_suppress
from otto.models import Commitment
from otto.nudge import check_and_nudge
from otto.state import CognitiveState, StateStore
from otto.store import CommitmentStore

logger = logging.getLogger("otto.agent.tools")

# Shared store instances -- set during agent init
_store: CommitmentStore | None = None
_state_store: StateStore | None = None


def init_stores(
    store: CommitmentStore | None = None,
    state_store: StateStore | None = None,
) -> None:
    """Initialize shared store instances. Called once during agent startup."""
    global _store, _state_store
    _store = store
    _state_store = state_store


def get_store() -> CommitmentStore:
    if _store is None:
        raise RuntimeError("Store not initialized. Call init_stores() first.")
    return _store


def get_state_store() -> StateStore:
    if _state_store is None:
        raise RuntimeError("State store not initialized. Call init_stores() first.")
    return _state_store


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic API format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "otto_list_commitments",
        "description": (
            "List commitments. By default shows active commitments ordered by "
            "deadline. Use 'filter' to change: 'active' (default), 'due' "
            "(overdue only), or 'all' (including done/parked)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "enum": ["active", "due", "all"],
                    "description": "Which commitments to show (default: active).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "otto_add_commitment",
        "description": (
            "Add a new commitment. Requires the commitment text. "
            "Optionally specify who it's to and a deadline (YYYY-MM-DD)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The commitment text.",
                },
                "who_to": {
                    "type": "string",
                    "description": "Who the commitment is to (default: unknown).",
                },
                "deadline": {
                    "type": "string",
                    "description": "Deadline in YYYY-MM-DD format (optional).",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "otto_mark_done",
        "description": (
            "Mark a commitment as done. Takes the short numeric ID "
            "shown in otto_list_commitments output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "short_id": {
                    "type": "integer",
                    "description": "Short numeric ID from the commitment list.",
                },
            },
            "required": ["short_id"],
        },
    },
    {
        "name": "otto_park_commitment",
        "description": (
            "Park a commitment guilt-free. It won't generate nudges "
            "but stays in history. Takes the short numeric ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "short_id": {
                    "type": "integer",
                    "description": "Short numeric ID from the commitment list.",
                },
            },
            "required": ["short_id"],
        },
    },
    {
        "name": "otto_run_nudge",
        "description": (
            "Run the follow-up nudge check. Returns nudge messages for "
            "overdue and stale commitments. Constitutional gating may "
            "suppress this if you're in a depleted state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "otto_get_stats",
        "description": (
            "Show commitment statistics: active count, done count, "
            "parked count, and average follow-ups before completion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "otto_get_energy",
        "description": (
            "Get your current cognitive state: energy level, burnout, "
            "momentum, nudge counters, and suppression count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "otto_set_energy",
        "description": (
            "Set your energy level. Valid values: high, medium, low, depleted. "
            "This affects how OTTO behaves -- in depleted state, nudges are "
            "suppressed by the constitutional layer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["high", "medium", "low", "depleted"],
                    "description": "Your current energy level.",
                },
            },
            "required": ["level"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _build_id_map(commitments: list[Commitment]) -> dict[int, str]:
    """Map short sequential IDs (1-based) to UUIDs."""
    return {i + 1: c.id for i, c in enumerate(commitments)}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool by name. Returns JSON string result."""
    try:
        if tool_name == "otto_list_commitments":
            return _handle_list(tool_input)
        elif tool_name == "otto_add_commitment":
            return _handle_add(tool_input)
        elif tool_name == "otto_mark_done":
            return _handle_done(tool_input)
        elif tool_name == "otto_park_commitment":
            return _handle_park(tool_input)
        elif tool_name == "otto_run_nudge":
            return _handle_nudge(tool_input)
        elif tool_name == "otto_get_stats":
            return _handle_stats(tool_input)
        elif tool_name == "otto_get_energy":
            return _handle_get_energy(tool_input)
        elif tool_name == "otto_set_energy":
            return _handle_set_energy(tool_input)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        logger.exception("Tool %s failed", tool_name)
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_list(tool_input: dict) -> str:
    store = get_store()
    filter_type = tool_input.get("filter", "active")

    if filter_type == "due":
        commitments = store.get_due()
        label = "overdue"
    elif filter_type == "all":
        commitments = store.get_all()
        label = "all"
    else:
        commitments = store.get_active()
        label = "active"

    if not commitments:
        return json.dumps({"commitments": [], "label": label, "count": 0})

    id_map = _build_id_map(commitments)
    items = []
    for short_id, uuid in sorted(id_map.items()):
        c = next(cm for cm in commitments if cm.id == uuid)
        items.append({
            "short_id": short_id,
            "text": c.commitment_text,
            "who_to": c.who_to,
            "deadline": c.deadline.isoformat() if c.deadline else None,
            "status": c.status,
            "follow_up_count": c.follow_up_count,
            "source_chat": c.source_chat,
            "created_at": c.created_at.isoformat(),
        })

    return json.dumps({
        "commitments": items,
        "label": label,
        "count": len(items),
    }, indent=2)


def _handle_add(tool_input: dict) -> str:
    from datetime import datetime, timezone

    store = get_store()
    text = tool_input["text"]
    who_to = tool_input.get("who_to", "unknown")
    deadline_str = tool_input.get("deadline")

    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return json.dumps({"error": "Bad date format. Use YYYY-MM-DD."})

    commitment = Commitment(
        raw_message=text,
        commitment_text=text,
        who_to=who_to,
        source_chat="agent",
        deadline=deadline,
        deadline_source="manual" if deadline else "none",
    )

    cid = store.add(commitment)
    return json.dumps({"added": True, "id": cid, "text": text})


def _handle_done(tool_input: dict) -> str:
    store = get_store()
    short_id = tool_input["short_id"]
    active = store.get_active()

    if not active:
        return json.dumps({"error": "No active commitments."})

    id_map = _build_id_map(active)
    uuid = id_map.get(short_id)

    if uuid is None:
        return json.dumps({
            "error": f"No commitment #{short_id}.",
            "hint": "Use otto_list_commitments to see current IDs.",
        })

    c = store.get(uuid)
    store.mark_done(uuid)

    # Track effectiveness
    state_store = get_state_store()
    state_store.increment_nudges_completed()

    return json.dumps({
        "done": True,
        "text": c.commitment_text,
    })


def _handle_park(tool_input: dict) -> str:
    store = get_store()
    short_id = tool_input["short_id"]
    active = store.get_active()

    if not active:
        return json.dumps({"error": "No active commitments."})

    id_map = _build_id_map(active)
    uuid = id_map.get(short_id)

    if uuid is None:
        return json.dumps({
            "error": f"No commitment #{short_id}.",
            "hint": "Use otto_list_commitments to see current IDs.",
        })

    c = store.get(uuid)
    store.mark_parked(uuid)
    return json.dumps({
        "parked": True,
        "text": c.commitment_text,
    })


def _handle_nudge(tool_input: dict) -> str:
    store = get_store()
    messages = check_and_nudge(store)

    # Track nudges sent
    if messages:
        state_store = get_state_store()
        for _ in messages:
            state_store.increment_nudges_sent()

    if not messages:
        return json.dumps({"nudges": [], "message": "Nothing to nudge about."})

    return json.dumps({"nudges": messages, "count": len(messages)})


def _handle_stats(tool_input: dict) -> str:
    store = get_store()
    counts = store.count()
    avg_raw = store.avg_follow_ups_done()

    return json.dumps({
        "active": counts.get("active", 0),
        "done": counts.get("done", 0),
        "parked": counts.get("parked", 0),
        "avg_follow_ups_before_done": round(avg_raw, 1) if avg_raw is not None else None,
    })


def _handle_get_energy(tool_input: dict) -> str:
    state_store = get_state_store()
    state = state_store.load()

    return json.dumps({
        "energy": state.energy,
        "burnout": state.burnout,
        "momentum": state.momentum,
        "nudges_sent_today": state.nudges_sent_today,
        "nudges_completed_today": state.nudges_completed_today,
        "nudge_effectiveness": round(state.nudge_effectiveness, 2),
        "suppressed_count": state.suppressed_count,
        "should_suppress_nudge": state.should_suppress_nudge,
    })


def _handle_set_energy(tool_input: dict) -> str:
    state_store = get_state_store()
    level = tool_input["level"]

    try:
        state = state_store.set_energy(level)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    result = {"energy": level, "set": True}
    if level == "depleted":
        result["message"] = "OTTO will give you space. Your commitments are safe."
    elif level == "low":
        result["message"] = "OTTO will go easy. Only urgent things."

    return json.dumps(result)
