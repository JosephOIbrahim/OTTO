"""MCP tools wrapping OTTO's commitment and cognitive state modules.

These tools use the @tool decorator from claude-agent-sdk to create
an in-process MCP server. The NEXUS agent calls these tools to manage
commitments, check cognitive state, and run nudges -- all gated by
the constitutional layer via hooks.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from ..config import OTTO_V4_SRC, get_default_db_path

# Add OTTO source to path so imports work
if OTTO_V4_SRC not in sys.path:
    sys.path.insert(0, OTTO_V4_SRC)

from otto.constitutional import should_suppress
from otto.models import Commitment, build_id_map, parse_duration
from otto.nudge import check_and_nudge
from otto.state import StateStore
from otto.store import CommitmentStore


def _json(obj: Any) -> str:
    """Serialize with sort_keys=True (He2025 compliance)."""
    return json.dumps(obj, sort_keys=True)


def _get_store(db_path: str | None = None) -> CommitmentStore:
    """Get or create a CommitmentStore."""
    if db_path:
        return CommitmentStore(db_path=db_path)
    return CommitmentStore()


def _get_state_store(db_path: str | None = None) -> StateStore:
    """Get or create a StateStore."""
    return StateStore(db_path=db_path or get_default_db_path())


# ---------------------------------------------------------------------------
# Commitment tools
# ---------------------------------------------------------------------------


@tool(
    "otto_list",
    "List commitments. Filter: 'active' (default), 'due' (overdue), 'all'.",
    {"filter": str},
)
async def otto_list(args: dict[str, Any]) -> dict[str, Any]:
    store = _get_store()
    filter_type = args.get("filter", "active")

    if filter_type == "due":
        commitments = store.get_due()
    elif filter_type == "all":
        commitments = store.get_all()
    else:
        commitments = store.get_active()

    if not commitments:
        return {"content": [{"type": "text", "text": _json({
            "commitments": [], "filter": filter_type, "count": 0,
        })}]}

    id_map = build_id_map(commitments)
    by_id = {c.id: c for c in commitments}
    items = []
    for short_id, uuid in sorted(id_map.items()):
        c = by_id[uuid]
        items.append({
            "short_id": short_id,
            "text": c.commitment_text,
            "who_to": c.who_to,
            "deadline": c.deadline.isoformat() if c.deadline else None,
            "status": c.status,
            "follow_up_count": c.follow_up_count,
            "created_at": c.created_at.isoformat(),
        })

    return {"content": [{"type": "text", "text": json.dumps({
        "commitments": items, "filter": filter_type, "count": len(items),
    }, indent=2, sort_keys=True)}]}


@tool(
    "otto_add",
    "Add a new commitment. Requires 'text'. Optional: 'who_to', 'deadline' (YYYY-MM-DD).",
    {"text": str, "who_to": str, "deadline": str},
)
async def otto_add(args: dict[str, Any]) -> dict[str, Any]:
    store = _get_store()
    text = args["text"]
    who_to = args.get("who_to", "unknown")
    deadline_str = args.get("deadline")

    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return {"content": [{"type": "text", "text": _json({
                "error": "Bad date format. Use YYYY-MM-DD.",
            })}], "is_error": True}

    commitment = Commitment(
        raw_message=text,
        commitment_text=text,
        who_to=who_to,
        source_chat="agent",
        deadline=deadline,
        deadline_source="manual" if deadline else "none",
    )
    cid = store.add(commitment)
    return {"content": [{"type": "text", "text": _json({
        "added": True, "id": cid, "text": text,
    })}]}


@tool(
    "otto_done",
    "Mark a commitment as done by short numeric ID.",
    {"short_id": int},
)
async def otto_done(args: dict[str, Any]) -> dict[str, Any]:
    store = _get_store()
    short_id = args["short_id"]
    active = store.get_active()

    if not active:
        return {"content": [{"type": "text", "text": _json({
            "error": "No active commitments.",
        })}], "is_error": True}

    id_map = build_id_map(active)
    uuid = id_map.get(short_id)
    if uuid is None:
        return {"content": [{"type": "text", "text": _json({
            "error": f"No commitment #{short_id}.",
        })}], "is_error": True}

    c = store.get(uuid)
    store.mark_done(uuid)

    state_store = _get_state_store()
    state_store.increment_nudges_completed()

    return {"content": [{"type": "text", "text": _json({
        "done": True, "text": c.commitment_text,
    })}]}


@tool(
    "otto_park",
    "Park a commitment guilt-free by short numeric ID.",
    {"short_id": int},
)
async def otto_park(args: dict[str, Any]) -> dict[str, Any]:
    store = _get_store()
    short_id = args["short_id"]
    active = store.get_active()

    if not active:
        return {"content": [{"type": "text", "text": _json({
            "error": "No active commitments.",
        })}], "is_error": True}

    id_map = build_id_map(active)
    uuid = id_map.get(short_id)
    if uuid is None:
        return {"content": [{"type": "text", "text": _json({
            "error": f"No commitment #{short_id}.",
        })}], "is_error": True}

    c = store.get(uuid)
    store.mark_parked(uuid)
    return {"content": [{"type": "text", "text": _json({
        "parked": True, "text": c.commitment_text,
    })}]}


@tool(
    "otto_nudge",
    "Run the follow-up nudge check. Constitutional gating may suppress this.",
    {},
)
async def otto_nudge(args: dict[str, Any]) -> dict[str, Any]:
    state_store = _get_state_store()
    state = state_store.load()
    suppression = should_suppress(state, "nudge")
    if suppression is not None:
        state_store.increment_suppressed()
        return {"content": [{"type": "text", "text": _json({
            "nudges": [], "suppressed": True, "reason": suppression.reason,
        })}]}

    store = _get_store()
    messages = check_and_nudge(store)

    if messages:
        for _ in messages:
            state_store.increment_nudges_sent()

    if not messages:
        return {"content": [{"type": "text", "text": _json({
            "nudges": [], "message": "Nothing to nudge about.",
        })}]}

    return {"content": [{"type": "text", "text": _json({
        "nudges": messages, "count": len(messages),
    })}]}


@tool(
    "otto_snooze",
    "Snooze a commitment. Duration: 30m, 4h, 2d.",
    {"short_id": int, "duration": str},
)
async def otto_snooze(args: dict[str, Any]) -> dict[str, Any]:
    store = _get_store()
    short_id = args["short_id"]
    duration = args["duration"]

    active = store.get_active()
    if not active:
        return {"content": [{"type": "text", "text": _json({
            "error": "No active commitments.",
        })}], "is_error": True}

    id_map = build_id_map(active)
    uuid = id_map.get(short_id)
    if uuid is None:
        return {"content": [{"type": "text", "text": _json({
            "error": f"No commitment #{short_id}.",
        })}], "is_error": True}

    delta = parse_duration(duration)
    if delta is None:
        return {"content": [{"type": "text", "text": _json({
            "error": "Invalid duration. Use e.g. 30m, 4h, 2d.",
        })}], "is_error": True}

    until = datetime.now(timezone.utc) + delta
    store.snooze(uuid, until)
    c = store.get(uuid)
    return {"content": [{"type": "text", "text": _json({
        "snoozed": True, "text": c.commitment_text, "until": until.isoformat(),
    })}]}


@tool(
    "otto_wip",
    "Add a work-in-progress note to a commitment.",
    {"short_id": int, "note": str},
)
async def otto_wip(args: dict[str, Any]) -> dict[str, Any]:
    store = _get_store()
    short_id = args["short_id"]
    note = args["note"]

    active = store.get_active()
    if not active:
        return {"content": [{"type": "text", "text": _json({
            "error": "No active commitments.",
        })}], "is_error": True}

    id_map = build_id_map(active)
    uuid = id_map.get(short_id)
    if uuid is None:
        return {"content": [{"type": "text", "text": _json({
            "error": f"No commitment #{short_id}.",
        })}], "is_error": True}

    store.add_note(uuid, note)
    c = store.get(uuid)
    return {"content": [{"type": "text", "text": _json({
        "noted": True, "text": c.commitment_text, "note": note,
    })}]}


# ---------------------------------------------------------------------------
# Cognitive state tools
# ---------------------------------------------------------------------------


@tool(
    "otto_energy_get",
    "Get current cognitive state: energy, burnout, momentum, nudge stats.",
    {},
)
async def otto_energy_get(args: dict[str, Any]) -> dict[str, Any]:
    state_store = _get_state_store()
    state = state_store.load()
    return {"content": [{"type": "text", "text": _json({
        "energy": state.energy,
        "burnout": state.burnout,
        "momentum": state.momentum,
        "nudges_sent_today": state.nudges_sent_today,
        "nudges_completed_today": state.nudges_completed_today,
        "nudge_effectiveness": round(state.nudge_effectiveness, 2),
        "suppressed_count": state.suppressed_count,
        "should_suppress_nudge": state.should_suppress_nudge,
    })}]}


@tool(
    "otto_energy_set",
    "Set energy level: high, medium, low, depleted.",
    {"level": str},
)
async def otto_energy_set(args: dict[str, Any]) -> dict[str, Any]:
    state_store = _get_state_store()
    level = args["level"]
    try:
        state_store.set_energy(level)
    except ValueError as e:
        return {"content": [{"type": "text", "text": _json({
            "error": str(e),
        })}], "is_error": True}

    result: dict[str, Any] = {"energy": level, "set": True}
    if level == "depleted":
        result["message"] = "OTTO will give you space. Your commitments are safe."
    elif level == "low":
        result["message"] = "OTTO will go easy. Only urgent things."
    return {"content": [{"type": "text", "text": _json(result)}]}


@tool(
    "otto_stats",
    "Show commitment statistics: active, done, parked counts and follow-up average.",
    {},
)
async def otto_stats(args: dict[str, Any]) -> dict[str, Any]:
    store = _get_store()
    counts = store.count()
    avg_raw = store.avg_follow_ups_done()
    return {"content": [{"type": "text", "text": _json({
        "active": counts.get("active", 0),
        "done": counts.get("done", 0),
        "parked": counts.get("parked", 0),
        "avg_follow_ups_before_done": round(avg_raw, 1) if avg_raw is not None else None,
    })}]}


# ---------------------------------------------------------------------------
# MCP server factory
# ---------------------------------------------------------------------------


ALL_COMMITMENT_TOOLS = [
    otto_list, otto_add, otto_done, otto_park,
    otto_nudge, otto_snooze, otto_wip,
    otto_energy_get, otto_energy_set, otto_stats,
]


def create_otto_mcp_server(
    name: str = "otto",
    version: str = "5.0.0",
) -> Any:
    """Create an in-process MCP server with all OTTO commitment tools."""
    return create_sdk_mcp_server(
        name=name,
        version=version,
        tools=ALL_COMMITMENT_TOOLS,
    )
