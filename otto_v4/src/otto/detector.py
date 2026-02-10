"""Commitment detector — calls Claude to identify promises in messages."""

from __future__ import annotations

import json
import os

import anthropic

from .log import get_logger

_log = get_logger(__name__)

from .models import Commitment

_SYSTEM_PROMPT = """\
You are a commitment detector. Given a WhatsApp message, determine if the sender is making a commitment — a promise to do something for someone.

Examples of commitments:
- "I'll send that over Monday"
- "Let me get back to you on that"
- "I'll take care of it"
- "Will do, by end of week"
- "I need to follow up with Sarah about the contract"

Examples of NOT commitments:
- "That sounds good"
- "Thanks!"
- "I think we should consider..."
- "Maybe next week"

If a commitment is found, respond with JSON:
{
    "found": true,
    "commitment_text": "what was promised",
    "who_to": "recipient name or 'unknown'",
    "deadline": "ISO date if mentioned, null if not",
    "deadline_source": "explicit" or "inferred" or "none",
    "confidence": 0.0-1.0
}

If no commitment, respond with:
{"found": false}

Respond ONLY with JSON. No explanation."""

_CONFIDENCE_THRESHOLD = float(os.environ.get("OTTO_CONFIDENCE_THRESHOLD", "0.7"))


async def detect_commitment(message: str, chat_name: str) -> Commitment | None:
    """Detect if a message contains a commitment. Returns Commitment or None."""
    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Chat: {chat_name}\nMessage: {message}"}
            ],
        )
    except Exception as e:
        _log.warning("API error: %s", e)
        return None

    raw_text = response.content[0].text.strip()

    # Claude sometimes wraps JSON in markdown code fences
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        # Drop first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw_text = "\n".join(lines).strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        _log.warning("JSON parse failed: %s", raw_text)
        return None

    if not data.get("found"):
        return None

    if data.get("confidence", 0) < _CONFIDENCE_THRESHOLD:
        return None

    deadline = None
    deadline_raw = data.get("deadline")
    if deadline_raw:
        try:
            from datetime import datetime
            deadline = datetime.fromisoformat(deadline_raw)
        except (ValueError, TypeError):
            pass

    return Commitment(
        raw_message=message,
        commitment_text=data["commitment_text"],
        who_to=data.get("who_to", "unknown"),
        source_chat=chat_name,
        deadline=deadline,
        deadline_source=data.get("deadline_source", "none"),
    )
